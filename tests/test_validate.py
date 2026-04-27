"""Tests for the `etl.validate` module."""

from __future__ import annotations

import pandas as pd

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

