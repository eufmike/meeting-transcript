# GitHub Copilot instructions

See [AGENTS.md](../../AGENTS.md) for full project conventions.

Quick reference:
- Python 3.11+, use `X | None` not `Optional[X]`
- Pydantic v2 — `model_validate`, `model_dump_json`, `Field(..., description=...)`
- No `print()` in `models.py` or `transcript.py`
- Line length 100; run `pixi run lint` to check
