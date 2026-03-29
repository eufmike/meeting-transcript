"""Gemini API client for meeting analysis."""

from google import genai  # type: ignore[import-untyped]
from google.genai import types  # type: ignore[import-untyped]

from meeting_transcript.analysis.action_items import SYSTEM_PROMPT, build_prompt, parse_response
from meeting_transcript.models import MeetingAnalysis, Transcript


class GeminiAnalyzer:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def analyze(self, transcript: Transcript) -> MeetingAnalysis:
        response = self._client.models.generate_content(
            model=self._model,
            contents=build_prompt(transcript),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
            ),
        )
        return parse_response(response.text, transcript)
