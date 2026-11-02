"""Canonical Invoice -> XRechnung CII XML (drafthorse), also used by the synthetic generator."""

from collections.abc import Callable
from decimal import Decimal

from drafthorse.models.accounting import ApplicableTradeTax
from drafthorse.models.document import Document
from drafthorse.models.party import TaxRegistration
from drafthorse.models.payment import PaymentMeans, PaymentTerms
from drafthorse.models.tradelines import LineItem as CiiLineItem

from einvoice.models import Address, Field, Invoice, LineItem, ValidationResult, value_of

XRECHNUNG_ID = "urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"
# The canonical Invoice has no contact or electronic address, but XRechnung requires both
# (BR-DE-2, BR-DE-5 to 7, PEPPOL-EN16931-R010/R020), so every file carries these placeholders.
CONTACT_NAME = "Rechnungswesen"
CONTACT_PHONE = "+49 30 1234567"
CONTACT_EMAIL = "rechnung@example.com"


def _set_address(party, address: Field[Address] | None) -> None:
    if address is None:
        return
    party.address.line_one = address.value.street or ""
    party.address.postcode = address.value.postcode or ""
    party.address.city_name = address.value.city or ""
    party.address.country_id = address.value.country or "DE"


def _add_line(doc: Document, line: LineItem) -> None:
    if line.allowances or line.charges:
        raise ValueError("line allowances and charges are not supported")
    unit = value_of(line.unit) or "C62"
    item = CiiLineItem()
    item.document.line_id = value_of(line.line_id)
    item.product.name = value_of(line.item_name)
    if line.po_line_ref is not None:
        item.agreement.buyer_order.line_id = line.po_line_ref.value
    item.agreement.net.amount = line.price.value
    item.agreement.net.basis_quantity = (value_of(line.price_base_quantity) or Decimal(1), unit)
    item.delivery.billed_quantity = (line.quantity.value, unit)
    item.settlement.trade_tax.type_code = "VAT"
    item.settlement.trade_tax.category_code = line.vat_category.value
    item.settlement.trade_tax.rate_applicable_percent = line.vat_rate.value
    item.settlement.monetary_summation.total_amount = line.net_amount.value
    doc.trade.items.add(item)


def invoice_to_cii(invoice: Invoice) -> bytes:
    """Write an XRechnung CII document; fields that are None are left out."""
    if any(value_of(total) for total in (invoice.allowance_total, invoice.charge_total)):
        raise ValueError("document allowances and charges are not supported")
    doc = Document()
    doc.context.guideline_parameter.id = XRECHNUNG_ID
    doc.header.id = invoice.number.value
    doc.header.type_code = value_of(invoice.type_code) or "380"
    doc.header.issue_date_time = invoice.issue_date.value

    agreement = doc.trade.agreement
    agreement.buyer_reference = value_of(invoice.buyer_reference)
    if invoice.po_number is not None:
        agreement.buyer_order.issuer_assigned_id = invoice.po_number.value
    seller, buyer = agreement.seller, agreement.buyer
    seller.name = invoice.seller_name.value
    _set_address(seller, invoice.seller_address)
    if invoice.seller_vat_id is not None:
        seller.tax_registrations.add(TaxRegistration(id=("VA", invoice.seller_vat_id.value)))
    if invoice.seller_tax_number is not None:
        seller.tax_registrations.add(TaxRegistration(id=("FC", invoice.seller_tax_number.value)))
    seller.contact.person_name = CONTACT_NAME
    seller.contact.telephone.number = CONTACT_PHONE
    seller.contact.email.address = CONTACT_EMAIL
    seller.electronic_address.uri_ID = ("EM", CONTACT_EMAIL)
    buyer.name = invoice.buyer_name.value
    _set_address(buyer, invoice.buyer_address)
    buyer.electronic_address.uri_ID = ("EM", CONTACT_EMAIL)

    if invoice.delivery_date is not None:
        doc.trade.delivery.event.occurrence = invoice.delivery_date.value

    settlement = doc.trade.settlement
    settlement.currency_code = invoice.currency.value
    if invoice.iban is not None:
        means = PaymentMeans(type_code="58")
        means.payee_account.iban = invoice.iban.value
        settlement.payment_means.add(means)
    if invoice.period_start is not None and invoice.period_end is not None:
        settlement.period.start = invoice.period_start.value
        settlement.period.end = invoice.period_end.value
    if invoice.due_date is not None:
        terms = PaymentTerms()
        terms.due = invoice.due_date.value
        settlement.terms.add(terms)

    for line in invoice.lines:
        _add_line(doc, line)
    for part in invoice.vat_breakdown:
        tax = ApplicableTradeTax()
        tax.type_code = "VAT"
        tax.category_code = part.category.value
        tax.rate_applicable_percent = part.rate.value
        tax.basis_amount = part.taxable_amount.value
        tax.calculated_amount = part.tax_amount.value
        settlement.trade_tax.add(tax)

    totals = settlement.monetary_summation
    totals.line_total = invoice.line_net_total.value
    totals.tax_basis_total = invoice.tax_exclusive_total.value
    totals.tax_total = (invoice.vat_total.value, invoice.currency.value)
    totals.grand_total = invoice.gross_total.value
    if invoice.prepaid_total is not None:
        totals.prepaid_total = invoice.prepaid_total.value
    totals.due_amount = invoice.amount_due.value
    return doc.serialize(schema="FACTUR-X_EN16931")


def to_xrechnung(
    invoice: Invoice, validate: Callable[[bytes], ValidationResult]
) -> tuple[bytes, ValidationResult]:
    """The outgoing XRechnung CII and the KoSIT verdict on it (SPEC 3.11)."""
    xml = invoice_to_cii(invoice)
    return xml, validate(xml)
