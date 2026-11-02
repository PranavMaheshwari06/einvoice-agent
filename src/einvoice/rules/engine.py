"""Runs every check in a fixed order and turns the results into AUTO_BOOK or REVIEW."""

from einvoice.models import STRUCTURED_FORMATS, CheckResult, Decision, Invoice, RuleContext
from einvoice.rules import arithmetic, duplicates, fraud, matching, ustg14

CHECKS = (
    ustg14.check_mandatory_fields,
    ustg14.check_vat_id,
    ustg14.check_vat_rates,
    arithmetic.check_arithmetic,
    duplicates.check_duplicates,
    matching.check_po_match,
    fraud.check_vendor,
)
REQUIRED_EXTRACTED_FIELDS = (
    "number",
    "issue_date",
    "seller_name",
    "tax_exclusive_total",
    "vat_total",
    "gross_total",
)


def _evidence_reasons(invoice: Invoice, context: RuleContext) -> list[str]:
    """Structured input needs a KoSIT accept; extracted input needs its quotes and confidence."""
    if invoice.format in STRUCTURED_FORMATS:
        if context.validation is None:
            return ["NOT_VALIDATED"]
        return [] if context.validation.accepted else ["KOSIT_REJECTED"]
    reasons = list(context.extraction_reasons)
    for name in REQUIRED_EXTRACTED_FIELDS:
        field = getattr(invoice, name)
        if field is None or field.confidence < context.extract_threshold:
            return reasons + ["LOW_EXTRACTION_CONFIDENCE"]
    return reasons


def decide(invoice: Invoice, context: RuleContext, results: list[CheckResult]) -> Decision:
    """Check results plus the evidence and GL gates give the decision; no check runs again."""
    reasons = [result.code for result in results if not result.passed]
    reasons += _evidence_reasons(invoice, context)
    if context.gl_probability is None or context.gl_probability < context.gl_threshold:
        reasons.append("LOW_GL_CONFIDENCE")
    reasons = list(dict.fromkeys(reasons))
    return Decision(kind="REVIEW" if reasons else "AUTO_BOOK", reasons=reasons)


def run(invoice: Invoice, context: RuleContext) -> tuple[list[CheckResult], Decision]:
    results = [result for check in CHECKS for result in check(invoice, context)]
    return results, decide(invoice, context, results)
