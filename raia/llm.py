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

import re
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
    contract the agent declared in the prompt (required sections, machine-block
    keys, the computed verdict, the engine's open issues) and produces a
    document that conforms to it, citing an excerpt that really was retrieved.

    That matters because it lets the whole chain — rationale engine, prompt
    assembly, validators, persistence, audit trail — be exercised offline, in
    CI and in the smoke test, without an API key. What it cannot do is produce
    a *good* analysis, which is exactly why the app refuses to serve mock
    output to an evaluator.
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
        prompt = ""
        for m in messages:
            content = m.content
            if isinstance(content, list):
                content = " ".join(str(p) for p in content)
            prompt += str(content) + "\n"

        sections = _csv_after(prompt, "RAIA-CONTRACT-SECTIONS:")
        keys = _csv_after(prompt, "RAIA-CONTRACT-KEYS:")
        citation = _first_citation(prompt)
        verdicts = _computed_verdicts(prompt)
        issues = _engine_issues(prompt)
        register = _register_ids(prompt)

        body = [
            "> **[MOCK MODE]** No model was called. This text conforms to the output "
            "contract so the pipeline can be exercised offline; it is not an analysis.",
            "",
        ]
        for section in sections or ["Analysis"]:
            body.append(f"## {section}")
            if section.strip().lower() == "open issues":
                body.extend(f"- {i}" for i in issues) if issues else body.append(
                    "- None raised by the rule engine."
                )
            else:
                body.append(
                    f"Placeholder analysis for this section. {citation}"
                    if citation else "Placeholder analysis for this section."
                )
                if register and section == (sections or [""])[0]:
                    body.append("Register accounted for: " + ", ".join(register) + ".")
            body.append("")

        block = ["```raia"]
        for key in keys:
            if key == "verdict.agrees_with_screen":
                block.append("verdict.agrees_with_screen: yes")
            elif key.startswith("verdict."):
                block.append(f"{key}: {verdicts.get(key[len('verdict.'):], 'unknown')}")
            else:
                block.append(f"{key}: covered — placeholder declaration from mock mode.")
        block.append("```")

        text = "\n".join(body + block)
        message = AIMessage(content=text, response_metadata={"stop_reason": "end_turn"})
        return ChatResult(generations=[ChatGeneration(message=message)])


def _csv_after(prompt: str, marker: str) -> List[str]:
    for line in prompt.splitlines():
        if line.strip().startswith(marker):
            raw = line.split(marker, 1)[1]
            return [p.strip() for p in raw.split(",") if p.strip()]
    return []


def _first_citation(prompt: str) -> str:
    """A citation tag from the retrieved excerpts — never the preamble's example.

    The system preamble contains an illustrative tag. Citing it would be
    exactly the fabrication the citation validator exists to catch, so the
    search starts at the excerpt block.
    """
    start = prompt.find("## Retrieved norm excerpts")
    if start == -1:
        return ""
    m = re.search(r"--- Excerpt \d+ (\[Source:[^\]]+\])", prompt[start:])
    return m.group(1) if m else ""


def _register_ids(prompt: str) -> List[str]:
    """Identifiers the rule engine put in the computed block.

    Echoing them lets the traceability validators be exercised offline: a smoke
    test that cannot reach a passing state would not tell us whether the checks
    work or whether the mock is simply silent.
    """
    start = prompt.find("### Computed by code")
    end = prompt.find("## Retrieved norm excerpts")
    if start == -1 or end == -1:
        return []
    block = prompt[start:end]
    out: List[str] = []
    for pattern in (r"\bEVR-\d+\b", r"\bAC-S\d+-\d+\b", r"(?<![\w-])S\d+(?![\w-])",
                    r"(?<![\w])#\d{1,2}(?![\w])"):
        for m in re.findall(pattern, block):
            if m not in out:
                out.append(m)
    return out


def _computed_verdicts(prompt: str) -> Dict[str, str]:
    """Read the rule engine's verdict lines out of the computed block."""
    out: Dict[str, str] = {}
    for m in re.finditer(r"^- `([a-z0-9_]+)`: \*\*(.+?)\*\*$", prompt, re.M):
        out[m.group(1)] = m.group(2)
    return out


def _engine_issues(prompt: str) -> List[str]:
    block = re.search(
        r"\*\*Open issues raised by the rule engine[^\n]*\*\*\n(.*?)(?:\n\*\*|\n## |\Z)",
        prompt,
        re.S,
    )
    if not block:
        return []
    return [l.strip("- ").strip() for l in block.group(1).splitlines() if l.strip().startswith("-")]


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
        f"Unknown RAIA_LLM_PROVIDER '{provider}'. Use 'anthropic', 'openai', or 'mock'."
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

    for i in range(attempts):
        try:
            message = llm.invoke(list(messages))
        except BaseException as exc:  # noqa: BLE001 - re-raised below
            last = exc
            if not is_transient(exc) or i == attempts - 1:
                raise
            time.sleep(config.LLM_RETRY_BASE_DELAY * (2 ** i))
            continue

        content = message.content
        if isinstance(content, list):  # multimodal / block content
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in content
            )
        return ChatResponse(
            text=str(content),
            finish_reason=finish_reason_of(message),
            retries=i,
            raw=message if isinstance(message, AIMessage) else None,
        )

    raise last
