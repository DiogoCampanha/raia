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

The profile section asks only broad, optional categories: the evaluation plan
reports aggregated profiles only, and no answer here identifies a person.
"""

from __future__ import annotations

INSTRUMENT_ID = "raia-panel-v1"

SCALE = [1, 2, 3, 4, 5]
SCALE_LABELS = {
    1: "Strongly disagree",
    2: "Disagree",
    3: "Neither agree nor disagree",
    4: "Agree",
    5: "Strongly agree",
}

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

STAGE_ITEM = "The output of this stage would be useful on a real project."

OPEN_QUESTIONS = [
    ("most_valuable", "What was most valuable about RAIA, and why?"),
    ("missing", "What is missing, or what should change first?"),
    ("context_limits", "In which organizational contexts would RAIA not work as it is? Why?"),
]

NO_ANSWER = "Prefer not to say"

PROFILE = [
    ("context", "Where do you mainly work?",
     ["Academia", "Industry", "Both academia and industry", "Public sector", "Other"]),
    ("role_family", "Which best describes your role?",
     ["Research or teaching", "Product or project management", "Software engineering",
      "Data science or machine learning", "Legal, compliance or risk", "Ethics or policy",
      "Leadership or management", "Other"]),
    ("experience", "Years of professional experience",
     ["Less than 3", "3 to 5", "6 to 10", "11 to 20", "More than 20"]),
    ("rai_expertise", "Experience with Responsible AI or AI governance",
     ["None", "Basic", "Intermediate", "Advanced", "Expert"]),
    ("region", "Region where you mainly work",
     ["Latin America", "North America", "Europe", "Africa", "Asia-Pacific", "Middle East"]),
    ("sector", "Sector closest to your work",
     ["Financial services", "Health", "Technology", "Government", "Education or research",
      "Retail or consumer", "Other"]),
]

CONSENT_TEXT = (
    "I agree to take part in the RAIA evaluation. My answers are used for research, analysed "
    "under a participant code rather than my name or email, and reported only in aggregate."
)
