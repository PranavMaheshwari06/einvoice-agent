import os

# MLflow sends usage telemetry over the network by default; unit tests stay offline.
os.environ["MLFLOW_DISABLE_TELEMETRY"] = "true"

from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest
from sklearn.feature_extraction.text import HashingVectorizer

from einvoice.ml.coding import calibrate, tfidf_model
from einvoice.ml.train import split_lines
from einvoice.models import (
    Evidence,
    Field,
    Invoice,
    PoLine,
    PurchaseOrder,
    RuleContext,
    ValidationResult,
    Vendor,
)
from einvoice.parsing.zugferd import parse_zugferd
from einvoice.synth.generate import generate, read_gold

FIXTURES = Path(__file__).parent / "fixtures"
MUSTANG_PDF = FIXTURES / "corpus" / "MustangGnuaccountingBeispielRE-20201121_508.pdf"
SYNTH_COUNT = 200
_HASHER = HashingVectorizer(n_features=64, alternate_sign=False, norm="l2")


def stub_encode(texts: list[str]) -> np.ndarray:
    """Stands in for the e5 encoder, whose download is a network boundary."""
    return _HASHER.transform(texts).toarray()


class Rows:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class FakeDatabase:
    """Stands in for a psycopg connection: answers a SELECT with the rows of the table it reads
    and records every statement, so tests see what would reach Postgres."""

    def __init__(self, tables: dict[str, list[tuple]] | None = None):
        self.tables = tables or {}
        self.sent: list[tuple[str, object]] = []
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def cursor(self):
        return self

    def execute(self, sql, params=None):
        self.sent.append((sql, params))
        rows = [rows for name, rows in self.tables.items() if f"FROM {name}" in sql]
        return Rows(rows[0] if rows else [])

    def executemany(self, sql, rows):
        self.sent.extend((sql, row) for row in rows)

    def commit(self):
        self.committed = True


def xml_value(value) -> Field:
    return Field(value=value, evidence=Evidence(source="xml"))


@pytest.fixture(scope="session")
def mustang_invoice() -> Invoice:
    """A real ZUGFeRD invoice that passes every content and arithmetic check."""
    return parse_zugferd(MUSTANG_PDF.read_bytes())


@pytest.fixture
def ready_invoice(mustang_invoice: Invoice) -> Invoice:
    return mustang_invoice.model_copy(update={"po_number": xml_value("PO-4711")})


@pytest.fixture
def ready_context() -> RuleContext:
    """Master data that matches the Mustang invoice: known vendor, PO, goods receipts."""
    order = PurchaseOrder(
        po_number="PO-4711",
        vendor_vat_id="DE136695976",
        lines=[
            PoLine(
                line_id="1",
                description="Design (hours)",
                quantity=Decimal(1),
                unit_price=Decimal("160"),
                received_quantity=Decimal(1),
            ),
            PoLine(
                line_id="2",
                description="Ballons",
                quantity=Decimal(400),
                unit_price=Decimal("0.79"),
                received_quantity=Decimal(400),
            ),
            PoLine(
                line_id="3",
                description="Hot air „heiße Luft“ (litres)",
                quantity=Decimal(800),
                unit_price=Decimal("0.025"),
                received_quantity=Decimal(800),
            ),
        ],
    )
    return RuleContext(
        vendor=Vendor(
            vat_id="DE136695976", name="Bei Spiel GmbH", iban="DE88 2008 0000 0970 3757 00"
        ),
        purchase_order=order,
        validation=ValidationResult(accepted=True, errors=[]),
        gl_probability=0.99,
    )


@pytest.fixture(scope="session")
def gold_dir(tmp_path_factory) -> Path:
    """A small seeded gold set with files, master data and all three splits."""
    directory = tmp_path_factory.mktemp("synth_small")
    generate(seed=1, out=directory, count=SYNTH_COUNT)
    return directory


@pytest.fixture(scope="session")
def gl_model(gold_dir):
    """A calibrated TF-IDF model trained on the train split of the small gold set."""
    train = split_lines(read_gold(gold_dir))["train"]
    return calibrate(tfidf_model(), train.texts, train.accounts, train.sellers)
