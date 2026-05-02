"""Tests for hosted readiness smoke-check script."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_hosted_readiness.py"


def _load_script() -> ModuleType:
    """Load the smoke-check script as a module for unit testing."""
    spec = importlib.util.spec_from_file_location("check_hosted_readiness", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_url_handles_trailing_slash() -> None:
    """URL builder should handle base URLs with and without trailing slashes."""
    script = _load_script()

    assert script._build_url("https://example.com", "/api/health") == "https://example.com/api/health"
    assert script._build_url("https://example.com/", "/api/health") == "https://example.com/api/health"


def test_liveness_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Liveness check accepts the public healthy contract."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        return 200, {"status": "healthy", "graph_initialized": True}

    monkeypatch.setattr(script, "_get_json", fake_get_json)

    assert script.check_liveness("https://example.com", 5.0) == []


def test_liveness_rejects_unhealthy_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """Liveness check rejects non-healthy status."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        return 200, {"status": "degraded", "graph_initialized": True}

    monkeypatch.setattr(script, "_get_json", fake_get_json)

    failures = script.check_liveness("https://example.com", 5.0)

    assert failures == ['/api/health did not return status "healthy"']


def test_liveness_rejects_missing_graph_initialized(monkeypatch: pytest.MonkeyPatch) -> None:
    """Liveness check rejects missing graph initialization flag."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        return 200, {"status": "healthy"}

    monkeypatch.setattr(script, "_get_json", fake_get_json)

    failures = script.check_liveness("https://example.com", 5.0)

    assert failures == ["/api/health did not report graph_initialized true"]


def test_detailed_readiness_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detailed readiness check accepts a bounded healthy payload."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        return 200, {
            "status": "healthy",
            "graph": {"available": True, "asset_count": 19, "relationship_count": 57},
            "database": {"configured": True, "type": "postgresql", "reachable": True},
        }

    monkeypatch.setattr(script, "_get_json", fake_get_json)

    assert script.check_detailed_readiness("https://example.com", 5.0) == []


def test_detailed_readiness_rejects_degraded_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detailed readiness check parses JSON status instead of trusting HTTP 200."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        return 200, {
            "status": "degraded",
            "graph": {"available": True, "asset_count": 19, "relationship_count": 57},
            "database": {"configured": True, "type": "postgresql", "reachable": False},
        }

    monkeypatch.setattr(script, "_get_json", fake_get_json)

    failures = script.check_detailed_readiness("https://example.com", 5.0)

    assert failures == ['/api/health/detailed status is "degraded", expected "healthy"']


def test_detailed_readiness_rejects_unexpected_top_level_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detailed readiness check rejects fields outside the public top-level contract."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        return 200, {
            "status": "healthy",
            "graph": {"available": True, "asset_count": 19, "relationship_count": 57},
            "database": {"configured": True, "type": "postgresql", "reachable": True},
            "extra": "not allowed",
        }

    monkeypatch.setattr(script, "_get_json", fake_get_json)

    failures = script.check_detailed_readiness("https://example.com", 5.0)

    assert "/api/health/detailed returned top-level field mismatch: missing=[], unexpected=['extra']" in failures


def test_detailed_readiness_rejects_missing_top_level_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detailed readiness check reports missing required top-level fields."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        return 200, {"status": "healthy"}

    monkeypatch.setattr(script, "_get_json", fake_get_json)

    failures = script.check_detailed_readiness("https://example.com", 5.0)

    assert (
        "/api/health/detailed returned top-level field mismatch: missing=['database', 'graph'], unexpected=[]"
    ) in failures


def test_detailed_readiness_rejects_forbidden_top_level_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detailed readiness check rejects obvious sensitive top-level fields."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        return 200, {
            "status": "healthy",
            "graph": {"available": True, "asset_count": 19, "relationship_count": 57},
            "database": {"configured": True, "type": "postgresql", "reachable": True},
            "environment": "production",
        }

    monkeypatch.setattr(script, "_get_json", fake_get_json)

    failures = script.check_detailed_readiness("https://example.com", 5.0)

    assert (
        "/api/health/detailed returned top-level field mismatch: missing=[], unexpected=['environment']"
    ) in failures
    assert "/api/health/detailed exposed forbidden top-level fields: ['environment']" in failures


def test_detailed_readiness_rejects_non_object_graph_or_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detailed readiness check rejects non-object graph/database fields."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        return 200, {
            "status": "healthy",
            "graph": [],
            "database": [],
        }

    monkeypatch.setattr(script, "_get_json", fake_get_json)

    failures = script.check_detailed_readiness("https://example.com", 5.0)

    assert "/api/health/detailed graph field is not an object" in failures
    assert "/api/health/detailed database field is not an object" in failures


def test_run_checks_returns_failure_on_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runtime request errors should produce a failed smoke check."""
    script = _load_script()

    def fake_check_liveness(base_url: str, timeout: float) -> list[str]:
        raise RuntimeError("request failed")

    monkeypatch.setattr(script, "check_liveness", fake_check_liveness)

    assert script.run_checks("https://example.com", 5.0) == script.CHECK_FAILED


def test_main_rejects_non_positive_timeout() -> None:
    """CLI rejects invalid timeout values."""
    script = _load_script()

    assert script.main(["https://example.com", "--timeout", "0"]) == script.USAGE_ERROR


@pytest.mark.parametrize(
    "base_url",
    [
        "example.com",
        "ftp://example.com",
        "https://",
        "https://user:secret@example.com",
        "https://example.com/my-app",
        "https://example.com?token=secret",
        "https://example.com#fragment",
    ],
)
def test_main_rejects_invalid_base_url(base_url: str) -> None:
    """CLI rejects base URLs outside the supported root http/https form."""
    script = _load_script()

    assert script.main([base_url]) == script.USAGE_ERROR
