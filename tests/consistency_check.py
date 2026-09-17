#!/usr/bin/env python3
"""
Run-to-run consistency of the RAIA record.

    python tests/consistency_check.py --agent risk_classifier --runs 5 [--out report.json]

Runs one agent several times on the same project and the same answers (the
canonical resume-screening scenario, with every upstream stage approved once
first) and measures how much the standard record agrees with itself across
runs: contract conformance, declared verdicts, overall status, the principles
and NIST AI RMF categories of the findings, the computed priorities, the owners
of the actions and the types of the open issues.

Nothing is persisted from the measured runs: they never reach the approval gate.
With the mock model every figure is 1.0 by construction — the script is meant to
be run with a real provider (``RAIA_LLM_PROVIDER=anthropic`` and a key), where
it turns "the standard makes outputs more consistent" into a number.
"""

import argparse
import itertools
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("RAIA_LLM_PROVIDER", "mock")
os.environ.setdefault("RAIA_FAKE_EMBED", "1")
_tmp = tempfile.mkdtemp(prefix="raia_consistency_")
os.environ.setdefault("RAIA_WORKSPACE_DIR", str(Path(_tmp) / "workspace"))


def jaccard(a: set, b: set) -> float:
    return 1.0 if not a and not b else len(a & b) / len(a | b)


def mean_pairwise(values: List[Any], score) -> float:
    pairs = list(itertools.combinations(values, 2))
    return round(sum(score(x, y) for x, y in pairs) / len(pairs), 3) if pairs else 1.0


def modal_share(values: List[Any]) -> float:
    if not values:
        return 1.0
    counts = Counter(json.dumps(v, sort_keys=True) for v in values)
    return round(counts.most_common(1)[0][1] / len(values), 3)


def measure(records: List[Dict[str, Any]], repairs: List[int]) -> Dict[str, Any]:
    ok = [r for r in records if not r.get("schema_errors")]
    return {
        "runs": len(records),
        "conformance_rate": round(len(ok) / len(records), 3) if records else 0,
        "mean_repairs": round(sum(repairs) / len(repairs), 3) if repairs else 0,
        "declared_verdict_agreement": modal_share([r.get("declared_verdict") for r in ok]),
        "agrees_with_rule_engine_agreement": modal_share([r.get("agrees_with_rule_engine") for r in ok]),
        "overall_status_agreement": modal_share([r.get("overall_status") for r in ok]),
        "finding_principles_jaccard": mean_pairwise(
            [{f.get("principle") for f in r.get("findings") or []} for r in ok], jaccard),
        "finding_nist_categories_jaccard": mean_pairwise(
            [{f.get("nist_category") for f in r.get("findings") or []} for r in ok], jaccard),
        "highest_priority_agreement": modal_share(
            [max((f.get("priority") for f in r.get("findings") or []),
                 key=lambda p: ["low", "medium", "high", "critical"].index(p), default=None) for r in ok]),
        "priority_profile_agreement": modal_share(
            [sorted(Counter(f.get("priority") for f in r.get("findings") or []).items()) for r in ok]),
        "action_owner_jaccard": mean_pairwise(
            [{a.get("owner_role") for a in r.get("actions") or []} for r in ok], jaccard),
        "issue_type_jaccard": mean_pairwise(
            [{i.get("type") for i in r.get("open_issues") or [] if i.get("origin") != "engine"} for r in ok], jaccard),
        "finding_counts": [len(r.get("findings") or []) for r in ok],
        "action_counts": [len(r.get("actions") or []) for r in ok],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--agent", default="risk_classifier")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    from raia.agents import AGENTS
    from raia.examples import EXAMPLES
    from raia.pipeline import StageRunner
    from raia.rag import index_exists, ingest_corpus
    from raia.repository import ArtifactRepository

    if not index_exists():
        ingest_corpus(verbose=False)
    project = "consistency"
    runner = StageRunner()
    order = list(AGENTS)
    for key in order[: order.index(args.agent)]:
        runner.start(project, key, EXAMPLES[key])
        runner.resume(project, key, {"action": "approve", "approver": "consistency-check"})
        print(f"approved upstream stage {key}")

    records, repairs = [], []
    repo = ArtifactRepository(project)
    for i in range(args.runs):
        run = AGENTS[args.agent].run(repo, EXAMPLES[args.agent])
        records.append(run.record)
        repairs.append(run.repairs)
        print(f"run {i + 1}/{args.runs}: {len(run.record.get('findings') or [])} finding(s), "
              f"status {run.record.get('overall_status')}")

    from raia import config

    report = {"agent": args.agent, "provider": config.LLM_PROVIDER, "model": config.LLM_MODEL,
              "temperature": config.LLM_TEMPERATURE, **measure(records, repairs)}
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
