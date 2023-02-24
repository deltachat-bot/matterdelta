"""Utilities"""
import asyncio
import logging
import os
from typing import Coroutine

_background_tasks = set()


def run_in_background(coro: Coroutine) -> None:
    """Schedule the execution of a coroutine object in a spawn task, keeping a
    reference to the task to avoid it disappearing mid-execution due to GC.
    """
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def get_log_level() -> int:
    """Get log level from environment variables. Defaults to INFO if not set."""
    level = os.getenv("MATTERDELTA_DEBUG", "info").upper()
    return int(getattr(logging, level))
