#!/usr/bin/env python3
"""
The RAIA AI Skill: the instructions, the references and the download.

    python tests/test_skill.py

Runs offline with the mock model. What is asserted, and why it matters:

* **The skill cannot contradict the software.** Every vocabulary, scale, rule
  and table in it is generated from the code; the copy in ``docs/ai-skill/``
  must match what the code generates now.
* **It travels.** SKILL.md is a valid skill (name, description, version) and
  small enough to paste into an assistant's custom instructions; every file it
  points to is in the download; the text names no assistant and assumes no
  connection; four formats are built from the same text.
* **The fixed part is frozen.** It takes no project, no person and no date, is
  identical byte for byte across projects and downloads, and its fingerprint is
  recorded: changing it without a new version fails here.
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
    print("== the fixed part: instructions and references ==")
    files = build.fixed_files()
    skill = files["SKILL.md"]
    front = re.match(r"^---\nname: (?P<name>[^\n]+)\ndescription: (?P<desc>[^\n]+)\n"
                     r"metadata:\n  version: \"(?P<version>[^\"\n]+)\"\n---\n", skill)
    check(bool(front), "SKILL.md opens with a name, a description and its version")
    check(front and front["name"] == SKILL and re.fullmatch(r"[a-z0-9-]{1,64}", SKILL) is not None,
          "…the name is the folder's, lower-case with hyphens")
    check(front and len(front["desc"]) <= 1024 and "<" not in front["desc"], "…the description fits a skill's limits")
    check(front and front["version"] == build.SKILL_VERSION, "…and the version is the one the code declares")
    check(len(skill) <= build.SKILL_MAX_CHARS, f"SKILL.md can be pasted as custom instructions ({len(skill)} chars)")
    check(not any("{{" in t for t in files.values()), "every generated block is filled")
    for ref in sorted(set(re.findall(r"`(references/[\w.-]+\.md)`", skill))):
        check(ref in files, f"SKILL.md points at {ref}, which exists")
    check(set(files) - {"SKILL.md"} == {f"references/{n}" for n in build._REFERENCE_ORDER},
          "every reference is named in the reading order of the single-file format")
    playbooks = files["references/playbooks.md"]
    for pid in sorted(set(re.findall(r"\bP\d+\b", skill))):
        check(f"## {pid} " in playbooks, f"playbook {pid} named in SKILL.md exists")
    vocab = files["references/vocabulary.md"]
    for name, values in (("priorities", V.PRIORITIES), ("magnitude", V.MAGNITUDE), ("likelihood", V.LIKELIHOOD),
                         ("responses", V.RESPONSES), ("owner roles", V.OWNER_ROLES),
                         ("issue types", V.ISSUE_TYPES), ("audit verdicts", V.AUDIT_VERDICTS),
                         ("MS goals", tuple(V.MS_GOALS)), ("ECCOLA cards", tuple(V.ECCOLA_CARDS)),
                         ("NIST categories", tuple(V.NIST_CATEGORIES))):
        check(all(f"`{v}`" in vocab for v in values), f"the vocabulary lists every value of {name}")
    from raia.contract import rubric
    check(rubric.matrix_md() in vocab, "the risk matrix is the one code applies")
    reading = files["references/reading-the-outputs.md"]
    named = set(re.findall(r"`(\d\d\w?_[a-z_]+\.md)`", reading))
    check(named and named <= set(ARTIFACT_FILES.values()), "every file the reading guide names is a RAIA artifact")
    text = "\n".join(files.values())
    foreign = [w for w in FOREIGN if w.lower() in text.lower()]
    check(not foreign, f"only the project's normative sources ({foreign or 'none foreign'})")
    check(not PAPER.search(text), "no paper or section references")
    check(f"`{SKILL}/SKILL.md`" in build.agents_md() and f"`{build.PROJECT_DIR}/PROJECT_CONTEXT.md`" in build.agents_md(),
          "AGENTS.md points coding assistants at the skill and at the project part")

    print("== the screen an assistant can run without a RAIA record is the rule engine's ==")
    from raia.agents import AGENTS
    from raia.rationale import risk_screen as RS
    screening = files["references/screening.md"]
    check(all(m["label"] in screening for m in RS.PROHIBITED_PRACTICES.values())
          and all(m["label"] in screening for m in RS.PURPOSE_AREAS.values()),
          "every prohibited practice and every high-risk area the engine knows is listed")
    check(all(t in screening for t in (RS.TIER_UNACCEPTABLE, RS.TIER_RESTRICTED, RS.TIER_HIGH, RS.TIER_LIMITED,
                                       RS.TIER_MINIMAL, RS.BR_EXCESSIVE, RS.BR_HIGH, RS.BR_NOT_LISTED)),
          "the tiers are named as the engine names them")
    codes = {c for c, _ in RS.EU_PROVIDER_HIGH_RISK + RS.EU_DEPLOYER_HIGH_RISK + RS.BR_HIGH_RISK + RS.BR_ALL_TIERS}
    codes |= {"eu.art27", "eu.art50", "eu.gpai", "eu.art6_3_doc", "br.publicity"}
    check(all(f"`{c}`" in screening for c in codes), "every obligation the engine can assemble is in the table")
    asked = [f.label for f in AGENTS["risk_classifier"].spec.input_fields if f.kind in ("select", "multiselect", "boolean")]
    check(all(q in screening for q in asked), "every structured question of the Risk Classifier is asked")
    check("self-assessed, not a RAIA record" in screening and "self-assessed, not a RAIA record" in skill,
          "…and the result is labelled as the assistant's own, not RAIA's")

    print("== the text is written for any assistant ==")
    named_tools = [w for w in ("Cursor", "ChatGPT", "Claude", "Copilot", "Gemini", ".cursor", ".claude") if w in text]
    check(not named_tools, f"the fixed part names no assistant ({named_tools or 'none'})")
    check("Never assume a connection" in skill and "Before you write anywhere" in playbooks,
          "it assumes no connection, and asks before writing where one exists")
    check("## P8 Review a product document" in playbooks and "## P11 Support a sprint ceremony" in playbooks
          and "Definition-of-done additions" in files["references/templates.md"],
          "it covers product documents and sprint ceremonies, not only the backlog")
    check("Without a project part" in skill and "Do not ask for it before helping" in skill,
          "it works with no RAIA project")
    for fmt, (label, ext, _) in build.FORMATS.items():
        readme = build.install_readme(fmt)
        check("{{" not in readme and build.SKILL_VERSION in readme and "fixed part" in readme
              and "project part" in readme, f"the {label} install note is filled and explains the two parts")

    print("== the fixed part is frozen ==")
    check(build.fixed_files() == files and build.fixed_zip() == build.fixed_zip(),
          "built twice, it is the same, byte for byte")
    check(build.fingerprint(files) == build.FIXED_FINGERPRINT,
          f"its fingerprint is the recorded one ({build.fingerprint(files)}); a change needs a new SKILL_VERSION "
          "and FIXED_FINGERPRINT in raia/skill/build.py")
    check(not EMAIL.search(text) and "your project" not in skill and not re.search(r"\b20\d\d-\d\d-\d\d\b", text),
          "it carries no project, no person and no date")

    print("== the copy in docs/ai-skill matches the code ==")
    wanted = build.generated()
    stale = [n for n, t in wanted.items()
             if not (build.OUT / n).exists() or (build.OUT / n).read_text(encoding="utf-8") != t]
    extra = [p.relative_to(build.OUT).as_posix() for p in build.OUT.rglob("*")
             if p.is_file() and p.relative_to(build.OUT).as_posix() not in wanted]
    check(not stale and not extra,
          f"docs/ai-skill is current ({stale or 'all current'}; left over: {extra or 'none'}; "
          "run python -m raia.skill.build)")


def test_bundle() -> None:
    print("== the download ==")
    ingest_corpus(verbose=False)
    svc = ProjectService(runner=StageRunner())
    ana = svc.sign_in("ana@example.org", "Ana Souza")
    PROJ = build.PROJECT_DIR

    early = svc.create_project(ana, "Early project")
    approve(svc, ana, early.id, "risk_classifier", EXAMPLES["risk_classifier"])
    early_zip = skill_bundle(svc.repository(ana, early.id), early.name, "chatgpt")
    z = zipfile.ZipFile(io.BytesIO(early_zip))
    ctx = z.read(f"{PROJ}/PROJECT_CONTEXT.md").decode()
    check("No requirements approved yet" in ctx and "Not run yet" in ctx,
          "with only the classification approved, the context says what is missing")
    check("high-risk" in ctx and "What RAIA was told" in ctx and "Employment" in ctx,
          "…and carries the tiers and the answers the classification rests on")
    check("bill, not in force" in ctx, "…naming the Brazilian bill as a bill")

    p = svc.create_project(ana, "Hiring assistant")
    approve(svc, ana, p.id, "risk_classifier", EXAMPLES["risk_classifier"])
    approve(svc, ana, p.id, "requirements_reviewer", EXAMPLES["requirements_reviewer"])
    approve(svc, ana, p.id, "story_generate", EXAMPLES["story_generate"])
    svc.create_sprint(ana, p.id, name="Sprint 1", capacity=3)
    picked = [x["id"] for x in svc.suggest_sprint(ana, p.id)["suggested"]]
    svc.schedule(ana, p.id, picked)
    svc.start_sprint(ana, p.id)
    repo = svc.repository(ana, p.id)
    project_files = {f"{PROJ}/{f}" for f in ("README.md", "PROJECT_CONTEXT.md", "MANIFEST.txt", "BRIEF.md", "backlog.csv",
                                             "backlog.json", "sprints.json", "roadmap.csv", "action_plan.csv",
                                             "action_plan.json")}
    project_files.add(f"{PROJ}/artifacts/{ARTIFACT_FILES['requirements_review']}")
    fixed = set(build.fixed_files())

    print("== Cursor: the skill where Cursor looks for it, the project beside it ==")
    z = zipfile.ZipFile(io.BytesIO(skill_bundle(repo, p.name, "cursor")))
    names = set(z.namelist())
    expected = {"README_FIRST.md", "AGENTS.md", *(f".cursor/skills/{SKILL}/{n}" for n in fixed), *project_files}
    check(expected <= names, f"the skill, AGENTS.md and the outputs are in the zip ({sorted(expected - names) or 'all'})")
    check(all(n.startswith((f".cursor/skills/{SKILL}/", f"{PROJ}/")) or n in ("README_FIRST.md", "AGENTS.md")
              for n in names), "nothing else is in it")
    check(all(z.read(f".cursor/skills/{SKILL}/{n}").decode() == t for n, t in build.fixed_files().items()),
          "the skill folder is the fixed part, unchanged")
    research = [n for n in names if n.rsplit("/", 1)[-1] in
                ("evaluation_events.jsonl", "git_history.txt", "history_chain.json")]
    check(not research, "no research data, history or hash chain")
    ctx = z.read(f"{PROJ}/PROJECT_CONTEXT.md").decode()
    bl, _ = B.load(repo)
    evrs = [e for s in bl["stories"] for e in s.get("evr_ids") or []]
    check(all(e in ctx for e in evrs) and all(s["id"] in ctx for s in bl["stories"]),
          "the context lists the requirements and every backlog story")
    check(all(i["id"] in ctx for i in repo.open_issues() if i.get("status", "open") == "open"),
          "…and every open decision")
    check(not EMAIL.search(ctx), "the generated context names no one by email")
    check("SPR-1" in ctx, "…and shows the open sprint")
    readme = z.read(f"{PROJ}/README.md").decode()
    check(p.name in readme and "{{" not in readme, "the project part's README names the project")
    check(p.name not in z.read("README_FIRST.md").decode(), "…and the install note does not")

    print("== ChatGPT and Claude: a skill to upload, the same bytes for everyone ==")
    for fmt in ("chatgpt", "claude"):
        z = zipfile.ZipFile(io.BytesIO(skill_bundle(repo, p.name, fmt)))
        names = set(z.namelist())
        check({"README_FIRST.md", f"{SKILL}.zip", *project_files} <= names
              and all(n.startswith(f"{PROJ}/") or n in ("README_FIRST.md", f"{SKILL}.zip") for n in names),
              f"{fmt}: the install note, the skill zip and the project part, nothing else")
        inner = z.read(f"{SKILL}.zip")
        check(inner == build.fixed_zip() and inner == zipfile.ZipFile(io.BytesIO(early_zip)).read(f"{SKILL}.zip")
              if fmt == "chatgpt" else inner == build.fixed_zip(),
              f"{fmt}: the skill zip is identical for two projects")
        inside = zipfile.ZipFile(io.BytesIO(inner)).namelist()
        check(sorted(inside) == sorted(f"{SKILL}/{n}" for n in fixed), f"{fmt}: it holds the skill folder only")

    print("== One Markdown file: the fixed part, then the project part ==")
    one = skill_bundle(repo, p.name, "generic").decode()
    other = skill_bundle(svc.repository(ana, early.id), early.name, "generic").decode()
    head, _, tail = one.partition(build.GENERIC_PROJECT_MARKER)
    check(tail and head == other.partition(build.GENERIC_PROJECT_MARKER)[0] == build.generic_fixed(),
          "everything before the marker is identical for two projects")
    check(p.name not in head and p.name in tail and "What RAIA was told" in tail and all(e in tail for e in evrs),
          "the project's facts come after it, and only after it")
    check(all(f"<!-- references/{n} -->" in head for n in build._REFERENCE_ORDER) and "## P1 Triage the backlog" in head,
          "every reference is in the file")
    check("{{" not in one and not head.startswith("---"), "it is plain Markdown, with no frontmatter to trip a reader")

    full = set(zipfile.ZipFile(io.BytesIO(session_bundle(repo, p.name))).namelist())
    check("evaluation_events.jsonl" in full and "artifacts/03_requirements_review.md" in full
          and "BRIEF.md" in full, "the full project download keeps the research data, and carries the brief")
    check(skill_bundle_name(p.name, "cursor").startswith("raia-hiring-assistant-ai-skill-cursor-")
          and skill_bundle_name(p.name, "generic").endswith(".md"), "the file is named for the project and the format")
    try:
        skill_bundle(repo, p.name, "word")
        check(False, "an unknown format is refused")
    except ValueError:
        check(True, "an unknown format is refused")


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
