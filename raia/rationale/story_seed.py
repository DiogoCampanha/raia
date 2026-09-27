"""
raia.rationale.story_seed
=========================

Deterministic scope for the User Story Refiner's generate mode.

Ethical requirements are constants of a project; the work that implements them
is spread over many sprints. The generate mode turns approved requirements
into RAI stories for the backlog, and this engine decides — before the model is
asked anything — which requirements that run covers:

* only requirements with **no live RAI story** yet (a requirement already in the
  backlog is not generated twice);
* **a short list by default**: the five highest-priority ones, legal
  obligations first, then the computed priority of the findings that link
  them. A person can widen the run to ten, or name the requirements to cover;
* for each, the facts the stories must answer to: the statement, the fit
  criterion, the verification method and the legal obligation behind it.

The coverage rule is a counted invariant, as the story register is for the
refine mode: every requirement in scope comes back covered by at least one
story, or with a one-line reason it needs none.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from ..fields import options, text_of
from .. import roadmap as R
from .story_map import CAPABILITY_OPTIONS, CARDS, SECTION_ECCOLA_SPRINTS, SECTION_MS_STYLE, cards_for
from .types import ChecklistItem, Finding, Pin, RationaleResult, md_table

SCOPE_OPTIONS = options(
    ("short", f"The {R.SHORT_LIST} highest-priority requirements without a story"),
    ("wider", f"Up to {R.MAX_GENERATE} requirements without a story"),
)

#: At most this many stories per requirement: a requirement that needs more is
#: a sign it should be split at the requirements gate, not here.
MAX_STORIES_PER_REQUIREMENT = 3

_ID_SPLIT = re.compile(r"[\s,;]+")


def scope(inputs: Dict[str, Any], review: Dict[str, Any], backlog: Dict[str, Any]) -> Dict[str, Any]:
    """Which requirements this run covers, and which were left for a later run."""
    uncovered = R.uncovered_requirements(review, backlog)
    by_id = {r["id"]: r for r in uncovered}
    named = [x.strip().upper() for x in _ID_SPLIT.split(text_of(inputs, "focus_requirements")) if x.strip()]
    limit = R.MAX_GENERATE if str(inputs.get("scope") or "short") == "wider" else R.SHORT_LIST
    unknown: List[str] = []
    if named:
        picked = []
        for n in named:
            match = by_id.get(n) or next((r for r in uncovered if r["id"].upper() == n), None)
            if match and match not in picked:
                picked.append(match)
            elif not match:
                unknown.append(n)
        chosen = picked[: R.MAX_GENERATE]
    else:
        chosen = uncovered[:limit]
    ids = {r["id"] for r in chosen}
    return {"chosen": chosen, "left": [r for r in uncovered if r["id"] not in ids], "unknown": unknown,
            "limit": limit}


def run(inputs: Dict[str, Any], upstream: Dict[str, Any]) -> RationaleResult:
    r = RationaleResult(engine="story_seed")
    review = (upstream.get("requirements_review") or {}).get("data") or {}
    risk = (upstream.get("risk_classification") or {}).get("data") or {}
    backlog = (upstream.get("backlog") or {}).get("data") or {}
    dod = text_of(inputs, "definition_of_done")

    sc = scope(inputs, review, backlog)
    chosen, left = sc["chosen"], sc["left"]
    evr_ids = [x["id"] for x in chosen]

    r.findings.append(Finding(
        "seed.scope", f"{len(chosen)} requirement(s) without a story are in scope for this run",
        ", ".join(evr_ids) or "none"))
    if left:
        r.findings.append(Finding(
            "seed.left", f"{len(left)} more requirement(s) without a story are left for a later run",
            ", ".join(x["id"] for x in left[:12]) + (" …" if len(left) > 12 else "")))
    if sc["unknown"]:
        r.notes.append("These named requirements are not approved or already have a story, so they "
                       "are not in scope: " + ", ".join(sc["unknown"]) + ".")

    r.tables["Requirements in scope (every id must be covered by a story, or listed in not_story with a reason)"] = md_table(
        ["EVR id", "Requirement", "Fit criterion", "Legal obligation", "Priority"],
        [[x["id"], x["statement"][:160] or "—", x["fit_criterion"][:160] or "—",
          x["obligation"] or "—", x["priority"] or "—"] for x in chosen],
    )
    labels = {o.value: o.label for o in CAPABILITY_OPTIONS if o.value != "none"}
    r.tables["What a story can touch (choose per story; it selects the ECCOLA cards allowed)"] = md_table(
        ["Code", "Meaning"], [[k, v] for k, v in labels.items()])
    project_cards = cards_for(risk, list(labels))
    r.tables["ECCOLA cards in scope for this product (a story may use those its touches select)"] = md_table(
        ["Card", "Title", "Selected because"],
        [[c["id"], c["title"], ", ".join(c["why"])] for c in project_cards])

    if dod:
        r.notes.append("A definition of done was provided; write the criteria in its terms.")
    r.notes.append(
        f"Name stories G1, G2, … in order and their criteria AC-G1-1, AC-G1-2, …; code gives each "
        f"story its backlog id (RAI-n) when a person approves. At most {MAX_STORIES_PER_REQUIREMENT} "
        "stories per requirement; one is usually enough.")

    if not chosen:
        r.raise_issue(
            "Every approved requirement already has a story in the backlog, so there is nothing to "
            "generate. Refine product stories, or plan the next sprint instead.",
            type="missing_information", decision_owner="product", blocking=False,
        )

    r.pins = [
        Pin("ms_rai_v2", SECTION_MS_STYLE, "how to make a criterion verifiable"),
        Pin("eccola", SECTION_ECCOLA_SPRINTS, "how cards are applied in a sprint"),
    ]
    r.checklist = [
        ChecklistItem("coverage", "Cover every requirement in scope with a story, or give a one-line reason it needs none"),
        ChecklistItem("stories", "Write each story as a user story a team can schedule in one sprint"),
        ChecklistItem("criteria", "Give each story verifiable ethical acceptance criteria"),
        ChecklistItem("traceability", "Trace each story and criterion to the requirement ids it implements"),
        ChecklistItem("cards", "Use only ECCOLA cards the story's touches select"),
        ChecklistItem("open_issues", "Carry forward every open issue raised here, plus any you add"),
    ]
    r.verdict = {
        "requirement_count": len(chosen),
        "evr_ids": evr_ids,
        "max_per_requirement": MAX_STORIES_PER_REQUIREMENT,
    }
    r.query_terms = (["verifiable acceptance criteria", "user stories", "sprint backlog"]
                     + [x["statement"][:60] for x in chosen][:5])
    r.data.update({
        "scope": chosen,
        "left_out": [x["id"] for x in left],
        "unknown": sc["unknown"],
        "limit": sc["limit"],
        "project_cards": [c["id"] for c in project_cards],
        "risk": {k: risk.get(k) for k in ("eu_is_high_risk", "br_is_high_risk", "eu_tier", "significant_effects",
                                          "deployment_stage", "annex_i_product", "data_categories", "human_oversight")},
    })
    return r


def allowed_cards(data: Dict[str, Any], touches: List[str]) -> List[str]:
    """The cards a generated story may carry, from what it touches (as the refine mode does)."""
    risk = data.get("risk") or {}
    return [c["id"] for c in cards_for(risk, touches)]


CARD_IDS = [c["id"] for c in CARDS]
