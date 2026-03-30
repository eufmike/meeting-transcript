"""Generate meeting notes markdown via Gemini, using SKILL.md as the system prompt."""

import csv
import json
import re
from pathlib import Path

from google import genai  # type: ignore  # google-genai has no stubs
from google.genai import types  # type: ignore  # google-genai has no stubs

# Resolve paths relative to the package root (four levels up from this file)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SKILL_PATH = _REPO_ROOT / ".github" / "skills" / "meeting-notes" / "SKILL.md"
_TEMPLATES: dict[str, Path] = {
    "en": _REPO_ROOT / "references" / "templates" / "meeting-notes.md",
    "zh-TW": _REPO_ROOT / "references" / "templates" / "meeting-notes-zh-tw.md",
}

# CJK Unified Ideographs block (covers most Chinese characters)
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def detect_language(rows: list[dict[str, str]], sample: int = 20) -> str:
    """Return 'zh-TW' if the transcript is predominantly Chinese, else 'en'."""
    texts = [r["text"] for r in rows if r.get("text")][:sample]
    combined = " ".join(texts)
    if not combined:
        return "en"
    cjk_chars = len(_CJK_RE.findall(combined))
    total_alpha = sum(1 for c in combined if c.isalpha())
    if total_alpha == 0:
        return "en"
    return "zh-TW" if (cjk_chars / total_alpha) >= 0.5 else "en"


def generate_notes(
    transcript_csv: Path,
    analysis_json: Path,
    output_path: Path,
    speaker_map: dict[str, str],
    api_key: str,
    model: str = "gemini-2.5-flash",
    lang: str = "auto",
) -> str:
    """Generate a meeting notes markdown file using Gemini.

    The SKILL.md is used as the system prompt so Gemini follows the same
    instructions defined for GitHub Copilot and Claude Code slash commands.

    Args:
        transcript_csv:  Path to the transcript CSV (start, end, speaker, text).
        analysis_json:   Path to the MeetingAnalysis JSON.
        output_path:     Where to write the resulting markdown file.
        speaker_map:     Mapping of speaker IDs to real names.
        api_key:         Gemini API key.
        model:           Gemini model name.
        lang:            Output language: "auto" | "zh-TW" | "en".
                         "auto" detects from the transcript content.
    """
    skill_instructions = _SKILL_PATH.read_text(encoding="utf-8")

    # Apply speaker map to CSV in-memory
    rows = list(csv.DictReader(transcript_csv.open(encoding="utf-8")))
    for row in rows:
        row["speaker"] = speaker_map.get(row["speaker"], row["speaker"])
    csv_text = _rows_to_text(rows)

    # Resolve language and template
    resolved_lang = detect_language(rows) if lang == "auto" else lang
    template_path = _TEMPLATES.get(resolved_lang, _TEMPLATES["en"])
    template = template_path.read_text(encoding="utf-8")

    analysis = json.loads(analysis_json.read_text(encoding="utf-8"))
    analysis_text = json.dumps(analysis, ensure_ascii=False, indent=2)

    # Strip frontmatter from skill so only the instruction body reaches Gemini
    skill_body = _strip_frontmatter(skill_instructions)

    lang_instruction = (
        "Write the entire document in Traditional Chinese (繁體中文). "
        "All section headings, metadata labels, summaries, topic headings, and "
        "action item descriptions must be in Traditional Chinese — not Simplified Chinese. "
        "Preserve the original transcript text verbatim."
        if resolved_lang == "zh-TW"
        else "Write the document in English."
    )

    speaker_map_json = json.dumps(speaker_map, ensure_ascii=False, indent=2)
    user_content = f"""\
Output ONLY the filled-in markdown document — no preamble, no explanation, \
no trailing commentary. Start your response with the `#` title line. \
Do NOT include a full transcript section.

Language instruction: {lang_instruction}

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
    # Prefer an explicit ```markdown ... ``` fence
    match = re.search(r"```(?:markdown)?\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Strip any plain-text preamble before the first # heading
    heading = re.search(r"^# ", text, re.MULTILINE)
    if heading:
        return text[heading.start():].strip()

    return text
