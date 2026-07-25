"""Domain types for GRAC v1 append-only assertion lifecycle and authority.

Authority is a typed context only — no HTTP, JWT, or Request objects may appear here.
API authorization maps into ``AuthorityContext`` at the boundary (later PR).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

# Re-export contract lifecycle vocabulary for domain callers.
LifecycleState = Literal[
    "Proposed",
    "Accepted",
    "Rejected",
    "Withdrawn",
    "Disputed",
    "Retracted",
    "Superseded",
]

AuthorityRole = Literal["proposer", "acceptor", "disputer", "retractor"]

EvidencePolarity = Literal["supporting", "opposing", "contextual"]

ConfidenceStatus = Literal["assessed", "not_assessed"]

Visibility = Literal["public", "internal", "restricted", "confidential"]

# Bounds aligned with ORM column lengths / contract size caps.
MAX_ACTOR_ID_LEN = 128
MAX_RATIONALE_LEN = 4096
MAX_SOURCE_REF_LEN = 2048
MAX_POLICY_VERSION_LEN = 64
MAX_CORRELATION_ID_LEN = 128
MAX_MEDIA_TYPE_LEN = 128
MAX_LICENSING_LEN = 512
MAX_REUSE_POLICY_LEN = 512
MAX_CUSTODY_ID_LEN = 128
MAX_PROPOSITION_LEN = 8192
MAX_PREDICATE_ID_LEN = 256
MAX_SUBJECT_ID_LEN = 128
MAX_OBJECT_ID_LEN = 128
MAX_METHOD_ID_LEN = 256
MAX_CONFIDENCE_TYPE_LEN = 128
MAX_CONFIDENCE_METHOD_LEN = 256
SHA256_HEX_LEN = 64
ENTITY_ID_LEN = 36

EVIDENCE_LINK_STATES: frozenset[LifecycleState] = frozenset({"Proposed", "Accepted", "Disputed"})
EVIDENCE_LINK_ROLES: frozenset[AuthorityRole] = frozenset({"proposer", "acceptor"})


class RelationshipAssertionError(Exception):
    """Base error for governed assertion domain failures."""


class IllegalTransition(RelationshipAssertionError):
    """Raised when a requested lifecycle edge is outside the frozen matrix."""


class UnauthorizedTransition(RelationshipAssertionError):
    """Raised when ``AuthorityContext`` lacks the role required by the matrix."""


class ConcurrencyConflict(RelationshipAssertionError):
    """Raised when ``expected_sequence`` does not match the assertion's latest event."""


class SupersessionCycle(RelationshipAssertionError):
    """Raised when supersession would create a cycle or self-supersession."""


class ValidationError(RelationshipAssertionError):
    """Raised when bounded fields or digest/payload shape are invalid."""


@dataclass(frozen=True, slots=True)
class AuthorityContext:
    """Typed authority for lifecycle decisions (no HTTP / JWT types)."""

    actor_id: str
    roles: frozenset[AuthorityRole]
    policy_version: str
    correlation_id: str | None = None


@dataclass(frozen=True, slots=True)
class AssertionProposal:
    """Immutable proposition payload used to create an assertion."""

    assertion_id: str
    predicate_id: str
    subject_id: str
    object_id: str
    method_id: str
    proposition: str
    effective_from: datetime
    confidence_status: ConfidenceStatus = "not_assessed"
    confidence_bp: int | None = None
    confidence_type: str | None = None
    confidence_method: str | None = None
    effective_to: datetime | None = None


@dataclass(frozen=True, slots=True)
class Assertion:
    """Immutable assertion proposition row (lifecycle lives in events)."""

    assertion_id: str
    predicate_id: str
    subject_id: str
    object_id: str
    method_id: str
    proposition: str
    confidence_status: ConfidenceStatus
    confidence_bp: int | None
    confidence_type: str | None
    confidence_method: str | None
    effective_from: datetime
    effective_to: datetime | None
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class AssertionEvent:
    """Append-only lifecycle/authority event for one assertion."""

    event_id: str
    assertion_id: str
    sequence: int
    from_state: LifecycleState | None
    to_state: LifecycleState
    authority: AuthorityRole
    actor_id: str
    rationale: str
    policy_version: str
    recorded_at: datetime
    successor_assertion_id: str | None = None
    correlation_id: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """Immutable evidence reference (digest + metadata; no body bytes)."""

    evidence_id: str
    source_ref: str
    content_sha256: str
    media_type: str
    visibility: Visibility
    custody_id: str
    recorded_at: datetime
    observed_at: datetime | None = None
    issued_at: datetime | None = None
    licensing: str | None = None
    reuse_policy: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceLink:
    """Append-only polarity link between an assertion and evidence."""

    link_id: str
    assertion_id: str
    evidence_id: str
    polarity: EvidencePolarity
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class AssertionAsOf:
    """Bitemporal reconstruction of an assertion as of ``known_at``."""

    assertion: Assertion
    state: LifecycleState
    events: tuple[AssertionEvent, ...]
    evidence_links: tuple[EvidenceLink, ...] = field(default_factory=tuple)
    effective_at: datetime | None = None
    known_at: datetime | None = None
