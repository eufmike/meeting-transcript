"""Tests for transcript parsing and models."""

from datetime import timedelta

from meeting_transcript.models import Speaker, Transcript, Utterance
from meeting_transcript.transcript import format_transcript, parse_raw_text


RAW = """\
Alice: Hello everyone, welcome to the meeting.
Bob: Thanks Alice, glad to be here.
Alice: Let's get started with the agenda.
Charlie: I have a quick question before we begin.
Bob: Sure Charlie, go ahead.
"""


def test_parse_raw_text_speaker_count():
    t = parse_raw_text(RAW, title="Test Meeting", date="2026-01-01")
    assert len(t.speakers) == 3


def test_parse_raw_text_utterance_count():
    t = parse_raw_text(RAW, title="Test Meeting", date="2026-01-01")
    assert len(t.utterances) == 5


def test_parse_raw_text_speaker_ids():
    t = parse_raw_text(RAW, title="Test Meeting", date="2026-01-01")
    ids = [s.id for s in t.speakers]
    assert ids == ["S1", "S2", "S3"]


def test_speaker_word_counts():
    t = parse_raw_text(RAW, title="Test Meeting", date="2026-01-01")
    counts = t.speaker_word_counts()
    assert counts["S1"] > 0
    assert counts["S2"] > 0
    assert counts["S3"] > 0


def test_utterances_by_speaker():
    t = parse_raw_text(RAW, title="Test Meeting", date="2026-01-01")
    alice = t.speakers[0]
    assert len(t.utterances_by_speaker(alice.id)) == 2


def test_format_transcript_contains_names():
    t = parse_raw_text(RAW, title="Team Sync", date="2026-01-01")
    output = format_transcript(t)
    assert "Alice" in output
    assert "Bob" in output
    assert "Team Sync" in output


def test_get_speaker_returns_none_for_unknown():
    t = Transcript(title="T", date="2026-01-01")
    assert t.get_speaker("X99") is None


def test_utterance_confidence_bounds():
    u = Utterance(
        speaker_id="S1",
        text="Hello",
        start=timedelta(seconds=0),
        end=timedelta(seconds=5),
        confidence=0.95,
    )
    assert u.confidence == 0.95


def test_speaker_model():
    s = Speaker(id="S1", name="Alice", role="Host")
    assert s.role == "Host"
