from einvoice.models import CheckResult, Invoice, RuleContext


def _compact(iban: str) -> str:
    return iban.replace(" ", "").upper()


def check_vendor(invoice: Invoice, context: RuleContext) -> list[CheckResult]:
    """Unknown vendors and bank details that differ from the master record always go to review."""
    vendor = context.vendor
    if vendor is None:
        message = "seller is not in the vendor master data"
        return [CheckResult(code="UNKNOWN_VENDOR", passed=False, message=message)]
    known = CheckResult(code="UNKNOWN_VENDOR", passed=True, message=f"known vendor {vendor.name}")
    if invoice.iban is None:
        unchanged = CheckResult(
            code="BANK_DETAILS_CHANGED", passed=True, message="invoice names no IBAN"
        )
        return [known, unchanged]
    invoice_iban, master_iban = _compact(invoice.iban.value), _compact(vendor.iban)
    changed = invoice_iban != master_iban
    # Show only the last four characters; the full IBAN does not belong in logs or reason texts.
    message = (
        f"invoice IBAN ...{invoice_iban[-4:]} differs from master record ...{master_iban[-4:]}"
        if changed
        else "IBAN matches the master record"
    )
    return [known, CheckResult(code="BANK_DETAILS_CHANGED", passed=not changed, message=message)]
