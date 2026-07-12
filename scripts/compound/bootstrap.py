"""Bounded bootstrap seed for the architecture-expert observation ledger."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

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

# Allow only fixed gh subcommands/flags and bounded tokens (no shell metacharacters).
_GH_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9_.:>=,\-]+$")
_GH_PR_JSON_FIELDS = "number,title,state,mergedAt,updatedAt,labels"
_PR_LIMIT_MIN = 1
_PR_LIMIT_MAX = 100

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
        messages.append(_seed_one_doc(repo_root, rel_path, domains))
    return messages


def _seed_one_doc(repo_root: Path, rel_path: str, domains: tuple[str, ...]) -> str:
    """Seed a single allowlisted doc into the ledger."""
    path = repo_root / rel_path
    if not path.exists():
        return f"skip missing seed doc: {rel_path}"
    for domain in domains:
        if domain not in DOMAINS:
            raise SchemaError(f"Invalid seed domain {domain}")
    obs_slug = rel_path.replace("\\", "/").replace("/", "__")
    payload = {
        "observation_id": f"bootstrap-doc-{obs_slug}",
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
    return f"{rel_path}: {message}"


def _clamp_pr_limit(limit: int) -> int:
    """Clamp PR scrape limit to a safe positive range."""
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise SchemaError(f"pr limit must be an int, got {type(limit).__name__}")
    return max(_PR_LIMIT_MIN, min(_PR_LIMIT_MAX, limit))


def _validate_gh_args(args: list[str]) -> list[str]:
    """Reject unsafe tokens before invoking ``gh`` (Sonar S8705)."""
    if not args or args[0] != "pr":
        raise SchemaError("Only `gh pr ...` invocations are allowed")
    validated: list[str] = []
    for arg in args:
        if not isinstance(arg, str) or not arg or not _GH_SAFE_TOKEN.fullmatch(arg):
            raise SchemaError(f"Rejected unsafe gh argument: {arg!r}")
        validated.append(arg)
    return validated


def _gh_json(args: list[str]) -> Any | None:
    try:
        safe_args = _validate_gh_args(args)
    except SchemaError:
        return None
    try:
        completed = subprocess.run(
            ["gh", *safe_args],
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


def _gh_pr_list_args(*, limit: int, search: str | None = None) -> list[str]:
    """Build ``gh pr list`` args shared by search and fallback paths."""
    safe_limit = _clamp_pr_limit(limit)
    args = [
        "pr",
        "list",
        "--state",
        "all",
        "--limit",
        str(safe_limit),
        "--json",
        _GH_PR_JSON_FIELDS,
    ]
    if search is not None:
        if not _GH_SAFE_TOKEN.fullmatch(search):
            raise SchemaError(f"Rejected unsafe gh search filter: {search!r}")
        args.extend(["--search", search])
    return args


def _paths_from_pr_files(file_entries: Any) -> list[str]:
    """Extract changed file paths from a gh PR ``files`` payload."""
    paths: list[str] = []
    for entry in file_entries or []:
        if isinstance(entry, str):
            paths.append(entry)
        elif isinstance(entry, dict):
            raw = entry.get("path") or entry.get("filename")
            if raw:
                paths.append(str(raw))
    return paths


def _status_from_pr(pr: Mapping[str, Any]) -> str:
    """Map gh PR state/mergedAt to landed vs provisional."""
    state = str(pr.get("state") or "").upper()
    merged = bool(pr.get("mergedAt"))
    if merged or state == "MERGED":
        return ObservationStatus.LANDED.value
    return ObservationStatus.PROVISIONAL.value


def _fetch_pr_files(number: int) -> list[str]:
    """Fetch changed paths for one PR via ``gh pr view --json files``."""
    data = _gh_json(["pr", "view", str(number), "--json", "files"])
    if not isinstance(data, dict):
        return []
    return _paths_from_pr_files(data.get("files"))


def _payload_from_pr(pr: Mapping[str, Any]) -> dict[str, Any] | None:
    """Build a bootstrap observation payload from one gh PR object."""
    number = pr.get("number")
    if not isinstance(number, int):
        return None
    title = str(pr.get("title") or f"PR #{number}")
    file_paths = _paths_from_pr_files(pr.get("files"))
    if not file_paths:
        file_paths = _fetch_pr_files(number)
    domains = list(detect_domains_from_paths(file_paths))
    return {
        "observation_id": f"bootstrap-pr-{number}",
        "source": ObservationSource.BOOTSTRAP.value,
        "event_type": "seed.pull_request",
        "status": _status_from_pr(pr),
        "primary_ref": f"pr:{number}",
        "summary": title[:240],
        "domains": domains,
        "refs": [f"pr:{number}"],
        "evidence_pointers": [f"github:pr:{number}"],
        "created_at": _now(),
    }


def scrape_recent_prs(repo_root: Path, *, limit: int = 50, days: int = 30) -> list[str]:
    """Bounded PR scrape via gh; non-fatal when gh is unavailable.

    Prefers PRs updated within ``days`` (plan A9); falls back to last ``limit``
    PRs when the search filter is unsupported.
    """
    safe_limit = _clamp_pr_limit(limit)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    data = _gh_json(_gh_pr_list_args(limit=safe_limit, search=f"updated:>={cutoff}"))
    if data is None:
        data = _gh_json(_gh_pr_list_args(limit=safe_limit))
    if data is None:
        return ["PR scrape skipped: gh unavailable or failed"]

    messages: list[str] = []
    for pr in data:
        if not isinstance(pr, dict):
            continue
        payload = _payload_from_pr(pr)
        if payload is None:
            continue
        _, message = append_observation(payload, repo_root=repo_root)
        messages.append(f"{payload['primary_ref']}: {message}")
    return messages


def run_bootstrap(repo_root: Path, *, scrape_prs: bool = True, pr_limit: int = 50) -> list[str]:
    """Run doc seed then optional bounded PR scrape."""
    messages = seed_from_docs(repo_root)
    if scrape_prs:
        messages.extend(scrape_recent_prs(repo_root, limit=_clamp_pr_limit(pr_limit)))
    return messages


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for bounded bootstrap."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--no-prs", action="store_true", help="Skip gh PR scrape")
    parser.add_argument(
        "--pr-limit",
        type=int,
        default=50,
        choices=range(_PR_LIMIT_MIN, _PR_LIMIT_MAX + 1),
        metavar=f"{_PR_LIMIT_MIN}-{_PR_LIMIT_MAX}",
        help=f"Max PRs to scrape ({_PR_LIMIT_MIN}-{_PR_LIMIT_MAX})",
    )
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
