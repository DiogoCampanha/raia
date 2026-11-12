"""
raia.ui.assessment
==================

The tester assessment instrument.

The five Likert dimensions and their definitions are the evaluation plan's
own: utility, completeness, usability, methodological rigor and
generalizability, each rated on a five-point agreement scale, followed by open
questions. The plan's success criterion (median of at least 4 on utility and
usability, and no dimension with a median below 3) is computed over exactly
these five items, so their wording and order are fixed and versioned by
:data:`INSTRUMENT_ID`. Change the wording and the id must change with it, or
responses from two different instruments would be pooled.

``raia-panel-v3`` leaves the five dimensions as they were and changes what is
around them:

* The assessment is about the software only. The AI Skill item of
  ``raia-panel-v2`` is gone: the skill is a download people use freely, and it
  is not rated.
* Every stage still needs an answer, and "Did not use this stage"
  (:data:`NOT_USED`) is one. It is kept apart from the scores: a stage nobody
  opened must not be rated from a guess, and it is counted, never averaged.
* An assessment is not linked to a project. What it is stored with is what the
  person used (:meth:`raia.projects.ProjectService.my_exposure`): for each
  stage, whether they ran or approved it, and whether that was on a demo or on
  a project of their own. No project, no version, no content.
* The profile asks three questions. With a panel drawn from one organisation,
  region, sector and context are the same for everyone and only help tell
  people apart.
* Each dimension carries a hint saying where in RAIA to look before rating it
  (:data:`DIMENSION_HINTS`). The hints are not part of the statements.
"""

from __future__ import annotations

INSTRUMENT_ID = "raia-panel-v3"

SCALE = [1, 2, 3, 4, 5]
SCALE_LABELS = {
    1: "Strongly disagree",
    2: "Disagree",
    3: "Neither agree nor disagree",
    4: "Agree",
    5: "Strongly agree",
}

#: The answer to a stage item from a person who did not use that stage.
NOT_USED = "not_used"
NOT_USED_LABEL = "Did not use this stage"
#: What a stage item offers: the scale, then :data:`NOT_USED`.
STAGE_OPTIONS = SCALE + [NOT_USED]

#: Shown at the top of the form. Neutral on purpose: the software may simply be
#: good, and nothing here should push a rating either way.
FRAMING = ("Rate what you saw. Negative feedback is as useful as positive, and a reason helps "
           "either way.")
#: What "enough use" means, shown above what the person has done so far.
BEFORE_RATING = ("Go through the software once before rating; a demo project is enough. "
                 "A stage you did not open can be answered \"Did not use this stage\".")

#: (key, dimension, statement). Statements are the evaluation plan's
#: definition of each dimension, phrased as a statement to agree with.
DIMENSIONS = [
    ("utility", "Utility",
     "RAIA addresses the problem it states and generates value for organizations."),
    ("completeness", "Completeness",
     "RAIA covers the principles and the phases of the Responsible AI life cycle."),
    ("usability", "Usability",
     "RAIA is clear, accessible and can be integrated into existing workflows."),
    ("rigor", "Methodological rigor",
     "RAIA is grounded in literature and consolidated practices."),
    ("generalizability", "Generalizability",
     "RAIA can be adapted to different organizational contexts."),
]

#: Where to look before rating a dimension. A pointer, never an argument: it
#: names pages and tabs, and says nothing about what a person should find there.
DIMENSION_HINTS = {
    "utility": "Where to look: the draft of any stage and a project's Action plan tab.",
    "completeness": "Where to look: the Agents page (the stages and what each covers) and a "
                    "project's Traceability tab.",
    "usability": "Where to look: a stage's form and review screen, and the Board.",
    "rigor": "Where to look: the Evidence tab of a draft (the excerpts behind each citation) and "
             "the Agents page (the sources each stage is grounded in).",
    "generalizability": "Where to look: the demo projects and the questions each stage asks.",
}

#: One required statement per stage, the same for every stage but naming it.
STAGE_ITEM = "The output of the {stage} would be useful on a real project."


def stage_statement(stage_name: str) -> str:
    """The statement a tester rates for one stage."""
    return STAGE_ITEM.format(stage=stage_name)


def stage_label(value) -> str:
    """How one answer to a stage item reads."""
    return NOT_USED_LABEL if value == NOT_USED else f"{value} · {SCALE_LABELS[value]}"


OPEN_QUESTIONS = [
    ("most_valuable", "What was most valuable about RAIA, and why?"),
    ("missing", "What is missing, or what should change first?"),
    ("context_limits", "In which organizational contexts would RAIA not work as it is? Why?"),
]

NO_ANSWER = "Prefer not to say"

PROFILE = [
    ("role_family", "Which best describes your role?",
     ["Research or teaching", "Product or project management", "Software engineering",
      "Data science or machine learning", "Legal, compliance or risk", "Ethics or policy",
      "Leadership or management", "Other"]),
    ("experience", "Years of professional experience",
     ["Less than 3", "3 to 5", "6 to 10", "11 to 20", "More than 20"]),
    ("ai_product_experience", "Experience with AI Product Development",
     ["None", "Basic", "Intermediate", "Advanced", "Expert"]),
]

CONSENT_TEXT = (
    "I agree to take part in the RAIA evaluation. My answers are used for research and reported "
    "only in aggregate."
)
#: What the consent rests on, shown beside it. It has to be true as written:
#: the tests read the export against these sentences.
CONSENT_DETAIL = (
    "Your answers are stored under a participant code, apart from your projects: an assessment "
    "names no project, and the research export gives assessments a different code from the one "
    "used for project activity. The researcher who runs this study also administers this "
    "deployment and prepares the export, and analyses the answers from that export. Open answers "
    "are read as you wrote them, so leave out anything that would identify you."
)

#: How each level of use reads on the Assessment page.
EXPOSURE_LABELS = {"approved": "run and approved", "run": "run, not approved", "none": "not used yet"}
