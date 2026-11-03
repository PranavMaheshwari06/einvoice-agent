import asyncio
import json

from conftest import FakeDatabase, stub_encode
from einvoice.agent import mcp_server
from einvoice.agent.graph import mcp_tools

READ_ONLY_TOOLS = {"get_invoice", "get_purchase_order", "get_vendor_history", "search_rules"}


def use_database(monkeypatch, tables):
    monkeypatch.setattr(mcp_server, "_connect", lambda: FakeDatabase(tables))


def test_server_offers_exactly_the_four_read_only_tools():
    tools = asyncio.run(mcp_server.mcp.list_tools())
    assert {tool.name for tool in tools} == READ_ONLY_TOOLS


def test_tools_over_stdio_are_the_same_four_and_none_books():
    async def names():
        async with mcp_tools() as tools:
            return {tool.name for tool in tools}

    assert asyncio.run(names()) == READ_ONLY_TOOLS


def test_invoice_summary_holds_values_without_evidence(mustang_invoice):
    summary = mcp_server.invoice_summary(mustang_invoice)
    assert summary["number"] == "RE-20201121/508"
    assert summary["seller_vat_id"] == "DE136695976"
    assert summary["gross_total"] == str(mustang_invoice.gross_total.value)
    assert summary["lines"][1]["item_name"] == "Ballons"
    assert "evidence" not in json.dumps(summary)


def test_get_invoice_adds_review_reasons_and_failed_checks(monkeypatch, mustang_invoice):
    use_database(
        monkeypatch,
        {
            "invoices": [(mustang_invoice.model_dump(mode="json"),)],
            "decisions": [(["MISSING_VAT_ID"],)],
            "checks": [("MISSING_VAT_ID", "§14 Abs. 4 VAT id or tax number: missing")],
        },
    )
    answer = mcp_server.get_invoice(7)
    assert answer["invoice_id"] == 7
    assert answer["number"] == "RE-20201121/508"
    assert answer["review_reasons"] == ["MISSING_VAT_ID"]
    assert answer["failed_checks"][0]["code"] == "MISSING_VAT_ID"


def test_search_rules_wraps_the_chunks(monkeypatch):
    use_database(monkeypatch, {"rule_chunks": [("BR-DE-15", "BR-DE-15", "Buyer reference", 0.93)]})
    monkeypatch.setattr(mcp_server, "query_encoder", stub_encode)
    answer = mcp_server.search_rules("Käuferreferenz fehlt")
    assert [chunk["source_id"] for chunk in answer["chunks"]] == ["BR-DE-15"]
