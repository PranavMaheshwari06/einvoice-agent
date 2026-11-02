# Risk-coverage evaluation

What it does: `einvoice eval` runs the gold set's validation and test invoices through the
pipeline, chooses thresholds on validation and reports coverage, risk and the rule-of-three
bound on test, in `reports/metrics.json` and `reports/risk_coverage.png`.

How it works: `run_gold` walks the gold set in issue order; every earlier invoice of any split
is a prior invoice for the duplicate check, and master data is looked up by what the invoice
states. PDFs and scans without a replay file `<dir>/replay/<id>.json` are skipped and counted.
`booking_errors` lists what would make an automatic booking wrong (SPEC section 2: vendor,
net, VAT, gross, GL account, due date, or a must-review invoice). `sweep` decides every
invoice with `engine.decide` for each pair of extraction and GL thresholds. `operating_point`
takes the highest validation coverage with zero wrong bookings, ties to the stricter
thresholds; `summarize` applies it to test, lists the wrong bookings and keeps the test curve.
`rule_of_three` gives 3/n, capped at 1, only when no booking was wrong.

Why this way: thresholds picked on test would report the best case of the test set itself, so
test is used only for reporting. `--fixtures` replaces KoSIT by "accepted" and says so in
`metrics.json`, which also records the encoder of the champion; a stubbed run cannot be
mistaken for a live one.

How it is tested: `tests/unit/test_evaluate.py` checks the wrong-booking definition on real
generated files, that changing test outcomes does not move the operating point, that the
sweep on stored results matches a full rules run, that the rules send every must-review
invoice to review, skipped counting, the replay path, the rule-of-three cap, a spaced VAT id
and the written files. The CLI test runs `eval --fixtures` with a patched champion.

Limits: on seed 1 in fixtures mode with a TF-IDF champion, every wrong booking at low
thresholds was a GL account; the rules caught every must-review invoice. Coverage at zero
wrong is therefore set by the GL probability, and it was low. Until A5 records replay
responses, PDFs and scans are not in the result.
