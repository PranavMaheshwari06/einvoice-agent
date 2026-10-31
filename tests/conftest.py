from decimal import Decimal
from pathlib import Path

import pytest

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

FIXTURES = Path(__file__).parent / "fixtures"
MUSTANG_PDF = FIXTURES / "corpus" / "MustangGnuaccountingBeispielRE-20201121_508.pdf"


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
