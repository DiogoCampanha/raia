#!/usr/bin/env python3
"""
The RAIA AI Skill: the instructions, the references and the download.

    python tests/test_skill.py

Runs offline with the mock model. What is asserted, and why it matters:

* **The skill cannot contradict the software.** Every vocabulary, scale, rule
  and table in it is generated from the code; the copy in ``docs/ai-skill/``
  must match what the code generates now.
* **It travels.** SKILL.md is a valid skill (name, description) and small enough
  to paste into an assistant's custom instructions; every file it points to is
  in the download.
* **It stays on the project's ground.** Only the project's normative sources,
  and no references to papers or their sections.
* **The download is the project's outputs for an assistant, not for the
  research.** No evaluation events, history or hash chain; no email address in
  the generated context; it works from the first approved stage.
"""

import io
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

os.environ["RAIA_LLM_PROVIDER"] = "mock"
os.environ["RAIA_FAKE_EMBED"] = "1"
os.environ.setdefault("RAIA_AUTH", "dev")
_tmp = tempfile.mkdtemp(prefix="raia_skill_")
os.environ["RAIA_WORKSPACE_DIR"] = str(Path(_tmp) / "workspace")
os.environ["RAIA_CHROMA_DIR"] = str(Path(_tmp) / "chroma")
if not os.environ.get("RAIA_DATABASE_URL"):
    os.environ["RAIA_DATABASE_URL"] = f"sqlite:///{Path(_tmp) / 'raia.db'}"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from raia import backlog as B                                    # noqa: E402
from raia.contract import vocab as V                             # noqa: E402
from raia.examples import EXAMPLES                               # noqa: E402
from raia.export import session_bundle, skill_bundle, skill_bundle_name  # noqa: E402
from raia.pipeline import StageRunner                            # noqa: E402
from raia.projects import ProjectService                         # noqa: E402
from raia.rag import ingest_corpus                               # noqa: E402
from raia.repository import ARTIFACT_FILES                       # noqa: E402
from raia.skill import build                                     # noqa: E402

FAILURES = []


def check(cond: bool, label: str) -> None:
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond:
        FAILURES.append(label)


SKILL = build.SKILL_DIR
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
#: Standards and laws outside the project's base that must not creep in.
FOREIGN = ("ISO/IEC", "ISO 42001", "GDPR", "LGPD", "OECD", "UNESCO", "EEOC", "four-fifths", "80% rule",
           "Blueprint for an AI Bill", "Singapore", "Model AI Governance")
PAPER = re.compile(r"\b(paper|qualifica|ISE'?2\d|LAAI|Section \d|§\s*\d|Figure \d|Table \d)", re.I)


def approve(svc, user, pid, key, inputs):
    out = svc.start_run(user, pid, key, inputs)
    svc.resume(user, pid, key, {"action": "approve", "draft_id": out["payload"]["draft_id"],
                                 "record": out["payload"]["record"]})


def test_static_files() -> None:
    print("== the instructions and references ==")
    files = build.static_files()
    skill = files[f"{SKILL}/SKILL.md"]
    front = re.match(r"^---\nname: (?P<name>[^\n]+)\ndescription: (?P<desc>[^\n]+)\n---\n", skill)
    check(bool(front), "SKILL.md opens with a name and a description")
    check(front and front["name"] == SKILL and re.fullmatch(r"[a-z0-9-]{1,64}", SKILL) is not None,
          "…the name is the folder's, lower-case with hyphens")
    check(front and len(front["desc"]) <= 1024 and "<" not in front["desc"], "…the description fits a skill's limits")
    check(len(skill) <= build.SKILL_MAX_CHARS, f"SKILL.md can be pasted as custom instructions ({len(skill)} chars)")
    check(not any("{{" in t for t in files.values()), "every generated block is filled")
    for ref in sorted(set(re.findall(r"`(references/[\w.-]+\.md)`", skill))):
        check(f"{SKILL}/{ref}" in files, f"SKILL.md points at {ref}, which exists")
    playbooks = files[f"{SKILL}/references/playbooks.md"]
    for pid in sorted(set(re.findall(r"\bP\d\b", skill))):
        check(f"## {pid} " in playbooks, f"playbook {pid} named in SKILL.md exists")
    vocab = files[f"{SKILL}/references/vocabulary.md"]
    for name, values in (("priorities", V.PRIORITIES), ("magnitude", V.MAGNITUDE), ("likelihood", V.LIKELIHOOD),
                         ("responses", V.RESPONSES), ("owner roles", V.OWNER_ROLES),
                         ("issue types", V.ISSUE_TYPES), ("audit verdicts", V.AUDIT_VERDICTS),
                         ("MS goals", tuple(V.MS_GOALS)), ("ECCOLA cards", tuple(V.ECCOLA_CARDS)),
                         ("NIST categories", tuple(V.NIST_CATEGORIES))):
        check(all(f"`{v}`" in vocab for v in values), f"the vocabulary lists every value of {name}")
    from raia.contract import rubric
    check(rubric.matrix_md() in vocab, "the risk matrix is the one code applies")
    reading = files[f"{SKILL}/references/reading-the-outputs.md"]
    named = set(re.findall(r"`(\d\d\w?_[a-z_]+\.md)`", reading))
    check(named and named <= set(ARTIFACT_FILES.values()), "every file the reading guide names is a RAIA artifact")
    text = "\n".join(files.values())
    foreign = [w for w in FOREIGN if w.lower() in text.lower()]
    check(not foreign, f"only the project's normative sources ({foreign or 'none foreign'})")
    check(not PAPER.search(text), "no paper or section references")
    check(f"`{SKILL}/SKILL.md`" in files["AGENTS.md"], "AGENTS.md points coding assistants at the skill")

    print("== the copy in docs/ai-skill matches the code ==")
    stale = [n for n, t in build.generated().items()
             if not (build.OUT / n).exists() or (build.OUT / n).read_text(encoding="utf-8") != t]
    check(not stale, f"docs/ai-skill is current ({stale or 'all current'}; run python -m raia.skill.build)")


def test_bundle() -> None:
    print("== the download ==")
    ingest_corpus(verbose=False)
    svc = ProjectService(runner=StageRunner())
    ana = svc.sign_in("ana@example.org", "Ana Souza")

    early = svc.create_project(ana, "Early project")
    approve(svc, ana, early.id, "risk_classifier", EXAMPLES["risk_classifier"])
    z = zipfile.ZipFile(io.BytesIO(skill_bundle(svc.repository(ana, early.id), early.name)))
    ctx = z.read(f"{SKILL}/project/PROJECT_CONTEXT.md").decode()
    check("No requirements approved yet" in ctx and "Not run yet" in ctx,
          "with only the classification approved, the context says what is missing")
    check("high-risk" in ctx and "What RAIA was told" in ctx and "Employment" in ctx,
          "…and carries the tiers and the answers the classification rests on")

    p = svc.create_project(ana, "Hiring assistant")
    approve(svc, ana, p.id, "risk_classifier", EXAMPLES["risk_classifier"])
    approve(svc, ana, p.id, "requirements_reviewer", EXAMPLES["requirements_reviewer"])
    approve(svc, ana, p.id, "story_generate", EXAMPLES["story_generate"])
    svc.create_sprint(ana, p.id, name="Sprint 1", capacity=3)
    picked = [x["id"] for x in svc.suggest_sprint(ana, p.id)["suggested"]]
    svc.schedule(ana, p.id, picked)
    svc.start_sprint(ana, p.id)
    repo = svc.repository(ana, p.id)
    data = skill_bundle(repo, p.name)
    z = zipfile.ZipFile(io.BytesIO(data))
    names = set(z.namelist())
    expected = {"README_FIRST.md", "AGENTS.md", f"{SKILL}/SKILL.md",
                *(f"{SKILL}/references/{r}" for r in ("reading-the-outputs.md", "vocabulary.md", "rai-guidelines.md",
                                                      "playbooks.md", "templates.md")),
                *(f"{SKILL}/project/{f}" for f in ("PROJECT_CONTEXT.md", "MANIFEST.txt", "backlog.csv", "backlog.json",
                                                   "sprints.json", "roadmap.csv", "action_plan.csv", "action_plan.json")),
                f"{SKILL}/project/artifacts/{ARTIFACT_FILES['requirements_review']}"}
    check(expected <= names, f"the skill, AGENTS.md and the outputs are in the zip ({sorted(expected - names) or 'all'})")
    research = [n for n in names if n.rsplit("/", 1)[-1] in
                ("evaluation_events.jsonl", "git_history.txt", "history_chain.json")]
    check(not research, "no research data, history or hash chain")
    check(all(n.startswith(f"{SKILL}/") or n in ("README_FIRST.md", "AGENTS.md") for n in names),
          "the skill folder is self-contained: only README_FIRST.md and AGENTS.md sit beside it")
    ctx = z.read(f"{SKILL}/project/PROJECT_CONTEXT.md").decode()
    bl, _ = B.load(repo)
    evrs = [e for s in bl["stories"] for e in s.get("evr_ids") or []]
    check(all(e in ctx for e in evrs) and all(s["id"] in ctx for s in bl["stories"]),
          "the context lists the requirements and every backlog story")
    check(all(i["id"] in ctx for i in repo.open_issues() if i.get("status", "open") == "open"),
          "…and every open decision")
    check(not EMAIL.search(ctx), "the generated context names no one by email")
    check("SPR-1" in ctx, "…and shows the open sprint")
    readme = z.read("README_FIRST.md").decode()
    check(p.name in readme and "{{" not in readme, "README_FIRST names the project")
    full = set(zipfile.ZipFile(io.BytesIO(session_bundle(repo, p.name))).namelist())
    check("evaluation_events.jsonl" in full and "artifacts/03_requirements_review.md" in full,
          "the full project download is unchanged")
    check(skill_bundle_name(p.name).startswith("raia-hiring-assistant-ai-skill-"), "the file is named for the project")


def main() -> None:
    test_static_files()
    test_bundle()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed")
        sys.exit(1)
    print("All AI Skill checks passed.")


if __name__ == "__main__":
    main()
