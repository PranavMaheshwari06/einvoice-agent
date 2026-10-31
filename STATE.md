# Build state

Read this first in every session. Update it before every commit.

Current stage: **A** (write code, unit tests only)
Next: **A4**

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
- [x] A2 Data: synthetic generator, AP policy, SKR03 subset, migrations
- [x] A3 Extraction: text, OCR, LLM extraction with evidence check
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

## UNVERIFIED
Things written in Stage A that could not be run there. Stage B checks each one and
deletes the line when it is confirmed or fixed.

- `validation/kosit.py`: the daemon takes a POST of the raw XML at `/` and answers 200 (accept) or 406 (reject) with the report as body.
- `tests/fixtures/kosit/report_reject_br_de_15.xml`: hand-written to the report schema; replace with a real daemon report for 01.01a UBL without BuyerReference and re-run `test_kosit.py`.
- `tests/unit/validation/test_kosit.py::test_live_validator_accepts_a_testsuite_invoice` (integration) has never run.
- `rules/legal.py`: `SMALL_AMOUNT_LIMIT` = 250 EUR (§33 UStDV) not checked against the primary source here.
- `parsing/zugferd.py`: XRechnung PDFs attach `xrechnung.xml` (no fixture has one).
- `db/migrations/001_init.sql`, `db/db.py`: never run against Postgres (pgvector extension, constraints, `migrate`, `load_master_data`); the unit test only checks the file text and a fake connection.
- `convert.py`, `synth/render.py`: generated CII and UBL are XSD-valid (drafthorse validates CII) but never went through KoSIT; BR-DE rules and the placeholder contact are unconfirmed. Run the validator over `data/synth` in B1.
- `synth/generate.py`: ZUGFeRD PDFs are reportlab PDFs with `drafthorse.pdf.attach_xml`, not PDF/A-3; pypdf reads them, a strict PDF/A or Mustang check may reject them.
- `synth/render.py`: no tesseract here, so the OCR legibility of the generated scans (rotation up to 1.5 degrees, noise) is unchecked; A3 OCR tests skip without it.
- `data/rules/skr03_subset.csv`: account numbers and names not checked against an official SKR03 list.
- `extraction/ocr.py`: `pytesseract.image_to_string(lang="deu")` and pypdfium2 `page.render(scale=300/72).to_pil()` never ran (no tesseract binary, no `deu` language data); both tests in `test_ocr.py` skip here.
- `extraction/prompts/extract_de.txt`: never sent to a real model; whether it yields valid JSON with exact quotes (and no code fences) is unknown. Replay fixtures are hand-written, not recorded.

## Blockers
Anything that stopped progress twice in a row, with what was tried.
