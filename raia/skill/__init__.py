"""
raia.skill
==========

The RAIA AI Skill: a portable folder that turns an AI assistant a team is
already allowed to use into a simplified RAIA for one project.

Teams that may only use pre-approved assistants at work can run RAIA on a
generic description of their product, then take the results to their own
assistant, where the real backlog and Jira live. The skill tells that
assistant how to read RAIA's records, how to apply them to the backlog
without weakening them, and how to keep the work going between RAIA runs —
with RAIA's own rules (computed priorities are never lowered, verdicts only
move down, a person decides) and RAIA's own sources only.

Two parts:

* :mod:`raia.skill.build` — the instructions and references. The prose lives in
  ``text/``; every vocabulary, scale, table and rule in it is generated from the
  code, so the skill cannot contradict the software. A static copy is kept in
  ``docs/ai-skill/`` and checked by the tests.
* :mod:`raia.skill.context` — ``PROJECT_CONTEXT.md``, one project's facts as of
  the download: what RAIA was told, the tiers, the requirements and where they
  stand, the open decisions, the backlog and the latest audit.

:func:`raia.export.skill_bundle` puts both in one zip with the project's
approved outputs (and without the research data).
"""
