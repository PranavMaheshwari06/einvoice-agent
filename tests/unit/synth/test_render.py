import random
from io import BytesIO

import pdfplumber
import pytest

from einvoice.parsing.cii import parse_cii
from einvoice.parsing.detect import detect_format
from einvoice.parsing.ubl import NS as UBL_NS
from einvoice.parsing.ubl import parse_ubl
from einvoice.parsing.xmltools import parse_xml
from einvoice.synth import render
from einvoice.synth.generate import generate


@pytest.fixture(scope="module")
def generated_invoice(tmp_path_factory):
    directory = tmp_path_factory.mktemp("render")
    generate(seed=3, out=directory, count=12)
    xml = next(directory.glob("invoices/*.xml"))
    return (parse_ubl if b"urn:oasis:names" in xml.read_bytes() else parse_cii)(xml.read_bytes())


@pytest.mark.parametrize("layout", range(len(render.LAYOUTS)))
def test_layout_shows_the_fields_extraction_must_find(generated_invoice, layout):
    pdf = render.render_pdf(generated_invoice, layout)
    text = pdfplumber.open(BytesIO(pdf)).pages[0].extract_text()
    gross = f"{generated_invoice.gross_total.value:,.2f}".translate(str.maketrans(",.", ".,"))
    assert generated_invoice.number.value in text
    assert generated_invoice.seller_vat_id.value in text
    assert generated_invoice.iban.value in text
    assert gross in text
    assert detect_format(pdf) == "pdf"


def test_missing_vat_id_is_left_off_the_page(generated_invoice):
    without = generated_invoice.model_copy(update={"seller_vat_id": None})
    text = pdfplumber.open(BytesIO(render.render_pdf(without, 0))).pages[0].extract_text()
    assert "USt-IdNr." not in text


def test_scan_has_no_text_layer_and_depends_on_the_seed(generated_invoice):
    pdf = render.render_pdf(generated_invoice, 0)
    scan = render.render_scan(pdf, random.Random(1))
    assert detect_format(scan) == "scan"
    assert scan == render.render_scan(pdf, random.Random(1))
    assert scan != render.render_scan(pdf, random.Random(2))


def test_ubl_output_parses_back(generated_invoice):
    again = parse_ubl(render.invoice_to_ubl(generated_invoice))
    assert again.number.value == generated_invoice.number.value
    assert again.gross_total.value == generated_invoice.gross_total.value
    assert [line.po_line_ref.value for line in again.lines] == [
        line.po_line_ref.value for line in generated_invoice.lines
    ]


def test_ubl_currency_sits_on_the_amount_only(generated_invoice):
    root = parse_xml(render.invoice_to_ubl(generated_invoice))
    assert root.xpath("//cac:Price/@*", namespaces=UBL_NS) == []
    assert root.xpath("//cac:Price/cbc:PriceAmount/@currencyID", namespaces=UBL_NS)
