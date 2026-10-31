"""lxml helpers shared by the UBL and CII parsers: safe parsing and fields with XPath evidence."""

from collections.abc import Callable
from datetime import date, datetime
from decimal import InvalidOperation
from typing import Literal, TypeVar

from lxml import etree

from einvoice.models import Address, Evidence, Field

T = TypeVar("T")

UBL_INVOICE_NS = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
UBL_CREDIT_NOTE_NS = "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
CII_NS = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"


def parse_xml(content: bytes) -> etree._Element:
    # Invoices come from outside: no DTDs, no entity expansion, no network access (XXE).
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True)
    try:
        return etree.fromstring(content, parser)
    except etree.XMLSyntaxError as error:
        raise ValueError(f"not well-formed XML: {error}") from error


def xml_syntax(root: etree._Element) -> Literal["ubl", "cii"]:
    namespace = etree.QName(root).namespace
    if namespace in (UBL_INVOICE_NS, UBL_CREDIT_NOTE_NS):
        return "ubl"
    if namespace == CII_NS:
        return "cii"
    raise ValueError(f"not a UBL or CII invoice: root element {root.tag}")


def cii_date(text: str) -> date:
    """CII dates use format 102 (YYYYMMDD)."""
    return datetime.strptime(text, "%Y%m%d").date()


def element_path(element: etree._Element, ns: dict[str, str]) -> str:
    """Absolute XPath of an element using the parser's prefixes, so it can be evaluated again."""
    prefix_for = {uri: prefix for prefix, uri in ns.items()}
    steps = []
    node: etree._Element | None = element
    while node is not None:
        qname = etree.QName(node)
        step = f"{prefix_for[qname.namespace]}:{qname.localname}"
        parent = node.getparent()
        if parent is not None:
            siblings = [child for child in parent if child.tag == node.tag]
            if len(siblings) > 1:
                step += f"[{siblings.index(node) + 1}]"
        steps.append(step)
        node = parent
    return "/" + "/".join(reversed(steps))


def _to_field(hit, ns: dict[str, str], bt: str, convert: Callable[[str], T]) -> Field[T] | None:
    if isinstance(hit, etree._Element):
        text, xpath = hit.text, element_path(hit, ns)
    else:
        text, xpath = str(hit), f"{element_path(hit.getparent(), ns)}/@{hit.attrname}"
    text = (text or "").strip()
    if not text:
        return None
    try:
        value = convert(text)
    except (ValueError, InvalidOperation) as error:
        raise ValueError(f"{bt} at {xpath}: cannot read {text!r}") from error
    return Field(value=value, evidence=Evidence(source="xml", bt=bt, xpath=xpath))


def xml_field(
    node: etree._Element,
    path: str,
    ns: dict[str, str],
    bt: str,
    convert: Callable[[str], T] = str,
) -> Field[T] | None:
    hits = node.xpath(path, namespaces=ns)
    return _to_field(hits[0], ns, bt, convert) if hits else None


def xml_fields(
    node: etree._Element,
    path: str,
    ns: dict[str, str],
    bt: str,
    convert: Callable[[str], T] = str,
) -> list[Field[T]]:
    fields = (_to_field(hit, ns, bt, convert) for hit in node.xpath(path, namespaces=ns))
    return [found for found in fields if found is not None]


def address_field(
    node: etree._Element, path: str, ns: dict[str, str], bt: str, parts: dict[str, str]
) -> Field[Address] | None:
    """Read an address element; `parts` maps Address attributes to paths relative to it."""
    hits = node.xpath(path, namespaces=ns)
    if not hits:
        return None
    values = {}
    for name, part_path in parts.items():
        found = xml_field(hits[0], part_path, ns, bt)
        values[name] = found.value if found else None
    evidence = Evidence(source="xml", bt=bt, xpath=element_path(hits[0], ns))
    return Field(value=Address(**values), evidence=evidence)
