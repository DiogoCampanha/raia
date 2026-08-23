"""
raia.llm
========

Provider-agnostic LLM factory.

The RAIA architecture specifies Claude as the reference LLM but requires
the system to remain provider-agnostic through the LangChain abstraction:
"switching models is simply a configuration change". This module is that
configuration point: every agent obtains its chat model exclusively through
:func:`get_chat_model`, never by instantiating a provider class directly.

Supported providers (set via RAIA_LLM_PROVIDER):

* ``anthropic`` -- Claude models via ``langchain-anthropic`` (default).
* ``openai``    -- GPT models via ``langchain-openai`` (optional dependency).
* ``mock``      -- deterministic canned responses, no network, no API key.
                   Used by the smoke tests and by the UI "demo mode".
"""

from typing import Any, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from . import config


class MockChatModel(BaseChatModel):
    """A stand-in chat model producing deterministic, plausible output.

    It lets users explore the full pipeline (and lets CI test it) without
    an API key. The response echoes the last user message header so that
    each agent's mock output is at least stage-appropriate.
    """

    @property
    def _llm_type(self) -> str:  # noqa: D401 - LangChain hook
        return "raia-mock"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        # Take the first line of the last human message as a "task hint".
        last = messages[-1].content if messages else ""
        if isinstance(last, list):  # multimodal message content
            last = " ".join(str(p) for p in last)
        hint = str(last).strip().splitlines()[0][:120] if last else "task"
        text = (
            "> **[MOCK MODE]** No LLM was called. Set `RAIA_LLM_PROVIDER=anthropic` "
            "and provide `ANTHROPIC_API_KEY` in `.env` for real analyses.\n\n"
            f"## Mock analysis\n\nTask received: *{hint}*\n\n"
            "### Findings\n\n"
            "1. This is a deterministic placeholder produced by the mock model. "
            "[Source: NIST AI RMF — GOVERN 1.1 | authority: advisory]\n"
            "2. A real run would ground every recommendation in retrieved "
            "norm excerpts and cite them like the line above.\n\n"
            "### Open issues\n\n- None (mock).\n"
        )
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])


def get_chat_model() -> BaseChatModel:
    """Return the chat model selected by configuration.

    Raises a clear, user-actionable error when the chosen provider's
    package or API key is missing.
    """
    provider = config.LLM_PROVIDER

    if provider == "mock":
        return MockChatModel()

    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Provider 'anthropic' selected but langchain-anthropic is not "
                "installed. Run: pip install langchain-anthropic"
            ) from exc
        return ChatAnthropic(
            model=config.LLM_MODEL,
            temperature=config.LLM_TEMPERATURE,
            max_tokens=config.LLM_MAX_TOKENS,
        )

    if provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Provider 'openai' selected but langchain-openai is not "
                "installed. Run: pip install langchain-openai"
            ) from exc
        return ChatOpenAI(
            model=config.LLM_MODEL,
            temperature=config.LLM_TEMPERATURE,
            max_tokens=config.LLM_MAX_TOKENS,
        )

    raise ValueError(
        f"Unknown RAIA_LLM_PROVIDER '{provider}'. "
        "Use 'anthropic', 'openai', or 'mock'."
    )
