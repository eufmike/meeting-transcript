"""Pydantic models for meeting transcripts."""

from datetime import timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field


class Speaker(BaseModel):
    id: str = Field(..., description="Unique speaker identifier, e.g. 'S1'")
    name: str = Field(..., description="Display name of the speaker")
    role: str | None = Field(default=None, description="Optional role, e.g. 'Host', 'Guest'")


class Utterance(BaseModel):
    speaker_id: str = Field(..., description="ID of the speaker")
    text: str = Field(..., description="Spoken text content")
    start: timedelta = Field(..., description="Start time within the meeting")
    end: timedelta = Field(..., description="End time within the meeting")
    confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Diarization confidence score"
    )
    words: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Word-level timestamps from Whisper: [{word, start, end, probability}]",
    )


class ActionItem(BaseModel):
    task: str = Field(..., description="Specific action to be taken")
    assignee: str = Field(..., description="Person responsible")
    deadline: str | None = Field(default=None, description="ISO 8601 date")
    priority: Literal["high", "medium", "low"] = Field(..., description="Urgency level")
    context: str | None = Field(
        default=None, description="Relevant quote from the transcript"
    )


class MeetingAnalysis(BaseModel):
    transcript_id: str = Field(..., description="<date>_<title>")
    summary: list[str] = Field(..., description="3–5 key decisions or conclusions")
    action_items: list[ActionItem] = Field(default_factory=list)
    unresolved: list[str] = Field(
        default_factory=list, description="Topics that were not resolved"
    )


class Transcript(BaseModel):
    title: str = Field(..., description="Meeting title")
    date: str = Field(..., description="Meeting date in ISO 8601 format")
    speakers: list[Speaker] = Field(default_factory=list)
    utterances: list[Utterance] = Field(default_factory=list)

    def get_speaker(self, speaker_id: str) -> Speaker | None:
        return next((s for s in self.speakers if s.id == speaker_id), None)

    def utterances_by_speaker(self, speaker_id: str) -> list[Utterance]:
        return [u for u in self.utterances if u.speaker_id == speaker_id]

    def speaker_word_counts(self) -> dict[str, int]:
        return {
            s.id: sum(len(u.text.split()) for u in self.utterances_by_speaker(s.id))
            for s in self.speakers
        }
