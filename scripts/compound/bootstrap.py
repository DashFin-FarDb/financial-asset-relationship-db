"""Bounded bootstrap seed for the architecture-expert observation ledger."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_SCRIPTS_ROOT = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from compound.append_observation import append_observation  # noqa: E402
from compound.schema import (  # noqa: E402
    DOMAINS,
    ObservationSource,
    ObservationStatus,
    SchemaError,
    detect_domains_from_paths,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Seed docs → primary domain mapping (read-only inputs; never written).
SEED_DOCS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("docs/adr/0001-production-architecture.md", ("architecture",)),
    ("docs/graph-persistence-lifecycle-seam.md", ("persistence", "architecture")),
    ("docs/phase-3-computation-layout-boundary-audit.md", ("architecture",)),
    ("docs/tech_spec.md", ("api",)),
    ("docs/graph-persistence-design.md", ("persistence",)),
    (".github/AUTOMATION_SCOPE_POLICY.md", ("ci-guardrails",)),
    (".github/AI_AGENT_GUARDRAILS.md", ("ci-guardrails",)),
    ("docs/PR_SCOPE_GUARDRAILS.md", ("ci-guardrails",)),
    ("docs/reconciliation-discovery-map.md", ("rebuild-reconciliation",)),
    ("docs/reconciliation-engine.md", ("rebuild-reconciliation",)),
    ("docs/governance/state-machine-and-operating-authority.md", ("rebuild-reconciliation",)),
    ("docs/staging-deployment-operating-baseline.md", ("deployment",)),
    ("docs/release-evidence-pack.md", ("deployment",)),
    ("docs/enterprise-readiness-index.md", ("architecture", "deployment")),
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def seed_from_docs(repo_root: Path) -> list[str]:
    """Emit landed bootstrap observations from existing allowlisted seed docs."""
    messages: list[str] = []
    for rel_path, domains in SEED_DOCS:
        path = repo_root / rel_path
        if not path.exists():
            messages.append(f"skip missing seed doc: {rel_path}")
            continue
        for domain in domains:
            if domain not in DOMAINS:
                raise SchemaError(f"Invalid seed domain {domain}")
        payload = {
            "observation_id": f"bootstrap-doc-{Path(rel_path).stem}",
            "source": ObservationSource.BOOTSTRAP.value,
            "event_type": "seed.doc",
            "status": ObservationStatus.LANDED.value,
            "primary_ref": f"doc:{rel_path}",
            "summary": f"Bootstrap seed from {rel_path}",
            "domains": list(domains),
            "refs": [rel_path],
            "evidence_pointers": [rel_path],
            "created_at": _now(),
        }
        _, message = append_observation(payload, repo_root=repo_root)
        messages.append(f"{rel_path}: {message}")
    return messages


def _gh_json(args: list[str]) -> Any | None:
    try:
        completed = subprocess.run(
            ["gh", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None


def scrape_recent_prs(repo_root: Path, *, limit: int = 50, days: int = 30) -> list[str]:
    """Bounded PR scrape via gh; non-fatal when gh is unavailable.

    Prefers PRs updated within ``days`` (plan A9); falls back to last ``limit``
    PRs when the search filter is unsupported.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    json_fields = "number,title,state,mergedAt,updatedAt,labels,files"
    data = _gh_json(
        [
            "pr",
            "list",
            "--state",
            "all",
            "--limit",
            str(limit),
            "--search",
            f"updated:>={cutoff}",
            "--json",
            json_fields,
        ]
    )
    if data is None:
        data = _gh_json(
            [
                "pr",
                "list",
                "--state",
                "all",
                "--limit",
                str(limit),
                "--json",
                json_fields,
            ]
        )
    if data is None:
        return ["PR scrape skipped: gh unavailable or failed"]

    messages: list[str] = []
    for pr in data:
        number = pr.get("number")
        if not isinstance(number, int):
            continue
        state = str(pr.get("state") or "").upper()
        merged = bool(pr.get("mergedAt"))
        status = ObservationStatus.LANDED.value if merged or state == "MERGED" else ObservationStatus.PROVISIONAL.value
        title = str(pr.get("title") or f"PR #{number}")
        file_entries = pr.get("files") or []
        paths: list[str] = []
        for entry in file_entries:
            if isinstance(entry, str):
                paths.append(entry)
            elif isinstance(entry, dict) and entry.get("path"):
                paths.append(str(entry["path"]))
            elif isinstance(entry, dict) and entry.get("filename"):
                paths.append(str(entry["filename"]))
        domains = list(detect_domains_from_paths(paths))
        payload = {
            "observation_id": f"bootstrap-pr-{number}",
            "source": ObservationSource.BOOTSTRAP.value,
            "event_type": "seed.pull_request",
            "status": status,
            "primary_ref": f"pr:{number}",
            "summary": title[:240],
            "domains": domains,
            "refs": [f"pr:{number}"],
            "evidence_pointers": [f"github:pr:{number}"],
            "created_at": _now(),
        }
        _, message = append_observation(payload, repo_root=repo_root)
        messages.append(f"pr:{number}: {message}")
    return messages


def run_bootstrap(repo_root: Path, *, scrape_prs: bool = True, pr_limit: int = 50) -> list[str]:
    """Run doc seed then optional bounded PR scrape."""
    messages = seed_from_docs(repo_root)
    if scrape_prs:
        messages.extend(scrape_recent_prs(repo_root, limit=pr_limit))
    return messages


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for bounded bootstrap."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--no-prs", action="store_true", help="Skip gh PR scrape")
    parser.add_argument("--pr-limit", type=int, default=50)
    args = parser.parse_args(argv)
    try:
        for line in run_bootstrap(args.repo_root, scrape_prs=not args.no_prs, pr_limit=args.pr_limit):
            print(line)
        return 0
    except (SchemaError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
