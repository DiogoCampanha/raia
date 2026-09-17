"""
raia.ui
=======

The Streamlit presentation layer, split out of ``app.py``.

* :mod:`raia.ui.routes`     — the page map: one registry of routes, used for every link.
* :mod:`raia.ui.state`      — who is signed in, which project is open, cached services.
* :mod:`raia.ui.theme`      — design tokens (CSS), icons and status vocabulary.
* :mod:`raia.ui.components` — page header, stat tiles, badges, stage tracker, empty states.
* :mod:`raia.ui.gate`       — the structured intake form and the human approval gate.
* :mod:`raia.ui.agent_docs` — user-facing documentation for each agent.
* :mod:`raia.ui.assessment` — the tester assessment instrument.
* :mod:`raia.ui.legal`      — the public privacy policy and user agreement.

Access control does not live here. Every project operation goes through
:class:`raia.projects.ProjectService`, which refuses what a person's role does
not allow; this package only decides what to show.
"""
