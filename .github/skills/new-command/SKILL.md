---
name: new-command
description: Scaffold a new Typer CLI command following project conventions
---

To add a new CLI command:

1. Read `src/meeting_transcript/main.py` and `src/meeting_transcript/transcript.py`.
2. Add any required pure logic to `transcript.py` (no I/O, no `print()`).
3. Add a new `@app.command()` function to `main.py` with:
   - `typer.Argument` / `typer.Option` with `help=` strings
   - Rich output via `console.print()`
4. Update the `[tasks]` section of `pixi.toml` if a convenience alias is useful.
5. Run the quality-check skill to verify.
