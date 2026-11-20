import threading
import queue

import numpy as np
import sounddevice as sd

from kokoro import KPipeline
from scipy.signal import butter, sosfilt


class VoiceOutput:

    def __init__(self):

        self.voice = "bm_george"
        self.speed = 0.94
        self.sample_rate = 24000

        self._queue = queue.Queue(maxsize=1)
        self._lock = threading.Lock()
        self._current_cancel = None
        self._worker = None
        self._pipeline = None
        self._stream = None

        print("[VOICE] Voice output initialized.")

    def speak_async(self, text):

        if not text or not text.strip():
            return

        with self._lock:

            if self._current_cancel:
                self._current_cancel.set()

            if self._stream is not None:
                try:
                    self._stream.abort()
                except Exception:
                    pass
                self._stream = None

            sd.stop()

            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break

            cancel_event = threading.Event()
            self._current_cancel = cancel_event

            self._queue.put((text, cancel_event))

            if self._worker is None or not self._worker.is_alive():

                self._worker = threading.Thread(
                    target=self._worker_loop,
                    name="omnisight-voice",
                    daemon=True
                )

                self._worker.start()

    def _load_pipeline(self):

        if self._pipeline is None:

            print("[VOICE] Loading Kokoro...")

            self._pipeline = KPipeline(lang_code="b")

            print("[VOICE] George is ready.")

    def _apply_smooth_eq(self, audio):

        high_sos = butter(
            2,
            3500,
            btype="highpass",
            fs=self.sample_rate,
            output="sos"
        )

        high = sosfilt(high_sos, audio)

        processed = audio - 0.20 * high

        peak = np.max(np.abs(processed))

        if peak > 0.98:
            processed *= 0.98 / peak

        return processed.astype(np.float32)

    def _worker_loop(self):

        try:
            self._load_pipeline()

        except Exception as exc:
            print(f"[VOICE] Kokoro loading failed: {exc}")
            return

        while True:

            try:
                text, cancel_event = self._queue.get(timeout=1)

            except queue.Empty:
                return

            if cancel_event.is_set():
                continue

            stream = None

            try:

                print("[VOICE] Generating streaming speech...")

                generator = self._pipeline(
                    text,
                    voice=self.voice,
                    speed=self.speed
                )

                for _, _, chunk in generator:

                    if cancel_event.is_set():
                        break

                    audio = np.asarray(
                        chunk,
                        dtype=np.float32
                    )

                    audio = self._apply_smooth_eq(audio)

                    if cancel_event.is_set():
                        break

                    if stream is None:

                        stream = sd.OutputStream(
                            samplerate=self.sample_rate,
                            channels=1,
                            dtype="float32"
                        )

                        stream.start()

                        with self._lock:
                            self._stream = stream

                        print("[VOICE] Speaking...")

                    # Send each generated chunk directly to playback.
                    stream.write(audio.reshape(-1, 1))

                if stream is not None:

                    if cancel_event.is_set():
                        stream.abort()
                    else:
                        stream.stop()

                    stream.close()

                    with self._lock:
                        if self._stream is stream:
                            self._stream = None

                if cancel_event.is_set():
                    print("[VOICE] Speech interrupted.")
                else:
                    print("[VOICE] Playback complete.")

            except Exception as exc:

                if stream is not None:
                    try:
                        stream.abort()
                        stream.close()
                    except Exception:
                        pass

                with self._lock:
                    if self._stream is stream:
                        self._stream = None

                print(
                    f"[VOICE] Speech error "
                    f"({type(exc).__name__}): {exc}"
                )

    def stop(self):

        with self._lock:

            if self._current_cancel:
                self._current_cancel.set()

            if self._stream is not None:
                try:
                    self._stream.abort()
                except Exception:
                    pass

                self._stream = None

            sd.stop()

        print("[VOICE] Playback stopped.")