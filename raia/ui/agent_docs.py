"""
raia.ui.agent_docs
==================

User-facing documentation for each agent, shown on the Agents page.

Everything that the code already declares — layer, SDLC phase, input groups,
artifacts read and produced, normative sources, required report sections — is
read from the agent's :class:`~raia.agents.base.AgentSpec` at render time, so
this page cannot drift from the implementation. Only the prose that no spec
holds lives here: when to use the agent, what its decision procedure settles in
code, and what is left for a person to decide.
"""

from __future__ import annotations

from typing import Dict

DOCS: Dict[str, Dict[str, object]] = {
    "risk_classifier": {
        "when": "At conception, before requirements are written, and again whenever the "
                "product's purpose, markets or data change.",
        "decides": [
            "Matches the declared purpose and practices against the prohibited-practice and "
            "high-risk area lists of the EU AI Act and the Brazilian PL 2338/2023.",
            "Reads how the AI works: flags a rules-only product that may fall outside the legal "
            "definition of an AI system, and applies transparency duties that the techniques "
            "imply even when they were not selected.",
            "Derives the risk tier for each jurisdiction and the obligations that follow "
            "from that tier and from your role (provider or deployer).",
            "Identifies the legal excerpts that must be in front of the reviewer.",
        ],
        "you": [
            "Whether a narrow-task exemption actually holds for your system.",
            "Whether a rules-only product is an AI system in the legal sense.",
            "Whether the classification fits how the product is really used.",
        ],
    },
    "requirements_reviewer": {
        "when": "Once the risk classification is approved and a first set of requirements exists.",
        "decides": [
            "Builds a coverage matrix: every obligation from the approved classification and "
            "each of the seven Responsible AI principles, tested against your requirements and "
            "existing controls.",
            "Lists the uncovered cells as gaps, so a gap is computed rather than asserted.",
            "On request, pre-fills the stakeholder and principle questions you left empty from the "
            "approved classification, with a reason per value, and offers a few candidate requirements "
            "for the gaps your answers leave. Candidates that cite no retrieved excerpt, address a gap "
            "that was not computed or have no testable fit criterion are dropped before you see them.",
            "Keeps adopted recommendations apart from the requirements the team wrote: coverage that "
            "rests on one is marked as such in the record.",
        ],
        "you": [
            "Which recommended requirements to adopt, edit or reject, one at a time, and whether "
            "pre-filled answers reflect the project. The controls in place are never pre-filled.",
            "Which proposed ethical value requirements the team adopts.",
            "How stakeholder values are weighed where they conflict.",
        ],
    },
    "story_refiner": {
        "when": "During sprint planning, for the stories about to enter a sprint.",
        "decides": [
            "Selects the ECCOLA themes relevant to each story from the approved risk tier, "
            "requirements and what that story touches, and records why each one applies.",
            "Traces every new acceptance criterion back to an approved requirement.",
            "Turns every existing criterion the agent flags as conflicting into a decision.",
        ],
        "you": [
            "Whether each acceptance criterion is testable in your context.",
            "Whether a conflicting existing criterion is rewritten or kept, and why.",
            "Which stories carry no ethical impact and can move on unchanged.",
        ],
    },
    "auditor": {
        "when": "At the end of a sprint or before a release decision.",
        "decides": [
            "Reads the register of approved requirements and acceptance criteria and matches "
            "each one to the evidence the sprint produced.",
            "Refuses to mark anything verified without evidence: an item with no evidence is "
            "not verified, whatever the narrative says.",
        ],
        "you": [
            "Whether the evidence is sufficient for an accountability record.",
            "What becomes an ethical checkpoint for the next iteration.",
        ],
    },
    "drift_monitor": {
        "when": "After deployment, on each monitoring period's telemetry export.",
        "decides": [
            "Computes every fairness and representativeness metric in code, with group sizes "
            "and trend, against thresholds read from the approved upstream artifacts.",
            "Checks that every number in the narrative is one the code computed.",
        ],
        "you": [
            "Whether a drift alert warrants action, and which action.",
            "Whether operational context explains a change in the numbers.",
        ],
    },
}

TURN = [
    ("Deterministic", "Structured intake", "Typed questions whose answers a rule reads."),
    ("Deterministic", "Decision procedure", "Computes the verdict, the tables and the required excerpts."),
    ("Generative", "Model pass", "Justifies, handles judgement calls, and fills the standard record."),
    ("Deterministic", "Contract and checks", "Priorities, ids and layout computed; citations, coverage, reconciliation checked."),
    ("Human", "Approval gate", "A person decides, with the evidence in front of them."),
]

LAYERS = {
    "Product": "Risk classification and ethical value requirements, at conception time.",
    "Dev": "Ethical acceptance criteria and accountability audits, inside sprints.",
    "Ops": "Fairness-drift monitoring, after deployment.",
}
