# Project conventions

These rules apply to every change in this repo, whichever tool or person writes it.
The design lives in `docs/SPEC.md`; progress and decisions live in `STATE.md`.

## What this project is

An accounts-payable pipeline for German e-invoices (XRechnung, ZUGFeRD, plain PDF, scans).
It turns an incoming invoice into a checked booking proposal, books automatically only
what the checks can prove, and sends everything else to a person with the reason.
Rules decide; models extract and explain.

## Size and shape

- Small and readable beats complete. Aim for roughly 3-4k lines of Python outside tests.
  If a module grows past ~300 lines, write one line in the STATE.md decision log saying why.
- Plain functions first. Use classes only for pydantic models, the one replay chat model
  in `llm.py`, and objects that really hold state.
- No abstract base classes, factories, registries, "manager"/"service" classes or plugin
  systems. If something has one implementation, it does not get an interface.
- No speculative options, flags or config values. Add a setting only when two real
  values exist today.
- Standard library first: `logging`, `argparse`, `pathlib`, `dataclasses` where pydantic
  is not needed, `json`, `hashlib`, `decimal` for money.
- Money is `decimal.Decimal`, never float. Dates are `datetime.date`.
- Dependencies: only the ones listed in `docs/SPEC.md` (section "Dependencies"). Adding one
  needs a one-line reason in the STATE.md decision log.

## Package layout

- `src/` layout, one package `einvoice`, installed with `pip install -e ".[dev]"`.
- Imports are absolute (`from einvoice.rules import engine`), no `sys.path` tricks.
- Entry point: `einvoice = "einvoice.cli:main"` with argparse subcommands.
- Tests mirror the package: `src/einvoice/rules/arithmetic.py` -> `tests/unit/rules/test_arithmetic.py`.
- Anything that needs Postgres, the KoSIT validator, a real LLM or the network is an
  integration test: mark it `@pytest.mark.integration`.

## Code style

- Type hints on public functions. `ruff` with the config in `pyproject.toml`; no other linters.
- Names describe the domain: `vat_total`, `po_number`, `buyer_reference`, not `data`, `obj`, `result2`.
- Comments say why, not what. No banner comments, no emojis, no commented-out code,
  no `# TODO: implement` stubs. If something is not built yet, it is not in the code.
- Docstrings only where behaviour is not obvious from the name and signature. One or two
  lines, no "Args/Returns" blocks restating the types.
- Errors: raise at boundaries (bad file, failed validation, missing env var) with a clear
  message. Never swallow exceptions; never return `None` to mean "failed".
- Log with `logging.getLogger(__name__)`. No print outside `cli.py`.

## Tests

- Small, focused, one test file per module. Test behaviour, not implementation details.
- Mock only at network boundaries (HTTP, database, LLM). Use real sample invoices from
  `tests/fixtures/` for parsing and rules.
- Every bug fixed gets a test that failed before the fix.

## Data and secrets

- Only public data (see `DATA_SOURCES.md`) and synthetic data from `einvoice.synth`.
  No real personal or company data, ever (DSGVO).
- No secrets in git. `.env` is ignored; `.env.example` lists variable names with empty values.
- Tests and CI use `LLM_PROVIDER=replay`. They never need an API key or a running model.

## Numbers and claims

- Every number in the README or docs comes from a file the code wrote:
  `reports/metrics.json` (or another file under `reports/`). Never type a metric by hand.
- If a result is weak, report it as it is and say what limits it.

## Docs

- `README.md`: first person, plain language, short. It has a "Limitations" section.
  Avoid marketing words: robust, seamless, cutting-edge, leverage, comprehensive,
  enterprise-grade, production-ready, state-of-the-art, powerful, revolutionize.
- `docs/notes/<topic>.md`: one design note per component (template in `docs/SPEC.md`).
  Written when the component is finished, in the same plain style.

## Git

- One commit per finished phase (or smaller), conventional style:
  `feat(rules): add §14 UStG mandatory-field checks`. No giant "initial implementation" commit.
- Never commit `data/raw/`, `mlruns/`, `.env`, model binaries or caches.
