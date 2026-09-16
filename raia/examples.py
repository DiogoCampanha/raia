"""
raia.examples
=============

The project's canonical walkthrough scenario: a resume-screening platform.

It is kept in one place, and filled into the *structured* fields as well as the
prose ones, because the structured answers are what the decision procedures
read. An example that only filled in the text boxes would demonstrate the old
behaviour — a model inferring everything from prose — which is exactly what the
walkthrough is meant to show has changed.

The scenario is deliberately a hard one: an employment system is high-risk
under both regimes, it is fully automated with no oversight designed, and it
processes proxies for protected attributes. Every stage therefore has something
real to say, and the fairness telemetry later in the walkthrough breaches its
threshold in the final window.
"""

from typing import Any, Dict

EXAMPLES: Dict[str, Dict[str, Any]] = {
    "risk_classifier": {
        "product_brief": (
            "TalentFlow is a resume-screening platform. A machine-learning model ranks and "
            "filters job applications, producing a shortlist for recruiters. The AI component "
            "scores each resume against the job description and against historical hiring data."
        ),
        "intended_use": (
            "Used by corporate HR departments in Brazil and the EU to screen high-volume "
            "vacancies. Recruiters see the ranked shortlist and decide whom to interview. "
            "Candidates below the cut-off are not shown to a recruiter at all."
        ),
        "target_users": (
            "Users: recruiters and HR managers. Affected people: all job applicants, including "
            "members of protected groups; candidates filtered out never interact with the "
            "system directly and are not told a model was involved."
        ),
        "role": "provider",
        "markets": ["eu", "br"],
        "public_sector": "no",
        "gpai_provider": "no",
        "purpose_areas": ["employment"],
        "annex_i_product": "no",
        "prohibited_practices": ["none"],
        "transparency_triggers": ["none"],
        "decision_autonomy": "fully_automated",
        "significant_effects": "yes",
        "human_oversight": "none_designed",
        "data_categories": ["protected_attributes", "proxies"],
        "deployment_stage": "development",
        "art63_claim": "no",
    },
    "requirements_reviewer": {
        "requirements": (
            "R1. The system shall rank applications by predicted job fit.\n"
            "R2. The system shall process at least 10,000 resumes per hour.\n"
            "R3. Recruiters shall be able to export the shortlist to CSV.\n"
            "R4. The system shall integrate with the corporate SSO.\n"
            "R5. Model retraining shall occur monthly on new hiring data."
        ),
        "requirement_format": "numbered",
        "existing_controls": ["logging"],
        "constraints": (
            "The first release is committed to a customer for the end of the quarter. "
            "The data team has no capacity for a new labelling effort this cycle."
        ),
        "values_at_stake": ["fairness", "transparency"],
        "stakeholders": ["users", "subjects"],
    },
    "story_refiner": {
        "user_stories": (
            "S1. As a recruiter, I want to see the top-20 ranked candidates for a vacancy so "
            "that I can build an interview shortlist quickly.\n"
            "S2. As a recruiter, I want to filter candidates by minimum qualification criteria "
            "so that unqualified applications are excluded automatically.\n"
            "S3. As an HR manager, I want a dashboard of screening throughput so that I can "
            "report hiring KPIs."
        ),
        "sprint_goal": "Ship ranking v2 and the qualification filter",
        "touched_capabilities": ["scoring", "automation", "analytics"],
        "definition_of_done": (
            "Merged behind a feature flag, unit and integration tests green, evaluation report "
            "attached to the ticket, documentation updated."
        ),
    },
    "auditor": {
        "sprint_id": "Sprint 7",
        "sprint_outcomes": (
            "Delivered the ranking API v2 (S1) with a disaggregated evaluation report — "
            "demographic parity difference measured at 0.08 across gender and 0.12 across race "
            "groups on validation data. The qualification filter (S2) shipped without "
            "disaggregated testing. Audit-log storage for ranking decisions was enabled."
        ),
        "evidence_types": ["test_results", "disaggregated", "audit_log"],
        "planned_epics": (
            "Next: explanation UI for recruiters (why a candidate was ranked); "
            "candidate-facing contestation form; retraining pipeline automation."
        ),
    },
    "drift_monitor": {
        "telemetry_csv": (
            "window,group,selection_rate,accuracy,n\n"
            "2026-04,gender=F,0.31,0.86,4120\n"
            "2026-04,gender=M,0.36,0.87,4380\n"
            "2026-05,gender=F,0.28,0.85,3980\n"
            "2026-05,gender=M,0.38,0.87,6110\n"
            "2026-06,gender=F,0.24,0.83,3610\n"
            "2026-06,gender=M,0.39,0.88,7240\n"
            "2026-06,gender=X,0.21,0.79,18\n"
        ),
        "incident": "none",
        "context_notes": (
            "A new job board was integrated as an application source in May, roughly doubling "
            "application volume. No model retraining happened in this period."
        ),
    },
}
