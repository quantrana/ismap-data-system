"""Shared data access helpers for the Streamlit dashboard."""

from __future__ import annotations

from typing import Any

import pandas as pd
import psycopg2
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

_SECRETS_HELP = (
    "Add `dashboard/.streamlit/secrets.toml` with a `[database]` section "
    "(copy from `dashboard/.streamlit/secrets.toml.example`)."
)


def _db_config() -> dict[str, Any]:
    """Return Postgres connection settings from Streamlit secrets only."""
    try:
        db = st.secrets["database"]
    except StreamlitSecretNotFoundError as exc:
        raise RuntimeError(
            f"No Streamlit secrets file found. {_SECRETS_HELP}"
        ) from exc
    except (KeyError, TypeError) as exc:
        raise RuntimeError(
            f"Missing or invalid `[database]` in secrets.toml. {_SECRETS_HELP}"
        ) from exc

    def _s(key: str) -> str | None:
        v = db.get(key)
        if v is None:
            return None
        return str(v).strip() or None

    host = _s("host")
    name = _s("name")
    user = _s("user")
    password = _s("password")
    port_raw = db.get("port", 5432)
    try:
        port = int(port_raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            "secrets.toml [database].port must be an integer."
        ) from exc

    return {
        "host": host,
        "port": port,
        "dbname": name,
        "user": user,
        "password": password,
    }


@st.cache_data(ttl=300, show_spinner=False)
def run_query(query: str) -> pd.DataFrame:
    """Run SQL and return a pandas DataFrame."""
    cfg = _db_config()
    missing = [k for k, v in cfg.items() if v in (None, "")]
    if missing:
        raise RuntimeError(
            f"Incomplete [database] in secrets.toml (missing: {', '.join(missing)}). "
            f"{_SECRETS_HELP}"
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
