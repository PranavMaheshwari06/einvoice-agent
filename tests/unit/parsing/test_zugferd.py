from datetime import date
from io import BytesIO

import pytest
from reportlab.pdfgen import canvas

from conftest import FIXTURES
from einvoice.parsing.cii import parse_cii
from einvoice.parsing.zugferd import parse_zugferd


def text_pdf(text: str) -> bytes:
    buffer = BytesIO()
    page = canvas.Canvas(buffer)
    page.drawString(72, 720, text)
    page.save()
    return buffer.getvalue()


def test_reads_embedded_factur_x_xml(mustang_invoice):
    assert mustang_invoice.format == "zugferd_pdf"
    assert mustang_invoice.number.value == "RE-20201121/508"
    assert mustang_invoice.due_date.value == date(2020, 12, 12)
    assert mustang_invoice.seller_vat_id.value == "DE136695976"
    assert len(mustang_invoice.lines) == 3


def test_pdf_and_standalone_xml_of_the_same_invoice_agree():
    from_pdf = parse_zugferd((FIXTURES / "corpus" / "zugferd_2p0_EN16931_Einfach.pdf").read_bytes())
    from_xml = parse_cii((FIXTURES / "corpus" / "EN16931_Einfach.cii.xml").read_bytes())
    # The two corpus files differ only in the unit codes of the lines (C62 vs H87).
    header = {"format", "lines"}
    assert from_pdf.model_dump(exclude=header) == from_xml.model_dump(exclude=header)
    line_nets = [[line.net_amount for line in invoice.lines] for invoice in (from_pdf, from_xml)]
    assert line_nets[0] == line_nets[1]


def test_plain_pdf_is_rejected():
    with pytest.raises(ValueError, match="no embedded invoice XML"):
        parse_zugferd(text_pdf("Rechnung Nr. 1"))
