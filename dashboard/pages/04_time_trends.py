"""Time trends page for the ISMAP Streamlit dashboard."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from data import get_sales_base, render_custom_sidebar


def render() -> None:
    """Render the time trends dashboard page."""
    render_custom_sidebar("trends")
    st.title("Time Trends")
    st.markdown(
        "Visualise temporal patterns such as daily, weekly, and seasonal trends."
    )

    try:
        df = get_sales_base()
    except Exception as exc:
        st.error(f"Unable to load data: {exc}")
        return

    if df.empty:
        st.warning("No data found in `fact_sales`.")
        return

    monthly = (
        df.assign(month=df["full_date"].dt.to_period("M").astype(str))
        .groupby("month", as_index=False)["total_amount"]
        .sum()
        .rename(columns={"total_amount": "revenue"})
    )
    quarterly = (
        df.assign(quarter=df["full_date"].dt.to_period("Q").astype(str))
        .groupby("quarter", as_index=False)["total_amount"]
        .sum()
        .rename(columns={"total_amount": "revenue"})
    )
    holiday_split = (
        df.assign(holiday_flag=df["is_holiday"].map({True: "Holiday", False: "Non-Holiday"}))
        .groupby("holiday_flag", as_index=False)["total_amount"]
        .sum()
        .rename(columns={"total_amount": "revenue"})
    )
    weekend_split = (
        df.assign(weekend_flag=df["is_weekend"].map({True: "Weekend", False: "Weekday"}))
        .groupby("weekend_flag", as_index=False)["total_amount"]
        .sum()
        .rename(columns={"total_amount": "revenue"})
    )
    seasonal = (
        df.groupby("month_name", as_index=False)["total_amount"]
        .sum()
        .rename(columns={"total_amount": "revenue"})
    )
    month_order = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    seasonal["month_name"] = seasonal["month_name"].astype("category").cat.set_categories(
        month_order, ordered=True
    )
    seasonal = seasonal.sort_values("month_name")

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.plotly_chart(
                px.line(
                    monthly,
                    x="month",
                    y="revenue",
                    title="Monthly Revenue Trend",
                    labels={"month": "Month", "revenue": "Revenue (TRY)"},
                    markers=True,
                ),
                width="stretch",
            )
    with col2:
        with st.container(border=True):
            st.plotly_chart(
                px.line(
                    quarterly,
                    x="quarter",
                    y="revenue",
                    title="Quarterly Revenue Trend",
                    labels={"quarter": "Quarter", "revenue": "Revenue (TRY)"},
                    markers=True,
                ),
                width="stretch",
            )

    col3, col4 = st.columns(2)
    with col3:
        with st.container(border=True):
            st.plotly_chart(
                px.bar(
                    holiday_split,
                    x="holiday_flag",
                    y="revenue",
                    color="holiday_flag",
                    title="Holiday vs Non-Holiday Revenue",
                    labels={"holiday_flag": "Day Type", "revenue": "Revenue (TRY)"},
                ),
                width="stretch",
            )
    with col4:
        with st.container(border=True):
            st.plotly_chart(
                px.bar(
                    weekend_split,
                    x="weekend_flag",
                    y="revenue",
                    color="weekend_flag",
                    title="Weekend vs Weekday Revenue",
                    labels={"weekend_flag": "Day Type", "revenue": "Revenue (TRY)"},
                ),
                width="stretch",
            )

    with st.container(border=True):
        st.plotly_chart(
            px.bar(
                seasonal,
                x="month_name",
                y="revenue",
                title="Seasonal Breakdown (by Month)",
                labels={"month_name": "Month", "revenue": "Revenue (TRY)"},
            ),
            width="stretch",
        )


if __name__ == "__main__":
    render()

