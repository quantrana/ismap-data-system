"""Bootstrap the ISMAP PostgreSQL star schema in Amazon RDS.

Idempotent: safe to run repeatedly during development and deploys.

Default behaviour: drop → create → verify → seed static dimensions.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import psycopg2
from psycopg2 import OperationalError
from psycopg2.extensions import connection as PGConnection
from psycopg2.extensions import cursor as PGCursor

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings


LOGGER = logging.getLogger(__name__)

SQL_DIR = PROJECT_ROOT / "sql"
DROP_SQL_PATH = SQL_DIR / "drop_schema.sql"
CREATE_SQL_PATH = SQL_DIR / "create_schema.sql"

EXPECTED_TABLES: List[Tuple[str, int]] = [
    ("dim_time", 12),
    ("dim_customer", 8),
    ("dim_product", 2),
    ("dim_store", 2),
    ("dim_payment", 2),
    ("fact_sales", 12),
    ("fact_daily_summary", 9),
]

CATEGORIES: Tuple[str, ...] = (
    "Books",
    "Clothing",
    "Cosmetics",
    "Food & Beverage",
    "Shoes",
    "Souvenir",
    "Technology",
    "Toys",
)
MALLS: Tuple[str, ...] = (
    "Kanyon",
    "Forum Istanbul",
    "Metrocity",
    "Metropol AVM",
    "Istinye Park",
    "Mall of Istanbul",
    "Emaar Square Mall",
    "Cevahir AVM",
    "Viaport Outlet",
    "Zorlu Center",
)
PAYMENT_METHODS: Tuple[str, ...] = ("Cash", "Credit Card", "Debit Card")


def connect_to_rds() -> PGConnection:
    """Open an autocommit psycopg2 connection to RDS PostgreSQL."""
    try:
        conn = psycopg2.connect(
            host=settings.RDS_HOST,
            port=settings.RDS_PORT,
            dbname=settings.RDS_DATABASE,
            user=settings.RDS_USER,
            password=settings.RDS_PASSWORD,
            connect_timeout=15,
        )
        conn.autocommit = True
    except OperationalError as exc:
        raise RuntimeError(
            "Failed to connect to RDS PostgreSQL at "
            f"{settings.RDS_HOST}:{settings.RDS_PORT}/{settings.RDS_DATABASE}. "
            "Check credentials, network access, and security group rules."
        ) from exc

    LOGGER.info("Connected to %s/%s", settings.RDS_HOST, settings.RDS_DATABASE)
    return conn


def drop_all_tables(conn: PGConnection) -> None:
    """Drop every star-schema table by executing ``sql/drop_schema.sql``."""
    sql = DROP_SQL_PATH.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    LOGGER.info("Dropped star schema tables")


def create_all_tables(conn: PGConnection) -> None:
    """Create the star-schema by executing ``sql/create_schema.sql``."""
    sql = CREATE_SQL_PATH.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    LOGGER.info("Created star schema tables")


def _fetchone_int(cur: PGCursor) -> int:
    """Return the first integer value from the current cursor result, or 0."""
    row = cur.fetchone()
    return int(row[0]) if row else 0


def verify_schema(conn: PGConnection) -> bool:
    """Verify all 7 star-schema tables exist with the expected column counts."""
    lines = ["Table Name          | Columns | Status"]
    all_ok = True

    with conn.cursor() as cur:
        for table_name, expected_cols in EXPECTED_TABLES:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = %s
                """,
                (table_name,),
            )
            exists = _fetchone_int(cur) == 1

            col_count = 0
            if exists:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    """,
                    (table_name,),
                )
                col_count = _fetchone_int(cur)

            ok = exists and col_count == expected_cols
            all_ok = all_ok and ok
            status = "OK" if ok else "FAIL"
            lines.append(f"{table_name:<19}| {col_count:<7}| {status}")

    LOGGER.info("Schema verification:\n%s", "\n".join(lines))
    return all_ok


def seed_static_dimensions(conn: PGConnection) -> None:
    """Insert reference values into ``dim_product``, ``dim_store``, ``dim_payment``.

    Idempotent via ``ON CONFLICT DO NOTHING``.
    """
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO dim_product (category) VALUES (%s) "
            "ON CONFLICT (category) DO NOTHING",
            [(c,) for c in CATEGORIES],
        )
        LOGGER.info("Seeded dim_product (%s categories)", len(CATEGORIES))

        cur.executemany(
            "INSERT INTO dim_store (shopping_mall) VALUES (%s) "
            "ON CONFLICT (shopping_mall) DO NOTHING",
            [(m,) for m in MALLS],
        )
        LOGGER.info("Seeded dim_store (%s malls)", len(MALLS))

        cur.executemany(
            "INSERT INTO dim_payment (payment_method) VALUES (%s) "
            "ON CONFLICT (payment_method) DO NOTHING",
            [(p,) for p in PAYMENT_METHODS],
        )
        LOGGER.info("Seeded dim_payment (%s methods)", len(PAYMENT_METHODS))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the database setup script."""
    parser = argparse.ArgumentParser(
        description="Create / reset / verify / seed the ISMAP PostgreSQL star schema."
    )
    parser.add_argument("--verify", action="store_true", help="Verify schema only.")
    parser.add_argument("--seed", action="store_true", help="Seed static dimensions only.")
    parser.add_argument("--drop", action="store_true", help="Drop schema only.")
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="When resetting, skip the seeding step.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    return parser.parse_args(argv)


def _configure_logging(level: str) -> None:
    """Configure root logging at the given level with timestamps."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def main(argv: list[str] | None = None) -> Dict[str, object]:
    """Entry point: run drop/create/verify/seed depending on CLI flags."""
    args = parse_args(argv)
    _configure_logging(args.log_level)

    conn: PGConnection | None = None
    try:
        conn = connect_to_rds()

        if args.verify:
            return {"action": "verify", "ok": verify_schema(conn)}

        if args.seed:
            seed_static_dimensions(conn)
            return {"action": "seed", "ok": True}

        if args.drop:
            drop_all_tables(conn)
            return {"action": "drop", "ok": True}

        drop_all_tables(conn)
        create_all_tables(conn)
        ok = verify_schema(conn)
        if not ok:
            LOGGER.error("Schema verification failed.")
            return {"action": "reset", "ok": False}

        if not args.no_seed:
            seed_static_dimensions(conn)

        return {"action": "reset", "ok": True, "seeded": (not args.no_seed)}
    except Exception:
        LOGGER.exception("Database setup failed.")
        return {"action": "error", "ok": False}
    finally:
        if conn is not None:
            try:
                conn.close()
            except psycopg2.Error:
                LOGGER.debug("Error closing connection (ignored).", exc_info=True)


if __name__ == "__main__":
    main()
