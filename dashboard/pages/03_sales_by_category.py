"""Sales by category page for the ISMAP Streamlit dashboard."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from data import get_sales_base, render_custom_sidebar


def render() -> None:
    """Render the sales by category dashboard page."""
    render_custom_sidebar("category")
    st.title("Sales by Category")
    st.markdown(
        "Explore performance across product categories and subcategories."
    )

    try:
        df = get_sales_base()
    except Exception as exc:
        st.error(f"Unable to load data: {exc}")
        return

    if df.empty:
        st.warning("No data found in `fact_sales`.")
        return

    by_category = (
        df.groupby("category", as_index=False)
        .agg(
            revenue=("total_amount", "sum"),
            quantity=("quantity", "sum"),
        )
        .sort_values("revenue", ascending=False)
    )

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.plotly_chart(
                px.pie(
                    by_category,
                    names="category",
                    values="revenue",
                    title="Revenue Share by Category",
                ),
                width="stretch",
            )
    with col2:
        with st.container(border=True):
            st.plotly_chart(
                px.bar(
                    by_category,
                    x="category",
                    y="quantity",
                    color="category",
                    title="Quantity Sold by Category",
                    labels={"category": "Category", "quantity": "Quantity"},
                ),
                width="stretch",
            )

    with st.container(border=True):
        st.plotly_chart(
            px.bar(
                by_category,
                x="category",
                y="revenue",
                title="Revenue by Category",
                labels={"category": "Category", "revenue": "Revenue (TRY)"},
            ),
            width="stretch",
        )


if __name__ == "__main__":
    render()

