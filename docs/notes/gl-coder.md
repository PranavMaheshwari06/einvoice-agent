# GL-account suggestion

What it does: suggests the SKR03 account for an invoice and a probability that gates AUTO_BOOK.
It is trained per invoice line on "item name | seller name" and applied to the invoice's
largest line, which is how the gold label is defined.

How it works: `ml/coding.py` builds two models: `tfidf_model()` (word 1-2 grams and char_wb
2-5 grams, logistic regression) as baseline, and `embedding_model(encode)` (e5 vectors,
logistic regression) with the encoder injected. `calibrate()` wraps either in
`CalibratedClassifierCV(method="isotonic")` with `GroupKFold(5)` folds by seller.
`ml/train.py` reads the gold set (`split_lines` refuses a seller in two splits), fits both on
train, scores both on validation and test (`score`: macro-F1, accuracy, top-label ECE,
coverage at 98 % precision, plus the ECE of the uncalibrated model on validation), picks the
champion on validation macro-F1 only (`pick_champion`), logs both runs to MLflow, registers
the champion as `gl-coder` with alias `champion`, and writes `reports/gl_coder.json`.
`suggest_account(model, invoice)` is what the pipeline calls.

Why this way: seller-grouped folds and splits make every score a score on unseen sellers, the
case a new vendor brings; a random split would put the same seller and item in train and test
and overstate accuracy. The encoder is passed in because the e5 download is a network
boundary; `E5Encoder` caches vectors by text and is shared, not copied, by sklearn's `clone`,
so the five calibration folds do not encode the same text five times. Models are saved with
cloudpickle: skops, MLflow's default, refuses the calibrated wrapper and the encoder, and the
models only come from our own training run.

How it is tested: `tests/unit/ml/test_coding.py` checks ECE and coverage on hand-computed
cases, probabilities in [0, 1], the largest-line rule, the e5 "query: " prefix and
normalisation (taken from the model card), pickling without the model, and one encode per
text across fold copies. `tests/unit/ml/test_train.py` trains both models on a small seeded
gold set with a hashing stub encoder against a temporary SQLite MLflow store and checks the
split, the champion rule, the report and that the registered champion loads and predicts. The
real e5 model never ran here.

Limits: on seed 1 (stub encoder for the second model) isotonic calibration did not beat the
raw model on validation ECE and it lowered coverage at 98 % precision a lot, because
the isotonic steps put many lines on one plateau and validation holds only six sellers. The
past-account feature is left out, since grouped test sellers never have history. Next I would
compare top-label calibration on out-of-fold scores and use more validation sellers.
