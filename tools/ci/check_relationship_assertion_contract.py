#!/usr/bin/env python3
"""CI gate: Governed Relationship Assertion Contract (GRAC) v1 conformance."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.governance.relationship_assertion_contract import run_conformance  # noqa: E402


def main() -> int:
    """Run conformance and exit non-zero on any violation."""
    violations = run_conformance()
    if violations:
        print("GRAC v1 conformance FAILED:", file=sys.stderr)
        for violation in violations:
            print(f"  - {violation}", file=sys.stderr)
        return 1
    print("GRAC v1 conformance PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
