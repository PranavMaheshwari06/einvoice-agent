# Build state

Read this first in every session. Update it before every commit.

Current stage: **A** (write code, unit tests only)
Next: **A2**

## Chunks (one chat per chunk; `/build` does the first unfinished one, then stops)
Sonnet: well-specified, self-contained work. Opus: work that has to hold many earlier
modules in mind at once. Use the newest model of that tier in the picker.

| Chunk | Phases | Model | Why |
|---|---|---|---|
| 1 | A0 | Sonnet | scaffold, config, fetch script |
| 2 | A1 | Opus | models, parsers, KoSIT client and rules; everything later builds on it |
| 3 | A2 | Sonnet | synthetic data and SQL, follows A1 models |
| 4 | A3 | Sonnet | extraction against replay fixtures |
| 5 | A4 | Opus | training, conversion and evaluation touch A1-A3 |
| 6 | A5 | Opus | agent graph, tools, RAG and guardrails use most of the package |
| 7 | A6, A7 | Sonnet | API/UI and monitoring on top of finished modules |
| 8 | A8, A9 | Sonnet | infra files and handoff docs |

Between chunks: new chat, `/check`, then `/build`.

## Stage A
- [x] A0 Scaffold
- [x] A1 Core: models, parsers, KoSIT client, rules
- [ ] A2 Data: synthetic generator, AP policy, SKR03 subset, migrations
- [ ] A3 Extraction: text, OCR, LLM extraction with evidence check
- [ ] A4 Models + eval: GL coder, convert, risk-coverage evaluation
- [ ] A5 Agent: MCP tools, RAG, LangGraph graph, guardrails, 30 cases
- [ ] A6 API + UI
- [ ] A7 Monitoring: metrics, drift, Grafana, retrain
- [ ] A8 Infra: Docker, Compose, k8s, CI (dispatch-only), Terraform
- [ ] A9 Handoff: README, design notes, UNVERIFIED list complete

## Stage B
- [ ] B0 Install, fetch, UNVERIFIED list, unit tests green
- [ ] B1 Postgres + validator in Compose, integration tests green
- [ ] B2 Real LLM, extraction eval, re-record replay fixtures (user reviews)
- [ ] B3 Train on full data, promote champion
- [ ] B4 Agent eval with real model (user tries 5 cases)
- [ ] B5 Full Compose stack, UI walkthrough
- [ ] B6 kind deploy, Prometheus, Grafana, drift CronJob
- [ ] B7 CI on push/PR, green (user confirms before first GHCR push)
- [ ] B8 Azure via Terraform (user sets budget first), demo, destroy
- [ ] B9 README results, demo GIF, review agent files before going public

## Decision log
One line each: date, decision, reason.

- 2026-10-31: `cli.py` has one subcommand (`config`) in A0; later phases add theirs when the code exists. Reason: no stubs, but `--help` must list something real.
- 2026-10-31: `fetch_data.py` takes the latest release of each KoSIT repo and the master commit of the ZUGFeRD corpus, and records the version in `DATA_SOURCES.md`. Reason: the SPEC names no fixed versions.
- 2026-10-31: setuptools as build backend, no extra dependency. CPU torch was installed in the venv before the rest to avoid CUDA wheels; `pyproject.toml` does not pin torch (comes with sentence-transformers).
- 2026-10-31: `tesseract` binary is not installed in this WSL; OCR tests in A3 must skip when it is missing.
- 2026-10-31: `Evidence` has a `bt` field next to `xpath`. `Invoice` also holds buyer address (BG-8), invoice period (BT-73/74), BT-107/108/113/114, and lines hold BT-132, BT-136/141 and BT-149. Reason: §14 needs the buyer address and period; arithmetic on real fixtures fails without allowances, charges and price base quantity.
- 2026-10-31: Rule context types (`Vendor`, `PurchaseOrder`, `PoLine`, `PriorInvoice`, `RuleContext`) live in `models.py`. `PoLine.received_quantity` is the summed goods receipts; `None` means 2-way match only.
- 2026-10-31: `engine.run` returns `(results, Decision)` so the caller can store every check. Missing GL probability counts as `LOW_GL_CONFIDENCE`.
- 2026-10-31: `legal.py` holds only constants a rule uses (VAT rates, §33 UStDV limit). The §27 Abs. 38 transition dates go in when a rule needs them.
- 2026-10-31: Price check is two-sided, code `PRICE_OUTSIDE_TOLERANCE`. VAT rate check: category S must be 19 or 7, other categories 0. A2's "wrong VAT rate" problem must use a rate outside these (e.g. 16), since rules cannot know the right rate for an item.
- 2026-10-31: Non-German seller VAT ids pass `INVALID_VAT_ID` with severity info (format only checked for DE).
- 2026-10-31: Fixtures: 14 public files, including the 03.07a pair (the only public files with line-level allowances). The corpus `unstructured/` Hetzner PDF is not used: it names a private person (DSGVO). Plain-PDF and scan tests build their files with reportlab and Pillow.
- 2026-10-31: No Java in this WSL, so the KoSIT report fixture is written by hand from `report.xsd` / `default-report.xsl`.

## UNVERIFIED
Things written in Stage A that could not be run there. Stage B checks each one and
deletes the line when it is confirmed or fixed.

- `validation/kosit.py`: the daemon takes a POST of the raw XML at `/` and answers 200 (accept) or 406 (reject) with the report as body.
- `tests/fixtures/kosit/report_reject_br_de_15.xml`: hand-written to the report schema; replace with a real daemon report for 01.01a UBL without BuyerReference and re-run `test_kosit.py`.
- `tests/unit/validation/test_kosit.py::test_live_validator_accepts_a_testsuite_invoice` (integration) has never run.
- `rules/legal.py`: `SMALL_AMOUNT_LIMIT` = 250 EUR (§33 UStDV) not checked against the primary source here.
- `parsing/zugferd.py`: XRechnung PDFs attach `xrechnung.xml` (no fixture has one).

## Blockers
Anything that stopped progress twice in a row, with what was tried.
