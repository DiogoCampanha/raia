"""
raia.contract
=============

The RAIA output contract: one standard record for every agent.

* :mod:`~raia.contract.vocab`    — closed vocabularies drawn from the project's normative sources
* :mod:`~raia.contract.rubric`   — risk level and priority, computed by code
* :mod:`~raia.contract.schema`   — the record schema: shared core + one extension per agent
* :mod:`~raia.contract.prompt`   — the contract as shown to the model
* :mod:`~raia.contract.assemble` — parse, repair, finalise, fall back
* :mod:`~raia.contract.render`   — the one Markdown layout every artifact follows
* :mod:`~raia.contract.checks`   — deterministic checks on the record
* :mod:`~raia.contract.actions`  — the project-wide action plan and its exports
"""

from .vocab import SCHEMA_VERSION  # noqa: F401 - re-exported
