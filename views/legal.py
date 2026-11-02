"""Public page: Privacy Policy and User Agreement (no sign-in required)."""

import streamlit as st

from raia.ui import legal
from raia.ui.components import esc, page_header

title, lead, parts = legal.sections(legal.text())
page_header(title, "How RAIA handles your information, and the terms under which you use it.")

toc, doc = st.columns([1, 3.2], gap="large")
with toc, st.container(key="legal-toc"):
    st.html('<nav class="raia-toc" aria-label="On this page"><p class="h">On this page</p><ol>'
            + "".join(f'<li><a href="#s{i}">{esc(h)}</a></li>'
                      for i, (h, _) in enumerate(parts, 1))
            + "</ol></nav>")
with doc, st.container(border=True, key="card-legal"):
    st.markdown(lead)
    for i, (head, md) in enumerate(parts, 1):
        st.subheader(head, anchor=f"s{i}")
        st.markdown(md)
