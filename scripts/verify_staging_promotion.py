"""Staging promotion verification script."""

import argparse
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import List, TypedDict

REPO_ROOT = Path(__file__).resolve().parent.parent


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
    distinct_confirmed = (
        "distinct asset_graph_database_url" in content
        or "asset_graph_database_url distinct" in content
        or "shared-boundary statement" in content
        or "approved exception" in content
    )
    if not distinct_confirmed:
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


def verify_staging_promotion(evidence_file: str) -> None:
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
    args = parser.parse_args()

    verify_staging_promotion(args.evidence_file)
