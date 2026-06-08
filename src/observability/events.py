"""Observability event schemas and structures."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ObservabilityEvent:
    """
    Structured domain event for observability.

    Attributes:
        event: The unique identifier for the type of event (e.g., 'graph_rebuild_requested').
        message: A human-readable description of the event.
        metadata: Domain-specific contextual data (e.g., job_id, user_ref).
    """

    event: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_extra(self) -> dict[str, Any]:
        """Produce a dictionary for use as logging `extra` with event and metadata.

        This dictionary includes only the `event` and `metadata` fields and does
        not include the human-readable `message`.

        Returns:
            dict[str, Any]: A mapping with keys `"event"` (the event identifier) and `"metadata"` (the event metadata).
        """
        return {
            "event": self.event,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class SLOBreachEvent(ObservabilityEvent):
    """
    Structured domain event specifically for SLO breaches.

    Inherits from ObservabilityEvent to ensure consistent log formatting while
    semantically identifying the event as a critical breach.
    """
