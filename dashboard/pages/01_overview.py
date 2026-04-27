"""Overview page for the ISMAP Streamlit dashboard.

Provides an executive summary of key performance indicators across
all malls and time periods.
"""

from __future__ import annotations

import streamlit as st


def render() -> None:
    """Render the overview dashboard page."""
    st.title("Overview")
    st.markdown(
        "High-level KPIs and summary visualisations for Istanbul shopping malls."
    )
    # Placeholder components; real implementation will query curated tables.
    st.metric("Total Revenue (TRY)", "—")
    st.metric("Total Transactions", "—")
    st.metric("Unique Customers", "—")


if __name__ == "__main__":
    render()

