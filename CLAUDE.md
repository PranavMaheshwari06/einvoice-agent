# einvoice-agent

An accounts-payable pipeline for German e-invoices (XRechnung, ZUGFeRD, plain PDF, scans).
It turns an incoming invoice into a checked booking proposal, books automatically only what
the checks can prove, and sends everything else to a person with the reason.
Rules decide; models extract and explain.

Design: `docs/SPEC.md`. Progress, decisions, next session: `STATE.md`. Per-phase history:
`docs/PHASE_LOG.md`. Learning guide for the owner: `docs/GUIDE.md`.

## How to work here

Act as a senior AI engineer building a portfolio project that a master's student will
present and defend.

- Every module must be explainable by the student in two sentences. If it cannot be, it is
  too clever or not needed.
- No assumptions. If a library behaviour, legal threshold, file format or requirement is not
  confirmed, check it by running it or by reading the primary source. If that is impossible,
  ask. Do not fill a gap with a plausible guess.
- No over-engineering. Build the smallest design that meets the SPEC. No new module, option,
  dependency or abstraction without a decision-log line in `STATE.md` that gives the reason.
  Do not add features the SPEC does not list.
- Logical checks are part of the work: assert invariants in code or tests (amounts add up,
  the split has no seller overlap, probabilities lie in [0, 1]), compare every model with a
  baseline, evaluate only on held-out data, look at the worst errors, and check that a result
  is plausible before it is written to `reports/`. If a number looks too good, look for
  leakage first.
- Write code that reads as written by one person: consistent domain names, short functions,
  one idea per module, no defensive branches for cases that cannot happen, no catch-all
  handlers, no placeholder or example code left behind.
- Comments say why, never what. Allowed: a reason, a legal or standard reference (section,
  BT id, rule id), a non-obvious constraint. Before each commit read the diff and delete
  comments that narrate the code.
- When a choice has an alternative, give a recommendation and one or two sentences of reason,
  not a list of options.

## Sessions

Phases are built in the order of `docs/SPEC.md` section 8. Each phase has two boxes in
`STATE.md`: `build` (code and unit tests) and `live` (checked against the real service:
Postgres, KoSIT validator, LLM, Docker). A phase is finished only when both are ticked. A
session without those services (the cloud) ticks `build` only and tags what it could not run
in the UNVERIFIED list as `[cloud-built]` with the phase that will close it.

Start of a session:
1. Check out the branch named in the "Next session" block of `STATE.md`.
2. Read `STATE.md`, then only the SPEC sections the phase names and the last entry of
   `docs/PHASE_LOG.md`. Do not read the whole repository.
3. Do the phase and nothing else. Stop at every STOP in SPEC section 8 and ask.

End of a session, even a partial one:
1. `ruff check .` and `pytest -m "not integration" -q` pass. Run `/simplify`, then
   `/code-review`, on the diff and apply what holds up.
2. Update `STATE.md`: tick boxes, UNVERIFIED lines, decision log, and the "Next session"
   block (branch, base branch, where, model, first message to paste, what not to touch).
3. Write the `docs/PHASE_LOG.md` entry and the design notes (`docs/notes/<topic>.md`, template
   in SPEC section 9) for finished components.
4. Commit per logical step, push the session branch, print the handoff block from `/build`.

Branches are named `pranav/<phase>-<topic>`, for example `pranav/a4-models-eval`, one per
session, started from the tip of the previous session's branch unless it is already merged.
Open a pull request only when asked.

## Size and shape

- Small and readable beats complete. Aim for roughly 3-4k lines of Python outside tests.
  If a module grows past about 300 lines, add a decision-log line saying why.
- Plain functions first. Classes only for pydantic models, the one replay chat model in
  `llm.py`, and objects that really hold state.
- No abstract base classes, factories, registries, "manager" or "service" classes, plugin
  systems. One implementation means no interface.
- No speculative options, flags or settings. Add a setting only when two real values exist.
- Standard library first: `logging`, `argparse`, `pathlib`, `dataclasses`, `json`, `hashlib`,
  `decimal` for money.
- Money is `decimal.Decimal`, never float. Dates are `datetime.date`.
- Dependencies are the ones in SPEC section 5. Adding one needs a decision-log line.

## Package layout

- `src/` layout, one package `einvoice`. Imports are absolute, no `sys.path` tricks.
- Entry point `einvoice = "einvoice.cli:main"`, argparse subcommands. A subcommand is added
  in the phase that builds the code behind it.
- Tests mirror the package: `src/einvoice/rules/arithmetic.py` is tested in
  `tests/unit/rules/test_arithmetic.py`.
- Anything that needs Postgres, the KoSIT validator, a real LLM or the network is an
  integration test marked `@pytest.mark.integration`.

## Code style

- Type hints on public functions. `ruff` with the config in `pyproject.toml`; no other linters.
- Names describe the domain: `vat_total`, `po_number`, `buyer_reference`, not `data`, `obj`.
- No emojis, no commented-out code, no `TODO` stubs. If it is not built, it is not in the code.
- Docstrings only where behaviour is not obvious from name and signature; one or two lines.
- Raise at boundaries (bad file, failed validation, missing setting) with a clear message.
  Never swallow an exception; never return `None` to mean "failed".
- Log with `logging.getLogger(__name__)`. No `print` outside `cli.py`.

## Tests

- Small, focused, one test file per module. Test behaviour, not implementation.
- Mock only at network boundaries (HTTP, database, LLM). Use the real sample invoices in
  `tests/fixtures/` for parsing and rules.
- Every fixed bug gets a test that failed before the fix.
- A test is never deleted, skipped or weakened to make a run pass.

## Data and secrets

- Only public data (`DATA_SOURCES.md`) and synthetic data from `einvoice.synth`. No real
  personal or company data (DSGVO).
- No secrets in git. `.env` is git-ignored; `.env.example` lists names with empty values.
  Never read, print or paste `.env` or an API key.
- Tests and CI use `LLM_PROVIDER=replay`; they never need a key or a running model.

## Numbers and claims

- Every number in the README or docs comes from a file the code wrote under `reports/`.
  Never type a metric by hand.
- A report produced through a stubbed path (fixtures, stub encoder) says so in the file. The
  README quotes only numbers from live-verified runs.
- If a result is weak, report it as it is and say what limits it.

## Docs

- `README.md`: first person, plain language, short, with a "Limitations" section. No
  marketing words (robust, seamless, cutting-edge, leverage, comprehensive, enterprise-grade,
  production-ready, state-of-the-art, powerful).
- `docs/notes/<topic>.md`: one design note per component, written in the phase that builds it.
- Commit messages: conventional style, imperative, one subject line, for example
  `feat(rules): add §14 UStG mandatory-field checks`. A body only when the why is not obvious.
- Never commit `data/raw/`, `mlruns/`, `mlflow.db`, `.env`, model binaries or caches.

## Environment

- Until the dev container exists (phase R0a) the cloud and laptop sessions use `.venv`. After
  R0a, commands run inside the dev container (`deploy/compose.yaml`, service `dev`).
- Cloud sessions cannot run Docker, the validator, Postgres, tesseract or a real LLM and do
  not write Dockerfile, Compose, devcontainer, Kubernetes, Terraform or CI files.
