"""Payment analysis page for the ISMAP Streamlit dashboard."""

from __future__ import annotations

import streamlit as st


def render() -> None:
    """Render the payment analysis dashboard page."""
    st.title("Payment Analysis")
    st.markdown(
        "Compare payment methods (cash, credit card, etc.) and their impact "
        "on basket sizes and conversion."
    )
    # Placeholder for payment method mix charts / tables.


if __name__ == "__main__":
    render()

