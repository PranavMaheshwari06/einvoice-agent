import shutil
from io import BytesIO

import pypdfium2
import pytest
from reportlab.pdfgen import canvas

from einvoice.extraction.ocr import ocr_pages
from einvoice.synth.generate import read_gold

needs_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None, reason="tesseract binary is not installed"
)


def _pdf_with_text(text: str) -> bytes:
    buffer = BytesIO()
    page = canvas.Canvas(buffer)
    page.setFont("Helvetica", 28)
    page.drawString(72, 700, text)
    page.save()
    return buffer.getvalue()


@needs_tesseract
def test_ocr_reads_a_scanned_pdf_page():
    pages = ocr_pages(_pdf_with_text("Rechnung Nr. 12345"))

    assert len(pages) == 1
    assert "Rechnung" in pages[0]


@pytest.mark.integration
def test_ocr_reads_number_and_seller_on_every_generated_scan(gold_dir):
    # Amounts are left out on purpose: tesseract misreads a digit now and then (inv_00187 of
    # seed 1 gives 36,64 for 35,27), which the arithmetic rule and the evidence check catch.
    scans = [record for record in read_gold(gold_dir) if record["format"] == "scan"]
    assert len(scans) > 5
    for record in scans:
        text = " ".join(ocr_pages((gold_dir / record["file"]).read_bytes())[0].split())
        assert record["number"] in text, record["id"]
        assert record["vendor_name"] in text, record["id"]


@needs_tesseract
def test_ocr_reads_an_image():
    image = pypdfium2.PdfDocument(_pdf_with_text("Gesamtbetrag 140,99")).get_page(0)
    buffer = BytesIO()
    image.render(scale=3).to_pil().save(buffer, format="PNG")

    assert "Gesamtbetrag" in ocr_pages(buffer.getvalue())[0]
