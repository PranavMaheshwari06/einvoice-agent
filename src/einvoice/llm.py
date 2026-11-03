"""The chat model behind extraction and the agent, chosen by LLM_PROVIDER (SPEC 3.8)."""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from einvoice.config import Settings


class ReplayChatModel(BaseChatModel):
    """Answers with recorded messages in order, so tests and CI never call a provider."""

    responses: list[AIMessage]
    position: int = 0

    @classmethod
    def from_file(cls, path: Path) -> "ReplayChatModel":
        recorded = json.loads(path.read_text(encoding="utf-8"))["responses"]
        return cls(responses=[AIMessage(**response) for response in recorded])

    @property
    def _llm_type(self) -> str:
        return "replay"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ReplayChatModel":
        return self

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs):
        if self.position == len(self.responses):
            raise RuntimeError(f"replay has only {len(self.responses)} recorded responses")
        message = self.responses[self.position]
        self.position += 1
        return ChatResult(generations=[ChatGeneration(message=message)])


def chat_model(settings: Settings, replay_file: Path | None = None) -> BaseChatModel:
    provider = settings.llm_provider
    if provider == "replay":
        if replay_file is None:
            raise ValueError("LLM_PROVIDER=replay needs a recorded replay file")
        return ReplayChatModel.from_file(replay_file)
    if provider == "ollama":
        from langchain_openai import ChatOpenAI

        # Ollama serves the OpenAI API under /v1 and ignores the key, which the client requires.
        return ChatOpenAI(
            model=settings.llm_model, base_url=f"{settings.ollama_base_url}/v1", api_key="ollama"
        )
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=settings.llm_model, api_key=settings.anthropic_api_key)
    raise ValueError(f"unknown LLM_PROVIDER {provider!r}: use replay, ollama, openai or anthropic")


def complete(model: BaseChatModel, prompt: str) -> str:
    """The `complete(prompt) -> str` that extraction takes, on top of a chat model."""
    return model.invoke(prompt).text


def recorded(message: AIMessage) -> dict:
    """One response in the replay file format that `ReplayChatModel.from_file` reads."""
    return {"content": message.content, "tool_calls": message.tool_calls}
