"""Customer demographics page for the ISMAP Streamlit dashboard."""

from __future__ import annotations

import streamlit as st


def render() -> None:
    """Render the customer demographics dashboard page."""
    st.title("Customer Demographics")
    st.markdown(
        "Understand customer profiles by gender, age group, and visit behaviour."
    )
    # Placeholder for demographic distribution charts.


if __name__ == "__main__":
    render()

