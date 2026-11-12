# RAIA AI Skill for Cursor

Skill version {{skill_version}}.

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

{{use_section}}
