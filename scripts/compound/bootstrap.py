"""Bounded bootstrap seed for the architecture-expert observation ledger."""

from __future__ import annotations

import argparse
import json
import re
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
GH_TIMEOUT_SECONDS = 60
MAX_PR_LIMIT = 100
GH_SEARCH_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

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


def _bounded_pr_limit(limit: int) -> int:
    if limit < 1 or limit > MAX_PR_LIMIT:
        raise SchemaError(f"pr_limit must be between 1 and {MAX_PR_LIMIT}")
    return limit


def _validated_updated_since(updated_since: str | None) -> str | None:
    """Constrain the gh search date to the YYYY-MM-DD value this module creates."""
    if updated_since is None:
        return None
    if not GH_SEARCH_DATE_PATTERN.fullmatch(updated_since):
        raise SchemaError("updated_since must use YYYY-MM-DD format")
    return updated_since


def seed_from_docs(repo_root: Path) -> list[str]:
    """Emit landed bootstrap observations from existing allowlisted seed docs."""
    messages: list[str] = []
    for rel_path, domains in SEED_DOCS:
        path = repo_root / rel_path
        if not path.exists():
            messages.append(f"skip missing seed doc: {rel_path}")
            continue
        _validate_seed_domains(domains)
        _, message = append_observation(_seed_doc_payload(rel_path, domains), repo_root=repo_root)
        messages.append(f"{rel_path}: {message}")
    return messages


def _validate_seed_domains(domains: tuple[str, ...]) -> None:
    """Validate hard-coded seed doc domains at runtime."""
    for domain in domains:
        if domain not in DOMAINS:
            raise SchemaError(f"Invalid seed domain {domain}")


def _seed_doc_payload(rel_path: str, domains: tuple[str, ...]) -> dict[str, Any]:
    """Build one landed bootstrap observation for a seed document."""
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


def _gh_pr_list(limit: int, *, updated_since: str | None = None) -> Any | None:
    bounded_limit = _bounded_pr_limit(limit)
    search_date = _validated_updated_since(updated_since)
    if shutil.which("gh") is None:
        return None
    json_fields = "number,title,state,mergedAt,updatedAt,labels,files"
    # Keep the subprocess command constant; apply operator-provided filters in Python.
    command = [
        "gh",
        "pr",
        "list",
        "--state",
        "all",
        "--limit",
        str(MAX_PR_LIMIT),
        "--json",
        json_fields,
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=GH_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None
    return _select_recent_prs(data, limit=bounded_limit, updated_since=search_date)


def _is_pr_mapping(item: Any) -> bool:
    """Return True when gh returned a PR object shape."""
    return isinstance(item, dict)


def _updated_on_or_after(pr: dict[str, Any], updated_since: str | None) -> bool:
    """Return True when the PR passes the optional YYYY-MM-DD updated filter."""
    if updated_since is None:
        return True
    return str(pr.get("updatedAt") or "")[:10] >= updated_since


def _select_recent_prs(data: list[Any], *, limit: int, updated_since: str | None = None) -> list[Any]:
    """Apply bounded PR scrape filters after gh returns JSON."""
    selected: list[Any] = []
    for item in data:
        if not _is_pr_mapping(item) or not _updated_on_or_after(item, updated_since):
            continue
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected


def _pr_status(pr: dict[str, Any]) -> str:
    """Return landed for merged PRs, otherwise provisional."""
    state = str(pr.get("state") or "").upper()
    merged = bool(pr.get("mergedAt"))
    return ObservationStatus.LANDED.value if merged or state == "MERGED" else ObservationStatus.PROVISIONAL.value


def _path_from_file_entry(entry: Any) -> str | None:
    """Normalize one gh file entry shape to a changed path."""
    if isinstance(entry, str):
        return entry
    if not isinstance(entry, dict):
        return None
    path = entry.get("path") or entry.get("filename")
    return str(path) if path else None


def _pr_paths(pr: dict[str, Any]) -> list[str]:
    """Extract changed paths from gh's mixed file entry shapes."""
    return [path for entry in pr.get("files") or [] if (path := _path_from_file_entry(entry))]


def _pr_payload(pr: dict[str, Any], number: int) -> dict[str, Any]:
    """Build one bootstrap observation payload from a gh PR object."""
    title = str(pr.get("title") or f"PR #{number}")
    return {
        "observation_id": f"bootstrap-pr-{number}",
        "source": ObservationSource.BOOTSTRAP.value,
        "event_type": "seed.pull_request",
        "status": _pr_status(pr),
        "primary_ref": f"pr:{number}",
        "summary": title[:240],
        "domains": list(detect_domains_from_paths(_pr_paths(pr))),
        "refs": [f"pr:{number}"],
        "evidence_pointers": [f"github:pr:{number}"],
        "created_at": _now(),
    }


def scrape_recent_prs(repo_root: Path, *, limit: int = 50, days: int = 30) -> list[str]:
    """Bounded PR scrape via gh; non-fatal when gh is unavailable.

    Prefers PRs updated within ``days`` (plan A9); falls back to last ``limit``
    PRs when the search filter is unsupported.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    data = _gh_pr_list(limit, updated_since=cutoff)
    if data is None:
        data = _gh_pr_list(limit)
    if data is None:
        return ["PR scrape skipped: gh unavailable or failed"]

    messages: list[str] = []
    for pr in data:
        number = pr.get("number")
        if not isinstance(number, int):
            continue
        _, message = append_observation(_pr_payload(pr, number), repo_root=repo_root)
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
