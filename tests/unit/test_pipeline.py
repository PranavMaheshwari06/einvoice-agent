import json

import pytest

from conftest import FIXTURES, MUSTANG_PDF
from einvoice.models import RuleContext, RuleViolation, ValidationResult
from einvoice.parsing.detect import detect_format
from einvoice.pipeline import process

ACCEPT = ValidationResult(accepted=True, errors=[])
REPLAY = json.loads((FIXTURES / "replay" / "extract_synth_inv_00001.json").read_text())


def no_model(_prompt: str) -> str:
    raise AssertionError("structured input must not reach the language model")


def no_validator(_xml: bytes) -> ValidationResult:
    raise AssertionError("extracted input must not reach KoSIT")


def test_zugferd_sends_the_embedded_xml_to_kosit(ready_context):
    seen = []

    def validate(xml: bytes) -> ValidationResult:
        seen.append(xml)
        return ACCEPT

    outcome = process(
        MUSTANG_PDF.read_bytes(),
        lambda _invoice: ready_context,
        validate,
        no_model,
        lambda _invoice: ("4930", 0.99),
    )
    assert detect_format(seen[0]) == "cii"
    assert outcome.invoice.format == "zugferd_pdf"
    assert outcome.context.validation == ACCEPT
    assert outcome.context.gl_probability == 0.99
    assert outcome.gl_account == "4930"
    assert "LOW_GL_CONFIDENCE" not in outcome.decision.reasons


def test_kosit_reject_and_missing_suggestion_send_to_review():
    reject = ValidationResult(
        accepted=False,
        errors=[RuleViolation(rule_id="BR-DE-15", level="error", message="no buyer reference")],
    )
    content = (FIXTURES / "xrechnung" / "01.01a-INVOICE_ubl.xml").read_bytes()
    outcome = process(
        content, lambda _invoice: RuleContext(), lambda _xml: reject, no_model, lambda _i: None
    )
    assert outcome.decision.kind == "REVIEW"
    assert {"KOSIT_REJECTED", "LOW_GL_CONFIDENCE"} <= set(outcome.decision.reasons)
    assert outcome.gl_account is None


def test_plain_pdf_goes_through_extraction_not_kosit():
    content = (FIXTURES / REPLAY["pdf"]).read_bytes()
    outcome = process(
        content,
        lambda _invoice: RuleContext(),
        no_validator,
        lambda _prompt: json.dumps(REPLAY["content"]),
        lambda _invoice: ("4930", 0.99),
    )
    assert outcome.invoice.format == "pdf"
    assert outcome.invoice.number.value == REPLAY["content"]["number"]["value"]
    assert outcome.context.validation is None


def test_planted_wrong_quote_adds_the_extraction_reason():
    content = (FIXTURES / REPLAY["pdf"]).read_bytes()
    planted = json.loads(json.dumps(REPLAY["content"]))
    planted["number"]["quote"] = "nicht auf der Seite"
    outcome = process(
        content,
        lambda _invoice: RuleContext(),
        no_validator,
        lambda _prompt: json.dumps(planted),
        lambda _invoice: ("4930", 0.99),
    )
    assert outcome.extraction_reasons == ["EVIDENCE_NOT_FOUND"]
    assert "EVIDENCE_NOT_FOUND" in outcome.decision.reasons


def test_unsupported_file_is_refused():
    with pytest.raises(ValueError, match="unsupported"):
        process(b"plain text", RuleContext, no_validator, no_model, lambda _i: None)
