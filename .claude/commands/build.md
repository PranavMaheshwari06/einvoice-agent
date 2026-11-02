---
description: Build the next phase from STATE.md, verify it as far as this environment allows, document it, hand off
argument-hint: "[phase id, e.g. A4]"
---

Build one phase of this repository and stop. Phase: $ARGUMENTS (empty means the one named in
the "Next session" block of `STATE.md`).

1. Read `CLAUDE.md` and `STATE.md`. Check you are on the branch the "Next session" block
   names. Read only the SPEC sections the phase uses (section 8 row, section 3 parts) and the
   last entry of `docs/PHASE_LOG.md`.
2. Say in one line which model the "Next session" block asks for. If you are clearly a
   different tier, say so and ask whether to continue.
3. Write the code and tests for this phase only, as small as the SPEC allows. Before writing a
   helper, check whether the package already has one.
4. Run `ruff check . && pytest -m "not integration" -q` until both pass. If this environment
   has the services the phase needs (Postgres, validator, LLM), run the live checks and
   integration tests as well. Never delete, skip or weaken a test to get a pass.
5. For everything that needed a service you do not have, add an UNVERIFIED line to `STATE.md`
   with the file, the assumption and the tag `[cloud-built]` plus the phase that closes it. Do
   not tick the `live` box in that case.
6. Logical checks for the phase (see `CLAUDE.md`): leakage, baseline comparison, invariants,
   plausibility of every number written to `reports/`. Fix or write down what fails.
7. Run `/simplify`, then `/code-review`, on the diff. Apply what holds up. Delete comments
   that only narrate the code.
8. Write `docs/notes/<topic>.md` for each finished component and the `docs/PHASE_LOG.md`
   entry. Update `STATE.md`: boxes, decision log, UNVERIFIED, "Next session" block.
9. Commit per logical step on the session branch and push it.
10. If the phase is A9, run every item of the release gate (SPEC section 8, "Release gate"),
    write each result (command, outcome, pass or fail) to `docs/RELEASE_CHECKLIST.md`, and
    stop for the owner's sign-off before anything becomes public.

Stop early and ask the owner only when: the same error survived two different fixes (write
it under Blockers first), the SPEC is ambiguous in a way that changes the design, or the
phase reaches a STOP in SPEC section 8. Never start the next phase, never continue because
context is left, never open a pull request unless asked.

Finish by printing exactly this block, filled in:

```
Phase <id> <build|live> done.
What happened (technical):
  <5 to 8 lines: modules added, key functions, data flow, one decision, one thing verified,
   one known limit>
Checks: ruff pass | pytest <n> passed | integration <n> passed or not run
UNVERIFIED: closed <n>, added <n>
Docs: <notes written>, PHASE_LOG entry
Branch: <name> (pushed) | base for next: <branch>
Next: <phase>  where: <cloud|laptop>  model: <Opus|Sonnet>
Start: new chat on branch <name>, paste: <first message from STATE.md>
```
