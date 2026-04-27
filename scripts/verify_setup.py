"""Health-check script that validates the local ISMAP environment end-to-end.

Each check runs in isolation so a single failure does not stop the rest.
Run:
    python scripts/verify_setup.py
"""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import boto3
import psycopg2
import requests
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import dotenv_values, load_dotenv
from psycopg2 import OperationalError


REQUIRED_PACKAGES = [
    "boto3",
    "kaggle",
    "requests",
    "psycopg2",
    "pandas",
    "streamlit",
    "plotly",
    "pytest",
]

REQUIRED_ENV_VARS = [
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_REGION",
    "S3_BUCKET_NAME",
    "RDS_HOST",
    "RDS_PORT",
    "RDS_DATABASE",
    "RDS_USER",
    "RDS_PASSWORD",
    "KAGGLE_USERNAME",
    "KAGGLE_KEY",
]

EXPECTED_TABLES = [
    "dim_time",
    "dim_customer",
    "dim_product",
    "dim_store",
    "dim_payment",
    "fact_sales",
    "fact_daily_summary",
]

S3_PREFIXES = [
    "raw/kaggle/",
    "raw/holidays/",
    "raw/uploads/",
    "processed/",
    "rejected/",
]

NAGER_TEST_URL = "https://date.nager.at/api/v3/PublicHolidays/2021/TR"

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Ansi:
    """ANSI color codes for terminal output."""

    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    RESET = "\033[0m"


def _supports_color() -> bool:
    """Return True if stdout looks like an ANSI-capable terminal."""
    if not sys.stdout.isatty():
        return False
    return os.getenv("TERM", "").lower() not in ("", "dumb")


def _colored(text: str, code: str) -> str:
    """Wrap ``text`` with the given ANSI ``code`` if the terminal supports it."""
    return f"{code}{text}{Ansi.RESET}" if _supports_color() else text


@dataclass(frozen=True)
class CheckResult:
    """Outcome of a single environment check."""

    ok: bool
    message: str
    fix: Optional[str] = None


def _load_env_file() -> Tuple[bool, Dict[str, str]]:
    """Load values from ``.env`` (without exporting) into a plain dict."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return False, {}
    values = dotenv_values(env_path)
    return True, {k: (v or "") for k, v in values.items() if isinstance(k, str)}


def _export_env() -> None:
    """Load ``.env`` into ``os.environ`` so child tools (e.g. Kaggle) can read it."""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


def _get_setting(env: Dict[str, str], key: str) -> str:
    """Return the value for ``key`` from ``.env`` or from ``os.environ``."""
    return (env.get(key) or os.getenv(key) or "").strip()


def _require_env(env: Dict[str, str], keys: List[str], fix: str) -> Optional[CheckResult]:
    """Return a failing CheckResult if any of ``keys`` is missing, else None."""
    missing = [k for k in keys if _get_setting(env, k) == ""]
    if missing:
        return CheckResult(False, f"Missing config: {', '.join(missing)}", fix=fix)
    return None


def check_python_version() -> CheckResult:
    """Confirm Python is at least 3.9."""
    v = sys.version_info
    version_str = platform.python_version()
    if (v.major, v.minor) >= (3, 9):
        return CheckResult(True, f"Python {version_str}")
    return CheckResult(
        False,
        f"Python {version_str} (requires >= 3.9)",
        fix="Install Python 3.9+ and re-run.",
    )


def check_required_packages() -> CheckResult:
    """Confirm every required Python package is importable."""
    missing = [p for p in REQUIRED_PACKAGES if find_spec(p) is None]
    if not missing:
        return CheckResult(True, "All packages installed")
    return CheckResult(
        False,
        f"Missing packages: {', '.join(missing)}",
        fix="Run: pip install -r requirements.txt",
    )


def check_env_file_configured() -> CheckResult:
    """Confirm ``.env`` exists and contains every required variable."""
    exists, env = _load_env_file()
    if not exists:
        return CheckResult(
            False,
            ".env missing",
            fix="Run: cp .env.example .env  (then fill in values)",
        )
    missing = [k for k in REQUIRED_ENV_VARS if _get_setting(env, k) == ""]
    if missing:
        return CheckResult(
            False,
            f".env missing/empty: {', '.join(missing)}",
            fix="Edit .env and set all required variables.",
        )
    return CheckResult(True, ".env configured")


def check_aws_credentials(env: Dict[str, str]) -> CheckResult:
    """Validate AWS credentials by calling STS ``get_caller_identity``."""
    req = _require_env(
        env,
        ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION"],
        fix="Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION in .env.",
    )
    if req:
        return req

    try:
        sts = boto3.client(
            "sts",
            aws_access_key_id=_get_setting(env, "AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=_get_setting(env, "AWS_SECRET_ACCESS_KEY"),
            region_name=_get_setting(env, "AWS_REGION"),
        )
        account = sts.get_caller_identity().get("Account", "unknown")
        return CheckResult(True, f"AWS credentials valid (account: {account})")
    except (ClientError, BotoCoreError) as exc:
        return CheckResult(
            False,
            f"AWS credentials invalid ({exc.__class__.__name__})",
            fix="Fix AWS_* in .env. Test with: aws sts get-caller-identity",
        )


def _s3_client(env: Dict[str, str]):
    """Build an S3 client using ``.env`` credentials."""
    return boto3.client(
        "s3",
        aws_access_key_id=_get_setting(env, "AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=_get_setting(env, "AWS_SECRET_ACCESS_KEY"),
        region_name=_get_setting(env, "AWS_REGION"),
    )


def check_s3_bucket_access(env: Dict[str, str]) -> CheckResult:
    """Confirm the configured S3 bucket exists and is listable."""
    req = _require_env(
        env,
        ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "S3_BUCKET_NAME"],
        fix="Set AWS_* and S3_BUCKET_NAME in .env.",
    )
    if req:
        return req

    bucket = _get_setting(env, "S3_BUCKET_NAME")
    try:
        _s3_client(env).list_objects_v2(Bucket=bucket, MaxKeys=1)
        return CheckResult(True, f"S3 bucket accessible ({bucket})")
    except (ClientError, BotoCoreError):
        return CheckResult(
            False,
            f"S3 bucket not accessible ({bucket})",
            fix=f"Confirm bucket exists and IAM allows access. Test: aws s3 ls s3://{bucket}",
        )


def check_s3_folder_structure(env: Dict[str, str]) -> CheckResult:
    """Confirm every required S3 prefix has at least one object."""
    req = _require_env(
        env,
        ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "S3_BUCKET_NAME"],
        fix="Set AWS_* and S3_BUCKET_NAME in .env.",
    )
    if req:
        return req

    bucket = _get_setting(env, "S3_BUCKET_NAME")
    s3 = _s3_client(env)

    missing: List[str] = []
    for prefix in S3_PREFIXES:
        try:
            resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1)
            if resp.get("KeyCount", 0) == 0:
                missing.append(prefix)
        except (ClientError, BotoCoreError):
            missing.append(prefix)

    if not missing:
        return CheckResult(True, "S3 folder structure OK")

    cmds = " && ".join(
        f"aws s3api put-object --bucket {bucket} --key {p}.keep" for p in missing
    )
    return CheckResult(
        False,
        f"Missing S3 prefixes: {', '.join(missing)}",
        fix=f"Create placeholders: {cmds}",
    )


def _connect_rds(env: Dict[str, str]) -> psycopg2.extensions.connection:
    """Open a short-lived psycopg2 connection to RDS using ``.env`` values."""
    req = _require_env(
        env,
        ["RDS_HOST", "RDS_PORT", "RDS_DATABASE", "RDS_USER", "RDS_PASSWORD"],
        fix="Set RDS_* in .env.",
    )
    if req:
        raise ValueError(req.message)

    try:
        port = int(_get_setting(env, "RDS_PORT"))
    except ValueError as exc:
        raise ValueError("RDS_PORT must be an integer.") from exc

    return psycopg2.connect(
        host=_get_setting(env, "RDS_HOST"),
        port=port,
        dbname=_get_setting(env, "RDS_DATABASE"),
        user=_get_setting(env, "RDS_USER"),
        password=_get_setting(env, "RDS_PASSWORD"),
        connect_timeout=8,
    )


def check_rds_reachable(env: Dict[str, str]) -> CheckResult:
    """Confirm RDS PostgreSQL is reachable; report the server version."""
    req = _require_env(
        env,
        ["RDS_HOST", "RDS_PORT", "RDS_DATABASE", "RDS_USER", "RDS_PASSWORD"],
        fix="Set RDS_* in .env.",
    )
    if req:
        return req

    conn = None
    try:
        conn = _connect_rds(env)
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = str(cur.fetchone()[0])
        return CheckResult(True, f"RDS reachable ({version.split(' on ', 1)[0].strip()})")
    except OperationalError:
        return CheckResult(
            False,
            "RDS not reachable",
            fix="Check RDS_* in .env and ensure your IP is allowed by the security group.",
        )
    except Exception as exc:
        return CheckResult(False, f"RDS check failed ({exc.__class__.__name__})")
    finally:
        if conn is not None:
            conn.close()


def check_database_tables_exist(env: Dict[str, str]) -> CheckResult:
    """Confirm all 7 star-schema tables exist in the configured database."""
    req = _require_env(
        env,
        ["RDS_HOST", "RDS_PORT", "RDS_DATABASE", "RDS_USER", "RDS_PASSWORD"],
        fix="Set RDS_* in .env.",
    )
    if req:
        return req

    conn = None
    try:
        conn = _connect_rds(env)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = ANY(%s)
                """,
                (EXPECTED_TABLES,),
            )
            existing = {r[0] for r in cur.fetchall()}

        missing = [t for t in EXPECTED_TABLES if t not in existing]
        if missing:
            return CheckResult(
                False,
                f"Schema missing tables: {', '.join(missing)}",
                fix="Run: python scripts/setup_database.py",
            )
        return CheckResult(True, "Database schema OK (7 tables)")
    except Exception:
        return CheckResult(
            False,
            "Schema check failed",
            fix="Run: python scripts/setup_database.py",
        )
    finally:
        if conn is not None:
            conn.close()


def check_dimensions_seeded(env: Dict[str, str]) -> CheckResult:
    """Confirm static dimensions have been seeded with the expected row counts."""
    req = _require_env(
        env,
        ["RDS_HOST", "RDS_PORT", "RDS_DATABASE", "RDS_USER", "RDS_PASSWORD"],
        fix="Set RDS_* in .env.",
    )
    if req:
        return req

    conn = None
    try:
        conn = _connect_rds(env)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT "
                "(SELECT COUNT(*) FROM dim_product), "
                "(SELECT COUNT(*) FROM dim_store), "
                "(SELECT COUNT(*) FROM dim_payment)"
            )
            product, store, payment = cur.fetchone()

        if (product, store, payment) == (8, 10, 3):
            return CheckResult(True, "Dimensions seeded")
        return CheckResult(
            False,
            f"Dimensions not seeded (got {product}/{store}/{payment}, want 8/10/3)",
            fix="Run: python scripts/setup_database.py --seed",
        )
    except Exception:
        return CheckResult(
            False,
            "Dimensions seed check failed",
            fix="Run: python scripts/setup_database.py --seed",
        )
    finally:
        if conn is not None:
            conn.close()


def check_kaggle_authenticated() -> CheckResult:
    """Confirm Kaggle API credentials authenticate successfully."""
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi  # type: ignore

        KaggleApi().authenticate()
        return CheckResult(True, "Kaggle API authenticated")
    except Exception:
        return CheckResult(
            False,
            "Kaggle API authentication failed",
            fix=(
                "Set KAGGLE_USERNAME/KAGGLE_KEY in .env or place a valid "
                "~/.kaggle/kaggle.json. Then re-run."
            ),
        )


def check_nager_api_reachable() -> CheckResult:
    """Confirm the Nager.Date public holidays API is reachable."""
    try:
        resp = requests.get(NAGER_TEST_URL, timeout=10)
        if resp.status_code != 200:
            return CheckResult(
                False,
                f"Nager.Date returned HTTP {resp.status_code}",
                fix="Try again later or check your network.",
            )
        if not isinstance(resp.json(), list):
            return CheckResult(
                False,
                "Nager.Date returned unexpected payload",
                fix="Try again later or check your network.",
            )
        return CheckResult(True, "Nager.Date API reachable")
    except Exception:
        return CheckResult(
            False,
            "Nager.Date API not reachable",
            fix="Check your internet connection and re-run.",
        )


def _run_check(fn: Callable[[], CheckResult]) -> CheckResult:
    """Run ``fn`` and convert any uncaught exception into a failing CheckResult."""
    try:
        return fn()
    except Exception as exc:
        return CheckResult(False, f"{fn.__name__} failed ({exc.__class__.__name__})")


def main() -> None:
    """Run every health check and exit non-zero on any failure."""
    env_exists, env = _load_env_file()
    env = env if env_exists else {}
    _export_env()

    checks: List[Callable[[], CheckResult]] = [
        check_python_version,
        check_required_packages,
        check_env_file_configured,
        lambda: check_aws_credentials(env),
        lambda: check_s3_bucket_access(env),
        lambda: check_s3_folder_structure(env),
        lambda: check_rds_reachable(env),
        lambda: check_database_tables_exist(env),
        lambda: check_dimensions_seeded(env),
        check_kaggle_authenticated,
        check_nager_api_reachable,
    ]

    divider = "─" * 44
    print(divider)
    print("  ISMAP Environment Verification")
    print(divider)

    results: List[CheckResult] = []
    for fn in checks:
        result = _run_check(fn)
        results.append(result)
        symbol = "OK" if result.ok else "FAIL"
        symbol_colored = (
            _colored(symbol, Ansi.GREEN) if result.ok else _colored(symbol, Ansi.RED)
        )
        print(f"  {symbol_colored:>6}  {result.message}")

    print(divider)
    passed = sum(1 for r in results if r.ok)
    print(f"  Result: {passed}/{len(results)} checks passed")

    failures = [r for r in results if not r.ok]
    if failures:
        for f in failures:
            if f.fix:
                print(f"  {_colored('Fix', Ansi.YELLOW)}: {f.fix}")
    print(divider)

    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
