#!/usr/bin/env python3
"""Staging proof validator for governed relationship assertions.

Supports two verification modes:
- seed_and_publish: Initial evidence creation and publication
- verify_after_restart: Post-restart persistence and continuity

Security: Credentials and sensitive data are never exposed in output.
"""

import argparse
import json
import os
import sys
from typing import Any
from urllib.parse import urlparse

EXIT_SUCCESS = 0
EXIT_FAILURE = 1


class ProofValidator:
    """Validates GRAC v1 staging proofs."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.errors: list[str] = []
        self.metadata: dict[str, Any] = {}

    def add_error(self, msg: str) -> None:
        """Record validation error."""
        self.errors.append(msg)

    def git_sha_is_valid(self, sha: str, label: str) -> bool:
        """Check Git SHA format."""
        if not sha or len(sha) != 40 or not all(c in "0123456789abcdef" for c in sha.lower()):
            self.add_error(f"{label} SHA invalid or missing")
            return False
        return True

    def digest_is_valid(self, digest: str | None, label: str) -> bool:
        """Check SHA-256 digest format."""
        if not digest or len(digest) != 64 or not all(c in "0123456789abcdef" for c in digest.lower()):
            self.add_error(f"{label} digest invalid or missing")
            return False
        return True

    def mask_database_url(self, url: str) -> str:
        """Hide sensitive URL parts."""
        try:
            parsed = urlparse(url)
            return f"{parsed.scheme}://{parsed.hostname or 'unknown'}/***"
        except Exception:
            return "***"

    def check_db_url_structure(self, url: str | None) -> bool:
        """Validate database URL without exposing credentials."""
        if not url:
            self.add_error("Database URL not configured")
            return False

        try:
            parsed = urlparse(url)
            has_scheme = bool(parsed.scheme)
            has_host = bool(parsed.hostname)
            has_creds = bool(parsed.username and parsed.password)

            if not has_scheme or not has_host:
                self.add_error(f"DB URL incomplete: {self.mask_database_url(url)}")
                return False

            if parsed.scheme.startswith("postgres") and not has_creds:
                self.add_error(f"DB URL missing credentials: {self.mask_database_url(url)}")
                return False

            return True
        except Exception:
            self.add_error("DB URL parsing failed")
            return False

    def actors_are_distinct(self, proposer: str, determiner: str, executor: str | None) -> bool:
        """Verify actor separation."""
        if not proposer or not determiner:
            self.add_error("Proposer or determiner missing")
            return False

        if proposer == determiner:
            self.add_error(f"Proposer equals determiner: {proposer[:8]}...")
            return False

        if executor and (executor == proposer or executor == determiner):
            self.add_error(f"Executor conflicts with proposer/determiner: {executor[:8]}...")
            return False

        return True

    def publication_is_correct(self, count: int, owner: str, expected: str | None) -> bool:
        """Verify publication count and ownership."""
        ok = True
        if count != 1:
            self.add_error(f"Publication count {count}, expected 1")
            ok = False
        if not owner:
            self.add_error("Publication owner missing")
            ok = False
        elif expected and owner != expected:
            self.add_error(f"Owner mismatch: {owner[:8]}... vs {expected[:8]}...")
            ok = False
        return ok

    def scopes_are_consistent(self, before: list[str], after: list[str], allow_loss: bool) -> bool:
        """Check scope consistency across transitions."""
        if not before or not after:
            self.add_error("Scope lists empty")
            return False

        if allow_loss:
            missing = set(before) - set(after)
            if missing:
                self.add_error(f"Scopes disappeared: {sorted(missing)[:3]}")
                return False
        else:
            if set(before) != set(after):
                self.add_error(f"Scope mismatch: {len(before)} before, {len(after)} after")
                return False

        return True

    def history_is_well_formed(self, entries: list[dict[str, Any]], min_count: int) -> bool:
        """Validate historical entries."""
        if not entries:
            self.add_error("History empty")
            return False

        if len(entries) < min_count:
            self.add_error(f"History has {len(entries)} entries, need {min_count}+")
            return False

        for idx, entry in enumerate(entries):
            if not isinstance(entry, dict):
                self.add_error(f"History[{idx}] not a dict")
                continue
            for req_field in ["known_at", "state", "actor"]:
                if req_field not in entry:
                    self.add_error(f"History[{idx}] missing {req_field}")

        return len(self.errors) == 0

    def load_authz_evidence(self, path: str, expected_sha: str) -> dict[str, Any]:
        """Load and validate authorization evidence."""
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            if data.get("status") != "passed":
                self.add_error(f"Authz status: {data.get('status')} (need passed)")

            sha = data.get("sha")
            if not sha:
                self.add_error("Authz evidence missing SHA")
            elif sha != expected_sha:
                self.add_error(f"Authz SHA mismatch: {sha[:8]}... vs {expected_sha[:8]}...")

            if not data.get("postgresql_checked"):
                self.add_error("Authz evidence: PostgreSQL not verified")

            return {
                "authz_sha": sha[:8] + "..." if sha else "N/A",
                "authz_status": data.get("status", "N/A"),
                "pg_verified": bool(data.get("postgresql_checked")),
            }
        except Exception as e:
            self.add_error(f"Authz evidence error: {e}")
            return {}

    def validate_seed_and_publish(self, args: argparse.Namespace) -> dict[str, Any]:
        """Mode 1: Seed and publish validation."""
        self.metadata["mode"] = "seed_and_publish"

        self.git_sha_is_valid(args.deployed_sha, "Deployed")
        self.metadata["sha"] = args.deployed_sha[:8] + "..." if args.deployed_sha else "N/A"

        if args.contract_digest or args.strict:
            self.digest_is_valid(args.contract_digest, "Contract")
            self.metadata["contract"] = args.contract_digest[:8] + "..." if args.contract_digest else "N/A"

        if args.registry_digest or args.strict:
            self.digest_is_valid(args.registry_digest, "Registry")
            self.metadata["registry"] = args.registry_digest[:8] + "..." if args.registry_digest else "N/A"

        db_url = args.database_url or os.getenv("DATABASE_URL")
        if db_url or args.strict:
            if db_url:
                self.check_db_url_structure(db_url)
                self.metadata["db"] = self.mask_database_url(db_url)
            else:
                self.add_error("DB URL required in strict mode")

        if args.authz_evidence or args.strict:
            if args.authz_evidence:
                authz_meta = self.load_authz_evidence(args.authz_evidence, args.deployed_sha)
                self.metadata.update(authz_meta)
            else:
                self.add_error("Authz evidence required in strict mode")

        if (args.proposer_id and args.determiner_id) or args.strict:
            if args.proposer_id and args.determiner_id:
                self.actors_are_distinct(args.proposer_id, args.determiner_id, args.executor_id)
                self.metadata["proposer"] = args.proposer_id[:8] + "..."
                self.metadata["determiner"] = args.determiner_id[:8] + "..."
            else:
                self.add_error("Actor IDs required in strict mode")

        if args.publication_count is not None:
            self.publication_is_correct(args.publication_count, args.owner_id or "", args.expected_owner)
            self.metadata["publications"] = args.publication_count

        if args.revision_hash:
            self.digest_is_valid(args.revision_hash, "Revision")
            self.metadata["revision"] = args.revision_hash[:8] + "..."

        return self.build_result()

    def validate_verify_after_restart(self, args: argparse.Namespace) -> dict[str, Any]:
        """Mode 2: Post-restart verification."""
        self.metadata["mode"] = "verify_after_restart"

        self.git_sha_is_valid(args.deployed_sha, "Deployed")
        self.metadata["sha"] = args.deployed_sha[:8] + "..." if args.deployed_sha else "N/A"

        if args.require_persistence:
            if args.startup_source != "persisted":
                self.add_error(f"Startup: {args.startup_source or 'N/A'} (need persisted)")
            self.metadata["startup"] = args.startup_source or "N/A"

        if args.authz_evidence or args.strict:
            if args.authz_evidence:
                authz_meta = self.load_authz_evidence(args.authz_evidence, args.deployed_sha)
                self.metadata.update(authz_meta)
            else:
                self.add_error("Authz evidence required in strict mode")

        if (args.before_scopes and args.after_scopes) or args.strict:
            if args.before_scopes and args.after_scopes:
                try:
                    before = json.loads(args.before_scopes)
                    after = json.loads(args.after_scopes)
                    self.scopes_are_consistent(before, after, False)
                    self.metadata["scopes_before"] = len(before)
                    self.metadata["scopes_after"] = len(after)
                except json.JSONDecodeError as e:
                    self.add_error(f"Scope JSON error: {e}")
            else:
                self.add_error("Scopes required in strict mode")

        if args.history_entries or args.strict:
            if args.history_entries:
                try:
                    entries = json.loads(args.history_entries)
                    self.history_is_well_formed(entries, args.expected_min_history)
                    self.metadata["history_entries"] = len(entries)
                except json.JSONDecodeError as e:
                    self.add_error(f"History JSON error: {e}")
            else:
                self.add_error("History required in strict mode")

        if args.empty_edge_before_scopes and args.empty_edge_after_scopes:
            try:
                before = json.loads(args.empty_edge_before_scopes)
                after = json.loads(args.empty_edge_after_scopes)
                self.scopes_are_consistent(before, after, True)
                self.metadata["edge_scopes_before"] = len(before)
                self.metadata["edge_scopes_after"] = len(after)
            except json.JSONDecodeError as e:
                self.add_error(f"Empty-edge JSON error: {e}")

        return self.build_result()

    def build_result(self) -> dict[str, Any]:
        """Construct result dictionary."""
        return {
            "status": "passed" if not self.errors else "failed",
            "errors": self.errors,
            "metadata": self.metadata,
        }


def display_result(result: dict[str, Any], output_path: str | None) -> None:
    """Show validation result."""
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, sort_keys=True)
        print(f"Results written to {output_path}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))

    mode = result["metadata"].get("mode", "unknown")
    status = result["status"]

    if status == "passed":
        print(f"✓ Validation passed ({mode})", file=sys.stderr)
    else:
        print(f"✗ Validation failed ({mode}):", file=sys.stderr)
        for err in result["errors"][:10]:
            print(f"  - {err}", file=sys.stderr)
        if len(result["errors"]) > 10:
            print(f"  ({len(result['errors']) - 10} more errors)", file=sys.stderr)


def setup_parser() -> argparse.ArgumentParser:
    """Configure argument parser."""
    parser = argparse.ArgumentParser(description="GRAC v1 staging proof validator")
    parser.add_argument("mode", choices=["seed_and_publish", "verify_after_restart"])
    parser.add_argument("--deployed-sha", required=True)
    parser.add_argument("--run-id", default=os.getenv("GITHUB_RUN_ID", "local"))
    parser.add_argument("--run-number", default=os.getenv("GITHUB_RUN_NUMBER", "0"))
    parser.add_argument("--database-url")
    parser.add_argument("--contract-digest")
    parser.add_argument("--registry-digest")
    parser.add_argument("--require-persistence", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--output")
    parser.add_argument("--authz-evidence")
    parser.add_argument("--proposer-id")
    parser.add_argument("--determiner-id")
    parser.add_argument("--executor-id")
    parser.add_argument("--publication-count", type=int)
    parser.add_argument("--owner-id")
    parser.add_argument("--expected-owner")
    parser.add_argument("--revision-hash")
    parser.add_argument("--expected-revision-hash")
    parser.add_argument("--startup-source")
    parser.add_argument("--before-scopes")
    parser.add_argument("--after-scopes")
    parser.add_argument("--history-entries")
    parser.add_argument("--expected-min-history", type=int, default=1)
    parser.add_argument("--empty-edge-before-scopes")
    parser.add_argument("--empty-edge-after-scopes")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    try:
        parser = setup_parser()
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)

        validator = ProofValidator({"run_id": args.run_id, "run_number": args.run_number})

        if args.mode == "seed_and_publish":
            result = validator.validate_seed_and_publish(args)
        else:
            result = validator.validate_verify_after_restart(args)

        display_result(result, args.output)

        return EXIT_SUCCESS if result["status"] == "passed" else EXIT_FAILURE

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_FAILURE


if __name__ == "__main__":
    sys.exit(main())
