"""Time trends page for the ISMAP Streamlit dashboard."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from data import get_sales_base


def render() -> None:
    """Render the time trends dashboard page."""
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

    daily = (
        df.groupby("full_date", as_index=False)["total_amount"]
        .sum()
        .rename(columns={"total_amount": "revenue"})
    )
    weekday_order = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    weekday = (
        df.groupby("day_name", as_index=False)["total_amount"]
        .sum()
        .rename(columns={"total_amount": "revenue"})
    )
    weekday["day_name"] = weekday["day_name"].astype("category").cat.set_categories(
        weekday_order, ordered=True
    )
    weekday = weekday.sort_values("day_name")

    holiday_weekend = (
        df.groupby(["is_weekend", "is_holiday"], as_index=False)["total_amount"]
        .sum()
        .rename(columns={"total_amount": "revenue"})
    )
    holiday_weekend["type"] = holiday_weekend.apply(
        lambda x: f"weekend={x['is_weekend']}, holiday={x['is_holiday']}", axis=1
    )

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(
            px.line(
                daily,
                x="full_date",
                y="revenue",
                title="Daily Revenue Trend",
                labels={"full_date": "Date", "revenue": "Revenue (TRY)"},
            ),
            use_container_width=True,
        )
    with col2:
        st.plotly_chart(
            px.bar(
                weekday,
                x="day_name",
                y="revenue",
                title="Revenue by Day of Week",
                labels={"day_name": "Day", "revenue": "Revenue (TRY)"},
            ),
            use_container_width=True,
        )

    st.plotly_chart(
        px.bar(
            holiday_weekend,
            x="type",
            y="revenue",
            color="type",
            title="Revenue by Holiday/Weekend Flag",
            labels={"type": "Flag Combination", "revenue": "Revenue (TRY)"},
        ),
        use_container_width=True,
    )


if __name__ == "__main__":
    render()

