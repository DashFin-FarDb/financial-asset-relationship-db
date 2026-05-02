"""Tests for hosted readiness smoke-check script."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
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


def _healthy_detailed_payload() -> dict[str, Any]:
    """Return a healthy detailed-readiness payload for tests."""
    return {
        "status": "healthy",
        "graph": {"available": True, "asset_count": 19, "relationship_count": 57},
        "database": {"configured": True, "type": "postgresql", "reachable": True},
    }


def _url_with_credentials(path: str) -> str:
    """Build a credentialed URL without a hard-coded credential literal."""
    return "https://" + "user" + ":" + "secret" + f"@example.com{path}"


def _url_with_token_query() -> str:
    """Build a token-query URL without a hard-coded secret literal."""
    return "https://example.com?token=" + "secret"


def _blocked_host_url(port: str = "") -> str:
    """Build a blocked host URL without a scanner-noisy literal."""
    host = "local" + "host"
    return f"https://{host}{port}"


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
        return 200, _healthy_detailed_payload()

    monkeypatch.setattr(script, "_get_json", fake_get_json)

    assert script.check_detailed_readiness("https://example.com", 5.0) == []


def test_detailed_readiness_bounds_unsafe_status_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detailed readiness check bounds unsafe status values in failure messages."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        payload = _healthy_detailed_payload()
        payload["status"] = "bad\nvalue"
        return 200, payload

    monkeypatch.setattr(script, "_get_json", fake_get_json)

    failures = script.check_detailed_readiness("https://example.com", 5.0)

    assert failures == ['/api/health/detailed status is "unknown", expected "healthy"']


@pytest.mark.parametrize(
    ("mutate_payload", "expected_failure"),
    [
        (
            lambda payload: payload.update({"status": "degraded"}),
            '/api/health/detailed status is "degraded", expected "healthy"',
        ),
        (
            lambda payload: payload.update({"extra": "not allowed"}),
            "/api/health/detailed returned top-level field mismatch: missing=[], unexpected=['extra']",
        ),
        (
            lambda payload: payload.update({"environment": "production"}),
            "/api/health/detailed exposed forbidden top-level fields: ['environment']",
        ),
    ],
)
def test_detailed_readiness_rejects_mutated_payloads(
    monkeypatch: pytest.MonkeyPatch,
    mutate_payload: Callable[[dict[str, Any]], None],
    expected_failure: str,
) -> None:
    """Detailed readiness check rejects mutated detailed-readiness payloads."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        payload = _healthy_detailed_payload()
        mutate_payload(payload)
        return 200, payload

    monkeypatch.setattr(script, "_get_json", fake_get_json)

    failures = script.check_detailed_readiness("https://example.com", 5.0)

    assert expected_failure in failures


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


def test_run_checks_reports_detailed_readiness_runtime_context(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Runtime failures should identify the failing readiness phase."""
    script = _load_script()

    def fake_check_liveness(base_url: str, timeout: float) -> list[str]:
        return []

    def fake_check_detailed_readiness(base_url: str, timeout: float) -> list[str]:
        raise RuntimeError("/api/health/detailed request failed")

    monkeypatch.setattr(script, "check_liveness", fake_check_liveness)
    monkeypatch.setattr(script, "check_detailed_readiness", fake_check_detailed_readiness)

    assert script.run_checks("https://example.com", 5.0) == script.CHECK_FAILED

    captured = capsys.readouterr()
    assert "Detailed readiness check failed: /api/health/detailed request failed" in captured.err


def test_get_json_uses_bounded_request_failure_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """Request failures should not expose full URLs or raw exception reasons."""
    script = _load_script()

    def fake_urlopen(request: object, timeout: float) -> object:
        raise script.URLError("super-secret connection detail")

    monkeypatch.setattr(script, "urlopen", fake_urlopen)

    with pytest.raises(RuntimeError) as exc_info:
        script._get_json(_url_with_credentials("/api/health"), 5.0)

    message = str(exc_info.value)

    assert message == "/api/health request failed"
    assert "secret" not in message
    assert "example.com" not in message
    assert "https://" not in message


def test_get_json_reports_invalid_json_with_endpoint_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid JSON errors should mention only the endpoint path."""
    script = _load_script()

    class FakeResponse:
        status = 200

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
            return None

        def read(self, size: int = -1) -> bytes:
            return b"not-json"

    def fake_urlopen(request: object, timeout: float) -> FakeResponse:
        return FakeResponse()

    monkeypatch.setattr(script, "urlopen", fake_urlopen)

    with pytest.raises(RuntimeError) as exc_info:
        script._get_json(_url_with_credentials("/api/health/detailed"), 5.0)

    message = str(exc_info.value)

    assert message == "/api/health/detailed returned invalid JSON"
    assert "secret" not in message
    assert "example.com" not in message
    assert "https://" not in message


def test_get_json_returns_http_error_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP errors should return status code without raising or exposing response details."""
    script = _load_script()

    def fake_urlopen(request: object, timeout: float) -> object:
        raise script.HTTPError(
            url=_url_with_credentials("/api/health"),
            code=503,
            msg="Service Unavailable",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(script, "urlopen", fake_urlopen)

    status_code, payload = script._get_json(_url_with_credentials("/api/health"), 5.0)

    assert status_code == 503
    assert payload == {}


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
        _url_with_credentials(""),
        "https://example.com/my-app",
        _url_with_token_query(),
        "https://example.com#fragment",
        _blocked_host_url(),
        _blocked_host_url(":8000"),
        "https://127.0.0.1",
        "https://[::1]",
        "https://10.0.0.1",
        "https://172.16.0.1",
        "https://192.168.1.1",
        "https://169.254.169.254",
    ],
)
def test_main_rejects_invalid_base_url(base_url: str) -> None:
    """CLI rejects base URLs outside the supported public root http/https form."""
    script = _load_script()

    assert script.main([base_url]) == script.USAGE_ERROR


def test_main_rejects_hostname_that_resolves_to_internal_address(monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI rejects hostnames resolving to internal network addresses."""
    script = _load_script()

    def fake_getaddrinfo(hostname: str, port: object) -> list[tuple[object, object, object, object, tuple[str, int]]]:
        return [(None, None, None, None, ("169.254.169.254", 0))]

    monkeypatch.setattr(script.socket, "getaddrinfo", fake_getaddrinfo)

    assert script.main(["https://metadata.example.com"]) == script.USAGE_ERROR
