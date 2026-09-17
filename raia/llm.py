"""
raia.llm
========

Provider-agnostic LLM factory and the single call site every agent goes
through.

The RAIA architecture specifies Claude as the reference model but requires the
system to remain provider-agnostic: switching models is a configuration
change. This module is that configuration point, and it also owns two things
that belong next to the call rather than scattered through the agents:

* **Transient-failure retry.** A provider overload during an evaluation
  session used to lose the attempt and the tester's place in the walkthrough.
  Overload, rate-limit and timeout responses are retried with backoff;
  everything else is raised immediately, because retrying a bad request just
  spends someone's budget.
* **Finish reason.** A response truncated at the token limit looks finished.
  The reason the model stopped is carried back so a validator can say so.

Supported providers (``RAIA_LLM_PROVIDER``):

* ``anthropic`` — Claude models via ``langchain-anthropic`` (default).
* ``openai``    — GPT models via ``langchain-openai`` (optional dependency).
* ``mock``      — deterministic canned responses, no network, no API key.
"""

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from . import config

#: Substrings that mark a provider failure as worth retrying. Anything else is
#: a bad request, an auth problem or a bug, and retrying it is pure waste.
TRANSIENT_MARKERS = (
    "overloaded", "rate limit", "rate_limit", "too many requests", "429", "529",
    "timeout", "timed out", "temporarily unavailable", "service unavailable",
    "503", "502", "connection reset", "connection error",
)


@dataclass
class ChatResponse:
    """One model reply, with the metadata the validators need."""

    text: str
    finish_reason: Optional[str] = None
    retries: int = 0
    raw: Optional[AIMessage] = None


class MockChatModel(BaseChatModel):
    """A stand-in chat model that satisfies the output contract.

    It is a proper test double rather than a lorem generator: it reads the
    contract hints the agent put in the prompt (verdict keys, checklist keys,
    the identifiers the rule engine assigned, a citation that really was
    retrieved) and returns a RAIA record that validates against the agent's
    schema and exercises every section of it.

    That matters because it lets the whole chain — rationale engine, prompt
    assembly, record parsing and finalisation, rendering, validators,
    persistence, audit trail — be exercised offline, in CI and in the smoke
    test, without an API key. What it cannot do is produce a *good* analysis,
    which is exactly why the app refuses to serve mock output to an evaluator.
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
        from .contract import mock as contract_mock

        prompt = ""
        for m in messages:
            content = m.content
            if isinstance(content, list):
                content = " ".join(str(p) for p in content)
            prompt += str(content) + "\n"

        text = contract_mock.reply(prompt)
        message = AIMessage(content=text, response_metadata={"stop_reason": "end_turn"})
        return ChatResult(generations=[ChatGeneration(message=message)])


def get_chat_model() -> BaseChatModel:
    """Return the chat model selected by configuration."""
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
        return ChatAnthropic(model=config.LLM_MODEL, max_tokens=config.LLM_MAX_TOKENS,
                             **_temperature_kwargs())

    if provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Provider 'openai' selected but langchain-openai is not "
                "installed. Run: pip install langchain-openai"
            ) from exc
        return ChatOpenAI(model=config.LLM_MODEL, max_tokens=config.LLM_MAX_TOKENS,
                          **_temperature_kwargs())

    raise ValueError(
        f"Unknown RAIA_LLM_PROVIDER '{provider}'. Use 'anthropic', 'openai', or 'mock'."
    )


def _temperature_kwargs() -> Dict[str, Any]:
    return {} if config.LLM_TEMPERATURE is None else {"temperature": config.LLM_TEMPERATURE}


def rejects_temperature(exc: BaseException) -> bool:
    """The provider refused the request because the model takes no temperature."""
    low = f"{exc}".lower()
    return "temperature" in low and any(
        word in low for word in ("deprecated", "not supported", "unsupported", "not allowed",
                                 "does not support", "invalid")
    )


def is_transient(exc: BaseException) -> bool:
    low = f"{type(exc).__name__} {exc}".lower()
    return any(marker in low for marker in TRANSIENT_MARKERS)


def finish_reason_of(message: AIMessage) -> Optional[str]:
    """Normalize the provider's stop reason across SDKs."""
    meta: Dict[str, Any] = getattr(message, "response_metadata", None) or {}
    for key in ("stop_reason", "finish_reason"):
        value = meta.get(key)
        if value:
            return str(value)
    return None


def invoke_chat(messages: Sequence[BaseMessage], model: Optional[BaseChatModel] = None) -> ChatResponse:
    """Call the configured model, retrying only what is worth retrying."""
    llm = model or get_chat_model()
    attempts = max(0, config.LLM_RETRIES) + 1
    last: BaseException = RuntimeError("no attempt was made")
    dropped_temperature = False

    for i in range(attempts):
        try:
            message = llm.invoke(list(messages))
        except BaseException as exc:  # noqa: BLE001 - re-raised below
            last = exc
            if (model is None and not dropped_temperature and config.LLM_TEMPERATURE is not None
                    and rejects_temperature(exc)):
                # The model takes no temperature. Stop sending one for the rest of
                # this process, so the provenance of every draft states what was
                # actually sent, and retry immediately.
                config.LLM_TEMPERATURE = None
                dropped_temperature = True
                llm = get_chat_model()
                try:
                    message = llm.invoke(list(messages))
                except BaseException as retry_exc:  # noqa: BLE001
                    last = retry_exc
                    if not is_transient(retry_exc) or i == attempts - 1:
                        raise
                    time.sleep(config.LLM_RETRY_BASE_DELAY * (2 ** i))
                    continue
                else:
                    return _response(message, i)
            if not is_transient(exc) or i == attempts - 1:
                raise
            time.sleep(config.LLM_RETRY_BASE_DELAY * (2 ** i))
            continue

        return _response(message, i)

    raise last


def _response(message: Any, retries: int) -> ChatResponse:
    content = message.content
    if isinstance(content, list):  # multimodal / block content
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in content
        )
    return ChatResponse(
        text=str(content),
        finish_reason=finish_reason_of(message),
        retries=retries,
        raw=message if isinstance(message, AIMessage) else None,
    )
