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
import pathlib
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import sessionmaker

from src.data.database import create_engine_from_url
from src.data.db_models import RebuildJobORM
from src.data.relationship_assertion_db_models import (
    RelationshipProjectionPublicationORM,
    RelationshipProjectionRevisionORM,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

EXIT_SUCCESS = 0
EXIT_FAILURE = 1


def validate_safe_path(path: str) -> str:
    """Validate file path to prevent path traversal attacks (CWE-22)."""
    # Restrict to simple filename in current working directory to prevent path traversal
    filename = os.path.basename(path)
    if filename != path:
        raise ValueError(f"Path traversal detected: directory components not allowed in '{path}'")
    return os.path.join(os.getcwd(), filename)


class ProofValidator:
    """Validates GRAC v1 staging proofs."""

    def __init__(self, config: dict[str, Any]):
        """Initialize the validator with configuration."""
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
        """Mask password credentials in database URL."""
        try:
            parsed = urlparse(url)
            if parsed.password:
                return url.replace(parsed.password, "********")
            return url
        except Exception:
            return "********"

    def check_db_url_structure(self, url: str | None) -> bool:
        """Validate database URL scheme."""
        if not url:
            return False
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("postgresql", "postgres", "sqlite")
        except Exception:
            return False

    def actors_are_distinct(self, proposer: str, determiner: str, executor: str | None) -> bool:
        """Ensure separation of duties among actors."""
        if not proposer or not determiner:
            self.add_error("Proposer and determiner must be specified")
            return False
        if proposer == determiner:
            self.add_error(f"Collision: proposer and determiner are same ({proposer[:8]}...)")
            return False
        if executor and proposer == executor:
            self.add_error(f"Collision: proposer and executor are same ({proposer[:8]}...)")
            return False
        if executor and determiner == executor:
            self.add_error(f"Collision: determiner and executor are same ({determiner[:8]}...)")
            return False
        return True

    def publication_is_correct(self, count: int, owner: str, expected: str | None) -> bool:
        """Verify publication properties."""
        ok = True
        if count <= 0:
            self.add_error(f"Invalid publication count: {count}")
            ok = False
        if not owner:
            self.add_error("Publication owner missing")
            ok = False
        elif expected and owner != expected:
            self.add_error(f"Owner mismatch: {owner[:8]}... vs {expected[:8]}...")
            ok = False
        return ok

    def scopes_are_consistent(self, before: list[str], after: list[str], enforce_no_loss: bool) -> bool:
        """Check scope consistency across transitions."""
        if not before or not after:
            self.add_error("Scope lists empty")
            return False

        if enforce_no_loss:
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
        """Validate pipeline execution history schema."""
        if len(entries) < min_count:
            self.add_error(f"History length: {len(entries)} (need {min_count})")
            return False

        for idx, entry in enumerate(entries):
            for req_field in ("id", "status", "created_at"):
                if req_field not in entry:
                    self.add_error(f"History[{idx}] missing {req_field}")

        return len(self.errors) == 0

    def _validate_safe_path(self, path: str) -> str:
        """Validate file path to prevent path traversal attacks (CWE-22)."""
        return validate_safe_path(path)

    def load_authz_evidence(self, path: str, expected_sha: str) -> dict[str, Any]:
        """Load and validate authorization evidence."""
        try:
            safe_path = validate_safe_path(path)
            with open(safe_path, encoding="utf-8") as f:
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

    def _validate_digests(self, args: argparse.Namespace) -> None:
        """Validate contract and registry digests."""
        if args.contract_digest or args.strict:
            self.digest_is_valid(args.contract_digest, "Contract")
            self.metadata["contract"] = args.contract_digest[:8] + "..." if args.contract_digest else "N/A"

        if args.registry_digest or args.strict:
            self.digest_is_valid(args.registry_digest, "Registry")
            self.metadata["registry"] = args.registry_digest[:8] + "..." if args.registry_digest else "N/A"

    def _validate_db(self, args: argparse.Namespace) -> None:
        """Validate database configuration URL."""
        db_url = args.database_url or os.getenv("DATABASE_URL")
        if db_url or args.strict:
            if db_url:
                self.check_db_url_structure(db_url)
                self.metadata["db"] = self.mask_database_url(db_url)
            else:
                self.add_error("DB URL required in strict mode")

    def _validate_authz(self, args: argparse.Namespace) -> None:
        """Validate authorization evidence file."""
        if args.authz_evidence or args.strict:
            if args.authz_evidence:
                authz_meta = self.load_authz_evidence(args.authz_evidence, args.deployed_sha)
                self.metadata.update(authz_meta)
            else:
                self.add_error("Authz evidence required in strict mode")

    def _validate_actors(self, args: argparse.Namespace) -> None:
        """Verify actor separation limits."""
        if (args.proposer_id and args.determiner_id) or args.strict:
            if args.proposer_id and args.determiner_id:
                self.actors_are_distinct(args.proposer_id, args.determiner_id, args.executor_id)
                self.metadata["proposer"] = args.proposer_id[:8] + "..."
                self.metadata["determiner"] = args.determiner_id[:8] + "..."
            else:
                self.add_error("Actor IDs required in strict mode")

    def _validate_publications(self, args: argparse.Namespace) -> None:
        """Verify publication properties and ownership."""
        if args.publication_count is not None:
            self.publication_is_correct(args.publication_count, args.owner_id or "", args.expected_owner)
            self.metadata["publications"] = args.publication_count

    def _validate_revision(self, args: argparse.Namespace) -> None:
        """Validate revision hash binding."""
        if args.revision_hash:
            self.digest_is_valid(args.revision_hash, "Revision")
            self.metadata["revision"] = args.revision_hash[:8] + "..."

            if args.expected_revision_hash:
                if args.revision_hash != args.expected_revision_hash:
                    self.add_error(
                        f"Revision hash mismatch: {args.revision_hash[:8]}... vs "
                        f"expected {args.expected_revision_hash[:8]}..."
                    )
                self.metadata["expected_revision"] = args.expected_revision_hash[:8] + "..."
            elif args.strict:
                self.add_error("Expected revision hash required in strict mode")

    def validate_seed_and_publish(self, args: argparse.Namespace) -> dict[str, Any]:
        """Mode 1: Seed and publish validation."""
        self.metadata["mode"] = "seed_and_publish"

        self.git_sha_is_valid(args.deployed_sha, "Deployed")
        self.metadata["sha"] = args.deployed_sha[:8] + "..." if args.deployed_sha else "N/A"

        self._validate_digests(args)
        self._validate_db(args)
        self._validate_authz(args)
        self._validate_actors(args)
        self._validate_publications(args)
        self._validate_revision(args)

        return self.build_result()

    def _validate_restart_persistence(self, args: argparse.Namespace) -> None:
        """Validate startup source persistence."""
        if args.require_persistence:
            if args.startup_source != "persisted":
                self.add_error(f"Startup: {args.startup_source or 'N/A'} (need persisted)")
            self.metadata["startup"] = args.startup_source or "N/A"

    def _validate_restart_authz(self, args: argparse.Namespace) -> None:
        """Validate authorization proof evidence."""
        if args.authz_evidence or args.strict:
            if args.authz_evidence:
                authz_meta = self.load_authz_evidence(args.authz_evidence, args.deployed_sha)
                self.metadata.update(authz_meta)
            else:
                self.add_error("Authz evidence required in strict mode")

    def _validate_restart_scopes(self, args: argparse.Namespace) -> None:
        """Validate consistency of governed scopes."""
        if (args.before_scopes and args.after_scopes) or args.strict:
            if args.before_scopes and args.after_scopes:
                try:
                    before = json.loads(args.before_scopes)
                    after = json.loads(args.after_scopes)
                    self.scopes_are_consistent(before, after, enforce_no_loss=True)
                    self.metadata["scopes_before"] = len(before)
                    self.metadata["scopes_after"] = len(after)
                except json.JSONDecodeError as e:
                    self.add_error(f"Scope JSON error: {e}")
            else:
                self.add_error("Scopes required in strict mode")

    def _validate_restart_history(self, args: argparse.Namespace) -> None:
        """Validate execution history entries."""
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

    def _validate_restart_edge_scopes(self, args: argparse.Namespace) -> None:
        """Validate scope consistency of empty edge assertions."""
        if args.empty_edge_before_scopes and args.empty_edge_after_scopes:
            try:
                before = json.loads(args.empty_edge_before_scopes)
                after = json.loads(args.empty_edge_after_scopes)
                self.scopes_are_consistent(before, after, enforce_no_loss=True)
                self.metadata["edge_scopes_before"] = len(before)
                self.metadata["edge_scopes_after"] = len(after)
            except json.JSONDecodeError as e:
                self.add_error(f"Empty-edge JSON error: {e}")

    def validate_verify_after_restart(self, args: argparse.Namespace) -> dict[str, Any]:
        """Mode 2: Post-restart verification."""
        self.metadata["mode"] = "verify_after_restart"

        self.git_sha_is_valid(args.deployed_sha, "Deployed")
        self.metadata["sha"] = args.deployed_sha[:8] + "..." if args.deployed_sha else "N/A"

        self._validate_restart_persistence(args)
        self._validate_restart_authz(args)
        self._validate_restart_scopes(args)
        self._validate_restart_history(args)
        self._validate_restart_edge_scopes(args)

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
        # Validate output path to prevent path traversal (CWE-22)
        safe_path = validate_safe_path(output_path)
        with open(safe_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, sort_keys=True)
        print(f"Results written to {safe_path}")
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
    parser.add_argument("--deployed-sha", required=True, help="Git commit SHA at target release")
    parser.add_argument("--run-id", default=os.getenv("GITHUB_RUN_ID", "local"))
    parser.add_argument("--run-number", default=os.getenv("GITHUB_RUN_NUMBER", "0"))
    parser.add_argument("--contract-digest", help="Staging validation contract digest")
    parser.add_argument("--registry-digest", help="Staging validation registry digest")
    parser.add_argument("--database-url", help="Database connection URL")
    parser.add_argument("--authz-evidence", help="Authorization pass evidence file")
    parser.add_argument("--proposer-id", help="Proposer actor signature UUID")
    parser.add_argument("--determiner-id", help="Determiner actor signature UUID")
    parser.add_argument("--executor-id", help="Executor actor signature UUID")
    parser.add_argument("--publication-count", type=int, help="Verified publication count")
    parser.add_argument("--owner-id", help="UUID of the owner role signature")
    parser.add_argument("--expected-owner", help="Expected owner role signature UUID")
    parser.add_argument("--revision-hash", help="Validation revision hash value")
    parser.add_argument("--expected-revision-hash", help="Expected target revision hash value")
    parser.add_argument("--require-persistence", action="store_true", help="Assert startup persistence")
    parser.add_argument("--startup-source", help="Observed runtime startup source value")
    parser.add_argument("--before-scopes", help="Scope list JSON before promotion")
    parser.add_argument("--after-scopes", help="Scope list JSON after promotion")
    parser.add_argument("--history-entries", help="Execution log history entries JSON")
    parser.add_argument("--expected-min-history", type=int, default=1, help="Minimum history length")
    parser.add_argument("--empty-edge-before-scopes", help="Empty-edge scope list JSON before promotion")
    parser.add_argument("--empty-edge-after-scopes", help="Empty-edge scope list JSON after promotion")
    parser.add_argument("--output", help="Proof validation JSON output filepath")
    parser.add_argument("--strict", action="store_true", help="Fail validation on any warning")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Execute the staging proof validator."""
    try:
        parser = setup_parser()
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)

        validator = ProofValidator(
            {
                "run_id": args.run_id if hasattr(args, "run_id") else None,
                "run_number": args.run_number if hasattr(args, "run_number") else None,
            }
        )

        if args.mode == "seed_and_publish":
            result = validator.validate_seed_and_publish(args)
        else:
            result = validator.validate_verify_after_restart(args)

        display_result(result, args.output)

        return EXIT_SUCCESS if result["status"] == "passed" else EXIT_FAILURE

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_FAILURE


def verify_deployed_sha(deployed_sha: str) -> None:
    """Verify that the deployed SHA matches the current git HEAD commit."""
    if not deployed_sha or len(deployed_sha) != 40 or not all(c in "0123456789abcdef" for c in deployed_sha.lower()):
        raise ValueError("Invalid deployed SHA")
    git_path = shutil.which("git")
    if not git_path:
        raise ValueError("git command not found on PATH")
    try:
        current_sha = subprocess.check_output([git_path, "rev-parse", "HEAD"]).decode("utf-8").strip()
        if current_sha.lower() != deployed_sha.lower():
            raise ValueError("Deployed SHA mismatch")
    except subprocess.SubprocessError as e:
        raise ValueError(f"Failed to verify deployed SHA: {e}")


def check_postgresql_proof(url: str) -> None:
    """Validate PostgreSQL database URL scheme."""
    if not url:
        raise ValueError("PostgreSQL proof was skipped")
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("postgresql", "postgres"):
            raise ValueError("PostgreSQL proof was skipped")
    except Exception as e:
        raise ValueError(f"PostgreSQL proof was skipped: {e}")


def check_schema_authz_evidence(deployed_sha: str) -> None:
    """Check that the database authorization evidence exists and is valid."""
    evidence_file = REPO_ROOT / "docs" / "evidence-records" / "hp004-db-authz-pass.md"
    if not evidence_file.is_file():
        raise ValueError(f"Authorization evidence file {evidence_file} is missing or mismatched")
    content = evidence_file.read_text(encoding="utf-8")
    if "db_authz: PASS" not in content or f"commit: {deployed_sha}" not in content:
        raise ValueError("Authorization evidence is missing or mismatched")


def run_seed_and_publish(db_url: str, deployed_sha: str, run_id: str) -> dict[str, Any]:
    """Seed the database with sample projection data and publish it."""
    engine = create_engine_from_url(db_url)
    from src.data.base import Base

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        now = datetime.now(timezone.utc)

        # Create rebuild job
        job = RebuildJobORM(
            job_id=run_id,
            requested_by="staging-proof",
            status="succeeded",
            source="staging",
            created_at=now,
            updated_at=now,
            started_at=now,
            completed_at=now,
            execution_id=run_id,
        )

        # Create projection revision
        revision_id = str(uuid.uuid4())
        edge_set_hash = "a" * 64
        projection_hash = "b" * 64
        governed_scopes_list = [{"predicate_id": "scope-1", "purpose": "testing"}]

        revision = RelationshipProjectionRevisionORM(
            id=revision_id,
            purpose="testing",
            effective_at=now,
            known_at=now,
            contract_version="v1",
            projector_version="v1",
            edge_set_hash=edge_set_hash,
            projection_hash=projection_hash,
            governed_scopes=json.dumps(governed_scopes_list),
            created_at=now,
        )

        session.add(job)
        session.add(revision)
        session.flush()

        # Create publication
        publication = RelationshipProjectionPublicationORM(
            id=str(uuid.uuid4()),
            revision_id=revision_id,
            rebuild_job_id=run_id,
            published_at=now,
            execution_id=run_id,
        )

        session.add(publication)
        session.commit()

        return {
            "deployed_sha": deployed_sha,
            "run_id": run_id,
            "mode": "seed_and_publish",
            "edge_set_hash": edge_set_hash,
            "projection_hash": projection_hash,
            "governed_scopes": governed_scopes_list,
        }
    except Exception:
        import traceback

        traceback.print_exc()
        try:
            from sqlalchemy import text

            with engine.connect() as conn:
                violations = conn.execute(text("PRAGMA foreign_key_check")).fetchall()
                print("FOREIGN KEY VIOLATIONS:", violations, file=sys.stderr)
        except Exception as fk_err:
            print("Failed to run foreign_key_check:", fk_err, file=sys.stderr)
        raise
    finally:
        session.close()
        engine.dispose()


def run_verify_after_restart(
    db_url: str, deployed_sha: str, run_id: str, prev_metadata: dict[str, Any]
) -> dict[str, Any]:
    """Verify continuity and persistence after database restart."""
    engine = create_engine_from_url(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        # Query publications and check continuity
        publication = session.query(RelationshipProjectionPublicationORM).filter_by(rebuild_job_id=run_id).first()
        scope_continuity_passed = False
        historical_reconstruction_passed = False

        if publication:
            revision = session.query(RelationshipProjectionRevisionORM).filter_by(id=publication.revision_id).first()
            if revision:
                # Check edge_set_hash and projection_hash match
                if (
                    revision.edge_set_hash == prev_metadata["edge_set_hash"]
                    and revision.projection_hash == prev_metadata["projection_hash"]
                ):
                    scope_continuity_passed = True

                # Check history/rebuild jobs are well-formed
                job = session.query(RebuildJobORM).filter_by(job_id=run_id).first()
                if job and job.status == "succeeded":
                    historical_reconstruction_passed = True

        return {
            "deployed_sha": deployed_sha,
            "run_id": run_id,
            "mode": "verify_after_restart",
            "scope_continuity_passed": scope_continuity_passed,
            "historical_reconstruction_passed": historical_reconstruction_passed,
        }
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
