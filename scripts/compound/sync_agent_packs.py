"""Sync Cursor and OpenHands agent packs from compound docs.

Sidecar-only: never writes AGENTS.md, ADRs, or policy docs.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_SCRIPTS_ROOT = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from compound.schema import DOMAINS, INDEX_PATH, PathPolicyError, assert_writable  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]

CURSOR_RULE_PATH = Path(".cursor/rules/architecture-expert.mdc")
CURSOR_QUERY_PATH = Path(".cursor/rules/architecture-expert-query.mdc")
OPENHANDS_PATH = Path(".openhands/microagents/architecture_expert.md")

FORBIDDEN_WRITE_INSTRUCTIONS = re.compile(
    r"(?i)\b(rewrite|overwrite|edit|modify|update)\b[\s\S]{0,40}\b(adrs?|agents\.md|policy)\b"
)


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _sanitize_pack_body(body: str) -> str:
    """Rewrite ADR/policy rewrite instructions into cite/propose-only language."""

    def _repl(match: re.Match[str]) -> str:
        return "cite or propose annotation for ADRs/policy (do not rewrite)"

    return FORBIDDEN_WRITE_INSTRUCTIONS.sub(_repl, body)


def _rewrite_compound_links(excerpt: str) -> str:
    """Rewrite relative compound links so sidecars resolve from repo root."""
    return (
        excerpt.replace("(README.md)", "(docs/compound/README.md)")
        .replace("(watched-series.yml)", "(docs/compound/watched-series.yml)")
        .replace("(runtime.yml)", "(docs/compound/runtime.yml)")
        .replace("(domains/", "(docs/compound/domains/")
        .replace("[domains/", "[docs/compound/domains/")
        .replace("](domains/", "](docs/compound/domains/")
    )


def build_cursor_rule(index_text: str) -> str:
    """Build Cursor rule markdown with frontmatter."""
    domain_lines = "\n".join(f"- `{domain}`: see `docs/compound/domains/{domain}.md`" for domain in DOMAINS)
    excerpt = _rewrite_compound_links(_sanitize_pack_body(index_text[:2000]))
    body = f"""# Architecture Expert (generated)

Docs-first compounded memory. Prefer `docs/compound/` over inventing seams.

## Mandatory branch/ref verification

Before reviewing, editing, or summarizing repository state, verify the current
branch, the branch/commit/PR referenced in the request, whether that branch has
an open PR, and whether it differs from `main`.

## Provisional vs landed

- **Landed**: merged to `main` or explicitly promoted — treat as canon.
- **Provisional**: open PR / watched series — label clearly; never present as landed.

## Source of truth

- Canonical docs: `docs/compound/INDEX.md` and domain docs under `docs/compound/domains/`.
- ADRs and `.github` policy remain human-owned — cite or propose annotation only; never rewrite them as fact.
- Never overwrite Dosu-maintained `AGENTS.md`.

## Domains

{domain_lines}

## Index excerpt

{excerpt}
"""
    return (
        "---\n"
        "description: Architecture-expert compounded memory (generated from docs/compound)\n"
        "globs:\n"
        '  - "docs/compound/**"\n'
        '  - "api/**"\n'
        '  - "src/**"\n'
        "alwaysApply: false\n"
        "---\n"
        f"{body}"
    )


def build_cursor_query_rule() -> str:
    """Build chat/query entrypoint rule."""
    return """---
description: Query architecture-expert compounded memory via docs/compound
alwaysApply: false
---
# Architecture Expert Query

When asked about architecture, seams, API, persistence/SQL, CI/guardrails,
rebuild/reconciliation, or deployment/readiness:

1. Read `docs/compound/INDEX.md` then the relevant `docs/compound/domains/*.md`.
2. Prefer `python scripts/compound/query_memory.py --question "..."` when available.
3. Label every claim as **landed** or **provisional**.
4. Cite evidence pointers; do not invent seams.
5. Never rewrite ADRs, policy docs, or `AGENTS.md`.
"""


def build_openhands_microagent(index_text: str) -> str:
    """Build OpenHands microagent with required frontmatter."""
    # Sanitize only the index excerpt; leave static Rules unsanitized (matches Cursor packs).
    excerpt = _rewrite_compound_links(_sanitize_pack_body(index_text[:1500])).replace("\n# ", "\n## ")
    if excerpt.startswith("# "):
        excerpt = "## " + excerpt[2:]
    body = f"""# Architecture Expert Microagent

Compounded architecture memory for this repository.

## Rules

- Read `docs/compound/` before answering seam/API/persistence questions.
- Distinguish provisional vs landed claims.
- Cite or propose annotation for ADRs/policy; never rewrite them.
- Do not overwrite `AGENTS.md`.
- Additive to PR Agent / existing reviewers - do not disable them.

## Index excerpt

{excerpt}
"""
    return (
        "---\n"
        "name: architecture-expert\n"
        "type: knowledge\n"
        "version: 1.0.0\n"
        "agent: CodeActAgent\n"
        "triggers:\n"
        '  - "@architecture-expert"\n'
        '  - "@arch-expert"\n'
        "---\n\n"
        f"{body}"
    )


def sync_agent_packs(repo_root: Path, *, dry_run: bool = False) -> dict[str, str]:
    """Generate sidecar packs from INDEX + domain docs."""
    index_text = _read_text(repo_root / INDEX_PATH)

    outputs = {
        CURSOR_RULE_PATH.as_posix(): build_cursor_rule(index_text),
        CURSOR_QUERY_PATH.as_posix(): build_cursor_query_rule(),
        OPENHANDS_PATH.as_posix(): build_openhands_microagent(index_text),
    }

    if dry_run:
        return outputs

    agents_before = _read_text(repo_root / "AGENTS.md")
    for rel, content in outputs.items():
        assert_writable(rel)
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")

    agents_after = _read_text(repo_root / "AGENTS.md")
    if agents_before != agents_after:
        raise PathPolicyError("AGENTS.md changed during pack sync — aborting")
    return outputs


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for agent pack sync."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        outputs = sync_agent_packs(args.repo_root, dry_run=args.dry_run)
        mode = "dry-run" if args.dry_run else "wrote"
        for path in sorted(outputs):
            print(f"{mode}: {path}")
        return 0
    except (PathPolicyError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
