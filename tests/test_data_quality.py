from __future__ import annotations

import os

import psycopg2
import pytest
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Open a connection to RDS PostgreSQL."""
    return psycopg2.connect(
        host=os.getenv("RDS_HOST"),
        port=os.getenv("RDS_PORT", 5432),
        dbname=os.getenv("RDS_DATABASE"),
        user=os.getenv("RDS_USER"),
        password=os.getenv("RDS_PASSWORD"),
        connect_timeout=15,
    )


def test_run_data_quality_checks_returns_report() -> None:
    """validate_retail_data should return a basic combined report structure."""
    import pandas as pd
    from etl import validate

    df = pd.DataFrame({c: [] for c in validate.EXPECTED_COLUMNS})
    report = validate.validate_retail_data(df)
    assert "schema_valid" in report
    assert "total_rows" in report
    assert "invalid_rows" in report


@pytest.mark.integration
def test_fact_sales_row_count() -> None:
    """fact_sales should have approximately 99,457 rows."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM fact_sales;")
        count = cur.fetchone()[0]
    conn.close()
    assert 94000 <= count <= 100000, f"Unexpected row count: {count}"


@pytest.mark.integration
def test_fact_sales_foreign_keys_resolve() -> None:
    """Every fact_sales foreign key should resolve to its dimension table."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM fact_sales f
            LEFT JOIN dim_time t ON f.date_key = t.date_key
            WHERE t.date_key IS NULL;
        """)
        assert cur.fetchone()[0] == 0

        cur.execute("""
            SELECT COUNT(*) FROM fact_sales f
            LEFT JOIN dim_customer c ON f.customer_key = c.customer_key
            WHERE c.customer_key IS NULL;
        """)
        assert cur.fetchone()[0] == 0

        cur.execute("""
            SELECT COUNT(*) FROM fact_sales f
            LEFT JOIN dim_product p ON f.product_key = p.product_key
            WHERE p.product_key IS NULL;
        """)
        assert cur.fetchone()[0] == 0

        cur.execute("""
            SELECT COUNT(*) FROM fact_sales f
            LEFT JOIN dim_store s ON f.store_key = s.store_key
            WHERE s.store_key IS NULL;
        """)
        assert cur.fetchone()[0] == 0

        cur.execute("""
            SELECT COUNT(*) FROM fact_sales f
            LEFT JOIN dim_payment p ON f.payment_key = p.payment_key
            WHERE p.payment_key IS NULL;
        """)
        assert cur.fetchone()[0] == 0
    conn.close()


@pytest.mark.integration
def test_no_null_surrogate_keys_in_fact_sales() -> None:
    """fact_sales should have no null surrogate keys."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM fact_sales
            WHERE date_key IS NULL
               OR customer_key IS NULL
               OR product_key IS NULL
               OR store_key IS NULL
               OR payment_key IS NULL;
        """)
        assert cur.fetchone()[0] == 0
    conn.close()


@pytest.mark.integration
def test_fact_sales_total_amount_equals_quantity_times_price() -> None:
    """A random sample of fact_sales should have total_amount == quantity * price."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT * FROM fact_sales
                ORDER BY RANDOM()
                LIMIT 100
            ) sample
            WHERE ABS(total_amount - (quantity * price)) > 0.01;
        """)
        assert cur.fetchone()[0] == 0
    conn.close()


@pytest.mark.integration
def test_dimension_row_counts() -> None:
    """dim_store should have 10 rows, dim_product 8, dim_payment 3."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM dim_store;")
        assert cur.fetchone()[0] == 10

        cur.execute("SELECT COUNT(*) FROM dim_product;")
        assert cur.fetchone()[0] == 8

        cur.execute("SELECT COUNT(*) FROM dim_payment;")
        assert cur.fetchone()[0] == 3
    conn.close()


@pytest.mark.integration
def test_dim_time_has_holiday() -> None:
    """dim_time should contain at least one row with is_holiday = TRUE."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM dim_time WHERE is_holiday = TRUE;")
        assert cur.fetchone()[0] >= 1
    conn.close()