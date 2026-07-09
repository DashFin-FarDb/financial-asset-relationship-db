"""Query compounded architecture memory from docs/compound."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_SCRIPTS_ROOT = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from compound.schema import DOMAINS, INDEX_PATH  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]

DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "architecture": ("architecture", "seam", "boundary", "module", "adr"),
    "api": ("api", "endpoint", "fastapi", "cors", "auth", "jwt"),
    "persistence": ("persistence", "sqlite", "postgres", "schema", "sql", "database", "graph lifecycle"),
    "ci-guardrails": ("ci", "guardrail", "workflow", "pre-commit", "automation"),
    "rebuild-reconciliation": ("rebuild", "reconciliation", "drift", "recovery", "checkpoint"),
    "deployment": ("deploy", "readiness", "staging", "promotion", "hosted"),
}


def _score_domain(question: str, domain: str) -> int:
    q = question.lower()
    return sum(1 for keyword in DOMAIN_KEYWORDS.get(domain, ()) if keyword in q)


def select_domains(question: str) -> list[str]:
    """Pick relevant domains for a question; fall back to architecture."""
    scored = sorted(
        ((domain, _score_domain(question, domain)) for domain in DOMAINS),
        key=lambda item: item[1],
        reverse=True,
    )
    selected = [domain for domain, score in scored if score > 0]
    return selected or ["architecture"]


def _extract_bullets(text: str, section: str) -> list[str]:
    match = re.search(rf"## {section}\n(.*?)(?=\n## |\Z)", text, re.S)
    if not match:
        return []
    block = match.group(1)
    bullets = []
    for line in block.splitlines():
        if line.startswith("- **"):
            bullets.append(line.strip())
    return bullets


def query_memory(repo_root: Path, question: str) -> str:
    """Answer from INDEX + domain docs with provisional/landed labels."""
    domains = select_domains(question)
    parts = [
        f"Question: {question}",
        f"Domains consulted: {', '.join(domains)}",
        "",
    ]
    index = repo_root / INDEX_PATH
    if index.exists():
        parts.append(f"Index: `{INDEX_PATH.as_posix()}`")
        parts.append("")

    found = False
    for domain in domains:
        domain_lines, domain_found = _domain_query_lines(repo_root, domain)
        if not domain_lines:
            continue
        found = found or domain_found
        parts.extend(domain_lines)

    if not found:
        parts.append(
            "No compounded observations matched yet. "
            "Run bootstrap/synthesize, or consult ADRs/seam docs directly "
            "(cite only; do not rewrite policy)."
        )
    parts.append("Reminder: label claims as landed vs provisional; never rewrite ADRs/AGENTS.md/policy.")
    return "\n".join(parts).rstrip() + "\n"


def _domain_query_lines(repo_root: Path, domain: str) -> tuple[list[str], bool]:
    """Render query answer lines for one domain doc."""
    path = repo_root / "docs" / "compound" / "domains" / f"{domain}.md"
    if not path.exists():
        return [], False
    text = path.read_text(encoding="utf-8")
    landed = _extract_bullets(text, "Landed")
    provisional = _extract_bullets(text, "Provisional")
    lines = [f"### {domain}"]
    found = _extend_section(lines, "Landed", landed)
    found = _extend_section(lines, "Provisional", provisional) or found
    if not found:
        lines.append("  _No observations yet in this domain._")
    lines.append("")
    return lines, found


def _extend_section(lines: list[str], title: str, items: list[str]) -> bool:
    """Append one answer section and return whether it had items."""
    if not items:
        return False
    lines.append(f"{title}:")
    lines.extend(f"  {item}" for item in items[:10])
    return True


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for memory query."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", required=True)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    try:
        print(query_memory(args.repo_root, args.question))
        return 0
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
