"""
raia.fields
===========

The structured-intake field model.

RAIA agents used to take free prose and let the model infer everything that
mattered. They now declare *typed* inputs, and the rule that governs this
module is deliberate:

    **Every field must be consumed by code.**

A field earns its place by being read by a decision procedure, a retrieval
facet, or a validator. A form of twenty selects that all end up concatenated
into the same prompt is a worse experience than three text areas and produces
the same output, so option vocabularies live next to the engines that read
them (see ``raia.rationale``) and the agent specs import them from there.

Kinds
-----
``textarea`` ``text``    free text (sanitized before it reaches a prompt)
``select``               one value from ``options``
``multiselect``          zero or more values from ``options``
``boolean``              yes / no, stored as ``"yes"`` / ``"no"``
``number``               numeric, stored as ``str`` for prompt rendering
``csv``                  tabular paste, with an optional file upload
``file``                 upload only (text extraction happens in the UI layer)

Values are stored by the UI as ``str`` for single-valued kinds and
``list[str]`` for ``multiselect``. Engines should read them through
:func:`selected`, :func:`chosen` and :func:`is_yes` rather than touching the
raw dict, so a missing key never raises.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

TEXT_KINDS = {"textarea", "text", "csv"}


@dataclass(frozen=True)
class Option:
    """One choice in a ``select`` or ``multiselect`` field.

    ``value`` is the stable code the engines match on; ``label`` is what the
    human reads. Never match on the label.
    """

    value: str
    label: str
    help: str = ""


@dataclass(frozen=True)
class ShowIf:
    """Conditional visibility: show this field when ``key`` holds one of ``values``."""

    key: str
    values: Tuple[str, ...]

    def satisfied(self, inputs: Dict[str, Any]) -> bool:
        current = inputs.get(self.key)
        if isinstance(current, (list, tuple, set)):
            return any(v in current for v in self.values)
        return str(current or "") in self.values


@dataclass
class InputField:
    """One human-provided input, rendered by the UI and read by an engine."""

    key: str
    label: str
    help: str = ""
    kind: str = "textarea"
    options: Sequence[Option] = field(default_factory=tuple)
    required: bool = False
    default: Any = None
    placeholder: str = ""
    show_if: Optional[ShowIf] = None
    group: str = "Inputs"
    height: int = 140
    file_types: Sequence[str] = field(default_factory=tuple)

    # -- helpers -----------------------------------------------------------

    @property
    def is_text(self) -> bool:
        return self.kind in TEXT_KINDS

    @property
    def is_multi(self) -> bool:
        return self.kind == "multiselect"

    def label_for(self, value: str) -> str:
        for opt in self.options:
            if opt.value == value:
                return opt.label
        return value

    def visible(self, inputs: Dict[str, Any]) -> bool:
        return self.show_if is None or self.show_if.satisfied(inputs)

    def is_empty(self, value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, (list, tuple, set)):
            return len(value) == 0
        return not str(value).strip()

    def render(self, value: Any) -> str:
        """Human-readable rendering of a value, for the prompt and the artifact."""
        if self.is_empty(value):
            return "(not provided)"
        if isinstance(value, (list, tuple, set)):
            return "\n".join(f"- {self.label_for(str(v))}" for v in value)
        if self.kind in ("select", "boolean"):
            return self.label_for(str(value))
        return str(value).strip()


# ---------------------------------------------------------------------------
# Safe readers — engines use these, never the raw dict
# ---------------------------------------------------------------------------


def selected(inputs: Dict[str, Any], key: str) -> List[str]:
    """Values chosen in a multiselect, as a list of codes (never ``None``)."""
    raw = inputs.get(key)
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        return [str(v) for v in raw if str(v).strip()]
    return [str(raw)] if str(raw).strip() else []


def chosen(inputs: Dict[str, Any], key: str, default: str = "") -> str:
    """The value of a single-valued field, as a code."""
    raw = inputs.get(key)
    if isinstance(raw, (list, tuple, set)):
        return str(next(iter(raw), default))
    return str(raw).strip() if raw is not None and str(raw).strip() else default


def is_yes(inputs: Dict[str, Any], key: str) -> bool:
    return chosen(inputs, key).lower() in ("yes", "true", "1")


def text_of(inputs: Dict[str, Any], key: str) -> str:
    raw = inputs.get(key)
    return str(raw).strip() if raw is not None else ""


def missing_required(fields: Sequence[InputField], inputs: Dict[str, Any]) -> List[str]:
    """Labels of visible, required fields the human has not filled in."""
    out: List[str] = []
    for f in fields:
        if not f.required or not f.visible(inputs):
            continue
        if f.is_empty(inputs.get(f.key)):
            out.append(f.label)
    return out


def options(*pairs: Tuple[str, str]) -> Tuple[Option, ...]:
    """Terse constructor: ``options(("eu", "European Union"), ...)``."""
    return tuple(Option(value=v, label=l) for v, l in pairs)


YES_NO = options(("yes", "Yes"), ("no", "No"))
YES_NO_UNSURE = options(("yes", "Yes"), ("no", "No"), ("unsure", "Not sure yet"))
