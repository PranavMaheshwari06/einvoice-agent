import json
from pathlib import Path

import pytest

from conftest import FIXTURES
from einvoice.agent import evals, mcp_server, rag
from einvoice.agent.rag import Chunk
from einvoice.config import Settings
from einvoice.llm import ReplayChatModel

ROOT = Path(__file__).parents[3]
CASES_FILE = ROOT / "evals" / "agent_cases.yaml"
REPLAY_DIR = FIXTURES / "replay"
CASES = evals.load_cases(CASES_FILE)
ACTIONS = {"approve_booking", "request_correction", "reject", "escalate"}
GUARDRAIL_CODES = {"INSUFFICIENT_EVIDENCE", "UNSUPPORTED_EXPLANATION", "INVALID_PROPOSAL"}


def stand_in_chunks() -> dict[str, Chunk]:
    """Replay does not read chunk texts; the UStG text is fetched only on the laptop."""
    return {
        source_id: Chunk(source_id, source_id, "") for case in CASES for source_id in case["rules"]
    }


def replay_model(case: dict) -> ReplayChatModel:
    return ReplayChatModel.from_file(evals.replay_file(REPLAY_DIR, case))


def test_about_thirty_cases_with_unique_ids_and_one_fixture_each():
    ids = [case["id"] for case in CASES]
    assert 28 <= len(ids) == len(set(ids))
    fixtures = {path.name for path in REPLAY_DIR.glob("agent_*.json")}
    assert fixtures == {f"agent_{case_id}.json" for case_id in ids}


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_case_is_consistent(case, mustang_invoice):
    expected = case["expected"]
    assert expected["action"] in ACTIONS
    assert set(expected["reasons"]) <= GUARDRAIL_CODES
    assert set(expected["cite"]) <= set(case["rules"])
    assert set(case["invoice"]) == set(mcp_server.invoice_summary(mustang_invoice))
    assert set(case["vendor_history"]) == {"vendor", "invoices"}


def test_cited_policy_and_br_de_ids_exist_in_the_real_sources():
    real = {
        chunk.source_id
        for chunk in rag.policy_chunks(
            (ROOT / "data/rules/ap_policy.md").read_text(encoding="utf-8")
        )
        + rag.br_de_chunks(FIXTURES / "kosit" / "XRechnung-UBL-validation.xsl")
    }
    used = {source_id for case in CASES for source_id in case["rules"]}
    assert {source_id for source_id in used if not source_id.startswith("UStG-")} <= real


def scores_of(cases: list[dict]) -> list[dict]:
    return [score for score, _ in evals.run(cases, replay_model, stand_in_chunks())]


def test_hand_written_replays_reach_the_expected_proposals():
    scores = scores_of(CASES)
    assert [score["id"] for score in scores if not score["passed"]] == []


def test_summary_counts_against_the_always_escalate_baseline():
    summary = evals.summarize(scores_of(CASES))
    escalations = sum(case["expected"]["action"] == "escalate" for case in CASES)
    assert summary["cases"] == len(CASES)
    assert summary["action_accuracy"] == 1.0
    assert summary["baseline_always_escalate_action_accuracy"] == escalations / len(CASES)
    assert 0 < summary["baseline_always_escalate_action_accuracy"] < 1
    assert summary["guardrail_cases"] == sum(bool(case["expected"]["reasons"]) for case in CASES)
    assert summary["citation_recall"] == 1.0
    assert summary["failures"] == []


def test_a_wrong_action_is_a_failure_with_the_proposal():
    case = dict(CASES[0], expected={**CASES[0]["expected"], "action": "reject"})
    summary = evals.summarize(scores_of([case]))
    assert summary["passed"] == 0
    assert summary["failures"][0]["proposal"]["action"] == "request_correction"


def test_recording_writes_fixtures_that_replay_the_same_run(tmp_path):
    case = CASES[0]
    [(_, messages)] = evals.run([case], replay_model, stand_in_chunks())
    evals.write_fixture(tmp_path, case, messages, "recorded from openai:test-model")
    written = json.loads(evals.replay_file(tmp_path, case).read_text(encoding="utf-8"))
    assert written["source"] == "recorded from openai:test-model"

    again = evals.run(
        [case],
        lambda c: ReplayChatModel.from_file(evals.replay_file(tmp_path, c)),
        stand_in_chunks(),
    )
    assert again[0][0]["passed"]


def test_replay_report_says_where_the_answers_came_from(tmp_path):
    report = evals.evaluate(
        CASES_FILE, REPLAY_DIR, stand_in_chunks(), Settings(llm_provider="replay"), tmp_path, False
    )
    written = json.loads((tmp_path / "agent_eval.json").read_text(encoding="utf-8"))
    assert written == report
    assert report["model"] == "replay"
    assert report["recorded"] is False
    assert report["replay_fixtures"] == {"hand-written": len(CASES)}


def test_recording_needs_a_real_provider(tmp_path):
    with pytest.raises(ValueError, match="real LLM_PROVIDER"):
        evals.evaluate(
            CASES_FILE,
            REPLAY_DIR,
            stand_in_chunks(),
            Settings(llm_provider="replay"),
            tmp_path,
            True,
        )


def test_citation_recall_counts_only_cases_that_expect_citations():
    uncited = {"citations": True, "cites_expected": False}
    scores = [
        {**score, **uncited} if not score["cites_expected"] else {**score, "citations": False}
        for score in scores_of(CASES)
    ]
    assert evals.summarize(scores)["citation_recall"] == 0.0


def test_case_search_returns_at_most_max_chunks():
    case = dict(CASES[0], rules=["AP-duplicates"] * 20)
    search = next(
        tool
        for tool in evals.case_tools(
            case, stand_in_chunks() | {"AP-duplicates": Chunk("AP-duplicates", "Duplicates", "")}
        )
        if tool.name == "search_rules"
    )
    assert len(search.invoke({"query": "x", "k": 50})["chunks"]) == rag.MAX_CHUNKS
