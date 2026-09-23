"""Sign out: end this browser session and return to the sign-in page.

Reached from the Account menu. It has no content of its own: opening it clears
the session and hands over to the identity provider's logout, which reloads
the app on the sign-in page.
"""

import streamlit as st

from raia import auth

for _key in list(st.session_state):
    del st.session_state[_key]
auth.logout()
