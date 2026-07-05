"""Staging promotion verification script."""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import List

SECRET_ASSIGNMENT_PATTERN = re.compile(
    "".join(
        (
            r"(?i)",
            r"(?:\b|_)(?:password|secret|token|key)(?:\b|_)",
            r"['\"]?[ \t]*[:=][ \t]*['\"]?",
            r"(?P<value>[a-z0-9+/=]{16,})",
        )
    )
)
DISTINCT_BOUNDARY_PATTERN = re.compile(
    "|".join(
        (
            r"\basset_graph_database_url\b[^\n]{0,80}\bdistinct\b",
            r"\bdistinct\b[^\n]{0,80}\basset_graph_database_url\b",
        )
    )
)


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

    if "asset_graph_database_url" not in content:
        missing.append("ASSET_GRAPH_DATABASE_URL boundary confirmation")

    _check_distinct_boundary(content, missing)
    _check_coordination_boundary(content, missing)


def _process_json_char(char: str, state: dict) -> bool:
    """Process a character for the JSON extraction state machine."""
    if state["in_string"]:
        return _process_json_string_char(char, state)
    if char == '"':
        state["in_string"] = True
        return False
    if char == "{":
        return _process_json_open_brace(state)
    return char == "}" and _process_json_close_brace(state)


def _process_json_string_char(char: str, state: dict) -> bool:
    """Process a character while the JSON scanner is inside a string."""
    if state["escaped"]:
        state["escaped"] = False
    elif char == "\\":
        state["escaped"] = True
    elif char == '"':
        state["in_string"] = False
    return False


def _process_json_open_brace(state: dict) -> bool:
    """Process an opening brace in the JSON scanner."""
    if state["depth"] == 0:
        state["start"] = state["index"]
    state["depth"] += 1
    return False


def _process_json_close_brace(state: dict) -> bool:
    """Process a closing brace in the JSON scanner."""
    if state["depth"] <= 0:
        return False
    state["depth"] -= 1
    return state["depth"] == 0 and state["start"] is not None


def _extract_balanced_json_objects(source: str) -> List[str]:
    """Extract brace-balanced JSON object candidates from source text."""
    blocks: List[str] = []
    state = {"start": None, "depth": 0, "in_string": False, "escaped": False, "index": 0}

    for index, char in enumerate(source):
        state["index"] = index
        if _process_json_char(char, state):
            blocks.append(source[state["start"] : index + 1])
            state["start"] = None

    return blocks


def _validate_persistence_data(data: dict) -> bool:
    """Validate a parsed JSON dict for persistence proofs."""
    if _has_expected_values(
        data.get("observed_fields"),
        {
            "graph_persistence_configured": True,
            "graph.persistence_enabled": True,
            "graph.persistence_loaded": True,
            "graph.startup_source": "persisted",
        },
    ):
        return True

    if data.get("graph_persistence_configured") is True and _has_expected_values(
        data.get("graph"),
        {
            "persistence_enabled": True,
            "persistence_loaded": True,
            "startup_source": "persisted",
        },
    ):
        return True

    return False


def _has_expected_values(candidate: object, expected_values: dict[str, object]) -> bool:
    """Return whether a dict candidate contains all expected key/value pairs."""
    return isinstance(candidate, dict) and all(candidate.get(key) == value for key, value in expected_values.items())


def _extract_json_blocks(content_raw: str) -> List[str]:
    """Extract JSON blocks from markdown fences or brace-balanced fallbacks."""
    fenced_blocks = re.findall(r"```(?:json)?[ \t]*\n(.*?)```", content_raw, re.IGNORECASE | re.DOTALL)
    json_blocks: List[str] = []
    for fenced_block in fenced_blocks:
        json_blocks.extend(_extract_balanced_json_objects(fenced_block))
    if not json_blocks:
        json_blocks = _extract_balanced_json_objects(content_raw)
    return json_blocks


def _check_persistence_proof(content_raw: str, missing: List[str]) -> None:
    """Check for durability/persistence proofs by parsing JSON payloads."""
    json_blocks = _extract_json_blocks(content_raw)

    found_all_in_one = False
    for block in json_blocks:
        try:
            data = json.loads(block)
            if isinstance(data, dict) and _validate_persistence_data(data):
                found_all_in_one = True
                break
        except json.JSONDecodeError:
            continue

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

    generic_actions_patterns = [
        r"https://github\.com/[^/\s)]+/[^/\s)]+/actions(?:$|[\s)])",
        r"https://github\.com/[^/\s)]+/[^/\s)]+/actions/(?!runs/)[^\s)]+",
    ]
    if any(re.search(pattern, content, flags=re.IGNORECASE) for pattern in generic_actions_patterns):
        missing.append("Generic Actions URLs are not allowed")


def _check_operational_evidence(content: str, missing: List[str]) -> None:
    """Check for smoke tests, ownership, and scanner summaries."""
    checks = [
        (("asset smoke evidence", "/api/assets?per_page=1"), "Asset smoke evidence"),
        (("hosted readiness --require-persistence",), "hosted readiness --require-persistence command"),
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

    if _contains_unredacted_secret(content):
        missing.append("Non-redacted evidence found (secrets/tokens must be redacted)")


def _contains_unredacted_secret(content: str) -> bool:
    """Return whether evidence contains a likely non-redacted secret assignment."""
    for match in SECRET_ASSIGNMENT_PATTERN.finditer(content):
        value = match.group("value").lower()
        if "redacted" in value or set(value) == {"x"}:
            continue
        return True
    return False


def _read_evidence_file(evidence_file: str) -> str:
    """Read an evidence file within the repo without following final-component symlinks."""
    repo_root = Path(__file__).resolve().parent.parent
    requested_path = Path(evidence_file)
    evidence_path = requested_path if requested_path.is_absolute() else repo_root / requested_path
    absolute_path = Path(os.path.abspath(evidence_path))

    if not absolute_path.is_relative_to(repo_root):
        print(f"Error: Invalid evidence file path {evidence_file}. Evidence must be within repo root {repo_root}.")
        sys.exit(1)

    if absolute_path.is_symlink():
        print(f"Error: Evidence path {evidence_file} is a symlink.")
        sys.exit(1)

    normalized_path = absolute_path.resolve(strict=False)

    if not normalized_path.is_relative_to(repo_root):
        print(f"Error: Invalid evidence file path {evidence_file}. Evidence must be within repo root {repo_root}.")
        sys.exit(1)

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(absolute_path, flags)
    except FileNotFoundError:
        print(f"Error: Evidence path {evidence_file} does not exist.")
        sys.exit(1)
    except OSError as exc:
        print(f"Error: Unable to open evidence path {evidence_file}: {exc}")
        sys.exit(1)

    file_stat = os.fstat(fd)
    if not stat_is_regular_file(file_stat.st_mode):
        os.close(fd)
        print(f"Error: Evidence path {evidence_file} is not a regular file.")
        sys.exit(1)

    with os.fdopen(fd, "r", encoding="utf-8") as f:
        return f.read()


def stat_is_regular_file(mode: int) -> bool:
    """Return whether a stat mode represents a regular file."""
    return (mode & 0o170000) == 0o100000


def verify_staging_promotion(evidence_file: str) -> None:
    """Verify baseline items in a staging promotion evidence file."""
    content_raw = _read_evidence_file(evidence_file)
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
