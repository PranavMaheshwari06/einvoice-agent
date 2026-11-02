# End-to-end pipeline and outgoing XRechnung

What it does: `pipeline.process` turns the bytes of one invoice file into the canonical
`Invoice`, every check result and the AUTO_BOOK or REVIEW decision. `convert.to_xrechnung`
writes a checked invoice as XRechnung CII and returns KoSIT's verdict on it.

How it works: `process` detects the format, then either parses (`read_structured` gives the
invoice and the XML that KoSIT must see, the attachment for ZUGFeRD) and validates, or reads
the text layer or OCR and calls `extract_invoice`. It asks `suggest` for the GL account, puts
the validation result, the extraction reasons and the GL probability into the `RuleContext`
built by `context_for`, and calls `engine.run`. KoSIT (`validate`), the language model
(`complete`), the GL model (`suggest`) and the master data (`context_for`) are all passed in.
`engine.decide` turns stored check results into a decision without running the checks again;
`engine.run` and the evaluation both use it. The `convert <file> --out <xml>` command parses a
structured file, writes CII and exits 1 when KoSIT rejects it.

Why this way: the evaluation and the API call the same function, so what is measured is what
is served (SPEC 3.13). Passing the services in keeps the function free of settings and lets
tests replace them without patching. `process` takes bytes rather than a path because the API
receives uploads.

How it is tested: `tests/unit/test_pipeline.py` runs a ZUGFeRD file (KoSIT sees the embedded
CII), a UBL file that KoSIT rejects with no GL suggestion, the synthetic plain PDF with its
replay response, a planted wrong quote and an unsupported file. `test_convert.py` and
`test_cli.py` check that the written CII is what gets validated and that a reject fails the
command. The live KoSIT daemon was not called.

Limits: SPEC 3.11 names `convert <invoice_id>`; without stored invoices (A6b) the command
takes a file. `process` has no persistence; the API phase stores the outcome.
