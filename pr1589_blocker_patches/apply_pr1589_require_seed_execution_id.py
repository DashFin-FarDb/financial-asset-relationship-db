"""Blocker patch tool for strict seed execution ID requirements."""

from __future__ import annotations

import argparse
import difflib
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    """Replace exactly one instance of a block of text."""
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one matching block, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    """Apply strict seed execution-ID requirement patch."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    root = Path(args.repo).resolve()
    wf = root / ".github/workflows/relationship-assertion-staging-proof.yml"
    py = root / "scripts/check_relationship_assertion_proof.py"
    wf0 = wf.read_text(encoding="utf-8")
    py0 = py.read_text(encoding="utf-8")
    wf1 = replace_once(
        wf0,
        """      execution_id:
        description: "Exact pipeline/rebuild execution correlation ID being certified"
        required: false
        type: string
""",
        """      execution_id:
        description: "Exact pipeline/rebuild execution ID; required for strict seed_and_publish"
        required: false
        type: string
""",
        "workflow input",
    )
    wf1 = replace_once(
        wf1,
        """          if [ "$MODE" = "seed_and_publish" ]; then
            ARGS=("seed_and_publish")
""",
        """          if [ "$MODE" = "seed_and_publish" ]; then
            if [ "$STRICT_MODE" = "true" ]; then
              if [ -z "$REBUILD_JOB_ID" ]; then
                echo "Error: rebuild_job_id is required for strict seed_and_publish"
                exit 1
              fi
              if [ -z "$EXECUTION_ID" ]; then
                echo "Error: execution_id is required for strict seed_and_publish"
                exit 1
              fi
            fi

            ARGS=("seed_and_publish")
""",
        "workflow strict preflight",
    )
    py1 = replace_once(
        py0,
        """        if args.strict and not getattr(args, "rebuild_job_id", None):
            self.add_error("Rebuild job ID required in strict mode")
            return self.build_result()

        self._populate_missing_evidence(args)
""",
        """        if args.strict:
            if not getattr(args, "rebuild_job_id", None):
                self.add_error("Rebuild job ID required in strict mode")
            if not getattr(args, "execution_id", None):
                self.add_error("Execution ID required in strict mode")
            if self.errors:
                return self.build_result()

        self._populate_missing_evidence(args)
""",
        "validator strict preconditions",
    )
    diff = "".join(
        [
            "".join(difflib.unified_diff(wf0.splitlines(True), wf1.splitlines(True), fromfile=str(wf), tofile=str(wf))),
            "".join(difflib.unified_diff(py0.splitlines(True), py1.splitlines(True), fromfile=str(py), tofile=str(py))),
        ]
    )
    if args.check:
        print(diff or "No changes required.")
        return
    wf.write_text(wf1, encoding="utf-8")
    py.write_text(py1, encoding="utf-8")
    print("Applied strict seed execution-ID requirement.")


if __name__ == "__main__":
    main()
