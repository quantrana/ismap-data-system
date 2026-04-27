"""AWS Lambda handler to orchestrate holiday extraction via Nager.Date.

This Lambda can be scheduled via CloudWatch Events to periodically
refresh the holiday dimension used for time-series enrichment.
"""

from __future__ import annotations

from typing import Any, Dict

from scripts import extract_holidays


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
    start_year = int(event.get("start_year", 2021))
    end_year = int(event.get("end_year", start_year))
    country_code = event.get("country_code", "TR")

    # Delegate to the script module's main function.
    result = extract_holidays.main(
        [
            "--start-year",
            str(start_year),
            "--end-year",
            str(end_year),
            "--country-code",
            country_code,
        ]
    )
    return result

