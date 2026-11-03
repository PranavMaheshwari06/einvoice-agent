from decimal import Decimal

import pytest

from conftest import xml_value
from einvoice.models import RuleContext
from einvoice.rules.ustg14 import (
    check_mandatory_fields,
    check_vat_id,
    check_vat_rates,
    is_valid_german_vat_id,
)


def failed(results) -> set[str]:
    return {result.code for result in results if not result.passed}


def test_complete_invoice_passes_every_requirement(mustang_invoice):
    results = check_mandatory_fields(mustang_invoice, RuleContext())
    assert len(results) == 10
    assert failed(results) == set()


def test_missing_vat_id_and_tax_number_fails(mustang_invoice):
    invoice = mustang_invoice.model_copy(update={"seller_vat_id": None})
    assert failed(check_mandatory_fields(invoice, RuleContext())) == {"MISSING_VAT_ID"}


def test_tax_number_instead_of_vat_id_is_enough(mustang_invoice):
    invoice = mustang_invoice.model_copy(
        update={"seller_vat_id": None, "seller_tax_number": xml_value("201/113/40209")}
    )
    assert failed(check_mandatory_fields(invoice, RuleContext())) == set()


def test_missing_delivery_date_fails_unless_a_period_is_given(mustang_invoice):
    no_date = mustang_invoice.model_copy(update={"delivery_date": None})
    assert failed(check_mandatory_fields(no_date, RuleContext())) == {"MISSING_DELIVERY_DATE"}
    with_period = no_date.model_copy(update={"period_start": mustang_invoice.issue_date})
    assert failed(check_mandatory_fields(with_period, RuleContext())) == set()


def test_line_without_quantity_fails(mustang_invoice):
    lines = [mustang_invoice.lines[0].model_copy(update={"quantity": None})]
    invoice = mustang_invoice.model_copy(update={"lines": lines})
    assert failed(check_mandatory_fields(invoice, RuleContext())) == {"MISSING_LINE_DETAILS"}


def test_small_amount_invoice_needs_fewer_fields(mustang_invoice):
    invoice = mustang_invoice.model_copy(
        update={
            "gross_total": xml_value(Decimal("119.00")),
            "buyer_name": None,
            "buyer_address": None,
            "number": None,
            "seller_vat_id": None,
            "delivery_date": None,
        }
    )
    results = check_mandatory_fields(invoice, RuleContext())
    assert failed(results) == set()
    assert "MISSING_SELLER_NAME" in {result.code for result in results}
    no_seller = invoice.model_copy(update={"seller_name": None})
    assert failed(check_mandatory_fields(no_seller, RuleContext())) == {"MISSING_SELLER_NAME"}


@pytest.mark.parametrize(
    ("gross_total", "expected_failures"),
    [
        (Decimal("250.00"), set()),
        (
            Decimal("250.01"),
            {
                "MISSING_BUYER_NAME",
                "MISSING_BUYER_ADDRESS",
                "MISSING_VAT_ID",
                "MISSING_INVOICE_NUMBER",
                "MISSING_DELIVERY_DATE",
            },
        ),
    ],
)
def test_small_amount_relief_ends_just_above_250_euro(
    mustang_invoice, gross_total, expected_failures
):
    """§33 UStDV: a total that 'nicht übersteigt' 250 EUR qualifies, one cent more does not."""
    invoice = mustang_invoice.model_copy(
        update={
            "gross_total": xml_value(gross_total),
            "buyer_name": None,
            "buyer_address": None,
            "number": None,
            "seller_vat_id": None,
            "delivery_date": None,
        }
    )
    assert failed(check_mandatory_fields(invoice, RuleContext())) == expected_failures


@pytest.mark.parametrize(
    ("vat_id", "valid"),
    [
        ("DE136695976", True),
        ("DE 136 695 976", True),
        ("de136695976", True),
        ("DE136695977", False),
        ("DE123456789", False),
        ("DE13669597", False),
        ("DE13669597X", False),
        ("ATU12345678", False),
    ],
)
def test_german_vat_id_check_digit(vat_id, valid):
    assert is_valid_german_vat_id(vat_id) is valid


def test_vat_id_check_flags_a_wrong_check_digit(mustang_invoice):
    invoice = mustang_invoice.model_copy(update={"seller_vat_id": xml_value("DE123456789")})
    assert failed(check_vat_id(invoice, RuleContext())) == {"INVALID_VAT_ID"}
    assert failed(check_vat_id(mustang_invoice, RuleContext())) == set()


def test_foreign_vat_id_is_noted_but_not_failed(mustang_invoice):
    invoice = mustang_invoice.model_copy(update={"seller_vat_id": xml_value("ATU12345678")})
    [result] = check_vat_id(invoice, RuleContext())
    assert result.passed and result.severity == "info"


def test_vat_rate_outside_section_12_fails(mustang_invoice):
    assert failed(check_vat_rates(mustang_invoice, RuleContext())) == set()
    wrong = mustang_invoice.vat_breakdown[1].model_copy(update={"rate": xml_value(Decimal("16"))})
    invoice = mustang_invoice.model_copy(
        update={"vat_breakdown": [mustang_invoice.vat_breakdown[0], wrong]}
    )
    assert failed(check_vat_rates(invoice, RuleContext())) == {"INVALID_VAT_RATE"}


def test_exempt_category_must_carry_zero_rate(mustang_invoice):
    exempt = mustang_invoice.vat_breakdown[0].model_copy(update={"category": xml_value("E")})
    invoice = mustang_invoice.model_copy(update={"vat_breakdown": [exempt]})
    assert failed(check_vat_rates(invoice, RuleContext())) == {"INVALID_VAT_RATE"}
    zero = exempt.model_copy(update={"rate": xml_value(Decimal("0"))})
    invoice = mustang_invoice.model_copy(update={"vat_breakdown": [zero]})
    assert failed(check_vat_rates(invoice, RuleContext())) == set()
