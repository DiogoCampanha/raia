# RAIA AI Skill for Cursor

Skill version 2.0.0.

## What is inside

```
README_FIRST.md                          This file
.cursor/skills/raia-responsible-ai/      The fixed part: the same for every project, never edited
  SKILL.md                               The instructions the assistant follows
  references/                            Reading RAIA outputs, vocabulary, guidelines, screening,
                                         playbooks, templates
raia-project/                            The project part: this project's outputs (see its README.md)
AGENTS.md                                Optional pointer for a code repository
```

## Install

1. Unzip at the root of the folder you open in Cursor. The skill lands in `.cursor/skills/`, where Cursor looks for skills, and `raia-project/` lands beside it.
2. To have the skill in every workspace, move `raia-responsible-ai/` to `~/.cursor/skills/` instead. Keep `raia-project/` in the workspace of the product it belongs to.
3. In the agent chat, ask in plain words, or type `/` and pick the skill.

`AGENTS.md` is for a code repository whose assistants should follow the skill on every backlog task. If the folder already has one, append this one's text to it. Delete it if you do not want it.

## Use

Then try:

- "Using the RAIA skill, triage this backlog." (attach an export or paste the stories)
- "Refine this story with the RAIA skill."
- "Review this product document for Responsible AI gaps."
- "Which requirements have no story yet? Draft RAI stories for the top three."
- "Suggest the next sprint from the RAIA backlog."
- "Write a one-page Responsible AI brief for my manager."

The skill also works with no project part: it screens the product itself and says that the result is self-assessed.

## The two parts

- **The fixed part never changes** within a version. It is identical for every project and every download. Do not edit it; a new version comes from RAIA.
- **The project part changes** whenever work is approved in RAIA. Download again and replace `raia-project/` (or the attached files). The skill itself stays where it is.

## Good to know

- **Share your backlog only with an assistant your organisation approves.** Nothing in this package is sent anywhere; it was produced on request and downloaded by you.
- **Approver names stay in the records** inside `raia-project/artifacts/`: that is their provenance.
- **It is lighter than RAIA.** The assistant follows RAIA's rules but has no rule engine, no retrieval over the normative texts and no approval gate. Material changes (a new purpose, market, data category or level of automation) go back to RAIA; the skill tells the assistant to say so.
- **PL 2338/2023 is a bill, not yet law.** The skill names it as such.
- RAIA is a research prototype developed at Universidade Presbiteriana Mackenzie. Its outputs support, and do not replace, legal and compliance advice.
