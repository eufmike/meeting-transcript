"""Tests for the timestamp alignment and merge logic."""

from datetime import timedelta

from meeting_transcript.alignment.merger import _merge_consecutive, align_segments
from meeting_transcript.diarization.speaker_id import DiarizationSegment
from meeting_transcript.models import Utterance
from meeting_transcript.transcription.whisper_asr import WhisperSegment


def _diar(*args: tuple[str, float, float]) -> list[DiarizationSegment]:
    return [DiarizationSegment(speaker=s, start=a, end=b) for s, a, b in args]


def _whisper(*args: tuple[float, float, str]) -> list[WhisperSegment]:
    return [WhisperSegment(start=a, end=b, text=t) for a, b, t in args]


def test_align_basic_assignment() -> None:
    diar = _diar(("SPEAKER_00", 0.0, 5.0), ("SPEAKER_01", 5.0, 10.0))
    whisper = _whisper((0.5, 4.5, "Hello"), (5.5, 9.5, "World"))
    result = align_segments(diar, whisper)
    assert result[0].speaker_id == "SPEAKER_00"
    assert result[1].speaker_id == "SPEAKER_01"


def test_align_max_overlap_wins() -> None:
    # Whisper segment overlaps mostly with SPEAKER_01
    diar = _diar(("SPEAKER_00", 0.0, 2.0), ("SPEAKER_01", 2.0, 6.0))
    whisper = _whisper((1.0, 5.0, "Mixed"))
    result = align_segments(diar, whisper)
    assert result[0].speaker_id == "SPEAKER_01"


def test_align_speaker_map_applied() -> None:
    diar = _diar(("SPEAKER_00", 0.0, 5.0))
    whisper = _whisper((0.0, 5.0, "Hi"))
    result = align_segments(diar, whisper, speaker_map={"SPEAKER_00": "Mom"})
    assert result[0].speaker_id == "Mom"


def test_align_unknown_speaker_when_no_overlap() -> None:
    diar = _diar(("SPEAKER_00", 10.0, 15.0))
    whisper = _whisper((0.0, 5.0, "No overlap"))
    result = align_segments(diar, whisper)
    assert result[0].speaker_id == "SPEAKER_UNKNOWN"


def test_align_empty_inputs() -> None:
    assert align_segments([], []) == []
    assert align_segments(_diar(("S0", 0.0, 5.0)), []) == []


def test_merge_consecutive_same_speaker() -> None:
    u1 = Utterance(speaker_id="A", text="Hello", start=timedelta(0), end=timedelta(seconds=2))
    u2 = Utterance(speaker_id="A", text="World", start=timedelta(seconds=2), end=timedelta(seconds=4))
    merged = _merge_consecutive([u1, u2])
    assert len(merged) == 1
    assert merged[0].text == "Hello World"
    assert merged[0].end == timedelta(seconds=4)


def test_merge_consecutive_different_speakers() -> None:
    u1 = Utterance(speaker_id="A", text="Hi", start=timedelta(0), end=timedelta(seconds=2))
    u2 = Utterance(speaker_id="B", text="Hey", start=timedelta(seconds=2), end=timedelta(seconds=4))
    merged = _merge_consecutive([u1, u2])
    assert len(merged) == 2


def test_merge_consecutive_empty() -> None:
    assert _merge_consecutive([]) == []


def test_align_preserves_words() -> None:
    diar = _diar(("SPEAKER_00", 0.0, 5.0))
    words = [{"word": "hi", "start": 0.1, "end": 0.5, "probability": 0.99}]
    whisper = [WhisperSegment(start=0.0, end=5.0, text="hi", words=words)]
    result = align_segments(diar, whisper)
    assert result[0].words == words


def test_merge_consecutive_words_combined() -> None:
    w1 = [{"word": "hello", "start": 0.0, "end": 0.5}]
    w2 = [{"word": "world", "start": 1.0, "end": 1.5}]
    u1 = Utterance(speaker_id="A", text="hello", start=timedelta(0), end=timedelta(seconds=1), words=w1)
    u2 = Utterance(speaker_id="A", text="world", start=timedelta(seconds=1), end=timedelta(seconds=2), words=w2)
    merged = _merge_consecutive([u1, u2])
    assert merged[0].words == w1 + w2
