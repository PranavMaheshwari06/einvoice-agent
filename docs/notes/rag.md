# Rule retrieval (RAG)

What it does: `agent/rag.py` turns the rule texts the agent may cite into chunks with stable
source ids, stores them with e5 embeddings in the `rule_chunks` table, and finds the chunks
closest to a query. If even the best chunk is not similar enough, it returns nothing, so the
agent has no text to cite and must escalate.

How it works: `ustg_chunks` reads the gesetze-im-internet.de XML and makes one chunk per Absatz
of § 14 (`UStG-14-4`), `policy_chunks` one per `##` heading of `data/rules/ap_policy.md`
(`AP-price-tolerance`), `br_de_chunks` one per BR-DE rule from the XRechnung UBL schematron of
the validator configuration (`BR-DE-15`, 39 rules, message text without the `[id]` prefix).
`corpus` joins them and refuses duplicate ids. `einvoice db index` embeds `title + body` with
`E5Encoder(prefix="passage: ")` and replaces the table (`store`). `search` embeds the query with
the `"query: "` prefix, takes the `k` nearest by cosine distance (`<=>`), and `supported` drops
all of them when the best similarity is below `MIN_SIMILARITY`. `k` is capped at `MAX_CHUNKS` (8),
because every returned chunk becomes citable for the agent.

Why this way: the same e5 model as the GL coder, so there is one encoder and one download. The
prefixes follow the e5 authors' retrieval evaluation (`microsoft/unilm`, `e5/mteb_beir_eval.py`:
`query: ` for queries, `passage: ` for documents). Vectors go to Postgres as pgvector's text
literal, so no type adapter has to be registered on each connection. Rebuilding the whole table
is simpler than an upsert and the corpus has about fifty chunks. A separate vector database
was rejected by the SPEC.

How it is tested: `tests/unit/agent/test_rag.py` runs the chunkers on the real AP policy and on
an unchanged copy of the schematron (39 rules, no BR-DEX), the UStG chunker on a hand-written
file in the gesetze-im-internet.de structure, the threshold rule, and `store`/`search` against
a fake connection with the hashing stub encoder. Nothing here ran against pgvector or e5.

Limits: `MIN_SIMILARITY = 0.80` is provisional; e5 gives unrelated texts high cosine scores, so
the value must be set from live queries. The UStG XML structure is unconfirmed (no access to
gesetze-im-internet.de from the cloud). Long chunks such as § 14 Abs. 4 may exceed the 512
tokens e5 reads and lose their end. Schematron messages with computed parts (BR-DE-18, the
BR-DE-CVD rules) lose those parts.
