from datetime import timedelta
from decimal import Decimal

import pytest

from einvoice.models import PriorInvoice, RuleContext
from einvoice.rules.duplicates import check_duplicates


def prior_like(invoice, **changes) -> PriorInvoice:
    values = {
        "seller_vat_id": invoice.seller_vat_id.value,
        "seller_name": invoice.seller_name.value,
        "number": invoice.number.value,
        "gross_total": invoice.gross_total.value,
        "issue_date": invoice.issue_date.value,
    }
    return PriorInvoice(**(values | changes))


def passed(invoice, prior_invoices) -> bool:
    [result] = check_duplicates(invoice, RuleContext(prior_invoices=prior_invoices))
    assert result.code == "DUPLICATE_INVOICE"
    return result.passed


def test_no_earlier_invoices_passes(mustang_invoice):
    assert passed(mustang_invoice, [])


def test_same_vat_id_and_number_is_a_duplicate(mustang_invoice):
    prior = prior_like(mustang_invoice, gross_total=Decimal("1.00"), seller_vat_id="DE 136695976")
    assert not passed(mustang_invoice, [prior])


def test_same_number_from_another_seller_is_not_a_duplicate(mustang_invoice):
    prior = prior_like(mustang_invoice, seller_vat_id="DE811569869", seller_name="Andere GmbH")
    assert passed(mustang_invoice, [prior])


@pytest.mark.parametrize(("days", "duplicate"), [(0, True), (7, True), (8, False)])
def test_same_seller_and_gross_within_seven_days(mustang_invoice, days, duplicate):
    prior = prior_like(
        mustang_invoice,
        seller_vat_id=None,
        seller_name="BEI SPIEL GMBH",
        number="RE-OTHER",
        issue_date=mustang_invoice.issue_date.value - timedelta(days=days),
    )
    assert passed(mustang_invoice, [prior]) is not duplicate


def test_same_seller_different_gross_is_not_a_duplicate(mustang_invoice):
    prior = prior_like(mustang_invoice, number="RE-OTHER", gross_total=Decimal("571.05"))
    assert passed(mustang_invoice, [prior])
