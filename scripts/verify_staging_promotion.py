"""Staging promotion verification script."""

import argparse
import json
import os
import re
import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, TypedDict

UTC = timezone.utc
DEFAULT_MAX_EVIDENCE_AGE_DAYS = 14
_PLACEHOLDER_OWNERS = frozenset({"", "tbd", "todo", "n/a", "none", "pending", "<owner>", "unknown"})
_TABLE_ROLE_PATTERN_TEMPLATE = r"^\s*\|\s*{role}\s*\|\s*([^|\n]+?)\s*\|"
_KV_ROLE_PATTERN_TEMPLATE = r"^\s*{role}\s*:\s*([^\n]+)$"
_CAPTURE_DATE_PATTERN = re.compile(
    r"(?:\*\*Evidence capture date:\*\*|evidence_capture_date\s*:)\s*(\d{4}-\d{2}-\d{2}(?:T[0-9:+-]+Z?)?)",
    re.IGNORECASE,
)
_EXPIRY_DATE_PATTERN = re.compile(
    r"(?:\*\*Evidence expiry date(?:\s*\(UTC\))?:\*\*|evidence_expires_at\s*:)\s*(\d{4}-\d{2}-\d{2}(?:T[0-9:+-]+Z?)?)",
    re.IGNORECASE,
)
_SOD_WAIVER_PATTERN = re.compile(r"^\s*sod_waiver\s*:\s*\S+", re.IGNORECASE | re.MULTILINE)

REPO_ROOT = Path(__file__).resolve().parent.parent
DISTINCT_BOUNDARY_PATTERN = re.compile(
    "|".join(
        (
            r"\basset_graph_database_url\b[^\n]{0,80}\bdistinct\b",
            r"\bdistinct\b[^\n]{0,80}\basset_graph_database_url\b",
        )
    )
)


class JsonScanState(TypedDict):
    """Mutable scanner state used to extract brace-balanced JSON blocks."""

    start: int | None
    depth: int
    in_string: bool
    escaped: bool


def _check_provider_labels(content: str, missing: List[str]) -> None:
    """Check for provider and hosting labels."""
    if "supabase" not in content:
        missing.append("Supabase provider label")
    if "vercel mapping" not in content and "vercel project" not in content and "deployment url" not in content:
        missing.append("Vercel mapping (frontend/backend traffic)")


def _check_distinct_boundary(content: str, missing: List[str]) -> None:
    """Check for distinct graph boundary definitions."""
    distinct_confirmed = DISTINCT_BOUNDARY_PATTERN.search(content) is not None
    if not distinct_confirmed and "approved exception" not in content and "shared-boundary statement" not in content:
        missing.append("Distinct ASSET_GRAPH_DATABASE_URL boundary or approved exception")


def _check_coordination_boundary(content: str, missing: List[str]) -> None:
    """Check for coordination boundary definitions."""
    if (
        "coordination_database_url" not in content
        and "coordination shares" not in content
        and "shared-boundary statement" not in content
        and "fallback boundary" not in content
    ):
        missing.append("Coordination boundary or explicit shared-boundary statement")


def _check_database_boundaries(content: str, missing: List[str]) -> None:
    """Check for required database boundary definitions."""
    if not re.search(r"\bdatabase_url\b", content):
        missing.append("DATABASE_URL boundary confirmation")

    asset_graph_present = "asset_graph_database_url" in content
    if not asset_graph_present:
        missing.append("ASSET_GRAPH_DATABASE_URL boundary confirmation")
    else:
        _check_distinct_boundary(content, missing)
    _check_coordination_boundary(content, missing)


def _advance_json_scan(state: JsonScanState, char: str, index: int) -> tuple[int, int] | None:
    """Advance the JSON span scanner by one character."""
    if state["in_string"]:
        if state["escaped"]:
            state["escaped"] = False
        elif char == "\\":
            state["escaped"] = True
        elif char == '"':
            state["in_string"] = False
        return None

    if char == '"':
        state["in_string"] = True
        return None

    if char == "{":
        if state["depth"] == 0:
            state["start"] = index
        state["depth"] += 1
        return None

    if char == "}" and state["depth"] > 0:
        state["depth"] -= 1
        if state["depth"] == 0 and state["start"] is not None:
            start = state["start"]
            state["start"] = None
            return (start, index + 1)

    return None


def _extract_balanced_json_objects(source: str) -> List[str]:
    """Extract brace-balanced JSON object candidates from source text."""
    state: JsonScanState = {"start": None, "depth": 0, "in_string": False, "escaped": False}
    blocks: List[str] = []
    for index, char in enumerate(source):
        span = _advance_json_scan(state, char, index)
        if span is not None:
            blocks.append(source[span[0] : span[1]])
    return blocks


def _json_object_has_persistence_proof(data: dict[str, object]) -> bool:
    """Return whether a parsed JSON object contains the persistence proof fields."""
    observed_fields = data.get("observed_fields")
    if isinstance(observed_fields, dict):
        return (
            observed_fields.get("graph_persistence_configured") is True
            and observed_fields.get("graph.persistence_enabled") is True
            and observed_fields.get("graph.persistence_loaded") is True
            and observed_fields.get("graph.startup_source") == "persisted"
        )

    graph_data = data.get("graph")
    if isinstance(graph_data, dict):
        return (
            data.get("graph_persistence_configured") is True
            and graph_data.get("persistence_enabled") is True
            and graph_data.get("persistence_loaded") is True
            and graph_data.get("startup_source") == "persisted"
        )

    return False


def _parse_json_block(block: str) -> dict[str, object] | None:
    """Parse a JSON block and return a dict payload if it is valid."""
    try:
        data = json.loads(block)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _iter_parsed_json_blocks(content_raw: str) -> List[dict[str, object]]:
    """Extract and parse candidate JSON blocks from a blob of markdown text."""
    fenced_blocks = re.findall(r"```(?:json)?[ \t]*\n(.*?)```", content_raw, re.IGNORECASE | re.DOTALL)
    candidate_blocks: List[str] = []
    for fenced_block in fenced_blocks:
        candidate_blocks.extend(_extract_balanced_json_objects(fenced_block))
    if not candidate_blocks:
        candidate_blocks = _extract_balanced_json_objects(content_raw)

    parsed_blocks: List[dict[str, object]] = []
    for block in candidate_blocks:
        parsed_block = _parse_json_block(block)
        if parsed_block is not None:
            parsed_blocks.append(parsed_block)
    return parsed_blocks


def _repo_relative_evidence_path(evidence_file: str) -> Path:
    """Validate the caller-provided evidence path as a repo-relative path."""
    normalized = evidence_file.replace("\\", "/")
    candidate = Path(normalized)
    if candidate.is_absolute() or any(part in ("", ".", "..") for part in candidate.parts):
        print(f"Error: Invalid evidence file path {evidence_file}. Evidence must be a repo-relative path.")
        sys.exit(1)
    return candidate


def _open_repo_file_no_symlink(path: Path):
    """Open a file under the repo root without following symlinks."""
    repo_fd = os.open(REPO_ROOT, os.O_RDONLY | os.O_DIRECTORY)
    current_fd = repo_fd
    try:
        parts = path.parts
        for index, part in enumerate(parts):
            is_last = index == len(parts) - 1
            flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
            if not is_last:
                flags |= os.O_DIRECTORY
            next_fd = os.open(part, flags, dir_fd=current_fd)
            if current_fd != repo_fd:
                os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except Exception:
        if current_fd != repo_fd:
            os.close(current_fd)
        raise
    finally:
        os.close(repo_fd)


def _read_evidence_file(evidence_file: str) -> str:
    """Read an evidence file within the repo without following symlinks."""
    relative_path = _repo_relative_evidence_path(evidence_file)
    file_fd = _open_repo_file_no_symlink(relative_path)
    try:
        if not stat.S_ISREG(os.fstat(file_fd).st_mode):
            raise OSError(f"Evidence path {evidence_file} is not a regular file.")
        handle = os.fdopen(file_fd, "r", encoding="utf-8")
    except Exception:
        try:
            os.close(file_fd)
        except OSError:
            # Best-effort cleanup: ignore close errors so the original exception is re-raised.
            pass
        raise

    with handle:
        return handle.read()


def _check_persistence_proof(content_raw: str, missing: List[str]) -> None:
    """Check for durability/persistence proofs by parsing JSON payloads."""
    found_all_in_one = any(
        _json_object_has_persistence_proof(parsed_block) for parsed_block in _iter_parsed_json_blocks(content_raw)
    )

    if not found_all_in_one:
        missing.append(
            "Complete durable graph proof in a single JSON block (requires graph_persistence_configured, "
            "graph.persistence_enabled, graph.persistence_loaded, and graph.startup_source == 'persisted')"
        )

    content_lower = content_raw.lower()
    if (
        "durable preview" not in content_lower
        and "non-durable preview" not in content_lower
        and "preview durability label" not in content_lower
    ):
        missing.append("Durable/non-durable preview label")


def _check_urls(content: str, missing: List[str]) -> None:
    """Check for valid, specific URLs and reject generic Actions URLs."""
    if "/actions/runs/" not in content and "/artifacts/" not in content:
        missing.append("Specific workflow run URL or artifact URL")

    generic_actions_pattern = r"https://github\.com/[^/\s)]+/[^/\s)]+/actions(?!/runs/)(?:[^\s)]*)?"
    if re.search(generic_actions_pattern, content):
        missing.append("Generic Actions URLs are not allowed")


def _check_operational_evidence(content: str, missing: List[str]) -> None:
    """Check for smoke tests, ownership, and scanner summaries."""
    checks = [
        (("asset smoke evidence", "/api/assets?per_page=1"), "Asset smoke evidence"),
        (("hosted readiness",), "hosted readiness"),
        (("health json", "health.json"), "health JSON"),
        (
            ("named owners", "deploy operator", "promotion approver"),
            "Named owners (deploy, promotion, rollback, restore, persistence-verification)",
        ),
        (("scanner summary", "security scanner"), "Scanner summary"),
    ]
    for patterns, err_msg in checks:
        if not any(p in content for p in patterns):
            missing.append(err_msg)

    # Simple heuristic for unredacted secrets/tokens (allow common redaction markers)
    keywords = "|".join(["password", "secret", "token", "key"])
    secret_pattern = (
        rf"(?i)(?:\b|_)({keywords})(?:\b|_)['\"]?[ \t]*[:=][ \t]*['\"]?" r"(?![^\s]*?(?:redacted|x{4,}))[\S\*]{8,}"
    )
    if re.search(secret_pattern, content):
        missing.append("Non-redacted evidence found (secrets/tokens must be redacted)")


REQUIRED_HARDENING_IDS = (
    "H-P0-01",
    "H-P0-02",
    "H-P0-03",
    "H-P0-04",
    "H-P0-06",
)
TOPOLOGY_MARKER_PATTERN = re.compile(
    r"topology\s*:\s*jobs\s*=\s*asset_graph\s*;\s*locks\s*=\s*coordination",
    re.IGNORECASE,
)
# Bare PASS is rejected; require an opaque run/artifact reference after '|'.
# Capture a single non-space token (no reluctant quantifier / backtracking).
DB_AUTHZ_PASS_PATTERN = re.compile(
    r"^\s*db_authz\s*:\s*PASS\s*\|\s*(\S+)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
# Allowlist: run/artifact-shaped refs with a numeric id (>=3 digits). Rejects
# denylist-evading placeholders such as TBD/TODO/N/A and angle-bracket templates.
DB_AUTHZ_OPAQUE_REF_PATTERN = re.compile(
    r"^(?:"
    r"\d{6,}"  # bare GitHub Actions run id
    r"|run-\d{3,}"  # run-123
    r"|artifact-\d{3,}"  # artifact-456
    r"|[A-Za-z0-9][A-Za-z0-9._-]{0,64}-run-\d{3,}"  # 1506-run-123456
    r")$",
    re.IGNORECASE,
)
DB_AUTHZ_OPAQUE_REF_ERROR = (
    "db_authz opaque ref must match run-<digits>, artifact-<digits>, "
    "<prefix>-run-<digits>, or a numeric workflow run id (>=6 digits)"
)
HARDENING_IDS_LINE_PATTERN = re.compile(r"hardening_ids\s*:\s*([^\n]+)", re.IGNORECASE)
HARDENING_ID_TOKEN_PATTERN = re.compile(r"^H-P0-\d{2}$")


def _hardening_id_tokens(ids_blob: str) -> set[str]:
    """Split a hardening_ids value on commas and keep exact H-P0-NN tokens."""
    tokens: set[str] = set()
    for raw_token in ids_blob.split(","):
        # Drop trailing `# ...` comments on a comma segment before matching.
        without_comment = raw_token.split("#", 1)[0]
        token = without_comment.strip().upper()
        if HARDENING_ID_TOKEN_PATTERN.fullmatch(token):
            tokens.add(token)
    return tokens


def _check_hardening_ids(content: str, missing: List[str]) -> None:
    """Require the P0 hardening_ids marker with exact foundation IDs."""
    ids_match = HARDENING_IDS_LINE_PATTERN.search(content)
    if ids_match is None:
        missing.append("hardening_ids marker with P0 foundation IDs")
        return
    ids_tokens = _hardening_id_tokens(ids_match.group(1))
    missing_ids = [item_id for item_id in REQUIRED_HARDENING_IDS if item_id not in ids_tokens]
    if missing_ids:
        missing.append("hardening_ids missing required IDs: " + ", ".join(missing_ids))


def _check_hardening_topology(content: str, missing: List[str]) -> None:
    """Require the jobs/locks topology marker."""
    if TOPOLOGY_MARKER_PATTERN.search(content) is None:
        missing.append("topology: jobs=asset_graph; locks=coordination")


def _check_hardening_db_authz(content: str, missing: List[str]) -> None:
    """Require db_authz PASS with an allowlisted opaque run/artifact ref."""
    authz_match = DB_AUTHZ_PASS_PATTERN.search(content)
    if authz_match is None:
        missing.append("db_authz: PASS|<opaque-ref> (bare PASS is not accepted)")
        return
    opaque_ref = authz_match.group(1).strip()
    if DB_AUTHZ_OPAQUE_REF_PATTERN.fullmatch(opaque_ref) is None:
        missing.append(DB_AUTHZ_OPAQUE_REF_ERROR)


def _check_hardening_foundation(content: str, missing: List[str]) -> None:
    """Check P0 hardening backlog markers required for staging promotion."""
    _check_hardening_ids(content, missing)
    _check_hardening_topology(content, missing)
    _check_hardening_db_authz(content, missing)


def _extract_named_role(content: str, table_label: str, kv_key: str) -> str | None:
    """Extract a named owner from either the sign-off Markdown table or a key-value marker."""
    table_match = re.search(
        _TABLE_ROLE_PATTERN_TEMPLATE.format(role=re.escape(table_label)),
        content,
        re.IGNORECASE | re.MULTILINE,
    )
    if table_match is not None:
        raw = table_match.group(1).strip().strip("`*@ ")
        if raw.lower() not in _PLACEHOLDER_OWNERS:
            return raw

    kv_match = re.search(
        _KV_ROLE_PATTERN_TEMPLATE.format(role=re.escape(kv_key)),
        content,
        re.IGNORECASE | re.MULTILINE,
    )
    if kv_match is not None:
        raw = kv_match.group(1).strip().strip("`*@ ")
        if raw.lower() not in _PLACEHOLDER_OWNERS:
            return raw
    return None


def _parse_iso_utc(raw: str) -> datetime | None:
    """Parse an ISO date (YYYY-MM-DD) or ISO-8601 datetime into a UTC-aware datetime."""
    cleaned = raw.strip()
    if not cleaned:
        return None
    if cleaned.endswith(("Z", "z")):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        # Date-only values expire at end of UTC day; datetimes default to UTC
        if len(raw.strip()) == 10:
            parsed = parsed.replace(hour=23, minute=59, second=59, tzinfo=UTC)
        else:
            parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def check_separation_of_duties(
    content_raw: str,
    missing: List[str],
    *,
    require_explicit: bool = False,
) -> None:
    """Enforce separation of duties between Deploy operator and Promotion approver (H-P3-05)."""
    deploy_operator = _extract_named_role(content_raw, "Deploy operator", "deploy_operator")
    promotion_approver = _extract_named_role(content_raw, "Promotion approver", "promotion_approver")

    if require_explicit:
        if not deploy_operator:
            missing.append("Separation of duties (H-P3-05): named Deploy operator is required")
        if not promotion_approver:
            missing.append("Separation of duties (H-P3-05): named Promotion approver is required")
        if not deploy_operator or not promotion_approver:
            return

    if deploy_operator and promotion_approver and deploy_operator.lower() == promotion_approver.lower():
        if require_explicit or _SOD_WAIVER_PATTERN.search(content_raw) is None:
            missing.append(
                "Separation of duties (H-P3-05): Deploy operator and Promotion approver must be distinct individuals"
            )


def check_evidence_expiry(
    content_raw: str,
    missing: List[str],
    *,
    require_explicit: bool = False,
    max_age_days: int = DEFAULT_MAX_EVIDENCE_AGE_DAYS,
    now: datetime | None = None,
) -> None:
    """Enforce evidence packet expiry and maximum capture age (H-P3-05)."""
    current_time = now.astimezone(UTC) if now is not None else datetime.now(UTC)

    expiry_match = _EXPIRY_DATE_PATTERN.search(content_raw)
    capture_match = _CAPTURE_DATE_PATTERN.search(content_raw)

    if expiry_match is not None:
        expiry_dt = _parse_iso_utc(expiry_match.group(1))
        if expiry_dt is None:
            missing.append("Evidence expiry (H-P3-05): unparseable evidence_expires_at date")
        elif expiry_dt < current_time:
            missing.append(f"Evidence expiry (H-P3-05): evidence packet expired on {expiry_match.group(1)}")

    if capture_match is not None:
        capture_dt = _parse_iso_utc(capture_match.group(1))
        if capture_dt is None:
            missing.append("Evidence expiry (H-P3-05): unparseable Evidence capture date")
        elif current_time - capture_dt > timedelta(days=max_age_days):
            missing.append(
                f"Evidence expiry (H-P3-05): evidence capture date {capture_match.group(1)} "
                f"exceeds maximum age of {max_age_days} days"
            )

    if require_explicit and expiry_match is None and capture_match is None:
        missing.append("Evidence expiry (H-P3-05): Evidence capture date or evidence_expires_at is required")


def verify_staging_promotion(
    evidence_file: str,
    *,
    enforce_sod: bool = False,
    enforce_expiry: bool = False,
    max_evidence_age_days: int = DEFAULT_MAX_EVIDENCE_AGE_DAYS,
    now: datetime | None = None,
) -> None:
    """Verify baseline items in a staging promotion evidence file."""
    evidence_path_obj = REPO_ROOT / _repo_relative_evidence_path(evidence_file)
    if not evidence_path_obj.exists():
        print(f"Error: Evidence path {evidence_file} does not exist.")
        sys.exit(1)
    if not evidence_path_obj.is_file():
        print(f"Error: Evidence path {evidence_file} is not a regular file.")
        sys.exit(1)

    try:
        content_raw = _read_evidence_file(evidence_file)
    except OSError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    content_lower = content_raw.lower()

    missing: List[str] = []

    _check_provider_labels(content_lower, missing)
    _check_database_boundaries(content_lower, missing)
    _check_persistence_proof(content_raw, missing)
    _check_urls(content_lower, missing)
    _check_operational_evidence(content_lower, missing)
    _check_hardening_foundation(content_raw, missing)
    check_separation_of_duties(content_raw, missing, require_explicit=enforce_sod)
    check_evidence_expiry(
        content_raw,
        missing,
        require_explicit=enforce_expiry,
        max_age_days=max_evidence_age_days,
        now=now,
    )

    if missing:
        print(
            "Staging promotion blocked. The following required baseline items "
            "are missing or not explicitly confirmed in the evidence file:"
        )
        for item in missing:
            print(f"  - {item}")
        sys.exit(1)

    print("Staging promotion verification passed. All baseline items are present.")
    sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify staging promotion baseline items in an evidence file.")
    parser.add_argument("evidence_file", help="Path to the release-candidate evidence Markdown file.")
    parser.add_argument(
        "--enforce-sod",
        action="store_true",
        help="Require explicit distinct Deploy operator and Promotion approver (H-P3-05).",
    )
    parser.add_argument(
        "--enforce-expiry",
        action="store_true",
        help="Require an explicit non-expired capture/expiry date on the RC evidence packet (H-P3-05).",
    )
    parser.add_argument(
        "--max-evidence-age-days",
        type=int,
        default=DEFAULT_MAX_EVIDENCE_AGE_DAYS,
        help=f"Maximum allowed evidence age in days (default: {DEFAULT_MAX_EVIDENCE_AGE_DAYS}).",
    )
    args = parser.parse_args()

    verify_staging_promotion(
        args.evidence_file,
        enforce_sod=args.enforce_sod,
        enforce_expiry=args.enforce_expiry,
        max_evidence_age_days=args.max_evidence_age_days,
    )
