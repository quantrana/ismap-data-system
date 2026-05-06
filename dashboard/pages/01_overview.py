"""Overview page for the ISMAP Streamlit dashboard.

Provides an executive summary of key performance indicators across
all malls and time periods.
"""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from data import get_sales_base, render_custom_sidebar


def render() -> None:
    """Render the overview dashboard page."""
    render_custom_sidebar("overview")
    st.title("Overview")
    st.markdown(
        "High-level KPIs and summary visualisations for Istanbul shopping malls."
    )
    try:
        df = get_sales_base()
    except Exception as exc:
        st.error(f"Unable to load data: {exc}")
        return

    if df.empty:
        st.warning("No data found in `fact_sales`.")
        return

    total_revenue = float(df["total_amount"].sum())
    transactions = int(df["invoice_no"].nunique())
    unique_customers = int(df["customer_id"].nunique())
    avg_order = total_revenue / transactions if transactions else 0.0

    with st.container(border=True):
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Revenue (TRY)", f"{total_revenue:,.2f}")
        m2.metric("Transactions", f"{transactions:,}")
        m3.metric("Unique Customers", f"{unique_customers:,}")
        m4.metric("Avg Transaction Value", f"{avg_order:,.2f}")

    monthly = (
        df.assign(month=df["full_date"].dt.to_period("M").astype(str))
        .groupby("month", as_index=False)["total_amount"]
        .sum()
        .rename(columns={"total_amount": "revenue"})
    )
    mall_revenue = (
        df.groupby("shopping_mall", as_index=False)["total_amount"]
        .sum()
        .sort_values("total_amount", ascending=False)
        .rename(columns={"total_amount": "revenue"})
    )

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.plotly_chart(
                px.line(
                    monthly,
                    x="month",
                    y="revenue",
                    markers=True,
                    title="Monthly Revenue",
                    labels={"month": "Month", "revenue": "Revenue (TRY)"},
                ),
                width="stretch",
            )
    with col2:
        with st.container(border=True):
            st.plotly_chart(
                px.bar(
                    mall_revenue,
                    x="shopping_mall",
                    y="revenue",
                    title="Revenue by Mall",
                    labels={"shopping_mall": "Mall", "revenue": "Revenue (TRY)"},
                ),
                width="stretch",
            )


if __name__ == "__main__":
    render()

