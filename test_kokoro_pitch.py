from kokoro import KPipeline
import soundfile as sf
import numpy as np
import librosa

print("Loading Kokoro...")

pipeline = KPipeline(lang_code="b")

text = (
    "Good evening, sir. "
    "All systems are operational. "
    "How may I assist you?"
)

print("Generating original George voice...")

generator = pipeline(
    text,
    voice="bm_george",
    speed=0.87
)

chunks = [audio for _, _, audio in generator]
original_audio = np.concatenate(chunks)

# Save original
sf.write("george_original.wav", original_audio, 24000)

# Generate pitch variations
for semitones in [-1, -2, -3]:

    print(f"Creating pitch variation: {semitones} semitones")

    pitched_audio = librosa.effects.pitch_shift(
        y=original_audio,
        sr=24000,
        n_steps=semitones
    )

    filename = f"george_pitch_{semitones}.wav"

    sf.write(filename, pitched_audio, 24000)

    print(f"Saved {filename}")

print("\nAll four auditions are ready!")