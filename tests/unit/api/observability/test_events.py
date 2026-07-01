"""Unit tests for ObservabilityEvent schema."""

from src.observability.events import ObservabilityEvent


def test_observability_event_to_extra():
    """Test that ObservabilityEvent.to_extra() returns the expected dictionary."""
    event = ObservabilityEvent(
        event="test_event",
        message="test message",
        metadata={"key": "value"},
    )
    extra = event.to_extra()
    # message is excluded from extra to avoid collisions with stdlib logging
    assert extra == {
        "event": "test_event",
        "metadata": {"key": "value"},
    }


def test_observability_event_default_metadata():
    """Test that ObservabilityEvent defaults to an empty metadata dictionary."""
    event = ObservabilityEvent(event="test_event", message="test message")
    assert event.metadata == {}
    assert event.to_extra()["metadata"] == {}
