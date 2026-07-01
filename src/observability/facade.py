"""Observability facade for the coordination and domain planes.

This module provides a sanctioned boundary for observability symbols,
allowing consumers to avoid direct dependencies on implementation modules.
"""

from .events import ObservabilityEvent
from .logger import log_event

__all__ = ["ObservabilityEvent", "log_event"]
