"""Read-only MCP tools for the review agent. There is no tool that writes or books (SPEC 3.7).

Run as `python -m einvoice.agent.mcp_server`; it speaks MCP over stdio.
"""

from mcp.server.fastmcp import FastMCP

from einvoice.agent import rag
from einvoice.config import get_settings
from einvoice.db import db
from einvoice.ml.coding import E5Encoder
from einvoice.models import Invoice

HEADER_FIELDS = (
    "number",
    "issue_date",
    "due_date",
    "delivery_date",
    "currency",
    "po_number",
    "buyer_reference",
    "seller_name",
    "seller_vat_id",
    "iban",
    "buyer_name",
    "tax_exclusive_total",
    "vat_total",
    "gross_total",
    "amount_due",
)
LINE_FIELDS = ("item_name", "quantity", "price", "net_amount", "vat_rate", "po_line_ref")

mcp = FastMCP("einvoice")
query_encoder = E5Encoder(prefix=rag.QUERY_PREFIX)


def _connect():
    return db.connect(get_settings().database_url)


def _values(dumped: dict, names: tuple[str, ...]) -> dict:
    return {name: None if dumped[name] is None else dumped[name]["value"] for name in names}


def invoice_summary(invoice: Invoice) -> dict:
    """Field values without their evidence, as JSON types; the full record would flood the model."""
    dumped = invoice.model_dump(mode="json")
    return {
        "format": invoice.format,
        **_values(dumped, HEADER_FIELDS),
        "lines": [_values(line, LINE_FIELDS) for line in dumped["lines"]],
    }


@mcp.tool()
def get_invoice(invoice_id: int) -> dict:
    """The invoice: header fields, totals, lines, the reasons it is in review and failed checks."""
    with _connect() as conn:
        invoice, reasons, failed_checks = db.fetch_invoice(conn, invoice_id)
    return {
        "invoice_id": invoice_id,
        **invoice_summary(invoice),
        "review_reasons": reasons,
        "failed_checks": failed_checks,
    }


@mcp.tool()
def get_purchase_order(po_number: str) -> dict:
    """The purchase order with its lines, prices and received quantities."""
    with _connect() as conn:
        return db.fetch_purchase_order(conn, po_number)


@mcp.tool()
def get_vendor_history(vat_id: str) -> dict:
    """The vendor master record (null if unknown) and the vendor's latest invoices."""
    with _connect() as conn:
        return db.fetch_vendor_history(conn, vat_id)


@mcp.tool()
def search_rules(query: str, k: int = 4) -> dict:
    """Rule texts (UStG §14, AP policy, BR-DE) closest to the query, each with its source_id."""
    with _connect() as conn:
        return {"chunks": rag.search(conn, query_encoder, query, k)}


TOOLS = (get_invoice, get_purchase_order, get_vendor_history, search_rules)

if __name__ == "__main__":
    mcp.run()
