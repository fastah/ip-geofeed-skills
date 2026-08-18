"""Portable analyzer runtime compatibility guard."""

from __future__ import annotations

import sys

MINIMUM_PYTHON = (3, 13)


def require_supported_python(version: tuple[int, int] | None = None) -> None:
    actual = version or sys.version_info[:2]
    if actual < MINIMUM_PYTHON:
        raise RuntimeError(
            f"fastah-geofeed-quality requires Python {MINIMUM_PYTHON[0]}."
            f"{MINIMUM_PYTHON[1]} or newer; found {actual[0]}.{actual[1]}"
        )
