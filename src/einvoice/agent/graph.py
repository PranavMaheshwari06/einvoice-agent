"""The review agent: the model calls read-only tools until it answers; `finalize` checks it."""

import json
import os
import sys
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal, NotRequired, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel, ValidationError

from einvoice.models import NotFound

PROMPT_FILE = Path(__file__).parent / "prompts" / "review_en.txt"
# Rounds of tool calls before the run is cut off; the prompt needs three, a stuck model escalates.
MAX_TOOL_ROUNDS = 6
GUARDRAIL_EXPLANATIONS = {
    "INVALID_PROPOSAL": "The model's answer was not a valid proposal; a person decides.",
    "INSUFFICIENT_EVIDENCE": "No rule text was found for this invoice; a person decides.",
    "UNSUPPORTED_EXPLANATION": (
        "The explanation did not cite rule texts found in this run; a person decides."
    ),
}


class AgentProposal(BaseModel):
    """What the agent proposes; `reasons` holds the guardrail codes that overruled the model."""

    action: Literal["approve_booking", "request_correction", "reject", "escalate"]
    explanation: str
    citations: list[str] = []
    vendor_email_de: str | None = None
    reasons: list[str] = []


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    proposal: NotRequired[AgentProposal]


def retrieved_sources(messages: Sequence[AnyMessage]) -> set[str]:
    """Source ids of every chunk that `search_rules` returned in this run."""
    sources = set()
    for message in messages:
        found = isinstance(message, ToolMessage) and message.name == "search_rules"
        if found and message.status == "success":
            sources.update(chunk["source_id"] for chunk in json.loads(message.text)["chunks"])
    return sources


def _escalate(reason: str) -> AgentProposal:
    return AgentProposal(
        action="escalate", explanation=GUARDRAIL_EXPLANATIONS[reason], reasons=[reason]
    )


def check_answer(messages: Sequence[AnyMessage]) -> AgentProposal:
    """The guardrails of SPEC 3.7, applied to the model's last message."""
    try:
        proposal = AgentProposal.model_validate_json(messages[-1].text)
    except ValidationError:
        return _escalate("INVALID_PROPOSAL")
    sources = retrieved_sources(messages)
    if not sources:
        return _escalate("INSUFFICIENT_EVIDENCE")
    if not proposal.citations or not set(proposal.citations) <= sources:
        return _escalate("UNSUPPORTED_EXPLANATION")
    return proposal.model_copy(update={"reasons": []})


def build_graph(model: BaseChatModel, tools: Sequence[BaseTool]):
    bound = model.bind_tools(tools)

    async def agent(state: AgentState) -> dict:
        return {"messages": [await bound.ainvoke(state["messages"])]}

    def route(state: AgentState) -> str:
        rounds = sum(isinstance(message, AIMessage) for message in state["messages"])
        wants_tools = bool(state["messages"][-1].tool_calls)
        return "tools" if wants_tools and rounds < MAX_TOOL_ROUNDS else "finalize"

    def finalize(state: AgentState) -> dict:
        return {"proposal": check_answer(state["messages"])}

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent)
    # A miss (wrong PO number) goes back to the model and other errors stop the run. Over MCP the
    # adapter returns every server error as a message, so there a database failure escalates.
    graph.add_node("tools", ToolNode(tools, handle_tool_errors=NotFound))
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route, ["tools", "finalize"])
    graph.add_edge("tools", "agent")
    graph.add_edge("finalize", END)
    return graph.compile()


async def propose(
    model: BaseChatModel, tools: Sequence[BaseTool], invoice_id: int, reasons: list[str]
) -> tuple[AgentProposal, list[AnyMessage]]:
    """Run the agent on one review invoice; the messages are returned for recording."""
    messages = [
        SystemMessage(PROMPT_FILE.read_text(encoding="utf-8")),
        HumanMessage(f"Invoice id {invoice_id} is in review. Reasons: {', '.join(reasons)}."),
    ]
    state = await build_graph(model, tools).ainvoke({"messages": messages})
    return state["proposal"], state["messages"]


@asynccontextmanager
async def mcp_tools() -> AsyncIterator[list[BaseTool]]:
    """The MCP server's tools over stdio, as LangChain tools the graph can bind."""
    # The stdio client passes only a minimal environment; the server needs DATABASE_URL.
    server = StdioServerParameters(
        command=sys.executable, args=["-m", "einvoice.agent.mcp_server"], env=dict(os.environ)
    )
    async with stdio_client(server) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        yield await load_mcp_tools(session)
