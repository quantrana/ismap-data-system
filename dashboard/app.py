"""Main Streamlit application entrypoint for ISMAP.

This module defines the top-level layout and navigation for the
interactive retail analytics dashboard.
"""

from __future__ import annotations

import streamlit as st

from data import get_sales_base


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

    st.divider()
    st.subheader("Data Health Check")
    try:
        df = get_sales_base()
    except Exception as exc:
        st.error(f"Could not connect to the warehouse: {exc}")
        st.info(
            "Set `RDS_HOST`, `RDS_PORT`, `RDS_DATABASE`, `RDS_USER`, `RDS_PASSWORD` "
            "in `.env`, or use `dashboard/.streamlit/secrets.toml`."
        )
        return

    if df.empty:
        st.warning("Connected successfully, but `fact_sales` has no rows yet.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Rows in fact_sales", f"{len(df):,}")
    c2.metric("Date Range", f"{df['full_date'].min().date()} to {df['full_date'].max().date()}")
    c3.metric("Malls", f"{df['shopping_mall'].nunique()}")


if __name__ == "__main__":
    main()

