"""Fits both GL-account models on train, picks the champion on validation, registers it."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import mlflow
import numpy as np
from sklearn.base import ClassifierMixin, clone
from sklearn.metrics import accuracy_score, f1_score

from einvoice.ml.coding import (
    CALIBRATION_FOLDS,
    Encoder,
    calibrate,
    coverage_at_precision,
    embedding_model,
    expected_calibration_error,
    line_text,
    tfidf_model,
)
from einvoice.synth.generate import read_gold

logger = logging.getLogger(__name__)

MODEL_NAME = "gl-coder"
CHAMPION_ALIAS = "champion"
TARGET_PRECISION = 0.98


@dataclass(frozen=True)
class Lines:
    texts: list[str]
    accounts: list[str]
    sellers: list[str]


def split_lines(gold: list[dict]) -> dict[str, Lines]:
    """Invoice lines per split; raises if a seller appears in two splits (that would leak)."""
    split_of_seller: dict[str, str] = {}
    rows: dict[str, list[tuple[str, str, str]]] = {}
    for record in gold:
        seller, split = record["vendor_vat_id"], record["split"]
        if split_of_seller.setdefault(seller, split) != split:
            raise ValueError(f"seller {seller} is in {split_of_seller[seller]} and {split}")
        for line in record["lines"]:
            text = line_text(line["item_name"], record["vendor_name"])
            rows.setdefault(split, []).append((text, line["gl_account"], seller))
    return {
        split: Lines(*map(list, zip(*split_rows, strict=True)))
        for split, split_rows in rows.items()
    }


def score(model: ClassifierMixin, lines: Lines) -> dict[str, float]:
    probabilities = model.predict_proba(lines.texts)
    if not np.all((probabilities >= 0) & (probabilities <= 1)):
        raise ValueError("model returned probabilities outside [0, 1]")
    predicted = model.classes_[probabilities.argmax(axis=1)]
    confidence = probabilities.max(axis=1)
    correct = predicted == np.asarray(lines.accounts)
    return {
        "macro_f1": float(f1_score(lines.accounts, predicted, average="macro", zero_division=0)),
        "accuracy": float(accuracy_score(lines.accounts, predicted)),
        "ece": expected_calibration_error(confidence, correct),
        "coverage_at_98_precision": coverage_at_precision(confidence, correct, TARGET_PRECISION),
    }


def pick_champion(validation_scores: dict[str, dict[str, float]]) -> str:
    """The champion is chosen on validation macro-F1 only; the test split never enters."""
    return max(validation_scores, key=lambda name: validation_scores[name]["macro_f1"])


def _fit(name: str, model, train: Lines, validation: Lines, test: Lines) -> dict:
    calibrated = calibrate(model, train.texts, train.accounts, train.sellers)
    raw = clone(model).fit(train.texts, train.accounts)
    scores = {"validation": score(calibrated, validation), "test": score(calibrated, test)}
    scores["validation"]["ece_uncalibrated"] = score(raw, validation)["ece"]
    logger.info("%s: validation %s", name, scores["validation"])
    return {"model": calibrated, "scores": scores}


def train(
    directory: Path, encode: Encoder, encoder_name: str, tracking_uri: str, reports: Path
) -> dict:
    """Fit both models, log them to MLflow, register the champion, write reports/gl_coder.json."""
    lines = split_lines(read_gold(directory))
    train_lines, validation, test = lines["train"], lines["validation"], lines["test"]
    candidates = {"tfidf": tfidf_model(), "embeddings": embedding_model(encode)}
    fitted = {
        name: _fit(name, model, train_lines, validation, test) for name, model in candidates.items()
    }
    champion = pick_champion(
        {name: result["scores"]["validation"] for name, result in fitted.items()}
    )

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(MODEL_NAME)
    for name, result in fitted.items():
        with mlflow.start_run(run_name=name):
            mlflow.log_params(
                {
                    "model": name,
                    "encoder": encoder_name if name == "embeddings" else "tfidf",
                    "calibration": f"isotonic, GroupKFold({CALIBRATION_FOLDS}) by seller",
                    "train_lines": len(train_lines.texts),
                }
            )
            for split, split_scores in result["scores"].items():
                mlflow.log_metrics({f"{split}_{key}": value for key, value in split_scores.items()})
            # skops (the default) refuses the calibrated wrapper and the injected encoder.
            info = mlflow.sklearn.log_model(
                result["model"], name="model", serialization_format="cloudpickle"
            )
            if name == champion:
                version = mlflow.register_model(info.model_uri, MODEL_NAME).version
                mlflow.MlflowClient().set_registered_model_alias(
                    MODEL_NAME, CHAMPION_ALIAS, version
                )

    report = {
        "encoder": encoder_name,
        "champion": champion,
        "chosen_on": "validation macro_f1",
        "lines": {split: len(split_lines.texts) for split, split_lines in lines.items()},
        "models": {name: result["scores"] for name, result in fitted.items()},
    }
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "gl_coder.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report


def load_champion(tracking_uri: str) -> tuple[ClassifierMixin, str]:
    """The registered champion and the encoder it was trained with."""
    mlflow.set_tracking_uri(tracking_uri)
    client = mlflow.MlflowClient()
    version = client.get_model_version_by_alias(MODEL_NAME, CHAMPION_ALIAS)
    encoder = client.get_run(version.run_id).data.params["encoder"]
    return mlflow.sklearn.load_model(f"models:/{MODEL_NAME}@{CHAMPION_ALIAS}"), encoder
