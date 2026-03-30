# AGENTS.md — Meeting Transcript Project

This file is the authoritative guide for AI agents (Claude Code, GitHub Copilot,
Cursor, Codex, etc.) working in this repository. Read it fully before making changes.

---

## AI agent compatibility

This project is designed to work with **Claude Code** and **GitHub Copilot** (and any
agent that respects the emerging shared conventions).

### Source of truth: `.github/`

All shared AI content lives under `.github/` so it is version-controlled, visible in
pull requests, and readable by every tool without per-tool duplication:

```text
.github/
├── agents/                        # agent persona definitions
│   └── transcript-agent.md        # Claude Code reads via .claude/agents symlink
├── commands/                      # slash-command prompts (Claude Code: /command-name)
│   ├── test.md
│   └── add-speaker.md
├── skills/                        # reusable task recipes
│   ├── quality-check/
│   │   └── SKILL.md               # dir name MUST match `name` frontmatter (Copilot rule)
│   └── new-command/
│       └── SKILL.md
└── copilot-instructions.md        # Copilot reads this on every request (monolithic)
```

### `.claude/` — symlinks only

`.claude/` contains Claude Code–specific config. `commands/` and `agents/` are
**symlinks** into `.github/` so both tools stay in sync automatically:

```text
.claude/
├── settings.json                  # Claude Code permissions (tool-specific, not symlinked)
├── commands -> ../.github/commands
└── agents  -> ../.github/agents
```

**Rule: never create files directly inside `.claude/commands/` or `.claude/agents/`.**
Add them to `.github/` — the symlinks propagate them to Claude Code.

### Loading flow at initialization

| Topic | Claude Code | GitHub Copilot |
| --- | --- | --- |
| **Instructions** | Walks ancestor dirs for `CLAUDE.md`; loads `~/.claude/CLAUDE.md` | `.github/copilot-instructions.md` only — no imports |
| **`@file` imports** | Supported in `CLAUDE.md`; resolved relative to that file, max 5 hops | **Not supported** — instructions must be monolithic |
| **Commands / prompts** | `.claude/commands/*.md` auto-discovered at startup | No dedicated commands dir; use Skills |
| **Agents** | `.claude/agents/*.md` auto-discovered at startup | Not applicable |
| **Skills** | `.claude/commands/` (flat `.md` files) | `.github/skills/<name>/SKILL.md` — `name` frontmatter must match directory name |
| **Subdirectory rules** | Each subdirectory can have its own `CLAUDE.md`; lazy-loaded when Claude reads files there | Not supported |

---

## Project purpose

A CLI tool that ingests meeting recordings or plain-text transcripts and produces
structured, speaker-identified output. Core responsibilities:

1. **Parse** raw text in `Speaker Name: text` format
2. **Identify speakers** and assign stable IDs
3. **Serialize** results to JSON (Pydantic models)
4. **Display** formatted transcripts and per-speaker statistics

---

## Tech stack

| Layer | Tool | Notes |
| --- | --- | --- |
| Environment | [pixi](https://pixi.sh) | `pixi.toml` is the single source of truth for deps |
| Data models | [Pydantic v2](https://docs.pydantic.dev/latest/) | Strict models in `models.py` |
| CLI | [Typer](https://typer.tiangolo.com) + Rich | Three commands: `parse`, `show`, `stats` |
| Linting | ruff | Config in `pyproject.toml` |
| Type checking | mypy (strict) | `mypy src` must pass clean |
| Tests | pytest | All tests in `tests/` |

---

## Repository layout

```text
src/meeting_transcript/
├── __init__.py            # package version only
├── models.py              # Pydantic models: Speaker, Utterance, Transcript,
│                          #   ActionItem, MeetingAnalysis
├── transcript.py          # Pure functions: parse, load, save, format
├── main.py                # Typer CLI: parse, show, stats, record, process, analyze
├── audio/
│   ├── recorder.py        # microphone → 16 kHz mono WAV
│   └── preprocessor.py    # resample / normalize any audio file
├── diarization/
│   ├── speaker_id.py      # pyannote 3.x → list[DiarizationSegment]
│   └── voiceprint.py      # voiceprint registration and cosine matching
├── transcription/
│   └── whisper_asr.py     # Whisper → list[WhisperSegment]
├── alignment/
│   └── merger.py          # max-overlap merge → list[Utterance]
└── analysis/
    ├── action_items.py    # prompt building and JSON response parsing
    └── gemini_client.py   # Gemini Flash API client

tests/
├── test_transcript.py
├── test_alignment.py       # merger.py unit tests (no hardware required)
├── test_models_extended.py # ActionItem, MeetingAnalysis validation
└── test_analysis.py        # prompt/parse logic with mocked API

config.yaml                 # API keys and model settings (gitignored)

references/
├── plans/                      # technical specs and planning docs
└── templates/
    └── meeting-notes.md        # mustache-style template for /meeting-notes skill

.github/
├── agents/                     # agent persona definitions
│   └── transcript-agent.md
├── commands/                   # slash commands / prompts (source of truth)
│   ├── test.md
│   ├── add-speaker.md
│   └── meeting-notes.md -> ../skills/meeting-notes/SKILL.md  # symlink
├── skills/                     # reusable task recipes (Copilot: dir name = `name`)
│   ├── quality-check/SKILL.md
│   ├── new-command/SKILL.md
│   └── meeting-notes/SKILL.md  # generate markdown meeting notes from CSV + JSON
├── workflows/                  # CI pipelines
├── copilot-instructions.md
├── PULL_REQUEST_TEMPLATE.md
└── ISSUE_TEMPLATE/

.claude/
├── settings.json               # Claude Code permissions (tool-specific, not symlinked)
├── commands -> ../.github/commands   # symlink — never add files here directly
└── agents  -> ../.github/agents     # symlink — never add files here directly

pixi.toml             # env + tasks
pyproject.toml        # build, ruff, mypy, pytest config
AGENTS.md             # this file — read by all agents
CLAUDE.md             # thin pointer → AGENTS.md
```

---

## Architecture rules

- **`models.py` is pure data.** No I/O, no CLI code, no business logic beyond
  simple query helpers (`get_speaker`, `utterances_by_speaker`, `speaker_word_counts`).
- **`transcript.py` is pure functions.** No global state. Functions take and return
  Pydantic models or primitives. I/O is limited to `load_transcript` / `save_transcript`.
- **`main.py` owns all I/O and user interaction.** It calls functions from `transcript.py`
  and renders output via Rich. No Pydantic model construction directly in `main.py`.
- **No new modules without discussion.** Extend existing files before creating new ones.

---

## Coding conventions

- Python 3.11+. Use `X | Y` union syntax, not `Optional[X]`.
- Line length 100 (ruff + editorconfig).
- No `print()` in library code (`models.py`, `transcript.py`). Use return values.
- Timedeltas for all timestamp fields — never raw floats or strings.
- Pydantic models use `Field(..., description=...)` on every field.
- Typer commands use `typer.Argument` / `typer.Option` with `help=` strings.

---

## Running the project

```bash
# Install environment
pixi install

# Run CLI
pixi run meeting-transcript parse sample.txt --title "Standup" -o out.json
pixi run meeting-transcript show out.json
pixi run meeting-transcript stats out.json

# Quality checks (all must pass before committing)
pixi run test
pixi run lint
pixi run format
pixi run typecheck
```

---

## Testing guidelines

- Every new public function in `transcript.py` needs at least one test.
- Every new Pydantic model or field needs a validation test.
- Tests are unit-level: no file I/O except via `tmp_path` pytest fixture.
- Do not mock internal functions. Test through the public interface.
- Confidence score bounds (`ge=0.0, le=1.0`) must be exercised.

---

## What agents should NOT do

- Do not introduce `Optional[X]` — use `X | None`.
- Do not add `print()` to library modules.
- Do not create helper utilities for one-off uses.
- Do not add backward-compat shims, re-exports, or `# removed` comments.
- Do not change `pixi.toml` channels or platforms without explicit user instruction.
- Do not commit secrets, audio files, or `.transcript.json` output files.
- Do not skip `ruff` or `mypy` errors by adding `# noqa` / `# type: ignore`
  without a comment explaining why.
