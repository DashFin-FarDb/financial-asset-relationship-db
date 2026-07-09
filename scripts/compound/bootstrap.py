"""Bounded bootstrap seed for the architecture-expert observation ledger."""

from __future__ import annotations

import argparse
import json
import shutil
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
GH_PR_JSON_FIELDS = "number,title,state,mergedAt,updatedAt,labels,files"
GH_PR_LIMIT = "50"
MIN_LOOKBACK_DAYS = 1
MAX_LOOKBACK_DAYS = 365

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
        _, message = append_observation(_seed_doc_payload(rel_path, domains), repo_root=repo_root)
        messages.append(f"{rel_path}: {message}")
    return messages


def _seed_doc_payload(rel_path: str, domains: tuple[str, ...]) -> dict[str, Any]:
    """Build a landed seed-doc observation payload."""
    invalid = [domain for domain in domains if domain not in DOMAINS]
    if invalid:
        raise SchemaError(f"Invalid seed domain {invalid[0]}")
    return {
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


def _bounded_int(value: int, *, minimum: int, maximum: int) -> int:
    """Clamp CLI-influenced integer values before using them in external commands."""
    return min(max(value, minimum), maximum)


def _gh_pr_list_json(*, cutoff: str | None = None) -> Any | None:
    """Run the single allowlisted gh command used by bootstrap PR scraping."""
    gh_path = shutil.which("gh")
    if gh_path is None:
        return None
    command: list[str] = [
        gh_path,
        "pr",
        "list",
        "--state",
        "all",
        "--limit",
        GH_PR_LIMIT,
    ]
    if cutoff is not None:
        command.extend(["--search", f"updated:>={cutoff}"])
    command.extend(["--json", GH_PR_JSON_FIELDS])
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )  # nosec B603 - command shape is allowlisted and args are clamped.
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None


def _pr_file_paths(pr: dict[str, Any]) -> list[str]:
    """Extract changed paths from gh PR JSON across gh output shapes."""
    return [path for entry in pr.get("files") or [] if (path := _file_path_from_pr_entry(entry)) is not None]


def _file_path_from_pr_entry(entry: Any) -> str | None:
    """Return a path from one gh PR file entry shape."""
    if isinstance(entry, str):
        return entry
    if not isinstance(entry, dict):
        return None
    path = entry.get("path") or entry.get("filename")
    return str(path) if path else None


def _pr_payload(pr: dict[str, Any]) -> dict[str, Any] | None:
    """Build a bootstrap observation payload from one gh PR JSON object."""
    number = pr.get("number")
    if not isinstance(number, int):
        return None
    state = str(pr.get("state") or "").upper()
    merged = bool(pr.get("mergedAt"))
    status = ObservationStatus.LANDED.value if merged or state == "MERGED" else ObservationStatus.PROVISIONAL.value
    return {
        "observation_id": f"bootstrap-pr-{number}",
        "source": ObservationSource.BOOTSTRAP.value,
        "event_type": "seed.pull_request",
        "status": status,
        "primary_ref": f"pr:{number}",
        "summary": str(pr.get("title") or f"PR #{number}")[:240],
        "domains": list(detect_domains_from_paths(_pr_file_paths(pr))),
        "refs": [f"pr:{number}"],
        "evidence_pointers": [f"github:pr:{number}"],
        "created_at": _now(),
    }


def scrape_recent_prs(repo_root: Path, *, days: int = 30) -> list[str]:
    """Bounded PR scrape via gh; non-fatal when gh is unavailable.

    Prefers PRs updated within ``days`` (plan A9); falls back to last fixed-limit
    PRs when the search filter is unsupported.
    """
    bounded_days = _bounded_int(days, minimum=MIN_LOOKBACK_DAYS, maximum=MAX_LOOKBACK_DAYS)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=bounded_days)).strftime("%Y-%m-%d")
    data = _gh_pr_list_json(cutoff=cutoff)
    if data is None:
        data = _gh_pr_list_json()
    if data is None:
        return ["PR scrape skipped: gh unavailable or failed"]

    messages: list[str] = []
    for pr in data:
        payload = _pr_payload(pr)
        if payload is None:
            continue
        _, message = append_observation(payload, repo_root=repo_root)
        messages.append(f"{payload['primary_ref']}: {message}")
    return messages


def run_bootstrap(repo_root: Path, *, scrape_prs: bool = True) -> list[str]:
    """Run doc seed then optional bounded PR scrape."""
    messages = seed_from_docs(repo_root)
    if scrape_prs:
        messages.extend(scrape_recent_prs(repo_root))
    return messages


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for bounded bootstrap."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--no-prs", action="store_true", help="Skip gh PR scrape")
    args = parser.parse_args(argv)
    try:
        for line in run_bootstrap(args.repo_root, scrape_prs=not args.no_prs):
            print(line)
        return 0
    except (SchemaError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
