"""Blocker patch tool for execution ID validation check."""

from __future__ import annotations

import argparse
import difflib
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    """Replace exactly one instance of a block of text."""
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"{label}: expected exactly one matching block, found {count}. "
            "Inspect the current branch source before applying."
        )
    return text.replace(old, new, 1)


def main() -> None:
    """Apply execution ID validation check patch."""
    parser = argparse.ArgumentParser(
        description="Fail closed on malformed execution IDs in PR #1589 lineage validation."
    )
    parser.add_argument("--repo", default=".", help="Repository root")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    root = Path(args.repo).resolve()
    if not (root / ".git").exists():
        raise SystemExit(f"{root} does not look like a Git checkout")

    path = root / "scripts/check_relationship_assertion_proof.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    old_job_check = """        if hasattr(args, "execution_id") and args.execution_id:
            clean_exec_id = _sanitize_db_id(args.execution_id)
            if clean_exec_id:
                job_query = job_query.where(RebuildJobORM.execution_id == clean_exec_id)
"""
    new_job_check = """        if getattr(args, "execution_id", None):
            clean_exec_id = _sanitize_db_id(args.execution_id)
            if not clean_exec_id:
                self.add_error("Certified execution ID is invalid")
                return None
            job_query = job_query.where(RebuildJobORM.execution_id == clean_exec_id)
"""
    updated = replace_once(
        updated,
        old_job_check,
        new_job_check,
        "rebuild-job execution binding",
    )

    old_publication_check = """        if getattr(args, "execution_id", None):
            clean_exec_id = _sanitize_db_id(args.execution_id)
            if clean_exec_id and execution_id != clean_exec_id:
                self.add_error(
                    f"Publication execution ID {execution_id} does not match certified execution {clean_exec_id}"
                )
                return None
"""
    new_publication_check = """        if getattr(args, "execution_id", None):
            clean_exec_id = _sanitize_db_id(args.execution_id)
            if not clean_exec_id:
                self.add_error("Certified execution ID is invalid")
                return None
            if execution_id != clean_exec_id:
                self.add_error(
                    f"Publication execution ID {execution_id} does not match certified execution {clean_exec_id}"
                )
                return None
"""
    updated = replace_once(
        updated,
        old_publication_check,
        new_publication_check,
        "publication execution binding",
    )

    diff = "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=str(path),
            tofile=str(path),
        )
    )

    if args.check:
        print(diff or "No changes required.")
        return

    path.write_text(updated, encoding="utf-8")
    print("Applied PR #1589 malformed execution-ID fail-closed fix.")
    print(f"Updated: {path}")


if __name__ == "__main__":
    main()
