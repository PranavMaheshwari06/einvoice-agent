from decimal import Decimal

import pytest

from conftest import FIXTURES, xml_value
from einvoice.models import RuleContext
from einvoice.parsing.cii import parse_cii
from einvoice.parsing.ubl import parse_ubl
from einvoice.parsing.zugferd import parse_zugferd
from einvoice.rules.arithmetic import check_arithmetic

REAL_INVOICES = [
    *sorted(FIXTURES.glob("xrechnung/*.xml")),
    *sorted(FIXTURES.glob("corpus/*.xml")),
    *sorted(FIXTURES.glob("corpus/*.pdf")),
]


def parse(path):
    if path.suffix == ".pdf":
        return parse_zugferd(path.read_bytes())
    return (parse_ubl if "ubl" in path.name else parse_cii)(path.read_bytes())


def failed(invoice) -> set[str]:
    return {result.code for result in check_arithmetic(invoice, RuleContext()) if not result.passed}


@pytest.mark.parametrize("path", REAL_INVOICES, ids=lambda path: path.name)
def test_real_invoices_add_up(path):
    assert failed(parse(path)) == set()


@pytest.mark.parametrize("name", ["03.07a-INVOICE_ubl.xml", "03.07a-INVOICE_uncefact.xml"])
def test_line_allowances_and_charges_are_part_of_the_line_net(name):
    invoice = parse(FIXTURES / "xrechnung" / name)
    assert invoice.lines[0].allowances and invoice.lines[0].charges
    assert failed(invoice) == set()
    without_charges = invoice.lines[0].model_copy(update={"charges": []})
    invoice = invoice.model_copy(update={"lines": [without_charges, *invoice.lines[1:]]})
    assert "LINE_NET_MISMATCH" in failed(invoice)


def with_line(invoice, index, **changes):
    lines = list(invoice.lines)
    lines[index] = lines[index].model_copy(update=changes)
    return invoice.model_copy(update={"lines": lines})


def test_wrong_line_net_fails(mustang_invoice):
    invoice = with_line(mustang_invoice, 1, net_amount=xml_value(Decimal("326.00")))
    assert failed(invoice) == {"LINE_NET_MISMATCH", "LINE_SUM_MISMATCH"}


@pytest.mark.parametrize(("net", "passes"), [("316.01", True), ("316.02", False)])
def test_line_tolerance_is_one_cent(mustang_invoice, net, passes):
    invoice = with_line(mustang_invoice, 1, net_amount=xml_value(Decimal(net)))
    assert ("LINE_NET_MISMATCH" not in failed(invoice)) is passes


def test_price_base_quantity_divides_the_price(mustang_invoice):
    invoice = with_line(
        mustang_invoice,
        1,
        price=xml_value(Decimal("7.90")),
        price_base_quantity=xml_value(Decimal("10")),
    )
    assert failed(invoice) == set()


def test_vat_total_off_fails(mustang_invoice):
    invoice = mustang_invoice.model_copy(update={"vat_total": xml_value(Decimal("85.04"))})
    assert failed(invoice) == {"VAT_TOTAL_MISMATCH", "TOTALS_MISMATCH"}


def test_vat_amount_not_matching_rate_fails(mustang_invoice):
    seven_percent, nineteen_percent = mustang_invoice.vat_breakdown
    wrong = seven_percent.model_copy(update={"rate": xml_value(Decimal("19"))})
    invoice = mustang_invoice.model_copy(update={"vat_breakdown": [wrong, nineteen_percent]})
    assert failed(invoice) == {"VAT_RATE_MISMATCH"}


def test_missing_totals_fail(mustang_invoice):
    invoice = mustang_invoice.model_copy(update={"amount_due": None})
    assert failed(invoice) == {"TOTALS_MISMATCH"}
