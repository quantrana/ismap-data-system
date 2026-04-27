"""Tests for the `etl.transform` module."""

from __future__ import annotations

import pandas as pd

from etl import transform


def test_transform_transactions_returns_dataframe() -> None:
    """`transform_transactions` should return a DataFrame with the same shape in the stub."""
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

