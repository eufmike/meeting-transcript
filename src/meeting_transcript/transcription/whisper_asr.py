"""Speech-to-text using OpenAI Whisper."""

from dataclasses import dataclass, field


@dataclass
class WhisperSegment:
    start: float
    end: float
    text: str
    words: list[dict[str, float]] = field(default_factory=list)


class WhisperTranscriber:
    """Wrapper around OpenAI Whisper for mixed-language transcription.

    Model sizes:
        large-v3  — best quality, best mixed-language handling (~3 GB RAM)
        medium    — balanced quality and speed (~1.5 GB)
        small     — fast, lower quality (~1 GB)
    """

    def __init__(self, model_size: str = "large-v3") -> None:
        import whisper

        self.model = whisper.load_model(model_size)

    def transcribe(
        self,
        audio_path: str,
        language: str | None = None,
        initial_prompt: str | None = None,
    ) -> list[WhisperSegment]:
        """Transcribe an audio file and return timestamped segments.

        Args:
            audio_path: Path to a 16 kHz mono WAV file.
            language: Primary language code (e.g. "zh"), or None for
                automatic per-segment detection (recommended for mixed audio).
            initial_prompt: Seed text that improves recognition of proper
                nouns and domain-specific terms.
        """
        result = self.model.transcribe(
            audio_path,
            language=language,
            task="transcribe",
            word_timestamps=True,
            initial_prompt=initial_prompt,
            condition_on_previous_text=True,
        )

        return [
            WhisperSegment(
                start=round(seg["start"], 3),
                end=round(seg["end"], 3),
                text=seg["text"].strip(),
                words=seg.get("words", []),
            )
            for seg in result["segments"]
        ]
