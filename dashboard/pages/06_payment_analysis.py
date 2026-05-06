"""Payment analysis page for the ISMAP Streamlit dashboard."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from data import get_sales_base, render_custom_sidebar


def render() -> None:
    """Render the payment analysis dashboard page."""
    render_custom_sidebar("payment")
    st.title("Payment Analysis")
    st.markdown(
        "Compare payment methods (cash, credit card, etc.) and their impact "
        "on basket sizes and conversion."
    )

    try:
        df = get_sales_base()
    except Exception as exc:
        st.error(f"Unable to load data: {exc}")
        return

    if df.empty:
        st.warning("No data found in `fact_sales`.")
        return

    by_payment = (
        df.groupby("payment_method", as_index=False)
        .agg(
            revenue=("total_amount", "sum"),
        )
        .sort_values("revenue", ascending=False)
    )
    by_payment_mall = (
        df.groupby(["shopping_mall", "payment_method"], as_index=False)["total_amount"]
        .sum()
        .rename(columns={"total_amount": "revenue"})
    )

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.plotly_chart(
                px.pie(
                    by_payment,
                    names="payment_method",
                    values="revenue",
                    title="Revenue Share by Payment Method",
                ),
                width="stretch",
            )
    with col2:
        with st.container(border=True):
            st.plotly_chart(
                px.bar(
                    by_payment_mall,
                    x="shopping_mall",
                    y="revenue",
                    color="payment_method",
                    barmode="stack",
                    title="Payment Method by Mall",
                    labels={"shopping_mall": "Mall", "revenue": "Revenue (TRY)"},
                ),
                width="stretch",
            )


if __name__ == "__main__":
    render()

