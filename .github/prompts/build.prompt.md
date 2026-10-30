---
agent: agent
description: Build the next Stage A chunk of einvoice-agent (one chunk per session), then stop
---

You are building Stage A of this repository, one chunk at a time. A chunk is one row of
the "Chunks" table in `STATE.md`. You do that chunk and nothing else, then stop.

Before anything else, read these three files completely:
1. `.github/copilot-instructions.md`: the conventions. Follow them in every file you write.
2. `docs/SPEC.md`: the design. Section 8 lists each phase, what it must produce, and its check.
3. `STATE.md`: where the build stands.

Then:

1. Find the first chunk in `STATE.md` whose phases are not all ticked. If the user named a
   chunk or phase range after `/build`, use that instead.
2. Tell the user, in one line, which model that chunk is meant for (the Model column). If
   you are clearly a different tier, say so and ask whether to continue or switch; do not
   switch yourself.
3. For each phase in the chunk, in order:
   1. Re-read that phase's row in SPEC section 8 and the SPEC sections it depends on.
   2. Write the code and tests for that phase only, as small as the SPEC allows. Before
      writing a helper, check whether the package already has one.
   3. Run from the repo root in the WSL terminal with the venv active
      (`source .venv/bin/activate`): `ruff check . && pytest -m "not integration" -q`.
      Fix failures until both pass. Never delete, skip or weaken a test to make it pass.
   4. If you used a library API, XPath, schema detail or file format you could not confirm
      by running it here (it needs Postgres, the validator, Docker, a real LLM or the
      network), add one line to UNVERIFIED in `STATE.md` naming the file and the assumption.
   5. Update `STATE.md`: tick the phase, set "Next:", log any choice the SPEC did not make.
   6. Commit: `git add -A && git commit -m "<type>(<scope>): <what>"`. One commit per phase.
4. When the chunk is done, STOP. Do not start the next chunk. Print exactly this block,
   filled in:

   ```
   Chunk <n> done: <phases>
   Commits: <git log --oneline for this chunk>
   ruff: pass | pytest: <n> passed
   UNVERIFIED added: <count>
   Next: chunk <n+1> (<phases>), model: <Sonnet|Opus>
   To continue: open a NEW chat, pick that model, type /check, then /build.
   ```

Stop early and ask the user only when:
- the same error has survived two different fix attempts (write it under Blockers first), or
- the SPEC is ambiguous in a way that changes the design (not a naming detail), or
- a step would need an API key, a secret, Docker, Kubernetes, a cloud account or personal
  data. Those belong to Stage B: write the code, list it under UNVERIFIED, and move on.

Never:
- add dependencies outside SPEC section 5 without a decision-log line,
- invent metrics or results; numbers come only from files the code writes under `reports/`,
- add abstractions, options or files the current phase does not need,
- run `git push`,
- continue into the next chunk because there is context left.

After the last chunk (A9), tell the user: "Stage A done. Run `git push`."
