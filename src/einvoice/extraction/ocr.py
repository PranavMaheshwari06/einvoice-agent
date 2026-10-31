from io import BytesIO

import pypdfium2
import pytesseract
from PIL import Image

OCR_SCALE = 300 / 72  # PDF points to 300 dpi


def ocr_pages(content: bytes) -> list[str]:
    """OCR text per page of a scanned PDF or a single image. Needs the tesseract binary."""
    if content.startswith(b"%PDF-"):
        images = [page.render(scale=OCR_SCALE).to_pil() for page in pypdfium2.PdfDocument(content)]
    else:
        images = [Image.open(BytesIO(content))]
    return [pytesseract.image_to_string(image, lang="deu") for image in images]
