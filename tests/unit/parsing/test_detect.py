from io import BytesIO

import pytest
from PIL import Image
from reportlab.pdfgen import canvas

from conftest import FIXTURES
from einvoice.parsing.detect import detect_format


def text_pdf() -> bytes:
    buffer = BytesIO()
    page = canvas.Canvas(buffer)
    page.drawString(72, 720, "Rechnung Nr. 2026-001")
    page.save()
    return buffer.getvalue()


def image_bytes(image_format: str) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (200, 280), "white").save(buffer, format=image_format)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("xrechnung/01.01a-INVOICE_ubl.xml", "ubl"),
        ("xrechnung/02.01a-INVOICE_ubl.xml", "ubl"),
        ("corpus/ubl-tc434-creditnote1.xml", "ubl"),
        ("xrechnung/01.01a-INVOICE_uncefact.xml", "cii"),
        ("corpus/EN16931_Rabatte.cii.xml", "cii"),
        ("corpus/zugferd_2p0_EN16931_Einfach.pdf", "zugferd_pdf"),
        ("corpus/MustangGnuaccountingBeispielRE-20201121_508.pdf", "zugferd_pdf"),
    ],
)
def test_detects_fixture_formats(name, expected):
    assert detect_format((FIXTURES / name).read_bytes()) == expected


def test_pdf_with_text_layer_is_pdf():
    assert detect_format(text_pdf()) == "pdf"


def test_pdf_without_text_is_scan():
    assert detect_format(image_bytes("PDF")) == "scan"


@pytest.mark.parametrize("image_format", ["PNG", "JPEG", "TIFF"])
def test_images_are_scans(image_format):
    assert detect_format(image_bytes(image_format)) == "scan"


def test_unknown_bytes_are_rejected():
    with pytest.raises(ValueError, match="unsupported file"):
        detect_format(b"PK\x03\x04 a zip file")
