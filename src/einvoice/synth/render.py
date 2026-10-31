"""Renders a canonical Invoice as UBL XML, a plain PDF in one of three layouts, or a noisy scan."""

import random
from dataclasses import dataclass
from decimal import Decimal
from io import BytesIO

import numpy as np
import pypdfium2
from lxml import etree
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from einvoice.models import Invoice

UBL_NS = {
    None: "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}
XRECHNUNG_ID = "urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"
CONTACT_EMAIL = "rechnung@example.com"
UNIT_TEXT = {
    "C62": "Stk",
    "HUR": "Std",
    "MON": "Monat",
    "KGM": "kg",
    "LTR": "l",
    "DAY": "Tag",
    "MTR": "m",
}


def _cents(amount: Decimal) -> str:
    return f"{amount:.2f}"


def _sub(parent: etree._Element, path: str, text: str | None = None, **attributes: str):
    """Append the elements of a 'cac:A/cbc:B' path (created as needed, last one new) to parent."""
    element = parent
    for step in path.split("/"):
        prefix, name = step.split(":")
        element = etree.SubElement(element, f"{{{UBL_NS[prefix]}}}{name}", **attributes)
    if text is not None:
        element.text = text
    return element


def _party(parent: etree._Element, role: str, name, address, vat_id, with_contact: bool) -> None:
    party = _sub(parent, f"cac:{role}/cac:Party")
    _sub(party, "cbc:EndpointID", CONTACT_EMAIL, schemeID="EM")
    postal = _sub(party, "cac:PostalAddress")
    _sub(postal, "cbc:StreetName", address.value.street)
    _sub(postal, "cbc:CityName", address.value.city)
    _sub(postal, "cbc:PostalZone", address.value.postcode)
    _sub(postal, "cac:Country/cbc:IdentificationCode", address.value.country or "DE")
    if vat_id is not None:
        tax = _sub(party, "cac:PartyTaxScheme")
        _sub(tax, "cbc:CompanyID", vat_id.value)
        _sub(tax, "cac:TaxScheme/cbc:ID", "VAT")
    _sub(party, "cac:PartyLegalEntity/cbc:RegistrationName", name.value)
    if with_contact:
        contact = _sub(party, "cac:Contact")
        _sub(contact, "cbc:Name", "Rechnungswesen")
        _sub(contact, "cbc:Telephone", "+49 30 1234567")
        _sub(contact, "cbc:ElectronicMail", CONTACT_EMAIL)


def _tax_category(parent: etree._Element, path: str, category, rate) -> None:
    tax = _sub(parent, path)
    _sub(tax, "cbc:ID", category.value)
    _sub(tax, "cbc:Percent", f"{rate.value:.2f}")
    _sub(tax, "cac:TaxScheme/cbc:ID", "VAT")


def invoice_to_ubl(invoice: Invoice) -> bytes:
    """UBL 2.1 XRechnung for the generated invoices; fields that are None are left out."""
    currency = {"currencyID": invoice.currency.value}
    root = etree.Element(f"{{{UBL_NS[None]}}}Invoice", nsmap=UBL_NS)
    _sub(root, "cbc:CustomizationID", XRECHNUNG_ID)
    _sub(root, "cbc:ProfileID", "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0")
    _sub(root, "cbc:ID", invoice.number.value)
    _sub(root, "cbc:IssueDate", invoice.issue_date.value.isoformat())
    if invoice.due_date is not None:
        _sub(root, "cbc:DueDate", invoice.due_date.value.isoformat())
    _sub(root, "cbc:InvoiceTypeCode", invoice.type_code.value)
    _sub(root, "cbc:DocumentCurrencyCode", invoice.currency.value)
    if invoice.buyer_reference is not None:
        _sub(root, "cbc:BuyerReference", invoice.buyer_reference.value)
    if invoice.po_number is not None:
        _sub(root, "cac:OrderReference/cbc:ID", invoice.po_number.value)
    _party(
        root,
        "AccountingSupplierParty",
        invoice.seller_name,
        invoice.seller_address,
        invoice.seller_vat_id,
        with_contact=True,
    )
    _party(
        root,
        "AccountingCustomerParty",
        invoice.buyer_name,
        invoice.buyer_address,
        None,
        with_contact=False,
    )
    if invoice.delivery_date is not None:
        _sub(root, "cac:Delivery/cbc:ActualDeliveryDate", invoice.delivery_date.value.isoformat())
    if invoice.iban is not None:
        means = _sub(root, "cac:PaymentMeans")
        _sub(means, "cbc:PaymentMeansCode", "58")
        _sub(means, "cac:PayeeFinancialAccount/cbc:ID", invoice.iban.value)

    tax_total = _sub(root, "cac:TaxTotal")
    _sub(tax_total, "cbc:TaxAmount", _cents(invoice.vat_total.value), **currency)
    for part in invoice.vat_breakdown:
        subtotal = _sub(tax_total, "cac:TaxSubtotal")
        _sub(subtotal, "cbc:TaxableAmount", _cents(part.taxable_amount.value), **currency)
        _sub(subtotal, "cbc:TaxAmount", _cents(part.tax_amount.value), **currency)
        _tax_category(subtotal, "cac:TaxCategory", part.category, part.rate)
    totals = _sub(root, "cac:LegalMonetaryTotal")
    _sub(totals, "cbc:LineExtensionAmount", _cents(invoice.line_net_total.value), **currency)
    _sub(totals, "cbc:TaxExclusiveAmount", _cents(invoice.tax_exclusive_total.value), **currency)
    _sub(totals, "cbc:TaxInclusiveAmount", _cents(invoice.gross_total.value), **currency)
    _sub(totals, "cbc:PayableAmount", _cents(invoice.amount_due.value), **currency)

    for line in invoice.lines:
        element = _sub(root, "cac:InvoiceLine")
        _sub(element, "cbc:ID", line.line_id.value)
        _sub(element, "cbc:InvoicedQuantity", f"{line.quantity.value:f}", unitCode=line.unit.value)
        _sub(element, "cbc:LineExtensionAmount", _cents(line.net_amount.value), **currency)
        if line.po_line_ref is not None:
            _sub(element, "cac:OrderLineReference/cbc:LineID", line.po_line_ref.value)
        item = _sub(element, "cac:Item")
        _sub(item, "cbc:Name", line.item_name.value)
        _tax_category(item, "cac:ClassifiedTaxCategory", line.vat_category, line.vat_rate)
        _sub(element, "cac:Price/cbc:PriceAmount", _cents(line.price.value), **currency)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


@dataclass(frozen=True)
class Layout:
    title: str
    number: str
    issued: str
    delivery: str
    order: str
    vat_id: str
    columns: tuple[str, ...]
    date_format: str
    seller_right: bool


LAYOUTS = (
    Layout(
        "Rechnung",
        "Rechnungsnummer",
        "Rechnungsdatum",
        "Lieferdatum",
        "Bestellnummer",
        "USt-IdNr.",
        ("pos", "name", "qty", "unit", "price", "vat", "net"),
        "%d.%m.%Y",
        False,
    ),
    Layout(
        "Rechnung",
        "Rechnung Nr.",
        "Datum",
        "Leistungsdatum",
        "Ihre Bestellung",
        "Umsatzsteuer-ID",
        ("pos", "name", "qty", "price", "net"),
        "%d.%m.%y",
        True,
    ),
    Layout(
        "Beleg",
        "Beleg-Nr.",
        "Belegdatum",
        "Liefertermin",
        "Auftrag",
        "VAT-ID",
        ("name", "qty", "unit", "price", "vat", "net"),
        "%d.%m.%Y",
        False,
    ),
)
HEADINGS = {
    "pos": "Pos.",
    "name": "Bezeichnung",
    "qty": "Menge",
    "unit": "Einheit",
    "price": "Einzelpreis",
    "vat": "USt %",
    "net": "Netto",
}
COLUMN_WIDTH = {"pos": 30, "qty": 45, "unit": 50, "price": 70, "vat": 45, "net": 70}
LEFT, RIGHT = 50, A4[0] - 50


def _de_number(amount: Decimal, places: int = 2) -> str:
    text = f"{amount:,.{places}f}"
    return text.replace(",", "\0").replace(".", ",").replace("\0", ".")


def _de_quantity(quantity: Decimal) -> str:
    return str(int(quantity)) if quantity == quantity.to_integral() else _de_number(quantity, 2)


def _draw_table(pdf: canvas.Canvas, invoice: Invoice, layout: Layout, top: float) -> float:
    fixed = sum(COLUMN_WIDTH[name] for name in layout.columns if name != "name")
    widths = {name: COLUMN_WIDTH.get(name, RIGHT - LEFT - fixed) for name in layout.columns}
    edges, x = {}, LEFT
    for name in layout.columns:
        edges[name] = (x, x + widths[name])
        x += widths[name]

    def cell(name: str, y: float, text: str) -> None:
        if name in ("name", "unit", "pos"):
            pdf.drawString(edges[name][0] + 2, y, text)
        else:
            pdf.drawRightString(edges[name][1] - 2, y, text)

    pdf.setFont("Helvetica-Bold", 9)
    for name in layout.columns:
        cell(name, top, HEADINGS[name])
    pdf.line(LEFT, top - 4, RIGHT, top - 4)
    pdf.setFont("Helvetica", 9)
    y = top - 18
    for position, line in enumerate(invoice.lines, start=1):
        cells = {
            "pos": str(position),
            "name": line.item_name.value,
            "qty": _de_quantity(line.quantity.value),
            "unit": UNIT_TEXT.get(line.unit.value, line.unit.value),
            "price": _de_number(line.price.value),
            "vat": _de_number(line.vat_rate.value, 0),
            "net": _de_number(line.net_amount.value),
        }
        for name in layout.columns:
            cell(name, y, cells[name])
        y -= 14
    pdf.line(LEFT, y + 6, RIGHT, y + 6)
    return y - 10


def render_pdf(invoice: Invoice, layout_index: int) -> bytes:
    layout = LAYOUTS[layout_index]
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, invariant=1)

    def day(field) -> str:
        return field.value.strftime(layout.date_format)

    seller_lines = [invoice.seller_name.value]
    address = invoice.seller_address.value
    seller_lines += [address.street, f"{address.postcode} {address.city}"]
    if invoice.seller_vat_id is not None:
        seller_lines.append(f"{layout.vat_id} {invoice.seller_vat_id.value}")
    pdf.setFont("Helvetica-Bold", 11)
    y = A4[1] - 60
    for text in seller_lines:
        if layout.seller_right:
            pdf.drawRightString(RIGHT, y, text)
        else:
            pdf.drawString(LEFT, y, text)
        pdf.setFont("Helvetica", 9)
        y -= 13

    buyer = invoice.buyer_address.value
    y = A4[1] - 190
    for text in (invoice.buyer_name.value, buyer.street, f"{buyer.postcode} {buyer.city}"):
        pdf.drawString(LEFT, y, text)
        y -= 13

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(LEFT, A4[1] - 270, layout.title)
    pdf.setFont("Helvetica", 9)
    meta = [(layout.number, invoice.number.value), (layout.issued, day(invoice.issue_date))]
    if invoice.delivery_date is not None:
        meta.append((layout.delivery, day(invoice.delivery_date)))
    if invoice.po_number is not None:
        meta.append((layout.order, invoice.po_number.value))
    y = A4[1] - 290
    for label, value in meta:
        pdf.drawString(LEFT, y, f"{label}: {value}")
        y -= 13

    y = _draw_table(pdf, invoice, layout, y - 20)
    pdf.setFont("Helvetica", 9)
    for part in invoice.vat_breakdown:
        rate = _de_number(part.rate.value, 0)
        pdf.drawString(
            LEFT, y, f"Nettobetrag {rate} %: {_de_number(part.taxable_amount.value)} EUR"
        )
        y -= 13
        pdf.drawString(LEFT, y, f"Umsatzsteuer {rate} %: {_de_number(part.tax_amount.value)} EUR")
        y -= 13
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(LEFT, y, f"Summe netto: {_de_number(invoice.tax_exclusive_total.value)} EUR")
    y -= 14
    pdf.drawString(LEFT, y, f"Gesamtbetrag: {_de_number(invoice.gross_total.value)} EUR")
    y -= 24
    pdf.setFont("Helvetica", 9)
    if invoice.due_date is not None:
        pdf.drawString(LEFT, y, f"Zahlbar bis {day(invoice.due_date)} ohne Abzug.")
        y -= 13
    if invoice.iban is not None:
        pdf.drawString(LEFT, y, f"IBAN: {invoice.iban.value}")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def render_scan(pdf_bytes: bytes, rng: random.Random) -> bytes:
    """Rasterise page one, tilt it slightly and add sensor noise; the result has no text layer."""
    page = pypdfium2.PdfDocument(pdf_bytes)[0]
    image = page.render(scale=3).to_pil().convert("L")
    image = image.rotate(rng.uniform(-1.5, 1.5), resample=Image.Resampling.BICUBIC, fillcolor=255)
    noise = np.random.default_rng(rng.randrange(2**32)).normal(0, 12, (image.height, image.width))
    pixels = np.clip(np.asarray(image, dtype=np.float32) + noise, 0, 255).astype(np.uint8)
    buffer = BytesIO()
    Image.fromarray(pixels).save(buffer, format="PNG")
    return buffer.getvalue()
