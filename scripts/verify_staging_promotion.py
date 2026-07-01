"""Staging promotion verification script."""

import argparse
import sys
from pathlib import Path


def verify_staging_promotion(evidence_file: str):
    """Verify baseline items in a staging promotion evidence file."""
    if not Path(evidence_file).exists():
        print(f"Error: Evidence file {evidence_file} not found.")
        sys.exit(1)

    evidence_path = Path(evidence_file).resolve(strict=True)
    if not evidence_path.is_relative_to(Path.cwd().resolve()):
        print(f"Error: Invalid evidence file path {evidence_file}.")
        sys.exit(1)
    with open(evidence_path, "r", encoding="utf-8") as f:
        content = f.read().lower()

    missing = []

    # 1. Supabase provider label
    if "supabase" not in content:
        missing.append("Supabase provider label")

    # 2. DATABASE_URL boundary
    if "database_url" not in content:
        missing.append("DATABASE_URL boundary confirmation")

    # 3. distinct ASSET_GRAPH_DATABASE_URL boundary (or approved exception)
    if "asset_graph_database_url" not in content:
        missing.append("ASSET_GRAPH_DATABASE_URL boundary confirmation")

    if (
        "distinct asset_graph_database_url" not in content
        and "asset_graph_database_url distinct" not in content
        and "exception" not in content
        and "shared-boundary statement" not in content
    ):
        missing.append("Distinct ASSET_GRAPH_DATABASE_URL boundary or approved exception")

    # 4. coordination boundary or explicit shared-boundary statement
    if (
        "coordination_database_url" not in content
        and "shared-boundary statement" not in content
        and "fallback boundary" not in content
    ):
        missing.append("Coordination boundary or explicit shared-boundary statement")

    # 5. Vercel mapping
    if "vercel mapping" not in content and "vercel project" not in content and "deployment url" not in content:
        missing.append("Vercel mapping (frontend/backend traffic)")

    # 6. durable/non-durable preview label
    if (
        "durable preview" not in content
        and "non-durable preview" not in content
        and "preview durability label" not in content
    ):
        missing.append("Durable/non-durable preview label")

    # 7. asset smoke evidence
    if "asset smoke evidence" not in content and "/api/assets?per_page=1" not in content:
        missing.append("Asset smoke evidence")

    # 8. named owners
    if "named owners" not in content and "deploy operator" not in content and "promotion approver" not in content:
        missing.append("Named owners (deploy, promotion, rollback, restore, persistence-verification)")

    # 9. scanner summary
    if "scanner summary" not in content and "security scanner" not in content:
        missing.append("Scanner summary")

    # 10. persistence-loaded proof
    if (
        "persistence_loaded == true" not in content
        and 'startup_source == "persisted"' not in content
        and "persistence-loaded proof" not in content
    ):
        missing.append("Persistence-loaded proof (graph.persistence_loaded == true)")

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
