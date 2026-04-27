"""Typed configuration loaded from environment variables (and optional .env)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import ClassVar, Iterable, List

from dotenv import load_dotenv


REQUIRED_ENV_VARS: tuple[str, ...] = (
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
)


@dataclass(frozen=True)
class Settings:
    """Strongly typed configuration container for ISMAP."""

    _REQUIRED_VARS: ClassVar[Iterable[str]] = REQUIRED_ENV_VARS

    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str
    S3_BUCKET_NAME: str

    RDS_HOST: str
    RDS_PORT: int
    RDS_DATABASE: str
    RDS_USER: str
    RDS_PASSWORD: str

    KAGGLE_USERNAME: str
    KAGGLE_KEY: str

    @classmethod
    def from_env(cls) -> "Settings":
        """Build a validated Settings instance from process environment + .env."""
        load_dotenv(override=False)

        missing: List[str] = [
            name for name in cls._REQUIRED_VARS if not os.getenv(name)
        ]
        if missing:
            raise ValueError(
                "Missing required environment variables: "
                f"{', '.join(sorted(missing))}. "
                "Set them in your shell or in `.env` (see `.env.example`)."
            )

        try:
            rds_port = int(os.environ["RDS_PORT"])
        except ValueError as exc:
            raise ValueError("RDS_PORT must be a valid integer.") from exc

        return cls(
            AWS_ACCESS_KEY_ID=os.environ["AWS_ACCESS_KEY_ID"],
            AWS_SECRET_ACCESS_KEY=os.environ["AWS_SECRET_ACCESS_KEY"],
            AWS_REGION=os.environ["AWS_REGION"],
            S3_BUCKET_NAME=os.environ["S3_BUCKET_NAME"],
            RDS_HOST=os.environ["RDS_HOST"],
            RDS_PORT=rds_port,
            RDS_DATABASE=os.environ["RDS_DATABASE"],
            RDS_USER=os.environ["RDS_USER"],
            RDS_PASSWORD=os.environ["RDS_PASSWORD"],
            KAGGLE_USERNAME=os.environ["KAGGLE_USERNAME"],
            KAGGLE_KEY=os.environ["KAGGLE_KEY"],
        )


settings: Settings = Settings.from_env()


__all__ = ["Settings", "settings", "REQUIRED_ENV_VARS"]
