"""Sales by mall page for the ISMAP Streamlit dashboard."""

from __future__ import annotations

import streamlit as st


def render() -> None:
    """Render the sales by mall dashboard page."""
    st.title("Sales by Mall")
    st.markdown(
        "Analyse revenue and transaction volumes broken down by shopping mall."
    )
    # Placeholder for mall-level bar charts / tables.


if __name__ == "__main__":
    render()

