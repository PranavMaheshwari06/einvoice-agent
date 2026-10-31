import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from einvoice.extraction.llm_extract import build_prompt, extract_invoice
from einvoice.extraction.text import page_texts
from einvoice.models import RuleContext
from einvoice.rules import arithmetic, engine

FIXTURES = Path(__file__).parents[2] / "fixtures"
REPLAY_CASES = sorted((FIXTURES / "replay").glob("extract_*.json"))


def load_case(path: Path) -> tuple[list[str], dict]:
    case = json.loads(path.read_text(encoding="utf-8"))
    return page_texts((FIXTURES / case["pdf"]).read_bytes()), case["content"]


def replay(content: dict):
    return lambda _prompt: json.dumps(content)


@pytest.mark.parametrize("path", REPLAY_CASES, ids=lambda path: path.stem)
def test_replayed_extraction_is_valid_and_every_quote_is_found(path):
    pages, content = load_case(path)

    invoice, reasons = extract_invoice(pages, "pdf", replay(content))

    assert reasons == []
    assert invoice.format == "pdf"
    assert invoice.number.value == content["number"]["value"]
    assert invoice.gross_total.value == Decimal(content["gross_total"]["value"])
    assert invoice.gross_total.evidence.source == "pdf"
    assert invoice.gross_total.evidence.quote == content["gross_total"]["quote"]
    assert len(invoice.lines) == len(content["lines"])


def test_three_replay_cases_exist():
    assert len(REPLAY_CASES) == 3


def test_planted_wrong_quote_sets_confidence_to_zero():
    pages, content = load_case(FIXTURES / "replay" / "extract_synth_inv_00001.json")
    content["gross_total"]["quote"] = "Gesamtbetrag: 999,99"

    invoice, reasons = extract_invoice(pages, "pdf", replay(content))

    assert reasons == ["EVIDENCE_NOT_FOUND"]
    assert invoice.gross_total.confidence == 0.0
    assert invoice.number.confidence == 0.98


def test_quote_on_the_wrong_page_is_not_found():
    pages, content = load_case(FIXTURES / "replay" / "extract_zugferd_einfach.json")
    content["gross_total"]["page"] = 1

    invoice, reasons = extract_invoice(pages, "pdf", replay(content))

    assert reasons == ["EVIDENCE_NOT_FOUND"]
    assert invoice.gross_total.confidence == 0.0


def test_page_number_beyond_the_document_is_not_found():
    pages, content = load_case(FIXTURES / "replay" / "extract_synth_inv_00001.json")
    content["number"]["page"] = 5

    invoice, reasons = extract_invoice(pages, "pdf", replay(content))

    assert reasons == ["EVIDENCE_NOT_FOUND"]
    assert invoice.number.confidence == 0.0


def test_quote_may_differ_from_the_page_in_line_breaks():
    content = {
        "gross_total": {
            "value": "140.99",
            "page": 1,
            "quote": "Gesamtbetrag: 140,99",
            "confidence": 0.9,
        }
    }

    invoice, reasons = extract_invoice(["Gesamtbetrag:\n140,99"], "pdf", replay(content))

    assert reasons == []
    assert invoice.gross_total.confidence == 0.9


def test_invalid_reply_is_retried_once_with_the_error():
    pages, content = load_case(FIXTURES / "replay" / "extract_synth_inv_00001.json")
    prompts = []

    def complete(prompt: str) -> str:
        prompts.append(prompt)
        return "not json" if len(prompts) == 1 else json.dumps(content)

    invoice, reasons = extract_invoice(pages, "pdf", complete)

    assert len(prompts) == 2
    assert "does not match the schema" in prompts[1]
    assert "not json" in prompts[1]
    assert invoice.number.value == "2975-00001"


def test_second_invalid_reply_raises():
    with pytest.raises(ValidationError):
        extract_invoice(["text"], "pdf", lambda _prompt: "{}}")


def test_amount_that_is_not_a_number_is_rejected():
    content = {"gross_total": {"value": "abc", "page": 1, "quote": "x", "confidence": 0.9}}

    with pytest.raises(ValidationError):
        extract_invoice(["x"], "pdf", replay(content))


def test_prompt_marks_pages_and_embeds_the_schema():
    prompt = build_prompt(["first page", "second page"])

    assert "[Seite 1]\nfirst page" in prompt
    assert "[Seite 2]\nsecond page" in prompt
    assert '"gross_total"' in prompt
    assert "{pages}" not in prompt and "{schema}" not in prompt


def test_extracted_invoice_passes_the_arithmetic_rules():
    pages, content = load_case(FIXTURES / "replay" / "extract_synth_inv_00001.json")

    invoice, _ = extract_invoice(pages, "pdf", replay(content))

    results = arithmetic.check_arithmetic(invoice, RuleContext())
    assert [result.code for result in results if not result.passed] == []


def test_positive_vat_rate_gets_category_s():
    pages, content = load_case(FIXTURES / "replay" / "extract_synth_inv_00001.json")

    invoice, _ = extract_invoice(pages, "pdf", replay(content))

    assert invoice.vat_breakdown[0].category.value == "S"


def test_address_confidence_is_the_lowest_of_its_parts():
    pages, content = load_case(FIXTURES / "replay" / "extract_mustang_rechnung.json")

    invoice, _ = extract_invoice(pages, "pdf", replay(content))

    assert invoice.buyer_address.value.city == "Spielkreis"
    assert invoice.buyer_address.confidence == 0.7


def test_unsupported_quote_sends_the_invoice_to_review():
    pages, content = load_case(FIXTURES / "replay" / "extract_synth_inv_00001.json")
    content = copy.deepcopy(content)
    content["issue_date"]["quote"] = "Datum: 31.12.99"
    invoice, _ = extract_invoice(pages, "pdf", replay(content))

    _, decision = engine.run(invoice, RuleContext(gl_probability=0.99))

    assert decision.kind == "REVIEW"
    assert "LOW_EXTRACTION_CONFIDENCE" in decision.reasons
