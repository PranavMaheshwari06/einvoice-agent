---
agent: agent
description: Build Stage A of einvoice-agent, phase by phase, from STATE.md
---

You are building Stage A of this repository.

Before anything else, read these three files completely:
1. `.github/copilot-instructions.md`: the conventions. Follow them in every file you write.
2. `docs/SPEC.md`: the design. Section 8 lists the Stage A phases, what each must produce, and its check.
3. `STATE.md`: where the build stands.

Then work in this loop until STATE.md says A9 is done:

1. Take the first unchecked Stage A phase in STATE.md.
2. Re-read that phase's row in SPEC section 8 and the SPEC sections it depends on.
3. Write the code and tests for that phase only. Keep it as small as the SPEC allows.
   Before writing a new helper, check whether the package already has one.
4. Run, in the WSL terminal, from the repo root with the venv active (`source .venv/bin/activate`):
   `ruff check . && pytest -m "not integration" -q`.
   Fix failures until both pass. Do not delete or skip a test to make it pass.
5. If you used a library API, XPath, schema detail or file format you could not confirm by
   running it here (because it needs Postgres, the validator, Docker, a real LLM or the
   network), add one line to the UNVERIFIED section of STATE.md naming the file and the
   assumption.
6. Update STATE.md: tick the phase, set "Next:", add decision-log lines for any choice
   the SPEC did not make for you.
7. Commit: `git add -A && git commit -m "<type>(<scope>): <what>"`. Do not push.
8. Continue with the next phase without waiting for me.

Stop and ask me only when:
- the same error has survived two different fix attempts (write it under Blockers first), or
- the SPEC is ambiguous in a way that changes the design (not a naming detail), or
- a step would need an API key, a secret, Docker, Kubernetes, a cloud account or personal data.
  Those belong to Stage B: write the code, list it under UNVERIFIED, and move on.

Never:
- add dependencies outside SPEC section 5 without a decision-log line,
- invent metrics or results; numbers come only from files the code writes under `reports/`,
- add abstractions, options or files the current phase does not need,
- run `git push`.

At A9, finish the README and the design notes, make sure the UNVERIFIED list is complete,
commit, and tell me: "Stage A done. Run `git push`."

If this chat gets long, it is fine to stop after a commit and continue in a new chat with
the same `/build` prompt: STATE.md carries everything over.
