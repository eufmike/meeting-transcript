---
name: quality-check
description: Run the full quality gate — lint, type check, tests — and report results
---

Run these pixi tasks in order, stopping at the first failure:

```bash
pixi run lint
pixi run typecheck
pixi run test
```

For each step report: PASS or FAIL with the relevant output.
If all pass, confirm the branch is ready to merge.
If any fail, explain the root cause and propose a fix before re-running.
