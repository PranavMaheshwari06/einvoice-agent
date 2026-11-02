"""Risk-coverage evaluation on the gold set: thresholds chosen on validation, reported on test."""

import json
import logging
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from functools import partial
from pathlib import Path

import matplotlib

from einvoice.models import (
    STRUCTURED_FORMATS,
    Invoice,
    PriorInvoice,
    PurchaseOrder,
    RuleContext,
    Vendor,
    value_of,
)
from einvoice.pipeline import Complete, Outcome, Suggest, Validate, process
from einvoice.rules import engine
from einvoice.rules.ustg14 import compact_vat_id
from einvoice.synth.generate import prior_invoice, read_gold, read_master_data

logger = logging.getLogger(__name__)

EXTRACT_THRESHOLDS = (0.5, 0.7, 0.8, 0.9, 0.95, 0.99)
GL_THRESHOLDS = tuple(round(step / 100, 2) for step in range(101))


@dataclass(frozen=True)
class Evaluated:
    record: dict
    outcome: Outcome
    errors: list[str]


def _vat_id(invoice: Invoice) -> str | None:
    """Extracted ids may carry spaces ("DE 123 456 789"); master data and gold hold them compact."""
    return None if invoice.seller_vat_id is None else compact_vat_id(invoice.seller_vat_id.value)


def booking_errors(invoice: Invoice, gl_account: str | None, record: dict) -> list[str]:
    """What makes an automatic booking wrong (SPEC section 2); empty means it was right."""
    stated = {
        "vendor": _vat_id(invoice),
        "net": value_of(invoice.tax_exclusive_total),
        "vat": value_of(invoice.vat_total),
        "gross": value_of(invoice.gross_total),
        "gl_account": gl_account,
        "due_date": value_of(invoice.due_date),
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


def _context(
    vendors: dict[str, Vendor],
    orders: dict[str, PurchaseOrder],
    prior: list[PriorInvoice],
    invoice: Invoice,
) -> RuleContext:
    """Master data is looked up by what the invoice states, as it would be in production."""
    return RuleContext(
        vendor=vendors.get(_vat_id(invoice)),
        purchase_order=orders.get(value_of(invoice.po_number)),
        prior_invoices=prior,
    )


def _replay(replay_dir: Path, record: dict) -> Complete | None:
    path = replay_dir / f"{record['id']}.json"
    if not path.exists():
        return None
    response = json.dumps(json.loads(path.read_text(encoding="utf-8"))["content"])
    return lambda _prompt: response


def _no_model(_prompt: str) -> str:
    raise RuntimeError("structured input never reaches the language model")


def run_gold(
    directory: Path, validate: Validate, suggest: Suggest, replay_dir: Path
) -> tuple[dict[str, list[Evaluated]], dict[str, int]]:
    """Process validation and test invoices in issue order; every earlier invoice is a prior one."""
    vendors, orders = read_master_data(directory)
    vendor_by_vat_id = {vendor.vat_id: vendor for vendor in vendors}
    order_by_number = {order.po_number: order for order in orders}
    evaluated: dict[str, list[Evaluated]] = {"validation": [], "test": []}
    skipped = {"validation": 0, "test": 0}
    prior: list[PriorInvoice] = []
    for record in read_gold(directory):
        split = record["split"]
        complete = _replay(replay_dir, record)
        structured = record["format"] in STRUCTURED_FORMATS
        if split in evaluated and not structured and complete is None:
            skipped[split] += 1
        elif split in evaluated:
            context_for = partial(_context, vendor_by_vat_id, order_by_number, list(prior))
            content = (directory / record["file"]).read_bytes()
            outcome = process(content, context_for, validate, complete or _no_model, suggest)
            errors = booking_errors(outcome.invoice, outcome.gl_account, record)
            evaluated[split].append(Evaluated(record, outcome, errors))
        prior.append(prior_invoice(record))
    return evaluated, skipped


def _books(item: Evaluated, extract_threshold: float, gl_threshold: float) -> bool:
    context = replace(
        item.outcome.context, extract_threshold=extract_threshold, gl_threshold=gl_threshold
    )
    decision = engine.decide(item.outcome.invoice, context, item.outcome.results)
    return decision.kind == "AUTO_BOOK"


def sweep(evaluated: list[Evaluated]) -> list[dict]:
    """Coverage and wrong auto-bookings for each threshold pair, decided by the rules engine."""
    points = []
    for extract_threshold in EXTRACT_THRESHOLDS:
        for gl_threshold in GL_THRESHOLDS:
            booked = [item for item in evaluated if _books(item, extract_threshold, gl_threshold)]
            points.append(
                {
                    "extract_threshold": extract_threshold,
                    "gl_threshold": gl_threshold,
                    "auto_booked": len(booked),
                    "wrong": sum(bool(item.errors) for item in booked),
                    "coverage": len(booked) / len(evaluated),
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


def rule_of_three(booked: int, wrong: int) -> float | None:
    """95% upper bound on the risk after zero errors in `booked` (3/n, at most 1); else None."""
    if booked == 0 or wrong > 0:
        return None
    return min(1.0, 3 / booked)


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
            "risk_upper_95": rule_of_three(booked, at_test["wrong"]),
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
    thresholds = (chosen["extract_threshold"], chosen["gl_threshold"])
    return [
        {"id": item.record["id"], "errors": item.errors}
        for item in evaluated
        if item.errors and _books(item, *thresholds)
    ]


def plot(curve: list[dict], test_point: dict | None, path: Path) -> None:
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

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
    for split, items in evaluated.items():
        if not items:
            raise ValueError(f"no {split} invoice could be processed (skipped: {skipped[split]})")
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
