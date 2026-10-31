"""Legal constants used by the rules. Each cites its source; check it there before relying on it."""

from decimal import Decimal

# §12 Abs. 1 UStG (checked against gesetze-im-internet.de, UStG XML fetched 2026-10-31).
STANDARD_VAT_RATE = Decimal("19")
# §12 Abs. 2 UStG (same source).
REDUCED_VAT_RATE = Decimal("7")
# §33 Satz 1 UStDV: invoices up to 250 EUR gross need fewer details (Kleinbetragsrechnung);
# 250 EUR since 1.1.2017, Zweites Bürokratieentlastungsgesetz. UStDV is not in data/raw.
SMALL_AMOUNT_LIMIT = Decimal("250")
