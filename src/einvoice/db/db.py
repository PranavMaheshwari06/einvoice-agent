"""PostgreSQL access: migrations, loading the seed master data, the reads of the agent tools."""

import json
import logging
from pathlib import Path

import psycopg

from einvoice.models import Invoice, NotFound

log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
VENDOR_HISTORY_LIMIT = 20


def connect(database_url: str) -> psycopg.Connection:
    return psycopg.connect(database_url)


def migrate(conn: psycopg.Connection) -> list[str]:
    """Apply the migration files not yet recorded in schema_migrations, in file name order."""
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY)")
    applied = {row[0] for row in conn.execute("SELECT name FROM schema_migrations")}
    newly_applied = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name in applied:
            continue
        conn.execute(path.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
        newly_applied.append(path.name)
        log.info("applied migration %s", path.name)
    conn.commit()
    return newly_applied


def load_master_data(conn: psycopg.Connection, directory: Path) -> None:
    """Insert the vendors, purchase orders and goods receipts written by the synthetic generator."""
    vendors = json.loads((directory / "vendors.json").read_text(encoding="utf-8"))
    orders = json.loads((directory / "purchase_orders.json").read_text(encoding="utf-8"))
    with conn.cursor() as cursor:
        for vendor in vendors:
            cursor.execute(
                "INSERT INTO vendors (vat_id, name, iban) VALUES (%s, %s, %s) "
                "ON CONFLICT DO NOTHING",
                (vendor["vat_id"], vendor["name"], vendor["iban"]),
            )
        for order in orders:
            cursor.execute(
                "INSERT INTO purchase_orders (po_number, vendor_vat_id) VALUES (%s, %s) "
                "ON CONFLICT DO NOTHING",
                (order["po_number"], order["vendor_vat_id"]),
            )
            for line in order["lines"]:
                cursor.execute(
                    "INSERT INTO po_lines (po_number, line_id, description, quantity, unit_price) "
                    "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    (
                        order["po_number"],
                        line["line_id"],
                        line["description"],
                        line["quantity"],
                        line["unit_price"],
                    ),
                )
                receipt = line["receipt"]
                if receipt is not None:
                    cursor.execute(
                        "INSERT INTO goods_receipts (po_number, line_id, quantity, received_on) "
                        "SELECT %s, %s, %s, %s WHERE NOT EXISTS ("
                        "SELECT 1 FROM goods_receipts WHERE po_number = %s AND line_id = %s)",
                        (
                            order["po_number"],
                            line["line_id"],
                            receipt["quantity"],
                            receipt["date"],
                            order["po_number"],
                            line["line_id"],
                        ),
                    )
    conn.commit()
    log.info("loaded %d vendors and %d purchase orders", len(vendors), len(orders))


def fetch_invoice(
    conn: psycopg.Connection, invoice_id: int
) -> tuple[Invoice, list[str], list[dict]]:
    """The stored invoice, its decision reasons and its failed checks."""
    row = conn.execute("SELECT canonical FROM invoices WHERE id = %s", (invoice_id,)).fetchone()
    if row is None:
        raise NotFound(f"no invoice with id {invoice_id}")
    decision = conn.execute(
        "SELECT reasons FROM decisions WHERE invoice_id = %s", (invoice_id,)
    ).fetchone()
    failed = conn.execute(
        "SELECT code, message FROM checks WHERE invoice_id = %s AND NOT passed ORDER BY id",
        (invoice_id,),
    ).fetchall()
    reasons = [] if decision is None else list(decision[0])
    return (
        Invoice.model_validate(row[0]),
        reasons,
        [{"code": code, "message": message} for code, message in failed],
    )


def fetch_purchase_order(conn: psycopg.Connection, po_number: str) -> dict:
    """The order with its lines; `received_quantity` is the sum of goods receipts or None."""
    order = conn.execute(
        "SELECT vendor_vat_id FROM purchase_orders WHERE po_number = %s", (po_number,)
    ).fetchone()
    if order is None:
        raise NotFound(f"no purchase order {po_number}")
    lines = conn.execute(
        "SELECT l.line_id, l.description, l.quantity::text, l.unit_price::text, "
        "(SELECT sum(g.quantity)::text FROM goods_receipts g "
        " WHERE g.po_number = l.po_number AND g.line_id = l.line_id) "
        "FROM po_lines l WHERE l.po_number = %s ORDER BY l.line_id",
        (po_number,),
    ).fetchall()
    columns = ("line_id", "description", "quantity", "unit_price", "received_quantity")
    return {
        "po_number": po_number,
        "vendor_vat_id": order[0],
        "lines": [dict(zip(columns, line, strict=True)) for line in lines],
    }


def fetch_vendor_history(conn: psycopg.Connection, vat_id: str) -> dict:
    """The master record (None for an unknown vendor) and the vendor's latest invoices."""
    vendor = conn.execute("SELECT name, iban FROM vendors WHERE vat_id = %s", (vat_id,)).fetchone()
    invoices = conn.execute(
        "SELECT i.invoice_number, i.issue_date::text, i.gross_total::text, b.gl_account "
        "FROM invoices i LEFT JOIN bookings b ON b.invoice_id = i.id "
        "WHERE i.seller_vat_id = %s ORDER BY i.issue_date DESC LIMIT %s",
        (vat_id, VENDOR_HISTORY_LIMIT),
    ).fetchall()
    columns = ("number", "issue_date", "gross_total", "gl_account")
    return {
        "vat_id": vat_id,
        "vendor": None if vendor is None else {"name": vendor[0], "iban": vendor[1]},
        "invoices": [dict(zip(columns, invoice, strict=True)) for invoice in invoices],
    }
