"""
raia.brief
==========

One page a person can hand to someone else.

A project's exports are made for a reader who will go through them: a zip,
tables, artifacts with their provenance. The next step of the person who ran
RAIA is usually smaller than that: telling a manager, a squad or the legal and
privacy owners where the product stands. The brief is that page: what the
product does with AI, where it sits, the most pressing risks, the requirements
that answer them, the decisions still needed and from whom, and what has been
verified.

It is written by code from the approved records and nothing else, like every
other figure RAIA shows: no model is called, nothing here is new analysis, and a
stage that was not approved is said to be missing. It names owner roles, never
people. It is plain Markdown that reads as plain text, so it can be pasted into
a page or a message as it is.
"""

from typing import Any, Dict, List

from .contract import digest as D
from .contract import vocab as V

#: How many of each thing fit on a page.
TOP_RISKS = 3
TOP_REQUIREMENTS = 5
TOP_DECISIONS = 5


def _structured(repo: Any, key: str) -> Dict[str, Any]:
    return dict((repo.read_data(key) or {}).get("structured") or {})


def _one_line(text: Any, n: int = 260) -> str:
    t = " ".join(str(text or "").split())
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def _what(repo: Any) -> List[str]:
    intake = _structured(repo, "product_brief").get("intake") or {}
    lines = [_one_line(intake.get(k), 420) for k in ("product_brief", "ai_output") if intake.get(k)]
    return lines or ["Not described yet: the Risk Classifier has not been approved."]


def _where(repo: Any) -> List[str]:
    rc = _structured(repo, "risk_classification")
    if not rc:
        return ["Not classified yet."]
    v = rc.get("computed_verdict") or {}
    out = []
    for label, tier, inst in ((D.EU_LABEL, v.get("eu_tier"), "eu"), (D.BR_LABEL, v.get("br_tier"), "br")):
        applies = D.applicability(v, inst)
        out.append(f"- {label}: {D.short_tier(tier)}" + (f" ({applies})" if applies else ""))
    obligations = rc.get("obligations") or []
    out.append("- Legal obligations that follow: " + (", ".join(str(o.get("code")) for o in obligations)
                                                       if obligations else "none computed"))
    return out


def _risks(repo: Any) -> List[str]:
    findings = (_structured(repo, "risk_classification").get("record") or {}).get("findings") or []
    if not findings:
        return ["None recorded." if _structured(repo, "risk_classification") else "Not analysed yet."]
    findings = sorted(findings, key=lambda f: -D.priority_rank(f.get("priority") or ""))
    out = [f"{i}. {_one_line(f.get('title'), 140)} ({V.PRINCIPLE_NAMES.get(f.get('principle'), f.get('principle'))}; "
           f"{f.get('priority')} priority{'; blocking' if f.get('blocking') else ''}) [{f.get('id')}]"
           for i, f in enumerate(findings[:TOP_RISKS], 1)]
    if len(findings) > TOP_RISKS:
        out.append(f"…and {len(findings) - TOP_RISKS} more in the risk classification.")
    return out


def _requirements(repo: Any) -> List[str]:
    from . import backlog as B
    from . import roadmap as R

    review = _structured(repo, "requirements_review")
    if not review:
        return ["No requirements approved yet."]
    bl, _ = B.load(repo)
    rows = R.requirement_states(review, bl)
    if not rows:
        return ["The approved review has no requirements."]
    order = {p: i for i, p in enumerate(R.PRIORITY_ORDER)}
    rows = sorted(rows, key=lambda r: (order.get(r["priority"], 9), not r["obligation"]))
    counts = R.state_counts(rows)
    out = [f"{len(rows)} approved: " + ", ".join(f"{n} {R.REQ_STATE_LABELS[s].lower()}" for s, n in counts.items() if n)
           + "."]
    out += [f"- {r['id']} ({r['priority']}{', legal obligation' if r['obligation'] else ''}): "
            f"{_one_line(r['statement'], 200)} State: {R.REQ_STATE_LABELS.get(r['state'], r['state']).lower()}."
            for r in rows[:TOP_REQUIREMENTS]]
    if len(rows) > TOP_REQUIREMENTS:
        out.append(f"…and {len(rows) - TOP_REQUIREMENTS} more in the requirements review.")
    return out


def _decisions(repo: Any) -> List[str]:
    issues = [i for i in repo.open_issues() if i.get("status", "open") == "open"]
    if not issues:
        return ["None open."]
    issues.sort(key=lambda i: (not i.get("blocking"), str(i.get("id", ""))))
    out = [f"- {'Blocking. ' if i.get('blocking') else ''}{_one_line(i.get('text') or i.get('description'), 220)} "
           f"Decided by: {V.OWNER_LABELS.get(i.get('decision_owner'), i.get('decision_owner') or 'not assigned')}. "
           f"[{i.get('id')}]" for i in issues[:TOP_DECISIONS]]
    if len(issues) > TOP_DECISIONS:
        out.append(f"…and {len(issues) - TOP_DECISIONS} more under Open issues.")
    return out


def _evidence(repo: Any) -> List[str]:
    audit = _structured(repo, "audit_report")
    if not audit:
        return ["No audit approved yet: nothing has been verified against evidence."]
    opinion = ((audit.get("record") or {}).get("extension") or {}).get("opinion") or {}
    out = [f"Latest audit opinion: {V.AUDIT_OPINION_LABELS.get(opinion.get('rating'), opinion.get('rating') or 'not rated')}."]
    if opinion.get("reasons"):
        out.append("Because: " + _one_line("; ".join(opinion["reasons"]), 300))
    return out


def project_brief(repo: Any, project_label: str, created: str) -> str:
    """The one-page brief of a project, as Markdown, from its approved records."""
    sections = [
        ("What it does with AI", _what(repo)),
        ("Where it sits", _where(repo)),
        ("Most pressing risks", _risks(repo)),
        ("Requirements that answer them", _requirements(repo)),
        ("Decisions needed", _decisions(repo)),
        ("What has been verified", _evidence(repo)),
    ]
    out = [f"# {project_label or repo.project}: Responsible AI brief", "",
           f"As of {created}. Written by RAIA from this project's approved records; nothing here was written by "
           "a model. A draft to support decisions, not legal or compliance advice.", ""]
    for title, lines in sections:
        out += [f"## {title}", "", *lines, ""]
    out += ["Sources: EU AI Act; PL 2338/2023 (" + ("a bill, not in force" if D.BR_LABEL != D.BR_NAME else "Brazil")
            + "); IEEE 7000; NIST AI RMF; Microsoft Responsible AI Standard v2; ECCOLA. Identifiers in brackets "
              "point to the project's records in RAIA.", ""]
    return "\n".join(out)
