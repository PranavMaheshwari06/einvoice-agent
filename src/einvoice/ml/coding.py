"""GL-account models (SKR03 per invoice line), their calibration and the scores that judge them."""

from collections.abc import Callable, Sequence

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import FeatureUnion, Pipeline, make_pipeline
from sklearn.preprocessing import FunctionTransformer

from einvoice.models import Invoice

Encoder = Callable[[list[str]], np.ndarray]
E5_MODEL = "intfloat/multilingual-e5-small"
CALIBRATION_FOLDS = 5
ECE_BINS = 10


def line_text(item_name: str, seller_name: str) -> str:
    return f"{item_name} | {seller_name}"


class E5Encoder:
    """Loads the sentence-transformers model on first use and leaves it out of the pickle."""

    def __init__(self, model_name: str = E5_MODEL) -> None:
        self.model_name = model_name
        self._model = None

    def __call__(self, texts: list[str]) -> np.ndarray:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        # The e5 model card asks for the "query: " prefix when embeddings are used as features.
        prefixed = [f"query: {text}" for text in texts]
        return self._model.encode(prefixed, normalize_embeddings=True)

    def __getstate__(self) -> dict:
        return {"model_name": self.model_name, "_model": None}


def _encode_unique(texts: Sequence[str], encode: Encoder) -> np.ndarray:
    """Training lines repeat the same seller and item many times; encode each text once."""
    unique, inverse = np.unique(np.asarray(texts, dtype=str), return_inverse=True)
    return encode(unique.tolist())[inverse]


def tfidf_model() -> Pipeline:
    features = FeatureUnion(
        [
            ("words", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True)),
            ("chars", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True)),
        ]
    )
    return make_pipeline(features, LogisticRegression(max_iter=2000))


def embedding_model(encode: Encoder) -> Pipeline:
    encoder = FunctionTransformer(_encode_unique, kw_args={"encode": encode})
    return make_pipeline(encoder, LogisticRegression(max_iter=2000))


def calibrate(
    model: Pipeline, texts: list[str], accounts: list[str], sellers: list[str]
) -> CalibratedClassifierCV:
    """Isotonic calibration on seller-grouped folds, so each fold calibrates on unseen sellers."""
    folds = list(GroupKFold(CALIBRATION_FOLDS).split(texts, accounts, sellers))
    calibrated = CalibratedClassifierCV(model, method="isotonic", cv=folds)
    return calibrated.fit(texts, accounts)


def expected_calibration_error(confidence: np.ndarray, correct: np.ndarray) -> float:
    """Top-label ECE over equal-width bins: the weighted gap between confidence and accuracy."""
    bins = np.minimum((confidence * ECE_BINS).astype(int), ECE_BINS - 1)
    gaps = [
        abs(correct[bins == b].mean() - confidence[bins == b].mean()) * np.mean(bins == b)
        for b in np.unique(bins)
    ]
    return float(sum(gaps))


def coverage_at_precision(confidence: np.ndarray, correct: np.ndarray, precision: float) -> float:
    """Largest share of lines that a confidence threshold can accept with at least `precision`."""
    order = np.argsort(-confidence, kind="stable")
    ranked = confidence[order]
    counts = np.arange(1, len(ranked) + 1)
    reached = np.cumsum(correct[order]) / counts >= precision
    # A threshold cannot separate equal confidences, so only cut where the next one is lower.
    cut = np.append(ranked[1:] < ranked[:-1], True)
    accepted = counts[reached & cut]
    return float(accepted.max() / len(ranked)) if accepted.size else 0.0


def suggest_account(model, invoice: Invoice) -> tuple[str, float] | None:
    """Account and probability for the invoice's largest named line; None when no line is named."""
    named = [line for line in invoice.lines if line.item_name is not None]
    if not named or invoice.seller_name is None:
        return None
    largest = max(named, key=lambda line: line.net_amount.value if line.net_amount else 0)
    text = line_text(largest.item_name.value, invoice.seller_name.value)
    probabilities = model.predict_proba([text])[0]
    best = int(np.argmax(probabilities))
    return str(model.classes_[best]), float(probabilities[best])
