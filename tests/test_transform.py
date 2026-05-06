from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from etl import transform


def test_transform_transactions_returns_dataframe() -> None:
    """`transform_transactions` should return a DataFrame with the same shape."""
    raw = pd.DataFrame({"col": [1, 2, 3]})
    result = transform.transform_transactions(raw)
    assert isinstance(result, pd.DataFrame)
    assert result.shape == raw.shape


def test_build_dim_product_store_payment() -> None:
    """Dimension builders should return distinct values with correct columns."""
    raw = pd.DataFrame(
        {
            "invoice_no": ["I1", "I2"],
            "customer_id": ["C1", "C2"],
            "gender": ["Male", "Female"],
            "age": [20, 30],
            "category": ["Books", "Clothing"],
            "quantity": [1, 2],
            "price": [10.0, 20.0],
            "payment_method": ["Cash", "Credit Card"],
            "invoice_date": ["2021-01-01", "2021-01-02"],
            "shopping_mall": ["Kanyon", "Metrocity"],
        }
    )
    dim_product = transform.build_dim_product(raw)
    dim_store = transform.build_dim_store(raw)
    dim_payment = transform.build_dim_payment(raw)

    assert list(dim_product.columns) == ["category"]
    assert list(dim_store.columns) == ["shopping_mall"]
    assert list(dim_payment.columns) == ["payment_method"]
    assert len(dim_product) == 2
    assert len(dim_store) == 2
    assert len(dim_payment) == 2


def test_parse_invoice_date_day_first() -> None:
    """parse_invoice_date should parse day-first dates correctly."""
    result = transform.parse_invoice_date("5/8/2022")
    assert result == date(2022, 8, 5)


def test_age_group_25() -> None:
    """Age 25 should map to the 18-25 bucket."""
    assert transform._age_group(25) == "18-25"


def test_age_group_30() -> None:
    """Age 30 should map to the 26-35 bucket."""
    assert transform._age_group(30) == "26-35"


def test_fact_sales_total_amount(valid_retail_df, sample_holidays) -> None:
    """fact_sales.total_amount should equal quantity * price for every row."""
    dims = transform.transform_dimensions(valid_retail_df, sample_holidays)

    customer_map = {
        cid: i + 1
        for i, cid in enumerate(valid_retail_df["customer_id"].unique())
    }
    product_map = {
        cat: i + 1
        for i, cat in enumerate(valid_retail_df["category"].unique())
    }
    store_map = {
        mall: i + 1
        for i, mall in enumerate(valid_retail_df["shopping_mall"].unique())
    }
    payment_map = {
        pm: i + 1
        for i, pm in enumerate(valid_retail_df["payment_method"].unique())
    }

    facts = transform.transform_facts(
        raw_df=valid_retail_df,
        dim_time_df=dims["dim_time"],
        customer_map=customer_map,
        product_map=product_map,
        store_map=store_map,
        payment_map=payment_map,
    )
    fact_sales = facts["fact_sales"]
    expected = (
        pd.to_numeric(valid_retail_df["quantity"]) *
        pd.to_numeric(valid_retail_df["price"])
    ).values
    assert (fact_sales["total_amount"].values == expected).all()


def test_dim_time_is_holiday(valid_retail_df, sample_holidays) -> None:
    """dim_time.is_holiday should be True for a known Turkish holiday."""
    from datetime import date
    extra_df = valid_retail_df.copy()
    extra_df["invoice_date"] = ["23/4/2022", "23/4/2022", "23/4/2022"]
    dim_time = transform.build_dim_time(extra_df, sample_holidays)
    holiday_rows = dim_time[dim_time["is_holiday"] == True]
    assert len(holiday_rows) >= 1


def test_dim_time_is_weekend(valid_retail_df, sample_holidays) -> None:
    """dim_time.is_weekend should be True for Saturday and Sunday dates."""
    dim_time = transform.build_dim_time(valid_retail_df, sample_holidays)
    for _, row in dim_time.iterrows():
        d = row["full_date"]
        if d.weekday() in (5, 6):
            assert row["is_weekend"] is True


def test_dim_time_season_spring(valid_retail_df, sample_holidays) -> None:
    """dim_time.season should be Spring for March dates."""
    march_df = valid_retail_df.copy()
    march_df["invoice_date"] = ["1/3/2022", "2/3/2022", "3/3/2022"]
    dim_time = transform.build_dim_time(march_df, sample_holidays)
    for _, row in dim_time.iterrows():
        assert row["season"] == "Spring"


def test_dim_time_season_summer(valid_retail_df, sample_holidays) -> None:
    """dim_time.season should be Summer for July dates."""
    july_df = valid_retail_df.copy()
    july_df["invoice_date"] = ["1/7/2022", "2/7/2022", "3/7/2022"]
    dim_time = transform.build_dim_time(july_df, sample_holidays)
    for _, row in dim_time.iterrows():
        assert row["season"] == "Summer"