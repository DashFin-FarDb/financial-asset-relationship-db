"""Staging promotion verification script."""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List


def _check_provider_labels(content: str, missing: List[str]) -> None:
    """Check for provider and hosting labels."""
    if "supabase" not in content:
        missing.append("Supabase provider label")
    if "vercel mapping" not in content and "vercel project" not in content and "deployment url" not in content:
        missing.append("Vercel mapping (frontend/backend traffic)")


def _check_distinct_boundary(content: str, missing: List[str]) -> None:
    """Check for distinct graph boundary definitions."""
    distinct_confirmed = "asset_graph_database_url" in content and "distinct" in content
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


def _extract_balanced_json_objects(source: str) -> List[str]:
    """Extract brace-balanced JSON object candidates from source text."""
    blocks: List[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False

    for index, char in enumerate(source):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    blocks.append(source[start : index + 1])
                    start = None

    return blocks


def _check_persistence_proof(content_raw: str, missing: List[str]) -> None:
    """Check for durability/persistence proofs by parsing JSON payloads."""
    # First inspect fenced blocks, then fall back to brace-balanced objects in the full evidence text.
    fenced_blocks = re.findall(r"```(?:json)?[ \t]*\n(.*?)```", content_raw, re.IGNORECASE | re.DOTALL)
    json_blocks: List[str] = []
    for fenced_block in fenced_blocks:
        json_blocks.extend(_extract_balanced_json_objects(fenced_block))
    if not json_blocks:
        json_blocks = _extract_balanced_json_objects(content_raw)

    found_all_in_one = False
    for block in json_blocks:
        try:
            data = json.loads(block)
            if not isinstance(data, dict):
                continue

            obs = data.get("observed_fields")
            if isinstance(obs, dict):
                if (
                    obs.get("graph_persistence_configured") is True
                    and obs.get("graph.persistence_enabled") is True
                    and obs.get("graph.persistence_loaded") is True
                    and obs.get("graph.startup_source") == "persisted"
                ):
                    found_all_in_one = True
                    break
            else:
                graph_data = data.get("graph")
                if isinstance(graph_data, dict):
                    if (
                        data.get("graph_persistence_configured") is True
                        and graph_data.get("persistence_enabled") is True
                        and graph_data.get("persistence_loaded") is True
                        and graph_data.get("startup_source") == "persisted"
                    ):
                        found_all_in_one = True
                        break
        except json.JSONDecodeError:
            # Candidate blocks are best-effort extracts and may not be valid JSON; skip and keep scanning.
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
    evidence_path_obj = Path(evidence_file)
    if not evidence_path_obj.exists():
        print(f"Error: Evidence path {evidence_file} does not exist.")
        sys.exit(1)
    if not evidence_path_obj.is_file():
        print(f"Error: Evidence path {evidence_file} is not a regular file.")
        sys.exit(1)

    evidence_path = Path(evidence_file).resolve(strict=True)
    repo_root = Path(__file__).resolve().parent.parent
    is_relative = evidence_path.is_relative_to(repo_root)
    if not is_relative:
        print(f"Error: Invalid evidence file path {evidence_file}. Evidence must be within repo root {repo_root}.")
        sys.exit(1)
    with open(evidence_path, "r", encoding="utf-8") as f:
        content_raw = f.read()
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
