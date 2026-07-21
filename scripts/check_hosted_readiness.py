"""Smoke-check hosted API liveness and bounded readiness endpoints."""

from __future__ import annotations

import argparse
import ipaddress
import json
import math
import socket
import sys
from collections.abc import Callable
from typing import Any, TypeGuard
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

SAFE_OBSERVED_FIELDS = ("status", "graph_persistence_configured")


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


def _validate_request_query(parsed: ParseResult, allowed_query: str | None) -> str | None:
    """Return an error when the request query does not match the allowlist exactly."""
    if parsed.params or parsed.fragment:
        return "request URL must not include params or fragments"
    expected_query = "" if allowed_query is None else allowed_query
    if parsed.query != expected_query:
        return "request URL query is not in the smoke-check allowlist"
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


def _validate_request_target(url: str, *, allowed_query: str | None = None) -> str | None:
    """Return a bounded validation error for a request URL target."""
    parsed = urlparse(url)
    validators: tuple[Callable[[ParseResult], str | None], ...] = (
        _validate_scheme_and_host,
        _validate_no_credentials,
        _validate_hostname_present,
        _validate_not_loopback_hostname,
        _validate_port,
        _validate_not_internal_address,
    )

    for validator in validators:
        validation_error = validator(parsed)
        if validation_error is not None:
            return validation_error

    return _validate_request_query(parsed, allowed_query)


def _response_failure_message(endpoint: str, exc: BaseException) -> str:
    """Return a bounded response-read failure message."""
    if _is_timeout_exception(exc):
        return f"{endpoint} request timed out"

    if isinstance(exc, UnicodeDecodeError):
        return f"{endpoint} returned non-UTF-8 response"

    return f"{endpoint} request failed"


def _read_response_body(
    url: str,
    timeout: float,
    *,
    allowed_query: str | None = None,
) -> tuple[int, str]:
    """Read an HTTP response while preserving bounded failure messages."""
    endpoint = _endpoint_path(url)

    # Revalidate request target to reduce DNS rebinding attack window
    target_error = _validate_request_target(url, allowed_query=allowed_query)
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


def _get_json(
    url: str,
    timeout: float,
    *,
    allowed_query: str | None = None,
) -> tuple[int, dict[str, Any]]:
    """Fetch a JSON object from a URL."""
    endpoint = _endpoint_path(url)
    status_code, raw_body = _read_response_body(url, timeout, allowed_query=allowed_query)

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


def _collect_observed_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Return safely observed readiness fields for JSON evidence output."""
    observed_fields: dict[str, Any] = {}

    for field_name in SAFE_OBSERVED_FIELDS:
        if field_name in payload:
            observed_fields[field_name] = payload[field_name]

    graph = payload.get("graph")
    if isinstance(graph, dict):
        for field_name in (
            "available",
            "asset_count",
            "relationship_count",
            "persistence_enabled",
            "persistence_loaded",
            "startup_source",
        ):
            if field_name in graph:
                observed_fields[f"graph.{field_name}"] = graph[field_name]

    database = payload.get("database")
    if isinstance(database, dict):
        for field_name in ("configured", "reachable"):
            if field_name in database:
                observed_fields[f"database.{field_name}"] = database[field_name]

    return observed_fields


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
    if isinstance(value, str) and value in valid_sources:
        return value
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


def _build_detailed_readiness_report(
    base_url: str,
    timeout: float,
    require_persistence: bool = False,
) -> tuple[list[str], dict[str, Any]]:
    """Return detailed readiness failures and observed fields."""
    failures: list[str] = []
    url = _build_url(base_url, "/api/health/detailed")
    status_code, payload = _get_json(url, timeout)

    if status_code != 200:
        failures.append(f"/api/health/detailed returned HTTP {status_code}")
        return failures, {}

    _record_top_level_contract_failures(payload, failures)
    _record_forbidden_field_failures(payload, failures)
    _record_detailed_shape_failures(payload, failures)

    if require_persistence:
        _record_persistence_gate_failures(payload, failures)

    return failures, _collect_observed_fields(payload)


def check_detailed_readiness(
    base_url: str,
    timeout: float,
    require_persistence: bool = False,
) -> list[str]:
    """Return detailed readiness check failures."""
    return _build_detailed_readiness_report(base_url, timeout, require_persistence)[0]


ASSETS_SMOKE_QUERY = "per_page=1"


def _has_more_value(payload: dict[str, Any]) -> Any:
    """Return the pagination hasMore flag from camelCase or snake_case."""
    if "hasMore" in payload:
        return payload.get("hasMore")
    return payload.get("has_more")


def _is_int(value: Any) -> TypeGuard[int]:
    """Return whether value is an int that is not a bool subclass instance."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_non_negative_int(value: Any) -> TypeGuard[int]:
    """Return whether value is a non-negative integer."""
    return _is_int(value) and value >= 0


def _is_positive_int(value: Any) -> TypeGuard[int]:
    """Return whether value is a positive integer."""
    return _is_int(value) and value >= 1


def _record_assets_smoke_shape_failures(payload: dict[str, Any], failures: list[str]) -> None:
    """Append assets smoke contract failures for response shape and emptiness."""
    items = payload.get("items")
    total = payload.get("total")
    page = payload.get("page")
    per_page = payload.get("per_page")
    has_more = _has_more_value(payload)

    if not isinstance(items, list):
        failures.append("/api/assets items field is not a list")
    if not _is_non_negative_int(total):
        failures.append("/api/assets total field is not a non-negative integer")
    if not _is_positive_int(page):
        failures.append("/api/assets page field is not a positive integer")
    if not _is_positive_int(per_page):
        failures.append("/api/assets per_page field is not a positive integer")
    if not isinstance(has_more, bool):
        failures.append("/api/assets hasMore field is not a boolean")
    if _is_non_negative_int(total) and total < 1:
        failures.append("/api/assets total is less than 1")
    if isinstance(items, list) and len(items) < 1:
        failures.append("/api/assets items list is empty")


def _collect_assets_smoke_observed(payload: dict[str, Any]) -> dict[str, Any]:
    """Collect bounded observed fields from an assets smoke response."""
    observed: dict[str, Any] = {}
    items = payload.get("items")
    total = payload.get("total")
    per_page = payload.get("per_page")
    has_more = _has_more_value(payload)

    if _is_int(total):
        observed["assets.total"] = total
    if isinstance(items, list):
        observed["assets.item_count"] = len(items)
    if _is_int(per_page):
        observed["assets.per_page"] = per_page
    if isinstance(has_more, bool):
        observed["assets.has_more"] = has_more
    return observed


def _build_assets_smoke_report(
    base_url: str,
    timeout: float,
) -> tuple[list[str], dict[str, Any]]:
    """Return assets smoke failures and bounded observed fields."""
    failures: list[str] = []
    url = f"{_build_url(base_url, '/api/assets')}?{ASSETS_SMOKE_QUERY}"
    status_code, payload = _get_json(url, timeout, allowed_query=ASSETS_SMOKE_QUERY)

    if status_code != 200:
        failures.append(f"/api/assets returned HTTP {status_code}")
        return failures, {}

    _record_assets_smoke_shape_failures(payload, failures)
    return failures, _collect_assets_smoke_observed(payload)


def check_assets_smoke(base_url: str, timeout: float) -> list[str]:
    """Return failures for the bounded /api/assets promotion smoke check."""
    return _build_assets_smoke_report(base_url, timeout)[0]


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


def _report_json_result(result: dict[str, Any]) -> int:
    """Emit structured JSON readiness output and return the process exit code."""
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return SUCCESS if result.get("status") == "passed" else CHECK_FAILED


def _run_named_check_json(
    label: str,
    base_url: str,
    timeout: float,
    check: Callable[[str, float], list[str]],
) -> tuple[list[str], bool]:
    """Run a named check for JSON output, preserving bounded failures."""
    try:
        return check(base_url, timeout), False
    except RuntimeError as exc:
        return [f"{label} check failed: {exc}"], True
    except Exception:
        return [f"{label} check failed: unexpected error"], True


def _safe_detailed_report(
    base_url: str,
    timeout: float,
    require_persistence: bool,
) -> tuple[list[str], dict[str, Any]]:
    """Build a detailed readiness report, converting exceptions to failures."""
    try:
        return _build_detailed_readiness_report(base_url, timeout, require_persistence)
    except RuntimeError as exc:
        return [f"Detailed readiness check failed: {exc}"], {}
    except Exception:
        return ["Detailed readiness check failed: unexpected error"], {}


def _safe_assets_smoke_report(
    base_url: str,
    timeout: float,
) -> tuple[list[str], dict[str, Any]]:
    """Build an assets smoke report, converting exceptions to failures."""
    try:
        return _build_assets_smoke_report(base_url, timeout)
    except RuntimeError as exc:
        return [f"Assets smoke check failed: {exc}"], {}
    except Exception:
        return ["Assets smoke check failed: unexpected error"], {}


def _skipped_checks_after_liveness_failure(
    assets_smoke: bool,
) -> tuple[list[str], list[str], dict[str, Any]]:
    """Return skipped follow-on check failures when liveness already failed."""
    detailed_failures = ["Detailed readiness check not run because liveness check failed"]
    assets_failures = ["Assets smoke check not run because liveness check failed"] if assets_smoke else []
    return detailed_failures, assets_failures, {}


def _run_checks_after_liveness(
    base_url: str,
    timeout: float,
    require_persistence: bool,
    assets_smoke: bool,
) -> tuple[list[str], list[str], dict[str, Any]]:
    """Run detailed readiness and optional assets smoke after liveness succeeds."""
    detailed_failures, observed_fields = _safe_detailed_report(
        base_url,
        timeout,
        require_persistence,
    )
    assets_failures: list[str] = []
    if assets_smoke:
        assets_failures, assets_observed = _safe_assets_smoke_report(base_url, timeout)
        observed_fields.update(assets_observed)
    return detailed_failures, assets_failures, observed_fields


def _build_json_checks_payload(
    *,
    liveness_failures: list[str],
    detailed_failures: list[str],
    assets_failures: list[str],
    assets_smoke: bool,
    require_persistence: bool,
    base_url_label: str,
    observed_fields: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the machine-readable hosted readiness JSON payload."""
    checks: dict[str, Any] = {
        "liveness": {"passed": not liveness_failures, "failures": liveness_failures},
        "detailed_readiness": {"passed": not detailed_failures, "failures": detailed_failures},
    }
    if assets_smoke:
        checks["assets_smoke"] = {"passed": not assets_failures, "failures": assets_failures}

    all_failures = [*liveness_failures, *detailed_failures, *assets_failures]
    return {
        "status": "passed" if not all_failures else "failed",
        "base_url_label": base_url_label,
        "require_persistence": require_persistence,
        "assets_smoke": assets_smoke,
        "checks": checks,
        "observed_fields": observed_fields,
    }


def _run_json_checks(
    base_url: str,
    timeout: float,
    require_persistence: bool = False,
    assets_smoke: bool = False,
    base_url_label: str = "redacted",
) -> int:
    """Run hosted readiness checks and emit JSON output."""
    liveness_failures, liveness_had_runtime_error = _run_named_check_json(
        "Liveness",
        base_url,
        timeout,
        check_liveness,
    )
    if liveness_had_runtime_error:
        detailed_failures, assets_failures, observed_fields = _skipped_checks_after_liveness_failure(assets_smoke)
    else:
        detailed_failures, assets_failures, observed_fields = _run_checks_after_liveness(
            base_url,
            timeout,
            require_persistence,
            assets_smoke,
        )

    return _report_json_result(
        _build_json_checks_payload(
            liveness_failures=liveness_failures,
            detailed_failures=detailed_failures,
            assets_failures=assets_failures,
            assets_smoke=assets_smoke,
            require_persistence=require_persistence,
            base_url_label=base_url_label,
            observed_fields=observed_fields,
        )
    )


def run_checks(
    base_url: str,
    timeout: float,
    require_persistence: bool = False,
    assets_smoke: bool = False,
    *,
    json_output: bool = False,
    base_url_label: str = "redacted",
) -> int:
    """Run hosted readiness checks and return a process exit code."""
    if json_output:
        return _run_json_checks(
            base_url,
            timeout,
            require_persistence,
            assets_smoke,
            base_url_label,
        )

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

    assets_failures: list[str] = []
    if assets_smoke:
        named_assets = _run_named_check("Assets smoke", base_url, timeout, check_assets_smoke)
        if named_assets is None:
            return CHECK_FAILED
        assets_failures = named_assets

    return _report_failures([*liveness_failures, *readiness_failures, *assets_failures])


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Smoke-check hosted API health/readiness endpoints.")
    parser.add_argument("base_url", help="Base URL of the hosted deployment, e.g. https://example.vercel.app")
    parser.add_argument("--timeout", type=float, default=5.0, help="Request timeout in seconds.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
    parser.add_argument(
        "--base-url-label",
        default="redacted",
        help="Operator-safe label to include in JSON output instead of the raw base URL.",
    )
    parser.add_argument(
        "--require-persistence",
        action="store_true",
        help="Prove persisted graph load rather than fallback generation.",
    )
    parser.add_argument(
        "--assets-smoke",
        action="store_true",
        help=(
            "Prove bounded GET /api/assets?per_page=1 returns at least one asset. "
            "Enabled automatically when --require-persistence is set."
        ),
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

    effective_assets_smoke = args.assets_smoke or args.require_persistence
    return run_checks(
        args.base_url,
        args.timeout,
        args.require_persistence,
        effective_assets_smoke,
        json_output=args.json,
        base_url_label=args.base_url_label,
    )


if __name__ == "__main__":
    raise SystemExit(main())
