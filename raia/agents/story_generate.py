"""
User Story Refiner — generate mode (Dev layer — Iterative development / sprints).

RAIA agent specification (the Refiner's second mode, not a sixth agent):
  Inputs   : the approved ethical requirements that have no story in the
             backlog yet — a short list by default, widened on request
  Outputs  : RAI stories for the backlog, each linked to the requirement(s)
             it implements and carrying verifiable ethical acceptance criteria
  Grounding: Microsoft RAI Standard v2 verifiable requirements; ECCOLA cards

Requirements are constants of a project; the work they need is spread over many
sprints. This mode writes that work down once, as backlog stories a team can
schedule. The same five-step turn applies: the rule engine
(:mod:`raia.rationale.story_seed`) fixes which requirements the run covers and
what each must answer to, the model writes the stories, code checks every
requirement in scope is covered or justified and that every story links one,
and a person approves. Only then do the stories enter the backlog, as
``RAI-n``.
"""

from typing import Any, Dict, List

from ..contract import checks as contract_checks
from ..fields import InputField
from ..rationale import story_seed
from ..rationale.types import RationaleResult
from ..validators import FAIL, PASS, WARN, ValidationItem
from .base import AgentSpec, BaseAgent

G_SCOPE = "1 · Which requirements"
G_TEAM = "2 · How your team works"


class StoryGeneratorMode(BaseAgent):
    spec = AgentSpec(
        key="story_generate",
        name="User Story Refiner",
        parent="story_refiner",
        mode_label="Generate from requirements",
        layer="Dev",
        sdlc_phase="Iterative development (sprints)",
        description=(
            "Turns approved ethical requirements into RAI stories for the backlog, each with "
            "verifiable acceptance criteria and linked to the requirement it implements."
        ),
        intro=(
            "Generate mode. RAIA takes the approved requirements that have no story yet — the five "
            "highest-priority ones unless you widen the run or name them — and writes the stories that "
            "implement them. Every requirement comes back covered by a story or with a one-line reason it "
            "needs none. Approved stories enter the backlog as RAI-n, ready to plan into sprints."
        ),
        grounding_sources=["ms_rai_v2", "eccola"],
        upstream_keys=["risk_classification", "requirements_review", "backlog"],
        required_upstream=["requirements_review"],
        output_key="rai_backlog",
        engine=story_seed.run,
        verdict_keys=["requirement_count"],
        input_fields=[
            InputField(
                key="scope", label="How many requirements", kind="select", group=G_SCOPE,
                options=story_seed.SCOPE_OPTIONS, default="short",
                help="Start short: five stories' worth of work is easier to review at the gate. Run "
                     "again for the next ones.",
            ),
            InputField(
                key="focus_requirements", label="Or name the requirements (optional)", kind="text",
                group=G_SCOPE, placeholder="EVR-2, EVR-5",
                help="Requirement ids without a story. When given, only these are covered.",
            ),
            InputField(
                key="definition_of_done", label="Your definition of done (optional)", kind="textarea",
                group=G_TEAM, height=100,
                help="Criteria are written in its terms, so they fit the team's process.",
            ),
        ],
        task_prompt=(
            "Write the RAI stories that implement the approved ethical requirements in scope, with the "
            "Microsoft RAI Standard v2 verifiable-requirement pattern and the ECCOLA cards. The "
            "requirement ids in scope are given: cover every one with at least one story, or list it in "
            "`not_story` with a one-line reason (for example, it is a policy decision rather than work "
            "for the team). Do not invent requirement ids, and do not cover requirements outside the "
            "scope.\n\n"
            "Each story in `stories`: `story_id` G1, G2, … in order; a short `title`; a `description` "
            "written as a user story a team can finish in one sprint (\"As a …, I want …, so that …\"); "
            "`evr_ids` naming the requirement(s) it implements; `touches` from the given codes; "
            "`eccola_cards` only from the cards its touches select; and `criteria` — new verifiable "
            "ethical acceptance criteria labelled AC-<story id>-<n> (e.g. AC-G1-1), each with the "
            "Standard's goal, the affected stakeholder group, a measurable `condition` with its "
            "threshold, the `evidence_artifact` that demonstrates it, an owner, and the `evr_ids` it "
            "implements. One story per requirement is usually enough; never more than three.\n\n"
            "The stories are the output the team uses. Findings and actions only explain them: at most "
            "three findings — the risks the stories answer, linked to requirement ids — and one action "
            "per finding, which may simply be to schedule the stories that answer it (name their ids)."
        ),
    )

    def extra_checks(self, report, draft, rationale: RationaleResult, record) -> None:
        verdict = rationale.verdict or {}
        scope: List[str] = [str(x) for x in verdict.get("evr_ids") or []]
        ext = record.get("extension") or {}
        stories = ext.get("stories") or []
        covered = [e for s in stories for e in s.get("evr_ids") or []]
        justified = [str(n.get("evr_id")) for n in ext.get("not_story") or []]
        report.add(contract_checks.check_registered_ids(
            "Requirement coverage", "seed_coverage", scope, covered + justified))
        unlinked = [str(s.get("story_id")) for s in stories if not s.get("evr_ids")]
        if unlinked:
            report.add(ValidationItem("seed.unlinked", FAIL, "Story links",
                                      "Every RAI story must link at least one requirement.", unlinked))
        else:
            report.add(ValidationItem("seed.linked", PASS, "Story links",
                                      f"All {len(stories)} stories link a requirement."))
        per: Dict[str, int] = {}
        for e in covered:
            per[e] = per.get(e, 0) + 1
        too_many = [f"{e}: {n} stories" for e, n in per.items() if n > story_seed.MAX_STORIES_PER_REQUIREMENT]
        report.add(ValidationItem("seed.per_requirement", WARN if too_many else PASS, "Stories per requirement",
                                  (f"More than {story_seed.MAX_STORIES_PER_REQUIREMENT} stories for a requirement: "
                                   "split it at the requirements gate instead.") if too_many
                                  else "No requirement is split into more than "
                                       f"{story_seed.MAX_STORIES_PER_REQUIREMENT} stories.", too_many))
        bad_cards = []
        for s in stories:
            allowed = story_seed.allowed_cards(rationale.data or {}, list(s.get("touches") or []))
            bad_cards += [f"{s.get('story_id')}:{c}" for c in s.get("eccola_cards") or [] if c not in allowed]
        report.add(ValidationItem("seed.cards", WARN if bad_cards else PASS, "Card selection",
                                  "Card(s) its touches do not select." if bad_cards
                                  else "Every card is selected by what its story touches.", bad_cards))
        report.add(contract_checks.check_criteria_ids(record))

    def structured_from(self, record: Dict[str, Any], rationale: RationaleResult) -> Dict[str, Any]:
        data = super().structured_from(record, rationale)
        data["generated"] = [
            {"story_id": s.get("story_id"), "title": s.get("title"), "evr_ids": s.get("evr_ids"),
             "criteria": [c.get("id") for c in s.get("criteria") or []]}
            for s in (record.get("extension") or {}).get("stories") or []
        ]
        return data
