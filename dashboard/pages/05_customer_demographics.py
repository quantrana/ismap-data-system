"""Customer demographics page for the ISMAP Streamlit dashboard."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from data import get_sales_base


def render() -> None:
    """Render the customer demographics dashboard page."""
    st.title("Customer Demographics")
    st.markdown(
        "Understand customer profiles by gender, age group, and visit behaviour."
    )

    try:
        df = get_sales_base()
    except Exception as exc:
        st.error(f"Unable to load data: {exc}")
        return

    if df.empty:
        st.warning("No data found in `fact_sales`.")
        return

    by_age_group = df.groupby("age_group", as_index=False).agg(
        customers=("customer_id", "nunique")
    )
    by_gender = df.groupby("gender", as_index=False).agg(customers=("customer_id", "nunique"))
    spend_heatmap = (
        df.groupby(["age_group", "gender"], as_index=False)["total_amount"]
        .sum()
        .rename(columns={"total_amount": "spend"})
    )

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(
            px.bar(
                by_age_group.sort_values("age_group"),
                x="age_group",
                y="customers",
                title="Age Group Distribution",
                labels={"age_group": "Age Group", "customers": "Unique Customers"},
            ),
            width="stretch",
        )
    with col2:
        st.plotly_chart(
            px.pie(
                by_gender,
                names="gender",
                values="customers",
                title="Gender Split",
            ),
            width="stretch",
        )

    st.plotly_chart(
        px.density_heatmap(
            spend_heatmap,
            x="age_group",
            y="gender",
            z="spend",
            title="Spending Heatmap: Age Group x Gender",
            labels={"age_group": "Age Group", "gender": "Gender", "spend": "Spend (TRY)"},
        ),
        width="stretch",
    )


if __name__ == "__main__":
    render()

