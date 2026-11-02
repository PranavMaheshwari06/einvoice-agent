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
