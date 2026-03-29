"""Speaker diarization using pyannote.audio."""

from dataclasses import dataclass
from pathlib import Path

import torch
from pyannote.audio import Pipeline


@dataclass
class DiarizationSegment:
    speaker: str  # e.g. "SPEAKER_00"
    start: float
    end: float


class SpeakerDiarizer:
    def __init__(self, hf_token: str, device: str = "mps") -> None:
        if device == "mps" and not torch.backends.mps.is_available():
            device = "cpu"

        self.pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=hf_token,
        ).to(torch.device(device))

    def diarize(
        self,
        audio_path: str | Path,
        num_speakers: int | None = None,
    ) -> list[DiarizationSegment]:
        """Run speaker diarization on a WAV file.

        Args:
            audio_path: Path to a 16 kHz mono WAV file.
            num_speakers: Expected speaker count. Providing this improves
                accuracy when the number of speakers is known in advance.

        Returns:
            List of DiarizationSegment ordered by start time.
        """
        params: dict[str, int] = {}
        if num_speakers is not None:
            params["num_speakers"] = num_speakers

        result = self.pipeline(str(audio_path), **params)

        # pyannote 4.x returns DiarizeOutput; 3.x returns Annotation directly
        annotation = getattr(result, "speaker_diarization", result)

        return [
            DiarizationSegment(
                speaker=speaker,
                start=round(turn.start, 3),
                end=round(turn.end, 3),
            )
            for turn, _, speaker in annotation.itertracks(yield_label=True)
        ]
