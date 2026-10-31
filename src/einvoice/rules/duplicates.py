from datetime import timedelta

from einvoice.models import CheckResult, Invoice, RuleContext

DUPLICATE_WINDOW = timedelta(days=7)


def _compact(vat_id: str | None) -> str | None:
    return vat_id.replace(" ", "").upper() if vat_id else None


def check_duplicates(invoice: Invoice, context: RuleContext) -> list[CheckResult]:
    """Same seller VAT id + number, or same seller + gross amount with issue dates within 7 days."""
    vat_id = _compact(invoice.seller_vat_id.value if invoice.seller_vat_id else None)
    seller_name = invoice.seller_name.value.casefold() if invoice.seller_name else None
    number = invoice.number.value if invoice.number else None
    gross = invoice.gross_total.value if invoice.gross_total else None
    issue_date = invoice.issue_date.value if invoice.issue_date else None

    for prior in context.prior_invoices:
        same_vat_id = vat_id is not None and _compact(prior.seller_vat_id) == vat_id
        if same_vat_id and number is not None and prior.number == number:
            message = f"invoice {number} from {vat_id} was already received"
            return [CheckResult(code="DUPLICATE_INVOICE", passed=False, message=message)]
        same_seller = same_vat_id or (
            seller_name is not None and prior.seller_name.casefold() == seller_name
        )
        if (
            same_seller
            and gross is not None
            and gross == prior.gross_total
            and issue_date is not None
            and abs(issue_date - prior.issue_date) <= DUPLICATE_WINDOW
        ):
            message = (
                f"invoice {prior.number} from the same seller has the same gross amount {gross} "
                f"and was issued on {prior.issue_date}"
            )
            return [CheckResult(code="DUPLICATE_INVOICE", passed=False, message=message)]
    return [
        CheckResult(code="DUPLICATE_INVOICE", passed=True, message="no earlier duplicate found")
    ]
