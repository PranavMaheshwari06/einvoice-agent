"""Mandatory invoice content under §14 Abs. 4 UStG, the seller's USt-IdNr format and VAT rates."""

import re

from einvoice.models import Address, CheckResult, Field, Invoice, RuleContext
from einvoice.rules.legal import REDUCED_VAT_RATE, SMALL_AMOUNT_LIMIT, STANDARD_VAT_RATE

GERMAN_VAT_ID = re.compile(r"DE\d{9}")


def _address_complete(address: Field[Address] | None) -> bool:
    return address is not None and all(
        (address.value.street, address.value.postcode, address.value.city)
    )


def _vat_breakdown_complete(invoice: Invoice) -> bool:
    return bool(invoice.vat_breakdown) and all(
        None not in (part.taxable_amount, part.rate, part.tax_amount)
        for part in invoice.vat_breakdown
    )


def check_mandatory_fields(invoice: Invoice, context: RuleContext) -> list[CheckResult]:
    small = invoice.gross_total is not None and invoice.gross_total.value <= SMALL_AMOUNT_LIMIT
    has_rates = bool(invoice.vat_breakdown) and all(
        part.rate is not None for part in invoice.vat_breakdown
    )
    # (code, what §14 Abs. 4 asks for, present, also required for a §33 UStDV small invoice)
    requirements = [
        ("MISSING_SELLER_NAME", "Nr. 1 seller name", invoice.seller_name is not None, True),
        (
            "MISSING_SELLER_ADDRESS",
            "Nr. 1 seller address",
            _address_complete(invoice.seller_address),
            True,
        ),
        ("MISSING_BUYER_NAME", "Nr. 1 buyer name", invoice.buyer_name is not None, False),
        (
            "MISSING_BUYER_ADDRESS",
            "Nr. 1 buyer address",
            _address_complete(invoice.buyer_address),
            False,
        ),
        (
            "MISSING_VAT_ID",
            "Nr. 2 seller USt-IdNr or Steuernummer",
            invoice.seller_vat_id is not None or invoice.seller_tax_number is not None,
            False,
        ),
        ("MISSING_ISSUE_DATE", "Nr. 3 issue date", invoice.issue_date is not None, True),
        ("MISSING_INVOICE_NUMBER", "Nr. 4 invoice number", invoice.number is not None, False),
        (
            "MISSING_LINE_DETAILS",
            "Nr. 5 quantity and description of every line",
            bool(invoice.lines)
            and all(None not in (line.quantity, line.item_name) for line in invoice.lines),
            True,
        ),
        (
            "MISSING_DELIVERY_DATE",
            "Nr. 6 delivery date or period",
            invoice.delivery_date is not None or invoice.period_start is not None,
            False,
        ),
        (
            "MISSING_VAT_BREAKDOWN",
            "Nr. 7-8 net amount, rate and VAT amount per rate",
            has_rates if small else _vat_breakdown_complete(invoice),
            True,
        ),
    ]
    return [
        CheckResult(
            code=code,
            passed=present,
            message=f"§14 Abs. 4 {label}: {'present' if present else 'missing'}",
        )
        for code, label, present, needed_when_small in requirements
        if needed_when_small or not small
    ]


def compact_vat_id(vat_id: str) -> str:
    return vat_id.replace(" ", "").upper()


def is_valid_german_vat_id(vat_id: str) -> bool:
    """DE + 9 digits; the last digit is the ISO 7064 MOD 11,10 check digit of the first eight."""
    compact = compact_vat_id(vat_id)
    if not GERMAN_VAT_ID.fullmatch(compact):
        return False
    product = 10
    for digit in compact[2:10]:
        total = (int(digit) + product) % 10 or 10
        product = 2 * total % 11
    return (11 - product) % 10 == int(compact[10])


def check_vat_id(invoice: Invoice, context: RuleContext) -> list[CheckResult]:
    if invoice.seller_vat_id is None:
        return []
    vat_id = compact_vat_id(invoice.seller_vat_id.value)
    if not vat_id.startswith("DE"):
        return [
            CheckResult(
                code="INVALID_VAT_ID",
                passed=True,
                severity="info",
                message=f"{vat_id} is not a German USt-IdNr; its format is not checked",
            )
        ]
    valid = is_valid_german_vat_id(vat_id)
    outcome = "has a valid" if valid else "fails the"
    return [
        CheckResult(
            code="INVALID_VAT_ID",
            passed=valid,
            message=f"USt-IdNr {vat_id} {outcome} format and check digit",
        )
    ]


def check_vat_rates(invoice: Invoice, context: RuleContext) -> list[CheckResult]:
    """Category S must use a §12 UStG rate; every other category carries 0 %."""
    wrong = []
    for part in invoice.vat_breakdown:
        if part.category is None or part.rate is None:
            continue
        allowed = (STANDARD_VAT_RATE, REDUCED_VAT_RATE) if part.category.value == "S" else (0,)
        if part.rate.value not in allowed:
            wrong.append(f"{part.category.value} {part.rate.value}%")
    return [
        CheckResult(
            code="INVALID_VAT_RATE",
            passed=not wrong,
            message=f"rates not allowed: {', '.join(wrong)}" if wrong else "VAT rates allowed",
        )
    ]
