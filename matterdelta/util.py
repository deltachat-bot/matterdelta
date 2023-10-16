"""Utilities"""
import logging
import os


def get_log_level() -> int:
    """Get log level from environment variables. Defaults to INFO if not set."""
    level = os.getenv("MATTERDELTA_DEBUG", "info").upper()
    return int(getattr(logging, level))
