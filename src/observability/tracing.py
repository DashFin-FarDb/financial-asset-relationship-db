"""Optional OpenTelemetry OTLP trace exporter for Grafana Tempo.

Remains a zero-overhead no-op unless ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set.
"""

from __future__ import annotations

import contextlib
import logging
import os
import threading
from collections.abc import Iterator, Mapping
from typing import Any

logger = logging.getLogger(__name__)

_TRACING_LOCK = threading.Lock()
_TRACING_STATE: dict[str, Any] = {
    "initialized": False,
    "enabled": False,
    "provider": None,
    "tracer": None,
}


class _NoOpSpan:
    """Lightweight no-op span used when OTLP tracing is disabled."""

    def set_attribute(self, _key: str, _value: Any) -> None:
        """Ignore attribute assignment when tracing is disabled."""

    def record_exception(self, _exception: BaseException) -> None:
        """Ignore exception recording when tracing is disabled."""


_NOOP_SPAN = _NoOpSpan()


def normalize_otlp_traces_endpoint(raw_endpoint: str) -> str:
    """Normalize an OTLP HTTP endpoint to include the ``/v1/traces`` path."""
    cleaned = raw_endpoint.strip().rstrip("/")
    if not cleaned:
        return ""
    if cleaned.endswith("/v1/traces"):
        return cleaned
    return f"{cleaned}/v1/traces"


def setup_tracing(
    *,
    endpoint: str | None = None,
    service_name: str | None = None,
) -> bool:
    """Initialize OTLP HTTP trace export when an endpoint is configured.

    Idempotent and thread-safe. Returns True when OTLP tracing is active,
    False when disabled or when OpenTelemetry dependencies are unavailable.
    """
    with _TRACING_LOCK:
        if _TRACING_STATE["initialized"]:
            return bool(_TRACING_STATE["enabled"])

        raw_endpoint = endpoint if endpoint is not None else os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
        normalized_endpoint = normalize_otlp_traces_endpoint(raw_endpoint)
        if not normalized_endpoint:
            _TRACING_STATE["initialized"] = True
            _TRACING_STATE["enabled"] = False
            return False

        resolved_service = (
            service_name
            if service_name is not None
            else (os.getenv("OTEL_SERVICE_NAME", "fardb-api").strip() or "fardb-api")
        )

        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            resource = Resource.create({"service.name": resolved_service})
            provider = TracerProvider(resource=resource)
            exporter = OTLPSpanExporter(endpoint=normalized_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            tracer = provider.get_tracer("fardb.observability")

            _TRACING_STATE["provider"] = provider
            _TRACING_STATE["tracer"] = tracer
            _TRACING_STATE["enabled"] = True
            _TRACING_STATE["initialized"] = True
            return True
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("OTLP tracing initialization skipped: %s", type(exc).__name__)
            _TRACING_STATE["initialized"] = True
            _TRACING_STATE["enabled"] = False
            return False


def is_tracing_enabled() -> bool:
    """Return whether OTLP tracing is currently active."""
    return bool(_TRACING_STATE["enabled"])


@contextlib.contextmanager
def start_span(
    name: str,
    attributes: Mapping[str, Any] | None = None,
) -> Iterator[Any]:
    """Start an OTLP span if tracing is active, otherwise yield a no-op span."""
    tracer = _TRACING_STATE.get("tracer")
    if tracer is None or not _TRACING_STATE.get("enabled"):
        yield _NOOP_SPAN
        return

    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                if value is not None:
                    span.set_attribute(key, value)
        yield span


def shutdown_tracing() -> None:
    """Flush and shut down the active TracerProvider, resetting state."""
    with _TRACING_LOCK:
        provider = _TRACING_STATE.get("provider")
        if provider is not None:
            try:
                provider.shutdown()
            except Exception:  # pylint: disable=broad-except
                pass
        _TRACING_STATE["provider"] = None
        _TRACING_STATE["tracer"] = None
        _TRACING_STATE["enabled"] = False
        _TRACING_STATE["initialized"] = False
