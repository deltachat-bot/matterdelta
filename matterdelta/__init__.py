"""Matterdelta bot."""
import asyncio

from .hooks import cli


def main() -> None:
    """Run the application."""
    try:
        asyncio.run(cli.start())
    except KeyboardInterrupt:
        pass
