# einvoice-agent: specification

## 1. Problem

Since 1 January 2025 every German business must be able to receive structured e-invoices
(EN 16931: XRechnung, ZUGFeRD/Factur-X from profile EN 16931 upward). Issuing them becomes
mandatory from 2027 for businesses with more than EUR 800k prior-year turnover and from 2028
for all (Wachstumschancengesetz; §14 UStG, transition rules in §27 Abs. 38 UStG; BMF letter
of 15.10.2024 and its follow-up letter; check the dates on bundesfinanzministerium.de). During the transition an accounts-payable inbox receives a
mix: XRechnung XML, ZUGFeRD PDFs with embedded XML, plain PDFs and scans.

Large companies buy ERP add-ons for this. Small businesses check invoices by hand.

Legal dates and thresholds are cited, not hard-coded as truth: they live in
`src/einvoice/rules/legal.py` as constants, each with its source (statute or BMF letter)
in a comment. Check them against the primary source before relying on them.

## 2. Goal and headline result

Turn any incoming invoice into a checked booking proposal. Book automatically only what
the checks can prove; send everything else to a reviewer with the exact reason.

Headline result: a **risk-coverage curve** on a labelled gold set.

- coverage = invoices booked automatically / all invoices
- risk = wrong automatic bookings / invoices booked automatically
- "wrong" = any of vendor, net, VAT, gross, GL account or due date differs from gold,
  or an invoice that gold marks as "must review" was booked automatically.

Report the highest coverage reached at zero observed wrong auto-bookings, the full curve,
and the 95% upper bound on the true risk at that point (rule of three: 3/n for n auto-booked
invoices with zero errors). This is computed by `einvoice.evaluate`, written to
`reports/metrics.json` and plotted to `reports/risk_coverage.png`.

Three rules hold everywhere:

1. Every extracted field carries its evidence: the XML element (BT id + XPath) for structured
   input, or page number and text span for PDF/scan input.
2. Rules decide; models extract and explain. No model output books anything on its own.
3. Every abstention is stored with machine-readable reason codes.

## 3. Pipeline

```
file ──> detect ──┬─ XML (UBL/CII) ──────────┐
                  ├─ ZUGFeRD PDF ─ embedded ─┤──> parse ──> KoSIT validate ─┐
                  ├─ plain PDF ── text ──────┤                              │
                  └─ scan ─────── OCR ───────┴──> LLM extract ──────────────┤
                                                                            v
                                   Invoice (canonical, with evidence + confidence)
                                                                            │
                     rules engine: §14 fields, arithmetic, USt-IdNr, duplicates,
                     PO / goods-receipt match, bank-detail change      ─────┤
                                                                            │
                     GL-account suggestion (SKR03, calibrated) ─────────────┤
                                                                            v
                                  decision: AUTO_BOOK | REVIEW(reasons)
                                                                            │
                            REVIEW ──> agent explains + proposes (cited) ──> person
                                                                 approve / correct
                                                                            │
                                     corrections become training labels (retrain)
```

### 3.1 Detect (`parsing/detect.py`)
Return one of `ubl`, `cii`, `zugferd_pdf`, `pdf`, `scan` from file bytes:
XML root namespace for UBL vs CII; PDF with an embedded `factur-x.xml` / `zugferd-invoice.xml`
/ `xrechnung.xml` attachment -> `zugferd_pdf`; PDF with an extractable text layer -> `pdf`;
image or PDF without text -> `scan`.

### 3.2 Structured path (`parsing/ubl.py`, `parsing/cii.py`, `parsing/zugferd.py`, `validation/kosit.py`)
- Parse with lxml into the canonical `Invoice`. Map by EN 16931 business terms; keep the
  XPath of each field as evidence. Confidence for parsed fields is 1.0.
- Fields used at minimum: BT-1 number, BT-2 issue date, BT-3 type code, BT-5 currency,
  BT-9 due date, BT-10 buyer reference (Leitweg-ID), BT-13 purchase order reference,
  BT-27 seller name, BT-31 seller VAT id, BT-32 seller tax registration, BT-35..40 seller
  address, BT-44 buyer name, BT-72 delivery date, BT-84 IBAN, BT-106 sum of line net,
  BT-109 total without VAT, BT-110 VAT total, BT-112 total with VAT, BT-115 amount due,
  per line BG-25 (BT-126 id, BT-129 quantity, BT-130 unit, BT-131 net, BT-146 price,
  BT-151 VAT category, BT-152 VAT rate, BT-153 item name), per VAT breakdown BG-23.
- ZUGFeRD: extract the embedded XML with pypdf and parse it as CII.
- KoSIT validation: HTTP POST of the XML to the validator daemon; parse the report into
  `ValidationResult(accepted: bool, errors: list[RuleViolation])` keeping rule ids such as
  `BR-DE-15`. Unit tests use a saved report XML; the live call is an integration test.

### 3.3 Unstructured path (`extraction/text.py`, `extraction/ocr.py`, `extraction/llm_extract.py`)
- Text per page with pdfplumber; scans via pytesseract `lang="deu"` (skip OCR tests when
  the tesseract binary is missing).
- The LLM receives the page texts and returns JSON matching `ExtractedInvoice`: each field
  has `value`, `page`, `quote` (the exact text it came from) and `confidence` in [0, 1].
- After parsing, the code checks every `quote` actually occurs on the given page. If it does
  not, the field's confidence is set to 0 (reason code `EVIDENCE_NOT_FOUND`).
- Prompt lives in `extraction/prompts/extract_de.txt`. Ask for JSON only; parse with
  `ExtractedInvoice.model_validate_json`; one retry with the validation error appended.

### 3.4 Canonical model (`models.py`)
pydantic models: `Evidence(source: "xml"|"pdf", xpath | (page, quote))`,
`Field[T](value, evidence, confidence)`, `LineItem`, `VatBreakdown`, `Invoice`,
`CheckResult(code, passed, message, severity)`, `Decision(kind: "AUTO_BOOK"|"REVIEW", reasons)`,
`BookingProposal(invoice_id, gl_account, amounts, due_date)`. Money as Decimal.

### 3.5 Rules engine (`rules/`)
Each check is a function `check_x(invoice, context) -> list[CheckResult]`; `engine.run` calls
them in a fixed list and builds the `Decision`.
- `ustg14.py`: mandatory content of §14 Abs. 4 UStG (seller/buyer name and address, VAT id
  or tax number, issue date, invoice number, quantity and description, delivery date or
  period, net per rate, rate, VAT amount). Small-amount invoices (§33 UStDV, threshold in
  `legal.py`) need fewer fields.
- `arithmetic.py`: line net = quantity x price (rounding to cents), sum of lines = BT-106,
  VAT per rate = rate x base, totals consistent; tolerance 0.01 EUR per line.
- `vat_id` check in `ustg14.py`: German USt-IdNr format `DE` + 9 digits with its check digit
  (ISO 7064 MOD 11,10). Format only; no online VIES call.
- `duplicates.py`: same seller VAT id + invoice number, or same seller + gross + issue date
  within 7 days.
- `matching.py`: 2-way match (invoice vs PO) and 3-way (plus goods receipt): price deviation
  per line <= 2% and quantity invoiced <= quantity received. Tolerances in the AP policy
  (`data/rules/ap_policy.md`) and as constants in `matching.py`.
- `fraud.py`: IBAN on the invoice differs from the vendor master record -> always REVIEW
  (`BANK_DETAILS_CHANGED`). Unknown vendor -> REVIEW.
- Decision: AUTO_BOOK only if the format is structured and KoSIT accepted it, or every
  required extracted field has confidence >= `extract_threshold`; all checks pass; PO match
  passes; and the GL suggestion probability >= `gl_threshold`. Otherwise REVIEW with all
  failing reason codes. The two thresholds are what `evaluate.py` sweeps.

### 3.6 GL-account suggestion (`ml/coding.py`, `ml/train.py`)
- Target: SKR03 account per invoice line (subset of ~25 accounts in `data/rules/skr03_subset.csv`).
- Features: line item text + seller name (+ seller's most frequent past account).
- Baseline: TF-IDF (word + char n-grams) + logistic regression.
- Second model: sentence embeddings (`intfloat/multilingual-e5-small`) + logistic regression.
- Both calibrated (`CalibratedClassifierCV`, isotonic) so the probability can gate AUTO_BOOK.
- Grouped split by seller, so the test set contains unseen sellers (avoids leakage).
- MLflow: log params, macro-F1, accuracy, expected calibration error, coverage at 98% precision;
  register the better model as `gl-coder`, alias `champion`.

### 3.7 Agent for exceptions (`agent/`)
- Runs only on REVIEW invoices. It **has no tool that books**. It writes a proposal row with
  status `pending`; booking only happens when a person approves in the UI/API.
- MCP server (`agent/mcp_server.py`, FastMCP from the `mcp` package) exposes read-only tools:
  `get_invoice(invoice_id)`, `get_purchase_order(po_number)`, `get_vendor_history(vat_id)`,
  `search_rules(query, k)`.
- `agent/rag.py`: chunks of UStG §14 (one per Absatz), the AP policy (one per heading) and the
  XRechnung business rules BR-DE-* (one per rule, text from the validator configuration),
  embedded with the same e5 model, stored in pgvector. `search_rules` returns chunks with
  source ids; if the best cosine similarity is below `min_similarity` it returns no chunks.
- `agent/graph.py` (LangGraph `StateGraph`): `agent` node (chat model with tools bound) <->
  `tools` node until the model answers, then `finalize` parses the answer into
  `AgentProposal(action: approve_booking|request_correction|reject|escalate, explanation,
  citations: list[source_id], vendor_email_de: str | None)`.
- Guardrails in `finalize`: every citation must be a source id returned by a tool call in
  this run; an explanation without citations, or with an unknown citation, becomes
  `escalate` with reason `UNSUPPORTED_EXPLANATION`. If `search_rules` returned nothing,
  action is `escalate` (`INSUFFICIENT_EVIDENCE`). No legal advice beyond the cited text.
- In the app the agent connects to the MCP server via `langchain-mcp-adapters` (stdio). In
  unit tests the same tool functions are bound directly (no transport).

### 3.8 LLM provider (`llm.py`)
One function `chat_model(settings)` with if/elif on `LLM_PROVIDER`:
- `replay`: `ReplayChatModel`, a small `BaseChatModel` subclass that returns pre-recorded
  `AIMessage`s (content and tool calls) from `tests/fixtures/replay/<case>.json`;
  `bind_tools` returns self. Used by tests and CI.
- `ollama`: `ChatOpenAI(base_url=OLLAMA_BASE_URL + "/v1", api_key="ollama", model=LLM_MODEL)`.
- `openai`: `ChatOpenAI(model=LLM_MODEL)`.
- `anthropic`: `ChatAnthropic(model=LLM_MODEL)`.
A `--record` flag on `einvoice eval` (A5, live) saves real responses as new replay fixtures.
The `openai` branch also covers any OpenAI-compatible endpoint (Google Gemini, Groq,
OpenRouter) through `OPENAI_BASE_URL`; the A5 provider probe decides which model records the
fixtures. API keys come from `Settings`, not from the process environment.

### 3.9 Feedback and retraining
Approving or correcting a proposal stores a row in `corrections` (field, old, new). The GL
account the reviewer confirms becomes a training label. `einvoice retrain` trains on the
synthetic set plus corrections, logs to MLflow, compares macro-F1 and coverage-at-zero-risk
against `champion`, and only moves the alias with `--promote`.

### 3.10 Monitoring and drift
- API exposes `/metrics` (prometheus_client): `einvoice_invoices_total{format,decision}`,
  `einvoice_review_reasons_total{reason}`, `einvoice_agent_proposals_total{action,outcome}`,
  `einvoice_processing_seconds` (histogram), `einvoice_gl_drift_psi` (gauge, read from the
  latest row of `drift_runs`).
- `ml/drift.py` (`einvoice drift`): population stability index (PSI) on gross amount and on
  predicted GL account distribution, and the share of unseen sellers, last 30 days vs the
  training reference. Written to `drift_runs`. PSI > 0.2 is flagged. Implemented with numpy
  (about 20 lines), no drift library.
- Grafana dashboard JSON in `deploy/grafana/einvoice.json`: touchless rate, review reasons,
  agent approval rate, latency p50/p95, drift PSI.

### 3.11 Outgoing side (`convert.py`)
`einvoice convert <invoice_id>` writes an XRechnung CII file from a checked `Invoice` (using
drafthorse) and validates it with KoSIT. Same code the synthetic generator uses.

### 3.12 API and UI
- FastAPI (`api/main.py`): `POST /invoices` (upload, runs the pipeline), `GET /invoices/{id}`,
  `GET /reviews`, `POST /reviews/{id}/agent`, `POST /proposals/{id}/approve`,
  `POST /proposals/{id}/correct`, `GET /health`, `GET /metrics`.
- Web UI, German and English (UI strings in one dict, language toggle). Streamlit is the
  placeholder in this SPEC; the stack is decided in A6a after the owner reviews a prototype
  (candidate: FastAPI + Jinja2 + HTMX, no Node build). Screens: inbox; invoice view with the
  PDF page next to the extracted fields, each field showing its evidence and confidence; check
  results; review queue with the agent's proposal, citations, optional German vendor email,
  and Approve / Correct / Reject.

### 3.13 End-to-end function (`pipeline.py`)
One function `process(path, context_source, ...)` runs detect, parse or extract, KoSIT
validation, the rules engine and the GL suggestion, and returns the `Invoice`, the check
results and the `Decision`. `evaluate.py` and the API both call it, so the evaluated path is the
served path. The KoSIT client, the chat model and the GL model are passed in, which is also how
tests replace them. It does not write to the database; persistence is in `db.py` (A6b).

## 4. Data

All sources are public or synthetic. `scripts/fetch_data.py` downloads into `data/raw/`
(git-ignored) and records URL, commit/release and licence in `DATA_SOURCES.md`.

| Source | Use | Licence |
|---|---|---|
| ZUGFeRD corpus, github.com/ZUGFeRD/corpus | real-layout PDFs; embedded XML is gold for PDF extraction | Apache-2.0 |
| XRechnung testsuite, github.com/itplr-kosit/xrechnung-testsuite | UBL/CII parser and rules tests | Apache-2.0 |
| KoSIT validator + validator-configuration-xrechnung, github.com/itplr-kosit | validation daemon; BR-DE rule texts for RAG | Apache-2.0 |
| UStG §14, §14a, §27 from gesetze-im-internet.de | RAG corpus, citations | official work, §5 UrhG |
| `data/rules/ap_policy.md` (written for this project) | AP policy: tolerances, approval rules | project licence |
| `data/rules/skr03_subset.csv` (written for this project) | ~25 SKR03 account numbers with generic names | project licence |
| Synthetic invoices (`einvoice.synth`) | training, gold set, demo | generated |

Small fixtures copied into `tests/fixtures/` keep their licence notice in
`tests/fixtures/NOTICE`.

### 4.1 Synthetic generator (`synth/generate.py`, `einvoice seed`)
Seeded (`--seed`), Faker `de_DE`. Generates 40 vendors (with VAT id, IBAN, typical item
categories), an item catalogue mapped to SKR03 accounts (some items legitimately map to two
accounts depending on the vendor, so the classifier has real ambiguity), purchase orders,
goods receipts and ~2,000 invoices rendered as: CII XML 25%, UBL XML 15%, ZUGFeRD PDF 30%,
plain PDF in 3 reportlab layouts 25%, scans 5% (PDF rasterised with pypdfium2, slight rotation
and noise). About 20% carry one labelled problem: missing VAT id, VAT sum off, duplicate,
price above PO tolerance, quantity above goods receipt, changed IBAN, unknown vendor, wrong
VAT rate, missing delivery date. Gold labels: correct booking per invoice and
`must_review: bool` with the expected reason codes. Split: train / validation / gold-test by
vendor groups.

## 5. Dependencies

Pin with `~=` to the version pip resolves in A0.

- core: pydantic, pydantic-settings, lxml, pypdf, pdfplumber, pypdfium2, pytesseract, Pillow,
  reportlab, drafthorse, faker, httpx, psycopg[binary], pgvector, numpy, scikit-learn,
  mlflow, sentence-transformers, matplotlib
- agent extra: langgraph, langchain-core, langchain-openai, langchain-anthropic, mcp,
  langchain-mcp-adapters
- api extra: fastapi, uvicorn, prometheus-client, python-multipart
- ui extra: streamlit
- dev extra: pytest, ruff

Not used, on purpose: an ORM, Airflow, Celery/queues, TensorFlow, a drift library, a vector
DB other than pgvector, LangChain chains/agents beyond what LangGraph needs.

## 6. Database (`db/migrations/*.sql`, `db/db.py`)
Plain SQL migrations applied in order by `einvoice db migrate` (a `schema_migrations` table
records applied files). psycopg 3, parameterised queries only.
Tables: `vendors`, `purchase_orders`, `po_lines`, `goods_receipts`, `invoices` (canonical JSON
in a `jsonb` column plus indexed columns), `checks`, `decisions`, `proposals`, `bookings`,
`corrections`, `rule_chunks` (with `embedding vector(384)`), `drift_runs`.
Unique constraint on (seller_vat_id, invoice_number) backs the duplicate rule.

## 7. Deployment (built phase by phase; the environment first, the rest in A4-A8)
- Dev container (`.devcontainer/`, R0a): VS Code opens the repo in the `dev` Compose service, so a
  fresh clone gives the same Python, tesseract and pinned packages (`requirements.lock`).
- One Docker image (`deploy/docker/Dockerfile`, python slim, CPU-only torch wheels) used for
  api, ui and jobs with different commands; a second small image for the KoSIT validator
  (`deploy/docker/validator.Dockerfile`, Temurin JRE, daemon on port 8081).
- `deploy/compose.yaml`: dev, postgres (pgvector/pgvector), validator from R0a; mlflow from A4;
  api, ui from A6b; prometheus, grafana from A7. Services sit in profiles (`core`, `ml`, `obs`)
  so a laptop with 6 GB RAM runs only what a phase needs.
- `deploy/k8s/` (kustomize): postgres StatefulSet + PVC, validator, mlflow, api, ui
  Deployments and Services, drift CronJob (daily), Prometheus and Grafana (plain manifests),
  Secret for DB password created by the user (`kubectl create secret ...`, never in git).
- `.github/workflows/ci.yml`: `on: workflow_dispatch` only until A9. Jobs: ruff + unit
  tests; eval gate (`einvoice eval --provider replay --fixtures`, fails if risk > 0 at the
  chosen thresholds or coverage drops below `reports/baseline.json`); build and push image to
  GHCR (main only); kind smoke test (create cluster, `kubectl apply -k`, wait, curl `/health`).
- `deploy/terraform/` (Azure): resource group, Container Apps environment, container apps
  for api, ui, validator (images from GHCR, scale to zero), PostgreSQL Flexible Server B1ms
  with the `vector` extension allowed, and `azurerm_consumption_budget_resource_group` with
  an email alert. MLflow stays local; the champion model is baked into the image at build.

## 8. Phases

The build order is fixed. Each phase has a `build` part (code and unit tests; works without
services) and a `live` part (checked against the real Postgres, KoSIT validator, LLM, Docker).
A phase is finished when both are done, its UNVERIFIED lines are closed, `ruff` and
`pytest -m "not integration"` pass, `pytest -m integration` passes for what it touched, its
design note and `docs/PHASE_LOG.md` entry exist, and STATE.md is updated. A session without
services (the cloud) does the `build` part and records what it could not run as UNVERIFIED.

| Phase | Produces | Live check | STOP |
|---|---|---|---|
| A0 Scaffold (done) | `pyproject.toml`, `Makefile`, `.env.example`, `.gitignore`, `LICENSE`, `DATA_SOURCES.md`, `scripts/fetch_data.py`, `src/einvoice/{__init__,config,cli}.py` | `einvoice --help` lists subcommands | |
| A1 Core (done) | `models.py`, `parsing/*`, `validation/kosit.py`, `rules/*` incl. `legal.py`, `tests/fixtures/` (a dozen files, NOTICE, one KoSIT report) | parsers read all fixtures; each rule has passing and failing cases | |
| A2 Data (done) | `synth/*`, `data/rules/ap_policy.md`, `data/rules/skr03_subset.csv`, `db/migrations/*.sql`, `db/db.py`, `convert.py` (`invoice_to_cii`) | `einvoice seed --seed 1` output parses with the A1 parsers; same seed, same output | |
| A3 Extraction (done) | `extraction/*`, prompt file, `tests/fixtures/replay/extract_*.json` | quote check sets confidence 0 on a planted wrong quote | |
| R0a Environment | `.devcontainer/`, `deploy/docker/Dockerfile`, `deploy/docker/validator.Dockerfile`, `deploy/compose.yaml` (dev, postgres, validator), `requirements.lock`, Makefile targets, README quick start | fresh clone: "Reopen in Container", `make check` and `make test-integration` pass | |
| R0b Catch-up | fixes found by the audit of A0-A3 (see STATE.md), integration tests for DB and validator | every UNVERIFIED line of A0-A3 closed; `pytest -m integration` green | |
| A4 Models + eval | `ml/coding.py`, `ml/train.py`, `convert.py` (+ KoSIT check, `convert` command), `pipeline.py`, `evaluate.py`, `train` and `eval` commands, `mlflow` service in Compose | `einvoice train` logs both models and registers `champion`; `einvoice eval` writes `reports/metrics.json` and `reports/risk_coverage.png` with the live validator | |
| A5 Agent | `agent/*`, `llm.py`, `evals/agent_cases.yaml` (about 30 cases), replay fixtures per case | provider probe, `einvoice eval --record`, re-recorded extraction fixtures, `reports/agent_eval.json` | owner reviews recorded fixtures and extraction accuracy |
| A6a UI design | UI brief, user flows, clickable prototype, German/English string list | owner approves the prototype | owner approves or edits the design and may supply a template |
| A6b API + UI | `api/main.py`, persistence functions in `db.py`, the approved UI | upload, review, approve, booking against Compose Postgres | owner tries 5 cases in the UI |
| A7 Monitoring | metrics in `api/main.py`, `ml/drift.py`, `einvoice retrain`, `einvoice drift`, `deploy/grafana/einvoice.json`, Prometheus in Compose | Grafana shows live metrics; a drift row is written | |
| A8 Infra | full `deploy/docker/*`, `deploy/compose.yaml`, `deploy/k8s/*`, `.github/workflows/ci.yml` (dispatch-only), `deploy/terraform/*` | full Compose stack; kind deploy with `/health` and the drift CronJob; `terraform validate` | |
| A9 Ship | CI on push/PR, Azure demo, `docs/RELEASE_CHECKLIST.md`, `README.md` with numbers from `reports/`, demo GIF, `docs/notes/*` | CI green; public URL works during the demo; release gate passed | before the first GHCR push; before Azure (owner sets a budget); release gate sign-off before the repo is public |

Test commands: `ruff check . && pytest -m "not integration" -q` for every phase;
`pytest -m integration -q` where the phase touched a service.

### Release gate (A9)

Run by the agent, one result per item written to `docs/RELEASE_CHECKLIST.md`, signed off by
the owner before the repository is public.

- Secrets: scan the working tree and the full git history (gitleaks or trufflehog in a
  container, plus GitHub secret scanning). `.env`, `mlflow.db`, Terraform state,
  `.claude/settings.local.json` and key files are not tracked and never were. Rotate any key
  that ever appeared in a file.
- Personal data: search fixtures, `DATA_SOURCES.md`, docs and git author metadata for names,
  emails and IBANs that are not from the generator. Confirm every corpus file is public and has
  its licence notice. The commit email is a no-reply address.
- Dependencies and images: `pip-audit` on `requirements.lock`, Trivy on both images, licence
  check of the dependencies against the repository's MIT licence.
- Hardening: no default passwords outside local Compose; Compose ports bound to localhost;
  Kubernetes and Terraform read secrets from Secrets or variables; upload size limit and file
  type check in the API; XML parsing safe against XXE (retest with a hostile sample); CORS and
  CSRF settings of the web app; no stack traces in API responses.
- Agent safety: the guardrail tests pass (no booking tool, unknown citation escalates, empty
  retrieval escalates); invoices with instructions hidden in the PDF text do not change the
  decision.
- Repository hygiene: `CLAUDE.md`, `.claude/`, `STATE.md` and the docs contain no private notes
  or machine paths; branch protection on `main`; secret scanning and Dependabot enabled.

## 9. Design note template (`docs/notes/<topic>.md`)

```
# <Component>
What it does: two or three sentences.
How it works: the steps, with file and function names.
Why this way: the choice and the alternative I rejected, with the reason.
How it is tested: which tests, what they prove, what they do not.
Limits: what would break first and what I would change next.
```
