from io import BytesIO

import pdfplumber


def page_texts(content: bytes) -> list[str]:
    """Text layer of each PDF page, in page order; a page without text gives an empty string."""
    with pdfplumber.open(BytesIO(content)) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]
