import json
from dataclasses import replace
from functools import partial

import pytest

from conftest import FIXTURES
from einvoice.evaluate import (
    EXTRACT_THRESHOLDS,
    booking_errors,
    evaluate,
    operating_point,
    rule_of_three,
    run_gold,
    summarize,
    sweep,
)
from einvoice.ml.coding import suggest_account
from einvoice.models import STRUCTURED_FORMATS, ValidationResult
from einvoice.pipeline import read_structured
from einvoice.rules import engine
from einvoice.synth.generate import read_gold

ACCEPT = ValidationResult(accepted=True, errors=[])


@pytest.fixture(scope="module")
def suggest(gl_model):
    return partial(suggest_account, gl_model)


@pytest.fixture(scope="module")
def evaluated(gold_dir, suggest, tmp_path_factory):
    replay_dir = tmp_path_factory.mktemp("no_replay")
    return run_gold(gold_dir, lambda _xml: ACCEPT, suggest, replay_dir)


def _structured(gold_dir, predicate):
    record = next(
        r for r in read_gold(gold_dir) if r["format"] in STRUCTURED_FORMATS and predicate(r)
    )
    content = (gold_dir / record["file"]).read_bytes()
    invoice, _ = read_structured(content, record["format"])
    return invoice, record


def test_a_correct_booking_has_no_errors(gold_dir):
    invoice, record = _structured(gold_dir, lambda r: not r["must_review"])
    assert booking_errors(invoice, record["gl_account"], record) == []


def test_wrong_account_and_must_review_count_as_wrong(gold_dir):
    invoice, record = _structured(gold_dir, lambda r: not r["must_review"])
    assert booking_errors(invoice, "0000", record) == ["gl_account"]
    invoice, record = _structured(gold_dir, lambda r: r["problem"] == "price_above_po")
    assert "must_review" in booking_errors(invoice, record["gl_account"], record)


def test_vat_sum_off_differs_from_gold_amounts(gold_dir):
    invoice, record = _structured(gold_dir, lambda r: r["problem"] == "vat_sum_off")
    errors = booking_errors(invoice, record["gl_account"], record)
    assert {"vat", "gross", "must_review"} <= set(errors)


def test_operating_point_is_the_highest_safe_coverage():
    points = [
        {
            "extract_threshold": 0.9,
            "gl_threshold": 0.5,
            "auto_booked": 8,
            "wrong": 1,
            "coverage": 0.8,
        },
        {
            "extract_threshold": 0.9,
            "gl_threshold": 0.7,
            "auto_booked": 6,
            "wrong": 0,
            "coverage": 0.6,
        },
        {
            "extract_threshold": 0.9,
            "gl_threshold": 0.8,
            "auto_booked": 6,
            "wrong": 0,
            "coverage": 0.6,
        },
        {
            "extract_threshold": 0.9,
            "gl_threshold": 0.9,
            "auto_booked": 2,
            "wrong": 0,
            "coverage": 0.2,
        },
    ]
    assert operating_point(points)["gl_threshold"] == 0.8
    assert operating_point(points[:1]) is None


def test_test_split_never_moves_the_operating_point(evaluated):
    by_split, _ = evaluated
    validation, test = by_split["validation"], by_split["test"]
    worse = [replace(item, errors=["gl_account"]) for item in test]
    assert (
        summarize(validation, test)["operating_point"]
        == summarize(validation, worse)["operating_point"]
    )


def test_sweep_on_stored_results_matches_a_full_rules_run(evaluated):
    validation = evaluated[0]["validation"]
    points = {(p["extract_threshold"], p["gl_threshold"]): p for p in sweep(validation)}
    for gl_threshold in (0.0, 0.5, 0.9):
        booked = 0
        for item in validation:
            context = replace(
                item.outcome.context,
                extract_threshold=EXTRACT_THRESHOLDS[0],
                gl_threshold=gl_threshold,
            )
            _, decision = engine.run(item.outcome.invoice, context)
            booked += decision.kind == "AUTO_BOOK"
        assert points[(EXTRACT_THRESHOLDS[0], gl_threshold)]["auto_booked"] == booked


def test_rules_send_every_must_review_invoice_to_review(evaluated):
    for items in evaluated[0].values():
        for item in items:
            if item.record["must_review"]:
                assert item.outcome.decision.kind == "REVIEW", item.record["id"]


def test_pdfs_and_scans_without_replay_are_skipped_and_counted(gold_dir, evaluated):
    by_split, skipped = evaluated
    gold = read_gold(gold_dir)
    for split in ("validation", "test"):
        records = [r for r in gold if r["split"] == split]
        unstructured = sum(r["format"] not in STRUCTURED_FORMATS for r in records)
        assert skipped[split] == unstructured
        assert len(by_split[split]) == len(records) - unstructured


def test_a_replay_response_lets_a_pdf_through(gold_dir, suggest, tmp_path):
    record = next(r for r in read_gold(gold_dir) if r["format"] == "pdf" and r["split"] == "test")
    replay = json.loads((FIXTURES / "replay" / "extract_synth_inv_00001.json").read_text())
    (tmp_path / f"{record['id']}.json").write_text(json.dumps(replay))
    by_split, skipped = run_gold(gold_dir, lambda _xml: ACCEPT, suggest, tmp_path)
    assert record["id"] in {item.record["id"] for item in by_split["test"]}


def test_evaluate_writes_metrics_and_plot(gold_dir, suggest, tmp_path):
    metrics = evaluate(
        gold_dir,
        lambda _xml: ACCEPT,
        "not called (test)",
        suggest,
        "tfidf",
        tmp_path / "no_replay",
        tmp_path / "reports",
    )
    written = json.loads((tmp_path / "reports" / "metrics.json").read_text())
    assert written == metrics
    assert (tmp_path / "reports" / "risk_coverage.png").stat().st_size > 0
    assert metrics["kosit"] == "not called (test)"
    assert metrics["encoder"] == "tfidf"
    assert metrics["thresholds_chosen_on"] == "validation"
    assert all(0 <= point["risk"] <= 1 for point in metrics["test_curve"])


def test_rule_of_three_bound(evaluated):
    validation, test = evaluated[0]["validation"], evaluated[0]["test"]
    result = summarize(validation, test)["test"]
    assert result["auto_booked"] > 0
    expected = 3 / result["auto_booked"] if result["wrong"] == 0 else None
    assert result["risk_upper_95"] == expected


def test_rule_of_three_is_capped_and_only_defined_without_errors():
    assert rule_of_three(300, 0) == pytest.approx(0.01)
    assert rule_of_three(2, 0) == 1.0
    assert rule_of_three(300, 1) is None
    assert rule_of_three(0, 0) is None


def test_a_spaced_vat_id_is_the_same_vendor(gold_dir):
    invoice, record = _structured(gold_dir, lambda r: not r["must_review"])
    spaced = invoice.seller_vat_id.value[:2] + " " + invoice.seller_vat_id.value[2:]
    invoice = invoice.model_copy(
        update={"seller_vat_id": invoice.seller_vat_id.model_copy(update={"value": spaced})}
    )
    assert booking_errors(invoice, record["gl_account"], record) == []


def test_a_split_without_processed_invoices_is_refused(gold_dir, suggest, tmp_path, monkeypatch):
    from einvoice import evaluate as module

    monkeypatch.setattr(
        module,
        "run_gold",
        lambda *_args: ({"validation": [], "test": []}, {"validation": 3, "test": 0}),
    )
    with pytest.raises(ValueError, match="no validation invoice could be processed"):
        evaluate(gold_dir, lambda _xml: ACCEPT, "x", suggest, "tfidf", tmp_path, tmp_path / "r")
