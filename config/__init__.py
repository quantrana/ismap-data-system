"""Configuration package for ISMAP.

This package exposes application-wide configuration objects, such as
the `settings` instance that centralizes environment configuration.
"""

from .settings import settings

__all__ = ["settings"]

