"""Client for the KoSIT validator running as an HTTP daemon, and a parser for its report."""

import logging

import httpx

from einvoice.models import RuleViolation, ValidationResult
from einvoice.parsing.xmltools import parse_xml

logger = logging.getLogger(__name__)

REPORT_NS = {"rep": "http://www.xoev.de/de/validator/varl/1"}
TIMEOUT_SECONDS = 60
# The daemon answers 200 when it recommends accept and 406 when it recommends reject;
# both carry a report. Anything else is a failure of the validator itself.
REPORT_STATUS_CODES = (200, 406)


def parse_report(report: bytes) -> ValidationResult:
    root = parse_xml(report)
    accepted = bool(root.xpath("/rep:report/rep:assessment/rep:accept", namespaces=REPORT_NS))
    errors = [
        RuleViolation(
            rule_id=message.get("code"),
            level=message.get("level"),
            message=" ".join((message.text or "").split()),
            xpath=message.get("xpathLocation"),
        )
        for message in root.xpath("//rep:message[@level!='information']", namespaces=REPORT_NS)
    ]
    return ValidationResult(accepted=accepted, errors=errors)


def validate(xml: bytes, validator_url: str) -> ValidationResult:
    response = httpx.post(
        validator_url,
        content=xml,
        headers={"Content-Type": "application/xml"},
        timeout=TIMEOUT_SECONDS,
    )
    if response.status_code not in REPORT_STATUS_CODES:
        raise RuntimeError(
            f"KoSIT validator at {validator_url} returned {response.status_code}: "
            f"{response.text[:300]}"
        )
    result = parse_report(response.content)
    logger.info("KoSIT: accepted=%s, %d messages", result.accepted, len(result.errors))
    return result
