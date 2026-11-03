import json

import pytest
from langchain_core.messages import AIMessage

from einvoice.config import Settings
from einvoice.llm import ReplayChatModel, chat_model, complete, recorded


def write_replay(path, responses):
    path.write_text(json.dumps({"case": "x", "source": "hand-written", "responses": responses}))
    return path


def test_replay_returns_recorded_messages_in_order(tmp_path):
    path = write_replay(
        tmp_path / "case.json",
        [
            {
                "content": "",
                "tool_calls": [{"name": "get_invoice", "args": {"invoice_id": 1}, "id": "c1"}],
            },
            {"content": "done"},
        ],
    )
    model = ReplayChatModel.from_file(path)

    first = model.invoke("anything")
    second = model.invoke("anything else")

    assert first.tool_calls[0]["name"] == "get_invoice"
    assert first.tool_calls[0]["args"] == {"invoice_id": 1}
    assert second.text == "done"


def test_replay_refuses_a_call_beyond_the_recording(tmp_path):
    model = ReplayChatModel.from_file(write_replay(tmp_path / "case.json", [{"content": "one"}]))
    model.invoke("first")
    with pytest.raises(RuntimeError, match="only 1 recorded"):
        model.invoke("second")


def test_replay_binds_tools_to_itself(tmp_path):
    model = ReplayChatModel.from_file(write_replay(tmp_path / "case.json", [{"content": "x"}]))
    assert model.bind_tools([]) is model


def test_recorded_message_replays_unchanged(tmp_path):
    message = AIMessage(
        content="", tool_calls=[{"name": "search_rules", "args": {"query": "§ 14"}, "id": "c7"}]
    )
    path = write_replay(tmp_path / "case.json", [recorded(message)])
    replayed = ReplayChatModel.from_file(path).invoke("prompt")
    assert replayed.tool_calls == message.tool_calls


def test_complete_returns_the_text_of_the_answer(tmp_path):
    model = ReplayChatModel.from_file(write_replay(tmp_path / "case.json", [{"content": "{}"}]))
    assert complete(model, "prompt") == "{}"


def test_replay_provider_needs_a_file():
    with pytest.raises(ValueError, match="replay file"):
        chat_model(Settings(llm_provider="replay"))


def test_unknown_provider_is_refused():
    with pytest.raises(ValueError, match="unknown LLM_PROVIDER 'gpt'"):
        chat_model(Settings(llm_provider="gpt"))


def test_ollama_uses_the_openai_api_under_v1():
    model = chat_model(
        Settings(llm_provider="ollama", llm_model="qwen3:4b", ollama_base_url="http://host:11434")
    )
    assert model.openai_api_base == "http://host:11434/v1"
    assert model.model_name == "qwen3:4b"


def test_openai_takes_key_and_base_url_from_settings():
    settings = Settings(
        llm_provider="openai",
        llm_model="gemini-flash",
        openai_api_key="test-key",
        openai_base_url="https://example.invalid/v1",
    )
    model = chat_model(settings)
    assert model.openai_api_base == "https://example.invalid/v1"
    assert model.openai_api_key.get_secret_value() == "test-key"


def test_anthropic_takes_the_key_from_settings():
    settings = Settings(llm_provider="anthropic", llm_model="claude-x", anthropic_api_key="k")
    model = chat_model(settings)
    assert model.model == "claude-x"
    assert model.anthropic_api_key.get_secret_value() == "k"
