# Build state

Read this first in every session. Update it before every commit.

Current phase: **R0b, cloud part** (session S1). A0 to A3 are built; A4 is not started.
Rules: `CLAUDE.md`. Design: `docs/SPEC.md`. History: `docs/PHASE_LOG.md`.

## Next session
Branch: `pranav/claude-code-setup` (base: `main`)
Session: S1, step 2 (R0b cloud fixes), where: cloud, model: Sonnet
First message: "Continue S1 step 2 from STATE.md: R0b cloud fixes, then print the S2 handoff."
Do not touch: Dockerfile, Compose, devcontainer, k8s, Terraform, CI files; A4 code.

## Sessions
One session per row. The branch of a session starts from the tip of the previous one unless
that one is already merged into `main`.

| Session | Phase | Where / model | Branch |
|---|---|---|---|
| S1 | instruction files, R0b cloud fixes | cloud, Sonnet | `pranav/claude-code-setup` |
| S2 | A4 build | cloud, Opus | `pranav/a4-models-eval` |
| S3 | A5 build | cloud, Opus | `pranav/a5-agent` |
| S4 | A6a UI design | cloud, Opus | `pranav/a6a-ui-design` |
| S5 | A6b build, A7 build | cloud, Sonnet | `pranav/a6b-api-ui` |
| L1 | R0a, then live passes R0b, A4, A5, A6b, A7 | laptop dev container, Sonnet then Opus | `pranav/r0-dev-environment`, then `pranav/<phase>-live` |
| L2 | A8, A9 | laptop, Opus then Sonnet | `pranav/a8-infra`, `pranav/a9-release` |

If credits or time run out, resume from the "Next session" block; it works in the cloud or in
VS Code on the laptop.

## Phases
`build` = code and unit tests. `live` = checked against the real service. Cloud sessions tick
`build` only.

- [x] A0 Scaffold: build, live
- [x] A1 Core (models, parsers, KoSIT client, rules): build; [ ] live (R0b)
- [x] A2 Data (generator, AP policy, SKR03 subset, migrations): build; [ ] live (R0b)
- [x] A3 Extraction (text, OCR, LLM extraction, evidence check): build; [ ] live (R0b, A5)
- [ ] R0a Environment (dev container, Dockerfile, Compose, lockfile): build, live (laptop)
- [ ] R0b Catch-up: [ ] build (cloud, S1), [ ] live (laptop)
- [ ] A4 Models + eval: [ ] build (S2), [ ] live
- [ ] A5 Agent: [ ] build (S3), [ ] live (provider probe, recording; STOP)
- [ ] A6a UI design: [ ] prototype (S4; STOP)
- [ ] A6b API + UI: [ ] build (S5), [ ] live (STOP)
- [ ] A7 Monitoring: [ ] build (S5), [ ] live
- [ ] A8 Infra: build, live (laptop)
- [ ] A9 Ship: CI, Azure, release gate, README (laptop; STOPs)

## R0b cloud findings (from the audit before S1)
1. `config.py` had no key or base-URL fields and an MLflow default the library refuses. Done in S1.
2. `CLAUDE.md` pointed at Stage B while this file said Stage A. Done in S1.
3. `engine._evidence_reasons` reports only the first low-confidence field. Open.
4. `legal.py` lacks the §27 Abs. 38 UStG transition dates. Open; add when a rule needs them.
5. Missing tests: `legal.py`, `db migrate` and `db load` handlers, replay-fixture content. Open.
6. No end-to-end function and no DB persistence or `RuleContext` builder: `pipeline.py` in A4
   (SPEC 3.13), persistence in A6b.

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
- 2026-10-31: `db/` is the package `einvoice.db` (`db.py` plus `migrations/*.sql`), listed under `package-data` in `pyproject.toml`. `einvoice db migrate` applies the SQL; `einvoice db load` loads vendors, purchase orders and goods receipts from the seed output (B1 needs it, SPEC names no command).
- 2026-10-31: `convert.py` exists since A2 with only `invoice_to_cii` (drafthorse), because the generator needs it; A4 adds the `convert` command and the KoSIT check. It refuses allowances and charges instead of dropping them. It writes placeholder contact and electronic address, since XRechnung requires them and the canonical `Invoice` has neither.
- 2026-10-31: Generator is split into `synth/catalogue.py` (37 items, data), `synth/render.py` (UBL writer, 3 PDF layouts, scan) and `synth/generate.py`. Each is over 300 lines because `ruff format` puts one argument per line and the logic needs several steps; none has a second implementation or option behind it.
- 2026-10-31: `einvoice seed` has `--count` (default 2000) because unit tests need a small set. Output: `vendors.json`, `purchase_orders.json` (lines carry their goods receipt or `null` for 2-way match), `gold.jsonl`, `invoices/`. Scans are PNG files.
- 2026-10-31: Gold labels: the invoice `gl_account` is the account of its largest line; `reasons` hold only rule codes (no `KOSIT_REJECTED`, no `LOW_GL_CONFIDENCE`); for `vat_sum_off` the gold amounts are the correct ones, the document states the wrong VAT. `test_generate.py` runs the A1 rules engine over every structured file and requires reasons == gold reasons; the same check over all 2000 files of seed 1 agreed.
- 2026-10-31: `missing_vat_id` and `missing_delivery_date` are only injected into invoices above 250 EUR, because the rules (correctly) do not require them for small amounts (§33 UStDV). The generator scales the first line up to get there.
- 2026-10-31: The same seed gives identical files except ZUGFeRD PDFs: drafthorse writes the current time into them. The test compares the embedded XML for those.
- 2026-10-31: Vendor split 24 train / 6 validation / 10 test; an unknown-vendor invoice has its own one-off vendor and gets a random split.
- 2026-10-31: SKR03 numbers and names in `skr03_subset.csv` are from memory (generic names), not copied from an official table.
- 2026-10-31: `extract_invoice(pages, format, complete)` takes a plain `complete(prompt) -> str` instead of a chat model, since `llm.py` only arrives in A5; A5 wraps the chat model in a lambda. It returns `(Invoice, reasons)`; the reason `EVIDENCE_NOT_FOUND` is for the caller to add to the decision, the engine itself reports `LOW_EXTRACTION_CONFIDENCE` for the zeroed field.
- 2026-10-31: `ExtractedInvoice` is typed (`Extracted[Decimal]`, `Extracted[date]`), so a bad amount or date fails validation and triggers the one retry. It carries what the rules need (addresses, line price, line net sum, VAT breakdown, amount due). Line VAT category is set to `S` only for a positive rate; a 0 % rate leaves it empty.
- 2026-10-31: Replay fixtures `tests/fixtures/replay/extract_*.json` hold `{pdf, content}`, `content` being the JSON object the model would return. The third PDF is the synthetic `inv_00001.pdf` (copied to `tests/fixtures/synth/`), not a third corpus file: the corpus has no other plain-layout PDF in the fixtures and the unstructured Hetzner PDF names a person.
- 2026-10-31: Quote check compares with whitespace collapsed (line breaks in the PDF text layer would otherwise reject correct quotes); it is case- and character-exact otherwise.
- 2026-11-02: Stage A/B split dropped. Each phase has a `build` and a `live` part; the cloud does `build`, the laptop does `live`. Reason: the whole repo is on the owner's laptop now, and writing five phases without running them only moves the risk to the end.
- 2026-11-02: Copilot files removed; `CLAUDE.md` holds the conventions and `.claude/commands/{build,check,verify}.md` replace the prompt files. Reason: the project is now built with Claude Code.
- 2026-11-02: Branches are named `pranav/<phase>-<topic>`, one per session. Reason: the random cloud branch name says nothing about the work.
- 2026-11-02: `Makefile` gets `check` only; `up`, `down`, `test-integration` and `lock` arrive with the Compose file in R0a. Reason: no target for a file that does not exist.
- 2026-11-02: `Settings` holds `openai_api_key`, `openai_base_url` and `anthropic_api_key` (SecretStr); `mlflow_tracking_uri` defaults to `sqlite:///mlflow.db`. Reason: `.env` is read by pydantic-settings and not copied into `os.environ`, so `llm.py` must pass keys explicitly; MLflow 3.17 refuses the file store.
- 2026-11-02: The "tesseract binary is not installed in this WSL" line above is obsolete: R0a puts tesseract with the `deu` data into the dev container image.
- 2026-11-02: `pipeline.py` added to the SPEC (3.13). Reason: `evaluate.py` and the API need the same end-to-end function.
- 2026-11-02: UI stack is open until A6a; `streamlit` stays in `pyproject.toml` until then. Reason: the owner wants a designed, more interactive UI and reviews a prototype first.
- 2026-11-02: LLM for recording: try a free OpenAI-compatible provider (Gemini first) behind a probe in A5; ask the owner before using a paid provider. Reason: owner's request; replay fixtures keep tests independent of the provider.

## A4 findings so far (no A4 code written yet; checked in the venv here)
- MLflow 3.17 refuses the file store `./mlruns` (maintenance mode). `sqlite:///mlflow.db` works: runs, `mlflow.sklearn.log_model(name=...)`, `register_model`, alias `champion` and `load_model("models:/gl-coder@champion")`; artifacts still land in `./mlruns`. Plan: default `mlflow_tracking_uri` to `sqlite:///mlflow.db`, add `mlflow.db` to `.gitignore`.
- `CalibratedClassifierCV(FrozenEstimator(...))` fails when the calibration set lacks a class (IndexError) or is tiny. `CalibratedClassifierCV(pipeline, method="isotonic", cv=list(GroupKFold(5).split(X, y, sellers)))` works with string labels and rare classes. Plan: fit on train split with seller-grouped folds, pick champion on validation macro-F1, report test.
- `intfloat/multilingual-e5-small` downloads (~470 MB to `~/.cache/huggingface`), 384-dim, about 300 texts/s on CPU. Unit tests must replace the encoder (download = network boundary).
- Plan for the past-account feature: leave it out, since grouped test sellers never have history (log in decision log).
- Plan for `einvoice eval`: test split; `--fixtures` = no KoSIT call (structured counted as accepted, stated in `metrics.json`); pdf/scan without a replay response are skipped and counted in `metrics.json`.

## UNVERIFIED
Things written without being able to run them. Tag `[open: <phase>]` names the phase that
closes the line. Closing means running the real check, adding an integration test if none
covers it, and deleting the line.

- [open: R0b] `validation/kosit.py`: the daemon takes a POST of the raw XML at `/` and answers 200 (accept) or 406 (reject) with the report as body.
- [open: R0b] `tests/fixtures/kosit/report_reject_br_de_15.xml`: hand-written to the report schema; replace with a real daemon report for 01.01a UBL without BuyerReference and re-run `test_kosit.py`.
- [open: R0b] `tests/unit/validation/test_kosit.py::test_live_validator_accepts_a_testsuite_invoice` (integration) has never run.
- [open: R0b] `rules/legal.py`: `SMALL_AMOUNT_LIMIT` = 250 EUR (§33 UStDV) not checked against the primary source here.
- [open: R0b] `parsing/zugferd.py`: XRechnung PDFs attach `xrechnung.xml` (no fixture has one).
- [open: R0b] `db/migrations/001_init.sql`, `db/db.py`: never run against Postgres (pgvector extension, constraints, `migrate`, `load_master_data`); the unit test only checks the file text and a fake connection.
- [open: R0b] `convert.py`, `synth/render.py`: generated CII and UBL are XSD-valid (drafthorse validates CII) but never went through KoSIT; BR-DE rules and the placeholder contact are unconfirmed. Run the validator over `data/synth`.
- [open: R0b] `synth/generate.py`: ZUGFeRD PDFs are reportlab PDFs with `drafthorse.pdf.attach_xml`, not PDF/A-3; pypdf reads them, a strict PDF/A or Mustang check may reject them.
- [open: R0b] `synth/render.py`: the OCR legibility of the generated scans (rotation up to 1.5 degrees, noise) is unchecked; the A3 OCR tests skip without tesseract.
- [open: R0b] `data/rules/skr03_subset.csv`: account numbers and names not checked against an official SKR03 list.
- [open: R0b] `extraction/ocr.py`: `pytesseract.image_to_string(lang="deu")` and pypdfium2 `page.render(scale=300/72).to_pil()` never ran; both tests in `test_ocr.py` skip without the binary and the `deu` data.
- [open: A5] `extraction/prompts/extract_de.txt`: never sent to a real model; whether it yields valid JSON with exact quotes (and no code fences) is unknown. Replay fixtures are hand-written, not recorded.

## Blockers
Anything that stopped progress twice in a row, with what was tried.

None.
