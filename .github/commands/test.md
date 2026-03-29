---
description: Run the full test suite with coverage
---

Run all quality checks in order:

1. `pixi run lint` — ruff linting
2. `pixi run typecheck` — mypy strict type checking
3. `pixi run test` — pytest with verbose output

Report which checks passed and which failed. If any check fails, show the
relevant output and suggest a fix. Do not move to the next check if the
previous one has errors that would mask its results.
