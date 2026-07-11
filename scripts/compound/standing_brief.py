"""Write durable standing briefs under docs/compound/briefs/."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS_ROOT = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from compound.schema import (  # noqa: E402
    BRIEFS_DIR,
    DOMAINS,
    LEDGER_PATH,
    PathPolicyError,
    SchemaError,
    assert_writable,
)
from compound.synthesize import _latest_by_primary_ref, load_ledger  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


def render_standing_brief(observations: list, *, as_of: str | None = None) -> str:
    """Render a standing brief markdown document."""
    stamp = as_of or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    latest = _latest_by_primary_ref(observations)
    by_domain: dict[str, list] = defaultdict(list)
    for obs in latest:
        for domain in obs.domains:
            by_domain[domain].append(obs)

    lines = [
        f"# Standing brief — {stamp}",
        "",
        "Architecture-expert compound brief (durable on knowledge branch).",
        "Claims are labeled landed vs provisional. ADRs/policy are not rewritten.",
        "",
        "## Seam movement by domain",
        "",
    ]
    for domain in DOMAINS:
        items = by_domain.get(domain, [])
        lines.append(f"### {domain}")
        if not items:
            lines.append("_No changes recorded._")
            lines.append("")
            continue
        for obs in sorted(items, key=lambda item: item.created_at or item.observation_id)[:15]:
            lines.append(f"- [{obs.status.value}] **{obs.primary_ref}**: {obs.summary}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_standing_brief(repo_root: Path, *, as_of: str | None = None) -> Path:
    """Write brief file under docs/compound/briefs/."""
    observations = load_ledger(repo_root / LEDGER_PATH)
    stamp = as_of or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rel = f"{BRIEFS_DIR.as_posix()}/{stamp}-standing-brief.md"
    assert_writable(rel)
    path = repo_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_standing_brief(observations, as_of=stamp), encoding="utf-8", newline="\n")
    return path


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for standing briefs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--as-of", default=None, help="YYYY-MM-DD stamp")
    args = parser.parse_args(argv)
    try:
        path = write_standing_brief(args.repo_root, as_of=args.as_of)
        print(f"wrote: {path.relative_to(args.repo_root).as_posix()}")
        return 0
    except (SchemaError, PathPolicyError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
