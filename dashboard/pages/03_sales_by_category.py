"""Sales by category page for the ISMAP Streamlit dashboard."""

from __future__ import annotations

import streamlit as st


def render() -> None:
    """Render the sales by category dashboard page."""
    st.title("Sales by Category")
    st.markdown(
        "Explore performance across product categories and subcategories."
    )
    # Placeholder for category breakdown charts / tables.


if __name__ == "__main__":
    render()

