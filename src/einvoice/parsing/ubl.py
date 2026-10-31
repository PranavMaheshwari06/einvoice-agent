"""UBL 2.1 Invoice and CreditNote -> canonical Invoice, mapped by EN 16931 business terms."""

from datetime import date
from decimal import Decimal

from lxml import etree

from einvoice.models import Invoice, LineItem, VatBreakdown
from einvoice.parsing.xmltools import (
    UBL_CREDIT_NOTE_NS,
    UBL_INVOICE_NS,
    address_field,
    parse_xml,
    xml_field,
    xml_fields,
    xml_syntax,
)

NS = {
    "ubl": UBL_INVOICE_NS,
    "cn": UBL_CREDIT_NOTE_NS,
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}
SELLER = "/*/cac:AccountingSupplierParty/cac:Party"
BUYER = "/*/cac:AccountingCustomerParty/cac:Party"
TOTALS = "/*/cac:LegalMonetaryTotal"
ADDRESS_PARTS = {
    "street": "cbc:StreetName",
    "city": "cbc:CityName",
    "postcode": "cbc:PostalZone",
    "country": "cac:Country/cbc:IdentificationCode",
}


def _line(line: etree._Element) -> LineItem:
    def text(path: str, bt: str):
        return xml_field(line, path, NS, bt)

    def amount(path: str, bt: str):
        return xml_field(line, path, NS, bt, Decimal)

    allowance = "cac:AllowanceCharge[cbc:ChargeIndicator='{}']/cbc:Amount"
    return LineItem(
        line_id=text("cbc:ID", "BT-126"),
        quantity=amount("cbc:InvoicedQuantity | cbc:CreditedQuantity", "BT-129"),
        unit=text("cbc:InvoicedQuantity/@unitCode | cbc:CreditedQuantity/@unitCode", "BT-130"),
        net_amount=amount("cbc:LineExtensionAmount", "BT-131"),
        po_line_ref=text("cac:OrderLineReference/cbc:LineID", "BT-132"),
        allowances=xml_fields(line, allowance.format("false"), NS, "BT-136", Decimal),
        charges=xml_fields(line, allowance.format("true"), NS, "BT-141", Decimal),
        price=amount("cac:Price/cbc:PriceAmount", "BT-146"),
        price_base_quantity=amount("cac:Price/cbc:BaseQuantity", "BT-149"),
        vat_category=text("cac:Item/cac:ClassifiedTaxCategory/cbc:ID", "BT-151"),
        vat_rate=amount("cac:Item/cac:ClassifiedTaxCategory/cbc:Percent", "BT-152"),
        item_name=text("cac:Item/cbc:Name", "BT-153"),
    )


def _vat_breakdown(subtotal: etree._Element) -> VatBreakdown:
    return VatBreakdown(
        taxable_amount=xml_field(subtotal, "cbc:TaxableAmount", NS, "BT-116", Decimal),
        tax_amount=xml_field(subtotal, "cbc:TaxAmount", NS, "BT-117", Decimal),
        category=xml_field(subtotal, "cac:TaxCategory/cbc:ID", NS, "BT-118"),
        rate=xml_field(subtotal, "cac:TaxCategory/cbc:Percent", NS, "BT-119", Decimal),
    )


def parse_ubl(content: bytes) -> Invoice:
    root = parse_xml(content)
    if xml_syntax(root) != "ubl":
        raise ValueError("not a UBL invoice")

    def text(path: str, bt: str):
        return xml_field(root, path, NS, bt)

    def amount(path: str, bt: str):
        return xml_field(root, path, NS, bt, Decimal)

    def day(path: str, bt: str):
        return xml_field(root, path, NS, bt, date.fromisoformat)

    vat_scheme = "cac:PartyTaxScheme[cac:TaxScheme/cbc:ID='VAT']/cbc:CompanyID"
    other_scheme = "cac:PartyTaxScheme[cac:TaxScheme/cbc:ID!='VAT']/cbc:CompanyID"
    return Invoice(
        format="ubl",
        number=text("/*/cbc:ID", "BT-1"),
        issue_date=day("/*/cbc:IssueDate", "BT-2"),
        type_code=text("/*/cbc:InvoiceTypeCode | /*/cbc:CreditNoteTypeCode", "BT-3"),
        currency=text("/*/cbc:DocumentCurrencyCode", "BT-5"),
        due_date=day("/*/cbc:DueDate | /*/cac:PaymentMeans/cbc:PaymentDueDate", "BT-9"),
        buyer_reference=text("/*/cbc:BuyerReference", "BT-10"),
        po_number=text("/*/cac:OrderReference/cbc:ID", "BT-13"),
        seller_name=text(f"{SELLER}/cac:PartyLegalEntity/cbc:RegistrationName", "BT-27"),
        seller_vat_id=text(f"{SELLER}/{vat_scheme}", "BT-31"),
        seller_tax_number=text(f"{SELLER}/{other_scheme}", "BT-32"),
        seller_address=address_field(
            root, f"{SELLER}/cac:PostalAddress", NS, "BG-5", ADDRESS_PARTS
        ),
        buyer_name=text(f"{BUYER}/cac:PartyLegalEntity/cbc:RegistrationName", "BT-44"),
        buyer_address=address_field(root, f"{BUYER}/cac:PostalAddress", NS, "BG-8", ADDRESS_PARTS),
        delivery_date=day("/*/cac:Delivery/cbc:ActualDeliveryDate", "BT-72"),
        period_start=day("/*/cac:InvoicePeriod/cbc:StartDate", "BT-73"),
        period_end=day("/*/cac:InvoicePeriod/cbc:EndDate", "BT-74"),
        iban=text("/*/cac:PaymentMeans/cac:PayeeFinancialAccount/cbc:ID", "BT-84"),
        line_net_total=amount(f"{TOTALS}/cbc:LineExtensionAmount", "BT-106"),
        allowance_total=amount(f"{TOTALS}/cbc:AllowanceTotalAmount", "BT-107"),
        charge_total=amount(f"{TOTALS}/cbc:ChargeTotalAmount", "BT-108"),
        tax_exclusive_total=amount(f"{TOTALS}/cbc:TaxExclusiveAmount", "BT-109"),
        # The TaxTotal with subtotals is in document currency (BT-110); the other is BT-111.
        vat_total=amount("/*/cac:TaxTotal[cac:TaxSubtotal]/cbc:TaxAmount", "BT-110"),
        gross_total=amount(f"{TOTALS}/cbc:TaxInclusiveAmount", "BT-112"),
        prepaid_total=amount(f"{TOTALS}/cbc:PrepaidAmount", "BT-113"),
        rounding_amount=amount(f"{TOTALS}/cbc:PayableRoundingAmount", "BT-114"),
        amount_due=amount(f"{TOTALS}/cbc:PayableAmount", "BT-115"),
        lines=[
            _line(line)
            for line in root.xpath("cac:InvoiceLine | cac:CreditNoteLine", namespaces=NS)
        ],
        vat_breakdown=[
            _vat_breakdown(subtotal)
            for subtotal in root.xpath("cac:TaxTotal/cac:TaxSubtotal", namespaces=NS)
        ],
    )
