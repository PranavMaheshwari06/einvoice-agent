# Agent evaluation

What it does: `einvoice agent-eval` plays the 32 cases of `evals/agent_cases.yaml` through the
review agent and writes `reports/agent_eval.json`: how many proposals had the expected action,
guardrail codes and citations, next to a baseline that escalates every invoice. With
`--record` and a real `LLM_PROVIDER` it saves the model's messages as the cases' replay
fixtures.

How it works: a case fixes the world the tools see: the invoice summary, review reasons, failed
checks, purchase order, vendor history and the source ids `search_rules` returns (for any
query). `evals.case_tools` builds tools with the names and argument schemas of the MCP tools
that answer from the case; chunk texts come from `rag.corpus`. `run` calls `graph.propose` per
case with `ReplayChatModel` (fixture `tests/fixtures/replay/agent_<id>.json`) or the live model,
`score` compares action, guardrail codes and required citations, `summarize` adds the
always-escalate baseline and lists failures with the full proposal. The report names the model
and how many fixtures are hand-written or recorded.

Why this way: fixing the tool answers makes a case depend only on the model, so a recorded run
replays identically and the numbers compare models, not database states. Retrieval quality is a
separate question (rag note). The baseline is "always escalate" because it is what a system
without an agent does and it is never wrong in a harmful way.

How it is tested: `tests/unit/agent/test_evals.py` checks that every case has one fixture, a
known action, citations among its rules and the same invoice keys as `invoice_summary`; that the
AP and BR-DE ids exist in the real sources; that all hand-written replays reach the expected
proposal; the baseline arithmetic; that a wrong action is reported with its proposal; and that a
recording replays to the same result.

Limits: the 32 replay fixtures are written by hand to match the expectations, so a replay report
shows that the pipeline works, not that a model is good; only a recorded run measures a model.
The expectations are mine, not a reviewer's. The UStG ids in the cases are checked only when
the corpus is built from the fetched law text. `search_rules` ignores the query, so a model that
searches badly is not penalised here.
