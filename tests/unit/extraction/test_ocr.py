import shutil
from io import BytesIO

import pypdfium2
import pytest
from reportlab.pdfgen import canvas

from einvoice.extraction.ocr import ocr_pages

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


@needs_tesseract
def test_ocr_reads_an_image():
    image = pypdfium2.PdfDocument(_pdf_with_text("Gesamtbetrag 140,99")).get_page(0)
    buffer = BytesIO()
    image.render(scale=3).to_pil().save(buffer, format="PNG")

    assert "Gesamtbetrag" in ocr_pages(buffer.getvalue())[0]
