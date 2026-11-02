from dataclasses import replace

from conftest import xml_value
from einvoice.models import Evidence, Field, RuleViolation, ValidationResult
from einvoice.rules.engine import REQUIRED_EXTRACTED_FIELDS, run


def as_extracted(invoice, confidence: float):
    """The same invoice as if an LLM had read it from a plain PDF."""
    updates = {"format": "pdf"}
    for name in REQUIRED_EXTRACTED_FIELDS:
        field = getattr(invoice, name)
        evidence = Evidence(source="pdf", page=1, quote=str(field.value))
        updates[name] = Field(value=field.value, evidence=evidence, confidence=confidence)
    return invoice.model_copy(update=updates)


def test_clean_structured_invoice_is_auto_booked(ready_invoice, ready_context):
    results, decision = run(ready_invoice, ready_context)
    assert decision.kind == "AUTO_BOOK"
    assert decision.reasons == []
    assert all(result.passed for result in results)


def test_unvalidated_structured_invoice_goes_to_review(ready_invoice, ready_context):
    _, decision = run(ready_invoice, replace(ready_context, validation=None))
    assert (decision.kind, decision.reasons) == ("REVIEW", ["NOT_VALIDATED"])


def test_kosit_rejection_goes_to_review(ready_invoice, ready_context):
    violation = RuleViolation(rule_id="BR-DE-15", level="error", message="[BR-DE-15] ...")
    context = replace(
        ready_context, validation=ValidationResult(accepted=False, errors=[violation])
    )
    _, decision = run(ready_invoice, context)
    assert decision.reasons == ["KOSIT_REJECTED"]


def test_uncertain_gl_account_goes_to_review(ready_invoice, ready_context):
    _, decision = run(ready_invoice, replace(ready_context, gl_probability=0.89))
    assert decision.reasons == ["LOW_GL_CONFIDENCE"]
    _, decision = run(ready_invoice, replace(ready_context, gl_probability=None))
    assert decision.reasons == ["LOW_GL_CONFIDENCE"]


def test_extracted_invoice_needs_confident_required_fields(ready_invoice, ready_context):
    _, decision = run(as_extracted(ready_invoice, 0.95), ready_context)
    assert decision.kind == "AUTO_BOOK"
    _, decision = run(as_extracted(ready_invoice, 0.5), ready_context)
    assert decision.reasons == ["LOW_EXTRACTION_CONFIDENCE"]


def test_every_failing_check_is_a_reason_once(ready_invoice, ready_context):
    invoice = ready_invoice.model_copy(
        update={"iban": xml_value("DE02120300000000202051"), "delivery_date": None}
    )
    _, decision = run(invoice, replace(ready_context, validation=None))
    assert decision.kind == "REVIEW"
    assert decision.reasons == ["MISSING_DELIVERY_DATE", "BANK_DETAILS_CHANGED", "NOT_VALIDATED"]


def test_extraction_reasons_send_an_extracted_invoice_to_review(ready_invoice, ready_context):
    extracted = as_extracted(ready_invoice, confidence=1.0)
    context = replace(ready_context, extraction_reasons=["EVIDENCE_NOT_FOUND"])
    _, decision = run(extracted, context)
    assert decision.reasons == ["EVIDENCE_NOT_FOUND"]
