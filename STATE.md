# Build state

Read this first in every session. Update it before every commit.

Current stage: **A** (write code, unit tests only)
Next: **A1**

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
- [ ] A1 Core: models, parsers, KoSIT client, rules
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

## UNVERIFIED
Things written in Stage A that could not be run there. Stage B checks each one and
deletes the line when it is confirmed or fixed.

## Blockers
Anything that stopped progress twice in a row, with what was tried.
