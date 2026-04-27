"""High-level data quality tests for ISMAP ETL."""

from __future__ import annotations

import pandas as pd

from etl import validate


def test_run_data_quality_checks_returns_report() -> None:
    """`validate_retail_data` should return a basic combined report structure."""
    df = pd.DataFrame({c: [] for c in validate.EXPECTED_COLUMNS})
    report = validate.validate_retail_data(df)
    assert "schema_valid" in report
    assert "total_rows" in report
    assert "invalid_rows" in report

