---
agent: agent
description: Verify the last finished chunk before starting the next one (read-only apart from running tests)
---

Check the repo state before the next chunk starts. Do not change any file.

1. Read `STATE.md` and `docs/SPEC.md` section 8.
2. Run in the WSL terminal, venv active: `git status --short`, `git log --oneline -15`,
   `ruff check . && pytest -m "not integration" -q`.
3. For the last ticked phase(s) in `STATE.md`, compare the "Produces" and "Check" columns
   in SPEC section 8 against the repo: does every listed file exist, and does the stated
   check actually pass? Run the check command where it needs no service or key.
4. Look for these problems and report each one you find, with file and line:
   - a test that is skipped, xfailed, empty, or asserts nothing meaningful,
   - a phase ticked in `STATE.md` whose files or commit are missing,
   - uncommitted changes,
   - a dependency not in SPEC section 5 without a decision-log line,
   - a hand-typed number that should come from `reports/`.
5. Answer in this format and nothing else:

   ```
   Last finished: <phase>
   ruff: pass|fail | pytest: <n passed, n failed, n skipped>
   Files from SPEC present: yes|no (<missing>)
   Problems: none | <list>
   Verdict: READY for chunk <n> (model: <Sonnet|Opus>) | FIX FIRST: <what>
   ```
