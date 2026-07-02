"""Staging promotion verification script."""

import argparse
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


def _check_database_boundaries(content: str, missing: List[str]) -> None:
    """Check for required database boundary definitions."""
    if not re.search(r"\bdatabase_url\b", content):
        missing.append("DATABASE_URL boundary confirmation")

    if "asset_graph_database_url" not in content:
        missing.append("ASSET_GRAPH_DATABASE_URL boundary confirmation")

    if (
        "distinct asset_graph_database_url" not in content
        and "asset_graph_database_url distinct" not in content
        and "approved exception" not in content
        and "shared-boundary statement" not in content
    ):
        missing.append("Distinct ASSET_GRAPH_DATABASE_URL boundary or approved exception")

    if (
        "coordination_database_url" not in content
        and "shared-boundary statement" not in content
        and "fallback boundary" not in content
    ):
        missing.append("Coordination boundary or explicit shared-boundary statement")


def _check_persistence_proof(content: str, missing: List[str]) -> None:
    """Check for durability/persistence proofs."""
    if (
        "persistence_loaded == true" not in content
        and 'startup_source == "persisted"' not in content
        and 'startup_source="persisted"' not in content
        and '"persistence_loaded": true' not in content
        and '"startup_source": "persisted"' not in content
        and "persistence-loaded proof" not in content
    ):
        missing.append("Persistence-loaded proof (graph.persistence_loaded == true)")

    if (
        "durable preview" not in content
        and "non-durable preview" not in content
        and "preview durability label" not in content
    ):
        missing.append("Durable/non-durable preview label")


def _check_operational_evidence(content: str, missing: List[str]) -> None:
    """Check for smoke tests, ownership, and scanner summaries."""
    if "asset smoke evidence" not in content and "/api/assets?per_page=1" not in content:
        missing.append("Asset smoke evidence")

    if "named owners" not in content and "deploy operator" not in content and "promotion approver" not in content:
        missing.append("Named owners (deploy, promotion, rollback, restore, persistence-verification)")

    if "scanner summary" not in content and "security scanner" not in content:
        missing.append("Scanner summary")


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
    if not evidence_path.is_relative_to(repo_root):
        print(f"Error: Invalid evidence file path {evidence_file}.")
        sys.exit(1)
    with open(evidence_path, "r", encoding="utf-8") as f:
        content = f.read().lower()

    missing: List[str] = []

    _check_provider_labels(content, missing)
    _check_database_boundaries(content, missing)
    _check_persistence_proof(content, missing)
    _check_operational_evidence(content, missing)

    if missing:
        print(
            "Staging promotion blocked. The following required baseline items are missing or not explicitly confirmed in the evidence file:"
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
