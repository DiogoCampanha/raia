"""
``PROJECT_CONTEXT.md``: one project's facts, for the assistant that reads the skill.

Built at download time from the project's blackboard, never from a model: the
stages and their status, what RAIA was told about the product (the baseline
for the skill's reconciliation step), the risk tiers and obligations, every
approved requirement and where it stands, the open decisions, the backlog and
sprints, the latest audit and the actions to do now. It names roles, not
people; who approved what stays in the artifacts' own provenance headers.
"""

import re
from typing import Any, Dict, List, Sequence

from ..contract import vocab as V
from .build import stages

#: Longest free text copied into a table cell; the full text is in the artifacts.
CELL = 220

_HEADER = re.compile(r"^\s*<!--.*?-->\s*", re.S)


def _short(text: Any, n: int = CELL) -> str:
    t = " ".join(str(text or "").split())
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def _table(head: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    def cell(x: Any) -> str:
        return str(x if x not in (None, "") else "—").replace("|", "/").replace("\n", " ")
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head),
                      *["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]])


def _structured(repo: Any, key: str) -> Dict[str, Any]:
    return dict((repo.read_data(key) or {}).get("structured") or {})


def _approved_at(repo: Any, key: str) -> str:
    return str((((repo.read_data(key) or {}).get("provenance") or {}).get("approval") or {})
               .get("approved_at") or "")[:10]


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def _stages(repo: Any) -> str:
    from ..lineage import stage_states
    from ..repository import ARTIFACT_FILES

    labels = {"approved": "Approved", "stale": "Approved, needs review (upstream changed)",
              "in_review": "Draft awaiting review", "ready": "Not run yet", "blocked": "Not run yet"}
    state = {s["agent"]: s for s in stage_states(repo)}
    rows = []
    for key, agent in stages():
        spec = agent.spec
        out = spec.output_key
        record = _structured(repo, out).get("record") or {}
        if key in state:
            status = labels.get(state[key]["status"], state[key]["status"])
        else:
            status = "Approved" if repo.read_artifact(out) is not None else "Not run yet"
        name = spec.name + (f" ({spec.mode_label.lower()} mode)" if spec.parent else "")
        rows.append([name, status, _approved_at(repo, out),
                     V.STATUS_LABELS.get(record.get("overall_status", ""), ""),
                     _short(record.get("headline"), 160),
                     f"`artifacts/{ARTIFACT_FILES[out]}`" if repo.read_artifact(out) is not None else ""])
    return _table(["Stage", "State", "Approved", "Record status", "Headline", "File"], rows)


def _told(repo: Any) -> str:
    from ..rationale import risk_screen as RS

    out: List[str] = []
    brief = repo.read_artifact("product_brief")
    if brief:
        body = _HEADER.sub("", brief).strip()
        out += ["The product description RAIA worked from (`artifacts/01_product_brief.md`):", "",
                "\n".join("> " + line if line.strip() else ">" for line in body.splitlines()), ""]
    rc = _structured(repo, "risk_classification")
    if rc:
        def lab(options, value) -> str:
            labels = {o.value: o.label for o in options}
            values = value if isinstance(value, list) else [value]
            return "; ".join(labels.get(str(v), str(v)) for v in values if v not in (None, "")) or "—"
        yes_no = {"yes": "Yes", "no": "No", "unsure": "Not sure yet"}
        rows = [
            ("Role", lab(RS.ROLE_OPTIONS, rc.get("role"))),
            ("Markets", lab(RS.MARKET_OPTIONS, rc.get("markets"))),
            ("Purpose areas", lab(RS.PURPOSE_OPTIONS, rc.get("purpose_areas") or ["none"])),
            ("Prohibited practices declared", lab(RS.PROHIBITED_OPTIONS, rc.get("prohibited_practices") or ["none"])),
            ("How people meet the AI", lab(RS.TRANSPARENCY_OPTIONS,
                                           (rc.get("transparency_triggers") or [])
                                           + (rc.get("derived_transparency_triggers") or []) or ["none"])),
            ("Data categories", lab(RS.DATA_OPTIONS, rc.get("data_categories") or ["none"])),
            ("Decision autonomy", lab(RS.AUTONOMY_OPTIONS, rc.get("decision_autonomy"))),
            ("Human oversight", lab(RS.OVERSIGHT_OPTIONS, rc.get("human_oversight"))),
            ("Significant effects on people", yes_no.get(str(rc.get("significant_effects")), str(rc.get("significant_effects") or "—"))),
            ("AI techniques", lab(RS.TECHNIQUE_OPTIONS, rc.get("ai_techniques"))),
            ("Where the AI acts", lab(RS.PIPELINE_OPTIONS, rc.get("ai_pipeline"))),
            ("Model source", lab(RS.MODEL_SOURCE_OPTIONS, rc.get("model_source"))),
            ("Stage", lab(RS.STAGE_OPTIONS, rc.get("deployment_stage"))),
        ]
        out += ["The answers the risk classification rests on:", "", _table(["Question", "Answer"], rows), ""]
    if not out:
        return "Nothing yet: the Risk Classifier has not been approved."
    out.append("Compare this with the real product before applying anything (`SKILL.md`, reconciliation step).")
    return "\n".join(out)


def _risk(repo: Any) -> str:
    rc = _structured(repo, "risk_classification")
    if not rc:
        return "Not classified yet."
    verdict = rc.get("computed_verdict") or {}
    record = rc.get("record") or {}
    out = [f"- **EU AI Act:** {verdict.get('eu_tier') or '—'}",
           f"- **PL 2338/2023 (Brazil):** {verdict.get('br_tier') or '—'}",
           f"- **Role:** {verdict.get('role') or rc.get('role') or '—'}", ""]
    if rc.get("obligations"):
        out += ["Obligations that follow:", "",
                _table(["Code", "Obligation", "Why"],
                       [[f"`{o.get('code')}`", o.get("title"), o.get("why")] for o in rc["obligations"]]), ""]
    findings = record.get("findings") or []
    if findings:
        order = {p: i for i, p in enumerate(reversed(V.PRIORITIES))}
        findings = sorted(findings, key=lambda f: order.get(f.get("priority"), 9))
        out += ["Risks found (approved):", "",
                _table(["Id", "Risk", "Principle", "Magnitude × likelihood", "Priority", "Blocking"],
                       [[f.get("id"), _short(f.get("title"), 120), V.PRINCIPLE_NAMES.get(f.get("principle"), f.get("principle")),
                         f"{f.get('magnitude')} × {f.get('likelihood')}", f.get("priority"),
                         "yes" if f.get("blocking") else ""] for f in findings]), ""]
    return "\n".join(out).rstrip()


def _requirements(repo: Any, bl: Dict[str, Any]) -> str:
    from .. import roadmap as R

    review = _structured(repo, "requirements_review")
    if not review:
        return "No requirements approved yet."
    rows = R.requirement_states(review, bl)
    if not rows:
        return "The approved review has no requirements."
    evrs = {str(e.get("id")): e for e in review.get("evrs") or []}
    order = {p: i for i, p in enumerate(R.PRIORITY_ORDER)}
    rows = sorted(rows, key=lambda r: (order.get(r["priority"], 9), not r["obligation"]))
    counts = R.state_counts(rows)
    summary = " · ".join(f"{n} {R.REQ_STATE_LABELS[s].lower()}" for s, n in counts.items() if n)
    table = _table(
        ["EVR", "Priority", "Legal obligation", "Requirement", "Fit criterion", "Verified by", "State", "Stories"],
        [[r["id"], r["priority"], r["obligation"], _short(r["statement"]),
          _short((evrs.get(r["id"]) or {}).get("fit_criterion"), 160),
          (evrs.get(r["id"]) or {}).get("verification_method"),
          R.REQ_STATE_LABELS.get(r["state"], r["state"]) + (f" ({r['verified_in']})" if r.get("verified_in") else ""),
          ", ".join(r["stories"])] for r in rows])
    excluded = review.get("excluded_evrs") or []
    note = (f"\n\nExcluded by a reviewer, not handed on: {', '.join(map(str, excluded))}." if excluded else "")
    return f"{len(rows)} approved requirements: {summary}.\n\n{table}{note}"


def _decisions(repo: Any) -> str:
    issues = repo.open_issues()
    if not issues:
        return "No decisions recorded."
    open_ = [i for i in issues if i.get("status", "open") == "open"]
    taken = len(issues) - len(open_)
    open_.sort(key=lambda i: (not i.get("blocking"), i.get("id", "")))
    head = (f"{len(open_)} open ({sum(1 for i in open_ if i.get('blocking'))} blocking), {taken} taken. "
            "Present these; a person decides.")
    if not open_:
        return head
    return head + "\n\n" + _table(
        ["Id", "Blocking", "Type", "Owner", "Decision needed", "Options", "Links", "Raised by"],
        [[i.get("id"), "yes" if i.get("blocking") else "", i.get("type"),
          V.OWNER_LABELS.get(i.get("decision_owner"), i.get("decision_owner")),
          _short(i.get("text") or i.get("description")), " · ".join(_short(o, 80) for o in i.get("options") or []),
          ", ".join(map(str, i.get("links") or [])), i.get("raised_by")] for i in open_])


def _board(bl: Dict[str, Any], sp: Dict[str, Any]) -> str:
    from .. import backlog as B

    stories = [s for s in bl.get("stories") or [] if s.get("status") != B.OBSOLETE]
    if not stories and not sp.get("sprints"):
        return "No backlog yet: it opens once the requirements are approved."
    out = []
    if stories:
        by_status = {}
        for s in stories:
            by_status[s["status"]] = by_status.get(s["status"], 0) + 1
        out += [f"{len(stories)} stories ({sum(1 for s in stories if s.get('origin') == B.RAI)} RAI, "
                f"{sum(1 for s in stories if s.get('origin') == B.PRODUCT)} product): "
                + " · ".join(f"{n} {B.STATUS_LABELS.get(k, k).lower()}" for k, n in by_status.items()) + ".", "",
                _table(["Story", "Origin", "Title", "EVRs", "Status", "Sprint", "Ethical criteria", "Jira"],
                       [[s["id"], B.ORIGIN_LABELS.get(s.get("origin"), s.get("origin")), _short(s.get("title"), 100),
                         ", ".join(s.get("evr_ids") or []),
                         B.STATUS_LABELS.get(s["status"], s["status"])
                         + (f" (carried over {s['carried_over']}x)" if s.get("carried_over") else ""),
                         s.get("sprint") or s.get("verified_in"),
                         ", ".join(c["id"] for c in B.ethical_criteria(s)),
                         (s.get("jira") or {}).get("key")] for s in stories]), ""]
    if sp.get("sprints"):
        out += ["Sprints:", "",
                _table(["Sprint", "Name", "State", "Goal", "Audit opinion"],
                       [[x["id"], x.get("name"), B.SPRINT_STATE_LABELS.get(x.get("state"), x.get("state")),
                         _short(x.get("goal"), 100), V.AUDIT_OPINION_LABELS.get(x.get("opinion"), x.get("opinion"))]
                        for x in sp["sprints"]]), ""]
    return "\n".join(out).rstrip()


def _audit(repo: Any) -> str:
    audit = _structured(repo, "audit_report")
    if not audit:
        return "No audit approved yet."
    ext = (audit.get("record") or {}).get("extension") or {}
    opinion = ext.get("opinion") or {}
    out = [f"Approved {_approved_at(repo, 'audit_report') or '—'}"
           + (f", closing {audit.get('sprint_close')}" if audit.get("sprint_close") else "") + ".", "",
           f"- **Opinion:** {V.AUDIT_OPINION_LABELS.get(opinion.get('rating'), opinion.get('rating') or '—')}"
           + (" — " + "; ".join(opinion.get("reasons") or []) if opinion.get("reasons") else "")]
    trend = (ext.get("progress") or {}).get("trend") or {}
    if trend:
        out.append(f"- **Trend:** {trend.get('direction', '—').replace('_', ' ')} — {trend.get('reason', '')}")
    if ext.get("next_focus"):
        out.append(f"- **Next focus:** {_short(ext['next_focus'], 300)}")
    if ext.get("pathway_summary"):
        out.append(f"- **Pathway:** {_short(ext['pathway_summary'], 300)}")
    weak = [b for b in ext.get("backlog_assessment") or [] if b.get("judgement") != "covered"]
    if weak:
        out += ["", "Requirements the backlog does not cover well:", "",
                _table(["Requirement", "Judgement", "Why"],
                       [[b.get("ref"), str(b.get("judgement", "")).replace("_", " "), _short(b.get("reason"))]
                        for b in weak])]
    return "\n".join(out)


def _actions(repo: Any) -> str:
    from ..contract import actions as action_plan

    rows = [r for r in action_plan.project_actions(repo) if r["priority"] in ("critical", "high")]
    if not rows:
        return "No critical or high-priority actions. The full plan is in `action_plan.csv`."
    shown = rows[:12]
    more = f"\n\n{len(rows) - len(shown)} more in `action_plan.csv`." if len(rows) > len(shown) else ""
    return _table(["Id", "Priority", "Action", "Owner", "Evidence", "Answers"],
                  [[r["id"], r["priority"], _short(r["action"], 160), V.OWNER_LABELS.get(r["owner_role"], r["owner_role"]),
                    _short(r["evidence_artifact"], 80), _short(r["findings"], 100)] for r in shown]) + more


def project_context(repo: Any, project_label: str, created: str) -> str:
    """The project's facts as Markdown, for ``project/PROJECT_CONTEXT.md``."""
    from .. import backlog as B
    from .. import __version__

    bl, sp = B.load(repo)
    sections = [
        ("Stages", _stages(repo)),
        ("What RAIA was told", _told(repo)),
        ("Risk classification", _risk(repo)),
        ("Ethical value requirements", _requirements(repo, bl)),
        ("Decisions for a person", _decisions(repo)),
        ("Backlog and sprints", _board(bl, sp)),
        ("Latest audit", _audit(repo)),
        ("Do now: critical and high-priority actions", _actions(repo)),
    ]
    head = [
        f"# Project context — {project_label or repo.project}",
        "",
        f"> Snapshot of the RAIA project as of **{created}** (RAIA {__version__}, records `{V.SCHEMA_VERSION}`). "
        "Generated by code from the approved records; nothing here was written by a model. If the team has "
        "approved new work in RAIA since, ask for a fresh download.",
        "",
        "Files in this folder: `artifacts/` (approved records, `.md` and structured `.json`), `action_plan.csv` / "
        "`action_plan.json`, `MANIFEST.txt`, and once the board exists `backlog.csv` / `backlog.json`, "
        "`sprints.json`, `roadmap.csv`.",
    ]
    body = [f"\n## {i}. {title}\n\n{text}" for i, (title, text) in enumerate(sections, start=1)]
    return "\n".join(head + body) + "\n"
