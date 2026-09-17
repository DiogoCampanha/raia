"""Public page: Privacy Policy and User Agreement (no sign-in required)."""

import streamlit as st

from raia.ui import legal

body = legal.text()
title, _, rest = body.partition("\n")
st.title(title.lstrip("# ").strip(), anchor=False)
st.markdown(rest)
