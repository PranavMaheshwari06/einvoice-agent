---
description: Close the first open UNVERIFIED line by running the real check (needs the live services)
---

Work through the UNVERIFIED list in `STATE.md`, one line at a time, in the order of the list.

For the first line that has a `[cloud-built]` or open tag:
1. Read the file and assumption it names. Say what the real check is and what it needs.
2. If the needed service is not available here (Postgres, validator, Docker, tesseract, real
   LLM, network), say so and stop; do not guess the result.
3. Run the check. If the assumption holds, add an integration test (marked
   `@pytest.mark.integration`) when none covers it, and delete the UNVERIFIED line.
4. If it does not hold, fix the code, add a test that failed before the fix, and delete the
   line. If the fix changes the design, stop and ask.
5. Run `ruff check .` and `pytest -m "not integration" -q`, plus the integration test.
6. Commit with a message naming the line that was closed.

Do one line per run unless `$ARGUMENTS` says "all". When the last UNVERIFIED line of a phase
is closed and its integration tests pass, tick that phase's `live` box in `STATE.md` and add
the `docs/PHASE_LOG.md` entry.
