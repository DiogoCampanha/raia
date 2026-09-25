#!/usr/bin/env python3
"""
Deterministic checks for the RAIA output contract (no model, no network).

    python tests/test_contract.py

Covers the closed vocabularies (and that every one of them comes from the
project's normative corpus), the risk-level matrix and its floors, parsing and
the fallback record, finalisation (ids, priorities, carried issues,
disagreement and acceptance issues, evidence discipline, computed severities,
idempotence), the one rendered layout, the schema shown to the model, and the
project action plan.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from raia.agents import AGENTS  # noqa: E402
from raia.contract import actions as action_plan  # noqa: E402
from raia.contract import assemble, checks, digest, mock, render, rubric  # noqa: E402
from raia.contract import vocab as V  # noqa: E402
from raia.contract.prompt import contract_text  # noqa: E402
from raia.contract.schema import model_facing_schema, record_model  # noqa: E402
from raia.examples import EXAMPLES  # noqa: E402
from raia.rationale.types import ChecklistItem, RationaleResult  # noqa: E402
from raia.validators import FAIL, PASS, check_citations, parse_machine_block  # noqa: E402

FAILURES = []


def check(cond: bool, label: str) -> None:
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond:
        FAILURES.append(label)


CORPUS = {p.stem: " ".join(p.read_text(encoding="utf-8").split()) for p in (ROOT / "corpus").glob("*.md")}
CITE = "[Source: EU AI Act (Regulation (EU) 2024/1689) — Article 6 and Annex III — High-Risk AI Systems | authority: legal]"
ADVISORY = "[Source: NIST AI Risk Management Framework 1.0 — MAP (context and risk identification) | authority: advisory]"
EVIDENCE = [{"citation": CITE, "authority": "legal"}, {"citation": ADVISORY, "authority": "advisory"}]


def test_vocabularies_come_from_the_corpus() -> None:
    print("== vocabularies are drawn only from the project's normative sources ==")
    nist = CORPUS["nist_ai_rmf"]
    check(all(code in nist for code in V.NIST_CATEGORIES), "every NIST AI RMF category is in the NIST corpus text")
    check(all(r in nist for r in V.RESPONSES), "the four risk responses are NIST AI RMF MANAGE 1's")
    check("likelihood and magnitude" in nist, "impact scales are NIST AI RMF MAP 5's")
    ms = CORPUS["ms_rai_v2"]
    check(all(re.search(rf"\b{g}\b", ms) for g in V.MS_GOALS),
          "every Microsoft RAI Standard v2 goal is in its corpus text")
    check("owner and a review cadence" in ms, "owner and review cadence come from the Standard")
    ieee = CORPUS["ieee_7000"]
    check("test, audit, measurement, or inspection" in ieee, "verification methods are IEEE 7000's")
    check("indirect stakeholders" in ieee, "direct/indirect stakeholders are IEEE 7000's")
    ecc = CORPUS["eccola"]
    check(all(f"**{c} {t}" in ecc or f"**{c} " in ecc for c, t in V.ECCOLA_CARDS.items()), "all 21 ECCOLA cards are in its corpus text")
    check(len(V.ECCOLA_CARDS) == 21, "exactly 21 cards")
    pl = CORPUS["pl_2338_2023"]
    check(all(w in pl for w in ("vulnerability", "irreversibility", "scale")),
          "the magnitude anchors use PL 2338/2023's harm criteria")
    for engine in ("coverage", "drift", "risk_screen", "story_map", "traceability"):
        text = (ROOT / "raia" / "rationale" / f"{engine}.py").read_text()
        types = set(re.findall(r'type="([a-z_]+)"', text))
        owners = set(re.findall(r'decision_owner="([a-z_]+)"', text))
        check(types <= set(V.ISSUE_TYPES) and owners <= set(V.OWNER_ROLES),
              f"{engine}: every engine issue uses the closed vocabularies")


def test_rubric() -> None:
    print("== risk level and priority are computed by code ==")
    check(rubric.risk_level("severe", "observed") == "critical", "severe × observed = critical")
    check(rubric.risk_level("negligible", "rare") == "low", "negligible × rare = low")
    check(rubric.risk_level("bogus", "rare") == "medium", "an unknown placement is never silently low")
    monotonic = all(
        V.rank(V.PRIORITIES, rubric.RISK_MATRIX[m][l]) <= V.rank(V.PRIORITIES, rubric.RISK_MATRIX[m][l2])
        for m in V.MAGNITUDE for l, l2 in zip(V.LIKELIHOOD, V.LIKELIHOOD[1:])
    ) and all(
        V.rank(V.PRIORITIES, rubric.RISK_MATRIX[m][l]) <= V.rank(V.PRIORITIES, rubric.RISK_MATRIX[m2][l])
        for l in V.LIKELIHOOD for m, m2 in zip(V.MAGNITUDE, V.MAGNITUDE[1:])
    )
    check(monotonic, "the matrix never lowers a level as likelihood or magnitude grows")
    legal = rubric.prioritise("limited", "rare", [], ["legal"], {})
    check(legal["priority"] == "high" and legal["risk_level"] == "low", "a legally grounded finding is at least high")
    floor = rubric.prioritise("limited", "rare", ["eu.art5"], [], {"eu.art5": ("critical", "prohibited")})
    check(floor["priority"] == "critical" and floor["blocking"], "a prohibited-practice floor is critical and blocking")
    check("raised to critical" in floor["priority_basis"], "the basis says why")


def _rationale(agent_key: str) -> RationaleResult:
    return AGENTS[agent_key].spec.engine(EXAMPLES[agent_key], {}) if agent_key == "risk_classifier" else RationaleResult(engine="t")


def _record(**over):
    base = {
        "summary": "s", "overall_status": "on_track", "declared_verdict": {"eu_tier": "high-risk", "br_tier": "high risk"},
        "agrees_with_rule_engine": True, "disagreement_rationale": "",
        "findings": [
            {"id": "F1", "title": "t", "statement": "x", "principle": "fairness", "nist_category": "MAP 5",
             "magnitude": "limited", "likelihood": "possible", "placement_rationale": "r", "citations": [ADVISORY]},
            {"id": "F2", "title": "t2", "statement": "x", "principle": "human_oversight", "nist_category": "GOVERN 2",
             "magnitude": "significant", "likelihood": "likely", "placement_rationale": "r", "citations": [CITE]},
        ],
        "actions": [
            {"id": "A1", "finding_ids": ["F2", "F9"], "action": "do", "response": "mitigate", "owner_role": "product",
             "lifecycle_stage": "plan_and_design", "review_cadence": "once", "verification_method": "audit",
             "evidence_artifact": "doc"},
            {"id": "A2", "finding_ids": ["F1"], "action": "live with it", "response": "accept", "owner_role": "product",
             "lifecycle_stage": "plan_and_design", "review_cadence": "once", "verification_method": "inspection",
             "evidence_artifact": "decision record"},
        ],
        "open_issues": [], "not_grounded": [], "coverage": [],
        "extension": {"prohibited_screen": "p", "eu_tier_justification": "e", "br_tier_justification": "b",
                      "obligations": [], "human_oversight_assessment": "h", "affected_persons_rights": "a",
                      "impact_assessments": "i"},
    }
    base.update(over)
    return base


def test_parse_and_fallback() -> None:
    print("== parsing, repair prompt and the fallback record ==")
    text = "Here it is:\n```json\n" + json.dumps(_record()) + "\n```"
    rec, errors = assemble.parse_record("risk_classifier", text)
    check(rec is not None and not errors, "a fenced record validates")
    bad = _record()
    bad["findings"][0]["magnitude"] = "catastrophic"
    rec, errors = assemble.parse_record("risk_classifier", json.dumps(bad))
    check(rec is None and any("findings.0.magnitude" in e for e in errors), "an off-scale value is rejected with its path")
    rec, errors = assemble.parse_record("risk_classifier", "I think the system is high risk.")
    check(rec is None and errors, "prose is not a record")
    check("did not validate" in assemble.repair_prompt(errors), "the repair prompt carries the errors")
    r = _rationale("risk_classifier")
    fb = assemble.finalize("risk_classifier", assemble.fallback_record("risk_classifier", r, errors, "prose"),
                           r, EVIDENCE, AGENTS["risk_classifier"].spec)
    check(checks.check_schema(fb).level == FAIL, "a fallback record fails the contract check")
    check(len(fb["open_issues"]) == len(r.open_issues), "…and still carries every engine issue")
    md = render.render("risk_classifier", fb, r.data, r.checklist_keys())
    check("Unparsed Model Reply" in md and "prose" in md, "…and shows the raw reply to the reviewer")


def test_finalize() -> None:
    print("== finalisation: what code decides ==")
    r = _rationale("risk_classifier")
    spec = AGENTS["risk_classifier"].spec
    rec = assemble.finalize("risk_classifier", _record(), r, EVIDENCE, spec)
    check([f["id"] for f in rec["findings"]] == ["RC-F1", "RC-F2"], "findings get stable, agent-prefixed ids")
    check(rec["actions"][0]["finding_ids"] == ["RC-F2"], "action links follow the renumbering")
    check(any("F9" in n for n in rec["contract_notes"]), "an unknown finding reference is removed and noted")
    check(rec["findings"][0]["priority"] == "low", "an advisory, limited × possible finding stays low")
    check(rec["findings"][1]["priority"] == "high", "a legally cited finding is raised to high")
    check(rec["actions"][0]["priority"] == "high", "an action inherits the priority of what it answers")
    engine = [i for i in rec["open_issues"] if i["origin"] == "engine"]
    check(len(engine) == len(r.open_issues) and all(i["type"] in V.ISSUE_TYPES for i in engine),
          "every engine issue is carried forward, typed")
    check(any(i["type"] == "risk_acceptance" and "RC-A2" in i["links"] for i in rec["open_issues"]),
          "accepting a risk opens an issue for a person")
    check(rec["overall_status"] != "on_track", "overall status is raised when issues are open")
    check(rec["meta"]["schema_version"] == V.SCHEMA_VERSION and rec["meta"]["frameworks"], "the record is stamped")
    again = assemble.finalize("risk_classifier", rec, r, EVIDENCE, spec)
    from raia.pipeline import _core
    check(_core(again) == _core(rec), "finalising twice changes nothing")

    dis = assemble.finalize("risk_classifier", _record(agrees_with_rule_engine=False, disagreement_rationale="Art. 6(3) holds"),
                            r, EVIDENCE, spec)
    check(any(i["type"] == "engine_disagreement" and "Art. 6(3)" in i["description"] for i in dis["open_issues"]),
          "a declared disagreement becomes an open issue (reconciliation)")

    prohibited = AGENTS["risk_classifier"].spec.engine(
        {**EXAMPLES["risk_classifier"], "prohibited_practices": ["social_scoring"]}, {})
    blocked = assemble.finalize("risk_classifier", _record(findings=[{**_record()["findings"][0], "links": ["prohibited_screen"]}],
                                                           actions=[]), prohibited, EVIDENCE, spec)
    check(blocked["findings"][0]["priority"] == "critical" and blocked["overall_status"] == "blocked",
          "a prohibited practice makes the finding critical and the record blocked")

    audit = RationaleResult(engine="t", verdict={"not_verified": ["EVR-1"], "assessable": []},
                            data={"audited_items": [{"id": "EVR-1", "computed_verdict": "NOT VERIFIED"}]})
    arec = _record(extension={"items": [{"item_id": "EVR-1", "verdict": "satisfied", "evidence": "trust me"}],
                              "accountability_log": [], "upcoming_checkpoints": []}, declared_verdict={})
    arec = assemble.finalize("auditor", arec, audit, EVIDENCE, AGENTS["auditor"].spec)
    check(arec["extension"]["items"][0]["verdict"] == "not_verified", "an upgraded verdict is restored by code")
    check(any(i.code == "verdicts.upgraded" and i.level == FAIL for i in checks.check_corrections(arec)),
          "…and the attempt is reported as a failure")


def test_render_and_schema() -> None:
    print("== the one layout, and the schema the model sees ==")
    for key in AGENTS:
        schema = model_facing_schema(key)
        dumped = json.dumps(schema)
        check('"priority"' not in dumped and '"risk_level"' not in dumped and '"computed"' not in dumped,
              f"{key}: computed fields are hidden from the model")
        check(render.required_sections(key)[:4] == ["Summary", "Action Plan", "Open Issues", "Findings"]
              and render.required_sections(key)[-3:] == render.COMMON_TAIL, f"{key}: shared frame around its own sections")
        check(AGENTS[key].spec.required_sections == render.required_sections(key), f"{key}: the spec uses the contract's layout")
    r = _rationale("risk_classifier")
    r.checklist = [ChecklistItem("tier_eu", "x")]
    rec = assemble.finalize("risk_classifier", _record(coverage=[{"key": "tier_eu", "status": "covered", "justification": "j"}]),
                            r, EVIDENCE, AGENTS["risk_classifier"].spec)
    md = render.render("risk_classifier", rec, r.data, r.checklist_keys())
    check(all(f"## {s}" in md for s in render.required_sections("risk_classifier")), "every section is rendered")
    block = parse_machine_block(md)
    check(block.get("coverage.tier_eu", "").startswith("covered") and block.get("verdict.agrees_with_screen") == "yes",
          "the machine block is rendered from the record")
    check(check_citations(md, [CITE, ADVISORY]).level == PASS, "citations inside tables still resolve")
    prompt = contract_text("risk_classifier", ["eu_tier", "br_tier"], r, [CITE])
    built = mock.build(prompt)
    check(record_model("risk_classifier").model_validate(built) is not None, "the offline double's record validates")


def test_published_schemas_are_current() -> None:
    print("== published schemas ==")
    from raia.contract.export_schema import OUT, generated

    stale = [n for n, t in generated().items() if not (OUT / n).exists() or (OUT / n).read_text(encoding="utf-8") != t]
    from raia.contract.agent_cards import OUT as CARDS, generated as cards

    stale_cards = [n for n, t in cards().items() if not (CARDS / n).exists() or (CARDS / n).read_text(encoding="utf-8") != t]
    check(not stale_cards, f"docs/agents cards match the code ({stale_cards or 'all current'}; run python -m raia.contract.agent_cards)")
    check(not stale, f"docs/schema matches the code ({stale or 'all current'}; run python -m raia.contract.export_schema)")


def test_action_plan() -> None:
    print("== the project action plan ==")
    r = _rationale("risk_classifier")
    rec = assemble.finalize("risk_classifier", _record(), r, EVIDENCE, AGENTS["risk_classifier"].spec)

    class Repo:
        def existing_artifacts(self):
            return ["risk_classification"]

        def read_data(self, key):
            return {"structured": {"record": rec}}

    rows = action_plan.project_actions(Repo())
    check([x["id"] for x in rows] == ["RC-A1", "RC-A2"], "actions are sorted by computed priority")
    check(action_plan.to_csv(rows).splitlines()[0].startswith("id,priority,stage"), "CSV export has the standard columns")
    check(json.loads(action_plan.to_json(rows))["schema"] == V.SCHEMA_VERSION, "JSON export is versioned")


def test_reading_order() -> None:
    print("== every record reads summary, actions, deep dive ==")
    r = _rationale("risk_classifier")
    rec = assemble.finalize("risk_classifier", _record(headline="High-risk: add human review first."), r, EVIDENCE,
                            AGENTS["risk_classifier"].spec)
    dg = digest.build("risk_classifier", rec, r.data)
    check(dg["headline"] == "High-risk: add human review first.", "the headline leads")
    kpi = {k["label"]: k for k in dg["kpis"]}
    check(kpi["Risks identified"]["value"] == len(rec["findings"]) and kpi["Actions to take"]["value"] == len(rec["actions"])
          and kpi["Decisions needed"]["value"] == len(rec["open_issues"]), "the summary counts are the record's counts")
    grouped = [a["id"] for g in dg["action_groups"] for a in g["actions"]]
    check(sorted(grouped) == sorted(a["id"] for a in rec["actions"]) and len(grouped) == len(set(grouped)),
          "every action appears exactly once in the action groups")
    members = {k: m for k, _, m, _ in V.ACTION_GROUPS}
    check(all(a["priority"] in members[g["key"]] for g in dg["action_groups"] for a in g["actions"]),
          "…in the group of its computed priority")
    top = dg["top_issues"][0]
    check(top["priority"] == max((f["priority"] for f in rec["findings"]), key=lambda p: V.rank(V.PRIORITIES, p)),
          "the main issues start with the highest priority")
    blocked = json.loads(json.dumps(rec))
    low = min(blocked["findings"], key=lambda f: V.rank(V.PRIORITIES, f["priority"]))
    low["blocking"] = True
    check(digest.build("risk_classifier", blocked, r.data)["top_issues"][0]["id"] == low["id"],
          "a blocking finding leads the main issues, whatever its priority")
    check(all(s.get("conclusion") for s in dg["deep"]), "every deep-dive section opens with a conclusion")
    check([s["md_title"] for s in dg["deep"]] == render.required_sections("risk_classifier")[3:],
          "the deep dive has exactly the document's analysis and appendix sections")
    md = render.render("risk_classifier", rec, r.data, r.checklist_keys())
    order = [md.index(f"## {t}") for t in render.required_sections("risk_classifier")]
    check(order == sorted(order), "the document follows the same order as the screen")
    check(md.index("High-risk: add human review first.") < md.index("## Action Plan"), "the document leads with the headline")
    older = dict(rec)
    older.pop("headline")
    check(digest.build("risk_classifier", older, r.data)["headline"] == "s",
          "a record written before headlines existed falls back to its summary's first sentence")
    check(record_model("risk_classifier").model_validate(_record()) is not None, "…and still validates")
    check("headline" in model_facing_schema("risk_classifier")["required"], "the model is always asked for a headline")


def test_story_conflicts() -> None:
    print("== conflicting existing criteria become decisions ==")
    from raia.rationale import story_map

    rationale = story_map.run(EXAMPLES["story_refiner"], {"requirements_review": {"data": {"evr_ids": ["EVR-1"]}}})
    stories = [{"story_id": sid, "no_impact_reason": "none"} for sid in rationale.verdict["story_ids"]]
    stories[1] = {"story_id": "S2", "criteria": [], "eccola_cards": ["#10"], "conflicts": [
        {"criterion_id": "S2-E1", "conflicts_with": ["EVR-1"], "problem": "Rejects with no human review.",
         "suggested_rewrite": "Reject only after a recruiter confirms."}]}
    base = {"headline": "h", "summary": "s", "overall_status": "on_track", "declared_verdict": {"story_count": "3"},
            "agrees_with_rule_engine": True, "findings": [], "actions": [], "open_issues": [], "coverage": [],
            "extension": {"stories": stories, "sprint_ethics_log": "One paragraph from an older record."}}
    check(record_model("story_refiner").model_validate(base).extension.sprint_ethics_log
          == ["One paragraph from an older record."], "an older one-paragraph ethics log still reads, as one entry")
    spec = AGENTS["story_refiner"].spec
    rec = assemble.finalize("story_refiner", base, rationale, [], spec)
    conflict = [i for i in rec["open_issues"] if "S2-E1" in (i.get("links") or [])]
    check(len(conflict) == 1 and conflict[0]["type"] == "value_tradeoff" and conflict[0]["origin"] == "code",
          "one decision per conflict, raised by code")
    check(any(o.startswith("Rewrite it:") for o in conflict[0]["options"]), "…offering the suggested rewrite")
    again = assemble.finalize("story_refiner", rec, rationale, [], spec)
    check(len([i for i in again["open_issues"] if "S2-E1" in (i.get("links") or [])]) == 1,
          "finalising again does not duplicate it")
    resolved = json.loads(json.dumps(rec))
    resolved["extension"]["stories"][1]["conflicts"] = []
    after = assemble.finalize("story_refiner", resolved, rationale, [], spec)
    check(not any("S2-E1" in (i.get("links") or []) for i in after["open_issues"]),
          "a conflict a reviewer removes no longer opens a decision")
    paste = digest.build("story_refiner", rec, rationale.data)["paste"]
    check("[REVIEW" in paste and "S1 — Ranked shortlist" in paste, "the paste-ready stories mark the conflict for review")


def main() -> None:
    for fn in (test_vocabularies_come_from_the_corpus, test_rubric, test_parse_and_fallback,
               test_finalize, test_render_and_schema, test_published_schemas_are_current, test_action_plan,
               test_reading_order, test_story_conflicts):
        fn()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} contract check(s) failed:")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("All contract checks passed.")


if __name__ == "__main__":
    main()
