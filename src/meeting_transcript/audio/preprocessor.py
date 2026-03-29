"""Audio preprocessing: resample and normalize to 16 kHz mono WAV."""

from pathlib import Path

from pydub import AudioSegment


def preprocess(input_path: Path, output_path: Path) -> None:
    """Convert any audio file to 16 kHz mono WAV.

    Args:
        input_path: Source audio file (any format supported by pydub/ffmpeg).
        output_path: Destination WAV file path.
    """
    audio = AudioSegment.from_file(str(input_path))
    audio = audio.set_channels(1).set_frame_rate(16000)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    audio.export(str(output_path), format="wav")
