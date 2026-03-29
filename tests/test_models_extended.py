"""Tests for the new ActionItem and MeetingAnalysis models."""

import pytest
from pydantic import ValidationError

from meeting_transcript.models import ActionItem, MeetingAnalysis


def test_action_item_valid() -> None:
    item = ActionItem(task="Book flights", assignee="Dad", priority="high")
    assert item.deadline is None
    assert item.context is None


def test_action_item_all_fields() -> None:
    item = ActionItem(
        task="Research hotels",
        assignee="Mom",
        deadline="2026-04-15",
        priority="medium",
        context="Mom said she'd look into hotels.",
    )
    assert item.deadline == "2026-04-15"
    assert item.priority == "medium"


def test_action_item_invalid_priority() -> None:
    with pytest.raises(ValidationError):
        ActionItem(task="Do something", assignee="Alex", priority="critical")  # type: ignore[arg-type]


def test_meeting_analysis_valid() -> None:
    analysis = MeetingAnalysis(
        transcript_id="2026-03-28_family",
        summary=["Go to Japan", "Budget 150k NTD"],
        action_items=[
            ActionItem(task="Book flights", assignee="Dad", priority="high"),
        ],
        unresolved=["Osaka side trip"],
    )
    assert len(analysis.action_items) == 1
    assert len(analysis.unresolved) == 1


def test_meeting_analysis_empty_defaults() -> None:
    analysis = MeetingAnalysis(
        transcript_id="2026-03-28_family",
        summary=["One decision"],
    )
    assert analysis.action_items == []
    assert analysis.unresolved == []


def test_meeting_analysis_json_roundtrip() -> None:
    analysis = MeetingAnalysis(
        transcript_id="2026-03-28_test",
        summary=["Decision A"],
        action_items=[ActionItem(task="T", assignee="X", priority="low")],
        unresolved=[],
    )
    restored = MeetingAnalysis.model_validate_json(analysis.model_dump_json())
    assert restored == analysis
