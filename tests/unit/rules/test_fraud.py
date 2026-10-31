from dataclasses import replace

from conftest import xml_value
from einvoice.rules.fraud import check_vendor


def failed(invoice, context) -> set[str]:
    return {result.code for result in check_vendor(invoice, context) if not result.passed}


def test_known_vendor_with_same_iban_passes(ready_invoice, ready_context):
    # The master record stores the IBAN with spaces; the invoice without.
    assert failed(ready_invoice, ready_context) == set()


def test_unknown_vendor_fails(ready_invoice, ready_context):
    assert failed(ready_invoice, replace(ready_context, vendor=None)) == {"UNKNOWN_VENDOR"}


def test_changed_iban_fails_without_showing_the_full_iban(ready_invoice, ready_context):
    invoice = ready_invoice.model_copy(update={"iban": xml_value("DE02120300000000202051")})
    results = check_vendor(invoice, ready_context)
    [changed] = [result for result in results if result.code == "BANK_DETAILS_CHANGED"]
    assert not changed.passed
    assert "DE02120300000000202051" not in changed.message
    assert "2051" in changed.message


def test_invoice_without_iban_passes(ready_invoice, ready_context):
    invoice = ready_invoice.model_copy(update={"iban": None})
    assert failed(invoice, ready_context) == set()
