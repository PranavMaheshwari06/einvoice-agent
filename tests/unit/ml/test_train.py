import json

import numpy as np
import pytest

from conftest import stub_encode
from einvoice.ml.coding import line_text
from einvoice.ml.train import load_champion, pick_champion, split_lines, train
from einvoice.synth.generate import read_gold


@pytest.fixture(scope="module")
def trained(gold_dir, tmp_path_factory):
    work = tmp_path_factory.mktemp("train")
    uri = f"sqlite:///{work / 'mlflow.db'}"
    # MLflow puts artifacts under ./mlruns next to a SQLite store; keep them out of the repo.
    with pytest.MonkeyPatch.context() as patch:
        patch.chdir(work)
        report = train(gold_dir, stub_encode, "stub-hashing", uri, work / "reports")
        yield report, uri, work


def test_no_seller_is_in_two_splits(gold_dir):
    lines = split_lines(read_gold(gold_dir))
    sellers = {split: set(split_lines.sellers) for split, split_lines in lines.items()}
    assert set(sellers) == {"train", "validation", "test"}
    assert not sellers["train"] & sellers["validation"]
    assert not sellers["train"] & sellers["test"]
    assert not sellers["validation"] & sellers["test"]


def test_a_seller_in_two_splits_is_refused(gold_dir):
    gold = read_gold(gold_dir)
    leaked = {**gold[1], "vendor_vat_id": gold[0]["vendor_vat_id"]}
    leaked["split"] = next(s for s in ("train", "test") if s != gold[0]["split"])
    with pytest.raises(ValueError, match="is in"):
        split_lines([gold[0], leaked])


def test_champion_is_the_best_validation_macro_f1():
    scores = {"tfidf": {"macro_f1": 0.6}, "embeddings": {"macro_f1": 0.7}}
    assert pick_champion(scores) == "embeddings"


def test_both_models_are_scored_against_each_other(trained):
    report, _, _ = trained
    assert set(report["models"]) == {"tfidf", "embeddings"}
    validation = {name: scores["validation"] for name, scores in report["models"].items()}
    assert report["champion"] == pick_champion(validation)
    assert report["encoder"] == "stub-hashing"
    for scores in validation.values():
        assert 0 <= scores["ece"] <= 1
        assert 0 <= scores["coverage_at_98_precision"] <= 1


def test_report_is_written(trained):
    report, _, work = trained
    assert json.loads((work / "reports" / "gl_coder.json").read_text()) == report


def test_registered_champion_loads_and_predicts(trained):
    report, uri, _ = trained
    model, encoder = load_champion(uri)
    expected = "tfidf" if report["champion"] == "tfidf" else "stub-hashing"
    assert encoder == expected
    probabilities = model.predict_proba([line_text("Druckerpapier A4", "Neu GmbH")])
    assert np.all((probabilities >= 0) & (probabilities <= 1))
