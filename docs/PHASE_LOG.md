# Phase log

One entry per finished step, newest last. Each entry says what happened in technical terms,
what was verified, and what is still open. Written by the session that did the work.

## A0 to A3 (2026-10-31, before the move to Claude Code)

Scaffold, core models/parsers/KoSIT client/rules, the synthetic data generator with the AP
policy and SKR03 subset, and the extraction path (text, OCR, LLM extraction with a quote
check). Built and unit-tested on a machine without Docker, Postgres or an LLM, so twelve
things are listed as UNVERIFIED in `STATE.md`. The choices are in its decision log.

## S1, instruction files (2026-11-02)

Replaced the Copilot setup by Claude Code files: `CLAUDE.md` (conventions, working
principles, session protocol), `.claude/commands/{build,check,verify}.md` and
`.claude/settings.json`. SPEC section 8 now splits every phase into `build` and `live`, adds
R0a/R0b and A6a, and has the release gate; section 3.13 adds `pipeline.py`. `STATE.md` has
the session table, branch names and the "Next session" block. `Settings` got the OpenAI and
Anthropic key fields and the SQLite MLflow default (tested in `test_config.py`). Checked
before the change: ruff clean, 162 passed, 2 skipped (OCR). Open: the R0b cloud fixes.

## S1, R0b cloud fixes (2026-11-02)

Added tests for `rules/legal.py` and for the `db migrate` and `db load` CLI handlers (the
database connection is replaced by a fake; the handlers' printed summaries and arguments are
checked). Audit finding 7 turned out not to be a defect: the engine emits the code
`LOW_EXTRACTION_CONFIDENCE` once and de-duplicates codes, so the reason list is complete. The
count-only replay test stays because the parametrized test already validates each fixture.
Result: ruff clean, 168 passed, 2 skipped (OCR). Live part of R0b (KoSIT, Postgres, tesseract)
needs the laptop and is listed under UNVERIFIED. Next: S2, A4 build, Opus.

## S2, A4 build (2026-11-02)

Built `ml/coding.py` (TF-IDF baseline, e5 embeddings with an injected encoder, isotonic
calibration on seller-grouped folds, ECE, coverage at 98 % precision, `suggest_account`),
`ml/train.py` (vendor-grouped split check, champion on validation macro-F1, MLflow runs,
`gl-coder@champion`, `reports/gl_coder.json`), `pipeline.py` (`process`), `evaluate.py`
(threshold sweep, operating point on validation, test report, rule of three, plot),
`convert.to_xrechnung` and the `train`, `eval` and `convert` commands. The rules engine got
`decide`, so the sweep reuses stored check results instead of copying the GL gate, and
extraction reasons now travel in `RuleContext`. A cloud run on seed 1 (2000 invoices, hashing
stub instead of e5, KoSIT skipped) worked end to end: the rules sent every must-review
invoice to review and every remaining wrong booking was a GL account. Two weak results are
recorded in STATE.md: isotonic calibration did not beat the raw model on validation ECE and
cut coverage at 98 % precision, and the test coverage at zero wrong bookings is low. Reports
from that run stayed out of the repo because they come from a stub. Result: ruff clean, 211
passed, 2 skipped (OCR). Next: S3, A5 build, Opus.

## L1, R0a (2026-11-02)

Built the dev environment: `.devcontainer/devcontainer.json`, `deploy/docker/Dockerfile`
(python 3.12 slim, tesseract with German data, packages from `requirements.lock`, uid 1000),
`deploy/docker/validator.Dockerfile` (Temurin 21 JRE, KoSIT validator 1.6.3, XRechnung
configuration 2026-08-31, daemon on 8081), `deploy/compose.yaml` (dev, postgres with pgvector,
validator; profile `core`, localhost ports), `requirements.lock` (172 lines, torch CPU wheel,
no CUDA packages) and the Makefile targets `up`, `down`, `test-integration`, `lock`; the README
quick start is rewritten. Verified live: the validator daemon answers a POST of 01.01a UBL
with 200 and a report; in the container `make check` gives 213 passed and none skipped (the two
OCR tests ran for the first time), `make test-integration` gives 1 passed, Postgres answers
and offers pgvector 0.8.7; the devcontainer CLI brings the stack up and runs the same tests;
a fresh clone of the pushed branch repeated all of it. One bug found on the way: a downloaded
`ADD` file is unreadable for the non-root validator user, fixed with `--chmod=644`. Not
checked: the "Reopen in Container" button itself. Next: R0b live, or S3 (A5 build).

## S3, A5 build (2026-11-02)

Built `llm.py` (`chat_model` with replay, ollama, openai and anthropic branches; `ReplayChatModel`
answers with recorded messages and tool calls), `agent/rag.py` (chunks of § 14 UStG per Absatz,
the AP policy per heading and the 39 BR-DE rules from the XRechnung UBL schematron; pgvector store
and search with a similarity cut-off and at most 8 chunks), `agent/mcp_server.py` (FastMCP with
the four read-only tools; reads in `db.py`), `agent/graph.py` (LangGraph agent and tool node,
`finalize` with the guardrails `INVALID_PROPOSAL`, `INSUFFICIENT_EVIDENCE`,
`UNSUPPORTED_EXPLANATION`, a cap of 6 tool rounds) and `agent/evals.py` with 32 cases in
`evals/agent_cases.yaml` and one hand-written replay fixture each. New commands: `db index`,
`agent-eval [--record]` and `eval --record`; `run_gold` now takes `complete_for`. Verified here:
the MCP server lists exactly the four read-only tools in process and over stdio (a real
subprocess), every guardrail escalates with its code, every kept citation in the 32 replayed
cases came from a tool call of the same run, and the e5 retrieval prefixes match the authors'
code. Not verified: no provider, Postgres, e5 model or UStG XML was reachable from the cloud, so
the replay results only show that the pipeline works; six `[cloud-built]` lines are in STATE.md.
`/simplify` and `/code-review` led to the k cap, `models.NotFound` instead of `LookupError` (a
`KeyError` in a tool no longer looks like a lookup miss), the round cap and citation recall over
citing cases only. Result: ruff clean, 334 passed, 2 skipped (OCR). Next: S4, A6a UI design,
Opus; A5 live on the laptop.
