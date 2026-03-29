"""Prompt building and response parsing for action item extraction."""

from meeting_transcript.models import MeetingAnalysis, Transcript

SYSTEM_PROMPT = """\
You are a meeting assistant. Analyze the transcript below and return a JSON
object with exactly these keys:

{
  "summary": ["<key decision 1>", "<key decision 2>", ...],
  "action_items": [
    {
      "task": "<specific action>",
      "assignee": "<name from transcript>",
      "deadline": "<ISO 8601 date or null>",
      "priority": "high" | "medium" | "low",
      "context": "<relevant quote or null>"
    }
  ],
  "unresolved": ["<topic still open>", ...]
}

Return only valid JSON. No markdown fences, no explanation.\
"""


def build_prompt(transcript: Transcript) -> str:
    lines = []
    for u in transcript.utterances:
        total = int(u.start.total_seconds())
        m, s = divmod(total, 60)
        lines.append(f"[{m:02d}:{s:02d}] {u.speaker_id}: {u.text}")
    return "\n".join(lines)


def parse_response(raw_json: str, transcript: Transcript) -> MeetingAnalysis:
    import json
    import re

    # Strip markdown code fences if the model wraps the response
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_json.strip())
    data = json.loads(cleaned)
    return MeetingAnalysis(
        transcript_id=f"{transcript.date}_{transcript.title}",
        **data,
    )
