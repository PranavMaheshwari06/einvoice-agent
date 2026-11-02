"""Seeded generator for vendors, purchase orders, goods receipts and labelled invoices."""

import json
import logging
import math
import random
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import NamedTuple

from drafthorse.pdf import attach_xml
from faker import Faker

from einvoice.convert import invoice_to_cii
from einvoice.models import (
    Address,
    Evidence,
    Field,
    Format,
    Invoice,
    LineItem,
    PoLine,
    PriorInvoice,
    PurchaseOrder,
    VatBreakdown,
    Vendor,
)
from einvoice.rules.legal import SMALL_AMOUNT_LIMIT
from einvoice.rules.ustg14 import is_valid_german_vat_id
from einvoice.synth import render
from einvoice.synth.catalogue import CATEGORIES

log = logging.getLogger(__name__)

START = date(2025, 1, 1)
VENDOR_COUNT = 40
SPLITS = ("train",) * 24 + ("validation",) * 6 + ("test",) * 10
FORMAT_WEIGHTS = {"cii": 25, "ubl": 15, "zugferd_pdf": 30, "pdf": 25, "scan": 5}
FILE_SUFFIX = {"cii": "xml", "ubl": "xml", "zugferd_pdf": "pdf", "pdf": "pdf", "scan": "png"}
PROBLEM_SHARE = 0.2
# Problem -> the rule codes that must fail. KoSIT and GL confidence are not part of the label.
PROBLEMS = {
    "missing_vat_id": ["MISSING_VAT_ID"],
    "vat_sum_off": ["VAT_TOTAL_MISMATCH"],
    "duplicate": ["DUPLICATE_INVOICE"],
    "price_above_po": ["PRICE_OUTSIDE_TOLERANCE"],
    "quantity_above_receipt": ["QUANTITY_ABOVE_RECEIPT"],
    "changed_iban": ["BANK_DETAILS_CHANGED"],
    "unknown_vendor": ["UNKNOWN_VENDOR", "PO_NOT_FOUND"],
    "wrong_vat_rate": ["INVALID_VAT_RATE"],
    "missing_delivery_date": ["MISSING_DELIVERY_DATE"],
}
# §33 UStDV: invoices up to the small-amount limit need neither VAT id nor delivery date.
NEEDS_LARGE_AMOUNT = {"missing_vat_id", "missing_delivery_date"}
# 16 % is not a German rate, so the VAT-rate rule can flag it without knowing the item.
WRONG_VAT_RATE = Decimal("16")
BUYER_NAME = "Beispiel Einkauf GmbH"
BUYER_ADDRESS = Address(street="Musterstraße 1", city="Berlin", postcode="10115", country="DE")
BUYER_REFERENCE = "04011000-1234512345-35"


@dataclass(frozen=True)
class VendorItem:
    name: str
    unit: str
    list_price: Decimal
    vat_rate: Decimal
    account: str
    max_quantity: int


@dataclass
class VendorProfile:
    vendor: Vendor
    address: Address
    payment_days: int
    items: list[VendorItem]
    split: str
    invoice_count: int = 0


@dataclass(frozen=True)
class DraftLine:
    item: VendorItem
    quantity: Decimal
    unit_price: Decimal
    vat_rate: Decimal


@dataclass(frozen=True)
class Draft:
    """What one invoice says, before it is rendered; problems are applied to it."""

    profile: VendorProfile
    number: str
    issue_date: date
    delivery_date: date
    po_number: str
    lines: tuple[DraftLine, ...]
    iban: str

    @property
    def due_date(self) -> date:
        return self.issue_date + timedelta(days=self.profile.payment_days)


class Amounts(NamedTuple):
    nets: list[Decimal]
    base_by_rate: dict[Decimal, Decimal]
    vat_by_rate: dict[Decimal, Decimal]
    net_total: Decimal
    vat_total: Decimal

    @property
    def gross_total(self) -> Decimal:
        return self.net_total + self.vat_total


def _cents(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _amounts(lines: tuple[DraftLine, ...]) -> Amounts:
    nets = [_cents(line.quantity * line.unit_price) for line in lines]
    base_by_rate: dict[Decimal, Decimal] = {}
    for line, net in zip(lines, nets, strict=True):
        base_by_rate[line.vat_rate] = base_by_rate.get(line.vat_rate, Decimal(0)) + net
    vat_by_rate = {rate: _cents(base * rate / 100) for rate, base in base_by_rate.items()}
    return Amounts(nets, base_by_rate, vat_by_rate, sum(nets), sum(vat_by_rate.values()))


def _vat_id(rng: random.Random) -> str:
    while True:
        candidate = f"DE{rng.randrange(10**8, 10**9)}"
        if is_valid_german_vat_id(candidate):
            return candidate


def _vendor_profile(rng: random.Random, fake: Faker, names: set[str], split: str) -> VendorProfile:
    name = fake.company()
    while name in names:
        name = fake.company()
    names.add(name)
    pool = [item for category in rng.sample(list(CATEGORIES), 2) for item in CATEGORIES[category]]
    items = []
    for item in rng.sample(pool, min(len(pool), rng.randint(4, 8))):
        low, high = item.price_range
        use_alt = item.alt_account is not None and rng.random() < 0.4
        items.append(
            VendorItem(
                name=rng.choice(item.names),
                unit=item.unit,
                list_price=Decimal(rng.randrange(low * 100, high * 100)) / 100,
                vat_rate=item.vat_rate,
                account=item.alt_account if use_alt else item.account,
                max_quantity=item.max_quantity,
            )
        )
    address = Address(
        street=fake.street_address(), city=fake.city(), postcode=fake.postcode(), country="DE"
    )
    vendor = Vendor(vat_id=_vat_id(rng), name=name, iban=fake.iban())
    return VendorProfile(vendor, address, rng.choice([14, 30, 30, 45]), items, split)


def _next_number(profile: VendorProfile) -> str:
    profile.invoice_count += 1
    return f"{profile.vendor.vat_id[-4:]}-{profile.invoice_count:05d}"


def _fresh_draft(
    rng: random.Random,
    profile: VendorProfile,
    issue_date: date,
    po_number: str,
    recent: dict[str, list[tuple[Decimal, date]]],
    large: bool,
) -> Draft:
    """A clean invoice; lines are redrawn until it is not a same-gross near-duplicate of another."""
    earlier = recent.get(profile.vendor.vat_id, [])
    while True:
        count = rng.choices([1, 2, 3, 4], weights=[35, 35, 20, 10])[0]
        lines = tuple(
            DraftLine(
                item, Decimal(rng.randint(1, item.max_quantity)), item.list_price, item.vat_rate
            )
            for item in rng.sample(profile.items, min(count, len(profile.items)))
        )
        if large and _amounts(lines).gross_total <= SMALL_AMOUNT_LIMIT:
            first = lines[0]
            unit_gross = first.unit_price * (1 + first.vat_rate / 100)
            quantity = Decimal(math.ceil(SMALL_AMOUNT_LIMIT / unit_gross) + 1)
            lines = (replace(first, quantity=quantity),) + lines[1:]
        gross = _amounts(lines).gross_total
        if all(gross != other or abs((day - issue_date).days) > 7 for other, day in earlier):
            break
    return Draft(
        profile=profile,
        number=_next_number(profile),
        issue_date=issue_date,
        delivery_date=issue_date - timedelta(days=rng.randint(1, 14)),
        po_number=po_number,
        lines=lines,
        iban=profile.vendor.iban,
    )


def _duplicate_draft(rng: random.Random, original: Draft) -> Draft:
    """The same invoice again: same number, or a new number with the same amount within 5 days."""
    if rng.random() < 0.5:
        return original
    shifted = original.issue_date + timedelta(days=rng.randint(0, 5))
    return replace(original, number=_next_number(original.profile), issue_date=shifted)


def _apply_problem(rng: random.Random, fake: Faker, draft: Draft, problem: str | None) -> Draft:
    if problem == "price_above_po":
        position = rng.randrange(len(draft.lines))
        line = draft.lines[position]
        higher = _cents(line.unit_price * Decimal(rng.randint(106, 125)) / 100)
        changed = replace(line, unit_price=higher)
        lines = draft.lines[:position] + (changed,) + draft.lines[position + 1 :]
        return replace(draft, lines=lines)
    if problem == "wrong_vat_rate":
        wrong = tuple(replace(line, vat_rate=WRONG_VAT_RATE) for line in draft.lines)
        return replace(draft, lines=wrong)
    if problem == "changed_iban":
        return replace(draft, iban=fake.iban())
    return draft


def _field(value, bt: str) -> Field:
    return Field(value=value, evidence=Evidence(source="xml", bt=bt))


def _build_invoice(
    draft: Draft, invoice_format: Format, problem: str | None, vat_offset: Decimal
) -> Invoice:
    amounts = _amounts(draft.lines)
    vat_total = amounts.vat_total + vat_offset
    gross = amounts.net_total + vat_total
    vendor = draft.profile.vendor
    lines = [
        LineItem(
            line_id=_field(str(position), "BT-126"),
            quantity=_field(line.quantity, "BT-129"),
            unit=_field(line.item.unit, "BT-130"),
            net_amount=_field(net, "BT-131"),
            po_line_ref=_field(str(position), "BT-132"),
            price=_field(line.unit_price, "BT-146"),
            vat_category=_field("S", "BT-151"),
            vat_rate=_field(line.vat_rate, "BT-152"),
            item_name=_field(line.item.name, "BT-153"),
        )
        for position, (line, net) in enumerate(zip(draft.lines, amounts.nets, strict=True), 1)
    ]
    breakdown = [
        VatBreakdown(
            taxable_amount=_field(base, "BT-116"),
            tax_amount=_field(amounts.vat_by_rate[rate], "BT-117"),
            category=_field("S", "BT-118"),
            rate=_field(rate, "BT-119"),
        )
        for rate, base in amounts.base_by_rate.items()
    ]
    return Invoice(
        format=invoice_format,
        number=_field(draft.number, "BT-1"),
        issue_date=_field(draft.issue_date, "BT-2"),
        type_code=_field("380", "BT-3"),
        currency=_field("EUR", "BT-5"),
        due_date=_field(draft.due_date, "BT-9"),
        buyer_reference=_field(BUYER_REFERENCE, "BT-10"),
        po_number=_field(draft.po_number, "BT-13"),
        seller_name=_field(vendor.name, "BT-27"),
        seller_vat_id=None if problem == "missing_vat_id" else _field(vendor.vat_id, "BT-31"),
        seller_address=_field(draft.profile.address, "BG-5"),
        buyer_name=_field(BUYER_NAME, "BT-44"),
        buyer_address=_field(BUYER_ADDRESS, "BG-8"),
        delivery_date=(
            None if problem == "missing_delivery_date" else _field(draft.delivery_date, "BT-72")
        ),
        iban=_field(draft.iban, "BT-84"),
        line_net_total=_field(amounts.net_total, "BT-106"),
        tax_exclusive_total=_field(amounts.net_total, "BT-109"),
        vat_total=_field(vat_total, "BT-110"),
        gross_total=_field(gross, "BT-112"),
        amount_due=_field(gross, "BT-115"),
        lines=lines,
        vat_breakdown=breakdown,
    )


def _purchase_order(draft: Draft, with_receipts: bool, short_line: int | None) -> dict:
    """The order as the buyer placed it: list prices, and a receipt per line unless 2-way only."""
    lines = []
    for position, line in enumerate(draft.lines):
        received = line.quantity - 1 if position == short_line else line.quantity
        receipt = {"quantity": str(received), "date": draft.delivery_date.isoformat()}
        lines.append(
            {
                "line_id": str(position + 1),
                "description": line.item.name,
                "quantity": str(line.quantity),
                "unit_price": str(line.item.list_price),
                "receipt": receipt if with_receipts else None,
            }
        )
    return {
        "po_number": draft.po_number,
        "vendor_vat_id": draft.profile.vendor.vat_id,
        "lines": lines,
    }


def _write_invoice(rng: random.Random, invoice: Invoice, path: Path) -> None:
    if invoice.format == "cii":
        content = invoice_to_cii(invoice)
    elif invoice.format == "ubl":
        content = render.invoice_to_ubl(invoice)
    elif invoice.format == "zugferd_pdf":
        content = attach_xml(render.render_pdf(invoice, 0), invoice_to_cii(invoice))
    else:
        pdf = render.render_pdf(invoice, rng.randrange(len(render.LAYOUTS)))
        content = render.render_scan(pdf, rng) if invoice.format == "scan" else pdf
    path.write_bytes(content)


def _gold_record(
    index: int, file_name: str, invoice_format: Format, draft: Draft, problem: str | None
) -> dict:
    amounts = _amounts(draft.lines)
    # The booking account of an invoice is the one of its largest line.
    largest = max(range(len(draft.lines)), key=lambda position: amounts.nets[position])
    return {
        "id": f"inv_{index:05d}",
        "file": file_name,
        "format": invoice_format,
        "split": draft.profile.split,
        "vendor_vat_id": draft.profile.vendor.vat_id,
        "vendor_name": draft.profile.vendor.name,
        "number": draft.number,
        "issue_date": draft.issue_date.isoformat(),
        "due_date": draft.due_date.isoformat(),
        "po_number": draft.po_number,
        "net_total": str(amounts.net_total),
        "vat_total": str(amounts.vat_total),
        "gross_total": str(amounts.gross_total),
        "gl_account": draft.lines[largest].item.account,
        "lines": [
            {
                "item_name": line.item.name,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "net_amount": str(net),
                "vat_rate": str(line.vat_rate),
                "gl_account": line.item.account,
            }
            for line, net in zip(draft.lines, amounts.nets, strict=True)
        ],
        "problem": problem,
        "must_review": problem is not None,
        "reasons": PROBLEMS.get(problem, []),
    }


def generate(seed: int, out: Path, count: int = 2000) -> None:
    """Write vendors.json, purchase_orders.json, gold.jsonl and invoices/ to `out`."""
    rng = random.Random(seed)
    fake = Faker("de_DE")
    fake.seed_instance(seed)
    names: set[str] = set()
    splits = list(SPLITS)
    rng.shuffle(splits)
    profiles = [_vendor_profile(rng, fake, names, splits[i]) for i in range(VENDOR_COUNT)]
    (out / "invoices").mkdir(parents=True, exist_ok=True)

    orders: list[dict] = []
    gold: list[dict] = []
    recent: dict[str, list[tuple[Decimal, date]]] = {}
    clean: list[Draft] = []
    for index in range(1, count + 1):
        issue_date = START + timedelta(days=index * 365 // count + rng.randrange(3))
        problem = rng.choice(list(PROBLEMS)) if rng.random() < PROBLEM_SHARE else None
        if problem == "duplicate" and not clean:
            problem = None
        formats, weights = list(FORMAT_WEIGHTS), list(FORMAT_WEIGHTS.values())
        invoice_format = rng.choices(formats, weights=weights)[0]

        if problem == "duplicate":
            draft = _duplicate_draft(rng, rng.choice(clean))
        else:
            if problem == "unknown_vendor":
                profile = _vendor_profile(rng, fake, names, rng.choice(SPLITS))
                po_number = f"PO-{rng.randrange(90000, 99999)}"
            else:
                profile = rng.choice(profiles)
                po_number = f"PO-{len(orders) + 1:05d}"
            large = problem in NEEDS_LARGE_AMOUNT
            draft = _fresh_draft(rng, profile, issue_date, po_number, recent, large)
            # The order is placed at list prices before problems change what the invoice says.
            if problem != "unknown_vendor":
                with_receipts = problem == "quantity_above_receipt" or rng.random() < 0.85
                short_line = None
                if problem == "quantity_above_receipt":
                    short_line = rng.randrange(len(draft.lines))
                orders.append(_purchase_order(draft, with_receipts, short_line))
            draft = _apply_problem(rng, fake, draft, problem)

        vat_offset = Decimal(rng.randint(5, 200)) / 100 if problem == "vat_sum_off" else Decimal(0)
        invoice = _build_invoice(draft, invoice_format, problem, vat_offset)
        file_name = f"invoices/inv_{index:05d}.{FILE_SUFFIX[invoice_format]}"
        _write_invoice(rng, invoice, out / file_name)
        gold.append(_gold_record(index, file_name, invoice_format, draft, problem))
        # Both grosses count: a vat_sum_off invoice says one amount and has another as gold.
        grosses = {invoice.gross_total.value, _amounts(draft.lines).gross_total}
        for gross in grosses:
            recent.setdefault(draft.profile.vendor.vat_id, []).append((gross, draft.issue_date))
        if problem is None:
            clean.append(draft)

    vendors = [profile.vendor.model_dump() for profile in profiles]
    for name, content in (("vendors.json", vendors), ("purchase_orders.json", orders)):
        (out / name).write_text(json.dumps(content, ensure_ascii=False, indent=1), encoding="utf-8")
    with (out / "gold.jsonl").open("w", encoding="utf-8") as file:
        for record in gold:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    log.info("wrote %d invoices to %s", count, out)


def read_gold(directory: Path) -> list[dict]:
    lines = (directory / "gold.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def prior_invoice(record: dict) -> PriorInvoice:
    """A gold record as the ledger holds it once received; a missing VAT id stays missing."""
    return PriorInvoice(
        seller_vat_id=None if record["problem"] == "missing_vat_id" else record["vendor_vat_id"],
        seller_name=record["vendor_name"],
        number=record["number"],
        gross_total=Decimal(record["gross_total"]),
        issue_date=date.fromisoformat(record["issue_date"]),
    )


def read_master_data(directory: Path) -> tuple[list[Vendor], list[PurchaseOrder]]:
    vendors = json.loads((directory / "vendors.json").read_text(encoding="utf-8"))
    orders = json.loads((directory / "purchase_orders.json").read_text(encoding="utf-8"))
    return (
        [Vendor(**vendor) for vendor in vendors],
        [
            PurchaseOrder(
                po_number=order["po_number"],
                vendor_vat_id=order["vendor_vat_id"],
                lines=[
                    PoLine(
                        line_id=line["line_id"],
                        description=line["description"],
                        quantity=Decimal(line["quantity"]),
                        unit_price=Decimal(line["unit_price"]),
                        received_quantity=(
                            None
                            if line["receipt"] is None
                            else Decimal(line["receipt"]["quantity"])
                        ),
                    )
                    for line in order["lines"]
                ],
            )
            for order in orders
        ],
    )
