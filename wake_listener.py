"""
wake_listener.py
----------------
Local wake-word listener for OmniSight.

Supported wake phrases:
1. Omni, wake up.
2. Only wake up.
3. Hello.
4. Thank you.
5. Thank u.
6. Ready.
7. Started.
8. Stop.
"""

import queue
import threading
import re

import numpy as np
import sounddevice as sd

from PyQt6.QtCore import QThread, pyqtSignal

from voice_input import (
    get_whisper_model,
    SAMPLE_RATE,
    CHANNELS,
    MIC_DEVICE
)


class WakeListener(QThread):

    wake_detected = pyqtSignal()
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    CHUNK_SECONDS = 3

    def __init__(self, parent=None):
        super().__init__(parent)

        self._stop_event = threading.Event()
        self._audio_queue = queue.Queue()

    def stop(self):
        self._stop_event.set()

    @staticmethod
    def normalize(text):

        text = text.lower()

        text = re.sub(
            r"[^a-z\s]",
            " ",
            text
        )

        return " ".join(text.split())

    def run(self):

        try:

            self.status_changed.emit(
                "Loading wake-word engine..."
            )

            model = get_whisper_model()

            chunk_size = (
                SAMPLE_RATE * self.CHUNK_SECONDS
            )

            self._audio_queue = queue.Queue()

            def audio_callback(
                indata,
                frames,
                time_info,
                status
            ):

                if status:
                    print(
                        f"[OmniSight Wake] {status}"
                    )

                self._audio_queue.put(
                    indata.copy()
                )

            self.status_changed.emit(
                "Standby: say a wake phrase to activate OmniSight."
            )

            print(
                "[OmniSight Wake] Listening for wake phrases..."
            )

            audio_buffer = []

            wake_phrases = (
                "omni wake up",
                "only wake up",
                "hello",
                "thank you",
                "thank u",
                "ready",
                "started",
                "stop"
            )

            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="float32",
                device=MIC_DEVICE,
                callback=audio_callback
            ):

                while not self._stop_event.is_set():

                    try:

                        chunk = self._audio_queue.get(
                            timeout=0.25
                        )

                    except queue.Empty:
                        continue

                    audio_buffer.append(chunk)

                    audio = np.concatenate(
                        audio_buffer,
                        axis=0
                    ).flatten()

                    if len(audio) < chunk_size:
                        continue

                    audio_buffer.clear()

                    if self._stop_event.is_set():
                        break

                    segments, info = model.transcribe(
                        audio,
                        language="en",
                        task="transcribe",
                        vad_filter=True,
                        beam_size=1
                    )

                    transcription = " ".join(
                        segment.text.strip()
                        for segment in segments
                    )

                    normalized = self.normalize(
                        transcription
                    )

                    print(
                        f"[OmniSight Wake] Heard: {normalized}"
                    )

                    if any(
                        phrase in normalized
                        for phrase in wake_phrases
                    ):

                        print(
                            "[OmniSight Wake] WAKE PHRASE DETECTED!"
                        )

                        self.wake_detected.emit()

                        break

        except Exception as exc:

            message = (
                f"{type(exc).__name__}: {exc}"
            )

            print(
                f"[OmniSight Wake] Error: {message}"
            )

            self.error_occurred.emit(message)

        finally:

            self.status_changed.emit(
                "Wake listener stopped."
            )