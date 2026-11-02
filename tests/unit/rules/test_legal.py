from decimal import Decimal

from einvoice.rules import legal


def test_vat_rates_and_small_amount_limit_are_decimals():
    assert legal.STANDARD_VAT_RATE == Decimal("19")
    assert legal.REDUCED_VAT_RATE == Decimal("7")
    assert legal.SMALL_AMOUNT_LIMIT == Decimal("250")
