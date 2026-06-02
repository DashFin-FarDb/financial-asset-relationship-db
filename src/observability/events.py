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
        """
        Convert the event to a dictionary suitable for logging 'extra'.

        Note: We exclude 'message' from the extra dict because standard
        library logging does not allow overwriting the 'message' attribute.
        The message is instead passed as the primary log argument.

        Returns:
        A dictionary containing the event name and metadata.
        """
        return {
            "event": self.event,
            "metadata": self.metadata,
        }
