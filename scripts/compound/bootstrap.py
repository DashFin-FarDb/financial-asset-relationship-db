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
GH_ARG_PATTERN = re.compile(r"^[A-Za-z0-9_./:>=,-]+$")
CUTOFF_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
GH_PR_JSON_FIELDS = "number,title,state,mergedAt,updatedAt,labels,files"
MIN_PR_LIMIT = 1
MAX_PR_LIMIT = 100
MIN_PR_LOOKBACK_DAYS = 1
MAX_PR_LOOKBACK_DAYS = 365

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


def _validated_gh_args(args: list[str]) -> list[str] | None:
    """Return gh args only when they match the bounded PR-list contract."""
    if args[:2] != ["pr", "list"]:
        return None
    for value in args:
        if not GH_ARG_PATTERN.fullmatch(value):
            return None
    if "--limit" not in args or "--json" not in args or "--state" not in args:
        return None
    try:
        limit = int(args[args.index("--limit") + 1])
    except (IndexError, ValueError):
        return None
    if not 1 <= limit <= 100:
        return None
    return args


def _validate_domains(domains: tuple[str, ...]) -> None:
    for domain in domains:
        if domain not in DOMAINS:
            raise SchemaError(f"Invalid seed domain {domain}")


def _seed_payload(rel_path: str, domains: tuple[str, ...]) -> dict[str, Any]:
    _validate_domains(domains)
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


def seed_from_docs(repo_root: Path) -> list[str]:
    """Emit landed bootstrap observations from existing allowlisted seed docs."""
    messages: list[str] = []
    for rel_path, domains in SEED_DOCS:
        path = repo_root / rel_path
        if not path.exists():
            messages.append(f"skip missing seed doc: {rel_path}")
            continue
        _, message = append_observation(_seed_payload(rel_path, domains), repo_root=repo_root)
        messages.append(f"{rel_path}: {message}")
    return messages


def _bounded_int(value: int, *, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise SchemaError(f"{name} must be an integer between {minimum} and {maximum}")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise SchemaError(f"{name} must be an integer between {minimum} and {maximum}") from exc
    if not minimum <= parsed <= maximum:
        raise SchemaError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def _cutoff_date(days: int) -> str:
    safe_days = _bounded_int(
        days,
        name="days",
        minimum=MIN_PR_LOOKBACK_DAYS,
        maximum=MAX_PR_LOOKBACK_DAYS,
    )
    return (datetime.now(timezone.utc) - timedelta(days=safe_days)).strftime("%Y-%m-%d")


def _gh_pr_list(*, limit: int, updated_since: str | None = None) -> Any | None:
    safe_limit = _bounded_int(limit, name="limit", minimum=MIN_PR_LIMIT, maximum=MAX_PR_LIMIT)
    if updated_since is not None and not CUTOFF_DATE_PATTERN.fullmatch(updated_since):
        return None
    gh_path = shutil.which("gh")
    if gh_path is None:
        return None
    command = [
        gh_path,
        "pr",
        "list",
        "--state",
        "all",
        "--limit",
        str(safe_limit),
    ]
    if updated_since is not None:
        command.extend(["--search", f"updated:>={updated_since}"])
    command.extend(["--json", GH_PR_JSON_FIELDS])
    try:
        completed = subprocess.run(
            command,
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


def _pr_status(pr: dict[str, Any]) -> str:
    state = str(pr.get("state") or "").upper()
    merged = bool(pr.get("mergedAt"))
    return ObservationStatus.LANDED.value if merged or state == "MERGED" else ObservationStatus.PROVISIONAL.value


def _paths_from_pr_files(file_entries: Any) -> list[str]:
    if not isinstance(file_entries, list):
        return []
    paths: list[str] = []
    for entry in file_entries:
        if isinstance(entry, str):
            paths.append(entry)
        elif isinstance(entry, dict):
            path = entry.get("path") or entry.get("filename")
            if path:
                paths.append(str(path))
    return paths


def _pr_payload(pr: dict[str, Any], number: int) -> dict[str, Any]:
    paths = _paths_from_pr_files(pr.get("files"))
    title = str(pr.get("title") or f"PR #{number}")
    return {
        "observation_id": f"bootstrap-pr-{number}",
        "source": ObservationSource.BOOTSTRAP.value,
        "event_type": "seed.pull_request",
        "status": _pr_status(pr),
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
    safe_limit = _bounded_int(limit, name="limit", minimum=MIN_PR_LIMIT, maximum=MAX_PR_LIMIT)
    data = _gh_pr_list(limit=safe_limit, updated_since=_cutoff_date(days))
    if data is None:
        data = _gh_pr_list(limit=safe_limit)
    if not isinstance(data, list):
        return ["PR scrape skipped: gh unavailable or failed"]

    messages: list[str] = []
    for pr in data:
        if not isinstance(pr, dict):
            continue
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
