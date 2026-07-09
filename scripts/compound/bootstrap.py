"""Bounded bootstrap seed for the architecture-expert observation ledger."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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
GITHUB_API_URL = "https://api.github.com"
MAX_PR_SCRAPE_LIMIT = 100

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
    if not 1 <= limit <= MAX_PR_SCRAPE_LIMIT:
        raise ValueError(f"pr_limit must be between 1 and {MAX_PR_SCRAPE_LIMIT}")
    return limit


def _updated_since_filter(cutoff: str) -> str:
    datetime.strptime(cutoff, "%Y-%m-%d")
    return f"updated:>={cutoff}"


def _validate_seed_domains(domains: tuple[str, ...]) -> None:
    """Validate seed document domain names."""
    for domain in domains:
        if domain not in DOMAINS:
            raise SchemaError(f"Invalid seed domain {domain}")


def _doc_seed_payload(rel_path: str, domains: tuple[str, ...]) -> dict[str, Any]:
    """Build one landed bootstrap observation payload from a seed doc path."""
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


def _seed_doc(repo_root: Path, rel_path: str, domains: tuple[str, ...]) -> str:
    """Append one seed-doc observation or return a skip message."""
    path = repo_root / rel_path
    if not path.exists():
        return f"skip missing seed doc: {rel_path}"
    _validate_seed_domains(domains)
    _, message = append_observation(_doc_seed_payload(rel_path, domains), repo_root=repo_root)
    return f"{rel_path}: {message}"


def seed_from_docs(repo_root: Path) -> list[str]:
    """Emit landed bootstrap observations from existing allowlisted seed docs."""
    return [_seed_doc(repo_root, rel_path, domains) for rel_path, domains in SEED_DOCS]


def _github_repository() -> str | None:
    """Return owner/repo from the Actions environment when valid."""
    repository = os.getenv("GITHUB_REPOSITORY", "")
    owner, separator, name = repository.partition("/")
    if not separator or not owner or not name:
        return None
    return repository


def _github_headers() -> dict[str, str]:
    """Return GitHub REST headers for optional token-authenticated reads."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "financial-asset-relationship-db-compound-bootstrap",
    }
    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_github_json(url: str) -> Any | None:
    """Fetch JSON from GitHub REST, returning None on unavailable API responses."""
    request = Request(url, headers=_github_headers())
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _fetch_pr_files(repository: str, number: int) -> list[dict[str, str]]:
    query = urlencode({"per_page": "100"})
    files = _fetch_github_json(f"{GITHUB_API_URL}/repos/{repository}/pulls/{number}/files?{query}")
    if not isinstance(files, list):
        return []
    return [
        {"path": str(file_entry["filename"])}
        for file_entry in files
        if isinstance(file_entry, dict) and file_entry.get("filename")
    ]


def _normalize_pr_entry(repository: str, pr: dict[str, Any]) -> dict[str, Any] | None:
    number = pr.get("number")
    if not isinstance(number, int):
        return None
    return {
        "number": number,
        "title": pr.get("title"),
        "state": pr.get("state"),
        "mergedAt": pr.get("merged_at"),
        "updatedAt": pr.get("updated_at"),
        "labels": pr.get("labels", []),
        "files": _fetch_pr_files(repository, number),
    }


def _fetch_pr_list(*, limit: int, updated_since: str | None = None) -> Any | None:
    repository = _github_repository()
    if repository is None:
        return None
    cutoff = _updated_since_filter(updated_since).removeprefix("updated:>=") if updated_since is not None else None
    query = urlencode(
        {"state": "all", "per_page": str(_bounded_pr_limit(limit)), "sort": "updated", "direction": "desc"}
    )
    pull_requests = _fetch_github_json(f"{GITHUB_API_URL}/repos/{repository}/pulls?{query}")
    if not isinstance(pull_requests, list):
        return None
    return [
        normalized
        for pr in pull_requests
        if isinstance(pr, dict) and (cutoff is None or str(pr.get("updated_at", ""))[:10] >= cutoff)
        if (normalized := _normalize_pr_entry(repository, pr)) is not None
    ]


def _observation_status_for_pr(pr: dict[str, Any]) -> str:
    """Return landed for merged PRs and provisional for open/unmerged PRs."""
    state = str(pr.get("state") or "").upper()
    merged = bool(pr.get("mergedAt"))
    return ObservationStatus.LANDED.value if merged or state == "MERGED" else ObservationStatus.PROVISIONAL.value


def _paths_from_pr_files(file_entries: Any) -> list[str]:
    """Extract changed paths from gh's PR file payload variants."""
    return [path for entry in file_entries or [] if (path := _path_from_pr_file_entry(entry)) is not None]


def _path_from_pr_file_entry(entry: Any) -> str | None:
    """Extract one path from a gh PR file entry variant."""
    if isinstance(entry, str):
        return entry
    if not isinstance(entry, dict):
        return None
    path = entry.get("path") or entry.get("filename")
    return str(path) if path else None


def _payload_from_pr(pr: dict[str, Any], number: int) -> dict[str, Any]:
    """Build a bootstrap observation payload from one gh PR item."""
    title = str(pr.get("title") or f"PR #{number}")
    paths = _paths_from_pr_files(pr.get("files"))
    return {
        "observation_id": f"bootstrap-pr-{number}",
        "source": ObservationSource.BOOTSTRAP.value,
        "event_type": "seed.pull_request",
        "status": _observation_status_for_pr(pr),
        "primary_ref": f"pr:{number}",
        "summary": title[:240],
        "domains": list(detect_domains_from_paths(paths)),
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
    data = _fetch_pr_list(limit=limit, updated_since=cutoff)
    if data is None:
        data = _fetch_pr_list(limit=limit)
    if data is None:
        return ["PR scrape skipped: gh unavailable or failed"]

    messages: list[str] = []
    for pr in data:
        number = pr.get("number")
        if not isinstance(number, int):
            continue
        payload = _payload_from_pr(pr, number)
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
