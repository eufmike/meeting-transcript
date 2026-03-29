"""Voiceprint registration and speaker identification."""

from pathlib import Path

import numpy as np
from pyannote.audio import Inference, Model


class VoiceprintManager:
    # Cosine distance threshold for a match. At 0.35 the false-positive rate
    # on the VoxCeleb benchmark is approximately 5%. Tune via config.yaml
    # (voiceprint.match_threshold) if your recording conditions differ.
    DEFAULT_THRESHOLD = 0.35

    def __init__(
        self,
        hf_token: str,
        db_path: str | Path = "data/voiceprints",
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        model = Model.from_pretrained(
            "pyannote/wespeaker-voxceleb-resnet34-LM",
            token=hf_token,
        )
        self.inference = Inference(model, window="whole")
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.threshold = threshold
        self.profiles: dict[str, np.ndarray] = {}

    def register(self, name: str, audio_path: str | Path) -> None:
        """Record a reference embedding for a family member.

        Record at least 30 seconds of clean speech for best results.
        """
        embedding = self.inference(str(audio_path))
        np.save(self.db_path / f"{name}.npy", embedding)
        self.profiles[name] = embedding

    def load_profiles(self) -> None:
        """Load all saved voiceprints from disk."""
        for npy_file in self.db_path.glob("*.npy"):
            self.profiles[npy_file.stem] = np.load(npy_file)

    def identify(self, segment_embedding: np.ndarray) -> str:
        """Return the best-matching registered name, or 'Unknown'."""
        from scipy.spatial.distance import cosine

        best_name, best_dist = "Unknown", float("inf")
        for name, ref in self.profiles.items():
            dist = float(cosine(segment_embedding, ref))
            if dist < best_dist:
                best_name, best_dist = name, dist
        return best_name if best_dist < self.threshold else "Unknown"

    def build_speaker_map(
        self,
        segments: list,
        audio_path: str | Path,
    ) -> dict[str, str]:
        """Map pyannote speaker IDs to registered names.

        For each unique speaker label, extracts an embedding from the first
        segment and compares it against registered profiles.

        Returns:
            Dict mapping e.g. "SPEAKER_00" -> "Mom".
        """
        seen: dict[str, str] = {}
        for seg in segments:
            if seg.speaker in seen:
                continue
            embedding = self.inference(
                str(audio_path),
                excerpt={"onset": seg.start, "offset": seg.end},
            )
            seen[seg.speaker] = self.identify(embedding)
        return seen
