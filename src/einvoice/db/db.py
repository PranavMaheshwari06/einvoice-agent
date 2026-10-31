"""PostgreSQL access: plain SQL migrations and loading the master data from `einvoice seed`."""

import json
import logging
from pathlib import Path

import psycopg

log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


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
