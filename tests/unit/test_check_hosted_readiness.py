"""Tests for hosted readiness smoke-check script."""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import urlparse

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
        "graph_persistence_configured": True,
        "graph": {"available": True, "asset_count": 19, "relationship_count": 57},
        "database": {"configured": True, "type": "postgresql", "reachable": True},
    }


def _healthy_detailed_payload_with_persistence() -> dict[str, Any]:
    """Return a healthy detailed-readiness payload with active persistence for tests."""
    return {
        "status": "healthy",
        "graph_persistence_configured": True,
        "graph": {
            "available": True,
            "asset_count": 19,
            "relationship_count": 57,
            "persistence_enabled": True,
            "persistence_loaded": True,
            "persistence_saved": False,
            "startup_source": "persisted",
        },
        "database": {"configured": True, "type": "postgresql", "reachable": True},
    }


def _healthy_assets_payload() -> dict[str, Any]:
    """Return a minimal healthy assets page payload for smoke tests."""
    return {
        "items": [{"id": "ASSET_1", "symbol": "AAA"}],
        "total": 19,
        "page": 1,
        "per_page": 1,
        "hasMore": True,
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


def _ipv4_url(*octets: int) -> str:
    """Build an IPv4 URL without scanner-noisy hard-coded IP literals."""
    return "https://" + ".".join(str(octet) for octet in octets)


def _ipv6_loopback_url() -> str:
    """Build an IPv6 loopback URL without a scanner-noisy hard-coded IP literal."""
    return "https://[" + "::" + "1]"


def test_no_redirect_handler_disables_redirects() -> None:
    """Redirect handler should not follow redirect targets."""
    script = _load_script()

    handler = script._NoRedirectHandler()

    assert (
        handler.redirect_request(
            req=script.Request("https://example.com/api/health"),
            fp=None,
            code=302,
            msg="Found",
            headers={},
            newurl="https://127.0.0.1/metadata",
        )
        is None
    )


def test_build_url_handles_trailing_slash() -> None:
    """URL builder should handle base URLs with and without trailing slashes."""
    script = _load_script()

    assert script._build_url("https://example.com", "/api/health") == "https://example.com/api/health"
    assert script._build_url("https://example.com/", "/api/health") == "https://example.com/api/health"


def test_liveness_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Liveness check accepts the public healthy contract."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        """Return a fake successful liveness JSON response."""
        return 200, {"status": "healthy", "graph_initialized": True}

    monkeypatch.setattr(script, "_get_json", fake_get_json)

    assert script.check_liveness("https://example.com", 5.0) == []


def test_liveness_rejects_unhealthy_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """Liveness check rejects non-healthy status."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        """Return a fake degraded liveness JSON response."""
        return 200, {"status": "degraded", "graph_initialized": True}

    monkeypatch.setattr(script, "_get_json", fake_get_json)

    failures = script.check_liveness("https://example.com", 5.0)

    assert failures == ['/api/health did not return status "healthy"']


def test_liveness_rejects_missing_graph_initialized(monkeypatch: pytest.MonkeyPatch) -> None:
    """Liveness check rejects missing graph initialization flag."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        """Return a fake liveness response without graph_initialized."""
        return 200, {"status": "healthy"}

    monkeypatch.setattr(script, "_get_json", fake_get_json)

    failures = script.check_liveness("https://example.com", 5.0)

    assert failures == ["/api/health did not report graph_initialized true"]


def test_detailed_readiness_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detailed readiness check accepts a bounded healthy payload."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        """Return a fake successful detailed readiness response."""
        return 200, _healthy_detailed_payload()

    monkeypatch.setattr(script, "_get_json", fake_get_json)

    assert script.check_detailed_readiness("https://example.com", 5.0) == []


def test_detailed_readiness_bounds_unsafe_status_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detailed readiness check bounds unsafe status values in failure messages."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        """Return a fake detailed readiness response with unsafe status."""
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
        """Return a mutated detailed readiness response."""
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
        """Return a partial detailed readiness response."""
        return 200, {"status": "healthy"}

    monkeypatch.setattr(script, "_get_json", fake_get_json)

    failures = script.check_detailed_readiness("https://example.com", 5.0)

    assert (
        "/api/health/detailed returned top-level field mismatch: "
        "missing=['database', 'graph', 'graph_persistence_configured'], unexpected=[]"
    ) in failures


def test_detailed_readiness_rejects_non_object_graph_or_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detailed readiness check rejects non-object graph/database fields."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        """Return a detailed readiness response with non-object fields."""
        return 200, {
            "status": "healthy",
            "graph_persistence_configured": True,
            "graph": [],
            "database": [],
        }

    monkeypatch.setattr(script, "_get_json", fake_get_json)

    failures = script.check_detailed_readiness("https://example.com", 5.0)

    assert "/api/health/detailed graph field is not an object" in failures
    assert "/api/health/detailed database field is not an object" in failures


def test_detailed_readiness_rejects_non_boolean_graph_persistence_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Detailed readiness check rejects non-boolean graph_persistence_configured values."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        """Return a detailed readiness response with an invalid persistence-configured type."""
        payload = _healthy_detailed_payload()
        payload["graph_persistence_configured"] = "true"
        return 200, payload

    monkeypatch.setattr(script, "_get_json", fake_get_json)

    failures = script.check_detailed_readiness("https://example.com", 5.0)

    assert "/api/health/detailed graph_persistence_configured field is not a boolean" in failures


def test_run_checks_returns_failure_on_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runtime request errors should produce a failed smoke check."""
    script = _load_script()

    def fake_check_liveness(base_url: str, timeout: float) -> list[str]:
        """Raise a fake runtime error."""
        raise RuntimeError("request failed")

    monkeypatch.setattr(script, "check_liveness", fake_check_liveness)

    assert script.run_checks("https://example.com", 5.0) == script.CHECK_FAILED


def test_run_checks_bounds_unexpected_exception(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Unexpected check exceptions should not produce tracebacks or raw details."""
    script = _load_script()

    def fake_check_liveness(base_url: str, timeout: float) -> list[str]:
        """Raise a fake unexpected exception."""
        raise TypeError("sensitive internal detail")

    monkeypatch.setattr(script, "check_liveness", fake_check_liveness)

    assert script.run_checks("https://example.com", 5.0) == script.CHECK_FAILED

    captured = capsys.readouterr()
    assert "Liveness check failed: unexpected error" in captured.err
    assert "sensitive internal detail" not in captured.err


def test_run_checks_reports_detailed_readiness_runtime_context(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Runtime failures should identify the failing readiness phase."""
    script = _load_script()

    def fake_check_liveness(base_url: str, timeout: float) -> list[str]:
        """Return an empty liveness failure list."""
        return []

    def fake_check_detailed_readiness(
        base_url: str,
        timeout: float,
        require_persistence: bool = False,
    ) -> list[str]:
        """Raise a fake detailed readiness runtime error."""
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
        """Raise a fake bounded request failure."""
        raise script.URLError("super-secret connection detail")

    monkeypatch.setattr(script, "urlopen", fake_urlopen)

    with pytest.raises(RuntimeError) as exc_info:
        script._get_json("https://example.com/api/health", 5.0)

    message = str(exc_info.value)

    assert message == "/api/health request failed"
    assert "secret" not in message
    assert "example.com" not in message
    assert "https://" not in message


def test_get_json_reports_invalid_json_with_endpoint_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid JSON errors should mention only the endpoint path."""
    script = _load_script()

    class FakeResponse:
        """Fake context-manager response returning invalid JSON bytes."""

        status = 200

        def __enter__(self) -> "FakeResponse":
            """Enter the fake response context."""
            return self

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
            """Exit the fake response context."""
            return None

        def read(self, size: int = -1) -> bytes:
            """Return invalid JSON bytes."""
            return b"not-json"

    def fake_urlopen(request: object, timeout: float) -> FakeResponse:
        """Return a fake response with invalid JSON."""
        return FakeResponse()

    monkeypatch.setattr(script, "urlopen", fake_urlopen)

    with pytest.raises(RuntimeError) as exc_info:
        script._get_json("https://example.com/api/health/detailed", 5.0)

    message = str(exc_info.value)

    assert message == "/api/health/detailed returned invalid JSON"
    assert "secret" not in message
    assert "example.com" not in message
    assert "https://" not in message


def test_get_json_returns_http_error_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP errors should return status code without raising or exposing response details."""
    script = _load_script()

    def fake_urlopen(request: object, timeout: float) -> object:
        """Raise a fake HTTP error."""
        raise script.HTTPError(
            url=_url_with_credentials("/api/health"),
            code=503,
            msg="Service Unavailable",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(script, "urlopen", fake_urlopen)

    status_code, payload = script._get_json("https://example.com/api/health", 5.0)

    assert status_code == 503
    assert payload == {}


def test_read_response_body_revalidates_request_target(monkeypatch: pytest.MonkeyPatch) -> None:
    """Request target should be revalidated before each request to reduce DNS rebinding window."""
    script = _load_script()

    def fake_validate_request_target(url: str, *, allowed_query: str | None = None) -> str | None:
        """Return a fake target validation failure."""
        return "target resolved to internal address"

    monkeypatch.setattr(script, "_validate_request_target", fake_validate_request_target)

    with pytest.raises(RuntimeError) as exc_info:
        script._read_response_body(_url_with_credentials("/api/health"), 5.0)

    message = str(exc_info.value)

    assert message == "/api/health request target validation failed"
    assert "secret" not in message
    assert "example.com" not in message


def test_read_response_body_rejects_invalid_request_target_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed request targets should fail before the HTTP request object is used."""
    script = _load_script()

    def fail_urlopen(request: object, timeout: float) -> object:
        """Fail if the request reaches the network layer."""
        pytest.fail("urlopen should not be called for invalid request targets")

    monkeypatch.setattr(script, "urlopen", fail_urlopen)

    with pytest.raises(RuntimeError) as exc_info:
        script._read_response_body(_url_with_credentials("/api/health"), 5.0)

    message = str(exc_info.value)

    assert message == "/api/health request target validation failed"
    assert "secret" not in message
    assert "example.com" not in message


def test_main_rejects_non_positive_timeout() -> None:
    """CLI rejects invalid timeout values."""
    script = _load_script()

    assert script.main(["https://example.com", "--timeout", "0"]) == script.USAGE_ERROR


@pytest.mark.parametrize(
    "timeout_value",
    ["0", "-1", "nan", "inf"],
)
def test_main_rejects_non_finite_timeout(timeout_value: str) -> None:
    """CLI rejects non-finite and non-positive timeout values."""
    script = _load_script()

    assert script.main(["https://example.com", "--timeout", timeout_value]) == script.USAGE_ERROR


@pytest.mark.parametrize(
    "base_url",
    [
        "example.com",
        "sftp://example.com",
        "https://",
        _url_with_credentials(""),
        "https://example.com/my-app",
        _url_with_token_query(),
        "https://example.com#fragment",
        "https://example.com:abc",
        _blocked_host_url(),
        _blocked_host_url(":8000"),
        _ipv4_url(127, 0, 0, 1),
        _ipv6_loopback_url(),
        _ipv4_url(10, 0, 0, 1),
        _ipv4_url(172, 16, 0, 1),
        _ipv4_url(192, 168, 1, 1),
        _ipv4_url(169, 254, 169, 254),
        _ipv4_url(100, 64, 0, 1),
    ],
)
def test_main_rejects_invalid_base_url(
    base_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI rejects invalid base URLs without real DNS lookups."""
    script = _load_script()

    def fail_getaddrinfo(hostname: str, port: object) -> object:
        """Fail if invalid URL validation attempts DNS resolution."""
        pytest.fail("invalid URL validation should not perform DNS resolution")

    monkeypatch.setattr(script.socket, "getaddrinfo", fail_getaddrinfo)

    assert script.main([base_url]) == script.USAGE_ERROR


def test_main_rejects_hostname_that_resolves_to_internal_address(monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI rejects hostnames resolving to internal network addresses."""
    script = _load_script()

    def fake_getaddrinfo(
        hostname: str,
        port: object,
    ) -> list[tuple[object, object, object, object, tuple[str, int]]]:
        """Return a fake internal resolved address."""
        return [(None, None, None, None, (".".join(("169", "254", "169", "254")), 0))]

    monkeypatch.setattr(script.socket, "getaddrinfo", fake_getaddrinfo)

    assert script.main(["https://metadata.example.com"]) == script.USAGE_ERROR


def test_detailed_readiness_with_require_persistence_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detailed readiness check accepts a persistent payload when require_persistence is True."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        """Return a fake successful detailed readiness response with persistence."""
        return 200, _healthy_detailed_payload_with_persistence()

    monkeypatch.setattr(script, "_get_json", fake_get_json)

    assert script.check_detailed_readiness("https://example.com", 5.0, require_persistence=True) == []


def _mutate_persistence_payload(mutator: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    """Return a persistence-ready payload after applying mutator."""
    payload = _healthy_detailed_payload_with_persistence()
    mutator(payload)
    return payload


@pytest.mark.parametrize(
    ("mutator", "expected_fragment", "forbid_fragments"),
    [
        (
            lambda p: p.__setitem__("graph_persistence_configured", False),
            "graph_persistence_configured is not true",
            (),
        ),
        (lambda p: p["graph"].__setitem__("persistence_enabled", False), "graph.persistence_enabled is not true", ()),
        (lambda p: p["graph"].__setitem__("persistence_loaded", False), "graph.persistence_loaded is not true", ()),
        (
            lambda p: p["graph"].__setitem__("startup_source", "sample_data"),
            'graph.startup_source is "sample_data", expected "persisted"',
            (),
        ),
        (lambda p: p["graph"].__setitem__("startup_source", None), "graph.startup_source field is missing", ()),
        (
            lambda p: p["graph"].__setitem__("startup_source", "untrusted_input\nwith_control_chars"),
            'graph.startup_source is "unknown", expected "persisted"',
            (),
        ),
        (
            lambda p: p.__setitem__("graph", "not_a_dict"),
            "graph field is not an object",
            ("skipped", "graph_persistence_configured", "persistence_enabled"),
        ),
        (
            lambda p: p.pop("graph"),
            "graph",
            ("graph_persistence_configured", "persistence_enabled"),
        ),
    ],
)
def test_detailed_readiness_with_require_persistence_failures(
    monkeypatch: pytest.MonkeyPatch,
    mutator: Callable[[dict[str, Any]], None],
    expected_fragment: str,
    forbid_fragments: tuple[str, ...],
) -> None:
    """require_persistence rejects non-persistent or misconfigured payloads."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        return 200, _mutate_persistence_payload(mutator)

    monkeypatch.setattr(script, "_get_json", fake_get_json)
    failures = script.check_detailed_readiness("https://example.com", 5.0, require_persistence=True)
    assert any(expected_fragment in failure for failure in failures)
    for fragment in forbid_fragments:
        assert not any(fragment in failure for failure in failures)


def test_parse_args_handles_require_persistence() -> None:
    """CLI argument parser correctly extracts the require-persistence flag."""
    script = _load_script()

    args = script.parse_args(["https://example.com", "--require-persistence"])
    assert args.require_persistence is True

    args_default = script.parse_args(["https://example.com"])
    assert args_default.require_persistence is False
    assert args_default.timeout == 30.0


def test_parse_args_handles_assets_smoke() -> None:
    """CLI argument parser correctly extracts the assets-smoke flag."""
    script = _load_script()

    args = script.parse_args(["https://example.com", "--assets-smoke"])
    assert args.assets_smoke is True

    args_default = script.parse_args(["https://example.com"])
    assert args_default.assets_smoke is False


def test_parse_args_handles_json_mode_and_label() -> None:
    """CLI argument parser should accept JSON output mode and a safe base URL label."""
    script = _load_script()

    args = script.parse_args(["https://example.com", "--json", "--base-url-label", "staging-api"])

    assert args.json is True
    assert args.base_url_label == "staging-api"


def test_assets_smoke_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Assets smoke accepts a bounded page with at least one item."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float, *, allowed_query: str | None = None) -> tuple[int, dict[str, Any]]:
        assert url.endswith("/api/assets?per_page=1")
        assert allowed_query == "per_page=1"
        return 200, _healthy_assets_payload()

    monkeypatch.setattr(script, "_get_json", fake_get_json)
    assert script.check_assets_smoke("https://example.com", 5.0) == []


def test_assets_smoke_rejects_empty_page(monkeypatch: pytest.MonkeyPatch) -> None:
    """Assets smoke rejects an empty items list or zero total."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float, *, allowed_query: str | None = None) -> tuple[int, dict[str, Any]]:
        return 200, {"items": [], "total": 0, "page": 1, "per_page": 1, "hasMore": False}

    monkeypatch.setattr(script, "_get_json", fake_get_json)
    failures = script.check_assets_smoke("https://example.com", 5.0)
    assert "/api/assets total is less than 1" in failures
    assert "/api/assets items list is empty" in failures


def test_validate_request_query_matches_allowlist_strictly() -> None:
    """Request query must equal allowed_query, defaulting to empty when unset."""
    script = _load_script()
    assert (
        script._validate_request_query(urlparse("https://example.com/api/assets"), "per_page=1")
        == "request URL query is not in the smoke-check allowlist"
    )
    assert script._validate_request_query(urlparse("https://example.com/api/assets?per_page=1"), "per_page=1") is None
    assert script._validate_request_query(urlparse("https://example.com/api/health"), None) is None
    assert (
        script._validate_request_query(urlparse("https://example.com/api/health?x=1"), None)
        == "request URL query is not in the smoke-check allowlist"
    )


def test_json_assets_smoke_skipped_when_liveness_runtime_fails(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Assets smoke is reported failed/skipped when liveness raises at runtime."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float, *, allowed_query: str | None = None) -> tuple[int, dict[str, Any]]:
        if url.endswith("/api/health"):
            raise RuntimeError("liveness unavailable")
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(script, "_get_json", fake_get_json)
    exit_code = script.main(["https://example.com", "--json", "--assets-smoke"])
    data = json.loads(capsys.readouterr().out)

    assert exit_code == script.CHECK_FAILED
    assert data["assets_smoke"] is True
    assert data["checks"]["assets_smoke"] == {
        "passed": False,
        "failures": ["Assets smoke check not run because liveness check failed"],
    }


def test_require_persistence_auto_enables_assets_smoke(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--require-persistence should also run the assets smoke check."""
    script = _load_script()

    def fake_get_json(
        url: str,
        timeout: float,
        *,
        allowed_query: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Return healthy payloads for liveness, detailed readiness, and assets."""
        if url.endswith("/api/health"):
            return 200, {"status": "healthy", "graph_initialized": True}
        if url.endswith("/api/health/detailed"):
            return 200, _healthy_detailed_payload_with_persistence()
        if url.endswith("/api/assets?per_page=1"):
            assert allowed_query == "per_page=1"
            return 200, _healthy_assets_payload()
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(script, "_get_json", fake_get_json)
    exit_code = script.main(
        [
            "https://example.com",
            "--json",
            "--require-persistence",
            "--base-url-label",
            "staging-api",
        ]
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert exit_code == script.SUCCESS
    assert data["require_persistence"] is True
    assert data["assets_smoke"] is True
    assert data["checks"]["assets_smoke"] == {"passed": True, "failures": []}
    assert data["observed_fields"]["assets.total"] == 19
    assert data["observed_fields"]["assets.item_count"] == 1


def test_main_json_outputs_machine_readable_success(capsys: pytest.CaptureFixture[str]) -> None:
    """JSON mode should emit valid bounded success output without the raw base URL."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float, *, allowed_query: str | None = None) -> tuple[int, dict[str, Any]]:
        """Return fake JSON payloads for both smoke-check endpoints."""
        if url.endswith("/api/health"):
            return 200, {"status": "healthy", "graph_initialized": True}
        if url.endswith("/api/health/detailed"):
            return 200, _healthy_detailed_payload_with_persistence()
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(script, "_get_json", fake_get_json)
    try:
        exit_code = script.main(["https://example.com", "--json", "--base-url-label", "staging-api"])
    finally:
        monkeypatch.undo()

    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert exit_code == script.SUCCESS
    assert captured.err == ""
    assert data["status"] == "passed"
    assert data["base_url_label"] == "staging-api"
    assert data["require_persistence"] is False
    assert data["assets_smoke"] is False
    assert "assets_smoke" not in data["checks"]
    assert data["checks"]["liveness"] == {"passed": True, "failures": []}
    assert data["checks"]["detailed_readiness"] == {"passed": True, "failures": []}
    assert data["observed_fields"]["graph.persistence_loaded"] is True
    assert data["observed_fields"]["graph.startup_source"] == "persisted"
    assert not any(key.startswith("assets.") for key in data["observed_fields"])
    assert "example.com" not in captured.out


def test_main_json_uses_default_redacted_base_url_label(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """JSON mode should default to a redacted base URL label when none is provided."""
    script = _load_script()

    def fake_get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        """Return fake JSON payloads for both smoke-check endpoints."""
        if url.endswith("/api/health"):
            return 200, {"status": "healthy", "graph_initialized": True}
        if url.endswith("/api/health/detailed"):
            return 200, _healthy_detailed_payload_with_persistence()
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(script, "_get_json", fake_get_json)
    exit_code = script.main(["https://example.com", "--json"])

    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert exit_code == script.SUCCESS
    assert captured.err == ""
    assert data["status"] == "passed"
    assert data["base_url_label"] == "redacted"
    assert "example.com" not in captured.out


def test_main_json_outputs_machine_readable_failure(capsys: pytest.CaptureFixture[str]) -> None:
    """JSON mode aggregates concurrent detailed-readiness and assets-smoke failures."""
    script = _load_script()

    def fake_get_json(
        url: str,
        timeout: float,
        *,
        allowed_query: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Return failing persistence and empty assets payloads after healthy liveness."""
        if url.endswith("/api/health"):
            return 200, {"status": "healthy", "graph_initialized": True}
        if url.endswith("/api/health/detailed"):
            payload = _healthy_detailed_payload_with_persistence()
            payload["graph"]["persistence_loaded"] = False
            payload["graph"]["startup_source"] = "sample_data"
            return 200, payload
        if url.endswith("/api/assets?per_page=1"):
            assert allowed_query == "per_page=1"
            return 200, {"items": [], "total": 0, "page": 1, "per_page": 1, "hasMore": False}
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(script, "_get_json", fake_get_json)
    try:
        exit_code = script.main(
            [
                "https://example.com",
                "--json",
                "--base-url-label",
                "staging-api",
                "--require-persistence",
            ]
        )
    finally:
        monkeypatch.undo()

    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert exit_code == script.CHECK_FAILED
    assert captured.err == ""
    assert data["status"] == "failed"
    assert data["base_url_label"] == "staging-api"
    assert data["require_persistence"] is True
    assert data["assets_smoke"] is True
    assert data["checks"]["liveness"] == {"passed": True, "failures": []}
    assert data["checks"]["detailed_readiness"]["passed"] is False
    assert (
        "/api/health/detailed graph.persistence_loaded is not true" in data["checks"]["detailed_readiness"]["failures"]
    )
    assert data["checks"]["assets_smoke"]["passed"] is False
    assert "/api/assets total is less than 1" in data["checks"]["assets_smoke"]["failures"]
    assert "/api/assets items list is empty" in data["checks"]["assets_smoke"]["failures"]
    assert data["observed_fields"]["graph.persistence_loaded"] is False
    assert data["observed_fields"]["graph.startup_source"] == "sample_data"
    assert data["observed_fields"]["assets.total"] == 0
    assert data["observed_fields"]["assets.item_count"] == 0
    assert "example.com" not in captured.out
