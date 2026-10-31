"""Canonical invoice model shared by every input path, plus the master data the rules read."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Generic, Literal, TypeVar

import pydantic
from pydantic import BaseModel

Format = Literal["ubl", "cii", "zugferd_pdf", "pdf", "scan"]
STRUCTURED_FORMATS: tuple[Format, ...] = ("ubl", "cii", "zugferd_pdf")

T = TypeVar("T")


class Evidence(BaseModel):
    """Where a value came from: an XML element (BT id + XPath) or a page and quote in a PDF."""

    source: Literal["xml", "pdf"]
    bt: str | None = None
    xpath: str | None = None
    page: int | None = None
    quote: str | None = None


class Field(BaseModel, Generic[T]):
    value: T
    evidence: Evidence
    confidence: float = pydantic.Field(default=1.0, ge=0.0, le=1.0)


class Address(BaseModel):
    street: str | None = None
    city: str | None = None
    postcode: str | None = None
    country: str | None = None


class LineItem(BaseModel):
    line_id: Field[str] | None = None
    quantity: Field[Decimal] | None = None
    unit: Field[str] | None = None
    net_amount: Field[Decimal] | None = None
    po_line_ref: Field[str] | None = None
    allowances: list[Field[Decimal]] = []
    charges: list[Field[Decimal]] = []
    price: Field[Decimal] | None = None
    price_base_quantity: Field[Decimal] | None = None
    vat_category: Field[str] | None = None
    vat_rate: Field[Decimal] | None = None
    item_name: Field[str] | None = None


class VatBreakdown(BaseModel):
    taxable_amount: Field[Decimal] | None = None
    tax_amount: Field[Decimal] | None = None
    category: Field[str] | None = None
    rate: Field[Decimal] | None = None


class Invoice(BaseModel):
    format: Format
    number: Field[str] | None = None
    issue_date: Field[date] | None = None
    type_code: Field[str] | None = None
    currency: Field[str] | None = None
    due_date: Field[date] | None = None
    buyer_reference: Field[str] | None = None
    po_number: Field[str] | None = None
    seller_name: Field[str] | None = None
    seller_vat_id: Field[str] | None = None
    seller_tax_number: Field[str] | None = None
    seller_address: Field[Address] | None = None
    buyer_name: Field[str] | None = None
    buyer_address: Field[Address] | None = None
    delivery_date: Field[date] | None = None
    period_start: Field[date] | None = None
    period_end: Field[date] | None = None
    iban: Field[str] | None = None
    line_net_total: Field[Decimal] | None = None
    allowance_total: Field[Decimal] | None = None
    charge_total: Field[Decimal] | None = None
    tax_exclusive_total: Field[Decimal] | None = None
    vat_total: Field[Decimal] | None = None
    gross_total: Field[Decimal] | None = None
    prepaid_total: Field[Decimal] | None = None
    rounding_amount: Field[Decimal] | None = None
    amount_due: Field[Decimal] | None = None
    lines: list[LineItem] = []
    vat_breakdown: list[VatBreakdown] = []


class RuleViolation(BaseModel):
    rule_id: str
    level: Literal["error", "warning", "information"]
    message: str
    xpath: str | None = None


class ValidationResult(BaseModel):
    accepted: bool
    errors: list[RuleViolation]


class CheckResult(BaseModel):
    code: str
    passed: bool
    message: str
    severity: Literal["error", "warning", "info"] = "error"


class Decision(BaseModel):
    kind: Literal["AUTO_BOOK", "REVIEW"]
    reasons: list[str]


class BookingProposal(BaseModel):
    invoice_id: str
    gl_account: str
    net_total: Decimal
    vat_total: Decimal
    gross_total: Decimal
    due_date: date | None


class Vendor(BaseModel):
    vat_id: str
    name: str
    iban: str


class PoLine(BaseModel):
    line_id: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    received_quantity: Decimal | None = None


class PurchaseOrder(BaseModel):
    po_number: str
    vendor_vat_id: str
    lines: list[PoLine]


class PriorInvoice(BaseModel):
    seller_vat_id: str | None
    seller_name: str
    number: str
    gross_total: Decimal
    issue_date: date


@dataclass
class RuleContext:
    """Everything the rules need besides the invoice; loaded from the database by the caller."""

    vendor: Vendor | None = None
    purchase_order: PurchaseOrder | None = None
    prior_invoices: list[PriorInvoice] = field(default_factory=list)
    validation: ValidationResult | None = None
    gl_probability: float | None = None
    extract_threshold: float = 0.9
    gl_threshold: float = 0.9
