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
