# Review agent

What it does: for an invoice the rules sent to review, the agent reads the invoice, the order,
the vendor history and the rule texts through read-only tools and proposes approve, request a
correction, reject or escalate, with an explanation, citations and optionally a German email to
the vendor. It cannot book: there is no tool that writes, and its proposal is stored as
`pending` until a person decides.

How it works: `agent/mcp_server.py` is a FastMCP server with four tools, `get_invoice`,
`get_purchase_order`, `get_vendor_history` (reads in `db.py`) and `search_rules` (`rag.search`).
`get_invoice` returns field values without evidence (`invoice_summary`) plus the review reasons
and failed checks. `agent/graph.py` builds a LangGraph `StateGraph`: `agent` (the chat model
with the tools bound) and `tools` (`ToolNode`) alternate until the model answers without a tool
call, then `finalize` runs `check_answer`. `propose(model, tools, invoice_id, reasons)` starts
the run with the prompt `agent/prompts/review_en.txt`; `mcp_tools()` connects to the server over
stdio with `langchain-mcp-adapters`. A miss (`models.NotFound`, e.g. a wrong PO number) goes
back to the model as an error message; other errors stop the run in-process, while over MCP the
adapter turns every server error into a message, so a database failure ends as an escalation.
After `MAX_TOOL_ROUNDS` (6) rounds of tool calls the run goes to `finalize`, so a stuck model
escalates instead of hitting LangGraph's recursion limit. `search_rules` returns at most
`rag.MAX_CHUNKS` (8) chunks, because every returned chunk becomes citable.

Guardrails in `check_answer` (SPEC 3.7), in this order: an answer that is not a valid
`AgentProposal` JSON becomes `escalate` with `INVALID_PROPOSAL`; no chunk returned by any
`search_rules` call in the run gives `INSUFFICIENT_EVIDENCE`; no citations, or a citation that
no `search_rules` call returned, gives `UNSUPPORTED_EXPLANATION`. An overruled proposal keeps
none of the model's text, citations or email, only a fixed explanation and the code in
`reasons`.

Why this way: the decision stays with the rules engine and a person; the model only explains,
so the worst a wrong or manipulated answer can do is a bad suggestion that a person reads. The
citation check compares with tool output of the same run, not with the whole corpus, so a model
cannot cite a rule it never saw. A fourth code, `INVALID_PROPOSAL`, was added because a live
model can answer in prose or with code fences; repairing the JSON would be guessing.

How it is tested: `tests/unit/agent/test_graph.py` drives the graph with inline replay messages
and the case tools: a cited proposal stands, an unknown or missing citation, no search, an empty
search and invalid JSON each escalate with their code, a miss returns to the model, a `KeyError` in a tool stops
the run, a model stuck in tool calls is cut off and escalates, and a failed search is no evidence; for all 32 eval cases every kept citation came from a tool call in
the run. `test_mcp_server.py` lists the tools in process and over stdio (a real subprocess): the
four read-only tools and nothing else. The tool functions run against a fake database.

Limits: never run with a real model or Postgres. The tools open one connection per call. The
agent sees field values but not their evidence or confidence. Prompt injection is only checked
by one eval case; the guardrails limit what a manipulated answer can claim, not what it says
inside a valid citation.
