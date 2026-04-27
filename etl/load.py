"""Load transformed star-schema DataFrames into Amazon RDS PostgreSQL.

Loading order:
    1. ``dim_time`` (idempotent upsert)
    2. ``dim_customer`` (idempotent upsert + return surrogate key map)
    3. Read seeded maps for ``dim_product`` / ``dim_store`` / ``dim_payment``
    4. Build facts via :func:`etl.transform.transform_facts`
    5. ``fact_sales`` (bulk insert)
    6. ``fact_daily_summary`` (idempotent upsert)

All steps run inside one transaction; any failure rolls back.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List

import pandas as pd
import psycopg2
from psycopg2 import OperationalError
from psycopg2 import sql as pg_sql
from psycopg2.extras import execute_values

from config.settings import settings
from etl import transform


LOGGER = logging.getLogger(__name__)

FACT_SALES_BATCH_SIZE = 5000
PAGE_SIZE = 5000


def get_connection() -> psycopg2.extensions.connection:
    """Open a psycopg2 connection to RDS PostgreSQL."""
    try:
        return psycopg2.connect(
            host=settings.RDS_HOST,
            port=settings.RDS_PORT,
            dbname=settings.RDS_DATABASE,
            user=settings.RDS_USER,
            password=settings.RDS_PASSWORD,
            connect_timeout=15,
        )
    except OperationalError as exc:
        raise RuntimeError(
            "Failed to connect to RDS PostgreSQL at "
            f"{settings.RDS_HOST}:{settings.RDS_PORT}/{settings.RDS_DATABASE}. "
            "Check credentials, network access, and security group rules."
        ) from exc


def load_dim_time(conn: psycopg2.extensions.connection, dim_time_df: pd.DataFrame) -> int:
    """Upsert ``dim_time`` rows; returns the number of rows processed."""
    if dim_time_df.empty:
        return 0

    cols = [
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
    ]
    values = [tuple(row) for row in dim_time_df[cols].to_numpy()]

    stmt = """
        INSERT INTO dim_time (
            date_key, full_date, day_name, day_of_week, week_number,
            month_number, month_name, quarter, year, is_weekend, is_holiday, season
        )
        VALUES %s
        ON CONFLICT (date_key) DO UPDATE SET
            full_date = EXCLUDED.full_date,
            day_name = EXCLUDED.day_name,
            day_of_week = EXCLUDED.day_of_week,
            week_number = EXCLUDED.week_number,
            month_number = EXCLUDED.month_number,
            month_name = EXCLUDED.month_name,
            quarter = EXCLUDED.quarter,
            year = EXCLUDED.year,
            is_weekend = EXCLUDED.is_weekend,
            is_holiday = EXCLUDED.is_holiday,
            season = EXCLUDED.season
    """
    with conn.cursor() as cur:
        execute_values(cur, stmt, values, page_size=PAGE_SIZE)

    LOGGER.info("Loaded dim_time: %s rows", len(values))
    return len(values)


def load_dim_customer(
    conn: psycopg2.extensions.connection, dim_customer_df: pd.DataFrame
) -> Dict[str, int]:
    """Upsert ``dim_customer`` and return ``{customer_id: customer_key}``."""
    if dim_customer_df.empty:
        return {}

    cols = [
        "customer_id",
        "gender",
        "age",
        "age_group",
        "first_purchase_date",
        "last_purchase_date",
        "total_transactions",
    ]
    values = [tuple(row) for row in dim_customer_df[cols].to_numpy()]

    stmt = """
        INSERT INTO dim_customer (
            customer_id, gender, age, age_group,
            first_purchase_date, last_purchase_date, total_transactions
        )
        VALUES %s
        ON CONFLICT (customer_id) DO UPDATE SET
            gender = EXCLUDED.gender,
            age = EXCLUDED.age,
            age_group = EXCLUDED.age_group,
            first_purchase_date = EXCLUDED.first_purchase_date,
            last_purchase_date = EXCLUDED.last_purchase_date,
            total_transactions = EXCLUDED.total_transactions
    """

    with conn.cursor() as cur:
        execute_values(cur, stmt, values, page_size=PAGE_SIZE)

        customer_ids = dim_customer_df["customer_id"].astype(str).tolist()
        cur.execute(
            "SELECT customer_id, customer_key FROM dim_customer WHERE customer_id = ANY(%s)",
            (customer_ids,),
        )
        mapping = {row[0]: int(row[1]) for row in cur.fetchall()}

    LOGGER.info("Loaded dim_customer: %s rows", len(values))
    return mapping


def get_dimension_map(
    conn: psycopg2.extensions.connection,
    table_name: str,
    key_column: str,
    value_column: str,
) -> Dict[str, int]:
    """Return ``{natural_key: surrogate_key}`` for any seeded dimension table."""
    query = pg_sql.SQL("SELECT {k}, {v} FROM {t}").format(
        k=pg_sql.Identifier(key_column),
        v=pg_sql.Identifier(value_column),
        t=pg_sql.Identifier(table_name),
    )
    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
    return {str(k): int(v) for k, v in rows}


def load_fact_sales(
    conn: psycopg2.extensions.connection, fact_sales_df: pd.DataFrame
) -> int:
    """Bulk insert ``fact_sales`` rows (in 5000-row batches).

    ``sale_id`` is SERIAL and is omitted from the INSERT.
    Caller manages the surrounding transaction.
    """
    if fact_sales_df.empty:
        return 0

    cols = [
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

    stmt = """
        INSERT INTO fact_sales (
            invoice_no, date_key, customer_key, product_key, store_key, payment_key,
            quantity, price, total_amount, is_holiday, is_weekend
        )
        VALUES %s
    """

    total_inserted = 0
    with conn.cursor() as cur:
        for batch_idx, start in enumerate(
            range(0, len(fact_sales_df), FACT_SALES_BATCH_SIZE), start=1
        ):
            batch = fact_sales_df.iloc[start : start + FACT_SALES_BATCH_SIZE]
            values = [tuple(row) for row in batch[cols].to_numpy()]
            execute_values(cur, stmt, values, page_size=len(values))
            total_inserted += len(values)
            LOGGER.info("Loaded fact_sales batch %s: %s rows", batch_idx, len(values))

    return total_inserted


def load_fact_daily_summary(
    conn: psycopg2.extensions.connection, summary_df: pd.DataFrame
) -> int:
    """Upsert ``fact_daily_summary`` keyed by ``(date_key, store_key)``."""
    if summary_df.empty:
        return 0

    cols = [
        "date_key",
        "store_key",
        "total_revenue",
        "total_transactions",
        "avg_transaction_value",
        "unique_customers",
        "top_category",
        "top_payment_method",
    ]
    values = [tuple(row) for row in summary_df[cols].to_numpy()]

    stmt = """
        INSERT INTO fact_daily_summary (
            date_key, store_key, total_revenue, total_transactions,
            avg_transaction_value, unique_customers, top_category, top_payment_method
        )
        VALUES %s
        ON CONFLICT (date_key, store_key) DO UPDATE SET
            total_revenue = EXCLUDED.total_revenue,
            total_transactions = EXCLUDED.total_transactions,
            avg_transaction_value = EXCLUDED.avg_transaction_value,
            unique_customers = EXCLUDED.unique_customers,
            top_category = EXCLUDED.top_category,
            top_payment_method = EXCLUDED.top_payment_method
    """
    with conn.cursor() as cur:
        execute_values(cur, stmt, values, page_size=PAGE_SIZE)

    LOGGER.info("Loaded fact_daily_summary: %s rows", len(values))
    return len(values)


def load_all(
    conn: psycopg2.extensions.connection,
    transformed_dimensions: Dict[str, pd.DataFrame],
    raw_df: pd.DataFrame,
    holidays: List[dict],
) -> Dict[str, object]:
    """Load every star-schema table inside a single transaction.

    On any failure, the entire transaction is rolled back.
    The ``holidays`` argument is currently unused at load time but is part of
    the public signature so callers can pass it through unchanged.
    """
    del holidays  # accepted for forward compatibility

    summary: Dict[str, object] = {
        "dim_time": {"rows": 0},
        "dim_customer": {"rows": 0},
        "fact_sales": {"rows": 0},
        "fact_daily_summary": {"rows": 0},
        "status": "failed",
        "error": None,
    }

    overall_start = time.perf_counter()
    old_autocommit = conn.autocommit
    conn.autocommit = False

    try:
        LOGGER.info("Starting load_all transaction")

        step = time.perf_counter()
        dim_time_rows = load_dim_time(conn, transformed_dimensions["dim_time"])
        summary["dim_time"] = {"rows": dim_time_rows}
        LOGGER.info("dim_time loaded in %.2fs", time.perf_counter() - step)

        step = time.perf_counter()
        customer_map = load_dim_customer(conn, transformed_dimensions["dim_customer"])
        summary["dim_customer"] = {"rows": int(len(transformed_dimensions["dim_customer"]))}
        LOGGER.info("dim_customer loaded in %.2fs", time.perf_counter() - step)

        product_map = get_dimension_map(conn, "dim_product", "category", "product_key")
        store_map = get_dimension_map(conn, "dim_store", "shopping_mall", "store_key")
        payment_map = get_dimension_map(conn, "dim_payment", "payment_method", "payment_key")

        step = time.perf_counter()
        facts = transform.transform_facts(
            raw_df=raw_df,
            dim_time_df=transformed_dimensions["dim_time"],
            customer_map=customer_map,
            product_map=product_map,
            store_map=store_map,
            payment_map=payment_map,
        )
        LOGGER.info("Facts transformed in %.2fs", time.perf_counter() - step)

        step = time.perf_counter()
        fact_sales_rows = load_fact_sales(conn, facts["fact_sales"])
        summary["fact_sales"] = {"rows": fact_sales_rows}
        LOGGER.info("fact_sales loaded in %.2fs", time.perf_counter() - step)

        step = time.perf_counter()
        daily_rows = load_fact_daily_summary(conn, facts["fact_daily_summary"])
        summary["fact_daily_summary"] = {"rows": daily_rows}
        LOGGER.info("fact_daily_summary loaded in %.2fs", time.perf_counter() - step)

        conn.commit()
        summary["status"] = "success"
        LOGGER.info("load_all committed (%.2fs)", time.perf_counter() - overall_start)
        return summary

    except Exception as exc:
        try:
            conn.rollback()
        except psycopg2.Error:
            LOGGER.exception("Rollback failed.")
        summary["status"] = "failed"
        summary["error"] = str(exc)
        LOGGER.exception("load_all failed; transaction rolled back.")
        return summary
    finally:
        conn.autocommit = old_autocommit


__all__ = [
    "get_connection",
    "load_dim_time",
    "load_dim_customer",
    "get_dimension_map",
    "load_fact_sales",
    "load_fact_daily_summary",
    "load_all",
]
