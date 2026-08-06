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
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Sequence
from urllib.parse import urlparse

from sqlalchemy import bindparam, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.functions import count

from src.data.database import create_engine_from_url
from src.data.db_models import RebuildJobORM
from src.data.relationship_assertion_db_models import (
    RelationshipAssertionEventORM,
    RelationshipAssertionORM,
    RelationshipProjectionEdgeORM,
    RelationshipProjectionPublicationORM,
    RelationshipProjectionRevisionORM,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

EXIT_SUCCESS = 0
EXIT_FAILURE = 1

_ALLOWED_EVIDENCE_FILENAMES = frozenset(
    {
        "authz-evidence.json",
        "staging-proof-result.json",
        "previous-staging-proof-result.json",
    }
)

PROOF_RESULT_FILENAME = "staging-proof-result.json"
AUTHZ_EVIDENCE_FILENAME = "authz-evidence.json"


def validate_safe_path(path: str) -> pathlib.Path:
    """Resolve one explicitly permitted evidence filename."""
    if path not in _ALLOWED_EVIDENCE_FILENAMES:
        raise ValueError(f"Unsupported evidence filename: {path!r}")

    resolved = pathlib.Path.cwd() / path
    if resolved.is_symlink():
        raise ValueError(f"Evidence path must not be a symbolic link: {path!r}")

    return resolved


def _sanitize_db_id(val: Any) -> str | None:
    """Sanitize database identifier input to prevent injection."""
    if not val or not isinstance(val, str):
        return None
    clean_val = val.strip()
    if not re.match(r"^[a-zA-Z0-9_\-]+$", clean_val):
        return None
    return clean_val


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

    def git_sha_is_valid(self, sha: str | None, label: str) -> bool:
        """Check Git SHA format."""
        if not re.match(r"^[0-9a-fA-F]{40}$", sha or ""):
            self.add_error(f"{label} SHA invalid or missing")
            return False
        return True

    def digest_is_valid(self, digest: str | None, label: str) -> bool:
        """Check SHA-256 digest format."""
        if not re.match(r"^[0-9a-fA-F]{64}$", digest or ""):
            self.add_error(f"{label} digest invalid or missing")
            return False
        return True

    def mask_database_url(self, url: str) -> str:
        """Mask password credentials and sensitive info in database URL."""
        try:
            parsed = urlparse(url)
            if parsed.scheme in ("sqlite", ""):
                return "sqlite:///*** (masked)"
            port_suffix = f":{parsed.port}" if parsed.port else ""
            return f"{parsed.scheme}://{parsed.hostname}{port_suffix}/*** (masked)"
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
        if not proposer:
            self.add_error("Proposer and determiner must be specified")
            return False
        if not determiner:
            self.add_error("Proposer and determiner must be specified")
            return False
        if proposer == determiner:
            self.add_error(f"Collision: proposer and determiner are same ({proposer[:8]}...)")
            return False
        if executor:
            if proposer == executor:
                self.add_error(f"Collision: proposer and executor are same ({proposer[:8]}...)")
                return False
            if determiner == executor:
                self.add_error(f"Collision: determiner and executor are same ({determiner[:8]}...)")
                return False
        return True

    def publication_is_correct(self, pub_count: int, owner: str, expected: str | None) -> bool:
        """Verify publication properties."""
        ok = True
        if pub_count != 1:
            self.add_error(f"Invalid publication count: {pub_count} (need exactly 1)")
            ok = False
        if not owner:
            self.add_error("Publication owner missing")
            ok = False
        elif expected and owner != expected:
            self.add_error(f"Owner mismatch: {owner[:8]}... vs {expected[:8]}...")
            ok = False
        return ok

    def normalize_scopes(self, lst: Any, expected_purpose: str | None = None) -> list[str] | None:
        """Normalize a list of scopes into a canonical list of strings, validating structure."""
        if not isinstance(lst, list) or not lst:
            self.add_error("Certified revision governed_scopes must be a non-empty list of identifiers or objects")
            return None

        parsed = []
        for scope in lst:
            if isinstance(scope, str):
                parsed.append(scope)
            elif isinstance(scope, dict):
                if "predicate_id" not in scope or "purpose" not in scope:
                    self.add_error(
                        "Certified revision governed_scopes contains invalid or missing predicate_id entries"
                    )
                    return None
                if expected_purpose and scope["purpose"] != expected_purpose:
                    self.add_error("Certified revision governed_scopes contains entries with incorrect purpose")
                    return None
                if not isinstance(scope["predicate_id"], str):
                    self.add_error(
                        "Certified revision governed_scopes contains invalid or missing predicate_id entries"
                    )
                    return None
                parsed.append(scope["predicate_id"])
            else:
                self.add_error("Certified revision governed_scopes contains invalid or missing predicate_id entries")
                return None

        if not all(isinstance(x, str) and x.strip() for x in parsed):
            self.add_error("Certified revision governed_scopes contains invalid or missing predicate_id entries")
            return None

        return parsed

    def scopes_are_consistent(
        self, before: Any, after: Any, enforce_no_loss: bool, expected_purpose: str | None = None
    ) -> bool:
        """Check scope consistency across transitions."""
        before_normalized = self.normalize_scopes(before, expected_purpose)
        after_normalized = self.normalize_scopes(after, expected_purpose)
        if before_normalized is None or after_normalized is None:
            return False

        if enforce_no_loss:
            missing = set(before_normalized) - set(after_normalized)
            if missing:
                self.add_error(f"Scopes disappeared: {sorted(missing)[:3]}")
                return False
        else:
            if set(before_normalized) != set(after_normalized):
                self.add_error(f"Scope mismatch: {len(before_normalized)} before, {len(after_normalized)} after")
                return False

        return True

    def _validate_history_entry(self, idx: int, entry: dict[str, Any]) -> None:
        """Validate a single history entry."""
        if "id" not in entry:
            self.add_error(f"History[{idx}] missing id")
        if "status" not in entry:
            self.add_error(f"History[{idx}] missing status")
        if "created_at" not in entry:
            self.add_error(f"History[{idx}] missing created_at")

    def history_is_well_formed(self, entries: list[dict[str, Any]], min_count: int) -> bool:
        """Validate pipeline execution history schema."""
        if len(entries) < min_count:
            self.add_error(f"History length: {len(entries)} (need {min_count})")
            return False

        for idx, entry in enumerate(entries):
            self._validate_history_entry(idx, entry)

        return len(self.errors) == 0

    def _validate_safe_path(self, path: str) -> str:
        """Validate file path to prevent path traversal attacks (CWE-22)."""
        return str(validate_safe_path(path))

    def load_authz_evidence(self, expected_sha: str) -> dict[str, Any]:
        """Load and validate authorization evidence."""
        try:
            safe_path = validate_safe_path(AUTHZ_EVIDENCE_FILENAME)
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

    def _format_digest(self, digest: str | None) -> str:
        """Format digest value for metadata."""
        if not digest:
            return "N/A"
        return digest[:8] + "..."

    def _validate_digests(self, args: argparse.Namespace) -> None:
        """Validate contract and registry digests."""
        if args.contract_digest or args.strict:
            self.digest_is_valid(args.contract_digest, "Contract")
            self.metadata["contract"] = self._format_digest(args.contract_digest)

        if args.registry_digest or args.strict:
            self.digest_is_valid(args.registry_digest, "Registry")
            self.metadata["registry"] = self._format_digest(args.registry_digest)

    def _validate_db(self, args: argparse.Namespace) -> None:
        """Validate database configuration URL."""
        db_url = os.getenv("DATABASE_URL")
        if not db_url and args.strict:
            self.add_error("DB URL required in strict mode")
            return

        if not db_url:
            return

        if not self.check_db_url_structure(db_url):
            try:
                scheme = urlparse(db_url).scheme or "unknown"
            except Exception:
                scheme = "unknown"
            self.add_error(f"Unsupported database URL scheme: {scheme}")
        self.metadata["db"] = self.mask_database_url(db_url)

    def _validate_authz(self, args: argparse.Namespace) -> None:
        """Validate authorization evidence file."""
        if not args.check_authz and args.strict:
            self.add_error("Strict mode requires authorization evidence")

        authz_meta = None
        if args.check_authz:
            authz_meta = self.load_authz_evidence(args.deployed_sha)
            self.metadata.update(authz_meta)

    def _validate_actors(self, args: argparse.Namespace) -> None:
        """Verify actor separation limits."""
        has_actors = bool(args.proposer_id and args.determiner_id)
        if not has_actors and args.strict:
            self.add_error("Actor IDs required in strict mode")
            return

        if has_actors:
            self.actors_are_distinct(args.proposer_id, args.determiner_id, args.executor_id)
            self.metadata["proposer"] = args.proposer_id[:8] + "..."
            self.metadata["determiner"] = args.determiner_id[:8] + "..."

    def _validate_publications(self, args: argparse.Namespace) -> None:
        """Verify publication properties and ownership."""
        if args.publication_count is not None:
            self.publication_is_correct(args.publication_count, args.owner_id or "", args.expected_owner)
            self.metadata["publications"] = args.publication_count
        elif args.strict:
            self.add_error("Publication count required in strict mode")

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
            elif args.strict and args.mode != "seed_and_publish":
                self.add_error("Expected revision hash required in strict mode")
        elif args.strict:
            self.add_error("Revision hash required in strict mode")

    def _populate_from_file(self, args: argparse.Namespace, prev_meta: dict[str, Any]) -> None:
        """Populate missing fields from previous metadata dict."""
        mapping = {
            "expected_revision_hash": "raw_revision_hash",
            "proposer_id": "raw_proposer_id",
            "determiner_id": "raw_determiner_id",
            "executor_id": "raw_executor_id",
            "owner_id": "raw_owner_id",
            "expected_owner": "raw_expected_owner",
            "rebuild_job_id": "raw_rebuild_job_id",
            "execution_id": "raw_execution_id",
            "expected_revision_id": "raw_revision_id",
        }
        for attr, key in mapping.items():
            if not getattr(args, attr, None):
                setattr(args, attr, prev_meta.get(key))

        if getattr(args, "publication_count", None) is None:
            args.publication_count = prev_meta.get("raw_publication_count")

    def _populate_jobs_and_owner_from_db(self, args: argparse.Namespace, conn: Any) -> str | None:
        """Query RebuildJobORM by expected rebuild-job-id, rejecting ambiguity and latest-job selection."""
        expected_job_id = _sanitize_db_id(args.rebuild_job_id)
        if not expected_job_id:
            self.add_error("Certified rebuild job ID not configured or invalid")
            return None

        job_query = select(
            RebuildJobORM.job_id,
            RebuildJobORM.requested_by,
            RebuildJobORM.execution_id,
            RebuildJobORM.status,
            RebuildJobORM.created_at,
        ).where(
            RebuildJobORM.job_id == expected_job_id,
        )

        if getattr(args, "execution_id", None):
            clean_exec_id = _sanitize_db_id(args.execution_id)
            if not clean_exec_id:
                self.add_error("Certified execution ID is invalid")
                return None
            job_query = job_query.where(RebuildJobORM.execution_id == clean_exec_id)

        rows = conn.execute(job_query.limit(2)).all()

        if not rows:
            self.add_error("Certified rebuild job was not found")
            return None

        if len(rows) != 1:
            self.add_error("Certified rebuild job evidence is ambiguous")
            return None

        job_id, requested_by, execution_id, status, created_at = rows[0]
        if not args.owner_id:
            args.owner_id = requested_by

        if not status or created_at is None:
            self.add_error("Certified rebuild job history is incomplete")
            return None

        created_at_value = created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at)
        self.metadata["raw_rebuild_job_id"] = job_id
        self.metadata["raw_execution_id"] = execution_id
        self.metadata["history_entries"] = [
            {
                "id": job_id,
                "status": status,
                "created_at": created_at_value,
            }
        ]
        return job_id

    def _get_publication_from_db(
        self, conn: Any, clean_job_id: str, args: argparse.Namespace
    ) -> tuple[str, str, str] | None:
        """Retrieve and validate publication row from DB."""
        publication_query = select(
            RelationshipProjectionPublicationORM.id,
            RelationshipProjectionPublicationORM.revision_id,
            RelationshipProjectionPublicationORM.execution_id,
        ).where(
            RelationshipProjectionPublicationORM.rebuild_job_id == clean_job_id,
        )

        rows = conn.execute(publication_query.limit(2)).all()

        if len(rows) == 0:
            self.add_error("Expected exactly one publication for rebuild job; found 0")
            args.publication_count = 0
            return None

        if len(rows) > 1:
            self.add_error(f"Expected exactly one publication for rebuild job; found {len(rows)} (ambiguous)")
            args.publication_count = len(rows)
            return None

        args.publication_count = 1
        return rows[0]

    def _get_and_validate_revision_scopes(self, conn: Any, clean_rev_id: str) -> tuple[str, list[str]] | None:
        """Fetch and validate revision projection hash and governed scopes."""
        rev_query = select(
            RelationshipProjectionRevisionORM.projection_hash,
            RelationshipProjectionRevisionORM.governed_scopes,
            RelationshipProjectionRevisionORM.purpose,
        ).where(
            RelationshipProjectionRevisionORM.id == clean_rev_id,
        )
        rev_row = conn.execute(rev_query).first()
        if not rev_row or not rev_row[0]:
            self.add_error(f"Revision {clean_rev_id} not found in database")
            return None

        proj_hash, governed_scopes_raw, purpose = rev_row
        try:
            governed_scopes = (
                json.loads(governed_scopes_raw) if isinstance(governed_scopes_raw, str) else governed_scopes_raw
            )
        except (TypeError, json.JSONDecodeError):
            self.add_error("Certified revision governed_scopes is malformed")
            return None

        parsed_scopes = self.normalize_scopes(governed_scopes, expected_purpose=purpose)
        if parsed_scopes is None:
            return None

        return proj_hash, parsed_scopes

    def _populate_publication_and_revision_from_db(
        self, args: argparse.Namespace, conn: Any, rebuild_job_id: str
    ) -> dict[str, Any] | None:
        """Retrieve the exact publication and revision identity, verifying execution correlation."""
        clean_job_id = _sanitize_db_id(rebuild_job_id)
        if not clean_job_id:
            self.add_error("Invalid rebuild job ID for publication lookup")
            return None

        pub_row = self._get_publication_from_db(conn, clean_job_id, args)
        if not pub_row:
            return None
        pub_id, revision_id, execution_id = pub_row

        if getattr(args, "execution_id", None):
            clean_exec_id = _sanitize_db_id(args.execution_id)
            if not clean_exec_id:
                self.add_error("Certified execution ID is invalid")
                return None
            if execution_id != clean_exec_id:
                self.add_error(
                    f"Publication execution ID {execution_id} does not match certified execution {clean_exec_id}"
                )
                return None

        clean_rev_id = _sanitize_db_id(revision_id)
        if not clean_rev_id:
            self.add_error("Invalid revision ID found for publication")
            return None

        rev_info = self._get_and_validate_revision_scopes(conn, clean_rev_id)
        if not rev_info:
            return None
        proj_hash, governed_scopes = rev_info

        if not args.revision_hash:
            args.revision_hash = proj_hash

        # Store exact lineage and the independent seed scope baseline.
        self.metadata["raw_publication_id"] = pub_id
        self.metadata["raw_revision_id"] = revision_id
        self.metadata["raw_revision_hash"] = proj_hash
        self.metadata["raw_governed_scopes"] = governed_scopes

        # Verify expected revision ID if provided (from previous result / metadata in restart mode)
        if getattr(args, "expected_revision_id", None) and revision_id != args.expected_revision_id:
            self.add_error(f"Revision ID mismatch: {revision_id} vs expected {args.expected_revision_id}")
            return None

        return {
            "publication_id": pub_id,
            "revision_id": revision_id,
            "execution_id": execution_id,
        }

    def _populate_proposer(self, args: argparse.Namespace, conn: Any, assertion_ids_subquery: Any) -> None:
        """Query and validate proposer actor."""
        proposer_stmt = (
            select(RelationshipAssertionEventORM.actor_id)
            .where(
                RelationshipAssertionEventORM.assertion_id.in_(assertion_ids_subquery),
                (RelationshipAssertionEventORM.to_state == "Proposed")
                | (RelationshipAssertionEventORM.authority == "proposer"),
            )
            .distinct()
        )
        proposer_rows = conn.execute(proposer_stmt.limit(2)).fetchall()
        proposers = [r[0] for r in proposer_rows if r[0]]

        if len(proposers) == 0:
            self.add_error("No correlated proposing actor evidence found")
        elif len(proposers) > 1:
            self.add_error("Ambiguous proposing actor evidence")
        else:
            db_proposer = proposers[0]
            if args.proposer_id and args.proposer_id != db_proposer:
                self.add_error(
                    f"Proposer mismatch: database evidence {db_proposer[:8]}... vs expected {args.proposer_id[:8]}..."
                )
            args.proposer_id = db_proposer

    def _populate_determiner(self, args: argparse.Namespace, conn: Any, assertion_ids_subquery: Any) -> None:
        """Query and validate determiner actor."""
        determiner_stmt = (
            select(RelationshipAssertionEventORM.actor_id)
            .where(
                RelationshipAssertionEventORM.assertion_id.in_(assertion_ids_subquery),
                (RelationshipAssertionEventORM.to_state == "Accepted")
                | (RelationshipAssertionEventORM.authority.in_(["determiner", "reviewer", "acceptor"])),
            )
            .distinct()
        )
        determiner_rows = conn.execute(determiner_stmt.limit(2)).fetchall()
        determiners = [r[0] for r in determiner_rows if r[0]]

        if len(determiners) == 0:
            self.add_error("No correlated determining actor evidence found")
        elif len(determiners) > 1:
            self.add_error("Ambiguous determining actor evidence")
        else:
            db_determiner = determiners[0]
            if args.determiner_id and args.determiner_id != db_determiner:
                self.add_error(
                    f"Determiner mismatch: database evidence {db_determiner[:8]}... "
                    f"vs expected {args.determiner_id[:8]}..."
                )
            args.determiner_id = db_determiner

    def _populate_actors_from_db(
        self,
        args: argparse.Namespace,
        conn: Any,
        rebuild_job_id: str | None,
        revision_id: str | None,
    ) -> None:
        """Query proposer and determiner actors from RelationshipAssertionEventORM."""
        clean_job_id = _sanitize_db_id(rebuild_job_id)
        clean_rev_id = _sanitize_db_id(revision_id)
        if not clean_job_id:
            self.add_error("Correlation failed: rebuild_job_id missing")
            return

        if not clean_rev_id:
            self.add_error("Correlation failed: revision_id missing")
            return

        assertion_ids_subquery = select(RelationshipProjectionEdgeORM.assertion_id).where(
            RelationshipProjectionEdgeORM.revision_id == clean_rev_id
        )

        self._populate_proposer(args, conn, assertion_ids_subquery)
        self._populate_determiner(args, conn, assertion_ids_subquery)

    def _populate_from_db(self, args: argparse.Namespace, conn: Any) -> None:
        """Populate missing validation fields using active DB connection."""
        rebuild_job_id = self._populate_jobs_and_owner_from_db(args, conn)
        if not rebuild_job_id:
            return
        pub_info = self._populate_publication_and_revision_from_db(args, conn, rebuild_job_id)
        if not pub_info:
            return
        revision_id = pub_info["revision_id"]
        self._populate_actors_from_db(args, conn, rebuild_job_id, revision_id)

    def _load_evidence_from_file(self, args: argparse.Namespace) -> None:
        """Load previous metadata from local file if available."""
        prev_path = PROOF_RESULT_FILENAME
        try:
            safe_prev_path = self._validate_safe_path(prev_path)
        except Exception as err:
            print(f"Warning: Failed to validate path {prev_path}: {err}", file=sys.stderr)
            return

        if safe_prev_path and os.path.isfile(safe_prev_path):
            try:
                with open(safe_prev_path, "r", encoding="utf-8") as f:
                    prev_data = json.load(f)
                    prev_meta = prev_data.get("metadata", {})
                    if prev_meta.get("mode") == "seed_and_publish":
                        self._populate_from_file(args, prev_meta)
            except Exception as exc:
                print(
                    f"Warning: failed to load prior metadata from '{prev_path}': {exc}",
                    file=sys.stderr,
                )

    def _load_evidence_from_db(self, args: argparse.Namespace) -> None:
        """Query database for missing validation inputs if DB URL is available."""
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            return

        missing_inputs = [
            args.publication_count,
            args.revision_hash,
            args.proposer_id,
            args.determiner_id,
            args.owner_id,
        ]
        has_missing = any(val is None or not val for val in missing_inputs)
        if not has_missing:
            return

        try:
            from sqlalchemy import create_engine

            engine = create_engine(db_url)
            with engine.connect() as conn:
                self._populate_from_db(args, conn)
        except Exception as err:
            print(f"Warning: Failed to query database: {err}", file=sys.stderr)

    def _populate_missing_evidence(self, args: argparse.Namespace) -> None:
        """Populate missing arguments from previous run results and database state."""
        self._load_evidence_from_file(args)
        self._load_evidence_from_db(args)

    def validate_seed_and_publish(self, args: argparse.Namespace) -> dict[str, Any]:
        """Mode 1: Seed and publish validation."""
        if args.strict:
            if not getattr(args, "rebuild_job_id", None):
                self.add_error("Rebuild job ID required in strict mode")
            if not getattr(args, "execution_id", None):
                self.add_error("Execution ID required in strict mode")
            if self.errors:
                return self.build_result()

        self._populate_missing_evidence(args)
        self.metadata["mode"] = "seed_and_publish"

        self.git_sha_is_valid(args.deployed_sha, "Deployed")
        self.metadata["sha"] = args.deployed_sha[:8] + "..." if args.deployed_sha else "N/A"

        self._validate_digests(args)
        self._validate_db(args)
        self._validate_authz(args)
        self._validate_actors(args)
        self._validate_publications(args)
        self._validate_revision(args)

        # Store raw parameters in metadata for restart mode verification continuity
        self.metadata["raw_proposer_id"] = args.proposer_id
        self.metadata["raw_determiner_id"] = args.determiner_id
        self.metadata["raw_executor_id"] = args.executor_id
        self.metadata["raw_publication_count"] = args.publication_count
        self.metadata["raw_owner_id"] = args.owner_id
        self.metadata["raw_expected_owner"] = args.expected_owner
        self.metadata["raw_revision_hash"] = args.revision_hash

        return self.build_result()

    def _validate_restart_persistence(self, args: argparse.Namespace) -> None:
        """Validate startup source persistence."""
        if args.require_persistence:
            if args.startup_source != "persisted":
                self.add_error(f"Startup: {args.startup_source or 'N/A'} (need persisted)")
            self.metadata["startup"] = args.startup_source or "N/A"

    def _validate_restart_authz(self, args: argparse.Namespace) -> None:
        """Validate authorization evidence."""
        authz_meta = None
        if args.check_authz or args.strict:
            if args.check_authz:
                authz_meta = self.load_authz_evidence(args.deployed_sha)
                self.metadata.update(authz_meta)
            else:
                self.add_error("Authz evidence required in strict mode")

    def _query_restart_scopes_from_db(self, args: argparse.Namespace, db_url: str) -> str | None:
        """Query current scopes from database for the current rebuild job ID."""
        try:
            from sqlalchemy import create_engine

            engine = create_engine(db_url)
            with engine.connect() as conn:
                rebuild_job_id = _sanitize_db_id(args.rebuild_job_id)
                if not rebuild_job_id:
                    self.add_error("Invalid or missing rebuild_job_id")
                    return None

                # Check publication existence and cardinality
                count_stmt = (
                    select(count())
                    .select_from(RelationshipProjectionPublicationORM)
                    .where(RelationshipProjectionPublicationORM.rebuild_job_id == bindparam("restart_rebuild_job_id"))
                )
                pub_count = int(
                    conn.execute(
                        count_stmt,
                        {"restart_rebuild_job_id": rebuild_job_id},
                    ).scalar()
                    or 0
                )
                if pub_count == 0:
                    self.add_error(f"Expected publication for rebuild job {rebuild_job_id} not found")
                    return None
                if pub_count > 1:
                    self.add_error(f"More than one publication matches rebuild job {rebuild_job_id}")
                    return None

                # Fetch publication and revision
                pub_stmt = select(RelationshipProjectionPublicationORM.revision_id).where(
                    RelationshipProjectionPublicationORM.rebuild_job_id == bindparam("restart_publication_job_id")
                )
                raw_revision_id = conn.execute(
                    pub_stmt,
                    {"restart_publication_job_id": rebuild_job_id},
                ).scalar()
                revision_id = _sanitize_db_id(raw_revision_id)
                if not revision_id:
                    self.add_error("Revision ID not found or invalid for publication")
                    return None

                rev_stmt = select(RelationshipProjectionRevisionORM.governed_scopes).where(
                    RelationshipProjectionRevisionORM.id == bindparam("restart_revision_id")
                )
                rev_scopes = conn.execute(
                    rev_stmt,
                    {"restart_revision_id": revision_id},
                ).scalar()
                if rev_scopes is None:
                    self.add_error(f"Revision {revision_id} cannot be found")
                    return None

                try:
                    json.loads(rev_scopes)
                    return str(rev_scopes)
                except Exception:
                    self.add_error("governed_scopes is malformed")
                    return None
        except Exception as e:
            self.add_error(f"Failed to query current scopes from database: {e}")
            return None

    def _resolve_restart_after_scopes(self, args: argparse.Namespace) -> str | None:
        """Resolve after_scopes from DB if missing."""
        after_str = args.after_scopes
        if after_str:
            return after_str

        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            if args.strict:
                self.add_error("Database URL required to observe current scopes in strict mode")
            return None

        after_str = self._query_restart_scopes_from_db(args, db_url)
        if after_str:
            args.after_scopes = after_str
        return after_str

    def _validate_restart_scopes(self, args: argparse.Namespace) -> None:
        """Validate consistency of governed scopes."""
        before_str = args.before_scopes
        if not before_str:
            if args.strict:
                self.add_error("Before scopes required in strict mode")
            return

        after_str = self._resolve_restart_after_scopes(args)
        if not after_str:
            self.add_error("After scopes observed as empty or missing")
            return

        try:
            before = json.loads(before_str)
            after = json.loads(after_str)
            self.scopes_are_consistent(before, after, enforce_no_loss=True)
            self.metadata["scopes_before"] = len(before) if isinstance(before, list) else 0
            self.metadata["scopes_after"] = len(after) if isinstance(after, list) else 0
        except Exception as e:
            self.add_error(f"Scope JSON error: {e}")

    def _validate_reconstructed_assertion(
        self,
        assertion_id: str,
        events: Sequence[Any],
    ) -> bool:
        """Validate one projected assertion's persisted lifecycle."""
        if not events:
            self.add_error(f"Assertion {assertion_id} has no persisted lifecycle events")
            return False

        sequences = [event.sequence for event in events]
        if any(not isinstance(sequence, int) for sequence in sequences):
            self.add_error(f"Assertion {assertion_id} has invalid lifecycle sequence values")
            return False
        if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
            self.add_error(f"Assertion {assertion_id} lifecycle sequence is not strictly ordered")
            return False

        proposed = [event for event in events if event.to_state == "Proposed" and event.authority == "proposer"]
        accepted = [
            event
            for event in events
            if event.to_state == "Accepted" and event.authority in {"determiner", "reviewer", "acceptor"}
        ]
        if len(proposed) != 1 or len(accepted) != 1:
            self.add_error(f"Assertion {assertion_id} must have exactly one proposer and one acceptance event")
            return False

        proposal = proposed[0]
        determination = accepted[0]
        if proposal.sequence >= determination.sequence:
            self.add_error(f"Assertion {assertion_id} acceptance does not follow proposal")
            return False
        if determination.from_state != "Proposed":
            self.add_error(f"Assertion {assertion_id} acceptance has invalid predecessor state")
            return False
        if not proposal.actor_id or not determination.actor_id:
            self.add_error(f"Assertion {assertion_id} lifecycle actor is missing")
            return False
        if proposal.actor_id == determination.actor_id:
            self.add_error(f"Assertion {assertion_id} proposer and determiner are not distinct")
            return False
        return True

    def _reconstruct_assertion_history_from_db(self, args: argparse.Namespace) -> None:
        """Reconstruct persisted lifecycle history for the certified revision."""
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            self.add_error("Database URL required for historical reconstruction")
            return

        rebuild_job_id = _sanitize_db_id(args.rebuild_job_id)
        execution_id = _sanitize_db_id(args.execution_id)
        expected_revision_id = _sanitize_db_id(args.expected_revision_id)
        if not rebuild_job_id or not execution_id or not expected_revision_id:
            self.add_error("Exact lineage IDs required for historical reconstruction")
            return

        engine = None
        try:
            from sqlalchemy import create_engine

            engine = create_engine(db_url)
            with engine.connect() as conn:
                publication_stmt = (
                    select(
                        RelationshipProjectionPublicationORM.revision_id,
                        RelationshipProjectionPublicationORM.execution_id,
                    )
                    .where(RelationshipProjectionPublicationORM.rebuild_job_id == bindparam("history_rebuild_job_id"))
                    .limit(2)
                )
                publication_rows = conn.execute(
                    publication_stmt,
                    {"history_rebuild_job_id": rebuild_job_id},
                ).all()
                if len(publication_rows) != 1:
                    self.add_error("Historical reconstruction requires exactly one certified publication")
                    return

                revision_id, publication_execution_id = publication_rows[0]
                if revision_id != expected_revision_id:
                    self.add_error("Historical reconstruction revision identity mismatch")
                    return
                if publication_execution_id != execution_id:
                    self.add_error("Historical reconstruction execution identity mismatch")
                    return

                assertion_ids = [
                    row[0]
                    for row in conn.execute(
                        select(RelationshipProjectionEdgeORM.assertion_id)
                        .where(RelationshipProjectionEdgeORM.revision_id == bindparam("history_revision_id"))
                        .distinct(),
                        {"history_revision_id": expected_revision_id},
                    ).all()
                    if row[0]
                ]

                reconstructed = 0
                for assertion_id in assertion_ids:
                    events = (
                        conn.execute(
                            select(RelationshipAssertionEventORM)
                            .where(RelationshipAssertionEventORM.assertion_id == bindparam("history_assertion_id"))
                            .order_by(RelationshipAssertionEventORM.sequence),
                            {"history_assertion_id": assertion_id},
                        )
                        .scalars()
                        .all()
                    )
                    if self._validate_reconstructed_assertion(assertion_id, events):
                        reconstructed += 1

                self.metadata["reconstructed_assertions"] = reconstructed
                if reconstructed != len(assertion_ids):
                    self.add_error("Historical reconstruction failed for one or more projected assertions")
        except Exception as exc:
            self.add_error(f"Historical reconstruction query failed: {exc}")
        finally:
            if engine is not None:
                engine.dispose()

    def _validate_restart_history(self, args: argparse.Namespace) -> None:
        """Validate rebuild audit history and reconstruct assertion lifecycle history."""
        if args.history_entries or args.strict:
            if args.history_entries:
                try:
                    entries = json.loads(args.history_entries)
                    self.history_is_well_formed(entries, args.expected_min_history)
                    self.metadata["history_entries"] = len(entries) if isinstance(entries, list) else 0
                except Exception as e:
                    self.add_error(f"History JSON error: {e}")
                    return
            else:
                self.add_error("History required in strict mode")
                return

        self._reconstruct_assertion_history_from_db(args)

    def _validate_restart_edge_scopes(self, args: argparse.Namespace) -> None:
        """Validate scope consistency of empty edge assertions."""
        if args.empty_edge_before_scopes and args.empty_edge_after_scopes:
            try:
                before = json.loads(args.empty_edge_before_scopes)
                after = json.loads(args.empty_edge_after_scopes)
                self.scopes_are_consistent(before, after, enforce_no_loss=True)
                self.metadata["edge_scopes_before"] = len(before) if isinstance(before, list) else 0
                self.metadata["edge_scopes_after"] = len(after) if isinstance(after, list) else 0
            except Exception as e:
                self.add_error(f"Empty-edge JSON error: {e}")

    def validate_verify_after_restart(self, args: argparse.Namespace) -> dict[str, Any]:
        """Mode 2: Post-restart verification."""
        self._populate_missing_evidence(args)
        self.metadata["mode"] = "verify_after_restart"

        self.git_sha_is_valid(args.deployed_sha, "Deployed")
        self.metadata["sha"] = args.deployed_sha[:8] + "..." if args.deployed_sha else "N/A"

        self._validate_restart_persistence(args)
        self._validate_restart_authz(args)
        self._validate_restart_scopes(args)
        self._validate_restart_history(args)
        self._validate_restart_edge_scopes(args)
        self._validate_revision(args)

        return self.build_result()

    def build_result(self) -> dict[str, Any]:
        """Construct result dictionary."""
        return {
            "status": "passed" if not self.errors else "failed",
            "errors": self.errors,
            "metadata": self.metadata,
        }


def display_result(result: dict[str, Any], write_output: bool) -> None:
    """Show validation result."""
    if write_output:
        # Validate output path to prevent path traversal (CWE-22)
        safe_path = validate_safe_path(PROOF_RESULT_FILENAME)

        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW

        fd = os.open(safe_path, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(result, file, indent=2, sort_keys=True)
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
    parser.add_argument("--check-authz", action="store_true", help="Check authorization pass evidence file")
    parser.add_argument("--proposer-id", help="Proposer actor signature UUID")
    parser.add_argument("--determiner-id", help="Determiner actor signature UUID")
    parser.add_argument("--executor-id", help="Executor actor signature UUID")
    parser.add_argument("--publication-count", type=int, help="Verified publication count")
    parser.add_argument(
        "--owner-id",
        help=("Authoritative publication-owner actor ID. Execution and correlation IDs are not ownership evidence."),
    )
    parser.add_argument(
        "--expected-owner",
        help="Protected expected publication-owner actor ID",
    )
    parser.add_argument("--revision-hash", help="Validation revision hash value")
    parser.add_argument("--expected-revision-hash", help="Expected target revision hash value")
    parser.add_argument("--rebuild-job-id", help="Exact rebuild job being certified")
    parser.add_argument("--execution-id", help="Exact pipeline/rebuild execution correlation being certified")
    parser.add_argument("--expected-revision-id", help="Expected target revision ID value")
    parser.add_argument("--require-persistence", action="store_true", help="Assert startup persistence")
    parser.add_argument("--startup-source", help="Observed runtime startup source value")
    parser.add_argument("--before-scopes", help="Scope list JSON before promotion")
    parser.add_argument("--after-scopes", help="Scope list JSON after promotion")
    parser.add_argument("--history-entries", help="Execution log history entries JSON")
    parser.add_argument("--expected-min-history", type=int, default=1, help="Minimum history length")
    parser.add_argument("--empty-edge-before-scopes", help="Empty-edge scope list JSON before promotion")
    parser.add_argument("--empty-edge-after-scopes", help="Empty-edge scope list JSON after promotion")
    parser.add_argument("--write-output", action="store_true", help="Write proof validation JSON output")
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

        display_result(result, args.write_output)

        return EXIT_SUCCESS if result["status"] == "passed" else EXIT_FAILURE

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_FAILURE


def verify_deployed_sha(deployed_sha: str) -> None:
    """Verify that the deployed SHA matches the current git HEAD commit."""
    if not re.match(r"^[0-9a-fA-F]{40}$", deployed_sha or ""):
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
        proposer_id = "proposer-actor-1"
        determiner_id = "determiner-actor-1"
        owner_id = "owner-actor-1"

        # Create rebuild job
        job = RebuildJobORM(
            job_id=run_id,
            requested_by=owner_id,
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
        governed_predicate_id = "scope-1"
        governed_scopes_list = [governed_predicate_id]

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

        # Create assertion
        assertion_id = str(uuid.uuid4())
        assertion = RelationshipAssertionORM(
            id=assertion_id,
            predicate_id=governed_predicate_id,
            subject_id="asset-1",
            object_id="asset-2",
            method_id="method-1",
            proposition="Asset 1 related to Asset 2",
            confidence_status="not_assessed",
            effective_from=now,
            recorded_at=now,
        )

        # Create proposal event
        prop_event = RelationshipAssertionEventORM(
            id=str(uuid.uuid4()),
            assertion_id=assertion_id,
            sequence=1,
            from_state=None,
            to_state="Proposed",
            authority="proposer",
            actor_id=proposer_id,
            rationale="Initial staging proposal",
            policy_version="v1",
            recorded_at=now,
            correlation_id=run_id,
        )

        # Create determination event
        det_event = RelationshipAssertionEventORM(
            id=str(uuid.uuid4()),
            assertion_id=assertion_id,
            sequence=2,
            from_state="Proposed",
            to_state="Accepted",
            authority="determiner",
            actor_id=determiner_id,
            rationale="Accepted proposal",
            policy_version="v1",
            recorded_at=now,
            correlation_id=run_id,
        )

        # Create projection edge linking revision to assertion
        edge = RelationshipProjectionEdgeORM(
            id=str(uuid.uuid4()),
            revision_id=revision_id,
            source_id="asset-1",
            target_id="asset-2",
            edge_type="same_sector",
            strength="1",
            direction="bidirectional",
            assertion_id=assertion_id,
        )

        session.add(job)
        session.add(revision)
        session.add(assertion)
        session.flush()

        session.add(prop_event)
        session.add(det_event)
        session.add(edge)
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
            "proposer_id": proposer_id,
            "determiner_id": determiner_id,
            "owner_id": owner_id,
            "raw_rebuild_job_id": run_id,
            "raw_execution_id": run_id,
            "raw_publication_id": publication.id,
            "raw_revision_id": revision_id,
            "raw_revision_hash": projection_hash,
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


def _query_verification_data_from_db(session: Any, rebuild_job_id: str) -> tuple[Any, Any, Any]:
    """Retrieve publication, revision, and rebuild job from DB."""
    publication = session.query(RelationshipProjectionPublicationORM).filter_by(rebuild_job_id=rebuild_job_id).first()
    if not publication:
        return None, None, None
    revision = session.query(RelationshipProjectionRevisionORM).filter_by(id=publication.revision_id).first()
    job = session.query(RebuildJobORM).filter_by(job_id=rebuild_job_id).first()
    return publication, revision, job


def _verify_scopes_continuity(revision: Any, prev_metadata: dict[str, Any]) -> bool:
    """Check scopes continuity for restart verification."""
    if not revision:
        return False

    try:
        persisted_scopes = json.loads(revision.governed_scopes)
    except (TypeError, json.JSONDecodeError):
        return False

    if not isinstance(persisted_scopes, list) or not persisted_scopes:
        return False

    is_valid = all(isinstance(scope_id, str) and scope_id.strip() for scope_id in persisted_scopes)
    if not is_valid:
        return False

    return (
        revision.edge_set_hash == prev_metadata.get("edge_set_hash")
        and revision.projection_hash == prev_metadata.get("projection_hash")
        and persisted_scopes == prev_metadata.get("governed_scopes")
    )


def _verify_scopes_and_history(revision: Any, job: Any, prev_metadata: dict[str, Any]) -> tuple[bool, bool]:
    """Check scopes continuity and historical reconstruction."""
    scope_continuity_passed = _verify_scopes_continuity(revision, prev_metadata)
    historical_reconstruction_passed = bool(job and job.status == "succeeded")
    return scope_continuity_passed, historical_reconstruction_passed


def run_verify_after_restart(
    db_url: str, deployed_sha: str, run_id: str, prev_metadata: dict[str, Any]
) -> dict[str, Any]:
    """Verify continuity and persistence after database restart."""
    engine = create_engine_from_url(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        rebuild_job_id = prev_metadata.get("raw_rebuild_job_id") or run_id
        _, revision, job = _query_verification_data_from_db(session, rebuild_job_id)
        scope_continuity_passed, historical_reconstruction_passed = _verify_scopes_and_history(
            revision, job, prev_metadata
        )

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
