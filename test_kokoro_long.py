import numpy as np
import soundfile as sf
from kokoro import KPipeline
from scipy.signal import butter, sosfilt

print("Loading Kokoro...")

pipeline = KPipeline(lang_code="b")

text = (
    "Good evening, sir. "

    "I've finished checking the system. "
    "Everything appears to be running smoothly. "

    "There is just one thing I'd like to bring to your attention. "

    "Your processor temperature is slightly higher than usual. "
    "Nothing alarming, but I'd recommend closing a few unnecessary applications. "

    "I've already prepared a summary of the system's performance. "

    "Would you like me to go through it with you? "
    "Or would you prefer a quick overview?"
)

print("Generating natural George voice...")

generator = pipeline(
    text,
    voice="bm_george",
    speed=0.87
)

chunks = [audio for _, _, audio in generator]
audio = np.concatenate(chunks).astype(np.float32)

print("Applying Smooth EQ...")

sr = 24000

low_sos = butter(2, 180, btype="lowpass", fs=sr, output="sos")
high_sos = butter(2, 3500, btype="highpass", fs=sr, output="sos")

low = sosfilt(low_sos, audio)
high = sosfilt(high_sos, audio)

audio = audio - 0.20 * high

peak = np.max(np.abs(audio))

if peak > 0.98:
    audio *= 0.98 / peak

sf.write("george_natural.wav", audio, sr)

print("Saved george_natural.wav")
print("Natural voice audition ready!")