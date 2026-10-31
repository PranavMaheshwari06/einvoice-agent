from decimal import Decimal

import pytest
from pydantic import ValidationError

from einvoice.models import Evidence, Field, LineItem


def test_field_rejects_confidence_above_one():
    with pytest.raises(ValidationError):
        Field(value="x", evidence=Evidence(source="pdf", page=1, quote="x"), confidence=1.5)


def test_typed_field_reads_money_as_decimal():
    line = LineItem(net_amount={"value": "10.50", "evidence": {"source": "xml"}})
    assert line.net_amount.value == Decimal("10.50")
    assert isinstance(line.net_amount.value, Decimal)
