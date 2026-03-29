"""Microphone recording to WAV."""

from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf


def record(
    output_path: Path,
    duration: int,
    sample_rate: int = 16000,
) -> None:
    """Record from the default microphone and save as a 16 kHz mono WAV.

    Args:
        output_path: Destination file path.
        duration: Recording length in seconds.
        sample_rate: Target sample rate. Defaults to 16000 (required by Whisper).
    """
    audio: np.ndarray = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), audio, sample_rate)
