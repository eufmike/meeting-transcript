"""Generate meeting notes markdown via Gemini, using SKILL.md as the system prompt."""

import csv
import json
from pathlib import Path

from google import genai  # type: ignore  # google-genai has no stubs
from google.genai import types  # type: ignore  # google-genai has no stubs

# Resolve paths relative to the package root (four levels up from this file)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SKILL_PATH = _REPO_ROOT / ".github" / "skills" / "meeting-notes" / "SKILL.md"
_TEMPLATE_PATH = _REPO_ROOT / "references" / "templates" / "meeting-notes.md"


def generate_notes(
    transcript_csv: Path,
    analysis_json: Path,
    output_path: Path,
    speaker_map: dict[str, str],
    api_key: str,
    model: str = "gemini-2.5-flash",
) -> str:
    """Generate a meeting notes markdown file using Gemini.

    The SKILL.md is used as the system prompt so Gemini follows the same
    instructions defined for GitHub Copilot and Claude Code slash commands.

    Args:
        transcript_csv:  Path to the transcript CSV (start, end, speaker, text).
        analysis_json:   Path to the MeetingAnalysis JSON.
        output_path:     Where to write the resulting markdown file.
        speaker_map:     Mapping of speaker IDs to real names,
                         e.g. {"SPEAKER_00": "媽媽", "SPEAKER_02": "爸爸"}.
        api_key:         Gemini API key.
        model:           Gemini model name.

    Returns:
        The generated markdown string.
    """
    skill_instructions = _SKILL_PATH.read_text(encoding="utf-8")
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")

    # Apply speaker map to CSV in-memory
    rows = list(csv.DictReader(transcript_csv.open(encoding="utf-8")))
    for row in rows:
        row["speaker"] = speaker_map.get(row["speaker"], row["speaker"])
    csv_text = _rows_to_text(rows)

    analysis = json.loads(analysis_json.read_text(encoding="utf-8"))
    analysis_text = json.dumps(analysis, ensure_ascii=False, indent=2)

    # Strip frontmatter from skill so only the instruction body reaches Gemini
    skill_body = _strip_frontmatter(skill_instructions)

    speaker_map_json = json.dumps(speaker_map, ensure_ascii=False, indent=2)
    user_content = f"""\
Output ONLY the filled-in markdown document — no preamble, no explanation, \
no trailing commentary. Start your response with the `#` title line and end it \
with the closing `</details>` tag of the Full Transcript section.

Speaker mapping (apply to all transcript rows — replace IDs with real names):
{speaker_map_json}

## Template

{template}

## Transcript CSV ({len(rows)} rows)

{csv_text}

## Analysis JSON

{analysis_text}
"""

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=skill_body,
        ),
    )

    notes: str = _extract_markdown(str(response.text).strip())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(notes, encoding="utf-8")
    return notes


def _rows_to_text(rows: list[dict[str, str]]) -> str:
    lines = ["start,end,speaker,text"]
    for r in rows:
        text = r["text"].replace('"', '""')
        lines.append(f'{r["start"]},{r["end"]},{r["speaker"]},"{text}"')
    return "\n".join(lines)


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter (--- ... ---) from a markdown file."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    return text[end + 4:].lstrip("\n") if end != -1 else text


def _extract_markdown(text: str) -> str:
    """Extract the markdown document from a Gemini response.

    Handles two common patterns:
    - Gemini wraps the output in a ```markdown ... ``` fence → extract the inner block.
    - Gemini adds a plain-text preamble before the # heading → strip it.
    """
    import re

    # Prefer an explicit ```markdown ... ``` fence
    match = re.search(r"```(?:markdown)?\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Strip any plain-text preamble before the first # heading
    heading = re.search(r"^# ", text, re.MULTILINE)
    if heading:
        return text[heading.start():].strip()

    return text
