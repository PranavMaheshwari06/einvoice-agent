"""ZUGFeRD / Factur-X: the invoice XML embedded in a PDF/A-3."""

from io import BytesIO

from pypdf import PdfReader

from einvoice.models import Invoice
from einvoice.parsing.cii import parse_cii
from einvoice.parsing.ubl import parse_ubl
from einvoice.parsing.xmltools import parse_xml, xml_syntax

ATTACHMENT_NAMES = ("factur-x.xml", "zugferd-invoice.xml", "xrechnung.xml")


def embedded_invoice_xml(reader: PdfReader) -> bytes | None:
    """The attached invoice XML, or None when the PDF carries none (a plain PDF)."""
    for name, contents in reader.attachments.items():
        if name.lower() in ATTACHMENT_NAMES and contents:
            return contents[0]
    return None


def parse_zugferd(content: bytes) -> Invoice:
    xml = embedded_invoice_xml(PdfReader(BytesIO(content)))
    if xml is None:
        raise ValueError(
            f"PDF has no embedded invoice XML (looked for {', '.join(ATTACHMENT_NAMES)})"
        )
    # xrechnung.xml may be UBL; factur-x.xml and zugferd-invoice.xml are CII.
    parse = parse_cii if xml_syntax(parse_xml(xml)) == "cii" else parse_ubl
    return parse(xml).model_copy(update={"format": "zugferd_pdf"})
