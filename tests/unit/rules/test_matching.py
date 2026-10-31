from dataclasses import replace
from decimal import Decimal

import pytest

from conftest import xml_value
from einvoice.rules.matching import check_po_match


def failed(invoice, context) -> set[str]:
    return {result.code for result in check_po_match(invoice, context) if not result.passed}


def with_po_line(context, index, **changes):
    order = context.purchase_order
    lines = list(order.lines)
    lines[index] = lines[index].model_copy(update=changes)
    return replace(context, purchase_order=order.model_copy(update={"lines": lines}))


def test_matching_po_and_receipts_pass(ready_invoice, ready_context):
    results = check_po_match(ready_invoice, ready_context)
    assert {result.code for result in results} == {
        "PO_LINE_NOT_FOUND",
        "PRICE_OUTSIDE_TOLERANCE",
        "QUANTITY_ABOVE_RECEIPT",
    }
    assert failed(ready_invoice, ready_context) == set()


def test_invoice_without_po_number_fails(mustang_invoice, ready_context):
    assert failed(mustang_invoice, ready_context) == {"NO_PO_REFERENCE"}


def test_unknown_po_fails(ready_invoice, ready_context):
    assert failed(ready_invoice, replace(ready_context, purchase_order=None)) == {"PO_NOT_FOUND"}


def test_po_of_another_vendor_fails(ready_invoice, ready_context):
    order = ready_context.purchase_order.model_copy(update={"vendor_vat_id": "DE811569869"})
    assert failed(ready_invoice, replace(ready_context, purchase_order=order)) == {"PO_NOT_FOUND"}


@pytest.mark.parametrize(
    ("po_price", "within"), [("0.78", True), ("0.77", False), ("0.80", True), ("0.81", False)]
)
def test_unit_price_may_deviate_two_percent(ready_invoice, ready_context, po_price, within):
    # The invoice says 0.79 per balloon.
    context = with_po_line(ready_context, 1, unit_price=Decimal(po_price))
    assert ("PRICE_OUTSIDE_TOLERANCE" not in failed(ready_invoice, context)) is within


def test_quantity_above_goods_receipt_fails(ready_invoice, ready_context):
    context = with_po_line(ready_context, 1, received_quantity=Decimal(399))
    assert failed(ready_invoice, context) == {"QUANTITY_ABOVE_RECEIPT"}


def test_without_goods_receipt_only_price_is_matched(ready_invoice, ready_context):
    context = with_po_line(ready_context, 1, received_quantity=None)
    assert failed(ready_invoice, context) == set()


def test_line_not_on_the_po_fails(ready_invoice, ready_context):
    context = with_po_line(ready_context, 2, description="Something else")
    assert failed(ready_invoice, context) == {"PO_LINE_NOT_FOUND"}


def test_po_line_reference_wins_over_the_name(ready_invoice, ready_context):
    line = ready_invoice.lines[1].model_copy(
        update={"po_line_ref": xml_value("B-2"), "item_name": xml_value("Luftballons bunt")}
    )
    invoice = ready_invoice.model_copy(update={"lines": [line]})
    context = with_po_line(ready_context, 1, line_id="B-2")
    assert failed(invoice, context) == set()
