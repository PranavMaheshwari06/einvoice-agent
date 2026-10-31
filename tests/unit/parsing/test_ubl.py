from datetime import date
from decimal import Decimal

import pytest

from conftest import FIXTURES
from einvoice.parsing.ubl import parse_ubl

UBL_FIXTURES = sorted(FIXTURES.glob("xrechnung/*_ubl.xml")) + sorted(
    FIXTURES.glob("corpus/*ubl*.xml")
)


@pytest.mark.parametrize("path", UBL_FIXTURES, ids=lambda path: path.name)
def test_reads_every_ubl_fixture(path):
    invoice = parse_ubl(path.read_bytes())
    assert invoice.format == "ubl"
    assert invoice.number and invoice.issue_date and invoice.gross_total
    assert invoice.lines and all(line.net_amount and line.item_name for line in invoice.lines)
    assert invoice.vat_breakdown


def test_reads_header_lines_and_evidence_of_01_01a():
    invoice = parse_ubl((FIXTURES / "xrechnung" / "01.01a-INVOICE_ubl.xml").read_bytes())
    assert invoice.number.value == "123456XX"
    assert invoice.number.evidence.bt == "BT-1"
    assert invoice.number.evidence.xpath == "/ubl:Invoice/cbc:ID"
    assert invoice.issue_date.value == date(2016, 4, 4)
    assert invoice.buyer_reference.value == "04011000-12345-03"
    assert invoice.seller_vat_id.value == "DE 123456789"
    assert invoice.iban.value == "DE79000000001234567890"
    assert invoice.seller_address.value.postcode == "12345"
    assert (invoice.tax_exclusive_total.value, invoice.vat_total.value) == (
        Decimal("314.86"),
        Decimal("22.04"),
    )
    first = invoice.lines[0]
    assert (first.quantity.value, first.unit.value, first.price.value) == (
        Decimal(1),
        "XPP",
        Decimal("288.79"),
    )
    assert first.po_line_ref.value == "6171175.1"
    assert first.vat_rate.value == Decimal(7)


def test_vat_total_is_the_one_in_document_currency():
    # 02.01a has a second TaxTotal in GBP (BT-111) after the EUR one with subtotals.
    invoice = parse_ubl((FIXTURES / "xrechnung" / "02.01a-INVOICE_ubl.xml").read_bytes())
    assert invoice.vat_total.evidence.xpath.startswith("/ubl:Invoice/cac:TaxTotal[1]/")
    assert invoice.seller_tax_number.value == "123/456/789"
    assert invoice.delivery_date.value == date(2018, 4, 13)
    assert invoice.po_number.value == "65002278"


def test_reads_credit_note():
    invoice = parse_ubl((FIXTURES / "corpus" / "ubl-tc434-creditnote1.xml").read_bytes())
    assert invoice.type_code.value == "381"
    assert invoice.lines[0].quantity.evidence.xpath.endswith("cbc:CreditedQuantity")


def test_rejects_cii_input():
    with pytest.raises(ValueError, match="not a UBL invoice"):
        parse_ubl((FIXTURES / "xrechnung" / "01.01a-INVOICE_uncefact.xml").read_bytes())
