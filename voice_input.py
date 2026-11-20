"""
voice_input.py
--------------
Local voice recording and speech recognition for OmniSight.
Uses SoundDevice + Faster-Whisper.
"""

import threading

import numpy as np
import sounddevice as sd

from PyQt6.QtCore import QThread, pyqtSignal
from faster_whisper import WhisperModel


# Audio configuration
SAMPLE_RATE = 16000
CHANNELS = 1
MIC_DEVICE = 1

# Whisper configuration
MODEL_SIZE = "small"
MODEL_DEVICE = "cpu"
COMPUTE_TYPE = "int8"


# Shared model cache
_whisper_model = None
_model_lock = threading.Lock()


def get_whisper_model():

    global _whisper_model

    with _model_lock:

        if _whisper_model is None:

            print("[OmniSight Voice] Loading Whisper...")

            _whisper_model = WhisperModel(
                MODEL_SIZE,
                device=MODEL_DEVICE,
                compute_type=COMPUTE_TYPE
            )

            print("[OmniSight Voice] Whisper ready!")

    return _whisper_model


class VoiceWorker(QThread):

    status_changed = pyqtSignal(str)
    transcription_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):

        super().__init__(parent)

        self._stop_event = threading.Event()
        self._audio_chunks = []

    def stop_recording(self):

        self._stop_event.set()

    def run(self):

        try:

            self.status_changed.emit("Loading voice engine...")

            model = get_whisper_model()

            self._audio_chunks = []

            def audio_callback(
                indata,
                frames,
                time_info,
                status
            ):

                if status:
                    print(f"[OmniSight Voice] {status}")

                self._audio_chunks.append(
                    indata.copy()
                )

            self.status_changed.emit("Listening...")

            print("[OmniSight Voice] Recording started.")

            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="float32",
                device=MIC_DEVICE,
                callback=audio_callback
            ):

                while not self._stop_event.is_set():

                    self._stop_event.wait(0.1)

            print("[OmniSight Voice] Recording stopped.")

            if not self._audio_chunks:

                self.error_occurred.emit(
                    "No audio was recorded."
                )

                return

            audio = np.concatenate(
                self._audio_chunks,
                axis=0
            ).flatten()

            if len(audio) < SAMPLE_RATE * 0.3:

                self.error_occurred.emit(
                    "Recording was too short."
                )

                return

            self.status_changed.emit("Transcribing...")

            print("[OmniSight Voice] Transcribing...")

            segments, info = model.transcribe(
                audio,
                language=None,
                task="transcribe",
                vad_filter=True
            )

            text_parts = [
                segment.text.strip()
                for segment in segments
                if segment.text.strip()
            ]

            transcription = " ".join(text_parts)

            print(
                f"[OmniSight Voice] "
                f"Detected language: {info.language}"
            )

            print(
                f"[OmniSight Voice] "
                f"Transcription: {transcription}"
            )

            self.transcription_ready.emit(
                transcription
            )

        except Exception as exc:

            message = (
                f"{type(exc).__name__}: {exc}"
            )

            print(
                f"[OmniSight Voice] Error: {message}"
            )

            self.error_occurred.emit(message)