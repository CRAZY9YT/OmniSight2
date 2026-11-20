"""
ask_pipeline.py
---------------
OmniSight AI request pipeline.
Talkback only activates for voice-originated questions.
"""

import csv
import os
import threading
import time
from datetime import datetime

from gemini_client import GeminiRequestError
from voice_output import VoiceOutput


LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "latency_log.csv"
)

LOG_COLUMNS = [
    "timestamp", "outcome", "capture_ms", "encode_ms",
    "request_ms", "total_ms", "image_kb", "attempts"
]


class AskPipeline:

    def __init__(
        self,
        engine,
        client,
        ui,
        log_path: str | None = LOG_PATH,
        clock=time.perf_counter
    ):

        self.engine = engine
        self.client = client
        self.ui = ui
        self.log_path = log_path
        self._clock = clock

        self._busy = threading.Lock()
        self._pending_question = None

        self.voice = VoiceOutput()

        print("[OmniSight] Talkback initialized.")

    # ======================================
    # SUBMIT QUESTION
    # ======================================

    def submit(self) -> bool:

        print("[DEBUG] Question requested")

        if not self._busy.acquire(blocking=False):

            self.ui.show_status(
                "Still working on the previous question."
            )

            return False

        callback_state = {"started": False}

        def on_question_received(question, voice_request=False):

            print(f"[DEBUG] Question received: {question}")

            if callback_state["started"]:
                print("[DEBUG] Duplicate dialog callback ignored.")
                return

            if not question:

                callback_state["started"] = True
                self._pending_question = None
                self._busy.release()

                print("[DEBUG] Dialog cancelled or empty.")
                return

            callback_state["started"] = True

            self._start_worker(
                question,
                voice_request
            )

        self.ui.set_question_callback(on_question_received)

        print("[DEBUG] Opening question dialog...")

        self.ui.ask_requested.emit()

        return True

    # ======================================
    # START WORKER
    # ======================================

    def _start_worker(self, question, voice_request):

        self._pending_question = question

        thread = threading.Thread(
            target=self._run,
            args=(question, voice_request),
            name="omnisight-ask",
            daemon=True
        )

        thread.start()

        print(
            f"[DEBUG] AI worker started. "
            f"Voice request: {voice_request}"
        )

    # ======================================
    # SCREEN DETECTION
    # ======================================

    @staticmethod
    def _needs_screen(question: str) -> bool:

        q = question.lower().strip()

        screen_keywords = [
            "screen", "see", "look", "show", "read", "find",
            "what is", "what's", "whats", "where", "which",
            "this", "here", "open", "window", "browser",
            "code", "error", "image", "text on", "says",
            "written", "display", "monitor", "tab"
        ]

        return any(kw in q for kw in screen_keywords)

    # ======================================
    # MAIN PIPELINE
    # ======================================

    def _run(self, question, voice_request):

        t = {}
        outcome = "ok"
        image_bytes = 0
        start = self._clock()

        needs_screen = self._needs_screen(question)

        try:

            self.ui.show_thinking()

            if needs_screen:

                s = self._clock()
                frame = self.engine.capture_frame()
                t["capture"] = self._clock() - s

                s = self._clock()
                jpeg = self.engine.encode_for_ai(frame)
                image_bytes = len(jpeg)
                t["encode"] = self._clock() - s

                scan_done = threading.Event()

                def _launch_scan():
                    self.ui.show_scan(
                        on_complete=scan_done.set
                    )

                from PyQt6.QtCore import QTimer

                QTimer.singleShot(0, _launch_scan)

                scan_done.wait(timeout=3.0)

                s = self._clock()

                answer = self.client.ask_direct_mode(
                    jpeg,
                    question
                )

                t["request"] = self._clock() - s

            else:

                t["capture"] = 0
                t["encode"] = 0

                s = self._clock()

                answer = self.client.ask_text_only(
                    question
                )

                t["request"] = self._clock() - s

            self.ui.show_response(answer)

            if voice_request:

                print(
                    "[OmniSight] Voice-originated answer. "
                    "Starting talkback."
                )

                self.voice.speak_async(answer)

            else:

                print(
                    "[OmniSight] Text-originated answer. "
                    "Talkback disabled."
                )

        except (GeminiRequestError, RuntimeError) as exc:

            outcome = "error"

            print(
                f"[OmniSight] AI request failed: {exc}"
            )

            self.ui.show_response(f"⚠ {exc}")

        except Exception as exc:

            outcome = "error"

            print(
                f"[OmniSight] Unexpected error "
                f"({type(exc).__name__}): {exc}"
            )

            self.ui.show_response(
                f"⚠ Unexpected error "
                f"({type(exc).__name__}): {exc}"
            )

        finally:

            total = self._clock() - start

            self.ui.show_status(
                self._status_text(
                    outcome,
                    total,
                    t,
                    needs_screen
                )
            )

            self._log(
                outcome,
                total,
                t,
                image_bytes
            )

            self._pending_question = None

            self._busy.release()

    # ======================================
    # STATUS
    # ======================================

    @staticmethod
    def _status_text(
        outcome: str,
        total: float,
        t: dict,
        used_screen: bool
    ) -> str:

        if outcome != "ok":

            return (
                f"Failed after {total:.1f}s. "
                "Press Ctrl+Shift+Space to retry."
            )

        if used_screen:

            return (
                f"Done in {total:.1f}s "
                f"(capture {t['capture'] * 1000:.0f} ms, "
                f"encode {t['encode'] * 1000:.0f} ms, "
                f"AI {t['request']:.1f}s)"
            )

        return f"Done in {total:.1f}s (chat mode)"

    # ======================================
    # LATENCY LOGGING
    # ======================================

    def _log(self, outcome, total, t, image_bytes):

        if not self.log_path:
            return

        try:

            new_file = not os.path.exists(
                self.log_path
            )

            with open(
                self.log_path,
                "a",
                newline="",
                encoding="utf-8"
            ) as f:

                w = csv.writer(f)

                if new_file:
                    w.writerow(LOG_COLUMNS)

                w.writerow([
                    datetime.now().isoformat(
                        timespec="seconds"
                    ),
                    outcome,
                    round(
                        t.get("capture", 0) * 1000
                    ),
                    round(
                        t.get("encode", 0) * 1000
                    ),
                    round(
                        t.get("request", 0) * 1000
                    ),
                    round(total * 1000),
                    round(image_bytes / 1024),
                    getattr(
                        self.client,
                        "last_attempts",
                        ""
                    ),
                ])

        except Exception as exc:

            print(
                f"[OmniSight] Latency log write failed: {exc}"
            )