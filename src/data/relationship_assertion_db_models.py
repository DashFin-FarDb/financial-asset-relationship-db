"""SQLAlchemy ORM models for GRAC v1 governed assertion persistence.

Seven additive tables only. Existing graph tables (including ``asset_relationships``)
are not modified. Rows are append-only; immutability is enforced by dialect-aware
triggers installed via ``relationship_assertion_schema``.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.data.base import Base

# ---------------------------------------------------------------------------
# Foreign key target constants (avoid duplicated string literals – Sonar S1192)
# ---------------------------------------------------------------------------

RELATIONSHIP_EVIDENCE_ID_FK = "relationship_evidence.id"
RELATIONSHIP_ASSERTIONS_ID_FK = "relationship_assertions.id"
RELATIONSHIP_PROJECTION_REVISIONS_ID_FK = "relationship_projection_revisions.id"
REBUILD_JOBS_JOB_ID_FK = "rebuild_jobs.job_id"

CONFIDENCE_STATUS_CHECK = "confidence_status IN ('assessed', 'not_assessed')"
CONFIDENCE_ASSESSED_CHECK = (
    "(confidence_status = 'not_assessed' AND confidence_bp IS NULL "
    "AND confidence_type IS NULL AND confidence_method IS NULL) OR "
    "(confidence_status = 'assessed' AND confidence_bp IS NOT NULL "
    "AND confidence_type IS NOT NULL AND confidence_method IS NOT NULL)"
)
CONFIDENCE_BP_RANGE_CHECK = "confidence_bp IS NULL OR (confidence_bp >= 0 AND confidence_bp <= 10000)"
POLARITY_CHECK = "polarity IN ('supporting', 'opposing', 'contextual')"
LIFECYCLE_STATES = "'Proposed', 'Accepted', 'Rejected', 'Withdrawn', 'Disputed', 'Retracted', 'Superseded'"
FROM_STATE_CHECK = f"from_state IS NULL OR from_state IN ({LIFECYCLE_STATES})"
TO_STATE_CHECK = f"to_state IN ({LIFECYCLE_STATES})"
DIRECTION_CHECK = "direction IN ('subject_to_object', 'object_to_subject', 'bidirectional')"
VISIBILITY_CHECK = "visibility IN ('public', 'internal', 'restricted', 'confidential')"
# Portable lowercase hex / decimal-string CHECKs (SQLite + PostgreSQL).
SHA256_HEX_CHECK = (
    "length({column}) = 64 AND {column} = lower({column}) AND translate({column}, '0123456789abcdef', '') = ''"
)
STRENGTH_DECIMAL_CHECK = (
    "length(strength) BETWEEN 1 AND 32 "
    "AND translate(strength, '0123456789.', '') = '' "
    "AND strength NOT LIKE '.%' AND strength NOT LIKE '%.' "
    "AND strength NOT LIKE '%..%' AND strength NOT LIKE '%.%.%' "
    "AND (strength = '0' OR strength = '1' OR strength LIKE '0.%' "
    "OR (strength LIKE '1.%' AND replace(substr(strength, 3), '0', '') = ''))"
)

EFFECTIVE_WINDOW_CHECK = "effective_to IS NULL OR effective_to >= effective_from"


class RelationshipEvidenceORM(Base):
    """Immutable evidence reference (no body bytes in v1)."""

    __tablename__ = "relationship_evidence"
    __table_args__ = (
        CheckConstraint(VISIBILITY_CHECK, name="ck_relationship_evidence_visibility"),
        CheckConstraint(
            SHA256_HEX_CHECK.format(column="content_sha256"),
            name="ck_relationship_evidence_sha256_hex",
        ),
        Index("ix_relationship_evidence_content_sha256", "content_sha256"),
        Index("ix_relationship_evidence_recorded_at", "recorded_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_ref: Mapped[str] = mapped_column(String(2048), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    media_type: Mapped[str] = mapped_column(String(128), nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False)
    licensing: Mapped[str | None] = mapped_column(String(512), nullable=True)
    reuse_policy: Mapped[str | None] = mapped_column(String(512), nullable=True)
    custody_id: Mapped[str] = mapped_column(String(128), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RelationshipAssertionORM(Base):
    """Immutable proposition row with confidence and effective-time axes."""

    __tablename__ = "relationship_assertions"
    __table_args__ = (
        CheckConstraint(CONFIDENCE_STATUS_CHECK, name="ck_relationship_assertions_confidence_status"),
        CheckConstraint(CONFIDENCE_BP_RANGE_CHECK, name="ck_relationship_assertions_confidence_bp"),
        CheckConstraint(CONFIDENCE_ASSESSED_CHECK, name="ck_relationship_assertions_confidence_assessed"),
        Index("ix_relationship_assertions_predicate_subject", "predicate_id", "subject_id"),
        CheckConstraint(EFFECTIVE_WINDOW_CHECK, name="ck_relationship_assertions_effective_window"),
        Index("ix_relationship_assertions_recorded_at", "recorded_at"),
        Index("ix_relationship_assertions_effective_from", "effective_from"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    predicate_id: Mapped[str] = mapped_column(String(256), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(128), nullable=False)
    object_id: Mapped[str] = mapped_column(String(128), nullable=False)
    method_id: Mapped[str] = mapped_column(String(256), nullable=False)
    proposition: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence_method: Mapped[str | None] = mapped_column(String(256), nullable=True)
    confidence_status: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RelationshipAssertionEvidenceORM(Base):
    """Append-only polarity link between an assertion and evidence."""

    __tablename__ = "relationship_assertion_evidence"
    __table_args__ = (
        CheckConstraint(POLARITY_CHECK, name="ck_relationship_assertion_evidence_polarity"),
        UniqueConstraint(
            "assertion_id",
            "evidence_id",
            name="uq_relationship_assertion_evidence_link",
        ),
        Index("ix_relationship_assertion_evidence_assertion_id", "assertion_id"),
        Index("ix_relationship_assertion_evidence_evidence_id", "evidence_id"),
        Index("ix_relationship_assertion_evidence_recorded_at", "recorded_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    assertion_id: Mapped[str] = mapped_column(
        ForeignKey(RELATIONSHIP_ASSERTIONS_ID_FK, ondelete="RESTRICT"),
        nullable=False,
    )
    evidence_id: Mapped[str] = mapped_column(
        ForeignKey(RELATIONSHIP_EVIDENCE_ID_FK, ondelete="RESTRICT"),
        nullable=False,
    )
    polarity: Mapped[str] = mapped_column(String(32), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RelationshipAssertionEventORM(Base):
    """Ordered lifecycle and authority history for an assertion."""

    __tablename__ = "relationship_assertion_events"
    __table_args__ = (
        CheckConstraint(FROM_STATE_CHECK, name="ck_relationship_assertion_events_from_state"),
        CheckConstraint(TO_STATE_CHECK, name="ck_relationship_assertion_events_to_state"),
        CheckConstraint("sequence >= 1", name="ck_relationship_assertion_events_sequence"),
        UniqueConstraint(
            "assertion_id",
            "sequence",
            name="uq_relationship_assertion_events_sequence",
        ),
        Index("ix_relationship_assertion_events_assertion_id", "assertion_id"),
        Index("ix_relationship_assertion_events_recorded_at", "recorded_at"),
        Index("ix_relationship_assertion_events_successor_assertion_id", "successor_assertion_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    assertion_id: Mapped[str] = mapped_column(
        ForeignKey(RELATIONSHIP_ASSERTIONS_ID_FK, ondelete="RESTRICT"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    authority: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    successor_assertion_id: Mapped[str | None] = mapped_column(
        ForeignKey(RELATIONSHIP_ASSERTIONS_ID_FK, ondelete="RESTRICT"),
        nullable=True,
    )
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class RelationshipProjectionRevisionORM(Base):
    """Deterministic candidate graph revision with content hashes."""

    __tablename__ = "relationship_projection_revisions"
    __table_args__ = (
        CheckConstraint(
            SHA256_HEX_CHECK.format(column="edge_set_hash"),
            name="ck_relationship_projection_revisions_edge_set_hash_hex",
        ),
        CheckConstraint(
            SHA256_HEX_CHECK.format(column="projection_hash"),
            name="ck_relationship_projection_revisions_projection_hash_hex",
        ),
        Index("ix_relationship_projection_revisions_purpose", "purpose"),
        Index("ix_relationship_projection_revisions_created_at", "created_at"),
        Index(
            "ix_relationship_projection_revisions_effective_known",
            "effective_at",
            "known_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(128), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    known_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    projector_version: Mapped[str] = mapped_column(String(64), nullable=False)
    edge_set_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    projection_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    governed_scopes: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RelationshipProjectionEdgeORM(Base):
    """Materialized governed edge belonging to a projection revision."""

    __tablename__ = "relationship_projection_edges"
    __table_args__ = (
        CheckConstraint(DIRECTION_CHECK, name="ck_relationship_projection_edges_direction"),
        CheckConstraint(STRENGTH_DECIMAL_CHECK, name="ck_relationship_projection_edges_strength"),
        Index("ix_relationship_projection_edges_revision_id", "revision_id"),
        Index("ix_relationship_projection_edges_assertion_id", "assertion_id"),
        Index(
            "ix_relationship_projection_edges_source_target",
            "source_id",
            "target_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    revision_id: Mapped[str] = mapped_column(
        ForeignKey(RELATIONSHIP_PROJECTION_REVISIONS_ID_FK, ondelete="RESTRICT"),
        nullable=False,
    )
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    edge_type: Mapped[str] = mapped_column(String(128), nullable=False)
    strength: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str] = mapped_column(String(32), nullable=False)
    assertion_id: Mapped[str] = mapped_column(
        ForeignKey(RELATIONSHIP_ASSERTIONS_ID_FK, ondelete="RESTRICT"),
        nullable=False,
    )


class RelationshipProjectionPublicationORM(Base):
    """Append-only proof that a succeeded rebuild published a revision."""

    __tablename__ = "relationship_projection_publications"
    __table_args__ = (
        UniqueConstraint(
            "revision_id",
            "rebuild_job_id",
            name="uq_relationship_projection_publications_rev_job",
        ),
        Index("ix_relationship_projection_publications_revision_id", "revision_id"),
        Index("ix_relationship_projection_publications_rebuild_job_id", "rebuild_job_id"),
        Index("ix_relationship_projection_publications_published_at", "published_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    revision_id: Mapped[str] = mapped_column(
        ForeignKey(RELATIONSHIP_PROJECTION_REVISIONS_ID_FK, ondelete="RESTRICT"),
        nullable=False,
    )
    rebuild_job_id: Mapped[str] = mapped_column(
        ForeignKey(REBUILD_JOBS_JOB_ID_FK, ondelete="RESTRICT"),
        nullable=False,
    )
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


GRAC_TABLE_NAMES: tuple[str, ...] = (
    "relationship_evidence",
    "relationship_assertions",
    "relationship_assertion_evidence",
    "relationship_assertion_events",
    "relationship_projection_revisions",
    "relationship_projection_edges",
    "relationship_projection_publications",
)
