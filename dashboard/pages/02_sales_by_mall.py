"""Sales by mall page for the ISMAP Streamlit dashboard."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from data import get_sales_base


def render() -> None:
    """Render the sales by mall dashboard page."""
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

    st.plotly_chart(
        px.bar(
            by_mall,
            x="shopping_mall",
            y="revenue",
            text_auto=".2s",
            title="Total Revenue by Mall",
            labels={"shopping_mall": "Mall", "revenue": "Revenue (TRY)"},
        ),
        use_container_width=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(
            px.bar(
                by_mall,
                x="shopping_mall",
                y="transactions",
                title="Transactions by Mall",
                labels={"shopping_mall": "Mall", "transactions": "Transactions"},
            ),
            use_container_width=True,
        )
    with col2:
        st.plotly_chart(
            px.scatter(
                by_mall,
                x="transactions",
                y="avg_basket",
                size="revenue",
                hover_name="shopping_mall",
                title="Basket Value vs Transaction Volume",
                labels={
                    "transactions": "Transactions",
                    "avg_basket": "Avg Basket (TRY)",
                },
            ),
            use_container_width=True,
        )

    st.dataframe(
        by_mall.style.format(
            {
                "revenue": "{:,.2f}",
                "transactions": "{:,}",
                "customers": "{:,}",
                "avg_basket": "{:,.2f}",
            }
        ),
        use_container_width=True,
    )


if __name__ == "__main__":
    render()

