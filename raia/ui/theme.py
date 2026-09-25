"""
raia.ui.theme
=============

Visual vocabulary shared by every page: the CSS layer, Material Symbols icon
names, and the one mapping from a stage status or risk level to a label and a
colour. No emoji anywhere in the interface: icons are Material Symbols, which
Streamlit renders natively and which read consistently across platforms.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict

import streamlit as st

ASSETS = Path(__file__).parent / "assets"
LOGO = str(ASSETS / "logo.svg")
ICON = str(ASSETS / "icon.svg")


class I:  # noqa: E742 - short on purpose: I.HOME reads well at call sites
    HOME = ":material/space_dashboard:"
    PROJECT = ":material/folder_open:"
    AGENTS = ":material/hub:"
    ASSESSMENT = ":material/fact_check:"
    GUIDE = ":material/school:"
    SETTINGS = ":material/settings:"
    PRIVACY = ":material/policy:"
    RESEARCH = ":material/analytics:"
    ADD = ":material/add:"
    DEMO = ":material/science:"
    OPEN = ":material/arrow_forward:"
    BACK = ":material/arrow_back:"
    RUN = ":material/play_arrow:"
    APPROVE = ":material/check:"
    REJECT = ":material/refresh:"
    REVISE = ":material/edit:"
    CONFIRM = ":material/task_alt:"
    DOWNLOAD = ":material/download:"
    EXAMPLE = ":material/content_paste:"
    RESTORE = ":material/restore:"
    DISCARD = ":material/delete:"
    LOCK = ":material/lock:"
    WARN = ":material/warning:"
    ERROR = ":material/error:"
    INFO = ":material/info:"
    OK = ":material/check_circle:"
    MAIL = ":material/mail:"
    PERSON = ":material/person:"
    GROUP = ":material/group:"
    ISSUE = ":material/gavel:"
    HISTORY = ":material/history:"
    DOCS = ":material/description:"
    OVERVIEW = ":material/dashboard:"
    LOGOUT = ":material/logout:"
    SAVE = ":material/save:"
    SHIELD = ":material/verified_user:"
    EVIDENCE = ":material/menu_book:"
    COMPUTE = ":material/calculate:"
    READ = ":material/visibility:"
    MOCK = ":material/science:"
    SUGGEST = ":material/lightbulb:"


#: status -> (label, badge colour, icon)
STATUS = {
    "approved": ("Approved", "green", ":material/check_circle:"),
    "stale": ("Needs review", "orange", ":material/sync_problem:"),
    "in_review": ("Awaiting review", "violet", ":material/rate_review:"),
    "ready": ("Ready to run", "blue", ":material/play_circle:"),
    "blocked": ("Waiting on upstream", "gray", ":material/lock:"),
}

#: risk level (see raia.projects.risk_summary) -> (badge colour, icon)
RISK = {
    "critical": ("red", ":material/block:"),
    "high": ("orange", ":material/priority_high:"),
    "medium": ("yellow", ":material/visibility:"),
    "low": ("green", ":material/check:"),
    "none": ("gray", ":material/remove:"),
}

LAYER_CLASS = {"Product": "product", "Dev": "dev", "Ops": "ops"}


# ---- Agent identity ------------------------------------------------------------------
#
# Each agent has its own colour, icon, question and header pattern, so a person
# can tell at a glance which agent they are working with. The identity is
# *chrome only*: the page header, the stage rail, navigation and the primary
# button. Inside a record, colour keeps its one meaning — the tones in
# theme.css (critical, high, medium, on track, a decision for a person) — and is
# the same for every agent. That is why no agent colour may equal a tone colour
# (tests/test_ui.py checks it), and why an agent is never told apart by colour
# alone: its icon and name are always shown with it.

#: The colours ``theme.css`` reserves for meaning inside a record.
TONES = {"critical": "#dc2626", "high": "#ea580c", "medium": "#d97706", "low": "#64748b",
         "ok": "#059669", "decision": "#7c3aed"}


@dataclass(frozen=True)
class AgentLook:
    icon: str       # Material Symbols name
    ink: str        # colour on the light theme; white text on it passes WCAG AA
    glow: str       # colour on the dark theme; passes AA on the dark background
    question: str   # the one question the agent answers, in the team's words
    motif: str      # SVG body of the faint header pattern (viewBox 0 0 240 120); see motif_url

    @property
    def material(self) -> str:
        return f":material/{self.icon}:"


_GAUGE = ('<path d="M40 118a80 80 0 0 1 160 0"/><path d="M62 118a58 58 0 0 1 116 0"/>'
          '<path d="M84 118a36 36 0 0 1 72 0"/><path d="M120 118 158 62" stroke-width="5"/>'
          '<circle cx="120" cy="118" r="7" fill="currentColor"/>')
_CHECKLIST = "".join(
    f'<rect x="48" y="{y}" width="18" height="18" rx="4"/><path d="m52 {y + 9} 4 4 7-8"/>'
    f'<path d="M80 {y + 9}h{w}"/>' for y, w in ((10, 110), (38, 84), (66, 120), (94, 70)))
_CARDS = ('<rect x="96" y="8" width="120" height="74" rx="10"/><rect x="72" y="24" width="120" height="74" rx="10"/>'
          '<rect x="48" y="40" width="120" height="74" rx="10" fill="currentColor" fill-opacity=".08"/>'
          '<path d="M64 62h70M64 78h88M64 94h52"/>')
_LENS = ("".join(f'<circle cx="{x}" cy="{y}" r="2.5" fill="currentColor" stroke="none"/>'
                 for x in range(40, 230, 22) for y in range(14, 120, 22))
         + '<circle cx="132" cy="58" r="34" stroke-width="5"/><path d="m157 83 32 32" stroke-width="9"/>')
_WAVE = ('<path d="M20 44h210" stroke-dasharray="6 7"/>'
         '<path d="M20 92c18 0 22-30 40-30s22 34 40 34 22-44 40-44 22 26 40 26 20-52 50-60" stroke-width="5"/>'
         '<path d="M20 116h210"/>')

AGENT_LOOK: Dict[str, AgentLook] = {
    "risk_classifier": AgentLook("balance", "#3730a3", "#a5b4fc",
                                 "How risky is this product under the law?", _GAUGE),
    "requirements_reviewer": AgentLook("checklist", "#0369a1", "#7dd3fc",
                                       "Do the requirements cover the ethical duties?", _CHECKLIST),
    "story_refiner": AgentLook("edit_note", "#0f766e", "#5eead4",
                               "Are the stories ready to build responsibly?", _CARDS),
    "auditor": AgentLook("manage_search", "#a21caf", "#f0abfc",
                         "Is there evidence the controls were built?", _LENS),
    "drift_monitor": AgentLook("monitoring", "#4d7c0f", "#bef264",
                               "Is the system still behaving in production?", _WAVE),
}

_NEUTRAL = AgentLook("hub", "#334155", "#cbd5e1", "", "")


def look(agent_key: str) -> AgentLook:
    return AGENT_LOOK.get(agent_key, _NEUTRAL)


def look_key(agent_key: str, place: str) -> str:
    """Widget/container key that paints what is inside it in the agent's colours.

    Streamlit adds ``st-key-<key>`` as a class on keyed elements; the rules
    generated by :func:`_agent_css` match on the ``look-<agent>`` prefix.
    """
    return f"look-{agent_key}-{place}"


def motif_url(agent_key: str) -> str:
    """The header pattern as a data URL, used as a CSS mask.

    The HTML sanitizer in front of ``st.html`` removes inline SVG, so the
    pattern travels inside CSS instead; as a mask it takes the agent's colour
    in either theme. Base64 keeps any ``<`` out of the style block.
    """
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 120" fill="none" stroke="#000" '
           'stroke-width="3" stroke-linecap="round" stroke-linejoin="round" color="#000">'
           + look(agent_key).motif + "</svg>")
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def _agent_css() -> str:
    rules = []
    for key, lk in AGENT_LOOK.items():
        rules.append(
            f'.look-{key}, [class*="st-key-look-{key}-"] {{ --agent-ink: {lk.ink}; --agent-glow: {lk.glow}; '
            f"--agent: {lk.ink}; --agent: light-dark({lk.ink}, {lk.glow}); "
            f'--agent-motif: url("{motif_url(key)}"); }}'
        )
    return "\n".join(rules)

ROLE = {"owner": ("Owner", ":material/shield_person:"),
        "editor": ("Editor", ":material/edit:"),
        "reviewer": ("Reviewer", ":material/rate_review:")}

CHECK = {"pass": ":material/check_circle:", "warn": ":material/warning:", "fail": ":material/cancel:"}


@lru_cache(maxsize=1)
def _css() -> str:
    return (Path(__file__).parent / "theme.css").read_text(encoding="utf-8")


def apply() -> None:
    """Inject the RAIA CSS layer. Call once per run, before any page renders."""
    st.html(f"<style>{_css()}\n{_agent_css()}</style>")
