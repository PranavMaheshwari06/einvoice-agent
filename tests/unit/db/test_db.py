import re

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
