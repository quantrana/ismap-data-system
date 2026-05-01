"""Shared data access helpers for the Streamlit dashboard."""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import psycopg2
import streamlit as st
from dotenv import load_dotenv
from streamlit.errors import StreamlitSecretNotFoundError


load_dotenv()


def _db_config() -> dict[str, Any]:
    """Return Postgres connection settings from Streamlit secrets or env vars."""
    try:
        if "database" in st.secrets:
            db = st.secrets["database"]
            return {
                "host": db.get("host"),
                "port": int(db.get("port", 5432)),
                "dbname": db.get("name"),
                "user": db.get("user"),
                "password": db.get("password"),
            }
    except StreamlitSecretNotFoundError:
        # No secrets file is configured; fall back to environment variables.
        pass

    return {
        "host": os.getenv("RDS_HOST"),
        "port": int(os.getenv("RDS_PORT", "5432")),
        "dbname": os.getenv("RDS_DATABASE"),
        "user": os.getenv("RDS_USER"),
        "password": os.getenv("RDS_PASSWORD"),
    }


@st.cache_data(ttl=300, show_spinner=False)
def run_query(query: str) -> pd.DataFrame:
    """Run SQL and return a pandas DataFrame."""
    cfg = _db_config()
    if not all(cfg.values()):
        raise RuntimeError(
            "Missing DB config. Set RDS_* env vars or [database] in .streamlit/secrets.toml."
        )

    with psycopg2.connect(**cfg) as conn:
        return pd.read_sql_query(query, conn)


@st.cache_data(ttl=300, show_spinner=True)
def get_sales_base() -> pd.DataFrame:
    """Return transaction-level data joined with key dimensions."""
    query = """
        SELECT
            fs.sale_id,
            fs.invoice_no,
            dt.full_date,
            dt.year,
            dt.month_name,
            dt.day_name,
            dt.is_weekend,
            dt.is_holiday,
            dc.customer_id,
            dc.gender,
            dc.age,
            dc.age_group,
            dp.category,
            ds.shopping_mall,
            dpay.payment_method,
            fs.quantity,
            fs.price,
            fs.total_amount
        FROM fact_sales fs
        JOIN dim_time dt ON fs.date_key = dt.date_key
        JOIN dim_customer dc ON fs.customer_key = dc.customer_key
        JOIN dim_product dp ON fs.product_key = dp.product_key
        JOIN dim_store ds ON fs.store_key = ds.store_key
        JOIN dim_payment dpay ON fs.payment_key = dpay.payment_key
    """
    df = run_query(query)
    if not df.empty:
        df["full_date"] = pd.to_datetime(df["full_date"])
    return df

