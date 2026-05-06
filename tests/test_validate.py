from __future__ import annotations

import pandas as pd
import pytest

from etl import validate


def test_validate_schema_passes_when_all_columns_present() -> None:
    """Schema validation should pass when all required columns are present."""
    df = pd.DataFrame({c: [1] for c in validate.EXPECTED_COLUMNS})
    result = validate.validate_schema(df)
    assert result["valid"] is True


def test_validate_schema_fails_when_missing_columns() -> None:
    """Schema validation should fail when a required column is missing."""
    df = pd.DataFrame({"invoice_no": ["I1"]})
    result = validate.validate_schema(df)
    assert result["valid"] is False


def test_valid_data_passes_validation(valid_retail_df) -> None:
    """Valid data should pass all data quality checks."""
    report = validate.validate_retail_data(valid_retail_df)
    assert report["schema_valid"] is True
    assert report["invalid_rows"] == 0


def test_invalid_category_is_rejected() -> None:
    """A row with an invalid category should be caught."""
    df = pd.DataFrame({c: ["I1"] if c == "invoice_no" else
                       ["C1"] if c == "customer_id" else
                       ["Male"] if c == "gender" else
                       [25] if c == "age" else
                       ["Electronics"] if c == "category" else
                       [1] if c == "quantity" else
                       [10.0] if c == "price" else
                       ["Cash"] if c == "payment_method" else
                       ["5/8/2022"] if c == "invoice_date" else
                       ["Kanyon"]
                       for c in validate.EXPECTED_COLUMNS})
    report = validate.validate_data_quality(df)
    assert report["invalid_rows"] >= 1
    assert report["error_summary"]["invalid_category"] >= 1


def test_negative_quantity_is_rejected() -> None:
    """A row with negative quantity should be caught."""
    df = pd.DataFrame({c: ["I1"] if c == "invoice_no" else
                       ["C1"] if c == "customer_id" else
                       ["Male"] if c == "gender" else
                       [25] if c == "age" else
                       ["Books"] if c == "category" else
                       [-1] if c == "quantity" else
                       [10.0] if c == "price" else
                       ["Cash"] if c == "payment_method" else
                       ["5/8/2022"] if c == "invoice_date" else
                       ["Kanyon"]
                       for c in validate.EXPECTED_COLUMNS})
    report = validate.validate_data_quality(df)
    assert report["error_summary"]["invalid_quantity"] >= 1


def test_negative_price_is_rejected() -> None:
    """A row with negative price should be caught."""
    df = pd.DataFrame({c: ["I1"] if c == "invoice_no" else
                       ["C1"] if c == "customer_id" else
                       ["Male"] if c == "gender" else
                       [25] if c == "age" else
                       ["Books"] if c == "category" else
                       [1] if c == "quantity" else
                       [-5.0] if c == "price" else
                       ["Cash"] if c == "payment_method" else
                       ["5/8/2022"] if c == "invoice_date" else
                       ["Kanyon"]
                       for c in validate.EXPECTED_COLUMNS})
    report = validate.validate_data_quality(df)
    assert report["error_summary"]["invalid_price"] >= 1


def test_null_invoice_no_is_rejected() -> None:
    """A row with null invoice_no should be caught."""
    df = pd.DataFrame({c: [None] if c == "invoice_no" else
                       ["C1"] if c == "customer_id" else
                       ["Male"] if c == "gender" else
                       [25] if c == "age" else
                       ["Books"] if c == "category" else
                       [1] if c == "quantity" else
                       [10.0] if c == "price" else
                       ["Cash"] if c == "payment_method" else
                       ["5/8/2022"] if c == "invoice_date" else
                       ["Kanyon"]
                       for c in validate.EXPECTED_COLUMNS})
    report = validate.validate_data_quality(df)
    assert report["error_summary"]["null_invoice_no"] >= 1


def test_separate_valid_invalid_splits_correctly(
    valid_retail_df, invalid_retail_df
) -> None:
    """Mixed valid/invalid rows should be split correctly."""
    combined = pd.concat([valid_retail_df, invalid_retail_df], ignore_index=True)
    report = validate.validate_data_quality(combined)
    valid_df, invalid_df = validate.separate_valid_invalid(
        combined, report["invalid_row_indices"]
    )
    assert len(valid_df) + len(invalid_df) == len(combined)
    assert len(invalid_df) == report["invalid_rows"]