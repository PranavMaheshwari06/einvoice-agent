import pytest

from conftest import FIXTURES
from einvoice.parsing.ubl import NS, parse_ubl
from einvoice.parsing.xmltools import parse_xml, xml_syntax


def test_external_entities_are_not_expanded(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET")
    content = (
        f'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file://{secret}">]><r>&x;</r>'
    ).encode()
    root = parse_xml(content)
    assert "TOP-SECRET" not in "".join(root.itertext())


def test_malformed_xml_raises_value_error():
    with pytest.raises(ValueError, match="not well-formed"):
        parse_xml(b"<Invoice><unclosed></Invoice>")


def test_unknown_root_is_rejected():
    with pytest.raises(ValueError, match="not a UBL or CII invoice"):
        xml_syntax(parse_xml(b'<Order xmlns="urn:example"/>'))


def test_evidence_xpath_finds_the_same_value_again():
    # 02.01a uses a default namespace on the root, so the path must use our own prefixes.
    content = (FIXTURES / "xrechnung" / "02.01a-INVOICE_ubl.xml").read_bytes()
    invoice = parse_ubl(content)
    root = parse_xml(content)
    second_line = invoice.lines[1]
    for field in (invoice.number, second_line.quantity, second_line.unit, invoice.vat_total):
        found = root.xpath(field.evidence.xpath, namespaces=NS)
        assert len(found) == 1
        text = found[0] if isinstance(found[0], str) else found[0].text
        assert text.strip() == str(field.value)
    assert second_line.unit.evidence.xpath.endswith("/@unitCode")
    assert "cac:InvoiceLine[2]" in second_line.quantity.evidence.xpath
