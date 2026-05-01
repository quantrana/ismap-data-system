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

    by_gender = (
        df.groupby("gender", as_index=False)
        .agg(revenue=("total_amount", "sum"), customers=("customer_id", "nunique"))
        .sort_values("revenue", ascending=False)
    )
    by_age_group = (
        df.groupby("age_group", as_index=False)
        .agg(revenue=("total_amount", "sum"), customers=("customer_id", "nunique"))
        .sort_values("age_group")
    )
    top_customers = (
        df.groupby(["customer_id", "gender", "age_group"], as_index=False)
        .agg(
            spend=("total_amount", "sum"),
            transactions=("invoice_no", "nunique"),
        )
        .sort_values("spend", ascending=False)
        .head(20)
    )

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(
            px.pie(
                by_gender,
                names="gender",
                values="revenue",
                title="Revenue Share by Gender",
            ),
            use_container_width=True,
        )
    with col2:
        st.plotly_chart(
            px.bar(
                by_age_group,
                x="age_group",
                y="customers",
                title="Unique Customers by Age Group",
                labels={"age_group": "Age Group", "customers": "Customers"},
            ),
            use_container_width=True,
        )

    st.subheader("Top 20 Customers by Spend")
    st.dataframe(
        top_customers.style.format({"spend": "{:,.2f}", "transactions": "{:,}"}),
        use_container_width=True,
    )


if __name__ == "__main__":
    render()

