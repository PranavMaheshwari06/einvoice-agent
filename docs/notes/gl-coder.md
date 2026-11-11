# GL-account suggestion

What it does: suggests the SKR03 account for an invoice and a probability that gates AUTO_BOOK.
It is trained per invoice line on "item name | seller name" and applied to the invoice's
largest line, which is how the gold label is defined.

How it works: `ml/coding.py` builds two models: `tfidf_model()` (word 1-2 grams and char_wb
2-5 grams, logistic regression) as baseline, and `embedding_model(encode)` (e5 vectors,
logistic regression) with the encoder injected. There is no calibration step: the top
probability of the logistic regression is what the gate compares with `gl_threshold`.
`ml/train.py` reads the gold set (`split_lines` refuses a seller in two splits), fits both on
train, scores both on validation and test (`score`: macro-F1, accuracy, top-label ECE,
coverage at 98 % precision), picks the
champion on validation macro-F1 only (`pick_champion`), logs both runs to MLflow, registers
the champion as `gl-coder` with alias `champion`, and writes `reports/gl_coder.json`.
`suggest_account(model, invoice)` is what the pipeline calls.

Why this way: seller-grouped splits make every score a score on unseen sellers, the case a new
vendor brings; a random split would put the same seller and item in train and test and
overstate accuracy. The encoder is passed in because the e5 download is a network boundary;
`E5Encoder` caches vectors by text.
Models are saved with cloudpickle: skops, MLflow's default, refuses the injected encoder, and
the models only come from our own training run.
I rejected isotonic calibration (`CalibratedClassifierCV`, seller-grouped folds), which the
SPEC first prescribed. On seed 1 with the real e5 model it cut TF-IDF coverage at 98 % precision
from 0.43 to 0.05 on validation and made TF-IDF's ECE worse (0.07 to 0.17). Top-label isotonic
on out-of-fold scores had the best ECE (0.04) but only four score levels and 0.30 coverage.
These comparison numbers come from a throwaway script on the first run and are not in
`reports/`; only the raw-score figures are (`reports/gl_coder.json`). The gate threshold is chosen on validation with zero wrong bookings anyway, so what matters
is the ranking, and the raw scores rank best.

How it is tested: `tests/unit/ml/test_coding.py` checks ECE and coverage on hand-computed
cases, probabilities in [0, 1], the largest-line rule, the e5 "query: " prefix and
normalisation (taken from the model card), pickling without the model, and one encode per
text. `tests/unit/ml/test_train.py` trains both models on a small seeded
gold set with a hashing stub encoder against a temporary SQLite MLflow store and checks the
split, the champion rule, the report and that the registered champion loads and predicts. In
A4 live, `einvoice train` ran with the real e5 model against the Compose MLflow server, and
`einvoice eval` loaded the champion from it.

Limits: the score is a model score, not a calibrated probability. TF-IDF is overconfident on
unseen sellers (test ECE about 0.13), so "0.95" does not mean 95 % right. The past-account
feature is left out, since grouped test sellers never have history. Items that different
vendors book to different accounts cap accuracy for a new seller. Next I would use more
validation sellers and add corrections from reviewers as labels (A7 retrain).
