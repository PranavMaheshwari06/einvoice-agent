"""UN/CEFACT CII D16B (XRechnung CII, ZUGFeRD/Factur-X) -> canonical Invoice."""

from decimal import Decimal

from lxml import etree

from einvoice.models import Invoice, LineItem, VatBreakdown
from einvoice.parsing.xmltools import (
    CII_NS,
    address_field,
    cii_date,
    parse_xml,
    xml_field,
    xml_fields,
    xml_syntax,
)

NS = {
    "rsm": CII_NS,
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
    "qdt": "urn:un:unece:uncefact:data:standard:QualifiedDataType:100",
}
DOCUMENT = "/rsm:CrossIndustryInvoice/rsm:ExchangedDocument"
TRANSACTION = "/rsm:CrossIndustryInvoice/rsm:SupplyChainTradeTransaction"
AGREEMENT = f"{TRANSACTION}/ram:ApplicableHeaderTradeAgreement"
DELIVERY = f"{TRANSACTION}/ram:ApplicableHeaderTradeDelivery"
SETTLEMENT = f"{TRANSACTION}/ram:ApplicableHeaderTradeSettlement"
TOTALS = f"{SETTLEMENT}/ram:SpecifiedTradeSettlementHeaderMonetarySummation"
ADDRESS_PARTS = {
    "street": "ram:LineOne",
    "city": "ram:CityName",
    "postcode": "ram:PostcodeCode",
    "country": "ram:CountryID",
}


def _line(line: etree._Element) -> LineItem:
    def text(path: str, bt: str):
        return xml_field(line, path, NS, bt)

    def amount(path: str, bt: str):
        return xml_field(line, path, NS, bt, Decimal)

    net_price = "ram:SpecifiedLineTradeAgreement/ram:NetPriceProductTradePrice"
    line_tax = "ram:SpecifiedLineTradeSettlement/ram:ApplicableTradeTax"
    allowance = (
        "ram:SpecifiedLineTradeSettlement/ram:SpecifiedTradeAllowanceCharge"
        "[ram:ChargeIndicator/udt:Indicator='{}']/ram:ActualAmount"
    )
    return LineItem(
        line_id=text("ram:AssociatedDocumentLineDocument/ram:LineID", "BT-126"),
        quantity=amount("ram:SpecifiedLineTradeDelivery/ram:BilledQuantity", "BT-129"),
        unit=text("ram:SpecifiedLineTradeDelivery/ram:BilledQuantity/@unitCode", "BT-130"),
        net_amount=amount(
            "ram:SpecifiedLineTradeSettlement/"
            "ram:SpecifiedTradeSettlementLineMonetarySummation/ram:LineTotalAmount",
            "BT-131",
        ),
        po_line_ref=text(
            "ram:SpecifiedLineTradeAgreement/ram:BuyerOrderReferencedDocument/ram:LineID", "BT-132"
        ),
        allowances=xml_fields(line, allowance.format("false"), NS, "BT-136", Decimal),
        charges=xml_fields(line, allowance.format("true"), NS, "BT-141", Decimal),
        price=amount(f"{net_price}/ram:ChargeAmount", "BT-146"),
        price_base_quantity=amount(f"{net_price}/ram:BasisQuantity", "BT-149"),
        vat_category=text(f"{line_tax}/ram:CategoryCode", "BT-151"),
        vat_rate=amount(f"{line_tax}/ram:RateApplicablePercent", "BT-152"),
        item_name=text("ram:SpecifiedTradeProduct/ram:Name", "BT-153"),
    )


def _vat_breakdown(tax: etree._Element) -> VatBreakdown:
    return VatBreakdown(
        taxable_amount=xml_field(tax, "ram:BasisAmount", NS, "BT-116", Decimal),
        tax_amount=xml_field(tax, "ram:CalculatedAmount", NS, "BT-117", Decimal),
        category=xml_field(tax, "ram:CategoryCode", NS, "BT-118"),
        rate=xml_field(tax, "ram:RateApplicablePercent", NS, "BT-119", Decimal),
    )


def parse_cii(content: bytes) -> Invoice:
    root = parse_xml(content)
    if xml_syntax(root) != "cii":
        raise ValueError("not a CII invoice")

    def text(path: str, bt: str):
        return xml_field(root, path, NS, bt)

    def amount(path: str, bt: str):
        return xml_field(root, path, NS, bt, Decimal)

    def day(path: str, bt: str):
        return xml_field(root, f"{path}/udt:DateTimeString", NS, bt, cii_date)

    seller = f"{AGREEMENT}/ram:SellerTradeParty"
    buyer = f"{AGREEMENT}/ram:BuyerTradeParty"
    period = f"{SETTLEMENT}/ram:BillingSpecifiedPeriod"
    # BT-110 is the tax total in invoice currency; a second one in tax currency is BT-111.
    vat_total = "ram:TaxTotalAmount[not(@currencyID) or @currencyID=../../ram:InvoiceCurrencyCode]"
    return Invoice(
        format="cii",
        number=text(f"{DOCUMENT}/ram:ID", "BT-1"),
        issue_date=day(f"{DOCUMENT}/ram:IssueDateTime", "BT-2"),
        type_code=text(f"{DOCUMENT}/ram:TypeCode", "BT-3"),
        currency=text(f"{SETTLEMENT}/ram:InvoiceCurrencyCode", "BT-5"),
        due_date=day(f"{SETTLEMENT}/ram:SpecifiedTradePaymentTerms/ram:DueDateDateTime", "BT-9"),
        buyer_reference=text(f"{AGREEMENT}/ram:BuyerReference", "BT-10"),
        po_number=text(
            f"{AGREEMENT}/ram:BuyerOrderReferencedDocument/ram:IssuerAssignedID", "BT-13"
        ),
        seller_name=text(f"{seller}/ram:Name", "BT-27"),
        seller_vat_id=text(
            f"{seller}/ram:SpecifiedTaxRegistration/ram:ID[@schemeID='VA']", "BT-31"
        ),
        seller_tax_number=text(
            f"{seller}/ram:SpecifiedTaxRegistration/ram:ID[@schemeID='FC']", "BT-32"
        ),
        seller_address=address_field(
            root, f"{seller}/ram:PostalTradeAddress", NS, "BG-5", ADDRESS_PARTS
        ),
        buyer_name=text(f"{buyer}/ram:Name", "BT-44"),
        buyer_address=address_field(
            root, f"{buyer}/ram:PostalTradeAddress", NS, "BG-8", ADDRESS_PARTS
        ),
        delivery_date=day(
            f"{DELIVERY}/ram:ActualDeliverySupplyChainEvent/ram:OccurrenceDateTime", "BT-72"
        ),
        period_start=day(f"{period}/ram:StartDateTime", "BT-73"),
        period_end=day(f"{period}/ram:EndDateTime", "BT-74"),
        iban=text(
            f"{SETTLEMENT}/ram:SpecifiedTradeSettlementPaymentMeans/"
            "ram:PayeePartyCreditorFinancialAccount/ram:IBANID",
            "BT-84",
        ),
        line_net_total=amount(f"{TOTALS}/ram:LineTotalAmount", "BT-106"),
        allowance_total=amount(f"{TOTALS}/ram:AllowanceTotalAmount", "BT-107"),
        charge_total=amount(f"{TOTALS}/ram:ChargeTotalAmount", "BT-108"),
        tax_exclusive_total=amount(f"{TOTALS}/ram:TaxBasisTotalAmount", "BT-109"),
        vat_total=amount(f"{TOTALS}/{vat_total}", "BT-110"),
        gross_total=amount(f"{TOTALS}/ram:GrandTotalAmount", "BT-112"),
        prepaid_total=amount(f"{TOTALS}/ram:TotalPrepaidAmount", "BT-113"),
        rounding_amount=amount(f"{TOTALS}/ram:RoundingAmount", "BT-114"),
        amount_due=amount(f"{TOTALS}/ram:DuePayableAmount", "BT-115"),
        lines=[
            _line(line)
            for line in root.xpath(
                f"{TRANSACTION}/ram:IncludedSupplyChainTradeLineItem", namespaces=NS
            )
        ],
        vat_breakdown=[
            _vat_breakdown(tax)
            for tax in root.xpath(f"{SETTLEMENT}/ram:ApplicableTradeTax", namespaces=NS)
        ],
    )
