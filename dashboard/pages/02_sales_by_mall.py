"""Sales by mall page for the ISMAP Streamlit dashboard."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from data import get_sales_base, render_custom_sidebar


def render() -> None:
    """Render the sales by mall dashboard page."""
    render_custom_sidebar("mall")
    st.title("Sales by Mall")
    st.markdown(
        "Analyse revenue and transaction volumes broken down by shopping mall."
    )

    try:
        df = get_sales_base()
    except Exception as exc:
        st.error(f"Unable to load data: {exc}")
        return

    if df.empty:
        st.warning("No data found in `fact_sales`.")
        return

    malls = sorted(df["shopping_mall"].dropna().unique().tolist())
    selected_mall = st.selectbox("Select Mall", malls)
    mall_df = df[df["shopping_mall"] == selected_mall]

    by_mall = (
        df.groupby("shopping_mall", as_index=False)
        .agg(
            revenue=("total_amount", "sum"),
            transactions=("invoice_no", "nunique"),
            customers=("customer_id", "nunique"),
            avg_basket=("total_amount", "mean"),
        )
        .sort_values("revenue", ascending=False)
    )

    with st.container(border=True):
        st.plotly_chart(
            px.bar(
                by_mall,
                x="shopping_mall",
                y="revenue",
                text_auto=".2s",
                title="Total Revenue by Mall",
                labels={"shopping_mall": "Mall", "revenue": "Revenue (TRY)"},
            ),
            width="stretch",
        )

    detail = (
        mall_df.groupby("shopping_mall", as_index=False)
        .agg(
            revenue=("total_amount", "sum"),
            transactions=("invoice_no", "nunique"),
            unique_customers=("customer_id", "nunique"),
            total_quantity=("quantity", "sum"),
            avg_transaction_value=("total_amount", "mean"),
        )
        .sort_values("revenue", ascending=False)
    )
    with st.container(border=True):
        st.subheader(f"Detailed Metrics - {selected_mall}")
        st.dataframe(
            detail.style.format(
                {
                    "revenue": "{:,.2f}",
                    "transactions": "{:,}",
                    "unique_customers": "{:,}",
                    "total_quantity": "{:,}",
                    "avg_transaction_value": "{:,.2f}",
                }
            ),
            width="stretch",
        )


if __name__ == "__main__":
    render()

