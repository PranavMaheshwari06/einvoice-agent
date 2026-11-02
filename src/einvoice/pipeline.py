"""One invoice file in; the invoice, every check result and the decision out (SPEC 3.13)."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from io import BytesIO

from pypdf import PdfReader

from einvoice.extraction.llm_extract import extract_invoice
from einvoice.extraction.ocr import ocr_pages
from einvoice.extraction.text import page_texts
from einvoice.models import (
    STRUCTURED_FORMATS,
    CheckResult,
    Decision,
    Format,
    Invoice,
    RuleContext,
    ValidationResult,
)
from einvoice.parsing.cii import parse_cii
from einvoice.parsing.detect import detect_format
from einvoice.parsing.ubl import parse_ubl
from einvoice.parsing.zugferd import embedded_invoice_xml, parse_zugferd
from einvoice.rules import engine

Validate = Callable[[bytes], ValidationResult]
Complete = Callable[[str], str]
Suggest = Callable[[Invoice], tuple[str, float] | None]
ContextFor = Callable[[Invoice], RuleContext]


@dataclass(frozen=True)
class Outcome:
    invoice: Invoice
    context: RuleContext
    extraction_reasons: list[str]
    results: list[CheckResult]
    decision: Decision
    gl_account: str | None


def read_structured(content: bytes, file_format: Format) -> tuple[Invoice, bytes]:
    """The parsed invoice and the XML that KoSIT must see (the attachment for ZUGFeRD)."""
    if file_format == "zugferd_pdf":
        return parse_zugferd(content), embedded_invoice_xml(PdfReader(BytesIO(content)))
    parse = parse_ubl if file_format == "ubl" else parse_cii
    return parse(content), content


def decide(
    invoice: Invoice, context: RuleContext, extraction_reasons: list[str]
) -> tuple[list[CheckResult], Decision]:
    results, decision = engine.run(invoice, context)
    reasons = list(dict.fromkeys(decision.reasons + extraction_reasons))
    return results, Decision(kind="REVIEW" if reasons else "AUTO_BOOK", reasons=reasons)


def process(
    content: bytes,
    context_for: ContextFor,
    validate: Validate,
    complete: Complete | None,
    suggest: Suggest,
) -> Outcome:
    """Detect, parse or extract, validate, suggest the GL account and run the rules.

    `validate` is called for structured input only, `complete` for PDFs and scans only.
    """
    file_format = detect_format(content)
    validation = None
    extraction_reasons: list[str] = []
    if file_format in STRUCTURED_FORMATS:
        invoice, xml = read_structured(content, file_format)
        validation = validate(xml)
    else:
        pages = page_texts(content) if file_format == "pdf" else ocr_pages(content)
        invoice, extraction_reasons = extract_invoice(pages, file_format, complete)
    suggestion = suggest(invoice)
    context = replace(
        context_for(invoice),
        validation=validation,
        gl_probability=None if suggestion is None else suggestion[1],
    )
    results, decision = decide(invoice, context, extraction_reasons)
    gl_account = None if suggestion is None else suggestion[0]
    return Outcome(invoice, context, extraction_reasons, results, decision, gl_account)
