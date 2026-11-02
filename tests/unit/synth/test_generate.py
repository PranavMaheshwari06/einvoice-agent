from decimal import Decimal
from io import BytesIO

import pytest
from pypdf import PdfReader

from einvoice.models import PriorInvoice, RuleContext, ValidationResult
from einvoice.parsing.cii import parse_cii
from einvoice.parsing.detect import detect_format
from einvoice.parsing.ubl import parse_ubl
from einvoice.parsing.zugferd import embedded_invoice_xml, parse_zugferd
from einvoice.rules import engine
from einvoice.synth.generate import (
    PROBLEMS,
    generate,
    prior_invoice,
    read_gold,
    read_master_data,
)

PARSERS = {"cii": parse_cii, "ubl": parse_ubl, "zugferd_pdf": parse_zugferd}


@pytest.fixture(scope="module")
def gold(gold_dir) -> list[dict]:
    return read_gold(gold_dir)


def test_every_file_is_detected_as_its_gold_format(gold_dir, gold):
    for record in gold:
        assert detect_format((gold_dir / record["file"]).read_bytes()) == record["format"]


def test_all_formats_and_all_problems_occur(gold):
    assert {record["format"] for record in gold} == {"cii", "ubl", "zugferd_pdf", "pdf", "scan"}
    assert {record["problem"] for record in gold} - {None} == set(PROBLEMS)


def test_structured_invoices_parse_to_gold(gold_dir, gold):
    parsed = 0
    for record in gold:
        if record["format"] not in PARSERS:
            continue
        invoice = PARSERS[record["format"]]((gold_dir / record["file"]).read_bytes())
        assert invoice.number.value == record["number"]
        assert invoice.seller_name.value == record["vendor_name"]
        assert invoice.issue_date.value.isoformat() == record["issue_date"]
        assert invoice.due_date.value.isoformat() == record["due_date"]
        assert invoice.tax_exclusive_total.value == Decimal(record["net_total"])
        assert [line.item_name.value for line in invoice.lines] == [
            line["item_name"] for line in record["lines"]
        ]
        if record["problem"] != "vat_sum_off":
            assert str(invoice.gross_total.value) == record["gross_total"]
        parsed += 1
    assert parsed > 50


def test_rules_flag_exactly_the_labelled_problems(gold_dir, gold):
    vendors, orders = read_master_data(gold_dir)
    vendor_by_vat_id = {vendor.vat_id: vendor for vendor in vendors}
    order_by_number = {order.po_number: order for order in orders}
    prior: list[PriorInvoice] = []
    checked = 0
    for record in gold:
        if record["format"] in PARSERS:
            invoice = PARSERS[record["format"]]((gold_dir / record["file"]).read_bytes())
            context = RuleContext(
                vendor=vendor_by_vat_id.get(record["vendor_vat_id"]),
                purchase_order=order_by_number.get(record["po_number"]),
                prior_invoices=list(prior),
                validation=ValidationResult(accepted=True, errors=[]),
                gl_probability=1.0,
            )
            _, decision = engine.run(invoice, context)
            assert set(decision.reasons) == set(record["reasons"]), record["id"]
            assert (decision.kind == "REVIEW") == record["must_review"], record["id"]
            checked += 1
        # Every earlier invoice counts as received, whatever its format.
        prior.append(prior_invoice(record))
    assert checked > 50


def test_gold_amounts_add_up(gold):
    for record in gold:
        net, vat = Decimal(record["net_total"]), Decimal(record["vat_total"])
        assert net + vat == Decimal(record["gross_total"])
        assert sum(Decimal(line["net_amount"]) for line in record["lines"]) == net
        assert record["gl_account"] in {line["gl_account"] for line in record["lines"]}


def test_vendors_do_not_share_splits(gold):
    splits_by_vendor: dict[str, set[str]] = {}
    for record in gold:
        splits_by_vendor.setdefault(record["vendor_vat_id"], set()).add(record["split"])
    assert all(len(splits) == 1 for splits in splits_by_vendor.values())
    assert {record["split"] for record in gold} == {"train", "validation", "test"}


def test_the_same_item_is_booked_to_different_accounts_by_different_vendors(gold):
    accounts_by_item: dict[str, set[str]] = {}
    for record in gold:
        for line in record["lines"]:
            accounts_by_item.setdefault(line["item_name"], set()).add(line["gl_account"])
    assert any(len(accounts) > 1 for accounts in accounts_by_item.values())


def test_duplicates_repeat_an_earlier_invoice(gold):
    by_id = {record["id"]: record for record in gold}
    duplicates = [record for record in gold if record["problem"] == "duplicate"]
    assert duplicates
    for record in duplicates:
        earlier = [
            other
            for other in gold
            if other["id"] < record["id"]
            and other["vendor_vat_id"] == record["vendor_vat_id"]
            and other["gross_total"] == record["gross_total"]
            and other["problem"] is None
        ]
        assert earlier, record["id"]
        assert by_id[record["id"]]["must_review"]


def test_same_seed_gives_the_same_output(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    generate(seed=7, out=first, count=25)
    generate(seed=7, out=second, count=25)
    for name in ("gold.jsonl", "vendors.json", "purchase_orders.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    for record in read_gold(first):
        one = (first / record["file"]).read_bytes()
        other = (second / record["file"]).read_bytes()
        if record["format"] == "zugferd_pdf":
            # drafthorse stamps the current time into the PDF; the embedded XML is the content.
            one = embedded_invoice_xml(PdfReader(BytesIO(one)))
            other = embedded_invoice_xml(PdfReader(BytesIO(other)))
        assert one == other, record["file"]


def test_a_different_seed_gives_different_invoices(tmp_path):
    generate(seed=1, out=tmp_path / "one", count=10)
    generate(seed=2, out=tmp_path / "two", count=10)
    assert (tmp_path / "one" / "gold.jsonl").read_bytes() != (
        tmp_path / "two" / "gold.jsonl"
    ).read_bytes()
