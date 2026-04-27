"""Main Streamlit application entrypoint for ISMAP.

This module defines the top-level layout and navigation for the
interactive retail analytics dashboard.
"""

from __future__ import annotations

import streamlit as st


def main() -> None:
    """Render the main landing page for the ISMAP dashboard."""
    st.set_page_config(
        page_title="ISMAP - Istanbul Shopping Mall Analytics Platform",
        page_icon="🛍️",
        layout="wide",
    )
    st.title("ISMAP - Istanbul Shopping Mall Analytics Platform")
    st.markdown(
        "Welcome to **ISMAP**, a cloud-native analytics platform providing "
        "actionable insights across Istanbul shopping malls."
    )
    st.markdown(
        "Use the navigation in the sidebar to explore sales performance, "
        "customer demographics, time trends, and more."
    )


if __name__ == "__main__":
    main()

