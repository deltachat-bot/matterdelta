"""Matterdelta bot."""
from .hooks import cli


def main() -> None:
    """Run the application."""
    try:
        cli.start()
    except KeyboardInterrupt:
        pass
