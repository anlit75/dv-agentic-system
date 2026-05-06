"""Shared helpers for all CLI entrypoints."""

import sys
from pathlib import Path


def read_input(input_file: str | None, input_text: str | None = None) -> str:
    """Read text from a file path, '-' (stdin), or a direct string.

    Priority: explicit ``input_text`` > ``input_file`` path > stdin.

    Args:
        input_file: File path to read, or "-" to read from stdin.
        input_text: Direct input string. If provided, overrides ``input_file``.

    Returns:
        The read text content.
    """
    if input_text:
        return input_text
    if input_file:
        if input_file == "-":
            return sys.stdin.read()
        return Path(input_file).read_text(encoding="utf-8")
    return sys.stdin.read()


def die(message: str) -> None:
    """Print message to stderr and exit with code 1.

    Args:
        message: Error message to print.
    """
    print(f"ERROR: {message}", file=sys.stderr)  # noqa: T201
    sys.exit(1)
