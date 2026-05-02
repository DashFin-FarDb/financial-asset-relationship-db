"""Smoke-check hosted API liveness and bounded readiness endpoints."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

SUCCESS = 0
CHECK_FAILED = 1
USAGE_ERROR = 2

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


def _build_url(base_url: str, path: str) -> str:
    """Build an absolute URL for a hosted API path."""
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def _validate_base_url(base_url: str) -> str | None:
    """Return a bounded validation error when the base URL is not usable."""
    parsed = urlparse(base_url)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "base_url must include an http:// or https:// scheme and host"

    if parsed.username or parsed.password:
        return "base_url must not include credentials"

    if parsed.path not in {"", "/"}:
        return "base_url must not include a path"

    if parsed.params or parsed.query or parsed.fragment:
        return "base_url must not include params, query strings, or fragments"

    return None


def _endpoint_path(url: str) -> str:
    """Return only the endpoint path for bounded operator output."""
    return urlparse(url).path or "/"
    

def _get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
    """Fetch a JSON object from a URL."""
    endpoint = _endpoint_path(url)
    request = Request(url, headers={"Accept": "application/json"}, method="GET")

    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310 - operator-supplied smoke-check URL
            status_code = response.status
            raw_body = response.read().decode("utf-8")
    except HTTPError as exc:
        return exc.code, {}
    except URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise RuntimeError(f"{endpoint} request timed out") from exc
        raise RuntimeError(f"{endpoint} request failed") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"{endpoint} request timed out") from exc

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{endpoint} returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise RuntimeError(f"{endpoint} did not return a JSON object")

    return status_code, payload


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


def check_detailed_readiness(base_url: str, timeout: float) -> list[str]:
    """Return detailed readiness check failures."""
    failures: list[str] = []
    url = _build_url(base_url, "/api/health/detailed")
    status_code, payload = _get_json(url, timeout)

    if status_code != 200:
        failures.append(f"/api/health/detailed returned HTTP {status_code}")
        return failures

    expected_top_level = {"status", "graph", "database"}
    actual_top_level = set(payload)
    missing_top_level = sorted(expected_top_level - actual_top_level)
    unexpected_top_level = sorted(actual_top_level - expected_top_level)
    if actual_top_level != expected_top_level:
        failures.append(
            "/api/health/detailed returned top-level field mismatch: "
            f"missing={missing_top_level}, unexpected={unexpected_top_level}"
        )

    leaked_fields = sorted(actual_top_level & FORBIDDEN_DETAILED_TOP_LEVEL_FIELDS)
    if leaked_fields:
        failures.append(f"/api/health/detailed exposed forbidden top-level fields: {leaked_fields}")

    readiness_status = payload.get("status")
    if readiness_status != "healthy":
        failures.append(f'/api/health/detailed status is "{readiness_status}", expected "healthy"')

    graph = payload.get("graph")
    if not isinstance(graph, dict):
        failures.append("/api/health/detailed graph field is not an object")

    database = payload.get("database")
    if not isinstance(database, dict):
        failures.append("/api/health/detailed database field is not an object")

    return failures


def run_checks(base_url: str, timeout: float) -> int:
    """Run hosted readiness checks and return a process exit code."""
    failures: list[str] = []

    try:
        failures.extend(check_liveness(base_url, timeout))
        failures.extend(check_detailed_readiness(base_url, timeout))
    except RuntimeError as exc:
        print(f"Hosted readiness smoke check failed: {exc}", file=sys.stderr)
        return CHECK_FAILED

    if failures:
        print("Hosted readiness smoke check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return CHECK_FAILED

    print("Hosted readiness smoke check passed.")
    return SUCCESS


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Smoke-check hosted API health/readiness endpoints.")
    parser.add_argument("base_url", help="Base URL of the hosted deployment, e.g. https://example.vercel.app")
    parser.add_argument("--timeout", type=float, default=5.0, help="Request timeout in seconds.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the hosted readiness smoke check."""
    args = parse_args(sys.argv[1:] if argv is None else argv)

    if args.timeout <= 0:
        print("--timeout must be greater than zero", file=sys.stderr)
        return USAGE_ERROR

    base_url_error = _validate_base_url(args.base_url)
    if base_url_error is not None:
        print(base_url_error, file=sys.stderr)
        return USAGE_ERROR

    return run_checks(args.base_url, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
