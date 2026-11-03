"""Agent evaluation: each case fixes what the read-only tools return and which proposal is right.

The case tools carry the names and argument schemas of the MCP tools but answer from the case,
so a run depends only on the model. `search_rules` returns the case's chunks for any query.
"""

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

import yaml
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage
from langchain_core.tools import StructuredTool

from einvoice.agent import mcp_server, rag
from einvoice.agent.graph import AgentProposal, propose
from einvoice.agent.rag import Chunk
from einvoice.config import Settings
from einvoice.llm import chat_model, recorded
from einvoice.models import NotFound

logger = logging.getLogger(__name__)


def load_cases(path: Path) -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def replay_file(replay_dir: Path, case: dict) -> Path:
    return replay_dir / f"agent_{case['id']}.json"


# The case tools take over the MCP tools' schemas, so the model sees the interface of the app.
TEMPLATES = {tool.__name__: StructuredTool.from_function(tool) for tool in mcp_server.TOOLS}


def _like(answer: Callable) -> StructuredTool:
    template = TEMPLATES[answer.__name__]
    return StructuredTool.from_function(
        answer,
        name=template.name,
        description=template.description,
        args_schema=template.args_schema,
    )


def case_tools(case: dict, chunks: dict[str, Chunk]) -> list[StructuredTool]:
    def get_invoice(invoice_id: int) -> dict:
        if invoice_id != case["invoice_id"]:
            raise NotFound(f"no invoice with id {invoice_id}")
        return {
            "invoice_id": invoice_id,
            **case["invoice"],
            "review_reasons": case["reasons"],
            "failed_checks": case.get("failed_checks", []),
        }

    def get_purchase_order(po_number: str) -> dict:
        order = case.get("purchase_order")
        if order is None or order["po_number"] != po_number:
            raise NotFound(f"no purchase order {po_number}")
        return order

    def get_vendor_history(vat_id: str) -> dict:
        if vat_id != case["invoice"]["seller_vat_id"]:
            return {"vat_id": vat_id, "vendor": None, "invoices": []}
        return {"vat_id": vat_id, **case["vendor_history"]}

    def search_rules(query: str, k: int = 4) -> dict:
        found = case["rules"][: min(k, rag.MAX_CHUNKS)]
        return {"chunks": [asdict(chunks[source_id]) for source_id in found]}

    return [
        _like(answer)
        for answer in (get_invoice, get_purchase_order, get_vendor_history, search_rules)
    ]


def score(case: dict, proposal: AgentProposal) -> dict:
    expected = case["expected"]
    checks = {
        "action": proposal.action == expected["action"],
        "reasons": proposal.reasons == expected.get("reasons", []),
        "citations": set(expected.get("cite", [])) <= set(proposal.citations),
    }
    return {
        "id": case["id"],
        "passed": all(checks.values()),
        **checks,
        "guardrail_case": bool(expected.get("reasons")),
        "cites_expected": bool(expected.get("cite")),
        "escalate_expected": expected["action"] == "escalate",
        "proposal": proposal,
    }


def summarize(scores: list[dict]) -> dict:
    """Pass rates next to the baseline that escalates every invoice."""
    count = len(scores)
    guarded = [s for s in scores if s["guardrail_case"]]
    cited = [s for s in scores if s["cites_expected"]]
    return {
        "cases": count,
        "passed": sum(s["passed"] for s in scores),
        "action_accuracy": sum(s["action"] for s in scores) / count,
        "baseline_always_escalate_action_accuracy": sum(s["escalate_expected"] for s in scores)
        / count,
        "citation_recall": sum(s["citations"] for s in cited) / len(cited),
        "guardrail_cases": len(guarded),
        "guardrail_passed": sum(s["passed"] for s in guarded),
        "failures": [
            {"id": s["id"], "proposal": s["proposal"].model_dump()}
            for s in scores
            if not s["passed"]
        ],
    }


def run(
    cases: list[dict], model_for: Callable[[dict], BaseChatModel], chunks: dict[str, Chunk]
) -> list[tuple[dict, list[AnyMessage]]]:
    """The score and the messages of every case."""
    results = []
    for case in cases:
        proposal, messages = asyncio.run(
            propose(model_for(case), case_tools(case, chunks), case["invoice_id"], case["reasons"])
        )
        results.append((score(case, proposal), messages))
        logger.info("case %s: %s", case["id"], "passed" if results[-1][0]["passed"] else "failed")
    return results


def write_fixture(directory: Path, case: dict, messages: list[AnyMessage], source: str) -> None:
    """The model's messages of one run in the format `ReplayChatModel.from_file` reads."""
    fixture = {
        "case": case["id"],
        "source": source,
        "responses": [recorded(m) for m in messages if isinstance(m, AIMessage)],
    }
    replay_file(directory, case).write_text(
        json.dumps(fixture, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )


def fixture_sources(cases: list[dict], replay_dir: Path) -> dict[str, int]:
    """How many replay fixtures were written by hand and how many by which model."""
    sources: dict[str, int] = {}
    for case in cases:
        source = json.loads(replay_file(replay_dir, case).read_text(encoding="utf-8"))["source"]
        sources[source] = sources.get(source, 0) + 1
    return sources


def evaluate(
    cases_file: Path,
    replay_dir: Path,
    chunks: dict[str, Chunk],
    settings: Settings,
    reports: Path,
    record: bool,
) -> dict:
    """Write reports/agent_eval.json for the configured model, or for the replay fixtures."""
    cases = load_cases(cases_file)
    live = settings.llm_provider != "replay"
    if record and not live:
        raise ValueError("recording needs a real LLM_PROVIDER, not replay")
    model_name = f"{settings.llm_provider}:{settings.llm_model}"
    if live:
        model = chat_model(settings)
        results = run(cases, lambda _case: model, chunks)
    else:
        results = run(
            cases, lambda case: chat_model(settings, replay_file(replay_dir, case)), chunks
        )
    if record:
        for case, (_, messages) in zip(cases, results, strict=True):
            write_fixture(replay_dir, case, messages, f"recorded from {model_name}")
    report = {
        "model": model_name if live else "replay",
        "recorded": record,
        "replay_fixtures": None if live else fixture_sources(cases, replay_dir),
        **summarize([case_score for case_score, _ in results]),
    }
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "agent_eval.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report
