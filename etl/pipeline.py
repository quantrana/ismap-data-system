"""Main ETL entry point: read → validate → transform → load → verify.

Two source modes:
    * ``--source local``: read CSV/JSON from disk
    * ``--source s3``:    read from the ISMAP data lake

Use ``--dry-run`` to skip the load step (useful for local development).
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import boto3
import pandas as pd
import psycopg2
from botocore.exceptions import BotoCoreError, ClientError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from etl import load, transform, validate


LOGGER = logging.getLogger(__name__)

S3_CSV_KEY = "raw/kaggle/customer_shopping_data.csv"
S3_HOLIDAYS_KEY = "raw/holidays/turkey_holidays_2021_2023.json"

ALL_TABLES = [
    "dim_time",
    "dim_customer",
    "dim_product",
    "dim_store",
    "dim_payment",
    "fact_sales",
    "fact_daily_summary",
]


def _timestamp() -> str:
    """Return a UTC timestamp string suitable for filenames."""
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _setup_logging() -> Path:
    """Configure root logging to stdout and a timestamped file under ``logs/``."""
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"pipeline_{_timestamp()}.log"

    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if not root_logger.handlers:
        console = logging.StreamHandler(stream=sys.stdout)
        console.setFormatter(logging.Formatter(fmt))

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(fmt))

        root_logger.addHandler(console)
        root_logger.addHandler(file_handler)

    return log_path


def _s3_client():
    """Build an S3 client from the configured AWS credentials."""
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )


def read_source_csv(source: str, local_path: str | None = None) -> pd.DataFrame:
    """Read the source transactions CSV from S3 or local disk."""
    if source not in {"s3", "local"}:
        raise ValueError('source must be "s3" or "local"')

    if source == "local":
        if not local_path:
            raise ValueError("local_path is required when source=local")
        df = pd.read_csv(local_path)
        LOGGER.info("Read %s rows from local", len(df))
        return df

    try:
        obj = _s3_client().get_object(Bucket=settings.S3_BUCKET_NAME, Key=S3_CSV_KEY)
        df = pd.read_csv(io.BytesIO(obj["Body"].read()))
    except (ClientError, BotoCoreError) as exc:
        raise RuntimeError(
            f"Failed to read CSV from s3://{settings.S3_BUCKET_NAME}/{S3_CSV_KEY}: {exc}"
        ) from exc

    LOGGER.info("Read %s rows from s3", len(df))
    return df


def read_holidays(source: str, local_path: str | None = None) -> List[dict]:
    """Read holidays JSON from S3 or local disk."""
    if source not in {"s3", "local"}:
        raise ValueError('source must be "s3" or "local"')

    if source == "local":
        if not local_path:
            raise ValueError("local_path is required when source=local")
        holidays = json.loads(Path(local_path).read_text(encoding="utf-8"))
        if not isinstance(holidays, list):
            raise ValueError("Holidays JSON must be a list.")
        LOGGER.info("Read %s holidays", len(holidays))
        return holidays

    try:
        obj = _s3_client().get_object(Bucket=settings.S3_BUCKET_NAME, Key=S3_HOLIDAYS_KEY)
        holidays = json.loads(obj["Body"].read().decode("utf-8"))
    except (ClientError, BotoCoreError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Failed to read holidays from s3://{settings.S3_BUCKET_NAME}/{S3_HOLIDAYS_KEY}: {exc}"
        ) from exc

    if not isinstance(holidays, list):
        raise RuntimeError("Holidays JSON in S3 is not a list.")
    LOGGER.info("Read %s holidays", len(holidays))
    return holidays


def save_rejected_rows(invalid_df: pd.DataFrame, source: str) -> None:
    """Persist rejected rows to S3 (``rejected/...``) or local disk."""
    if invalid_df.empty:
        return

    ts = _timestamp()
    if source == "local":
        out_path = PROJECT_ROOT / "data" / "sample" / f"rejected_{ts}.csv"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        invalid_df.to_csv(out_path, index=False)
        LOGGER.info("Saved %s rejected rows to %s", len(invalid_df), out_path)
        return

    key = f"rejected/rejected_{ts}.csv"
    csv_bytes = invalid_df.to_csv(index=False).encode("utf-8")
    try:
        _s3_client().put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=key,
            Body=csv_bytes,
            ContentType="text/csv",
        )
    except (ClientError, BotoCoreError) as exc:
        raise RuntimeError(
            f"Failed to upload rejected rows to s3://{settings.S3_BUCKET_NAME}/{key}: {exc}"
        ) from exc

    LOGGER.info("Saved %s rejected rows to s3://%s/%s",
                len(invalid_df), settings.S3_BUCKET_NAME, key)


def _query_table_counts(conn: psycopg2.extensions.connection) -> Dict[str, int]:
    """Return ``{table_name: row_count}`` for every star-schema table."""
    counts: Dict[str, int] = {}
    with conn.cursor() as cur:
        for t in ALL_TABLES:
            cur.execute(f"SELECT COUNT(*) FROM {t};")
            counts[t] = int(cur.fetchone()[0])
    return counts


def run_pipeline(
    source: str = "local",
    local_csv: str | None = None,
    local_holidays: str | None = None,
    dry_run: bool = False,
) -> Dict[str, object]:
    """Run the complete ISMAP ETL pipeline and return a structured summary."""
    total_start = time.perf_counter()
    rejected_rows = 0
    step = "init"

    try:
        step = "read"
        step_start = time.perf_counter()
        df = read_source_csv(source=source, local_path=local_csv)
        holidays = read_holidays(source=source, local_path=local_holidays)
        read_time = time.perf_counter() - step_start
        LOGGER.info("READ done in %.2fs", read_time)

        step = "validate"
        step_start = time.perf_counter()
        report = validate.validate_retail_data(df)
        validate_time = time.perf_counter() - step_start
        LOGGER.info(
            "VALIDATE done: schema_valid=%s total=%s valid=%s invalid=%s (%.2fs)",
            report["schema_valid"],
            report["total_rows"],
            report["valid_rows"],
            report["invalid_rows"],
            validate_time,
        )

        if not report["schema_valid"]:
            raise RuntimeError("Schema invalid; aborting pipeline.")

        valid_df, invalid_df = validate.separate_valid_invalid(df, report["invalid_row_indices"])
        rejected_rows = int(len(invalid_df))
        if rejected_rows:
            save_rejected_rows(invalid_df, source=source)

        step = "transform_dimensions"
        step_start = time.perf_counter()
        dims = transform.transform_dimensions(valid_df, holidays)
        transform_time = time.perf_counter() - step_start
        for name, df_dim in dims.items():
            LOGGER.info("Dimension %s: %s rows", name, len(df_dim))
        LOGGER.info("TRANSFORM dimensions done in %.2fs", transform_time)

        if dry_run:
            if rejected_rows:
                LOGGER.info("Dry-run complete (%s rejected rows)", rejected_rows)
            else:
                LOGGER.info("Dry-run complete")
            return {
                "status": "success",
                "source": source,
                "dry_run": True,
                "rejected_rows": rejected_rows,
                "counts": {k: int(len(v)) for k, v in dims.items()},
                "timing_seconds": {
                    "read": round(read_time, 3),
                    "validate": round(validate_time, 3),
                    "transform_dimensions": round(transform_time, 3),
                    "total": round(time.perf_counter() - total_start, 3),
                },
            }

        step = "load"
        step_start = time.perf_counter()
        conn = load.get_connection()
        try:
            load_result = load.load_all(
                conn=conn,
                transformed_dimensions=dims,
                raw_df=valid_df,
                holidays=holidays,
            )
        finally:
            conn.close()
        load_time = time.perf_counter() - step_start
        LOGGER.info("LOAD done in %.2fs", load_time)

        if load_result.get("status") != "success":
            raise RuntimeError(f"Load failed: {load_result.get('error')}")

        step = "verify"
        step_start = time.perf_counter()
        with load.get_connection() as conn:
            counts = _query_table_counts(conn)
        verify_time = time.perf_counter() - step_start

        total_time = time.perf_counter() - total_start
        LOGGER.info(
            "Pipeline complete | "
            "dim_time=%s dim_customer=%s dim_product=%s dim_store=%s dim_payment=%s "
            "fact_sales=%s fact_daily_summary=%s | total=%.2fs",
            counts["dim_time"],
            counts["dim_customer"],
            counts["dim_product"],
            counts["dim_store"],
            counts["dim_payment"],
            counts["fact_sales"],
            counts["fact_daily_summary"],
            total_time,
        )

        return {
            "status": "success",
            "source": source,
            "dry_run": False,
            "rejected_rows": rejected_rows,
            "counts": counts,
            "timing_seconds": {
                "read": round(read_time, 3),
                "validate": round(validate_time, 3),
                "transform_dimensions": round(transform_time, 3),
                "load": round(load_time, 3),
                "verify": round(verify_time, 3),
                "total": round(total_time, 3),
            },
        }

    except Exception as exc:
        LOGGER.exception("Pipeline failed at step: %s", step)
        return {
            "status": "failed",
            "failed_step": step,
            "error": str(exc),
            "source": source,
            "dry_run": dry_run,
            "rejected_rows": rejected_rows,
            "timing_seconds": {"total": round(time.perf_counter() - total_start, 3)},
        }


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments for the pipeline runner."""
    parser = argparse.ArgumentParser(description="Run the ISMAP ETL pipeline.")
    parser.add_argument("--source", choices=["s3", "local"], required=True)
    parser.add_argument("--csv", help="Local CSV path (required if --source local)")
    parser.add_argument("--holidays", help="Local holidays JSON path (required if --source local)")
    parser.add_argument("--dry-run", action="store_true", help="Run validate+transform only.")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    """Pipeline CLI entry point."""
    log_path = _setup_logging()
    args = _parse_args(argv)

    if args.source == "local" and (not args.csv or not args.holidays):
        raise SystemExit("For --source local, you must provide --csv and --holidays.")

    LOGGER.info("Pipeline log: %s", log_path)
    result = run_pipeline(
        source=args.source,
        local_csv=args.csv,
        local_holidays=args.holidays,
        dry_run=args.dry_run,
    )
    if result.get("status") != "success":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
