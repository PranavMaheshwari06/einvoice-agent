# Accounts payable policy

Written for this project. It is an example policy for a small company, not legal advice.
The tolerances below are the same values as the constants in `rules/matching.py` and
`rules/duplicates.py`.

## Automatic booking

An invoice is booked without a person only when all of the following hold:

- structured invoices (XRechnung, ZUGFeRD) were accepted by the KoSIT validator;
  invoices read from PDF or scan have every required field extracted with high confidence
- every content and arithmetic check passes
- the purchase order matches the invoice
- the suggested general-ledger account (SKR03) has a probability above the set threshold

Everything else goes to a reviewer together with the reason codes of the failed checks.

## Purchase order matching

Every invoice must name a purchase order (BT-13) that belongs to the same seller.
Each invoice line is matched to a purchase order line by line reference (BT-132) or by
item description.

## Price tolerance

The unit price on the invoice may differ from the purchase order price by at most 2 percent
in either direction. A larger deviation goes to review (`PRICE_OUTSIDE_TOLERANCE`).

## Goods receipt

Where goods receipts exist, the invoiced quantity must not exceed the quantity received.
Invoices above it go to review (`QUANTITY_ABOVE_RECEIPT`). A purchase order without goods
receipts is matched on price and reference only.

## Vendor master data

The seller must exist in the vendor master data. An unknown vendor always goes to review
(`UNKNOWN_VENDOR`). Vendors are not created from an invoice.

## Bank details

If the IBAN on the invoice differs from the IBAN in the vendor master record, the invoice
always goes to review (`BANK_DETAILS_CHANGED`), whatever the other checks say. The reviewer
confirms the change with the vendor by a known channel before it is accepted.

## Duplicates

An invoice is a duplicate if the same seller VAT id and invoice number were received before,
or if the same seller sent the same gross amount with an issue date within 7 days of an
earlier invoice. Duplicates are not booked (`DUPLICATE_INVOICE`).

## Mandatory content

Invoices must carry the details required by §14 Abs. 4 UStG. Invoices up to a gross amount of
250 EUR need fewer details (§33 UStDV). A missing mandatory field goes to review; the
reviewer asks the vendor for a corrected invoice.

## VAT rates

Standard-rated lines must use 19 percent or 7 percent. Other VAT categories carry 0 percent.
Any other rate goes to review (`INVALID_VAT_RATE`).
