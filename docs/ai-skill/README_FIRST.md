# RAIA AI Skill — your project

Created (the date of your download) from the RAIA project "your project".

This package turns an AI assistant your organisation already approves into a simplified RAIA for this project. The assistant reads what RAIA produced (risk classification, ethical value requirements, RAI backlog, audits), applies it to your real backlog and keeps the work going between RAIA runs: it classifies backlog items, writes ethical acceptance criteria, suggests what goes into a sprint, checks a sprint against its evidence and prepares Jira-ready items.

## What is inside

```
README_FIRST.md                 This file (for people)
AGENTS.md                       Pointer for coding assistants working in your repository
raia-responsible-ai/
  SKILL.md                      The instructions the assistant follows
  references/                   How to read RAIA outputs, vocabulary, RAI guidelines,
                                playbooks and templates
  project/
    PROJECT_CONTEXT.md          This project's facts, as of the date above
    MANIFEST.txt                What each project file is
    artifacts/                  The approved RAIA records (.md and structured .json)
    action_plan.csv/.json       Every approved action, by priority
    backlog.csv/.json           The backlog with its ethical criteria and requirement links
    sprints.json, roadmap.csv   Sprints and where each requirement stands
```

Research data (evaluation events) and the version history are not included. Use **Download project** in RAIA if you need them.

## How to use it

**A coding assistant in your repository.** Unzip at the root of your product repository. `AGENTS.md` lands at the root; if you already have one, append this one's text to it. Assistants that read skill folders (for example Claude Code, from `.claude/skills/`) can also take the `raia-responsible-ai/` folder there; update the paths in `AGENTS.md` if you move it.

**A chat assistant that supports skills.** Zip the `raia-responsible-ai/` folder on its own and upload it as a skill.

**A chat assistant without skills.** Paste `SKILL.md` into the assistant's custom instructions (it is short enough for most), and attach `PROJECT_CONTEXT.md`, the files in `references/` and the CSV files as knowledge files or to the conversation.

Then try:

- "Using the RAIA skill, triage this backlog." (attach a Jira export or paste the stories)
- "Refine story US-4 with the RAIA skill."
- "Which requirements have no story yet? Draft RAI stories for the top three."
- "Suggest the next sprint from the RAIA backlog."
- "Self-audit sprint SPR-2 against this evidence: ..."
- "Prepare a Jira CSV for the stories we agreed."

## Good to know

- **Share your backlog only with an assistant your organisation approves.** Nothing in this package is sent anywhere; it was produced on request and downloaded by you.
- **Approver names stay in the records.** Each approved artifact records who approved it and when: that is its provenance.
- **It is a snapshot.** After you approve new work in RAIA, download the skill again so the assistant reads current records.
- **It is lighter than RAIA.** Between RAIA runs the assistant follows RAIA's rules but has no rule engine, no retrieval over the normative texts and no approval gate. Material changes (a new purpose, market, data category or level of automation) go back to RAIA; the skill tells the assistant to say so.
- RAIA is a research prototype developed at Universidade Presbiteriana Mackenzie. Its outputs support, and do not replace, legal and compliance advice.
