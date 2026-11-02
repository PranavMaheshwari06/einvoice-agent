"""Risk-coverage evaluation on the gold set: thresholds chosen on validation, reported on test."""

import json
import logging
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import matplotlib
import numpy as np

from einvoice.models import (
    STRUCTURED_FORMATS,
    Field,
    Invoice,
    PriorInvoice,
    PurchaseOrder,
    RuleContext,
    Vendor,
)
from einvoice.pipeline import Complete, Outcome, Suggest, Validate, decide, process
from einvoice.synth.generate import read_gold, read_master_data

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

logger = logging.getLogger(__name__)

EXTRACT_THRESHOLDS = (0.5, 0.7, 0.8, 0.9, 0.95, 0.99)
GL_THRESHOLDS = tuple(round(step / 100, 2) for step in range(101))
GL_REASON = "LOW_GL_CONFIDENCE"


@dataclass(frozen=True)
class Evaluated:
    record: dict
    outcome: Outcome


def _value(field: Field | None):
    return None if field is None else field.value


def booking_errors(invoice: Invoice, gl_account: str | None, record: dict) -> list[str]:
    """What makes an automatic booking wrong (SPEC section 2); empty means it was right."""
    stated = {
        "vendor": _value(invoice.seller_vat_id),
        "net": _value(invoice.tax_exclusive_total),
        "vat": _value(invoice.vat_total),
        "gross": _value(invoice.gross_total),
        "gl_account": gl_account,
        "due_date": _value(invoice.due_date),
    }
    gold = {
        "vendor": record["vendor_vat_id"],
        "net": Decimal(record["net_total"]),
        "vat": Decimal(record["vat_total"]),
        "gross": Decimal(record["gross_total"]),
        "gl_account": record["gl_account"],
        "due_date": date.fromisoformat(record["due_date"]),
    }
    errors = [name for name in gold if stated[name] != gold[name]]
    return errors + (["must_review"] if record["must_review"] else [])


def _prior(record: dict) -> PriorInvoice:
    return PriorInvoice(
        seller_vat_id=None if record["problem"] == "missing_vat_id" else record["vendor_vat_id"],
        seller_name=record["vendor_name"],
        number=record["number"],
        gross_total=Decimal(record["gross_total"]),
        issue_date=date.fromisoformat(record["issue_date"]),
    )


def _context_for(
    vendors: dict[str, Vendor], orders: dict[str, PurchaseOrder], prior: list[PriorInvoice]
):
    """Master data is looked up by what the invoice states, as it would be in production."""

    def context_for(invoice: Invoice) -> RuleContext:
        return RuleContext(
            vendor=vendors.get(_value(invoice.seller_vat_id)),
            purchase_order=orders.get(_value(invoice.po_number)),
            prior_invoices=prior,
        )

    return context_for


def _replay(replay_dir: Path, record: dict) -> Complete | None:
    path = replay_dir / f"{record['id']}.json"
    if not path.exists():
        return None
    response = json.dumps(json.loads(path.read_text(encoding="utf-8"))["content"])
    return lambda _prompt: response


def run_gold(
    directory: Path, validate: Validate, suggest: Suggest, replay_dir: Path
) -> tuple[dict[str, list[Evaluated]], dict[str, int]]:
    """Process validation and test invoices in issue order; every earlier invoice is a prior one."""
    gold = read_gold(directory)
    vendors, orders = read_master_data(directory)
    vendor_by_vat_id = {vendor.vat_id: vendor for vendor in vendors}
    order_by_number = {order.po_number: order for order in orders}
    evaluated: dict[str, list[Evaluated]] = {"validation": [], "test": []}
    skipped = {"validation": 0, "test": 0}
    prior: list[PriorInvoice] = []
    for record in gold:
        split = record["split"]
        if split in evaluated:
            complete = _replay(replay_dir, record)
            if record["format"] not in STRUCTURED_FORMATS and complete is None:
                skipped[split] += 1
            else:
                context_for = _context_for(vendor_by_vat_id, order_by_number, list(prior))
                content = (directory / record["file"]).read_bytes()
                outcome = process(content, context_for, validate, complete, suggest)
                evaluated[split].append(Evaluated(record, outcome))
        prior.append(_prior(record))
    return evaluated, skipped


def _gate_inputs(evaluated: list[Evaluated], extract_threshold: float):
    """Per invoice: blocked by anything but the GL gate, the GL probability, and whether wrong."""
    blocked, probability, wrong = [], [], []
    for item in evaluated:
        outcome = item.outcome
        context = replace(outcome.context, extract_threshold=extract_threshold)
        _, decision = decide(outcome.invoice, context, outcome.extraction_reasons)
        blocked.append(any(reason != GL_REASON for reason in decision.reasons))
        probability.append(-1.0 if context.gl_probability is None else context.gl_probability)
        wrong.append(bool(booking_errors(outcome.invoice, outcome.gl_account, item.record)))
    return np.array(blocked), np.array(probability), np.array(wrong)


def sweep(evaluated: list[Evaluated]) -> list[dict]:
    """Coverage and wrong auto-bookings for each threshold pair.

    The GL gate is the last check of `engine.run` (probability below threshold -> review), so
    the rules run once per extraction threshold and the GL threshold is applied here.
    """
    points = []
    for extract_threshold in EXTRACT_THRESHOLDS:
        blocked, probability, wrong = _gate_inputs(evaluated, extract_threshold)
        for gl_threshold in GL_THRESHOLDS:
            booked = ~blocked & (probability >= gl_threshold)
            points.append(
                {
                    "extract_threshold": extract_threshold,
                    "gl_threshold": gl_threshold,
                    "auto_booked": int(booked.sum()),
                    "wrong": int((booked & wrong).sum()),
                    "coverage": float(booked.mean()),
                }
            )
    return points


def operating_point(validation_points: list[dict]) -> dict | None:
    """Highest validation coverage with zero wrong bookings; ties go to the stricter thresholds."""
    safe = [point for point in validation_points if point["wrong"] == 0 and point["auto_booked"]]
    if not safe:
        return None
    return max(safe, key=lambda p: (p["coverage"], p["extract_threshold"], p["gl_threshold"]))


def _at(points: list[dict], chosen: dict) -> dict:
    return next(
        point
        for point in points
        if point["extract_threshold"] == chosen["extract_threshold"]
        and point["gl_threshold"] == chosen["gl_threshold"]
    )


def summarize(validation: list[Evaluated], test: list[Evaluated]) -> dict:
    validation_points = sweep(validation)
    test_points = sweep(test)
    chosen = operating_point(validation_points)
    result: dict = {"operating_point": chosen, "test": None, "worst_errors": []}
    if chosen is not None:
        at_test = _at(test_points, chosen)
        booked = at_test["auto_booked"]
        result["test"] = {
            **at_test,
            "invoices": len(test),
            "risk": at_test["wrong"] / booked if booked else None,
            # Rule of three: with zero errors in n, the 95% upper bound on the risk is 3/n.
            "risk_upper_95": 3 / booked if booked and at_test["wrong"] == 0 else None,
        }
        result["worst_errors"] = _wrong_bookings(test, chosen)
    curve_threshold = chosen["extract_threshold"] if chosen else EXTRACT_THRESHOLDS[0]
    result["test_curve"] = [
        {**point, "risk": point["wrong"] / point["auto_booked"]}
        for point in test_points
        if point["extract_threshold"] == curve_threshold and point["auto_booked"]
    ]
    return result


def _wrong_bookings(evaluated: list[Evaluated], chosen: dict) -> list[dict]:
    rows = []
    for item in evaluated:
        context = replace(
            item.outcome.context,
            extract_threshold=chosen["extract_threshold"],
            gl_threshold=chosen["gl_threshold"],
        )
        _, decision = decide(item.outcome.invoice, context, item.outcome.extraction_reasons)
        errors = booking_errors(item.outcome.invoice, item.outcome.gl_account, item.record)
        if decision.kind == "AUTO_BOOK" and errors:
            rows.append({"id": item.record["id"], "errors": errors})
    return rows


def plot(curve: list[dict], test_point: dict | None, path: Path) -> None:
    figure, axes = plt.subplots(figsize=(6, 4))
    axes.plot(
        [point["coverage"] for point in curve],
        [point["risk"] for point in curve],
        color="#2a6fb0",
        linewidth=2,
    )
    if test_point is not None and test_point["auto_booked"]:
        axes.plot(test_point["coverage"], test_point["risk"], "o", color="#2a6fb0", markersize=8)
        axes.annotate(
            f"thresholds chosen on validation (GL >= {test_point['gl_threshold']})",
            (test_point["coverage"], test_point["risk"]),
            xytext=(8, 8),
            textcoords="offset points",
            fontsize=9,
        )
    axes.set_xlabel("coverage (share booked automatically)")
    axes.set_ylabel("risk (wrong / booked automatically)")
    axes.set_title("Risk-coverage on the test split", fontsize=11)
    axes.grid(color="#dddddd", linewidth=0.5)
    axes.spines[["top", "right"]].set_visible(False)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def evaluate(
    directory: Path,
    validate: Validate,
    kosit: str,
    suggest: Suggest,
    encoder: str,
    replay_dir: Path,
    reports: Path,
) -> dict:
    """Write reports/metrics.json and reports/risk_coverage.png; `kosit` says how KoSIT ran."""
    evaluated, skipped = run_gold(directory, validate, suggest, replay_dir)
    metrics = {
        "kosit": kosit,
        "encoder": encoder,
        "thresholds_chosen_on": "validation",
        "reported_on": "test",
        "processed": {split: len(items) for split, items in evaluated.items()},
        "skipped_without_replay": skipped,
        **summarize(evaluated["validation"], evaluated["test"]),
    }
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "metrics.json").write_text(json.dumps(metrics, indent=1), encoding="utf-8")
    plot(metrics["test_curve"], metrics["test"], reports / "risk_coverage.png")
    logger.info("test result at the validation operating point: %s", metrics["test"])
    return metrics
