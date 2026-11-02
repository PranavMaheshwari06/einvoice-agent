import pickle

import numpy as np
import pytest

from conftest import stub_encode, xml_value
from einvoice.ml.coding import (
    E5Encoder,
    calibrate,
    coverage_at_precision,
    embedding_model,
    expected_calibration_error,
    line_text,
    suggest_account,
    tfidf_model,
)
from einvoice.models import Invoice, LineItem

TEXTS = [
    line_text(item, seller)
    for seller in ("Alpha GmbH", "Beta AG", "Gamma KG", "Delta OHG", "Epsilon eG", "Zeta UG")
    for item in ("Druckerpapier A4", "Toner schwarz", "Bürostuhl", "Webhosting")
]
ACCOUNTS = ["4930", "4930", "0650", "4980"] * 6
SELLERS = [text.split(" | ")[1] for text in TEXTS]


def test_ece_is_zero_when_confidence_matches_accuracy():
    confidence = np.array([0.75] * 4)
    correct = np.array([True, True, True, False])
    assert expected_calibration_error(confidence, correct) == pytest.approx(0.0)


def test_ece_is_the_gap_for_an_overconfident_model():
    confidence = np.array([0.95, 0.95])
    correct = np.array([True, False])
    assert expected_calibration_error(confidence, correct) == pytest.approx(0.45)


def test_coverage_stops_before_the_first_error_that_breaks_precision():
    confidence = np.array([0.99, 0.95, 0.9, 0.8])
    correct = np.array([True, True, False, True])
    assert coverage_at_precision(confidence, correct, 0.98) == 0.5


def test_coverage_cannot_split_equal_confidences():
    confidence = np.array([0.9, 0.9, 0.9])
    correct = np.array([True, True, False])
    assert coverage_at_precision(confidence, correct, 0.98) == 0.0


@pytest.mark.parametrize("model", [tfidf_model(), embedding_model(stub_encode)])
def test_calibrated_models_return_probabilities(model):
    calibrated = calibrate(model, TEXTS, ACCOUNTS, SELLERS)
    probabilities = calibrated.predict_proba([line_text("Toner schwarz", "Neu GmbH")])
    assert np.all((probabilities >= 0) & (probabilities <= 1))
    assert probabilities.sum() == pytest.approx(1.0)


def test_suggestion_uses_the_largest_line():
    calibrated = calibrate(tfidf_model(), TEXTS, ACCOUNTS, SELLERS)
    invoice = Invoice(
        format="ubl",
        seller_name=xml_value("Neu GmbH"),
        lines=[
            LineItem(item_name=xml_value("Toner schwarz"), net_amount=xml_value(10)),
            LineItem(item_name=xml_value("Bürostuhl"), net_amount=xml_value(400)),
        ],
    )
    account, probability = suggest_account(calibrated, invoice)
    assert account == "0650"
    assert 0 <= probability <= 1


def test_no_suggestion_without_a_named_line():
    calibrated = calibrate(tfidf_model(), TEXTS, ACCOUNTS, SELLERS)
    invoice = Invoice(format="pdf", seller_name=xml_value("Neu GmbH"), lines=[LineItem()])
    assert suggest_account(calibrated, invoice) is None


class RecordingModel:
    def __init__(self):
        self.calls = []

    def encode(self, texts, normalize_embeddings):
        self.calls.append((texts, normalize_embeddings))
        return np.ones((len(texts), 3))


def test_e5_encoder_prefixes_query_and_normalizes():
    encoder = E5Encoder()
    encoder._model = RecordingModel()
    encoder(["Toner | Alpha GmbH"])
    assert encoder._model.calls == [(["query: Toner | Alpha GmbH"], True)]


def test_e5_encoder_pickles_without_the_loaded_model():
    encoder = E5Encoder()
    encoder._model = RecordingModel()
    restored = pickle.loads(pickle.dumps(encoder))
    assert restored._model is None
    assert restored.model_name == encoder.model_name
