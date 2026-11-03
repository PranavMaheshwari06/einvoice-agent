# LLM provider

What it does: `llm.chat_model(settings)` returns the chat model that extraction and the review
agent use, chosen by `LLM_PROVIDER`. With `replay` it returns `ReplayChatModel`, which answers
with recorded messages, so tests and CI never call a provider and never need a key.

How it works: `chat_model` is one if/elif. `replay` reads a fixture file
(`{"case", "source", "responses": [{"content", "tool_calls"}]}`) and hands out the responses in
order; `bind_tools` returns the model itself because the recording already contains the tool
calls. `ollama` is `ChatOpenAI` against `OLLAMA_BASE_URL/v1`, `openai` is `ChatOpenAI` with the
key and base URL from `Settings` (this also covers OpenAI-compatible endpoints such as Gemini),
`anthropic` is `ChatAnthropic`. `complete(model, prompt)` turns a chat model into the
`complete(prompt) -> str` that `extract_invoice` and `pipeline.process` take; `recorded(message)`
writes a message back in the fixture format.

Why this way: one function with a branch per provider is all the SPEC needs; a registry or a
provider class per vendor would be an interface with one caller. Keys come from `Settings`
because pydantic-settings reads `.env` without copying it into `os.environ`, where the client
libraries would look. Replay is a real `BaseChatModel` so the LangGraph code under test is the
same code that runs with a live model.

How it is tested: `tests/unit/test_llm.py` replays messages in order, refuses a call past the
recording, round-trips a recorded tool call, and checks that each live branch is built with the
model, base URL and key from `Settings` (constructing the client opens no connection). It does
not prove that any provider answers; that is the A5 live provider probe.

Limits: no temperature or retry settings, so a live run is not reproducible and a rate limit
fails the run. The replay model does not compare the prompt with the one that was recorded, so a
changed prompt does not invalidate old fixtures; re-record after a prompt change.
