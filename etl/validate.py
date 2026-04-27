"""Schema and row-level data quality rules for the Kaggle retail dataset.

Source: ``customer_shopping_data.csv`` (99,458 rows, 10 columns).

All functions are pure: they take DataFrames and return structured results.
No I/O, no DB calls.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

import pandas as pd


LOGGER = logging.getLogger(__name__)


EXPECTED_COLUMNS: List[str] = [
    "invoice_no",
    "customer_id",
    "gender",
    "age",
    "category",
    "quantity",
    "price",
    "payment_method",
    "invoice_date",
    "shopping_mall",
]

VALID_MALLS: List[str] = [
    "Kanyon",
    "Forum Istanbul",
    "Metrocity",
    "Metropol AVM",
    "Istinye Park",
    "Mall of Istanbul",
    "Emaar Square Mall",
    "Cevahir AVM",
    "Viaport Outlet",
    "Zorlu Center",
]

VALID_CATEGORIES: List[str] = [
    "Books",
    "Clothing",
    "Cosmetics",
    "Food & Beverage",
    "Shoes",
    "Souvenir",
    "Technology",
    "Toys",
]

VALID_PAYMENT_METHODS: List[str] = ["Cash", "Credit Card", "Debit Card"]
VALID_GENDERS: List[str] = ["Male", "Female"]

MIN_AGE = 1
MAX_AGE = 120


def validate_schema(df: pd.DataFrame) -> Dict[str, object]:
    """Return ``{"valid": bool, "errors": [...]}`` for the column-level schema."""
    errors: List[str] = []
    actual_cols = list(df.columns)

    if len(actual_cols) != len(EXPECTED_COLUMNS):
        errors.append(f"expected_{len(EXPECTED_COLUMNS)}_columns_got_{len(actual_cols)}")
    if actual_cols != EXPECTED_COLUMNS:
        errors.append("column_names_mismatch")

    valid = not errors
    LOGGER.info("Schema valid=%s", valid)
    if not valid:
        LOGGER.warning("Schema errors: %s", errors)

    return {"valid": valid, "errors": errors}


def _stripped_str_series(df: pd.DataFrame, col: str) -> pd.Series:
    """Return ``df[col]`` as a stripped string series (NA preserved)."""
    return df[col].astype("string").str.strip()


def validate_data_quality(df: pd.DataFrame) -> Dict[str, object]:
    """Run row-level data quality checks and return a structured report.

    Per-row rules:
        - invoice_no: not null, prefix ``I``
        - customer_id: not null, prefix ``C``
        - gender: in {Male, Female}
        - age: numeric, ``1..120``
        - category: in the 8 valid categories
        - quantity: numeric, > 0
        - price: numeric, > 0
        - payment_method: in {Cash, Credit Card, Debit Card}
        - invoice_date: not null, parseable (day-first)
        - shopping_mall: in the 10 valid malls
    """
    total_rows = int(len(df))
    LOGGER.info("Validating %s rows", total_rows)

    if total_rows == 0:
        return {
            "total_rows": 0,
            "valid_rows": 0,
            "invalid_rows": 0,
            "error_summary": {},
            "invalid_row_indices": [],
        }

    invoice_no = _stripped_str_series(df, "invoice_no")
    customer_id = _stripped_str_series(df, "customer_id")
    gender = _stripped_str_series(df, "gender")
    category = _stripped_str_series(df, "category")
    payment_method = _stripped_str_series(df, "payment_method")
    shopping_mall = _stripped_str_series(df, "shopping_mall")

    age_num = pd.to_numeric(df["age"], errors="coerce")
    qty_num = pd.to_numeric(df["quantity"], errors="coerce")
    price_num = pd.to_numeric(df["price"], errors="coerce")

    # Source dates are mixed day-first formats (e.g. "5/8/2022", "16/05/2021").
    parsed_date = pd.to_datetime(df["invoice_date"], errors="coerce", dayfirst=True)

    invalid_masks: Dict[str, pd.Series] = {
        "null_invoice_no": invoice_no.isna(),
        "invalid_invoice_no_prefix": invoice_no.notna() & ~invoice_no.str.startswith("I"),
        "null_customer_id": customer_id.isna(),
        "invalid_customer_id_prefix": customer_id.notna() & ~customer_id.str.startswith("C"),
        "invalid_gender": gender.isna() | ~gender.isin(VALID_GENDERS),
        "invalid_age": age_num.isna() | (age_num < MIN_AGE) | (age_num > MAX_AGE),
        "invalid_category": category.isna() | ~category.isin(VALID_CATEGORIES),
        "invalid_quantity": qty_num.isna() | (qty_num <= 0),
        "invalid_price": price_num.isna() | (price_num <= 0),
        "invalid_payment_method": (
            payment_method.isna() | ~payment_method.isin(VALID_PAYMENT_METHODS)
        ),
        "invalid_invoice_date": df["invoice_date"].isna() | parsed_date.isna(),
        "invalid_shopping_mall": shopping_mall.isna() | ~shopping_mall.isin(VALID_MALLS),
    }

    error_summary = {key: int(mask.sum()) for key, mask in invalid_masks.items()}

    any_invalid = pd.Series(False, index=df.index)
    for mask in invalid_masks.values():
        any_invalid |= mask

    invalid_rows = int(any_invalid.sum())
    invalid_indices = df.index[any_invalid].tolist()

    if invalid_rows:
        LOGGER.warning(
            "Found %s invalid rows (%.2f%%)",
            invalid_rows,
            (invalid_rows / total_rows) * 100.0,
        )
    else:
        LOGGER.info("No invalid rows")

    return {
        "total_rows": total_rows,
        "valid_rows": total_rows - invalid_rows,
        "invalid_rows": invalid_rows,
        "error_summary": error_summary,
        "invalid_row_indices": invalid_indices,
    }


def separate_valid_invalid(
    df: pd.DataFrame, invalid_indices: List[int]
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split ``df`` into ``(valid_df, invalid_df)`` using ``invalid_indices``."""
    invalid_set = set(invalid_indices)
    invalid_mask = df.index.isin(invalid_set)
    return df.loc[~invalid_mask].copy(), df.loc[invalid_mask].copy()


def validate_retail_data(df: pd.DataFrame) -> Dict[str, object]:
    """Run schema + data quality checks and return a combined report."""
    schema_result = validate_schema(df)
    if not schema_result["valid"]:
        return {
            "schema_valid": False,
            "total_rows": int(len(df)),
            "valid_rows": 0,
            "invalid_rows": int(len(df)),
            "error_summary": {"schema_errors": len(schema_result["errors"])},
            "invalid_row_indices": df.index.tolist(),
        }

    dq = validate_data_quality(df)
    return {
        "schema_valid": True,
        "total_rows": int(dq["total_rows"]),
        "valid_rows": int(dq["valid_rows"]),
        "invalid_rows": int(dq["invalid_rows"]),
        "error_summary": dq["error_summary"],
        "invalid_row_indices": dq["invalid_row_indices"],
    }


__all__ = [
    "EXPECTED_COLUMNS",
    "VALID_CATEGORIES",
    "VALID_MALLS",
    "VALID_PAYMENT_METHODS",
    "VALID_GENDERS",
    "validate_schema",
    "validate_data_quality",
    "separate_valid_invalid",
    "validate_retail_data",
]
