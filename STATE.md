# Build state

Read this first in every session. Update it before every commit.

Current stage: **A** (write code, unit tests only)
Next: **A0**

## Stage A
- [ ] A0 Scaffold
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

## UNVERIFIED
Things written in Stage A that could not be run there. Stage B checks each one and
deletes the line when it is confirmed or fixed.

## Blockers
Anything that stopped progress twice in a row, with what was tried.
