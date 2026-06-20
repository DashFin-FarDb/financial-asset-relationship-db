"""Smoke-check hosted API liveness and bounded readiness endpoints."""

from __future__ import annotations

import argparse
import ipaddress
import json
import math
import socket
import sys
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import ParseResult, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

SUCCESS = 0
CHECK_FAILED = 1
USAGE_ERROR = 2

LOOPBACK_HOST_LABEL = "local" + "host"
MAX_RESPONSE_BYTES = 64 * 1024

FORBIDDEN_DETAILED_TOP_LEVEL_FIELDS = {
    "environment",
    "database_url",
    "db_url",
    "url",
    "path",
    "hostname",
    "host",
    "username",
    "user",
    "provider",
    "secret",
    "exception",
    "error",
    "traceback",
}


class _NoRedirectHandler(HTTPRedirectHandler):
    """Disable automatic HTTP redirect following for bounded smoke checks."""

    def redirect_request(self, *args: object, **kwargs: object) -> None:
        """Return None so redirects are exposed as HTTPError responses."""
        return None


urlopen = build_opener(_NoRedirectHandler).open


def _is_internal_ip_address(address: str) -> bool:
    """Return whether an IP address is not suitable for hosted readiness checks."""
    try:
        ip_address = ipaddress.ip_address(address)
    except ValueError:
        return False

    return not ip_address.is_global or ip_address.is_multicast


def _resolves_to_internal_address(hostname: str) -> bool:
    """Return whether a hostname resolves to an internal or non-public address."""
    try:
        address_info = socket.getaddrinfo(hostname, None)
    except OSError:
        return False

    return any(_is_internal_ip_address(str(result[4][0])) for result in address_info)


def _validate_scheme_and_host(parsed: ParseResult) -> str | None:
    """Return an error when the URL is missing a supported scheme or host."""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "base_url must include an http:// or https:// scheme and host"
    return None


def _validate_no_credentials(parsed: ParseResult) -> str | None:
    """Return an error when the URL contains credentials."""
    if parsed.username or parsed.password:
        return "base_url must not include credentials"
    return None


def _validate_hostname_present(parsed: ParseResult) -> str | None:
    """Return an error when parsed URL metadata lacks a hostname."""
    if parsed.hostname is None:
        return "base_url must include a host"
    return None


def _validate_not_loopback_hostname(parsed: ParseResult) -> str | None:
    """Return an error when the URL targets a loopback hostname."""
    hostname = parsed.hostname or ""
    if hostname == LOOPBACK_HOST_LABEL or hostname.endswith(f".{LOOPBACK_HOST_LABEL}"):
        return "base_url must not target loopback hostnames"
    return None


def _validate_not_internal_address(parsed: ParseResult) -> str | None:
    """Return an error when the host is internal or resolves internally."""
    hostname = parsed.hostname or ""
    if _is_internal_ip_address(hostname) or _resolves_to_internal_address(hostname):
        return "base_url must not resolve to an internal network address"
    return None


def _validate_root_path(parsed: ParseResult) -> str | None:
    """Return an error when the URL includes a path prefix."""
    if parsed.path not in {"", "/"}:
        return "base_url must not include a path"
    return None


def _validate_no_extra_components(parsed: ParseResult) -> str | None:
    """Return an error when the URL includes params, query strings, or fragments."""
    extra_components = (parsed.params, parsed.query, parsed.fragment)
    if any(extra_components):
        return "base_url must not include params, query strings, or fragments"
    return None


def _validate_port(parsed: ParseResult) -> str | None:
    """Return an error when the URL contains an invalid port value."""
    try:
        _ = parsed.port
    except ValueError:
        return "base_url must not include an invalid port"
    return None


def _build_url(base_url: str, path: str) -> str:
    """Build an absolute URL for a hosted API path."""
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def _validate_base_url(base_url: str) -> str | None:
    """Return a bounded validation error when the base URL is not usable."""
    parsed = urlparse(base_url)
    validators = (
        _validate_scheme_and_host,
        _validate_no_credentials,
        _validate_hostname_present,
        _validate_not_loopback_hostname,
        _validate_root_path,
        _validate_no_extra_components,
        _validate_port,
        _validate_not_internal_address,
    )

    for validator in validators:
        validation_error = validator(parsed)
        if validation_error is not None:
            return validation_error

    return None


def _endpoint_path(url: str) -> str:
    """Return only the endpoint path for bounded operator output."""
    return urlparse(url).path or "/"


def _is_timeout_exception(exc: BaseException) -> bool:
    """Return whether an exception represents a request timeout."""
    timeout_types = (TimeoutError, socket.timeout)
    return isinstance(exc, timeout_types) or (isinstance(exc, URLError) and isinstance(exc.reason, timeout_types))


def _validate_request_target(url: str) -> str | None:
    """Return a bounded validation error for a request URL target."""
    parsed = urlparse(url)
    return _validate_not_internal_address(parsed)


def _response_failure_message(endpoint: str, exc: BaseException) -> str:
    """Return a bounded response-read failure message."""
    if _is_timeout_exception(exc):
        return f"{endpoint} request timed out"

    if isinstance(exc, UnicodeDecodeError):
        return f"{endpoint} returned non-UTF-8 response"

    return f"{endpoint} request failed"


def _read_response_body(url: str, timeout: float) -> tuple[int, str]:
    """Read an HTTP response while preserving bounded failure messages."""
    endpoint = _endpoint_path(url)

    # Revalidate request target to reduce DNS rebinding attack window
    target_error = _validate_request_target(url)
    if target_error is not None:
        raise RuntimeError(f"{endpoint} request target validation failed")

    request = Request(url, headers={"Accept": "application/json"}, method="GET")

    try:
        with urlopen(  # nosec B310 - operator-supplied smoke-check URL
            request,
            timeout=timeout,
        ) as response:
            raw_body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw_body) > MAX_RESPONSE_BYTES:
                raise RuntimeError(f"{endpoint} response body exceeded size limit")
            return response.status, raw_body.decode("utf-8")
    except HTTPError as exc:
        # Treat HTTP error responses as bounded readiness failures at the caller.
        return exc.code, ""
    except (URLError, TimeoutError, UnicodeDecodeError) as exc:
        raise RuntimeError(_response_failure_message(endpoint, exc)) from exc


def _parse_json_object(endpoint: str, raw_body: str) -> dict[str, Any]:
    """Parse a JSON object from a bounded endpoint response."""
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{endpoint} returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise RuntimeError(f"{endpoint} did not return a JSON object")

    return payload


def _get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
    """Fetch a JSON object from a URL."""
    endpoint = _endpoint_path(url)
    status_code, raw_body = _read_response_body(url, timeout)

    if status_code != 200:
        return status_code, {}

    return status_code, _parse_json_object(endpoint, raw_body)


def check_liveness(base_url: str, timeout: float) -> list[str]:
    """Return liveness check failures."""
    failures: list[str] = []
    url = _build_url(base_url, "/api/health")
    status_code, payload = _get_json(url, timeout)

    if status_code != 200:
        failures.append(f"/api/health returned HTTP {status_code}")
        return failures

    if payload.get("status") != "healthy":
        failures.append('/api/health did not return status "healthy"')

    if payload.get("graph_initialized") is not True:
        failures.append("/api/health did not report graph_initialized true")

    return failures


def _record_top_level_contract_failures(payload: dict[str, Any], failures: list[str]) -> None:
    """Record top-level detailed-readiness contract failures."""
    expected_top_level = {"status", "graph_persistence_configured", "graph", "database"}
    actual_top_level = set(payload)
    missing_top_level = sorted(expected_top_level - actual_top_level)
    unexpected_top_level = sorted(actual_top_level - expected_top_level)

    if actual_top_level != expected_top_level:
        failures.append(
            "/api/health/detailed returned top-level field mismatch: "
            f"missing={missing_top_level}, unexpected={unexpected_top_level}"
        )


def _record_forbidden_field_failures(payload: dict[str, Any], failures: list[str]) -> None:
    """Record detailed-readiness forbidden top-level field failures."""
    leaked_fields = sorted(set(payload) & FORBIDDEN_DETAILED_TOP_LEVEL_FIELDS)
    if leaked_fields:
        failures.append(f"/api/health/detailed exposed forbidden top-level fields: {leaked_fields}")


def _readiness_status_label(value: Any) -> str:
    """Return a bounded readiness status label for operator output."""
    if value in {"healthy", "degraded"}:
        return str(value)
    return "unknown"


def _startup_source_label(value: Any) -> str:
    """Return a bounded startup source label for operator output."""
    valid_sources = {
        "persisted",
        "real_data",
        "sample_data",
        "empty_persistence_fallback",
        "rebuild",
        "failed",
        "cache",
        "explicit_factory",
        "unknown",
    }
    if value in valid_sources:
        return str(value)
    return "unknown"


def _record_detailed_shape_failures(payload: dict[str, Any], failures: list[str]) -> None:
    """Record detailed-readiness status and object-shape failures."""
    readiness_status = payload.get("status")
    if readiness_status != "healthy":
        status_label = _readiness_status_label(readiness_status)
        failures.append(f'/api/health/detailed status is "{status_label}", expected "healthy"')

    if not isinstance(payload.get("graph_persistence_configured"), bool):
        failures.append("/api/health/detailed graph_persistence_configured field is not a boolean")

    if not isinstance(payload.get("graph"), dict):
        failures.append("/api/health/detailed graph field is not an object")

    if not isinstance(payload.get("database"), dict):
        failures.append("/api/health/detailed database field is not an object")


def _record_persistence_gate_failures(payload: dict[str, Any], failures: list[str]) -> None:
    """Record failures when the durable graph-persistence gate is not satisfied."""
    if payload.get("graph_persistence_configured") is not True:
        failures.append("/api/health/detailed graph_persistence_configured is not true")

    graph = payload.get("graph")
    if isinstance(graph, dict):
        if graph.get("persistence_enabled") is not True:
            failures.append("/api/health/detailed graph.persistence_enabled is not true")
        if graph.get("persistence_loaded") is not True:
            failures.append("/api/health/detailed graph.persistence_loaded is not true")
        actual_source = graph.get("startup_source")
        if actual_source is None:
            failures.append("/api/health/detailed graph.startup_source field is missing")
        else:
            source_label = _startup_source_label(actual_source)
            if source_label != "persisted":
                failures.append(f'/api/health/detailed graph.startup_source is "{source_label}", expected "persisted"')


def check_detailed_readiness(
    base_url: str,
    timeout: float,
    require_persistence: bool = False,
) -> list[str]:
    """Return detailed readiness check failures."""
    failures: list[str] = []
    url = _build_url(base_url, "/api/health/detailed")
    status_code, payload = _get_json(url, timeout)

    if status_code != 200:
        failures.append(f"/api/health/detailed returned HTTP {status_code}")
        return failures

    _record_top_level_contract_failures(payload, failures)
    _record_forbidden_field_failures(payload, failures)
    _record_detailed_shape_failures(payload, failures)

    if require_persistence:
        _record_persistence_gate_failures(payload, failures)

    return failures


def _run_named_check(
    label: str,
    base_url: str,
    timeout: float,
    check: Callable[[str, float], list[str]],
) -> list[str] | None:
    """Run a named check and report bounded runtime failures."""
    try:
        return check(base_url, timeout)
    except RuntimeError as exc:
        print(f"{label} check failed: {exc}", file=sys.stderr)
        return None
    except Exception:
        print(f"{label} check failed: unexpected error", file=sys.stderr)
        return None


def _report_failures(failures: list[str]) -> int:
    """Report accumulated readiness failures and return the process exit code."""
    if not failures:
        print("Hosted readiness smoke check passed.")
        return SUCCESS

    print("Hosted readiness smoke check failed:", file=sys.stderr)
    for failure in failures:
        print(f"- {failure}", file=sys.stderr)
    return CHECK_FAILED


def run_checks(base_url: str, timeout: float, require_persistence: bool = False) -> int:
    """Run hosted readiness checks and return a process exit code."""
    liveness_failures = _run_named_check("Liveness", base_url, timeout, check_liveness)
    if liveness_failures is None:
        return CHECK_FAILED

    readiness_failures = _run_named_check(
        "Detailed readiness",
        base_url,
        timeout,
        lambda url, t: check_detailed_readiness(url, t, require_persistence),
    )
    if readiness_failures is None:
        return CHECK_FAILED

    return _report_failures([*liveness_failures, *readiness_failures])


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Smoke-check hosted API health/readiness endpoints.")
    parser.add_argument("base_url", help="Base URL of the hosted deployment, e.g. https://example.vercel.app")
    parser.add_argument("--timeout", type=float, default=5.0, help="Request timeout in seconds.")
    parser.add_argument(
        "--require-persistence",
        action="store_true",
        help="Prove persisted graph load rather than fallback generation.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the hosted readiness smoke check."""
    args = parse_args(sys.argv[1:] if argv is None else argv)

    if not math.isfinite(args.timeout) or args.timeout <= 0:
        print("--timeout must be a positive finite number", file=sys.stderr)
        return USAGE_ERROR

    base_url_error = _validate_base_url(args.base_url)
    if base_url_error is not None:
        print(base_url_error, file=sys.stderr)
        return USAGE_ERROR

    return run_checks(args.base_url, args.timeout, args.require_persistence)


if __name__ == "__main__":
    raise SystemExit(main())
