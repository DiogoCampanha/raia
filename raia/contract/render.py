"""
raia.contract.render
====================

The one layout every RAIA artifact follows, rendered by code from the record.

Every document reads in the same order as the screen: **Summary** (status,
headline, a few numbers, the main issues), **Action Plan** (grouped Do now,
Plan, Track) and **Open Issues** (the decisions a person must take); then the
**deep dive** — Findings, the agent's own sections, each opening with its
conclusion — and a traceability appendix (Not Grounded in Retrieved Excerpts,
Declared Coverage, Verdict Reconciliation). The screen and the document draw
the same digest (:mod:`raia.contract.digest`), so they cannot drift apart.

The agent's own sections are named after what its normative source produces (a
value register and ethical value requirements, a sprint ethics log, drift
alerts and a response plan). Nothing in the Markdown is written by the model
directly; it is all a view of fields that were validated first.
"""

from __future__ import annotations

from typing import Any, Dict, List

from . import digest as D
from . import vocab as V

COMMON_HEAD = ["Summary", "Action Plan", "Open Issues", "Findings"]
COMMON_TAIL = list(D.TRACE_SECTIONS)

AGENT_SECTIONS: Dict[str, List[str]] = D.AGENT_MD_SECTIONS

STATUS_LABELS = V.STATUS_LABELS


def required_sections(agent_key: str) -> List[str]:
    return COMMON_HEAD + AGENT_SECTIONS.get(agent_key, []) + COMMON_TAIL


def cell(value: Any) -> str:
    if value is None or value == "" or value == []:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value) or "—"
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def table(headers: List[str], rows: List[List[Any]]) -> str:
    if not rows:
        return "_None._"
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def sentence(value: Any) -> str:
    """A cell value ending in exactly one full stop."""
    text = cell(value)
    return text if text.endswith((".", "!", "?")) else text + "."


def label(value: Any) -> str:
    return str(value or "—").replace("_", " ")


def cites(values: Any) -> str:
    return " ".join(str(v) for v in values or [])


def para(value: Any) -> str:
    return str(value).strip() if value and str(value).strip() else "_Not provided._"



# ---------------------------------------------------------------------------
# Machine block
# ---------------------------------------------------------------------------


def machine_block(record: Dict[str, Any], checklist_keys: List[str]) -> str:
    lines = ["```raia", f"schema: {record.get('meta', {}).get('schema_version', V.SCHEMA_VERSION)}"]
    for k, v in (record.get("declared_verdict") or {}).items():
        lines.append(f"verdict.{k}: {v}")
    lines.append("verdict.agrees_with_screen: " + ("yes" if record.get("agrees_with_rule_engine", True) else "no"))
    cov = {c.get("key"): c for c in record.get("coverage") or []}
    for key in list(dict.fromkeys(list(checklist_keys) + list(cov))):
        c = cov.get(key)
        if c:
            lines.append(f"coverage.{key}: {c.get('status')} — {cell(c.get('justification'))}")
    lines.append("```")
    return "\n".join(lines)




# ---------------------------------------------------------------------------
# Digest -> Markdown
# ---------------------------------------------------------------------------


def _tags(tags) -> str:
    return " · ".join(t for t, _ in tags if t)


def _card_line(c: Dict[str, Any]) -> str:
    """One card on one line, so an identifier and everything said about it stay together."""
    head = f"**{c['id']}" + (f" — {c['title']}" if c.get("title") else "") + "**" if c.get("id") else f"**{c.get('title', '')}**"
    parts = [head]
    if c.get("tags"):
        parts.append(f"[{_tags(c['tags'])}]")
    if c.get("lead"):
        parts.append(sentence(c["lead"]))
    if c.get("body"):
        parts.append(sentence(c["body"]))
    for k, v in c.get("fields") or []:
        if isinstance(v, (list, tuple)):
            v = " | ".join(str(x) for x in v)
        parts.append(f"_{k}:_ {sentence(v)}")
    if c.get("cites"):
        parts.append(cites(c["cites"]))
    return "- " + " ".join(p for p in parts if p)


def _blocks(blocks: List[Dict[str, Any]]) -> str:
    out: List[str] = []
    for b in blocks:
        t = b.get("type")
        if t == "text":
            text = (b.get("text") or "").strip()
            out.append(f"**{b['label']}.** {text}".rstrip() if text else f"**{b['label']}.**")
        elif t == "table":
            out.append(table(b["headers"], b["rows"]))
        elif t == "cards":
            out.append("\n".join(_card_line(c) for c in b["items"]) or "_None._")
        elif t == "bullets":
            out.append("\n".join(f"- {cell(x)}" for x in b["items"]) or "_None._")
        elif t == "note":
            out.append(f"_{b['text']}_")
    return "\n\n".join(out)


def _action_line(a: Dict[str, Any]) -> str:
    flag = " · Blocking" if a["blocking"] else ""
    return (f"- **{a['id']}** · {V.PRIORITY_LABELS.get(a['priority'], a['priority'])}{flag} — {sentence(a['text'])} "
            f"_Owner:_ {a['owner_label']} · _When:_ {a['when']} · _Done when:_ {sentence(a['done_when'])} "
            f"_Answers:_ {', '.join(a['findings']) or '—'} · _Response:_ {a['response']}"
            + (f" {cites(a['cites'])}" if a["cites"] else ""))


def _decision_line(d: Dict[str, Any]) -> str:
    return (f"- **{d['id']}** · {d['type_label']} · decided by {d['owner_label']}"
            f"{' · **blocking**' if d['blocking'] else ''} · raised by {d['origin']} — {cell(d['text'])}"
            + (f" Options: {'; '.join(d['options'])}." if d["options"] else ""))


def markdown_from_digest(dg: Dict[str, Any]) -> Dict[str, str]:
    """Section title -> Markdown body, for every section of the layout."""
    sections: Dict[str, str] = {}

    kpis = dg["kpis"]
    summary = [f"**{dg['status']['label']}** — {dg['headline']}".rstrip(" —")]
    if dg["summary"]:
        summary += ["", dg["summary"]]
    if dg.get("signature"):
        summary += ["", D.signature_text(dg["signature"])]
    summary += ["", table([k["label"] for k in kpis], [[f"{k['value']} — {k['hint']}" for k in kpis]])]
    if dg["top_issues"]:
        summary += ["", "**Main issues**", ""]
        for f in dg["top_issues"]:
            flag = " · Blocking" if f.get("blocking") else ""
            summary.append(f"- **{f.get('id')}** · {V.PRIORITY_LABELS.get(f.get('priority'), f.get('priority'))}{flag} — "
                           f"{cell(f.get('title'))} ({D.principle_name(f.get('principle'))})")
    if dg["principles"]:
        summary += ["", "**Risk areas:** " + ", ".join(f"{n} ({c})" for n, c in dg["principles"])]
    sections["Summary"] = "\n".join(summary)

    plan: List[str] = []
    for g in dg["action_groups"]:
        if g["actions"]:
            plan += [f"### {g['title']} — {g['hint'].lower()}", "", "\n".join(_action_line(a) for a in g["actions"]), ""]
    sections["Action Plan"] = "\n".join(plan).strip() or "_No actions._"

    sections["Open Issues"] = "\n".join(_decision_line(d) for d in dg["decisions"]) or "- None."

    for sec in dg["deep"]:
        sections[sec["md_title"]] = f"> **Conclusion.** {sec['conclusion']}\n\n{_blocks(sec['blocks'])}".rstrip()
    return sections


def render(agent_key: str, record: Dict[str, Any], computed_data: Dict[str, Any],
           checklist_keys: List[str]) -> str:
    dg = D.build(agent_key, record, computed_data or {})
    meta = dg["meta"]
    parts: List[str] = [
        f"> **{meta.get('record_type', 'RAIA record')}** · `{meta.get('schema_version', V.SCHEMA_VERSION)}` · "
        f"{meta.get('agent_name', agent_key)} · {meta.get('layer', '')} layer · {meta.get('sdlc_phase', '')}",
        "",
    ]
    for n in dg["notices"]:
        parts += [f"> **{n}**", ""]

    sections = markdown_from_digest(dg)
    deep_start = COMMON_HEAD.index("Findings")
    for i, title in enumerate(required_sections(agent_key)):
        if i == deep_start:
            parts += ["---", "", "_Deep dive: the analysis behind each point._", ""]
        if title == COMMON_TAIL[0]:
            parts += ["---", "", "_Traceability appendix._", ""]
        parts += [f"## {title}", "", sections.get(title) or "_None._", ""]

    if dg["unparsed"]:
        parts += ["## Unparsed Model Reply", "", "```text", dg["unparsed"][:6000], "```", ""]

    parts.append(machine_block(record, checklist_keys))
    return "\n".join(parts)
