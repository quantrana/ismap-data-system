from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture
def valid_retail_df() -> pd.DataFrame:
    """A small valid retail DataFrame matching the expected schema."""
    return pd.DataFrame(
        {
            "invoice_no": ["I1", "I2", "I3"],
            "customer_id": ["C1", "C2", "C3"],
            "gender": ["Male", "Female", "Male"],
            "age": [25, 30, 45],
            "category": ["Books", "Clothing", "Shoes"],
            "quantity": [1, 2, 3],
            "price": [10.0, 20.0, 30.0],
            "payment_method": ["Cash", "Credit Card", "Debit Card"],
            "invoice_date": ["5/8/2022", "16/05/2021", "1/3/2023"],
            "shopping_mall": ["Kanyon", "Metrocity", "Zorlu Center"],
        }
    )


@pytest.fixture
def invalid_retail_df() -> pd.DataFrame:
    """A small invalid retail DataFrame with deliberate data quality issues."""
    return pd.DataFrame(
        {
            "invoice_no": [None, "I2", "I3"],
            "customer_id": ["C1", "C2", "C3"],
            "gender": ["Male", "Unknown", "Male"],
            "age": [25, -5, 45],
            "category": ["Books", "Electronics", "Shoes"],
            "quantity": [1, -2, 3],
            "price": [10.0, 20.0, -5.0],
            "payment_method": ["Cash", "Bitcoin", "Debit Card"],
            "invoice_date": ["5/8/2022", "16/05/2021", "1/3/2023"],
            "shopping_mall": ["Kanyon", "Metrocity", "Zorlu Center"],
        }
    )


@pytest.fixture
def sample_holidays() -> list:
    """A holidays list containing one known Turkish public holiday."""
    return [
        {
            "date": "2022-04-23",
            "localName": "Ulusal Egemenlik ve Çocuk Bayramı",
            "name": "National Sovereignty and Children's Day",
            "countryCode": "TR",
            "fixed": True,
            "global": True,
            "counties": None,
            "launchYear": None,
            "types": ["Public"],
        }
    ]