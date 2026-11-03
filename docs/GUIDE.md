# Guide to the project

For the owner, to learn and explain the project. Extended in every phase. Design decisions are
in `docs/SPEC.md`, per-component notes in `docs/notes/`, history in `docs/PHASE_LOG.md`.

## What the project does

An accounts-payable team receives invoices as XML, PDFs with embedded XML, plain PDFs and
scans. The pipeline reads each one into the same `Invoice` model, checks it against the rules
a booking clerk would apply, and either proposes a booking automatically or sends it to a
person with the reasons. Models read and explain; rules decide.

## Terms

- **XRechnung**: the German e-invoice standard (XML, EN 16931). Syntaxes: UBL and CII.
- **ZUGFeRD / Factur-X**: a PDF with the invoice XML embedded.
- **EN 16931**: the European semantic model. Fields are numbered business terms (BT-1 is the
  invoice number, BT-109 the net total).
- **KoSIT validator**: the official checker for XRechnung; it returns rule ids such as
  BR-DE-15.
- **§14 UStG**: the German VAT law section that lists what an invoice must contain.
- **§33 UStDV**: lowers those requirements for invoices up to 250 EUR.
- **SKR03**: a standard chart of accounts; the GL (general ledger) coder predicts one.
- **2-way / 3-way match**: invoice against purchase order / against purchase order and goods
  receipt.
- **Risk-coverage curve**: share of invoices booked automatically (coverage) against the share
  of wrong automatic bookings (risk), as the thresholds change. The headline result.

## Reading order for the code

1. `models.py`: the data everything else passes around.
2. `parsing/`: XML and ZUGFeRD to `Invoice`, with evidence.
3. `rules/`: the checks and `engine.py`, which builds the decision.
4. `extraction/`: PDF text, OCR, LLM extraction and the quote check.
5. `synth/`: how test invoices and gold labels are made.
6. Later phases add `ml/`, `pipeline.py`, `evaluate.py`, `agent/`, `api/` and the UI.

## How to run

See the quick start in `README.md`. `make check` runs lint and the unit tests. Integration
tests need the services from `deploy/compose.yaml` (added in phase R0a).

## Sections added by later phases

Each phase appends a short section here: what was added, how to run it, what to look at.
The release checklist (`docs/RELEASE_CHECKLIST.md`) is linked here when A9 writes it.

### A6a UI design (S4)

`docs/ui/brief.md` describes who uses the UI, the three screens, the user flows and the stack
recommendation, and ends with the open points for your review. Open
`docs/ui/prototype/index.html` in a browser to click through it: inbox, invoice view (click a
field to see its evidence), checks, and the review queue with Approve, Correct and Reject. All
data in it is invented (`data.js`); all UI text is in `strings.js`, German and English.
