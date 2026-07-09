"""Bounded bootstrap seed for the architecture-expert observation ledger."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess  # nosec B404 - gh invocations are path-resolved and argument-validated.
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
GH_JSON_FIELDS = "number,title,state,mergedAt,updatedAt,labels,files"
GH_SEARCH_PATTERN = re.compile(r"^updated:>=\d{4}-\d{2}-\d{2}$")

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
        payload = _seed_doc_payload(rel_path, domains)
        _, message = append_observation(payload, repo_root=repo_root)
        messages.append(f"{rel_path}: {message}")
    return messages


def _seed_doc_payload(rel_path: str, domains: tuple[str, ...]) -> dict[str, Any]:
    """Build a landed observation payload for one seed document."""
    _validate_seed_domains(domains)
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


def _validate_seed_domains(domains: tuple[str, ...]) -> None:
    """Validate static seed domain declarations."""
    for domain in domains:
        if domain not in DOMAINS:
            raise SchemaError(f"Invalid seed domain {domain}")


def _validated_gh_pr_list_args(args: list[str]) -> list[str] | None:
    """Return validated gh args for the bounded PR-list scrape."""
    if len(args) not in {8, 10} or args[:4] != ["pr", "list", "--state", "all"]:
        return None
    if args[4] != "--limit" or not args[5].isdigit():
        return None
    limit = int(args[5])
    if limit < 1 or limit > 100:
        return None
    json_index = 6
    if len(args) == 10:
        if args[6] != "--search" or not GH_SEARCH_PATTERN.fullmatch(args[7]):
            return None
        json_index = 8
    if args[json_index] != "--json" or args[json_index + 1] != GH_JSON_FIELDS:
        return None
    return args


def _gh_json(args: list[str]) -> Any | None:
    gh_path = shutil.which("gh")
    validated_args = _validated_gh_pr_list_args(args)
    if gh_path is None or validated_args is None:
        return None
    try:
        completed = subprocess.run(
            [gh_path, *validated_args],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )  # nosec B603 - gh path and arguments are strictly allowlisted above.
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
    data = _scrape_pr_data(limit=limit, days=days)
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


def _scrape_pr_data(*, limit: int, days: int) -> Any | None:
    """Fetch PR JSON data from gh using a bounded preferred query plus fallback."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    bounded_limit = max(1, min(limit, 100))
    preferred = [
        "pr",
        "list",
        "--state",
        "all",
        "--limit",
        str(bounded_limit),
        "--search",
        f"updated:>={cutoff}",
        "--json",
        GH_JSON_FIELDS,
    ]
    fallback = ["pr", "list", "--state", "all", "--limit", str(bounded_limit), "--json", GH_JSON_FIELDS]
    return _gh_json(preferred) or _gh_json(fallback)


def _pr_payload(pr: Any) -> dict[str, Any] | None:
    """Build a bootstrap observation payload from one gh PR JSON object."""
    if not isinstance(pr, dict):
        return None
    number = pr.get("number")
    if not isinstance(number, int):
        return None
    title = str(pr.get("title") or f"PR #{number}")
    return {
        "observation_id": f"bootstrap-pr-{number}",
        "source": ObservationSource.BOOTSTRAP.value,
        "event_type": "seed.pull_request",
        "status": _pr_observation_status(pr),
        "primary_ref": f"pr:{number}",
        "summary": title[:240],
        "domains": list(detect_domains_from_paths(_pr_paths(pr.get("files") or []))),
        "refs": [f"pr:{number}"],
        "evidence_pointers": [f"github:pr:{number}"],
        "created_at": _now(),
    }


def _pr_observation_status(pr: dict[str, Any]) -> str:
    """Return landed for merged PRs, provisional otherwise."""
    state = str(pr.get("state") or "").upper()
    return (
        ObservationStatus.LANDED.value
        if pr.get("mergedAt") or state == "MERGED"
        else ObservationStatus.PROVISIONAL.value
    )


def _pr_paths(file_entries: list[Any]) -> list[str]:
    """Extract changed paths from gh PR file entries."""
    paths: list[str] = []
    for entry in file_entries:
        if isinstance(entry, str):
            paths.append(entry)
        elif isinstance(entry, dict) and entry.get("path"):
            paths.append(str(entry["path"]))
        elif isinstance(entry, dict) and entry.get("filename"):
            paths.append(str(entry["filename"]))
    return paths


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
