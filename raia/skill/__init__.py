"""
raia.skill
==========

The RAIA AI Skill: instructions that turn an AI assistant a person is allowed
to use into a simplified RAIA, for their real backlog, tickets and product
documents.

Teams that may only use pre-approved assistants at work can give RAIA no more
than a generic description of their product; their real work lives elsewhere.
The skill tells their own assistant how to read RAIA's records, how to apply
them without weakening them and how to keep the work going between RAIA runs,
with RAIA's own rules (computed priorities are never lowered, verdicts only
move down, a person decides) and RAIA's own sources only. It also works with no
RAIA project at all: it then screens the product itself, with the rule engine's
tables, and says that the result is self-assessed.

Two parts, kept apart on purpose:

* **The fixed part** (:mod:`raia.skill.build`): ``SKILL.md`` and its
  references. The prose lives in ``text/``; every vocabulary, scale, table and
  rule in it is generated from the code, so the skill cannot contradict the
  software. It takes no project, no person and no date, is byte-identical for
  every download of a version, and carries that version and a fingerprint. A
  static copy is kept in ``docs/ai-skill/`` and checked by the tests.
* **The project part** (:mod:`raia.skill.context`, :func:`raia.export.skill_bundle`):
  ``PROJECT_CONTEXT.md`` (one project's facts as of the download) and the
  project's approved outputs. It is the only thing that differs between two
  downloads, and a person replaces it after new approvals without touching the
  skill.

The text is written for any assistant: it assumes no file access and no
connection to a tracker (pasted text and attached exports are the normal
input), and what is specific to an assistant lives only in that format's
install note. Four formats are offered (:data:`raia.skill.build.FORMATS`):
Cursor, ChatGPT, Claude, and one Markdown file.
"""
