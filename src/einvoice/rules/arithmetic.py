"""Arithmetic of lines, VAT breakdown and document totals (EN 16931 BR-CO rules, in cents)."""

from decimal import ROUND_HALF_UP, Decimal

from einvoice.models import CheckResult, Field, Invoice, LineItem, RuleContext

CENT = Decimal("0.01")
TOLERANCE = Decimal("0.01")
ZERO = Decimal("0")


def _cents(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _or_zero(field: Field[Decimal] | None) -> Decimal:
    return field.value if field is not None else ZERO


def _expected_line_net(line: LineItem) -> Decimal | None:
    if line.quantity is None or line.price is None:
        return None
    base_quantity = line.price_base_quantity.value if line.price_base_quantity else Decimal(1)
    gross = line.quantity.value * line.price.value / base_quantity
    adjustments = sum((f.value for f in line.charges), ZERO) - sum(
        (f.value for f in line.allowances), ZERO
    )
    return _cents(gross + adjustments)


def _result(code: str, problems: list[str], ok_message: str) -> CheckResult:
    return CheckResult(
        code=code, passed=not problems, message="; ".join(problems) if problems else ok_message
    )


def _line_nets(invoice: Invoice) -> CheckResult:
    problems = []
    for position, line in enumerate(invoice.lines, start=1):
        label = line.line_id.value if line.line_id else str(position)
        expected = _expected_line_net(line)
        if expected is None or line.net_amount is None:
            problems.append(f"line {label}: quantity, price or net amount missing")
        elif abs(expected - line.net_amount.value) > TOLERANCE:
            problems.append(
                f"line {label}: net {line.net_amount.value}, quantity x price {expected}"
            )
    return _result("LINE_NET_MISMATCH", problems, "every line net = quantity x price")


def _line_sum(invoice: Invoice) -> CheckResult:
    if invoice.line_net_total is None or any(line.net_amount is None for line in invoice.lines):
        return _result("LINE_SUM_MISMATCH", ["sum of line net amounts (BT-106) missing"], "")
    line_sum = sum((line.net_amount.value for line in invoice.lines), ZERO)
    stated = invoice.line_net_total.value
    problems = (
        [f"lines add up to {line_sum}, BT-106 is {stated}"]
        if abs(line_sum - stated) > TOLERANCE
        else []
    )
    return _result("LINE_SUM_MISMATCH", problems, "lines add up to BT-106")


def _vat_per_rate(invoice: Invoice) -> CheckResult:
    problems = []
    if not invoice.vat_breakdown:
        problems.append("no VAT breakdown")
    for part in invoice.vat_breakdown:
        if None in (part.taxable_amount, part.rate, part.tax_amount):
            problems.append("VAT breakdown entry without base, rate or amount")
            continue
        expected = _cents(part.taxable_amount.value * part.rate.value / 100)
        if abs(expected - part.tax_amount.value) > TOLERANCE:
            problems.append(
                f"{part.rate.value}% of {part.taxable_amount.value} is {expected}, "
                f"invoice says {part.tax_amount.value}"
            )
    return _result("VAT_RATE_MISMATCH", problems, "VAT per rate = rate x base")


def _vat_total(invoice: Invoice) -> CheckResult:
    if invoice.vat_total is None:
        return _result("VAT_TOTAL_MISMATCH", ["VAT total (BT-110) missing"], "")
    breakdown_sum = sum((_or_zero(part.tax_amount) for part in invoice.vat_breakdown), ZERO)
    stated = invoice.vat_total.value
    problems = (
        [f"VAT breakdown adds up to {breakdown_sum}, BT-110 is {stated}"]
        if abs(breakdown_sum - stated) > TOLERANCE
        else []
    )
    return _result("VAT_TOTAL_MISMATCH", problems, "VAT breakdown adds up to BT-110")


def _totals(invoice: Invoice) -> CheckResult:
    required = {
        "BT-106": invoice.line_net_total,
        "BT-109": invoice.tax_exclusive_total,
        "BT-112": invoice.gross_total,
        "BT-115": invoice.amount_due,
    }
    missing = [bt for bt, field in required.items() if field is None]
    if missing:
        return _result("TOTALS_MISMATCH", [f"missing {', '.join(missing)}"], "")
    net = invoice.tax_exclusive_total.value
    gross = invoice.gross_total.value
    due = invoice.amount_due.value
    expected_net = (
        invoice.line_net_total.value
        - _or_zero(invoice.allowance_total)
        + _or_zero(invoice.charge_total)
    )
    expected_gross = net + _or_zero(invoice.vat_total)
    expected_due = gross - _or_zero(invoice.prepaid_total) + _or_zero(invoice.rounding_amount)
    problems = [
        f"{name} is {stated}, expected {expected}"
        for name, stated, expected in (
            ("BT-109", net, expected_net),
            ("BT-112", gross, expected_gross),
            ("BT-115", due, expected_due),
        )
        if abs(stated - expected) > TOLERANCE
    ]
    return _result("TOTALS_MISMATCH", problems, "net, gross and amount due are consistent")


def check_arithmetic(invoice: Invoice, context: RuleContext) -> list[CheckResult]:
    return [
        _line_nets(invoice),
        _line_sum(invoice),
        _vat_per_rate(invoice),
        _vat_total(invoice),
        _totals(invoice),
    ]
