"""Fetch Turkish public holidays from Nager.Date and upload them to S3.

API:     ``GET https://date.nager.at/api/v3/PublicHolidays/{year}/TR``
Years:   2021–2023 (matches the retail dataset)
Output:  Combined JSON saved locally and uploaded to the ISMAP S3 data lake.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
import requests
from botocore.exceptions import BotoCoreError, ClientError
from requests import Response

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings


NAGER_DATE_BASE_URL = "https://date.nager.at/api/v3"
COUNTRY_CODE = "TR"
DEFAULT_YEARS = [2021, 2022, 2023]
DEFAULT_S3_KEY = "raw/holidays/turkey_holidays_2021_2023.json"
DEFAULT_LOCAL_PATH = "data/sample/holidays.json"

REQUEST_TIMEOUT_SECONDS = 10
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2

LOGGER = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Configure root logging at INFO level with timestamps."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def _validate_json_response(response: Response) -> List[Dict[str, Any]]:
    """Return the response body as a list of dicts, or raise."""
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("Nager.Date returned non-JSON response.") from exc

    if not isinstance(payload, list) or any(not isinstance(x, dict) for x in payload):
        raise RuntimeError("Nager.Date returned unexpected payload (expected list of dicts).")
    return payload


def fetch_holidays_for_year(year: int) -> List[Dict[str, Any]]:
    """Return Turkish public holidays for a given year (with retries)."""
    url = f"{NAGER_DATE_BASE_URL}/PublicHolidays/{year}/{COUNTRY_CODE}"

    last_exc: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            if response.status_code != 200:
                raise RuntimeError(
                    f"Nager.Date returned HTTP {response.status_code} for year {year}."
                )
            return _validate_json_response(response)
        except Exception as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS)
                continue
            raise RuntimeError(
                f"Failed to fetch holidays for {year} after {MAX_RETRIES} attempts: {exc}"
            ) from exc

    raise RuntimeError(f"Failed to fetch holidays for {year}: {last_exc}")


def fetch_all_holidays(years: Optional[List[int]] = None) -> List[Dict[str, Any]]:
    """Return holidays across all requested years (defaults to 2021–2023)."""
    years = years or DEFAULT_YEARS
    combined: List[Dict[str, Any]] = []

    for year in years:
        holidays = fetch_holidays_for_year(year)
        combined.extend(holidays)
        LOGGER.info("Fetched %s holidays for %s", len(holidays), year)

    LOGGER.info("Total: %s holidays across %s years", len(combined), len(years))
    return combined


def upload_to_s3(holidays: List[Dict[str, Any]], s3_key: str = DEFAULT_S3_KEY) -> bool:
    """Upload holidays JSON to S3 and verify the object exists."""
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )

    body = json.dumps(holidays, ensure_ascii=False).encode("utf-8")

    try:
        s3_client.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=s3_key,
            Body=body,
            ContentType="application/json",
        )
        s3_client.head_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
    except (ClientError, BotoCoreError) as exc:
        raise RuntimeError(
            f"S3 upload failed for s3://{settings.S3_BUCKET_NAME}/{s3_key}: {exc}"
        ) from exc

    return True


def save_local_copy(holidays: List[Dict[str, Any]], filepath: str) -> None:
    """Write a pretty-printed JSON copy of the holidays list to disk."""
    out_path = Path(filepath).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(holidays, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _holiday_date_range(holidays: List[Dict[str, Any]]) -> str:
    """Return a ``min to max`` string of holiday dates (or ``unknown``)."""
    dates = [h["date"] for h in holidays if isinstance(h.get("date"), str) and h["date"]]
    if not dates:
        return "unknown"
    return f"{min(dates)} to {max(dates)}"


def main() -> None:
    """Fetch 2021–2023 Turkish holidays, save locally, and upload to S3."""
    _configure_logging()
    start = time.perf_counter()

    holidays = fetch_all_holidays(DEFAULT_YEARS)
    save_local_copy(holidays, DEFAULT_LOCAL_PATH)
    upload_to_s3(holidays, DEFAULT_S3_KEY)

    elapsed = time.perf_counter() - start
    summary = {
        "total_holidays": len(holidays),
        "date_range": _holiday_date_range(holidays),
        "sample_3": holidays[:3],
        "s3_path": f"s3://{settings.S3_BUCKET_NAME}/{DEFAULT_S3_KEY}",
        "time_seconds": round(elapsed, 3),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    LOGGER.info(
        "Holiday extraction complete: total=%s range=%s s3=%s time=%.2fs",
        summary["total_holidays"],
        summary["date_range"],
        summary["s3_path"],
        elapsed,
    )


if __name__ == "__main__":
    main()
