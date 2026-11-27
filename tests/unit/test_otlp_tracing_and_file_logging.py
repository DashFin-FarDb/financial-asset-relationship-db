"""Unit tests for optional OTLP tracing export and structured JSON file logging."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from src.observability import logging as obs_logging
from src.observability import tracing


def test_normalize_otlp_traces_endpoint() -> None:
    """Endpoint normalization appends /v1/traces once and strips whitespace."""
    assert tracing.normalize_otlp_traces_endpoint("") == ""
    assert tracing.normalize_otlp_traces_endpoint("  http://127.0.0.1:4318/ ") == "http://127.0.0.1:4318/v1/traces"
    assert (
        tracing.normalize_otlp_traces_endpoint("http://127.0.0.1:4318/v1/traces") == "http://127.0.0.1:4318/v1/traces"
    )


def test_setup_tracing_noop_when_endpoint_unset(monkeypatch) -> None:
    """Tracing remains disabled and start_span is a no-op when no endpoint is set."""
    tracing.shutdown_tracing()
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    assert tracing.setup_tracing() is False
    assert tracing.is_tracing_enabled() is False

    with tracing.start_span("noop.span", attributes={"k": "v"}) as span:
        span.set_attribute("extra", 1)


def test_start_span_exports_attributes_when_enabled() -> None:
    """When tracing is active, start_span emits spans with non-null attributes."""
    tracing.shutdown_tracing()
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracing._TRACING_STATE.update(  # pylint: disable=protected-access
        {
            "initialized": True,
            "enabled": True,
            "provider": provider,
            "tracer": provider.get_tracer("test"),
        }
    )
    try:
        with tracing.start_span("db.graph.stage_snapshot", attributes={"db.system": "postgresql", "ignored": None}):
            pass
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "db.graph.stage_snapshot"
        assert spans[0].attributes["db.system"] == "postgresql"
        assert "ignored" not in spans[0].attributes
    finally:
        tracing.shutdown_tracing()
        assert tracing.is_tracing_enabled() is False


def test_setup_logging_attaches_json_file_handler_when_env_set(tmp_path: Path, monkeypatch) -> None:
    """Setting LOG_FILE_PATH writes structured JSON log lines to that file."""
    log_file = tmp_path / "fardb-api.log"
    monkeypatch.setenv("LOG_FILE_PATH", str(log_file))

    prev_initialized = obs_logging._logging_state["initialized"]  # pylint: disable=protected-access
    obs_logging._logging_state["initialized"] = False  # pylint: disable=protected-access
    try:
        obs_logging.setup_logging()
        test_logger = logging.getLogger("test.file_logging")
        test_logger.info("hello_loki_file")
        for h in logging.getLogger().handlers:
            h.flush()
        contents = log_file.read_text(encoding="utf-8").strip().splitlines()
        assert contents
        parsed = json.loads(contents[-1])
        assert parsed["event"] == "hello_loki_file"
        assert "trace_id" in parsed
    finally:
        for h in list(logging.getLogger().handlers):
            if isinstance(h, logging.FileHandler) and Path(h.baseFilename) == log_file:
                h.close()
                logging.getLogger().removeHandler(h)
        obs_logging._logging_state["initialized"] = prev_initialized  # pylint: disable=protected-access
