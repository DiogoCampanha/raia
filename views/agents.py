"""Agents: how RAIA works, and each agent's documentation."""

import json

import streamlit as st

from raia import config
from raia.agents import AGENTS
from raia.contract import SCHEMA_VERSION
from raia.contract.assemble import RECORD_TYPES
from raia.repository import ARTIFACT_FILES
from raia.ui.agent_docs import DOCS, LAYERS, TURN
from raia.ui.components import agent_header, esc, page_header
from raia.ui.theme import look

page_header(
    "How RAIA works",
    "Five specialized agents apply Responsible AI across the software life cycle. Each one "
    "drafts; a person decides. This page explains the architecture and documents every agent.",
    eyebrow="Architecture",
)

p1, p2, p3 = st.columns(3, gap="medium")
for col, (icon, head, body) in zip((p1, p2, p3), [
    (":material/how_to_reg:", "People are the checkpoint",
     "No agent output is saved until a person reviews and approves it, and no agent ever "
     "triggers another one."),
    (":material/calculate:", "Code decides what is decidable",
     "Prohibition lists, obligation tables, coverage matrices and fairness metrics are computed "
     "by rules before any model is called. The model explains; it does not produce the facts."),
    (":material/verified:", "Everything is cited and versioned",
     "Citations are verified against the excerpts actually retrieved, and every approval becomes "
     "a recorded version attributed to the person who approved it."),
]):
    with col, st.container(border=True, height="stretch"):
        st.markdown(f"{icon} **{head}**")
        st.caption(body)

# ---- Interactive architecture diagram -----------------------------------------------

st.subheader("Architecture", anchor=False)
st.caption("Select an agent to see what it reads and produces. Arrows are the order of work; "
           "H marks a mandatory human approval gate.")

producers = {a.spec.output_key: a.spec.name for a in AGENTS.values()}
producers["product_brief"] = AGENTS["risk_classifier"].spec.name
nodes = [{
    "key": k, "name": a.spec.name, "layer": a.spec.layer, "phase": a.spec.sdlc_phase,
    "what": a.spec.description,
    "reads": [f"{producers.get(u, u)} ({ARTIFACT_FILES.get(u, u)})" for u in a.spec.upstream_keys],
    "writes": ARTIFACT_FILES.get(a.spec.output_key, a.spec.output_key),
    "grounding": [config.SOURCE_NAMES.get(g, g) for g in a.spec.grounding_sources],
} for k, a in AGENTS.items()]

node_html = []
for i, n in enumerate(nodes):
    if i:
        node_html.append('<div class="arch-gate" aria-hidden="true"><span>H</span></div>')
    node_html.append(
        f'<button type="button" class="arch-node look-{esc(n["key"])}" data-key="{esc(n["key"])}" '
        f'aria-pressed="false"><span class="arch-layer"><span class="raia-icon">{esc(look(n["key"]).icon)}</span>'
        f'{esc(n["layer"])}</span>'
        f'<span class="arch-name">{esc(n["name"])}</span>'
        f'<span class="arch-phase">{esc(n["phase"])}</span></button>'
    )

DIAGRAM = """
<style>
.arch { container-type: inline-size; font-family: inherit; color: inherit; }
.arch-flow { display: flex; flex-direction: column; gap: .35rem; }
.arch-node { all: unset; box-sizing: border-box; cursor: pointer; display: flex; flex-direction: column; gap: .2rem;
  padding: .75rem .85rem; border-radius: .625rem; border: 1px solid rgba(100,116,139,.28);
  border-top: 3px solid var(--c); background: rgba(100,116,139,.05); transition: background .15s, box-shadow .15s; }
.arch-node:hover { background: rgba(100,116,139,.11); }
.arch-node:focus-visible { outline: 2px solid var(--c); outline-offset: 2px; }
.arch-node[aria-pressed="true"] { background: color-mix(in srgb, var(--c) 9%, transparent); box-shadow: 0 0 0 1px var(--c) inset; }
.arch-node { --c: var(--agent, #2563eb); }
.arch-layer { display: flex; align-items: center; gap: .35rem; font-size: .6875rem; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--c); }
.arch-layer .raia-icon { font-size: 1.05rem; letter-spacing: 0; }
.arch-name { font-weight: 600; font-size: .95rem; line-height: 1.25; }
.arch-phase { font-size: .75rem; opacity: .65; line-height: 1.3; }
.arch-gate { display: flex; align-items: center; justify-content: center; }
.arch-gate span { width: 1.5rem; height: 1.5rem; border-radius: 50%; border: 2px solid #7c3aed; color: #7c3aed;
  display: flex; align-items: center; justify-content: center; font-size: .72rem; font-weight: 700; }
.arch-repo { margin-top: .75rem; padding: .7rem .9rem; border-radius: .625rem; border: 1px dashed rgba(100,116,139,.45);
  font-size: .85rem; text-align: center; }
.arch-repo strong { font-weight: 600; }
.arch-detail { margin-top: .75rem; padding: .9rem 1rem; border-radius: .625rem; border: 1px solid rgba(100,116,139,.28);
  font-size: .875rem; line-height: 1.5; min-height: 3rem; }
.arch-detail h4 { margin: 0 0 .35rem; font-size: 1rem; }
.arch-detail dl { display: grid; grid-template-columns: max-content 1fr; gap: .25rem .9rem; margin: .5rem 0 0; }
.arch-detail dt { opacity: .65; } .arch-detail dd { margin: 0; }
.arch-hint { opacity: .65; }
@container (min-width: 760px) {
  .arch-flow { flex-direction: row; align-items: stretch; gap: 0; }
  .arch-node { flex: 1 1 0; min-width: 0; }
  .arch-gate { flex: 0 0 2.25rem; position: relative; }
  .arch-gate::before { content: ""; position: absolute; left: 0; right: 0; top: 50%; height: 1px; background: rgba(100,116,139,.45); }
  .arch-gate span { position: relative; background: var(--raia-bg, transparent); backdrop-filter: blur(2px); }
}
</style>
<div class="arch" id="raia-arch">
  <div class="arch-flow" role="group" aria-label="RAIA agents in pipeline order">__NODES__</div>
  <div class="arch-repo"><strong>Shared artifact repository</strong> · agents communicate only through
    approved, versioned, tamper-evident documents</div>
  <div class="arch-detail" aria-live="polite"><span class="arch-hint">Select an agent above.</span></div>
</div>
<script>
(function () {
  const data = __DATA__;
  const root = document.getElementById("raia-arch");
  if (!root) return;
  const detail = root.querySelector(".arch-detail");
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}[c]));
  const list = (xs) => xs.length ? xs.map(esc).join("<br>") : "Nothing: this is the first stage";
  root.querySelectorAll(".arch-node").forEach((btn) => {
    btn.addEventListener("click", () => {
      const n = data.find((d) => d.key === btn.dataset.key);
      root.querySelectorAll(".arch-node").forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
      detail.innerHTML = "<h4>" + esc(n.name) + "</h4><div>" + esc(n.what) + "</div><dl>" +
        "<dt>Layer</dt><dd>" + esc(n.layer) + " · " + esc(n.phase) + "</dd>" +
        "<dt>Reads</dt><dd>" + list(n.reads) + "</dd>" +
        "<dt>Produces</dt><dd>" + esc(n.writes) + "</dd>" +
        "<dt>Grounded in</dt><dd>" + list(n.grounding) + "</dd></dl>";
    });
  });
})();
</script>
"""
st.html(DIAGRAM.replace("__NODES__", "".join(node_html)).replace("__DATA__", json.dumps(nodes)),
        unsafe_allow_javascript=True)

l1, l2, l3 = st.columns(3, gap="medium")
for col, (layer, blurb) in zip((l1, l2, l3), LAYERS.items()):
    with col, st.container(border=True, height="stretch"):
        st.markdown(f"**{layer} layer**")
        st.caption(blurb)
        st.caption(" · ".join(a.spec.name for a in AGENTS.values() if a.spec.layer == layer))

st.subheader("What happens inside one stage", anchor=False)
cols = st.columns(len(TURN), gap="small")
for i, (col, (kind, name, body)) in enumerate(zip(cols, TURN), start=1):
    with col, st.container(border=True, height="stretch"):
        st.caption(f"{i} · {kind}")
        st.markdown(f"**{name}**")
        st.caption(body)

# ---- Agent documentation ----------------------------------------------------------------

st.subheader("Agent documentation", anchor=False)
tabs = st.tabs([f"{look(k).material} {a.spec.name}" for k, a in AGENTS.items()])
for tab, (key, agent) in zip(tabs, AGENTS.items()):
    spec = agent.spec
    doc = DOCS.get(key, {})
    with tab:
        agent_header(key, spec.name, spec.description, eyebrow=f"{spec.layer} layer · {spec.sdlc_phase}",
                     compact=True)
        if doc.get("when"):
            st.markdown(f"**When to use it.** {doc['when']}")
        c1, c2 = st.columns(2, gap="large")
        with c1:
            st.markdown("**What the code settles before the model runs**")
            for line in doc.get("decides", []):
                st.markdown(f"- {line}")
        with c2:
            st.markdown("**What stays with you**")
            for line in doc.get("you", []):
                st.markdown(f"- {line}")
        with st.container(border=True):
            g1, g2 = st.columns(2, gap="large")
            with g1:
                st.caption("Questions it asks")
                for group in spec.field_groups():
                    st.markdown(f"- {group.split('·', 1)[-1].strip()}")
                st.caption("Reads")
                st.markdown("\n".join(f"- {producers.get(u, u)} — `{ARTIFACT_FILES.get(u, u)}`"
                                      for u in spec.upstream_keys) or "- Nothing: first stage")
            with g2:
                st.caption("Produces")
                st.markdown(f"- `{ARTIFACT_FILES.get(spec.output_key, spec.output_key)}` — a "
                            f"{RECORD_TYPES.get(spec.key, 'RAIA record').lower()} (`{SCHEMA_VERSION}`), with "
                            "sections: " + ", ".join(spec.required_sections))
                st.caption("Grounded in")
                st.markdown("\n".join(f"- {config.SOURCE_NAMES.get(g, g)}"
                                      for g in spec.grounding_sources))
                st.caption("Requires approved")
                st.markdown("\n".join(f"- {producers.get(u, u)}" for u in spec.required_upstream)
                            or "- Nothing")
