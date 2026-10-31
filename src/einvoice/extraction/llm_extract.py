"""LLM extraction for plain PDFs and scans: every value must point at a quote on its page."""

import json
import logging
from collections.abc import Callable, Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Generic, Literal, TypeVar

import pydantic
from pydantic import BaseModel, ValidationError

from einvoice.models import Address, Evidence, Field, Invoice, LineItem, VatBreakdown

logger = logging.getLogger(__name__)

PROMPT_FILE = Path(__file__).parent / "prompts" / "extract_de.txt"
T = TypeVar("T")


class Extracted(BaseModel, Generic[T]):
    value: T
    page: int = pydantic.Field(ge=1)
    quote: str
    confidence: float = pydantic.Field(ge=0.0, le=1.0)


class ExtractedAddress(BaseModel):
    street: Extracted[str] | None = None
    postcode: Extracted[str] | None = None
    city: Extracted[str] | None = None


class ExtractedLine(BaseModel):
    item_name: Extracted[str] | None = None
    quantity: Extracted[Decimal] | None = None
    unit_price: Extracted[Decimal] | None = None
    net_amount: Extracted[Decimal] | None = None
    vat_rate: Extracted[Decimal] | None = None


class ExtractedVat(BaseModel):
    rate: Extracted[Decimal] | None = None
    taxable_amount: Extracted[Decimal] | None = None
    tax_amount: Extracted[Decimal] | None = None


class ExtractedInvoice(BaseModel):
    number: Extracted[str] | None = None
    issue_date: Extracted[date] | None = None
    due_date: Extracted[date] | None = None
    delivery_date: Extracted[date] | None = None
    po_number: Extracted[str] | None = None
    currency: Extracted[str] | None = None
    seller_name: Extracted[str] | None = None
    seller_vat_id: Extracted[str] | None = None
    seller_address: ExtractedAddress | None = None
    buyer_name: Extracted[str] | None = None
    buyer_address: ExtractedAddress | None = None
    iban: Extracted[str] | None = None
    line_net_total: Extracted[Decimal] | None = None
    tax_exclusive_total: Extracted[Decimal] | None = None
    vat_total: Extracted[Decimal] | None = None
    gross_total: Extracted[Decimal] | None = None
    amount_due: Extracted[Decimal] | None = None
    lines: list[ExtractedLine] = []
    vat_breakdown: list[ExtractedVat] = []


def build_prompt(pages: list[str]) -> str:
    template = PROMPT_FILE.read_text(encoding="utf-8")
    schema = json.dumps(ExtractedInvoice.model_json_schema(), separators=(",", ":"))
    text = "\n\n".join(f"[Seite {number}]\n{page}" for number, page in enumerate(pages, start=1))
    return template.replace("{schema}", schema).replace("{pages}", text)


def _fields(node: object) -> Iterator[Extracted]:
    if isinstance(node, Extracted):
        yield node
    elif isinstance(node, BaseModel):
        for name in type(node).model_fields:
            yield from _fields(getattr(node, name))
    elif isinstance(node, list):
        for item in node:
            yield from _fields(item)


def _squash(text: str) -> str:
    return " ".join(text.split())


def check_quotes(extracted: ExtractedInvoice, pages: list[str]) -> list[str]:
    """Zero the confidence of every field whose quote is not on its page; return reason codes."""
    squashed = [_squash(page) for page in pages]
    reasons: list[str] = []
    for field in _fields(extracted):
        on_page = 1 <= field.page <= len(pages) and _squash(field.quote) in squashed[field.page - 1]
        if not on_page:
            logger.warning("quote %r not found on page %d", field.quote, field.page)
            field.confidence = 0.0
            reasons = ["EVIDENCE_NOT_FOUND"]
    return reasons


def _field(extracted: Extracted | None) -> Field | None:
    if extracted is None:
        return None
    evidence = Evidence(source="pdf", page=extracted.page, quote=extracted.quote)
    return Field(value=extracted.value, evidence=evidence, confidence=extracted.confidence)


def _vat_category(rate: Field[Decimal] | None) -> Field[str] | None:
    """Only a positive rate implies category S; a 0 % rate could be Z, E or AE, so it stays open."""
    if rate is None or rate.value <= 0:
        return None
    return Field(value="S", evidence=rate.evidence, confidence=rate.confidence)


def _address(address: ExtractedAddress | None) -> Field[Address] | None:
    if address is None:
        return None
    parts = [part for part in (address.street, address.postcode, address.city) if part]
    if not parts:
        return None
    value = Address(
        street=address.street.value if address.street else None,
        postcode=address.postcode.value if address.postcode else None,
        city=address.city.value if address.city else None,
    )
    evidence = Evidence(source="pdf", page=parts[0].page, quote=parts[0].quote)
    return Field(value=value, evidence=evidence, confidence=min(part.confidence for part in parts))


def to_invoice(extracted: ExtractedInvoice, format: Literal["pdf", "scan"]) -> Invoice:
    lines = []
    for line in extracted.lines:
        rate = _field(line.vat_rate)
        lines.append(
            LineItem(
                item_name=_field(line.item_name),
                quantity=_field(line.quantity),
                price=_field(line.unit_price),
                net_amount=_field(line.net_amount),
                vat_rate=rate,
                vat_category=_vat_category(rate),
            )
        )
    breakdown = []
    for part in extracted.vat_breakdown:
        rate = _field(part.rate)
        breakdown.append(
            VatBreakdown(
                taxable_amount=_field(part.taxable_amount),
                tax_amount=_field(part.tax_amount),
                rate=rate,
                category=_vat_category(rate),
            )
        )
    return Invoice(
        format=format,
        number=_field(extracted.number),
        issue_date=_field(extracted.issue_date),
        currency=_field(extracted.currency),
        due_date=_field(extracted.due_date),
        po_number=_field(extracted.po_number),
        seller_name=_field(extracted.seller_name),
        seller_vat_id=_field(extracted.seller_vat_id),
        seller_address=_address(extracted.seller_address),
        buyer_name=_field(extracted.buyer_name),
        buyer_address=_address(extracted.buyer_address),
        delivery_date=_field(extracted.delivery_date),
        iban=_field(extracted.iban),
        line_net_total=_field(extracted.line_net_total),
        tax_exclusive_total=_field(extracted.tax_exclusive_total),
        vat_total=_field(extracted.vat_total),
        gross_total=_field(extracted.gross_total),
        amount_due=_field(extracted.amount_due),
        lines=lines,
        vat_breakdown=breakdown,
    )


def _ask(prompt: str, complete: Callable[[str], str]) -> ExtractedInvoice:
    reply = complete(prompt)
    try:
        return ExtractedInvoice.model_validate_json(reply)
    except ValidationError as error:
        retry = (
            f"{prompt}\n\nYour previous answer:\n{reply}\n\n"
            f"It does not match the schema:\n{error}\nAnswer again with corrected JSON only."
        )
        return ExtractedInvoice.model_validate_json(complete(retry))


def extract_invoice(
    pages: list[str], format: Literal["pdf", "scan"], complete: Callable[[str], str]
) -> tuple[Invoice, list[str]]:
    """Ask the model, check each quote against its page, return the invoice and reason codes."""
    extracted = _ask(build_prompt(pages), complete)
    reasons = check_quotes(extracted, pages)
    return to_invoice(extracted, format), reasons
