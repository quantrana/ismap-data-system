"""Transform validated retail transactions into the ISMAP star schema.

Inputs : a validated source DataFrame (Kaggle ``customer_shopping_data.csv``)
         plus a list of Turkish public-holiday dicts (Nager.Date).
Outputs: dimension and fact DataFrames matching ``sql/create_schema.sql``.

All functions are pure: no I/O, no DB or S3 calls.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Dict, List

import pandas as pd
from dateutil import parser as date_parser


LOGGER = logging.getLogger(__name__)


EXPECTED_SOURCE_COLUMNS: List[str] = [
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


def parse_invoice_date(date_str: str) -> date:
    """Parse a source ``invoice_date`` value into a ``date``.

    The Istanbul dataset uses day-first formats such as ``5/8/2022`` and
    ``16/05/2021``. We always parse with ``dayfirst=True`` so the same string
    consistently maps to the same ``date_key``.
    """
    if date_str is None:
        raise ValueError("invoice_date is None")
    s = str(date_str).strip()
    if not s or s.lower() == "nan":
        raise ValueError("invoice_date is empty")
    try:
        return date_parser.parse(s, dayfirst=True).date()
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"Unparseable invoice_date: {s}") from exc


def _date_key(d: date) -> int:
    """Return the YYYYMMDD integer surrogate key for a ``date``."""
    return int(d.strftime("%Y%m%d"))


def _season(month: int) -> str:
    """Return the meteorological season name for a 1–12 month number."""
    if month in (12, 1, 2):
        return "Winter"
    if month in (3, 4, 5):
        return "Spring"
    if month in (6, 7, 8):
        return "Summer"
    return "Autumn"


def _parse_invoice_date_series(series: pd.Series) -> pd.Series:
    """Apply :func:`parse_invoice_date` to every value in a string series."""
    return series.astype("string").map(lambda x: parse_invoice_date(str(x)))


def build_dim_time(df: pd.DataFrame, holidays: List[dict]) -> pd.DataFrame:
    """Build ``dim_time`` from invoice dates and Turkish public holidays."""
    unique_dates = sorted(set(_parse_invoice_date_series(df["invoice_date"]).dropna()))

    holiday_dates: set[date] = set()
    for h in holidays:
        d = h.get("date")
        if isinstance(d, str) and d:
            try:
                holiday_dates.add(parse_invoice_date(d))
            except ValueError:
                continue

    rows: List[Dict[str, object]] = []
    for d in unique_dates:
        _, iso_week, iso_weekday = d.isocalendar()
        month = d.month
        rows.append(
            {
                "date_key": _date_key(d),
                "full_date": d,
                "day_name": d.strftime("%A"),
                "day_of_week": int(iso_weekday),
                "week_number": int(iso_week),
                "month_number": int(month),
                "month_name": d.strftime("%B"),
                "quarter": ((month - 1) // 3) + 1,
                "year": int(d.year),
                "is_weekend": iso_weekday in (6, 7),
                "is_holiday": d in holiday_dates,
                "season": _season(month),
            }
        )

    dim_time = pd.DataFrame(
        rows,
        columns=[
            "date_key",
            "full_date",
            "day_name",
            "day_of_week",
            "week_number",
            "month_number",
            "month_name",
            "quarter",
            "year",
            "is_weekend",
            "is_holiday",
            "season",
        ],
    )

    LOGGER.info(
        "Built dim_time: %s dates, %s holidays",
        len(dim_time),
        int(dim_time["is_holiday"].sum()) if not dim_time.empty else 0,
    )
    return dim_time


def _age_group(age: object) -> str:
    """Return an age-bucket label (``18-25``..``56-69``) or ``Unknown``."""
    try:
        a = int(age)
    except (TypeError, ValueError):
        return "Unknown"

    if 18 <= a <= 25:
        return "18-25"
    if 26 <= a <= 35:
        return "26-35"
    if 36 <= a <= 45:
        return "36-45"
    if 46 <= a <= 55:
        return "46-55"
    if 56 <= a <= 69:
        return "56-69"
    return "Unknown"


def build_dim_customer(df: pd.DataFrame) -> pd.DataFrame:
    """Build ``dim_customer`` aggregated by ``customer_id``."""
    work = df.copy()
    work["_parsed_date"] = _parse_invoice_date_series(work["invoice_date"])

    out = (
        work.groupby("customer_id", dropna=False)
        .agg(
            gender=("gender", "first"),
            age=("age", "first"),
            first_purchase_date=("_parsed_date", "min"),
            last_purchase_date=("_parsed_date", "max"),
            total_transactions=("invoice_no", "count"),
        )
        .reset_index()
    )
    out["age_group"] = out["age"].map(_age_group)

    out = out[
        [
            "customer_id",
            "gender",
            "age",
            "age_group",
            "first_purchase_date",
            "last_purchase_date",
            "total_transactions",
        ]
    ]

    LOGGER.info("Built dim_customer: %s customers", len(out))
    return out


def build_dim_product(df: pd.DataFrame) -> pd.DataFrame:
    """Build ``dim_product`` from distinct categories."""
    out = pd.DataFrame({"category": sorted(df["category"].dropna().astype(str).unique())})
    LOGGER.info("Built dim_product: %s categories", len(out))
    return out


def build_dim_store(df: pd.DataFrame) -> pd.DataFrame:
    """Build ``dim_store`` from distinct shopping malls."""
    out = pd.DataFrame(
        {"shopping_mall": sorted(df["shopping_mall"].dropna().astype(str).unique())}
    )
    LOGGER.info("Built dim_store: %s stores", len(out))
    return out


def build_dim_payment(df: pd.DataFrame) -> pd.DataFrame:
    """Build ``dim_payment`` from distinct payment methods."""
    out = pd.DataFrame(
        {"payment_method": sorted(df["payment_method"].dropna().astype(str).unique())}
    )
    LOGGER.info("Built dim_payment: %s methods", len(out))
    return out


def build_fact_sales(
    df: pd.DataFrame,
    dim_time_df: pd.DataFrame,
    dim_customer_map: Dict[str, int],
    dim_product_map: Dict[str, int],
    dim_store_map: Dict[str, int],
    dim_payment_map: Dict[str, int],
) -> pd.DataFrame:
    """Build ``fact_sales`` using surrogate-key maps and ``dim_time`` flags."""
    work = df.copy()
    work["date_key"] = _parse_invoice_date_series(work["invoice_date"]).map(_date_key).astype(int)

    work["customer_key"] = work["customer_id"].map(dim_customer_map)
    work["product_key"] = work["category"].map(dim_product_map)
    work["store_key"] = work["shopping_mall"].map(dim_store_map)
    work["payment_key"] = work["payment_method"].map(dim_payment_map)

    missing_any = work[
        work[["customer_key", "product_key", "store_key", "payment_key"]].isna().any(axis=1)
    ]
    if not missing_any.empty:
        raise KeyError(
            "Missing surrogate key mappings for some rows. "
            f"Example row indices: {missing_any.index.tolist()[:5]}"
        )

    qty = pd.to_numeric(work["quantity"], errors="coerce")
    price = pd.to_numeric(work["price"], errors="coerce")
    if qty.isna().any() or price.isna().any():
        raise ValueError("quantity/price contain non-numeric values.")

    work["quantity"] = qty.astype(int)
    work["price"] = price.astype(float)
    work["total_amount"] = (qty * price).astype(float)

    time_lookup = dim_time_df.set_index("date_key")[["is_holiday", "is_weekend"]]
    flags = time_lookup.reindex(work["date_key"].values)
    if flags.isna().any(axis=None):
        dim_keys = set(dim_time_df["date_key"].astype(int).unique())
        missing = sorted(set(work["date_key"].unique()) - dim_keys)
        LOGGER.warning(
            "fact_sales has %s date_keys missing from dim_time (first 5): %s",
            len(missing),
            missing[:5],
        )
        raise KeyError("Some date_key values were not found in dim_time_df.")

    work["is_holiday"] = flags["is_holiday"].values.astype(bool)
    work["is_weekend"] = flags["is_weekend"].values.astype(bool)

    out = work[
        [
            "invoice_no",
            "date_key",
            "customer_key",
            "product_key",
            "store_key",
            "payment_key",
            "quantity",
            "price",
            "total_amount",
            "is_holiday",
            "is_weekend",
        ]
    ].copy()

    LOGGER.info(
        "Built fact_sales: %s rows, total_amount=%.2f",
        len(out),
        float(out["total_amount"].sum()),
    )
    return out


def build_fact_daily_summary(
    fact_sales_df: pd.DataFrame,
    product_map_reverse: Dict[int, str],
    payment_map_reverse: Dict[int, str],
) -> pd.DataFrame:
    """Aggregate ``fact_sales`` to one row per ``(date_key, store_key)``."""
    grouped = fact_sales_df.groupby(["date_key", "store_key"], as_index=False)

    agg = grouped.agg(
        total_revenue=("total_amount", "sum"),
        total_transactions=("invoice_no", "count"),
        unique_customers=("customer_key", "nunique"),
    )
    agg["avg_transaction_value"] = (
        agg["total_revenue"] / agg["total_transactions"]
    ).round(2)

    # Top category per group: highest summed revenue.
    revenue_by_product = (
        fact_sales_df.groupby(["date_key", "store_key", "product_key"])["total_amount"]
        .sum()
        .reset_index()
    )
    top_product_idx = revenue_by_product.groupby(["date_key", "store_key"])[
        "total_amount"
    ].idxmax()
    top_category = revenue_by_product.loc[top_product_idx, ["date_key", "store_key", "product_key"]]
    top_category["top_category"] = top_category["product_key"].map(product_map_reverse)
    top_category = top_category.drop(columns=["product_key"])

    # Top payment method per group: most frequent transaction count.
    txn_by_payment = (
        fact_sales_df.groupby(["date_key", "store_key", "payment_key"])
        .size()
        .reset_index(name="txn_count")
    )
    top_payment_idx = txn_by_payment.groupby(["date_key", "store_key"])["txn_count"].idxmax()
    top_payment = txn_by_payment.loc[top_payment_idx, ["date_key", "store_key", "payment_key"]]
    top_payment["top_payment_method"] = top_payment["payment_key"].map(payment_map_reverse)
    top_payment = top_payment.drop(columns=["payment_key"])

    out = (
        agg.merge(top_category, on=["date_key", "store_key"], how="left")
        .merge(top_payment, on=["date_key", "store_key"], how="left")
        [
            [
                "date_key",
                "store_key",
                "total_revenue",
                "total_transactions",
                "avg_transaction_value",
                "unique_customers",
                "top_category",
                "top_payment_method",
            ]
        ]
    )

    LOGGER.info("Built fact_daily_summary: %s rows", len(out))
    return out


def transform_dimensions(raw_df: pd.DataFrame, holidays: List[dict]) -> Dict[str, pd.DataFrame]:
    """Build all dimension DataFrames from validated raw data."""
    return {
        "dim_time": build_dim_time(raw_df, holidays),
        "dim_customer": build_dim_customer(raw_df),
        "dim_product": build_dim_product(raw_df),
        "dim_store": build_dim_store(raw_df),
        "dim_payment": build_dim_payment(raw_df),
    }


def transform_facts(
    raw_df: pd.DataFrame,
    dim_time_df: pd.DataFrame,
    customer_map: Dict[str, int],
    product_map: Dict[str, int],
    store_map: Dict[str, int],
    payment_map: Dict[str, int],
) -> Dict[str, pd.DataFrame]:
    """Build fact DataFrames once dimension surrogate keys are available."""
    fact_sales = build_fact_sales(
        raw_df,
        dim_time_df=dim_time_df,
        dim_customer_map=customer_map,
        dim_product_map=product_map,
        dim_store_map=store_map,
        dim_payment_map=payment_map,
    )
    fact_daily = build_fact_daily_summary(
        fact_sales_df=fact_sales,
        product_map_reverse={v: k for k, v in product_map.items()},
        payment_map_reverse={v: k for k, v in payment_map.items()},
    )
    return {"fact_sales": fact_sales, "fact_daily_summary": fact_daily}


def transform_transactions(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Compatibility shim returning a copy of ``raw_df``.

    Older callers/tests still reference this name; the canonical pipeline now
    uses :func:`transform_dimensions` and :func:`transform_facts`.
    """
    return raw_df.copy()


__all__ = [
    "parse_invoice_date",
    "build_dim_time",
    "build_dim_customer",
    "build_dim_product",
    "build_dim_store",
    "build_dim_payment",
    "build_fact_sales",
    "build_fact_daily_summary",
    "transform_dimensions",
    "transform_facts",
    "transform_transactions",
]
