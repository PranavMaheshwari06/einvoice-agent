import asyncio
import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from conftest import FIXTURES
from einvoice.agent import evals
from einvoice.agent.graph import MAX_TOOL_ROUNDS, check_answer, propose, retrieved_sources
from einvoice.agent.rag import Chunk
from einvoice.llm import ReplayChatModel

CASES_FILE = Path(__file__).parents[3] / "evals" / "agent_cases.yaml"
CASES = {case["id"]: case for case in evals.load_cases(CASES_FILE)}
CHUNKS = {
    source_id: Chunk(source_id, source_id, f"text of {source_id}")
    for case in CASES.values()
    for source_id in case["rules"]
}


def call(name: str, args: dict, call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def answer(**proposal) -> AIMessage:
    fields = {"explanation": "x", "citations": [], "vendor_email_de": None, **proposal}
    return AIMessage(content=json.dumps(fields))


def run_case(case_id: str, responses: list[AIMessage]):
    case = CASES[case_id]
    model = ReplayChatModel(responses=responses)
    tools = evals.case_tools(case, CHUNKS)
    return asyncio.run(propose(model, tools, case["invoice_id"], case["reasons"]))


def searched(*replies: AIMessage) -> list[AIMessage]:
    """get_invoice, then search_rules, then the given replies."""
    return [
        call("get_invoice", {"invoice_id": CASES["missing_vat_id"]["invoice_id"]}, "c1"),
        call("search_rules", {"query": "USt-IdNr fehlt"}, "c2"),
        *replies,
    ]


def test_a_cited_proposal_stands():
    proposal, _ = run_case(
        "missing_vat_id", searched(answer(action="request_correction", citations=["UStG-14-4"]))
    )
    assert proposal.action == "request_correction"
    assert proposal.citations == ["UStG-14-4"]
    assert proposal.reasons == []


def test_a_citation_not_returned_in_this_run_escalates():
    proposal, _ = run_case(
        "missing_vat_id", searched(answer(action="request_correction", citations=["UStG-14-9"]))
    )
    assert proposal.action == "escalate"
    assert proposal.reasons == ["UNSUPPORTED_EXPLANATION"]
    assert proposal.citations == []


def test_an_explanation_without_citations_escalates():
    proposal, _ = run_case("missing_vat_id", searched(answer(action="approve_booking")))
    assert proposal.reasons == ["UNSUPPORTED_EXPLANATION"]


def test_no_search_at_all_escalates_for_insufficient_evidence():
    proposal, _ = run_case(
        "instruction_in_item_text",
        [
            call(
                "get_invoice", {"invoice_id": CASES["instruction_in_item_text"]["invoice_id"]}, "c1"
            ),
            answer(action="approve_booking", citations=["UStG-14-4"]),
        ],
    )
    assert proposal.action == "escalate"
    assert proposal.reasons == ["INSUFFICIENT_EVIDENCE"]


def test_empty_retrieval_escalates_whatever_the_model_cites():
    case = CASES["empty_retrieval_missing_field"]
    proposal, _ = run_case(
        "empty_retrieval_missing_field",
        [
            call("get_invoice", {"invoice_id": case["invoice_id"]}, "c1"),
            call("search_rules", {"query": "USt-IdNr"}, "c2"),
            answer(action="request_correction", citations=["UStG-14-4"]),
        ],
    )
    assert proposal.reasons == ["INSUFFICIENT_EVIDENCE"]


@pytest.mark.parametrize(
    "content", ["```json\n{}\n```", '{"action": "book_now", "explanation": ""}']
)
def test_an_answer_that_is_not_a_proposal_escalates(content):
    proposal, _ = run_case("missing_vat_id", searched(AIMessage(content=content)))
    assert proposal.action == "escalate"
    assert proposal.reasons == ["INVALID_PROPOSAL"]


def test_a_lookup_miss_goes_back_to_the_model():
    _, messages = run_case(
        "missing_vat_id",
        searched(
            call("get_purchase_order", {"po_number": "PO-0000"}, "c3"),
            answer(action="request_correction", citations=["UStG-14-4"]),
        ),
    )
    miss = next(
        m for m in messages if isinstance(m, ToolMessage) and m.name == "get_purchase_order"
    )
    assert miss.status == "error"
    assert "no purchase order PO-0000" in miss.text


def test_failed_search_calls_are_not_evidence():
    failed = ToolMessage(
        content="Error: boom", name="search_rules", tool_call_id="c1", status="error"
    )
    found = ToolMessage(
        content=json.dumps({"chunks": [{"source_id": "BR-DE-15"}]}),
        name="search_rules",
        tool_call_id="c2",
    )
    assert retrieved_sources([failed, found]) == {"BR-DE-15"}
    assert check_answer([failed, answer(action="reject", citations=["BR-DE-15"])]).reasons == [
        "INSUFFICIENT_EVIDENCE"
    ]


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_every_kept_citation_came_from_a_tool_call_in_the_run(case_id):
    case = CASES[case_id]
    model = ReplayChatModel.from_file(evals.replay_file(FIXTURES / "replay", case))
    tools = evals.case_tools(case, CHUNKS)
    proposal, messages = asyncio.run(propose(model, tools, case["invoice_id"], case["reasons"]))
    assert set(proposal.citations) <= retrieved_sources(messages)
    assert proposal.reasons or proposal.citations


def test_a_model_stuck_in_tool_calls_is_cut_off_and_escalates():
    rounds = range(MAX_TOOL_ROUNDS + 2)
    loop = [call("search_rules", {"query": f"try {n}"}, f"c{n}") for n in rounds]
    proposal, messages = run_case("missing_vat_id", loop)
    assert proposal.reasons == ["INVALID_PROPOSAL"]
    assert sum(isinstance(m, AIMessage) for m in messages) == MAX_TOOL_ROUNDS


def test_a_programming_error_in_a_tool_stops_the_run():
    broken = dict(CASES["missing_vat_id"], rules=["NOT-IN-CORPUS"])
    model = ReplayChatModel(responses=searched(answer(action="reject", citations=["X"])))
    tools = evals.case_tools(broken, CHUNKS)
    with pytest.raises(KeyError, match="NOT-IN-CORPUS"):
        asyncio.run(propose(model, tools, broken["invoice_id"], broken["reasons"]))
