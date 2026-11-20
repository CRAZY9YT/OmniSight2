import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt
from pydub import AudioSegment

# Load original Kokoro audio
audio, sr = sf.read("george_original.wav")

# Convert to float if necessary
audio = audio.astype(np.float32)


def process_audio(audio, sr, low_gain=1.0, high_gain=1.0):
    result = audio.copy()

    # Warmth: gentle low-frequency boost
    low_sos = butter(
        2, 180, btype="lowpass",
        fs=sr, output="sos"
    )
    low = sosfilt(low_sos, result)

    # High-frequency detail
    high_sos = butter(
        2, 3500, btype="highpass",
        fs=sr, output="sos"
    )
    high = sosfilt(high_sos, result)

    # Blend frequency ranges
    result = result + (low_gain - 1) * low
    result = result + (high_gain - 1) * high

    # Prevent clipping
    peak = np.max(np.abs(result))
    if peak > 0.98:
        result *= 0.98 / peak

    return result


versions = {
    "warm": (1.20, 1.0),
    "smooth": (1.0, 0.80),
    "balanced": (1.15, 0.85),
}

for name, (low, high) in versions.items():

    processed = process_audio(
        audio, sr,
        low_gain=low,
        high_gain=high
    )

    filename = f"george_{name}.wav"
    sf.write(filename, processed, sr)

    print(f"Created: {filename}")

print("\nEQ auditions ready!")