"""Download the Istanbul Shopping Mall dataset from Kaggle and upload it to S3.

Dataset: ``mehmettahiraslan/customer-shopping-dataset``
File:    ``customer_shopping_data.csv`` (99,458 rows, 10 columns)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import boto3
import pandas as pd
from botocore.exceptions import BotoCoreError, ClientError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings


LOGGER = logging.getLogger(__name__)

DATASET_ID = "mehmettahiraslan/customer-shopping-dataset"
RAW_CSV_NAME = "customer_shopping_data.csv"
DEFAULT_S3_KEY = "raw/kaggle/customer_shopping_data.csv"
EXPECTED_COLUMNS = [
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


def _configure_logging() -> None:
    """Configure root logging at INFO level with timestamps."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def _ensure_kaggle_credentials() -> Path:
    """Make sure ``~/.kaggle/kaggle.json`` exists and return its path."""
    os.environ["KAGGLE_USERNAME"] = settings.KAGGLE_USERNAME
    os.environ["KAGGLE_KEY"] = settings.KAGGLE_KEY

    kaggle_dir = Path.home() / ".kaggle"
    kaggle_json = kaggle_dir / "kaggle.json"
    if kaggle_json.exists():
        return kaggle_json

    try:
        kaggle_dir.mkdir(parents=True, exist_ok=True)
        kaggle_json.write_text(
            json.dumps(
                {"username": settings.KAGGLE_USERNAME, "key": settings.KAGGLE_KEY},
                indent=2,
            ),
            encoding="utf-8",
        )
        try:
            kaggle_json.chmod(0o600)
        except OSError:
            LOGGER.debug("Could not chmod %s; continuing.", kaggle_json)
        LOGGER.info("Created Kaggle credentials at %s", kaggle_json)
    except OSError as exc:
        raise RuntimeError(
            f"Failed to write Kaggle credentials at {kaggle_json}: {exc}"
        ) from exc

    return kaggle_json


def _get_kaggle_api():
    """Return an authenticated Kaggle API client."""
    _ensure_kaggle_credentials()

    # Import after credentials are in place; the Kaggle client may try to
    # authenticate during import in some environments.
    from kaggle.api.kaggle_api_extended import KaggleApi  # type: ignore

    api = KaggleApi()
    api.authenticate()
    return api


def download_from_kaggle(output_dir: str) -> str:
    """Download the dataset from Kaggle and return the path to the CSV."""
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        api = _get_kaggle_api()
    except Exception as exc:
        raise RuntimeError(
            "Kaggle authentication failed. Set KAGGLE_USERNAME/KAGGLE_KEY "
            "or place a valid ~/.kaggle/kaggle.json."
        ) from exc

    try:
        api.dataset_download_files(DATASET_ID, path=str(out_dir), unzip=True)
    except Exception as exc:
        msg = str(exc).lower()
        if "404" in msg or "not found" in msg:
            raise RuntimeError(
                f"Kaggle dataset not found: {DATASET_ID}"
            ) from exc
        raise RuntimeError(
            f"Kaggle download failed for {DATASET_ID}: {exc}"
        ) from exc

    csv_path = out_dir / RAW_CSV_NAME
    if not csv_path.exists():
        matches = list(out_dir.rglob(RAW_CSV_NAME))
        if not matches:
            raise FileNotFoundError(
                f"Expected `{RAW_CSV_NAME}` was not found under {out_dir} "
                "after Kaggle download."
            )
        csv_path = matches[0]

    return str(csv_path)


def validate_downloaded_file(filepath: str) -> Dict[str, object]:
    """Return a structured validation summary for the downloaded CSV."""
    path = Path(filepath)
    file_size_mb = round(path.stat().st_size / (1024 * 1024), 4)

    df = pd.read_csv(path)
    columns = list(df.columns)
    rows = int(df.shape[0])
    col_count = int(df.shape[1])

    valid = (
        col_count == 10
        and columns == EXPECTED_COLUMNS
        and rows > 0
    )

    return {
        "valid": valid,
        "rows": rows,
        "columns": col_count,
        "file_size_mb": file_size_mb,
    }


def upload_to_s3(filepath: str, s3_key: str = DEFAULT_S3_KEY) -> bool:
    """Upload a local file to S3 and verify the object exists."""
    path = Path(filepath).resolve()
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    validation = validate_downloaded_file(str(path))

    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )

    metadata = {
        "upload_timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "kaggle",
        "row_count": str(int(validation["rows"])),
    }

    try:
        s3_client.upload_file(
            Filename=str(path),
            Bucket=settings.S3_BUCKET_NAME,
            Key=s3_key,
            ExtraArgs={"Metadata": metadata},
        )
        s3_client.head_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
    except (ClientError, BotoCoreError) as exc:
        raise RuntimeError(
            f"S3 upload failed for s3://{settings.S3_BUCKET_NAME}/{s3_key}: {exc}"
        ) from exc

    return True


def _write_sample(filepath: str, sample_out: Path, n: int = 100) -> None:
    """Write the first N rows of ``filepath`` to ``sample_out``."""
    sample_out = sample_out.resolve()
    sample_out.parent.mkdir(parents=True, exist_ok=True)
    pd.read_csv(filepath).head(n).to_csv(sample_out, index=False)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the Kaggle extraction script."""
    parser = argparse.ArgumentParser(
        description="Download the Istanbul Shopping Mall Kaggle dataset and upload to S3."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw/kaggle"),
        help="Local directory for the Kaggle download.",
    )
    parser.add_argument(
        "--s3-key",
        type=str,
        default=DEFAULT_S3_KEY,
        help="S3 object key for the raw CSV.",
    )
    parser.add_argument(
        "--sample-out",
        type=Path,
        default=Path("data/sample/sample_100.csv"),
        help="Path for the 100-row development sample CSV.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    """Run download → validate → sample → upload. Exits non-zero on failure."""
    _configure_logging()
    args = parse_args(argv)

    overall_start = time.perf_counter()

    try:
        t0 = time.perf_counter()
        csv_path = download_from_kaggle(str(args.output_dir))
        LOGGER.info("Downloaded CSV: %s (%.2fs)", csv_path, time.perf_counter() - t0)

        t0 = time.perf_counter()
        validation = validate_downloaded_file(csv_path)
        if not validation["valid"]:
            actual_cols = pd.read_csv(csv_path, nrows=0).columns.tolist()
            raise RuntimeError(
                "Downloaded CSV failed validation. "
                f"Expected columns: {EXPECTED_COLUMNS}. Got: {actual_cols}"
            )
        LOGGER.info(
            "Validated CSV: rows=%s columns=%s size_mb=%s (%.2fs)",
            validation["rows"],
            validation["columns"],
            validation["file_size_mb"],
            time.perf_counter() - t0,
        )

        t0 = time.perf_counter()
        _write_sample(csv_path, args.sample_out, n=100)
        LOGGER.info("Wrote sample: %s (%.2fs)", args.sample_out, time.perf_counter() - t0)

        t0 = time.perf_counter()
        upload_to_s3(csv_path, s3_key=args.s3_key)
        LOGGER.info(
            "Uploaded to s3://%s/%s (%.2fs)",
            settings.S3_BUCKET_NAME,
            args.s3_key,
            time.perf_counter() - t0,
        )

        LOGGER.info(
            "Kaggle extraction complete: rows=%s size_mb=%s s3=s3://%s/%s total=%.2fs",
            validation["rows"],
            validation["file_size_mb"],
            settings.S3_BUCKET_NAME,
            args.s3_key,
            time.perf_counter() - overall_start,
        )
    except Exception as exc:
        LOGGER.exception("Kaggle extraction failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
