from datetime import date
from decimal import Decimal

import pytest

from conftest import FIXTURES
from einvoice.models import Field, Invoice
from einvoice.parsing.cii import parse_cii
from einvoice.parsing.ubl import parse_ubl

CII_FIXTURES = sorted(FIXTURES.glob("xrechnung/*_uncefact.xml")) + sorted(
    FIXTURES.glob("corpus/*.cii.xml")
)


def values(invoice: Invoice) -> dict:
    """Field values without evidence, to compare the same invoice read from two syntaxes."""
    header = {name: field.value for name, field in invoice if isinstance(field, Field)}
    lines = [
        {name: field.value for name, field in line if isinstance(field, Field)}
        for line in invoice.lines
    ]
    return {"header": header, "lines": lines}


@pytest.mark.parametrize("path", CII_FIXTURES, ids=lambda path: path.name)
def test_reads_every_cii_fixture(path):
    invoice = parse_cii(path.read_bytes())
    assert invoice.format == "cii"
    assert invoice.number and invoice.issue_date and invoice.gross_total
    assert invoice.lines and all(line.net_amount and line.item_name for line in invoice.lines)
    assert invoice.vat_breakdown


@pytest.mark.parametrize("case", ["01.01a", "01.14a", "02.01a"])
def test_cii_and_ubl_of_the_same_testsuite_case_agree(case):
    ubl = parse_ubl((FIXTURES / "xrechnung" / f"{case}-INVOICE_ubl.xml").read_bytes())
    cii = parse_cii((FIXTURES / "xrechnung" / f"{case}-INVOICE_uncefact.xml").read_bytes())
    # The 02.01a CII file states RoundingAmount 0; its UBL twin leaves it out.
    cii = cii.model_copy(update={"rounding_amount": None})
    assert values(cii) == values(ubl)


def test_reads_dates_po_and_document_allowances_of_rabatte():
    invoice = parse_cii((FIXTURES / "corpus" / "EN16931_Rabatte.cii.xml").read_bytes())
    assert invoice.po_number.value == "2013-471331"
    assert invoice.delivery_date.value == date(2018, 6, 3)
    assert invoice.issue_date.evidence.xpath.endswith("ram:IssueDateTime/udt:DateTimeString")
    assert invoice.allowance_total.value > 0
    assert invoice.seller_tax_number.value == "201/113/40209"
    assert invoice.vat_total.value == Decimal("21.30")


def test_reads_line_allowances_and_charges():
    invoice = parse_cii((FIXTURES / "xrechnung" / "03.07a-INVOICE_uncefact.xml").read_bytes())
    first = invoice.lines[0]
    assert [field.evidence.bt for field in first.allowances] == ["BT-136", "BT-136"]
    assert [field.evidence.bt for field in first.charges] == ["BT-141", "BT-141"]


def test_rejects_ubl_input():
    with pytest.raises(ValueError, match="not a CII invoice"):
        parse_cii((FIXTURES / "xrechnung" / "01.01a-INVOICE_ubl.xml").read_bytes())
