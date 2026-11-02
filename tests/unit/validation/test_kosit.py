import re

import httpx
import pytest

from conftest import FIXTURES
from einvoice.config import get_settings
from einvoice.validation.kosit import parse_report, validate

REJECT_REPORT = (FIXTURES / "kosit" / "report_reject_br_de_15.xml").read_bytes()
ACCEPT_REPORT = b"""<rep:report xmlns:rep="http://www.xoev.de/de/validator/varl/1" valid="true"
    varlVersion="1.0.0">
  <rep:scenarioMatched>
    <rep:validationStepResult id="val-sch.1" valid="true">
      <rep:message id="val-sch.1.1" level="information" code="INFO-1">just a note</rep:message>
    </rep:validationStepResult>
  </rep:scenarioMatched>
  <rep:assessment><rep:accept/></rep:assessment>
</rep:report>"""


def test_reject_report_keeps_rule_ids():
    result = parse_report(REJECT_REPORT)
    assert result.accepted is False
    assert [error.rule_id for error in result.errors] == ["BR-DE-15"]
    assert result.errors[0].level == "error"
    assert result.errors[0].message.startswith("[BR-DE-15]")
    assert result.errors[0].xpath.endswith("Invoice[1]")


def test_accept_report_drops_information_messages():
    result = parse_report(ACCEPT_REPORT)
    assert result.accepted is True
    assert result.errors == []


def test_validate_reads_the_report_of_a_406_response(monkeypatch):
    def fake_post(url, content, headers, timeout):
        assert headers["Content-Type"] == "application/xml"
        return httpx.Response(406, content=REJECT_REPORT)

    monkeypatch.setattr(httpx, "post", fake_post)
    result = validate(b"<Invoice/>", "http://validator:8081")
    assert result.accepted is False


def test_validate_raises_when_the_validator_fails(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: httpx.Response(500, text="boom"))
    with pytest.raises(RuntimeError, match="returned 500"):
        validate(b"<Invoice/>", "http://validator:8081")


@pytest.mark.integration
def test_live_validator_accepts_a_testsuite_invoice():
    xml = (FIXTURES / "xrechnung" / "01.01a-INVOICE_ubl.xml").read_bytes()
    result = validate(xml, get_settings().validator_url)
    assert result.accepted, result.errors


@pytest.mark.integration
def test_live_validator_rejects_a_missing_buyer_reference():
    xml = (FIXTURES / "xrechnung" / "01.01a-INVOICE_ubl.xml").read_bytes()
    without_buyer_reference = re.sub(
        rb"\s*<cbc:BuyerReference>.*?</cbc:BuyerReference>", b"", xml, flags=re.S
    )
    assert without_buyer_reference != xml
    result = validate(without_buyer_reference, get_settings().validator_url)
    assert result.accepted is False
    assert "BR-DE-15" in [error.rule_id for error in result.errors]
