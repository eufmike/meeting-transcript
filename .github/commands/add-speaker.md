---
description: Scaffold a new speaker-identification strategy
---

The user wants to add a new speaker identification strategy. Do the following:

1. Read `src/meeting_transcript/models.py` and `src/meeting_transcript/transcript.py`
   to understand the current data model and parsing pipeline.
2. Ask the user: what input format does the new strategy consume? (e.g. audio
   file, VTT/SRT subtitle, JSON from a third-party API)
3. Add any new Pydantic fields to models with `Field(..., description=...)`.
4. Add a new parsing function to `transcript.py` — pure function, no I/O side effects
   beyond what is passed in.
5. Expose it as a new Typer subcommand in `main.py` if it requires its own flags.
6. Write at least two tests in `tests/test_transcript.py`.
7. Run `/test` to verify everything passes.
