"""AWS Lambda handler to orchestrate holiday extraction via Nager.Date.

This Lambda can be scheduled via CloudWatch Events to periodically
refresh the holiday dimension used for time-series enrichment.
"""

from __future__ import annotations
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.extract_holidays import (
    fetch_all_holidays,
    upload_to_s3,
    _holiday_date_range,
)

LOGGER = logging.getLogger(__name__)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Entry point for the holiday extraction Lambda function.

    Parameters
    ----------
    event:
        AWS event payload with optional configuration overrides.
    context:
        AWS Lambda context object (unused in this stub).

    Returns
    -------
    dict
        Summary of the extraction run.
    """
    current_year = datetime.now(timezone.utc).year
    start_year = int(event.get("start_year", current_year))
    end_year = int(event.get("end_year", current_year))
    
    years = list(range(start_year, end_year + 1))
    LOGGER.info("Fetching holidays for years: %s", years)

    holidays = fetch_all_holidays(years)
    upload_to_s3(holidays)

    summary = {
        "status": "success",
        "years": years,
        "total_holidays": len(holidays),
        "date_range": _holiday_date_range(holidays),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    LOGGER.info("Holiday extraction complete: %s", summary)
    return summary