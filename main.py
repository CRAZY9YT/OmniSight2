"""
main.py
-------
OmniSight AI entry point.
"""

import os
import sys
import keyboard

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal

from ask_pipeline import AskPipeline
from delta_engine import DeltaEngine
from sidecar_ui import SidecarWindow
from live_viewer import LiveOverlay
from live_monitor import LiveMonitor
from live_voice import LiveVoiceController
from wake_listener import WakeListener


# ======================================
# HOTKEYS
# ======================================

HOTKEY = "ctrl+shift+space"

LIVE_HOTKEY = "ctrl+shift+l"

LIVE_VOICE_HOTKEY = "ctrl+shift+v"

LIVE_STOP_SPEECH_HOTKEY = "ctrl+shift+b"

WAKE_ARM_HOTKEY = "ctrl+shift+j"


# ======================================
# PROVIDER
# ======================================

PROVIDER = os.environ.get(
    "OMNISIGHT_PROVIDER",
    "local"
).lower()


# ======================================
# HOTKEY BRIDGE
# ======================================

class HotkeyBridge(QObject):

    toggle_live = pyqtSignal()

    toggle_live_voice = pyqtSignal()

    stop_live_speech = pyqtSignal()

    arm_wake = pyqtSignal()


# ======================================
# MAIN
# ======================================

def main():

    print("[OmniSight] Starting up...")

    print(
        f"[OmniSight] Selected provider: {PROVIDER.upper()}"
    )

    # ======================================
    # AI CLIENT
    # ======================================

    try:

        if PROVIDER == "local":

            from local_client import LocalClient

            client = LocalClient()

        elif PROVIDER == "gemini":

            from gemini_client import GeminiClient

            client = GeminiClient()

        else:

            raise ValueError(
                f"Unknown provider: {PROVIDER}"
            )

    except Exception as exc:

        print(
            f"[OmniSight] Startup error: {exc}"
        )

        sys.exit(1)

    # ======================================
    # APPLICATION
    # ======================================

    app = QApplication(sys.argv)

    app.setQuitOnLastWindowClosed(False)

    # ======================================
    # SIDECAR
    # ======================================

    sidecar = SidecarWindow()

    sidecar.show()

    # ======================================
    # LIVE OVERLAY
    # ======================================

    live_overlay = LiveOverlay()

    # ======================================
    # SCREEN ENGINE
    # ======================================

    delta_engine = DeltaEngine()

    delta_engine.add_excluded_window(
        int(sidecar.winId())
    )

    # ======================================
    # HOTKEY BRIDGE
    # ======================================

    bridge = HotkeyBridge()

    # ======================================
    # NORMAL Q&A PIPELINE
    # ======================================

    pipeline = AskPipeline(
        delta_engine,
        client,
        sidecar
    )

    # ======================================
    # LIVE MONITOR
    # ======================================

    monitor = LiveMonitor(
        delta_engine,
        client,
        sidecar.show_live_update,
        sidecar.show_status
    )

    # ======================================
    # LIVE VOICE CONTROLLER
    # ======================================

    live_voice = LiveVoiceController(
        engine=delta_engine,
        client=client,
        monitor=monitor,
        voice_output=pipeline.voice,
        sidecar=sidecar
    )

    # ======================================
    # WAKE WORD STATE
    # ======================================

    wake_listener = None

    wake_armed = False

    # ======================================
    # START WAKE LISTENER
    # ======================================

    def start_wake_listener():

        nonlocal wake_listener

        if not wake_armed:
            return

        if live_overlay.isVisible():
            return

        if wake_listener is not None:

            if wake_listener.isRunning():
                return

        wake_listener = WakeListener()

        wake_listener.wake_detected.connect(
            handle_wake_word
        )

        wake_listener.status_changed.connect(
            sidecar.show_status
        )

        wake_listener.error_occurred.connect(
            lambda error: print(
                f"[OmniSight Wake] {error}"
            )
        )

        wake_listener.start()

        print(
            "[OmniSight] Wake listener started."
        )

    # ======================================
    # STOP WAKE LISTENER
    # ======================================

    def stop_wake_listener():

        nonlocal wake_listener

        if wake_listener is None:
            return

        if wake_listener.isRunning():

            wake_listener.stop()

            wake_listener.wait(4000)

        wake_listener = None

    # ======================================
    # ARM WAKE DETECTION
    # ======================================

    def arm_wake_detection():

        nonlocal wake_armed

        if wake_armed:

            print(
                "[OmniSight] Wake detection is already armed."
            )

            return

        wake_armed = True

        print(
            "[OmniSight] Wake detection ARMED!"
        )

        sidecar.show_status(
            'Standby: say "Omni, wake up."'
        )

        start_wake_listener()

    bridge.arm_wake.connect(
        arm_wake_detection
    )

    # ======================================
    # LIVE TOGGLE
    # ======================================

    def toggle_live():

        if live_overlay.isVisible():

            live_overlay.toggle_live()

            live_voice.set_live_active(False)

            monitor.stop()

            print(
                "[OmniSight] LIVE mode deactivated."
            )

            if wake_armed:
                start_wake_listener()

        else:

            stop_wake_listener()

            live_overlay.toggle_live()

            monitor.start()

            live_voice.set_live_active(True)

            print(
                "[OmniSight] LIVE mode activated."
            )

    bridge.toggle_live.connect(
        toggle_live
    )

    # ======================================
    # WAKE WORD ACTIVATION
    # ======================================

    def handle_wake_word():

        if live_overlay.isVisible():
            return

        print(
            "[OmniSight] Wake phrase recognised!"
        )

        toggle_live()

        pipeline.voice.speak_async(
            "Hello sir, all functions operational. "
            "How may I help you today?"
        )

    # ======================================
    # LIVE VOICE CONNECTIONS
    # ======================================

    bridge.toggle_live_voice.connect(
        live_voice.toggle_recording
    )

    bridge.stop_live_speech.connect(
        live_voice.stop_speech
    )

    # ======================================
    # GLOBAL HOTKEYS
    # ======================================

    keyboard.add_hotkey(
        HOTKEY,
        pipeline.submit
    )

    keyboard.add_hotkey(
        LIVE_HOTKEY,
        bridge.toggle_live.emit
    )

    keyboard.add_hotkey(
        LIVE_VOICE_HOTKEY,
        bridge.toggle_live_voice.emit
    )

    keyboard.add_hotkey(
        LIVE_STOP_SPEECH_HOTKEY,
        bridge.stop_live_speech.emit
    )

    keyboard.add_hotkey(
        WAKE_ARM_HOTKEY,
        bridge.arm_wake.emit
    )

    # ======================================
    # CLEANUP
    # ======================================

    def cleanup():

        print(
            "[OmniSight] Shutting down..."
        )

        stop_wake_listener()

        live_voice.shutdown()

        monitor.stop()

        keyboard.unhook_all()

    app.aboutToQuit.connect(
        cleanup
    )

    # ======================================
    # STARTUP
    # ======================================

    print("[OmniSight] Ready!")

    print(
        f"[OmniSight] Ask: {HOTKEY.upper()}"
    )

    print(
        f"[OmniSight] LIVE toggle: {LIVE_HOTKEY.upper()}"
    )

    print(
        f"[OmniSight] LIVE voice: {LIVE_VOICE_HOTKEY.upper()}"
    )

    print(
        f"[OmniSight] Stop speech: {LIVE_STOP_SPEECH_HOTKEY.upper()}"
    )

    print(
        f"[OmniSight] Enable wake detection: {WAKE_ARM_HOTKEY.upper()}"
    )

    print(
        "[OmniSight] Wake detection is DISABLED."
    )

    sidecar.show_status(
        "Press CTRL + SHIFT + J to enable wake detection."
    )

    sys.exit(
        app.exec()
    )


# ======================================
# ENTRY POINT
# ======================================

if __name__ == "__main__":

    main()