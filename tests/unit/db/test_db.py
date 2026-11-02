import json
import re
import uuid

import psycopg
import pytest

from einvoice.config import get_settings
from einvoice.db import db

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


@pytest.fixture
def live_connection():
    """A connection whose tables live in a throwaway schema, so the dev data stays untouched."""
    schema = f"test_{uuid.uuid4().hex}"
    with psycopg.connect(get_settings().database_url) as connection:
        connection.execute(f"CREATE SCHEMA {schema}")
        connection.execute(f"SET search_path TO {schema}, public")
        connection.commit()
        yield connection
        connection.rollback()
        connection.execute(f"DROP SCHEMA {schema} CASCADE")
        connection.commit()


def write_master_data(directory):
    vendors = [{"vat_id": "DE123456789", "name": "Muster GmbH", "iban": "DE02120300000000202051"}]
    orders = [
        {
            "po_number": "PO-1",
            "vendor_vat_id": "DE123456789",
            "lines": [
                {
                    "line_id": "1",
                    "description": "Schrauben",
                    "quantity": "10",
                    "unit_price": "1.50",
                    "receipt": {"quantity": "10", "date": "2026-01-05"},
                },
                {
                    "line_id": "2",
                    "description": "Muttern",
                    "quantity": "5",
                    "unit_price": "0.80",
                    "receipt": None,
                },
            ],
        }
    ]
    (directory / "vendors.json").write_text(json.dumps(vendors), encoding="utf-8")
    (directory / "purchase_orders.json").write_text(json.dumps(orders), encoding="utf-8")


@pytest.mark.integration
def test_live_migrate_and_load_are_repeatable(live_connection, tmp_path):
    assert db.migrate(live_connection) == ["001_init.sql"]
    assert db.migrate(live_connection) == []

    write_master_data(tmp_path)
    db.load_master_data(live_connection, tmp_path)
    db.load_master_data(live_connection, tmp_path)
    counts = {
        table: live_connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("vendors", "purchase_orders", "po_lines", "goods_receipts")
    }
    assert counts == {"vendors": 1, "purchase_orders": 1, "po_lines": 2, "goods_receipts": 1}


@pytest.mark.integration
def test_live_database_rejects_a_duplicate_invoice_and_an_unknown_decision(live_connection):
    db.migrate(live_connection)
    insert_invoice = (
        "INSERT INTO invoices (format, seller_vat_id, invoice_number, source_file, canonical) "
        "VALUES ('ubl', 'DE123456789', 'R-1', 'r1.xml', '{}') RETURNING id"
    )
    live_connection.execute(insert_invoice)
    with pytest.raises(psycopg.errors.UniqueViolation):
        live_connection.execute(insert_invoice)
    live_connection.rollback()

    invoice_id = live_connection.execute(insert_invoice).fetchone()[0]
    with pytest.raises(psycopg.errors.CheckViolation):
        live_connection.execute(
            "INSERT INTO decisions (invoice_id, kind, reasons) VALUES (%s, 'MAYBE', '{}')",
            (invoice_id,),
        )
