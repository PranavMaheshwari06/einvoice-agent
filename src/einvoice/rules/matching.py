"""2-way (invoice vs purchase order) and 3-way (plus goods receipt) matching per line."""

from decimal import Decimal

from einvoice.models import CheckResult, Invoice, LineItem, PoLine, PurchaseOrder, RuleContext

# Same values as data/rules/ap_policy.md: unit price may deviate at most 2 % from the PO.
PRICE_TOLERANCE = Decimal("0.02")


def _find_po_line(line: LineItem, order: PurchaseOrder) -> PoLine | None:
    for po_line in order.lines:
        if line.po_line_ref is not None and line.po_line_ref.value == po_line.line_id:
            return po_line
    if line.item_name is not None:
        for po_line in order.lines:
            if line.item_name.value.casefold() == po_line.description.casefold():
                return po_line
    return None


def _unit_price(line: LineItem) -> Decimal | None:
    if line.price is None:
        return None
    base_quantity = line.price_base_quantity.value if line.price_base_quantity else Decimal(1)
    return line.price.value / base_quantity


def _result(code: str, failing: list[str], problem: str, ok_message: str) -> CheckResult:
    if failing:
        return CheckResult(
            code=code, passed=False, message=f"{problem}: lines {', '.join(failing)}"
        )
    return CheckResult(code=code, passed=True, message=ok_message)


def check_po_match(invoice: Invoice, context: RuleContext) -> list[CheckResult]:
    if invoice.po_number is None:
        message = "invoice has no purchase order reference (BT-13)"
        return [CheckResult(code="NO_PO_REFERENCE", passed=False, message=message)]
    po_number = invoice.po_number.value
    order = context.purchase_order
    seller_vat_id = invoice.seller_vat_id.value.replace(" ", "") if invoice.seller_vat_id else None
    other_seller = (
        seller_vat_id is not None and order is not None and (order.vendor_vat_id != seller_vat_id)
    )
    if order is None or order.po_number != po_number or other_seller:
        message = f"purchase order {po_number} not found for this seller"
        return [CheckResult(code="PO_NOT_FOUND", passed=False, message=message)]

    unmatched, price_off, quantity_over = [], [], []
    for position, line in enumerate(invoice.lines, start=1):
        label = line.line_id.value if line.line_id else str(position)
        po_line = _find_po_line(line, order)
        if po_line is None:
            unmatched.append(label)
            continue
        unit_price = _unit_price(line)
        if unit_price is None or abs(unit_price - po_line.unit_price) > (
            po_line.unit_price * PRICE_TOLERANCE
        ):
            price_off.append(label)
        if po_line.received_quantity is not None and (
            line.quantity is None or line.quantity.value > po_line.received_quantity
        ):
            quantity_over.append(label)
    return [
        _result("PO_LINE_NOT_FOUND", unmatched, "no matching PO line", "every line is on the PO"),
        _result(
            "PRICE_OUTSIDE_TOLERANCE",
            price_off,
            f"unit price deviates more than {PRICE_TOLERANCE:%} from the PO",
            "prices within tolerance",
        ),
        _result(
            "QUANTITY_ABOVE_RECEIPT",
            quantity_over,
            "invoiced quantity above goods received",
            "quantities covered by goods receipts",
        ),
    ]
