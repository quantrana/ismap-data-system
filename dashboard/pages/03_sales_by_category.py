"""Sales by category page for the ISMAP Streamlit dashboard."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from data import get_sales_base


def render() -> None:
    """Render the sales by category dashboard page."""
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

    categories = sorted(df["category"].unique().tolist())
    selected = st.multiselect("Categories", categories, default=categories)
    if selected:
        df = df[df["category"].isin(selected)]

    by_category = (
        df.groupby("category", as_index=False)
        .agg(
            revenue=("total_amount", "sum"),
            quantity=("quantity", "sum"),
            transactions=("invoice_no", "nunique"),
        )
        .sort_values("revenue", ascending=False)
    )

    st.plotly_chart(
        px.bar(
            by_category,
            x="category",
            y="revenue",
            color="category",
            title="Revenue by Category",
            labels={"category": "Category", "revenue": "Revenue (TRY)"},
        ),
        use_container_width=True,
    )

    heatmap_df = (
        df.groupby(["shopping_mall", "category"], as_index=False)["total_amount"]
        .sum()
        .rename(columns={"total_amount": "revenue"})
    )
    st.plotly_chart(
        px.density_heatmap(
            heatmap_df,
            x="category",
            y="shopping_mall",
            z="revenue",
            title="Category Revenue by Mall",
            labels={
                "category": "Category",
                "shopping_mall": "Mall",
                "revenue": "Revenue (TRY)",
            },
        ),
        use_container_width=True,
    )

    st.dataframe(
        by_category.style.format(
            {"revenue": "{:,.2f}", "quantity": "{:,}", "transactions": "{:,}"}
        ),
        use_container_width=True,
    )


if __name__ == "__main__":
    render()

