"""Core transcript processing logic."""

import json
from datetime import timedelta
from pathlib import Path

from .models import Speaker, Transcript, Utterance


def load_transcript(path: Path) -> Transcript:
    """Load a transcript from a JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return Transcript.model_validate(data)


def save_transcript(transcript: Transcript, path: Path) -> None:
    """Persist a transcript to a JSON file."""
    path.write_text(
        transcript.model_dump_json(indent=2),
        encoding="utf-8",
    )


def parse_raw_text(raw: str, title: str, date: str) -> Transcript:
    """Parse a plain-text transcript with lines like 'Speaker Name: text'.

    Each line is treated as a single utterance with auto-incremented timestamps
    of 1 minute per utterance. Speaker IDs are assigned in order of first
    appearance.
    """
    speakers: dict[str, Speaker] = {}
    utterances: list[Utterance] = []
    minute = 0

    for line in raw.strip().splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue

        name, _, text = line.partition(":")
        name = name.strip()
        text = text.strip()

        if name not in speakers:
            speaker_id = f"S{len(speakers) + 1}"
            speakers[name] = Speaker(id=speaker_id, name=name)

        utterances.append(
            Utterance(
                speaker_id=speakers[name].id,
                text=text,
                start=timedelta(minutes=minute),
                end=timedelta(minutes=minute + 1),
            )
        )
        minute += 1

    return Transcript(
        title=title,
        date=date,
        speakers=list(speakers.values()),
        utterances=utterances,
    )


def format_transcript(transcript: Transcript) -> str:
    """Return a human-readable transcript string."""
    lines: list[str] = [f"# {transcript.title}", f"Date: {transcript.date}", ""]
    for utterance in transcript.utterances:
        speaker = transcript.get_speaker(utterance.speaker_id)
        name = speaker.name if speaker else utterance.speaker_id
        start = _fmt_duration(utterance.start)
        lines.append(f"[{start}] {name}: {utterance.text}")
    return "\n".join(lines)


def _fmt_duration(delta: timedelta) -> str:
    total = int(delta.total_seconds())
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02}:{m:02}:{s:02}" if h else f"{m:02}:{s:02}"
