"""GL-account models (SKR03 per invoice line) and the scores that judge them."""

from collections.abc import Callable, Sequence

import numpy as np
from sklearn.base import ClassifierMixin
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline, make_pipeline
from sklearn.preprocessing import FunctionTransformer

from einvoice.models import Invoice

Encoder = Callable[[list[str]], np.ndarray]
E5_MODEL = "intfloat/multilingual-e5-small"
ECE_BINS = 10


def line_text(item_name: str, seller_name: str) -> str:
    return f"{item_name} | {seller_name}"


class E5Encoder:
    """Loads the sentence-transformers model on first use; the model and cache stay out of pickles.

    Training, scoring and every invoice repeat the same item and seller, so vectors are
    cached by text.
    """

    def __init__(self, prefix: str = "query: ") -> None:
        # e5 expects "query: " for features and search queries, "passage: " for indexed texts.
        self._prefix = prefix
        self._model = None
        self._cache: dict[str, np.ndarray] = {}

    def __call__(self, texts: list[str]) -> np.ndarray:
        missing = [text for text in dict.fromkeys(texts) if text not in self._cache]
        if missing:
            if self._model is None:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(E5_MODEL)
            prefixed = [f"{self._prefix}{text}" for text in missing]
            vectors = self._model.encode(prefixed, normalize_embeddings=True)
            self._cache.update(zip(missing, vectors, strict=True))
        return np.stack([self._cache[text] for text in texts])

    def __getstate__(self) -> dict:
        return {"_prefix": self._prefix, "_model": None, "_cache": {}}


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


def suggest_account(model: ClassifierMixin, invoice: Invoice) -> tuple[str, float] | None:
    """Account and probability for the invoice's largest named line; None when no line is named."""
    named = [line for line in invoice.lines if line.item_name is not None]
    if not named or invoice.seller_name is None:
        return None
    largest = max(named, key=lambda line: line.net_amount.value if line.net_amount else 0)
    text = line_text(largest.item_name.value, invoice.seller_name.value)
    probabilities = model.predict_proba([text])[0]
    best = int(np.argmax(probabilities))
    return str(model.classes_[best]), float(probabilities[best])
