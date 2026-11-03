# Build state

Read this first in every session. Update it before every commit.

Current phase: **live passes on the laptop** (R0b live in progress, then A4 live, then A5 live).
A0 to A5 are built; R0a is live. S4 (A6a UI design) is built on `pranav/a6a-ui-design`, is not
merged, and awaits the owner's review (STOP).
Rules: `CLAUDE.md`. Design: `docs/SPEC.md`. History: `docs/PHASE_LOG.md`.

## Next session
Laptop (dev container), in this order. Each branch starts from the updated `main` after the
previous pull request is merged.

1. R0b live on `pranav/r0b-live` (in progress). Three UNVERIFIED lines wait for the owner's decision: §33 UStDV, PDF/A, SKR03. First message: "Start L1 from STATE.md: close the R0b UNVERIFIED lines (Postgres migrations and loading, KoSIT over data/synth, real daemon report fixture), then stop."
2. A4 live on `pranav/a4-live`, started from `main` after R0b live is merged. First message: "Start A4 live from STATE.md: add the mlflow service to deploy/compose.yaml, close every [open: A4] UNVERIFIED line with /verify, check for leakage before any number is written down, then stop for the owner's calibration decision." Steps: add the `mlflow` service to `deploy/compose.yaml` (SPEC 7 and 8: profile `ml`, port bound to 127.0.0.1, a decision-log line); `einvoice seed`; `einvoice train` with the real e5 model, which also checks the "query: " prefix in `ml/coding.py`; `load_champion` from the Compose MLflow service; `einvoice eval` with the live validator; `einvoice convert` through KoSIT. Plausibility first: if a number looks too good, look for leakage (seller split, thresholds chosen on validation only, worst errors) before writing it down. Commit and push, open no PR yet. STOP for the calibration decision: show `ece` and `ece_uncalibrated` for both models from `reports/gl_coder.json`, from `reports/metrics.json` the test result at the operating point (coverage, wrong, risk_upper_95) and the worst errors, explain the "A4 findings" block, and recommend either isotonic as specified or top-label isotonic on out-of-fold scores. Do not tick A4 live before the decision. After it: apply it (retrain if needed), update `reports/`, this file and `docs/PHASE_LOG.md`, open the PR "A4 live".
3. A5 live on `pranav/a5-live`, started from `main` after A4 live is merged. First message: "Start A5 live from STATE.md: run the provider probe, index the rules, record extraction and agent fixtures, write reports/agent_eval.json, then stop for the owner's review." Steps: `make fetch`; `einvoice db migrate`, `einvoice db index`; set `MIN_SIMILARITY` from a few relevant and unrelated queries; probe = `einvoice agent-eval` with each candidate `LLM_PROVIDER` (Gemini through `OPENAI_BASE_URL` first, ask before a paid one); `einvoice agent-eval --record` and `einvoice eval --record` with the chosen model; the owner reviews the recorded fixtures and the extraction accuracy (STOP).

Waiting for the owner (no session to start): S4 (A6a UI design) is built on `pranav/a6a-ui-design` (2 commits on top of `pranav/a5-agent`; not merged into `main`). The owner reviews `docs/ui/brief.md` and `docs/ui/prototype/index.html` and answers the open points in the brief (STOP). S5 (A6b build, A7 build) starts only after that; its brief is in the STATE.md of `pranav/a6a-ui-design`.
Do not touch: A6b code (API, persistence, UI); the files under `docs/ui/` (they live on `pranav/a6a-ui-design`).

## Sessions
One session per row. The branch of a session starts from the tip of the previous one unless
that one is already merged into `main`.

| Session | Phase | Where / model | Branch |
|---|---|---|---|
| S1 (done) | instruction files, R0b cloud fixes | cloud, Sonnet | `pranav/claude-code-setup` |
| S2 | A4 build | cloud, Opus | `pranav/a4-models-eval` |
| S3 (done) | A5 build | cloud, Opus | `pranav/a5-agent` |
| S4 (built, awaiting owner review, not merged) | A6a UI design | cloud, Opus | `pranav/a6a-ui-design` |
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
- [x] R0a Environment (dev container, Dockerfile, Compose, lockfile): [x] build, [x] live (L1)
- [ ] R0b Catch-up: [x] build (cloud, S1), [ ] live (laptop)
- [ ] A4 Models + eval: [x] build (S2), [ ] live
- [ ] A5 Agent: [x] build (S3), [ ] live (provider probe, recording; STOP)
- [ ] A6a UI design: [x] prototype built (S4, on `pranav/a6a-ui-design`, not merged), [ ] owner approval (STOP)
- [ ] A6b API + UI: [ ] build (S5), [ ] live (STOP)
- [ ] A7 Monitoring: [ ] build (S5), [ ] live
- [ ] A8 Infra: build, live (laptop)
- [ ] A9 Ship: CI, Azure, release gate, README (laptop; STOPs)

## R0b cloud findings (from the audit before S1)
1. `config.py` had no key or base-URL fields and an MLflow default the library refuses. Done in S1.
2. `CLAUDE.md` pointed at Stage B while this file said Stage A. Done in S1.
3. `engine._evidence_reasons` reports one code once; `run` de-duplicates codes, so REVIEW reasons are complete. Not a defect, closed.
4. `legal.py` lacks the §27 Abs. 38 UStG transition dates. Deferred until a rule needs them.
5. Missing tests for `legal.py` and the `db migrate` / `db load` handlers. Done in S1 (`test_legal.py`, `test_cli.py`).
6. No end-to-end function and no DB persistence or `RuleContext` builder: `pipeline.py` in A4 (SPEC 3.13), persistence in A6b.

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
- 2026-10-31: SKR03 numbers and names in `skr03_subset.csv` were written from memory (generic names). 2026-11-03: every number was checked against the DATEV Standardkontenrahmen SKR 03, Art.-Nr. 11174, valid 2026 (the datev.de PDF, read as text). 22 numbers exist there with a matching account; 0650 and 0670 are bank-liability sub-accounts and 4610 does not exist, so they became 0420, 0480 and 4600. The names stay the project's own short forms (the DATEV list may not be reprinted); 4210, 4530, 4800, 4940, 4964 and 4980 are worded differently from DATEV's, and DATEV's 4800 is narrower (technical equipment and machines). Not checked: whether each catalogue item belongs on its account. `tests/unit/synth/test_catalogue.py` pins the pairs.
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
- 2026-11-02: `test_three_replay_cases_exist` stays. The parametrized replay test already validates every fixture and its PDF, and the count guards against the parametrization silently becoming empty.
- 2026-11-02: LLM for recording: try a free OpenAI-compatible provider (Gemini first) behind a probe in A5; ask the owner before using a paid provider. Reason: owner's request; replay fixtures keep tests independent of the provider.
- 2026-11-02: GL model input is "item name | seller name" per line; the invoice account is predicted from the largest line, matching the gold label. The past-account feature is left out because grouped test sellers never have history.
- 2026-11-02: MLflow models are logged with `serialization_format="cloudpickle"`. Reason: skops (the default in 3.17) refuses `_CalibratedClassifier` and the injected encoder; the models come only from our own training run.
- 2026-11-02: `E5Encoder` caches vectors by text and returns itself from `__deepcopy__`. Reason: `CalibratedClassifierCV` clones the pipeline per fold and `clone` deep-copies `kw_args`, which would load the model and encode the same texts five times.
- 2026-11-02: `train` writes `reports/gl_coder.json` (both models, validation and test, raw-model ECE). Reason: the baseline comparison needs a file under `reports/` to be quoted.
- 2026-11-02: `engine.decide(invoice, context, results)` split out of `engine.run`, and `RuleContext.extraction_reasons` added. Reason: the threshold sweep re-decides stored results without running the checks again, and AUTO_BOOK is decided in one place.
- 2026-11-02: `pipeline.process` takes file bytes, not a path (SPEC 3.13 says path). Reason: the API receives uploads.
- 2026-11-02: `einvoice convert <file> --out <xml>` instead of `convert <invoice_id>` (SPEC 3.11). Reason: no stored invoices before A6b; switch to the id there.
- 2026-11-02: `einvoice eval` reads replay responses from `<dir>/replay/<id>.json` (`{pdf, content}`, the A3 fixture format); PDFs and scans without one are skipped and counted. Thresholds: extraction 0.5 to 0.99 (6 values), GL 0 to 1 in steps of 0.01; the operating point is the highest validation coverage with zero wrong bookings, ties to the stricter thresholds; the rule-of-three bound is capped at 1.
- 2026-11-02: `cli.main` sets `MLFLOW_DISABLE_TELEMETRY=true` unless set, and `tests/conftest.py` sets it. Reason: MLflow 3.17 sends usage telemetry over the network by default; the cloud proxy blocked it during a test run.
- 2026-11-02: R0a: `requirements.lock` is a plain `pip freeze` written by `make lock` from a clean python:3.12-slim container, with torch installed first from the PyTorch CPU index and that index as the first line of the file. Reason: pip alone is enough because `pyproject.toml` already pins with `~=`; uv or pip-tools would be a new tool for a file that changes rarely.
- 2026-11-02: R0a: one `Dockerfile` for dev and later api and ui, with the dev tools (pytest, ruff, make, git) in it; the user is uid 1000. Reason: tests run on the image that ships; a root user would leave root-owned `.pytest_cache` and `data/synth` in the mounted repo. The HF model cache is a named volume so a rebuild does not download e5 again.
- 2026-11-02: R0a: all three services sit in the Compose profile `core`, ports are bound to 127.0.0.1, the Postgres image is `pgvector/pgvector:pg16`, and `devcontainer.json` names the three services in `runServices`. `make install` is removed (the lock replaces it); `up`, `down` and `lock` run on the host, the other targets inside the container.
- 2026-11-02: R0a: the validator image pins jar v1.6.3 and configuration v2026-08-31 (XRechnung 3.0.2) as build ARGs, the same versions as `DATA_SOURCES.md`; Temurin 21 JRE because the configuration docs ask for Java 11 or later. `ADD --chmod=644` because a downloaded file is root-only otherwise and the daemon runs as a system user.
- 2026-11-02: `models.value_of` and `ustg14.compact_vat_id` are shared helpers. Reason: the field-unwrap and VAT-id compaction had several copies; evaluation must compare an extracted "DE 123 456 789" with the compact master-data id.
- 2026-11-02: S3 branch `pranav/a5-agent` starts from `origin/main` (owner: A4 and R0a are merged). The cloud venv has no torch: the PyTorch CPU index is blocked here, so the lock was installed without torch and sentence-transformers; unit tests stub the encoder anyway.
- 2026-11-02: `llm.chat_model(settings, replay_file=None)`; replay needs the file. Agent replay fixtures are `{case, source, responses: [{content, tool_calls}]}` with `source` "hand-written" or "recorded from <provider>:<model>", so a report can say where its answers came from. Extraction keeps its `{pdf, content}` format (A3, brief). `llm.complete(model, prompt)` is the `complete` extraction takes.
- 2026-11-02: `agent/evals.py` (not named in the SPEC) runs `evals/agent_cases.yaml`; `einvoice agent-eval [--record]` writes `reports/agent_eval.json`. Each case fixes the tool answers and `search_rules` returns the case's chunks for any query, so a run depends only on the model and a recording replays identically. Baseline: escalate every invoice. PyYAML (already in the lock) is now a direct dependency of the `agent` extra for the SPEC's YAML file.
- 2026-11-02: `einvoice db index` builds `rule_chunks` from `data/raw` and the AP policy. Reason: the RAG needs the table filled and the SPEC names no command.
- 2026-11-02: Source ids: `UStG-14-<Absatz>`, `AP-<heading slug>`, BR-DE rule ids. BR-DE texts come from the UBL schematron of the validator configuration (39 rules incl. BR-DE-CVD-* and BR-DE-TMP-32, no BR-DEX; UBL texts are all German, CII has one English text). The schematron is copied unchanged to `tests/fixtures/kosit/`.
- 2026-11-02: e5 prefixes for retrieval: `query: ` for queries, `passage: ` for indexed texts, confirmed in the authors' code (`microsoft/unilm`, `e5/mteb_beir_eval.py`; Hugging Face is blocked here). `E5Encoder` takes the prefix. An encoder pickled before this change has no `_prefix`; no champion is registered yet (A4 live not run), so retraining in A4 live is enough.
- 2026-11-02: `AgentProposal` has `reasons` for the guardrail codes. A fourth code, `INVALID_PROPOSAL`, covers an answer that is not valid proposal JSON (also prose or code fences), and a run cut off after `MAX_TOOL_ROUNDS` = 6 rounds of tool calls. An overruled proposal keeps no model text, citations or email. `INSUFFICIENT_EVIDENCE` also applies when `search_rules` was never called.
- 2026-11-02: `search_rules` returns `{"chunks": [...]}`, at most `MAX_CHUNKS` = 8. Reason: FastMCP splits a returned list into several content items, and every returned chunk becomes citable. `MIN_SIMILARITY` = 0.80 is provisional; the SPEC rule "best below the cut-off, no chunks" is applied literally.
- 2026-11-02: `models.NotFound(LookupError)` marks a missing invoice or PO. The tool node sends only `NotFound` back to the model, because `KeyError` is a `LookupError` too and would hide programming errors. Over MCP the adapter returns every server error as a message (its default), so a database failure ends as an escalation.
- 2026-11-02: `get_invoice` returns field values without evidence (`invoice_summary`), plus review reasons and failed checks. Reason: the canonical record with XPaths and quotes is several times larger and the agent cites rules, not fields.
- 2026-11-02: `evaluate.run_gold` takes `complete_for(record)` (`replay` or `recording`) instead of a replay directory. `einvoice eval --record` sends PDFs and scans to `LLM_PROVIDER` and keeps the last reply that parses as JSON, so extraction's one retry still works while recording. `metrics.json` has an `extraction` field naming the source of the replies.
- 2026-11-02: `einvoice agent-eval` builds the corpus from `data/raw` also in replay mode, although replay never reads chunk texts. Reason: the same run checks that every case's source id exists in the real sources; CI does not run the agent eval (SPEC 7 gates only `einvoice eval`).

## A4 findings (S2, cloud run on seed 1, 2000 invoices, hashing stub instead of e5, KoSIT skipped)
Numbers are not quoted here because they come from a stubbed run outside `reports/`; rerun
`einvoice train` and `einvoice eval` live to get them.
- Isotonic calibration as prescribed (`CalibratedClassifierCV`, seller-grouped `GroupKFold(5)`) did not beat the raw TF-IDF model on validation ECE, and it cut coverage at 98 % precision to a small fraction of the raw model's on both validation and test. `ensemble=False` and sigmoid did not change that. Cause: train folds (unseen sellers) are harder than the six validation sellers, so calibrated scores come out underconfident there, and isotonic steps put many lines on one plateau. Not turned into a passing test because it does not hold; `gl_coder.json` records `ece` and `ece_uncalibrated` side by side. Owner decision for the live run: keep as specified, or try top-label isotonic on out-of-fold scores.
- Pipeline on structured invoices (fixtures mode): the rules sent every must-review invoice to review and blocked no clean invoice; every wrong booking at low thresholds was the GL account of an unseen seller. Test coverage at zero wrong bookings was low, with a wide rule-of-three bound. The headline number therefore depends on the GL model, not on the rules.
- Part of the validation and test lines are ambiguous by item: the same item is booked to a different account by different vendors (the generator's `alt_account`), which caps accuracy for unseen sellers.

## UNVERIFIED
Things written without being able to run them. Tag `[open: <phase>]` names the phase that
closes the line. Closing means running the real check, adding an integration test if none
covers it, and deleting the line.

- [open: L1 owner] "Reopen in Container" in VS Code was not clicked; R0a checked `.devcontainer/devcontainer.json` with the devcontainer CLI (`up`, `exec`), which reads the same file.
- [open: owner] `rules/ustg14.py::check_mandatory_fields`: applies the §33 UStDV small-invoice relief to every invoice with a gross total up to 250 EUR. §33 says that relief does not apply to invoices for services under §§ 3c, 6a and 13b UStG, and the rule does not look at that. Left unchanged on the owner's decision; decide whether the SPEC needs it or the README Limitations name it.
- [open: R0b] `synth/generate.py`: the ZUGFeRD PDFs (reportlab plus `drafthorse.pdf.attach_xml`) are not valid PDF/A-3. Checked 2026-11-03 with Mustang-CLI 2.26.0 (the jar's sha256 equals GitHub's digest for core-2.26.0), run in a container without network: the control `tests/fixtures/corpus/MustangGnuaccountingBeispielRE-20201121_508.pdf` is PDF/A-3u compliant; `data/synth/invoices/inv_00011.pdf` and `inv_00012.pdf` (seed 1) fail PDF/A-3b on the same two rules, ISO 19005-3 §6.2.11.4.1 (Helvetica and Helvetica-Bold are not embedded) and §6.2.4.3 (DeviceGray without an output intent). The XML of inv_00012 is valid; the XML of inv_00011 fails only on its injected `vat_sum_off`. Mustang exits 0 for inv_00012 although its PDF is invalid, so a check must read the report, not the exit code. Not fixed on the owner's decision; the README Limitations names it. Closes when the generator writes PDF/A-3 (embedded fonts, an output intent) or the owner accepts the limitation for good.
- [open: A5] `extraction/prompts/extract_de.txt`: never sent to a real model; whether it yields valid JSON with exact quotes (and no code fences) is unknown. Replay fixtures are hand-written, not recorded.
- [open: A4] `ml/coding.py::E5Encoder`: `SentenceTransformer("intfloat/multilingual-e5-small").encode(..., normalize_embeddings=True)` never ran here (no HuggingFace access, sentence-transformers not installed); the "query: " prefix is from the model card. Run `einvoice train` with the real model.
- [open: A4] `ml/train.py`: MLflow runs, registry and alias were checked only against a local SQLite store; the Compose MLflow service and `load_champion` from it are untested.
- [open: A4] `einvoice eval` without `--fixtures`: never called the live KoSIT daemon; `reports/metrics.json` and `risk_coverage.png` with live validation do not exist yet.
- [open: A4] `einvoice convert`: the written CII never went through the live KoSIT daemon.
- [open: A5] `evaluate.run_gold`: PDFs and scans are skipped until replay responses exist under `<dir>/replay/`; scans also need tesseract.

- [open: A5] `llm.py`: the `ollama`, `openai` (Gemini through `OPENAI_BASE_URL`) and `anthropic` branches never reached a provider [cloud-built]; tool calling and the JSON answer format are unchecked. The provider probe decides the model.
- [open: A5] `agent/prompts/review_en.txt` and the 32 fixtures `tests/fixtures/replay/agent_*.json`: written by hand, never sent to or recorded from a model [cloud-built]. Re-record with `einvoice agent-eval --record`; the owner reviews them (STOP). `reports/agent_eval.json` does not exist yet.
- [open: A5] `agent/rag.py::ustg_chunks`: assumes the gesetze-im-internet.de XML has `norm/metadaten/enbez` = "§ 14" and one `textdaten/text/Content/P` per Absatz starting with "(n)", and no named entities that need the DTD [cloud-built]; the host is blocked here and `tests/fixtures/ustg/ustg_structure.xml` is hand-written. The UStG ids in the cases (`UStG-14-4`) are checked only then.
- [open: A5] `agent/rag.py::store`, `nearest`: never ran against pgvector [cloud-built] (text literal with `::vector`, `<=>` as cosine distance, named parameters). `MIN_SIMILARITY` = 0.80 is a placeholder value to set from live queries; chunk lengths against e5's 512 tokens are unchecked.
- [open: A5] `db/db.py::fetch_invoice`, `fetch_purchase_order`, `fetch_vendor_history` and the MCP tools on top: never ran against Postgres [cloud-built]; the stdio test only lists the tools. Full use needs stored invoices (A6b).
- [open: A5] `einvoice eval --record`: never called a model [cloud-built]; the existing extraction fixtures are still hand-written (line above about `extract_de.txt`).

## Blockers
Anything that stopped progress twice in a row, with what was tried.

None.
