"""Compatibility helpers for enum types across supported Python versions."""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """Compatibility stand-in for :class:`enum.StrEnum` on Python 3.10+."""


__all__ = ["StrEnum"]
