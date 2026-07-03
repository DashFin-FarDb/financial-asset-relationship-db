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


def _check_persistence_proof(content: str, missing: List[str]) -> None:  # noqa: C901
    """Check for durability/persistence proofs by parsing JSON payloads."""
    # Try to find JSON blocks (markdown or bare curly braces)
    json_blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL | re.IGNORECASE)
    if not json_blocks:
        json_blocks = re.findall(r"(\{[\s\S]*?\})", content)

    found_all_in_one = False

    for block in json_blocks:
        try:
            data = json.loads(block)
            if not isinstance(data, dict):
                continue

            configured = data.get("graph_persistence_configured") is True

            graph_data = data.get("graph", {})
            enabled = False
            loaded = False
            source = False
            if isinstance(graph_data, dict):
                enabled = graph_data.get("persistence_enabled") is True
                loaded = graph_data.get("persistence_loaded") is True
                source = graph_data.get("startup_source") == "persisted"

            if configured and enabled and loaded and source:
                found_all_in_one = True
                break
        except json.JSONDecodeError:
            continue

    if not found_all_in_one:
        missing.append(
            "Complete durable graph proof in a single JSON block (requires graph_persistence_configured, graph.persistence_enabled, graph.persistence_loaded, and graph.startup_source == 'persisted')"
        )

    if (
        "durable preview" not in content
        and "non-durable preview" not in content
        and "preview durability label" not in content
    ):
        missing.append("Durable/non-durable preview label")


def _check_urls(content: str, missing: List[str]) -> None:
    """Check for valid, specific URLs and reject generic Actions URLs."""
    if "/actions/runs/" not in content and "/artifacts/" not in content:
        missing.append("Specific workflow run URL or artifact URL")

    if re.search(r"https://github\.com/[^/]+/[^/]+/actions/?(?:\s|\)|$)", content):
        missing.append("Generic Actions URLs are not allowed")


def _check_operational_evidence(content: str, missing: List[str]) -> None:
    """Check for smoke tests, ownership, and scanner summaries."""
    if "asset smoke evidence" not in content and "/api/assets?per_page=1" not in content:
        missing.append("Asset smoke evidence")

    if "hosted readiness" not in content:
        missing.append("hosted readiness")

    if "health json" not in content and "health.json" not in content:
        missing.append("health JSON")

    if "named owners" not in content and "deploy operator" not in content and "promotion approver" not in content:
        missing.append("Named owners (deploy, promotion, rollback, restore, persistence-verification)")

    if "scanner summary" not in content and "security scanner" not in content:
        missing.append("Scanner summary")

    # Simple heuristic for unredacted secrets/tokens
    if re.search(r"(?i)(password|secret|token|key)[\"']?\s*[:=]\s*[\"']?[^\s\*]{8,}", content):
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
        content = f.read().lower()

    missing: List[str] = []

    _check_provider_labels(content, missing)
    _check_database_boundaries(content, missing)
    _check_persistence_proof(content, missing)
    _check_urls(content, missing)
    _check_operational_evidence(content, missing)

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
