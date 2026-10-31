import pytest

from conftest import FIXTURES
from einvoice.convert import invoice_to_cii
from einvoice.parsing.cii import parse_cii


def test_cii_invoice_survives_a_round_trip():
    original = parse_cii((FIXTURES / "corpus" / "EN16931_Einfach.cii.xml").read_bytes())
    again = parse_cii(invoice_to_cii(original))
    for name in ("number", "issue_date", "seller_name", "seller_vat_id", "gross_total"):
        assert getattr(again, name).value == getattr(original, name).value
    assert again.seller_address.value == original.seller_address.value

    def line_values(invoice):
        return [
            (line.item_name.value, line.quantity.value, line.net_amount.value)
            for line in invoice.lines
        ]

    assert line_values(again) == line_values(original)
    assert [part.tax_amount.value for part in again.vat_breakdown] == [
        part.tax_amount.value for part in original.vat_breakdown
    ]


def test_line_allowances_are_refused_instead_of_dropped():
    invoice = parse_cii((FIXTURES / "xrechnung" / "03.07a-INVOICE_uncefact.xml").read_bytes())
    with pytest.raises(ValueError, match="allowances"):
        invoice_to_cii(invoice)
