"""Pure GRAC v1 lifecycle planners — no DB, HTTP, or wall-clock side effects.

Transition authority and edges come solely from ``load_contract_bundle`` /
``find_transition``. Callers supply ``recorded_at`` and identifiers.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import cast
from uuid import uuid4

from src.governance.relationship_assertion import (
    ENTITY_ID_LEN,
    EVIDENCE_LINK_ROLES,
    EVIDENCE_LINK_STATES,
    MAX_ACTOR_ID_LEN,
    MAX_CONFIDENCE_METHOD_LEN,
    MAX_CONFIDENCE_TYPE_LEN,
    MAX_CORRELATION_ID_LEN,
    MAX_CUSTODY_ID_LEN,
    MAX_LICENSING_LEN,
    MAX_MEDIA_TYPE_LEN,
    MAX_METHOD_ID_LEN,
    MAX_OBJECT_ID_LEN,
    MAX_POLICY_VERSION_LEN,
    MAX_PREDICATE_ID_LEN,
    MAX_PROPOSITION_LEN,
    MAX_RATIONALE_LEN,
    MAX_REUSE_POLICY_LEN,
    MAX_SOURCE_REF_LEN,
    MAX_SUBJECT_ID_LEN,
    SHA256_HEX_LEN,
    Assertion,
    AssertionEvent,
    AssertionProposal,
    AuthorityContext,
    AuthorityRole,
    ConcurrencyConflict,
    EvidenceLink,
    EvidencePolarity,
    EvidenceRecord,
    IllegalTransition,
    LifecycleState,
    SupersessionCycle,
    UnauthorizedTransition,
    ValidationError,
    Visibility,
)
from src.governance.relationship_assertion_contract import (
    TransitionsDocument,
    find_transition,
    load_contract_bundle,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_HEX_DIGEST_CHARS = frozenset("0123456789abcdef")


def _new_id() -> str:
    """Return a UUID4 string (36 chars) for event/link identifiers."""
    return str(uuid4())


def _require_non_empty(value: str, field_name: str, max_len: int) -> str:
    """Validate a required bounded string field."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field_name} must be a non-empty string")
    if len(value) > max_len:
        raise ValidationError(f"{field_name} exceeds maximum length of {max_len}")
    return value


def _require_optional(value: str | None, field_name: str, max_len: int) -> str | None:
    """Validate an optional bounded string field."""
    if value is None:
        return None
    return _require_non_empty(value, field_name, max_len)


def normalize_sha256_hex(value: str) -> str:
    """Normalize and validate a SHA-256 digest to lowercase hex (64 chars)."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("content_sha256 must be a non-empty string")
    normalized = "".join(ch for ch in value.lower() if ch in _HEX_DIGEST_CHARS)
    if len(normalized) != SHA256_HEX_LEN or not _SHA256_RE.fullmatch(normalized):
        raise ValidationError(f"content_sha256 must be {SHA256_HEX_LEN} lowercase hex characters")
    return normalized


def validate_authority(ctx: AuthorityContext, required: AuthorityRole | set[AuthorityRole]) -> None:
    """Fail closed when ``ctx`` lacks every required role (any-of for a set)."""
    _require_non_empty(ctx.actor_id, "actor_id", MAX_ACTOR_ID_LEN)
    _require_non_empty(ctx.policy_version, "policy_version", MAX_POLICY_VERSION_LEN)
    _require_optional(ctx.correlation_id, "correlation_id", MAX_CORRELATION_ID_LEN)
    if not ctx.roles:
        raise UnauthorizedTransition("AuthorityContext.roles must not be empty")
    needed = {required} if isinstance(required, str) else set(required)
    if ctx.roles.isdisjoint(needed):
        raise UnauthorizedTransition(f"missing required authority role(s) {sorted(needed)}; have {sorted(ctx.roles)}")


def validate_proposal(proposal: AssertionProposal) -> None:
    """Validate proposition shape, confidence pairing, and field bounds."""
    _require_non_empty(proposal.assertion_id, "assertion_id", ENTITY_ID_LEN)
    _require_non_empty(proposal.predicate_id, "predicate_id", MAX_PREDICATE_ID_LEN)
    _require_non_empty(proposal.subject_id, "subject_id", MAX_SUBJECT_ID_LEN)
    _require_non_empty(proposal.object_id, "object_id", MAX_OBJECT_ID_LEN)
    _require_non_empty(proposal.method_id, "method_id", MAX_METHOD_ID_LEN)
    _require_non_empty(proposal.proposition, "proposition", MAX_PROPOSITION_LEN)
    if proposal.effective_from.tzinfo is None:
        raise ValidationError("effective_from must be timezone-aware UTC")
    if proposal.effective_to is not None and proposal.effective_to.tzinfo is None:
        raise ValidationError("effective_to must be timezone-aware UTC")
    if proposal.effective_to is not None and proposal.effective_to < proposal.effective_from:
        raise ValidationError("effective_to must be >= effective_from")

    if proposal.confidence_status == "not_assessed":
        if (
            proposal.confidence_bp is not None
            or proposal.confidence_type is not None
            or proposal.confidence_method is not None
        ):
            raise ValidationError("not_assessed confidence forbids confidence_bp/type/method")
        return

    if proposal.confidence_status != "assessed":
        raise ValidationError("confidence_status must be assessed or not_assessed")
    if proposal.confidence_bp is None or not (0 <= proposal.confidence_bp <= 10000):
        raise ValidationError("assessed confidence_bp must be an integer in [0, 10000]")
    _require_non_empty(proposal.confidence_type or "", "confidence_type", MAX_CONFIDENCE_TYPE_LEN)
    _require_non_empty(proposal.confidence_method or "", "confidence_method", MAX_CONFIDENCE_METHOD_LEN)


def validate_evidence_record(evidence: EvidenceRecord) -> EvidenceRecord:
    """Validate evidence reference bounds and digest; return normalized copy if needed."""
    _require_non_empty(evidence.evidence_id, "evidence_id", ENTITY_ID_LEN)
    _require_non_empty(evidence.source_ref, "source_ref", MAX_SOURCE_REF_LEN)
    digest = normalize_sha256_hex(evidence.content_sha256)
    _require_non_empty(evidence.media_type, "media_type", MAX_MEDIA_TYPE_LEN)
    _require_non_empty(evidence.custody_id, "custody_id", MAX_CUSTODY_ID_LEN)
    if evidence.visibility not in ("public", "internal", "restricted", "confidential"):
        raise ValidationError(f"invalid visibility: {evidence.visibility!r}")
    _require_optional(evidence.licensing, "licensing", MAX_LICENSING_LEN)
    _require_optional(evidence.reuse_policy, "reuse_policy", MAX_REUSE_POLICY_LEN)
    if evidence.recorded_at.tzinfo is None:
        raise ValidationError("recorded_at must be timezone-aware UTC")
    if digest == evidence.content_sha256:
        return evidence
    return EvidenceRecord(
        evidence_id=evidence.evidence_id,
        source_ref=evidence.source_ref,
        content_sha256=digest,
        media_type=evidence.media_type,
        visibility=cast(Visibility, evidence.visibility),
        custody_id=evidence.custody_id,
        recorded_at=evidence.recorded_at,
        observed_at=evidence.observed_at,
        issued_at=evidence.issued_at,
        licensing=evidence.licensing,
        reuse_policy=evidence.reuse_policy,
    )


def load_transitions() -> TransitionsDocument:
    """Load the pinned frozen transition matrix from the contract bundle."""
    _contract, _predicates, transitions = load_contract_bundle()
    return transitions


def resolve_state(events: Sequence[AssertionEvent]) -> LifecycleState:
    """Fold ordered events into the current lifecycle state."""
    if not events:
        raise ValidationError("cannot resolve state from empty event stream")
    ordered = sorted(events, key=lambda event: event.sequence)
    expected = 1
    for event in ordered:
        if event.sequence != expected:
            raise ValidationError(f"event sequence gap: expected {expected}, got {event.sequence}")
        expected += 1
    return ordered[-1].to_state


def plan_propose(
    proposal: AssertionProposal,
    ctx: AuthorityContext,
    *,
    recorded_at: datetime,
    event_id: str | None = None,
) -> tuple[Assertion, AssertionEvent]:
    """Plan creation of an assertion in ``Proposed`` with sequence 1."""
    validate_proposal(proposal)
    validate_authority(ctx, "proposer")
    if recorded_at.tzinfo is None:
        raise ValidationError("recorded_at must be timezone-aware UTC")
    assertion = Assertion(
        assertion_id=proposal.assertion_id,
        predicate_id=proposal.predicate_id,
        subject_id=proposal.subject_id,
        object_id=proposal.object_id,
        method_id=proposal.method_id,
        proposition=proposal.proposition,
        confidence_status=proposal.confidence_status,
        confidence_bp=proposal.confidence_bp,
        confidence_type=proposal.confidence_type,
        confidence_method=proposal.confidence_method,
        effective_from=proposal.effective_from,
        effective_to=proposal.effective_to,
        recorded_at=recorded_at,
    )
    event = AssertionEvent(
        event_id=event_id or _new_id(),
        assertion_id=proposal.assertion_id,
        sequence=1,
        from_state=None,
        to_state="Proposed",
        authority="proposer",
        actor_id=ctx.actor_id,
        rationale="propose",
        policy_version=ctx.policy_version,
        recorded_at=recorded_at,
        correlation_id=ctx.correlation_id,
    )
    return assertion, event


def plan_transition(
    assertion_id: str,
    current: LifecycleState,
    to_state: LifecycleState,
    ctx: AuthorityContext,
    *,
    expected_sequence: int,
    rationale: str,
    recorded_at: datetime,
    successor_assertion_id: str | None = None,
    event_id: str | None = None,
    transitions: TransitionsDocument | None = None,
) -> AssertionEvent:
    """Plan a single matrix transition with authority and concurrency guards."""
    _require_non_empty(assertion_id, "assertion_id", ENTITY_ID_LEN)
    rationale_value = _require_non_empty(rationale, "rationale", MAX_RATIONALE_LEN)
    if expected_sequence < 1:
        raise ConcurrencyConflict("expected_sequence must be >= 1 (last applied sequence)")
    if recorded_at.tzinfo is None:
        raise ValidationError("recorded_at must be timezone-aware UTC")

    matrix = transitions if transitions is not None else load_transitions()
    allowed = find_transition(matrix, current, to_state)
    if allowed is None:
        raise IllegalTransition(f"illegal transition: {current}->{to_state}")

    required_role = cast(AuthorityRole, allowed.authority)
    validate_authority(ctx, required_role)

    if allowed.requires_successor:
        successor = _require_non_empty(
            successor_assertion_id or "",
            "successor_assertion_id",
            ENTITY_ID_LEN,
        )
        if successor == assertion_id:
            raise SupersessionCycle("self-supersession is forbidden")
    else:
        if successor_assertion_id is not None:
            raise IllegalTransition(
                f"non-supersession transition {current}->{to_state} must not set successor_assertion_id"
            )
        successor = None

    return AssertionEvent(
        event_id=event_id or _new_id(),
        assertion_id=assertion_id,
        sequence=expected_sequence + 1,
        from_state=current,
        to_state=to_state,
        authority=required_role,
        actor_id=ctx.actor_id,
        rationale=rationale_value,
        policy_version=ctx.policy_version,
        recorded_at=recorded_at,
        successor_assertion_id=successor,
        correlation_id=ctx.correlation_id,
    )


def plan_accept(
    assertion_id: str,
    current: LifecycleState,
    ctx: AuthorityContext,
    *,
    expected_sequence: int,
    rationale: str,
    recorded_at: datetime,
    event_id: str | None = None,
    transitions: TransitionsDocument | None = None,
) -> AssertionEvent:
    """Plan Proposed|Disputed → Accepted."""
    return plan_transition(
        assertion_id,
        current,
        "Accepted",
        ctx,
        expected_sequence=expected_sequence,
        rationale=rationale,
        recorded_at=recorded_at,
        event_id=event_id,
        transitions=transitions,
    )


def plan_reject(
    assertion_id: str,
    current: LifecycleState,
    ctx: AuthorityContext,
    *,
    expected_sequence: int,
    rationale: str,
    recorded_at: datetime,
    event_id: str | None = None,
    transitions: TransitionsDocument | None = None,
) -> AssertionEvent:
    """Plan Proposed → Rejected."""
    return plan_transition(
        assertion_id,
        current,
        "Rejected",
        ctx,
        expected_sequence=expected_sequence,
        rationale=rationale,
        recorded_at=recorded_at,
        event_id=event_id,
        transitions=transitions,
    )


def plan_withdraw(
    assertion_id: str,
    current: LifecycleState,
    ctx: AuthorityContext,
    *,
    expected_sequence: int,
    rationale: str,
    recorded_at: datetime,
    event_id: str | None = None,
    transitions: TransitionsDocument | None = None,
) -> AssertionEvent:
    """Plan Proposed → Withdrawn."""
    return plan_transition(
        assertion_id,
        current,
        "Withdrawn",
        ctx,
        expected_sequence=expected_sequence,
        rationale=rationale,
        recorded_at=recorded_at,
        event_id=event_id,
        transitions=transitions,
    )


def plan_dispute(
    assertion_id: str,
    current: LifecycleState,
    ctx: AuthorityContext,
    *,
    expected_sequence: int,
    rationale: str,
    recorded_at: datetime,
    event_id: str | None = None,
    transitions: TransitionsDocument | None = None,
) -> AssertionEvent:
    """Plan Accepted → Disputed."""
    return plan_transition(
        assertion_id,
        current,
        "Disputed",
        ctx,
        expected_sequence=expected_sequence,
        rationale=rationale,
        recorded_at=recorded_at,
        event_id=event_id,
        transitions=transitions,
    )


def plan_reaffirm(
    assertion_id: str,
    current: LifecycleState,
    ctx: AuthorityContext,
    *,
    expected_sequence: int,
    rationale: str,
    recorded_at: datetime,
    event_id: str | None = None,
    transitions: TransitionsDocument | None = None,
) -> AssertionEvent:
    """Plan Disputed → Accepted (reaffirm)."""
    return plan_transition(
        assertion_id,
        current,
        "Accepted",
        ctx,
        expected_sequence=expected_sequence,
        rationale=rationale,
        recorded_at=recorded_at,
        event_id=event_id,
        transitions=transitions,
    )


def plan_retract(
    assertion_id: str,
    current: LifecycleState,
    ctx: AuthorityContext,
    *,
    expected_sequence: int,
    rationale: str,
    recorded_at: datetime,
    event_id: str | None = None,
    transitions: TransitionsDocument | None = None,
) -> AssertionEvent:
    """Plan Accepted|Disputed → Retracted."""
    return plan_transition(
        assertion_id,
        current,
        "Retracted",
        ctx,
        expected_sequence=expected_sequence,
        rationale=rationale,
        recorded_at=recorded_at,
        event_id=event_id,
        transitions=transitions,
    )


def plan_supersede(
    assertion_id: str,
    current: LifecycleState,
    ctx: AuthorityContext,
    *,
    expected_sequence: int,
    rationale: str,
    recorded_at: datetime,
    successor_assertion_id: str,
    successor_chain_lookup: Callable[[str], Sequence[str]] | Mapping[str, Sequence[str]] | None = None,
    event_id: str | None = None,
    transitions: TransitionsDocument | None = None,
) -> AssertionEvent:
    """Plan Accepted|Disputed → Superseded with cycle prevention."""
    assert_no_cycle(assertion_id, successor_assertion_id, successor_chain_lookup)
    return plan_transition(
        assertion_id,
        current,
        "Superseded",
        ctx,
        expected_sequence=expected_sequence,
        rationale=rationale,
        recorded_at=recorded_at,
        successor_assertion_id=successor_assertion_id,
        event_id=event_id,
        transitions=transitions,
    )


def plan_register_evidence(
    assertion_id: str,
    state: LifecycleState,
    link: EvidenceLink,
    ctx: AuthorityContext,
    *,
    evidence: EvidenceRecord | None = None,
) -> EvidenceLink:
    """Validate authority/state gates for an append-only evidence link."""
    _require_non_empty(assertion_id, "assertion_id", ENTITY_ID_LEN)
    if assertion_id != link.assertion_id:
        raise ValidationError("evidence link assertion_id mismatch")
    if state not in EVIDENCE_LINK_STATES:
        raise IllegalTransition(f"evidence links forbidden in state {state}")
    validate_authority(ctx, set(EVIDENCE_LINK_ROLES))
    if link.polarity not in ("supporting", "opposing", "contextual"):
        raise ValidationError(f"invalid evidence polarity: {link.polarity!r}")
    _require_non_empty(link.link_id, "link_id", ENTITY_ID_LEN)
    _require_non_empty(link.evidence_id, "evidence_id", ENTITY_ID_LEN)
    if link.recorded_at.tzinfo is None:
        raise ValidationError("recorded_at must be timezone-aware UTC")
    if evidence is not None:
        validate_evidence_record(evidence)
        if evidence.evidence_id != link.evidence_id:
            raise ValidationError("evidence record id mismatch with link")
    return link


def assert_no_cycle(
    predecessor_id: str,
    successor_id: str,
    successor_chain_lookup: Callable[[str], Sequence[str]] | Mapping[str, Sequence[str]] | None = None,
) -> None:
    """Reject self-supersession and cycles in the successor chain."""
    _require_non_empty(predecessor_id, "predecessor_id", ENTITY_ID_LEN)
    _require_non_empty(successor_id, "successor_id", ENTITY_ID_LEN)
    if predecessor_id == successor_id:
        raise SupersessionCycle("self-supersession is forbidden")
    if successor_chain_lookup is None:
        return

    def _next(node: str) -> Sequence[str]:
        if callable(successor_chain_lookup):
            return successor_chain_lookup(node)
        return successor_chain_lookup.get(node, ())

    seen: set[str] = set()
    stack = [successor_id]
    while stack:
        current = stack.pop()
        if current == predecessor_id:
            raise SupersessionCycle(f"supersession cycle: {predecessor_id} already reachable from {successor_id}")
        if current in seen:
            continue
        seen.add(current)
        stack.extend(_next(current))


def proposals_equivalent(existing: Assertion, proposal: AssertionProposal) -> bool:
    """Return True when an existing assertion matches a proposal for idempotent create."""
    return (
        existing.assertion_id == proposal.assertion_id
        and existing.predicate_id == proposal.predicate_id
        and existing.subject_id == proposal.subject_id
        and existing.object_id == proposal.object_id
        and existing.method_id == proposal.method_id
        and existing.proposition == proposal.proposition
        and existing.confidence_status == proposal.confidence_status
        and existing.confidence_bp == proposal.confidence_bp
        and existing.confidence_type == proposal.confidence_type
        and existing.confidence_method == proposal.confidence_method
        and existing.effective_from == proposal.effective_from
        and existing.effective_to == proposal.effective_to
    )


def cast_polarity(value: str) -> EvidencePolarity:
    """Cast a stored polarity string to the domain literal."""
    if value not in ("supporting", "opposing", "contextual"):
        raise ValidationError(f"invalid evidence polarity: {value!r}")
    return cast(EvidencePolarity, value)
