import re

import pytest

from conftest import FakeDatabase
from einvoice.db import db
from einvoice.models import NotFound

EXPECTED_TABLES = {
    "vendors",
    "purchase_orders",
    "po_lines",
    "goods_receipts",
    "invoices",
    "checks",
    "decisions",
    "proposals",
    "bookings",
    "corrections",
    "rule_chunks",
    "drift_runs",
}


class FakeConnection:
    """Stands in for psycopg.Connection and records what the migration runner sends."""

    def __init__(self):
        self.applied: set[str] = set()
        self.scripts: list[str] = []

    def execute(self, sql, params=None):
        if sql.startswith("SELECT name"):
            return [(name,) for name in sorted(self.applied)]
        if sql.startswith("INSERT INTO schema_migrations"):
            self.applied.add(params[0])
        elif "CREATE TABLE IF NOT EXISTS" not in sql:
            self.scripts.append(sql)
        return []

    def commit(self):
        pass


def migration_sql() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in db.MIGRATIONS_DIR.glob("*.sql"))


def test_migrations_create_every_table_of_the_spec():
    created = set(re.findall(r"CREATE TABLE (\w+)", migration_sql()))
    assert created == EXPECTED_TABLES


def test_duplicate_rule_is_backed_by_a_unique_constraint():
    assert "UNIQUE (seller_vat_id, invoice_number)" in migration_sql()


def test_embeddings_match_the_e5_model_size():
    assert "vector(384)" in migration_sql()


def test_migrate_applies_each_file_once_in_order():
    connection = FakeConnection()
    first = db.migrate(connection)
    assert first == sorted(path.name for path in db.MIGRATIONS_DIR.glob("*.sql"))
    assert len(connection.scripts) == len(first)
    assert db.migrate(connection) == []
    assert len(connection.scripts) == len(first)


def test_fetch_invoice_returns_the_invoice_reasons_and_failed_checks(mustang_invoice):
    conn = FakeDatabase(
        {
            "invoices": [(mustang_invoice.model_dump(mode="json"),)],
            "decisions": [(["UNKNOWN_VENDOR"],)],
            "checks": [("UNKNOWN_VENDOR", "no vendor DE136695976")],
        }
    )
    invoice, reasons, failed = db.fetch_invoice(conn, 3)
    assert invoice == mustang_invoice
    assert reasons == ["UNKNOWN_VENDOR"]
    assert failed == [{"code": "UNKNOWN_VENDOR", "message": "no vendor DE136695976"}]


def test_fetch_invoice_refuses_an_unknown_id():
    with pytest.raises(NotFound, match="no invoice with id 9"):
        db.fetch_invoice(FakeDatabase({"invoices": []}), 9)


def test_fetch_purchase_order_names_the_line_columns():
    conn = FakeDatabase(
        {
            "purchase_orders": [("DE100000001",)],
            "po_lines": [("1", "Toner schwarz", "4.0000", "105.0000", None)],
        }
    )
    order = db.fetch_purchase_order(conn, "PO-1")
    assert order["vendor_vat_id"] == "DE100000001"
    assert order["lines"] == [
        {
            "line_id": "1",
            "description": "Toner schwarz",
            "quantity": "4.0000",
            "unit_price": "105.0000",
            "received_quantity": None,
        }
    ]


def test_fetch_purchase_order_refuses_an_unknown_number():
    with pytest.raises(NotFound, match="no purchase order PO-9"):
        db.fetch_purchase_order(FakeDatabase({"purchase_orders": []}), "PO-9")


def test_vendor_history_of_an_unknown_vendor_has_no_master_record():
    conn = FakeDatabase({"vendors": [], "invoices": []})
    assert db.fetch_vendor_history(conn, "DE100000099") == {
        "vat_id": "DE100000099",
        "vendor": None,
        "invoices": [],
    }


def test_vendor_history_lists_booked_accounts():
    conn = FakeDatabase(
        {
            "vendors": [("Muster GmbH", "DE89370400440532013000")],
            "invoices": [("RE-1", "2026-08-12", "249.90", "4930")],
        }
    )
    history = db.fetch_vendor_history(conn, "DE100000001")
    assert history["vendor"] == {"name": "Muster GmbH", "iban": "DE89370400440532013000"}
    assert history["invoices"][0]["gl_account"] == "4930"
