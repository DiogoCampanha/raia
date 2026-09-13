#!/usr/bin/env python3
"""
Smoke test: exercises the full RAIA pipeline offline.

Runs with the mock model and fake embeddings (no API key, no model download):

    RAIA_LLM_PROVIDER=mock RAIA_FAKE_EMBED=1 python tests/smoke_test.py

It covers the whole chain — corpus ingestion, pinned retrieval, stage gates,
decision procedures, the human-review interrupt, the rejection loop, approval,
Git persistence with structured sidecars and provenance, the Open Issues
register, restart recovery, and the session export — and then runs the
deterministic unit checks in ``tests/test_engines.py``.

Two invariants are asserted directly, because they are the claims the project
stands on:

* nothing is persisted without an explicit human approval, including on the
  restart-recovery path;
* a fabricated citation is *detected*, not merely discouraged.

Exits non-zero on any failure (usable in CI).
"""

import os
import sys
import tempfile
from pathlib import Path

# Force offline-friendly configuration BEFORE importing raia.
os.environ["RAIA_LLM_PROVIDER"] = "mock"
os.environ["RAIA_FAKE_EMBED"] = "1"
_tmp = tempfile.mkdtemp(prefix="raia_smoke_")
os.environ["RAIA_WORKSPACE_DIR"] = str(Path(_tmp) / "workspace")
os.environ["RAIA_CHROMA_DIR"] = str(Path(_tmp) / "chroma")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from raia.agents import AGENTS                                  # noqa: E402
from raia.agents.drift_monitor import compute_fairness_summary  # noqa: E402
from raia.examples import EXAMPLES                              # noqa: E402
from raia.export import session_bundle                          # noqa: E402
from raia.pipeline import StageRunner                           # noqa: E402
from raia.rag import NormativeRetriever, corpus_sections, ingest_corpus  # noqa: E402
from raia.repository import ArtifactRepository, OPEN, RESOLVED  # noqa: E402

PROJECT = "smoke-project"


def check(cond: bool, label: str) -> None:
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond:
        sys.exit(1)


def main() -> None:
    print("== 1. Corpus ingestion ==")
    n = ingest_corpus(verbose=False)
    check(n > 20, f"ingested {n} chunks (> 20)")

    print("== 2. Every pinned section exists in the corpus ==")
    sections = corpus_sections()
    bad = []
    for agent in AGENTS.values():
        if agent.spec.engine is None:
            continue
        try:
            rationale = agent.spec.engine(EXAMPLES.get(agent.spec.key, {}), {})
        except Exception:  # noqa: BLE001 - engines needing upstream are covered later
            continue
        for pin in rationale.pins:
            if pin.section not in sections.get(pin.source, []):
                bad.append(f"{agent.spec.key}: {pin.source} / {pin.section}")
    check(not bad, f"all pinned sections resolve ({bad or 'none missing'})")

    print("== 3. Retrieval: pins always present, citations indexed ==")
    r = NormativeRetriever()
    chunks = r.retrieve(
        "high-risk employment recruitment obligations",
        sources=["eu_ai_act", "pl_2338_2023"],
        pins=[("eu_ai_act", "Article 6 and Annex III — High-Risk AI Systems", "area list")],
    )
    check(any(c.pinned for c in chunks), "a pinned section is in the result set")
    check(all(c.source in ("eu_ai_act", "pl_2338_2023") for c in chunks), "source filter respected")
    check(all(c.authority == "legal" for c in chunks), "authority metadata present")
    check(all(c.chunk_id for c in chunks), "every excerpt carries an id for provenance")
    check("[Source:" in NormativeRetriever.citation_index(chunks)[0], "citation index built")

    print("== 4. Stage gates ==")
    runner = StageRunner()
    missing = runner.check_gate(PROJECT, "requirements_reviewer")
    check("risk_classification" in missing, "downstream agent blocked before upstream approval")

    print("== 5. Required inputs are enforced ==")
    rc = AGENTS["risk_classifier"]
    check(len(rc.missing_inputs({})) > 0, "an empty form is refused")
    check(rc.missing_inputs(EXAMPLES["risk_classifier"]) == [], "the example scenario is complete")

    print("== 6. Risk Classifier: decision procedure, review, rejection loop ==")
    out = runner.start(PROJECT, "risk_classifier", EXAMPLES["risk_classifier"])
    check(out["status"] == "awaiting_review", "run pauses at the human checkpoint")
    payload = out["payload"]
    check(payload["rationale"]["verdict"]["eu_tier"].startswith("high-risk"),
          "employment scenario computed as high-risk")
    check(len(payload["evidence"]) > 0 and any(e["pinned"] for e in payload["evidence"]),
          "the gate is given its evidence, including the required excerpts")
    check(payload["validation"]["level"] == "pass", "automated checks pass on the mock draft")

    repo = ArtifactRepository(PROJECT)
    check(repo.read_artifact("risk_classification") is None,
          "INVARIANT: nothing is persisted while a draft is under review")

    out = runner.resume(PROJECT, "risk_classifier",
                        {"action": "reject", "feedback": "Be specific about oversight.",
                         "reason": "too_vague"})
    check(out["payload"]["attempt"] == 2, "rejection loops back with feedback")
    check(repo.read_artifact("risk_classification") is None,
          "INVARIANT: a rejected draft is still not persisted")

    out = runner.resume(PROJECT, "risk_classifier",
                        {"action": "approve", "content": out["payload"]["draft"],
                         "approver": "smoke-tester"})
    check(out["status"] == "approved" and out["commit"], "approval persists and commits")

    print("== 7. Provenance and the structured sidecar ==")
    text = repo.read_artifact("risk_classification") or ""
    check("approved by: smoke-tester" in text, "approver recorded in the artifact header")
    check("corpus version:" in text and "prompt sha256/16:" in text,
          "corpus version and prompt digest recorded")
    data = repo.read_data("risk_classification")
    prov = data["provenance"]
    check(prov["attempt"] == 2, "the approved attempt is recorded, not the first one")
    check(len(prov["corpus"]["excerpts"]) > 0, "every excerpt in the prompt is identified")
    check(prov["approval"]["rejections_before_approval"][0]["reason_code"] == "too_vague",
          "the rejection reason is part of the record")
    check(data["structured"]["computed_verdict"]["eu_tier"].startswith("high-risk"),
          "the sidecar carries the machine-readable verdict")

    print("== 8. Open Issues register ==")
    issues = repo.open_issues()
    check(len(issues) > 0, f"{len(issues)} conflict(s) recorded for human arbitration")
    check(all(i["status"] == OPEN for i in issues), "new issues start open")
    check(repo.set_issue_status(issues[0]["id"], RESOLVED, "settled by legal", "smoke-tester"),
          "an issue can be arbitrated")
    check(repo.open_issues()[0]["status"] == RESOLVED, "arbitration is recorded")

    print("== 9. The remaining four agents ==")
    for key in ("requirements_reviewer", "story_refiner", "auditor", "drift_monitor"):
        out = runner.start(PROJECT, key, EXAMPLES[key])
        payload = out["payload"]
        level = payload["validation"]["level"]
        failed = [i["code"] for i in payload["validation"]["items"] if i["level"] == "fail"]
        check(level != "fail", f"{key}: automated checks pass ({failed or 'no failures'})")
        check(bool(payload["rationale"]["engine"]), f"{key}: a decision procedure ran")
        runner.resume(PROJECT, key,
                      {"action": "approve", "content": payload["draft"], "approver": "smoke-tester"})
        check(repo.read_artifact(AGENTS[key].spec.output_key) is not None, f"{key}: artifact committed")

    print("== 10. Cross-agent structure actually flows ==")
    review = repo.read_data("requirements_review")["structured"]
    check(len(review["evr_ids"]) > 0, "the requirements review published a requirement register")
    audit = repo.read_data("audit_report")["structured"]
    check(len(audit.get("audited_items", [])) > 0,
          "the auditor read that register rather than re-reading prose")

    print("== 11. A fabricated citation is detected ==")
    agent = AGENTS["risk_classifier"]
    from raia.rationale.types import empty_rationale
    from raia import validators as V

    fake = "## Risk Classification\nHigh risk. [Source: EU AI Act — Article 99 | authority: legal]"
    report = V.check_citations(fake, NormativeRetriever.citation_index(chunks))
    check(report.level == V.FAIL, "a citation to an excerpt that was not retrieved is flagged")

    print("== 12. Restart recovery still goes through the gate ==")
    fresh = ArtifactRepository("restart-project")
    saved = runner.start("restart-project", "risk_classifier", EXAMPLES["risk_classifier"])
    pending = fresh.load_pending("risk_classifier")
    check(pending is not None, "an in-review draft is saved to disk")
    lost = StageRunner()  # a new process: the in-memory thread is gone
    check(not lost.has_thread("restart-project", "risk_classifier"), "the graph thread is lost")
    restored = lost.restore("restart-project", "risk_classifier", pending)
    check(restored["status"] == "awaiting_review",
          "INVARIANT: a restored review stops at the human checkpoint again")
    check(fresh.read_artifact("risk_classification") is None,
          "INVARIANT: recovery persists nothing on its own")
    done = lost.resume("restart-project", "risk_classifier",
                       {"action": "approve", "content": restored["payload"]["draft"],
                        "approver": "smoke-tester"})
    check(bool(done["commit"]), "the restored review can then be approved normally")

    print("== 13. Deterministic metrics stay reproducible ==")
    table = compute_fairness_summary(EXAMPLES["drift_monitor"]["telemetry_csv"])
    # Widest gap in the final window of the example: gender=M 0.39 vs gender=X 0.21.
    check("| Window |" in table and "0.1800" in table, "fairness table computed outside the UI")

    print("== 14. Audit trail and export ==")
    history = repo.history()
    check(len(history) >= 6, f"{len(history)} commits recorded")
    events = [e["kind"] for e in repo.events()]
    check("rejection" in events and "approval" in events, "evaluation events captured")
    bundle = session_bundle(repo)
    check(len(bundle) > 1000 and bundle[:2] == b"PK", "session export produces a zip")

    print("== 15. Deterministic unit checks ==")
    import tests.test_engines as engines  # noqa: E402

    engines.main()


if __name__ == "__main__":
    main()
    print("\nAll smoke checks passed.")
