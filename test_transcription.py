from faster_whisper import WhisperModel

print("[OmniSight] Loading Whisper model...")

model = WhisperModel(
    "small",
    device="cpu",
    compute_type="int8"
)

print("[OmniSight] Model loaded!")
print("[OmniSight] Transcribing mic_test.wav...")

segments, info = model.transcribe(
    "mic_test.wav",
    language=None,
    task="transcribe"
)

transcription = []

for segment in segments:
    transcription.append(segment.text)

result = " ".join(transcription).strip()

print("\n========== RESULTS ==========")
print("Detected language:", info.language)
print("Transcription:", result)
print("=============================")