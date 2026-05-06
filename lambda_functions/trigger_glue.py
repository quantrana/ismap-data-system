"""AWS Lambda handler to trigger AWS Glue ETL jobs for ISMAP.

This function will be wired to CloudWatch Events (EventBridge) or S3
notifications to start Glue jobs on a schedule or in response to new data.
"""

from __future__ import annotations
import logging
import sys
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from etl.pipeline import run_pipeline

LOGGER = logging.getLogger(__name__)

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    #Entry point for the Lambda function triggered by an S3 PUT event
    """Entry point triggered by an S3 PUT event.

    Parameters
    ----------
    event:
        AWS event payload containing S3 bucket and object key details.
    context:
        AWS Lambda context object (unused).

    Returns
    -------
    dict
        Pipeline result summary, or a skipped/error status dict.
    """

    LOGGER.info("trigger_glue invoked: %s", event)

    #1. Parse the bucket and object key from the S3 event

    try:
        record = event["Records"][0]["s3"]
        bucket = record["bucket"]["name"]
        key = record["object"]["key"]
    except (KeyError, IndexError) as exc:
        LOGGER.error("Malformed S3 event — cannot parse bucket/key: %s", exc)
        return {"status": "error", "reason": "malformed_event"}

    LOGGER.info("S3 event: bucket=%s key=%s", bucket, key)

    #2. Ignore anything that isn't a .csv file under the raw/ prefix.

    if not (key.endswith(".csv") and key.startswith("raw/")):
        LOGGER.info("Skipping key %s — not a raw/ CSV, no action taken.", key)
        return {"status": "skipped", "bucket": bucket, "key": key}
        
    #3. Call run_pipeline(source="s3") and log the outcome.

    LOGGER.info("Starting ETL pipeline for s3://%s/%s", bucket, key)
    result = run_pipeline(source="s3")

    if result.get("status") == "success":
        LOGGER.info("Pipeline completed successfully: %s", result)
    else: 
        LOGGER.error(
            "Pipeline failed at step '%s' : %s",
            result.get("failed_step"),
            result.get("error"),
        )
    return result