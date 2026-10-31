from io import BytesIO

from pypdf import PdfReader

from einvoice.models import Format
from einvoice.parsing.xmltools import parse_xml, xml_syntax
from einvoice.parsing.zugferd import embedded_invoice_xml

IMAGE_SIGNATURES = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"II*\x00", b"MM\x00*")


def detect_format(content: bytes) -> Format:
    """Classify file bytes as ubl, cii, zugferd_pdf, pdf (text layer) or scan (no text)."""
    if b"%PDF-" in content[:1024]:
        reader = PdfReader(BytesIO(content))
        if embedded_invoice_xml(reader) is not None:
            return "zugferd_pdf"
        if any((page.extract_text() or "").strip() for page in reader.pages):
            return "pdf"
        return "scan"
    if content.startswith(IMAGE_SIGNATURES):
        return "scan"
    if content.lstrip(b"\xef\xbb\xbf \t\r\n").startswith(b"<"):
        return xml_syntax(parse_xml(content))
    raise ValueError("unsupported file: not XML, PDF or an image")
