"""Tests for prompt building and response parsing (no API calls)."""

import json
from datetime import timedelta

import pytest

from meeting_transcript.analysis.action_items import build_prompt, parse_response
from meeting_transcript.models import Speaker, Transcript, Utterance


def _make_transcript() -> Transcript:
    return Transcript(
        title="Family Sync",
        date="2026-03-28",
        speakers=[Speaker(id="Mom", name="Mom"), Speaker(id="Dad", name="Dad")],
        utterances=[
            Utterance(
                speaker_id="Mom",
                text="Let's book the flights soon.",
                start=timedelta(seconds=0),
                end=timedelta(seconds=10),
            ),
            Utterance(
                speaker_id="Dad",
                text="I'll handle it by Friday.",
                start=timedelta(seconds=11),
                end=timedelta(seconds=20),
            ),
        ],
    )


def test_build_prompt_contains_speakers() -> None:
    t = _make_transcript()
    prompt = build_prompt(t)
    assert "Mom" in prompt
    assert "Dad" in prompt


def test_build_prompt_contains_text() -> None:
    t = _make_transcript()
    prompt = build_prompt(t)
    assert "book the flights" in prompt
    assert "handle it by Friday" in prompt


def test_build_prompt_timestamp_format() -> None:
    t = _make_transcript()
    prompt = build_prompt(t)
    assert "[00:00]" in prompt
    assert "[00:11]" in prompt


def test_parse_response_valid() -> None:
    t = _make_transcript()
    raw = json.dumps({
        "summary": ["Book flights by Friday"],
        "action_items": [
            {
                "task": "Book flights",
                "assignee": "Dad",
                "deadline": "2026-04-04",
                "priority": "high",
                "context": "Dad said he'd handle it",
            }
        ],
        "unresolved": [],
    })
    analysis = parse_response(raw, t)
    assert analysis.transcript_id == "2026-03-28_Family Sync"
    assert len(analysis.action_items) == 1
    assert analysis.action_items[0].assignee == "Dad"


def test_parse_response_empty_action_items() -> None:
    t = _make_transcript()
    raw = json.dumps({"summary": ["No actions"], "action_items": [], "unresolved": []})
    analysis = parse_response(raw, t)
    assert analysis.action_items == []


def test_parse_response_invalid_json_raises() -> None:
    t = _make_transcript()
    with pytest.raises(json.JSONDecodeError):
        parse_response("not json", t)
