---
description: Audit the repo before the next session starts (read-only apart from running tests)
---

Check the repo state before the next session. Do not change any file.

1. Read `STATE.md` and `docs/SPEC.md` section 8.
2. Run `git status --short`, `git log --oneline -15`, `git branch --show-current`,
   `ruff check .` and `pytest -m "not integration" -q`. If Docker is available, also run
   `docker compose -f deploy/compose.yaml ps` and `pytest -m integration -q`.
3. For every phase with a ticked `build` or `live` box, compare the "Produces" column of SPEC
   section 8 with the repo: does each listed file exist, and does the stated check pass?
4. Report each problem with file and line:
   - a test that is skipped (other than OCR without tesseract), xfailed, empty, or asserts
     nothing meaningful,
   - a ticked box whose files or commit are missing,
   - a `live` box ticked while an UNVERIFIED line of that phase is still open,
   - uncommitted changes, or a branch that differs from the "Next session" block,
   - a dependency missing from SPEC section 5 and the decision log,
   - a number in README or docs that does not come from `reports/`,
   - a missing design note or `PHASE_LOG.md` entry for a finished component,
   - narrating comments in the last commit's diff,
   - for A9: `docs/RELEASE_CHECKLIST.md` missing, any item not passed, or no sign-off line.
5. Answer in this format and nothing else:

```
Branch: <name>  Last finished: <phase and box>
ruff: pass|fail | pytest: <n passed, n failed, n skipped> | integration: <result or not run>
Files from SPEC present: yes|no (<missing>)
Problems: none | <list>
Verdict: READY for <phase> (where: <cloud|laptop>, model: <Opus|Sonnet>) | FIX FIRST: <what>
```
