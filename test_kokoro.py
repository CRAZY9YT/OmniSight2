from kokoro import KPipeline
import soundfile as sf
import numpy as np

print("Loading Kokoro...")

pipeline = KPipeline(lang_code="b")

text = (
    "Good evening, sir. "
    "All systems are operational. "
    "How may I assist you?"
)

for speed in [0.87]:

    print(f"Generating George at speed {speed}...")

    generator = pipeline(
        text,
        voice="bm_george",
        speed=speed
    )

    chunks = [
        audio
        for _, _, audio in generator
    ]

    final_audio = np.concatenate(chunks)

    filename = f"george_{speed}.wav"

    sf.write(filename, final_audio, 24000)

    print(f"Saved {filename}")

print("Auditions complete!")