"""Pure GRAC v1 lifecycle planners — no DB, HTTP, or wall-clock side effects.

Transition authority and edges come solely from ``load_contract_bundle`` /
``find_transition``. Callers supply ``recorded_at`` and identifiers.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
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
    TransitionSpec,
    find_transition,
    load_contract_bundle,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GROUPED_SHA256_RE = re.compile(r"^[0-9a-f]{4}(?:-[0-9a-f]{4}){15}$")
_UTC_OFFSET = timedelta(0)
_DETERMINATION_STATES: frozenset[LifecycleState] = frozenset({"Accepted", "Rejected", "Superseded"})


@dataclass(frozen=True)
class TransitionTiming:
    """Sequence, rationale, and timestamp inputs shared by transition planners."""

    expected_sequence: int
    rationale: str
    recorded_at: datetime
    event_id: str | None = None
    transitions: TransitionsDocument | None = None


@dataclass(frozen=True)
class TransitionPlan:
    """Fully specified lifecycle transition to plan as an append-only event."""

    assertion_id: str
    current: LifecycleState
    to_state: LifecycleState
    ctx: AuthorityContext
    timing: TransitionTiming
    successor_assertion_id: str | None = None
    proposer_actor_id: str | None = None


@dataclass(frozen=True)
class NamedTransitionPlan:
    """Named matrix edge inputs folded into a single transition plan."""

    to_state: LifecycleState
    assertion_id: str
    current: LifecycleState
    ctx: AuthorityContext
    timing: TransitionTiming
    proposer_actor_id: str | None = None


@dataclass(frozen=True)
class SupersedePlan:
    """Supersession transition with optional successor-chain cycle detection."""

    transition: TransitionPlan
    successor_chain_lookup: Callable[[str], Sequence[str]] | Mapping[str, Sequence[str]] | None = None


@dataclass(frozen=True)
class EvidenceRegistrationPlan:
    """Evidence link registration against a resolved lifecycle state."""

    assertion_id: str
    state: LifecycleState
    link: EvidenceLink
    ctx: AuthorityContext
    evidence: EvidenceRecord | None = None


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


def _require_utc_datetime(value: object, field_name: str) -> None:
    """Validate that a datetime is timezone-aware and has zero UTC offset."""
    message = f"{field_name} must be timezone-aware UTC"
    if not isinstance(value, datetime):
        raise ValidationError(message)
    if value.tzinfo is None:
        raise ValidationError(message)
    if value.utcoffset() != _UTC_OFFSET:
        raise ValidationError(message)


def _canonicalize_sha256_hex(value: str) -> str | None:
    """Return the canonical digest for supported plain/grouped forms."""
    normalized = value.lower()
    if _SHA256_RE.fullmatch(normalized):
        return normalized
    if _GROUPED_SHA256_RE.fullmatch(normalized):
        return normalized.replace("-", "")
    return None


def normalize_sha256_hex(value: str) -> str:
    """Normalize and validate a SHA-256 digest to lowercase hex (64 chars)."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("content_sha256 must be a non-empty string")
    canonical = _canonicalize_sha256_hex(value)
    if canonical is None:
        raise ValidationError(f"content_sha256 must be {SHA256_HEX_LEN} lowercase hex characters")
    return canonical


def _require_non_bool_int(value: int, field_name: str) -> int:
    """Reject bools/floats while preserving Python's integer contract."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"{field_name} must be an integer")
    return value


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


def _validate_proposal_identity(proposal: AssertionProposal) -> None:
    """Validate proposition identity and bounded string fields."""
    _require_non_empty(proposal.assertion_id, "assertion_id", ENTITY_ID_LEN)
    _require_non_empty(proposal.predicate_id, "predicate_id", MAX_PREDICATE_ID_LEN)
    _require_non_empty(proposal.subject_id, "subject_id", MAX_SUBJECT_ID_LEN)
    _require_non_empty(proposal.object_id, "object_id", MAX_OBJECT_ID_LEN)
    _require_non_empty(proposal.method_id, "method_id", MAX_METHOD_ID_LEN)
    _require_non_empty(proposal.proposition, "proposition", MAX_PROPOSITION_LEN)


def _validate_proposal_effective_window(proposal: AssertionProposal) -> None:
    """Validate effective_from/to ordering and UTC constraints."""
    _require_utc_datetime(proposal.effective_from, "effective_from")
    if proposal.effective_to is not None:
        _require_utc_datetime(proposal.effective_to, "effective_to")
    if proposal.effective_to is not None and proposal.effective_to < proposal.effective_from:
        raise ValidationError("effective_to must be >= effective_from")


def _has_assessed_confidence_fields(proposal: AssertionProposal) -> bool:
    """Return True when any assessed-only confidence field is populated."""
    fields = (proposal.confidence_bp, proposal.confidence_type, proposal.confidence_method)
    return any(value is not None for value in fields)


def _validate_not_assessed_confidence(proposal: AssertionProposal) -> None:
    """Validate confidence fields when status is not_assessed."""
    if _has_assessed_confidence_fields(proposal):
        raise ValidationError("not_assessed confidence forbids confidence_bp/type/method")


def _validate_assessed_confidence(proposal: AssertionProposal) -> None:
    """Validate confidence fields when status is assessed."""
    if proposal.confidence_bp is None:
        raise ValidationError("assessed confidence_bp must be an integer in [0, 10000]")
    confidence_bp = _require_non_bool_int(proposal.confidence_bp, "confidence_bp")
    if not (0 <= confidence_bp <= 10000):
        raise ValidationError("assessed confidence_bp must be an integer in [0, 10000]")
    _require_non_empty(proposal.confidence_type or "", "confidence_type", MAX_CONFIDENCE_TYPE_LEN)
    _require_non_empty(proposal.confidence_method or "", "confidence_method", MAX_CONFIDENCE_METHOD_LEN)


def validate_proposal(proposal: AssertionProposal) -> None:
    """Validate proposition shape, confidence pairing, and field bounds."""
    _validate_proposal_identity(proposal)
    _validate_proposal_effective_window(proposal)
    if proposal.confidence_status == "not_assessed":
        _validate_not_assessed_confidence(proposal)
        return
    if proposal.confidence_status != "assessed":
        raise ValidationError("confidence_status must be assessed or not_assessed")
    _validate_assessed_confidence(proposal)


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
    _require_utc_datetime(evidence.recorded_at, "recorded_at")
    if evidence.observed_at is not None:
        _require_utc_datetime(evidence.observed_at, "observed_at")
    if evidence.issued_at is not None:
        _require_utc_datetime(evidence.issued_at, "issued_at")
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


def _validate_initial_event(event: AssertionEvent) -> None:
    """Ensure the first event in a stream is a proper propose transition."""
    if event.from_state is not None or event.to_state != "Proposed":
        raise ValidationError("initial event must transition from None to Proposed")
    if event.authority != "proposer":
        raise ValidationError("initial event must use proposer authority")
    _require_non_empty(event.actor_id, "actor_id", MAX_ACTOR_ID_LEN)


def _validate_event_continuity(event: AssertionEvent, previous_state: LifecycleState) -> None:
    """Ensure a follow-on event continues from the prior lifecycle state."""
    if event.from_state != previous_state:
        raise ValidationError(
            f"event state continuity gap: expected from_state {previous_state}, got {event.from_state}"
        )


def _validate_successor_pointer(allowed: TransitionSpec, event: AssertionEvent) -> None:
    """Ensure successor_assertion_id presence matches the matrix edge."""
    if allowed.requires_successor and event.successor_assertion_id is None:
        raise ValidationError("supersession event requires successor_assertion_id")
    if not allowed.requires_successor and event.successor_assertion_id is not None:
        raise ValidationError("non-supersession event must not set successor_assertion_id")


def _validate_follow_on_event(
    event: AssertionEvent,
    previous_state: LifecycleState,
    transitions: TransitionsDocument,
    proposer_actor_id: str,
) -> None:
    """Ensure a follow-on event aligns with matrix rules and continuity."""
    _validate_event_continuity(event, previous_state)
    from_state_value = cast(LifecycleState, event.from_state)
    allowed = find_transition(transitions, from_state_value, event.to_state)
    if allowed is None:
        raise ValidationError(f"event transition outside matrix: {from_state_value}->{event.to_state}")
    if event.authority != allowed.authority:
        raise ValidationError(
            f"event authority {event.authority!r} does not match required authority {allowed.authority!r}"
        )
    _validate_successor_pointer(allowed, event)
    _validate_actor_relationship(event.to_state, event.actor_id, proposer_actor_id)


def _validate_actor_relationship(
    to_state: LifecycleState,
    actor_id: str,
    proposer_actor_id: str | None,
) -> None:
    """Enforce proposer ownership and reviewer separation for sensitive transitions."""
    actor = _require_non_empty(actor_id, "actor_id", MAX_ACTOR_ID_LEN)
    if to_state not in _DETERMINATION_STATES and to_state != "Withdrawn":
        return
    proposer = _require_non_empty(proposer_actor_id or "", "proposer_actor_id", MAX_ACTOR_ID_LEN)
    if to_state == "Withdrawn" and actor != proposer:
        raise UnauthorizedTransition("withdrawal actor must match the assertion proposer of record")
    if to_state in _DETERMINATION_STATES and actor == proposer:
        raise UnauthorizedTransition("determining actor must differ from the assertion proposer of record")


def resolve_state(events: Sequence[AssertionEvent]) -> LifecycleState:
    """Fold ordered events into the current lifecycle state."""
    if not events:
        raise ValidationError("cannot resolve state from empty event stream")
    ordered = sorted(events, key=lambda event: event.sequence)
    expected = 1
    previous_state: LifecycleState | None = None
    previous_recorded_at: datetime | None = None
    proposer_actor_id: str | None = None
    transitions = load_transitions()
    for event in ordered:
        sequence = _require_non_bool_int(event.sequence, "event sequence")
        if sequence != expected:
            raise ValidationError(f"event sequence gap: expected {expected}, got {event.sequence}")
        _require_utc_datetime(event.recorded_at, "recorded_at")
        if previous_recorded_at is not None and event.recorded_at <= previous_recorded_at:
            raise ValidationError("event recorded_at must be strictly increasing within an assertion stream")
        if expected == 1:
            _validate_initial_event(event)
            proposer_actor_id = event.actor_id
        else:
            _validate_follow_on_event(
                event,
                cast(LifecycleState, previous_state),
                transitions,
                cast(str, proposer_actor_id),
            )
        previous_state = event.to_state
        previous_recorded_at = event.recorded_at
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
    _require_utc_datetime(recorded_at, "recorded_at")
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


def _validate_transition_plan(plan: TransitionPlan) -> tuple[TransitionsDocument, TransitionSpec]:
    """Validate transition inputs and resolve the allowed matrix edge."""
    _require_non_empty(plan.assertion_id, "assertion_id", ENTITY_ID_LEN)
    _require_non_empty(plan.timing.rationale, "rationale", MAX_RATIONALE_LEN)
    expected_sequence_value = _require_non_bool_int(plan.timing.expected_sequence, "expected_sequence")
    if expected_sequence_value < 1:
        raise ConcurrencyConflict("expected_sequence must be >= 1 (last applied sequence)")
    _require_utc_datetime(plan.timing.recorded_at, "recorded_at")

    matrix = plan.timing.transitions if plan.timing.transitions is not None else load_transitions()
    allowed = find_transition(matrix, plan.current, plan.to_state)
    if allowed is None:
        raise IllegalTransition(f"illegal transition: {plan.current}->{plan.to_state}")
    return matrix, allowed


def _resolve_successor(plan: TransitionPlan, allowed: TransitionSpec) -> str | None:
    """Resolve and validate successor_assertion_id for supersession edges."""
    if allowed.requires_successor:
        successor = _require_non_empty(
            plan.successor_assertion_id or "",
            "successor_assertion_id",
            ENTITY_ID_LEN,
        )
        if successor == plan.assertion_id:
            raise SupersessionCycle("self-supersession is forbidden")
        return successor
    if plan.successor_assertion_id is not None:
        raise IllegalTransition(
            f"non-supersession transition {plan.current}->{plan.to_state} " "must not set successor_assertion_id"
        )
    return None


def _build_transition_event(
    plan: TransitionPlan,
    allowed: TransitionSpec,
    successor: str | None,
) -> AssertionEvent:
    """Materialize a planned transition as an append-only event DTO."""
    required_role = cast(AuthorityRole, allowed.authority)
    validate_authority(plan.ctx, required_role)
    _validate_actor_relationship(plan.to_state, plan.ctx.actor_id, plan.proposer_actor_id)
    expected_sequence_value = _require_non_bool_int(plan.timing.expected_sequence, "expected_sequence")
    rationale_value = _require_non_empty(plan.timing.rationale, "rationale", MAX_RATIONALE_LEN)
    return AssertionEvent(
        event_id=plan.timing.event_id or _new_id(),
        assertion_id=plan.assertion_id,
        sequence=expected_sequence_value + 1,
        from_state=plan.current,
        to_state=plan.to_state,
        authority=required_role,
        actor_id=plan.ctx.actor_id,
        rationale=rationale_value,
        policy_version=plan.ctx.policy_version,
        recorded_at=plan.timing.recorded_at,
        successor_assertion_id=successor,
        correlation_id=plan.ctx.correlation_id,
    )


def _plan_transition(plan: TransitionPlan) -> AssertionEvent:
    """Plan a matrix transition after its public entry point has been selected."""
    _matrix, allowed = _validate_transition_plan(plan)
    successor = _resolve_successor(plan, allowed)
    return _build_transition_event(plan, allowed, successor)


def plan_transition(plan: TransitionPlan) -> AssertionEvent:
    """Plan a non-supersession matrix transition with authority guards."""
    if plan.to_state == "Superseded":
        raise IllegalTransition("Superseded is available only through plan_supersede")
    return _plan_transition(plan)


def _plan_named_transition(plan: NamedTransitionPlan) -> AssertionEvent:
    """Plan a named matrix edge via ``TransitionPlan``."""
    return plan_transition(
        TransitionPlan(
            assertion_id=plan.assertion_id,
            current=plan.current,
            to_state=plan.to_state,
            ctx=plan.ctx,
            timing=plan.timing,
            proposer_actor_id=plan.proposer_actor_id,
        )
    )


def plan_accept(
    assertion_id: str,
    current: LifecycleState,
    ctx: AuthorityContext,
    *,
    timing: TransitionTiming,
    proposer_actor_id: str,
) -> AssertionEvent:
    """Plan Proposed|Disputed → Accepted."""
    return _plan_named_transition(
        NamedTransitionPlan("Accepted", assertion_id, current, ctx, timing, proposer_actor_id)
    )


def plan_reject(
    assertion_id: str,
    current: LifecycleState,
    ctx: AuthorityContext,
    *,
    timing: TransitionTiming,
    proposer_actor_id: str,
) -> AssertionEvent:
    """Plan Proposed → Rejected."""
    return _plan_named_transition(
        NamedTransitionPlan("Rejected", assertion_id, current, ctx, timing, proposer_actor_id)
    )


def plan_withdraw(
    assertion_id: str,
    current: LifecycleState,
    ctx: AuthorityContext,
    *,
    timing: TransitionTiming,
    proposer_actor_id: str,
) -> AssertionEvent:
    """Plan Proposed → Withdrawn."""
    return _plan_named_transition(
        NamedTransitionPlan("Withdrawn", assertion_id, current, ctx, timing, proposer_actor_id)
    )


def plan_dispute(
    assertion_id: str,
    current: LifecycleState,
    ctx: AuthorityContext,
    *,
    timing: TransitionTiming,
) -> AssertionEvent:
    """Plan Accepted → Disputed."""
    return _plan_named_transition(NamedTransitionPlan("Disputed", assertion_id, current, ctx, timing))


def plan_reaffirm(
    assertion_id: str,
    current: LifecycleState,
    ctx: AuthorityContext,
    *,
    timing: TransitionTiming,
    proposer_actor_id: str,
) -> AssertionEvent:
    """Plan Disputed → Accepted (reaffirm)."""
    return _plan_named_transition(
        NamedTransitionPlan("Accepted", assertion_id, current, ctx, timing, proposer_actor_id)
    )


def plan_retract(
    assertion_id: str,
    current: LifecycleState,
    ctx: AuthorityContext,
    *,
    timing: TransitionTiming,
) -> AssertionEvent:
    """Plan Accepted|Disputed → Retracted."""
    return _plan_named_transition(NamedTransitionPlan("Retracted", assertion_id, current, ctx, timing))


def plan_supersede(plan: SupersedePlan) -> AssertionEvent:
    """Plan Accepted|Disputed → Superseded with cycle prevention."""
    assert_no_cycle(
        plan.transition.assertion_id,
        plan.transition.successor_assertion_id or "",
        plan.successor_chain_lookup,
    )
    return _plan_transition(plan.transition)


def _validate_evidence_link_scope(plan: EvidenceRegistrationPlan) -> None:
    """Validate assertion/state gates for evidence link registration."""
    _require_non_empty(plan.assertion_id, "assertion_id", ENTITY_ID_LEN)
    if plan.assertion_id != plan.link.assertion_id:
        raise ValidationError("evidence link assertion_id mismatch")
    if plan.state not in EVIDENCE_LINK_STATES:
        raise IllegalTransition(f"evidence links forbidden in state {plan.state}")
    validate_authority(plan.ctx, set(EVIDENCE_LINK_ROLES))


def _validate_evidence_link_fields(link: EvidenceLink) -> None:
    """Validate polarity and link identity fields."""
    if link.polarity not in ("supporting", "opposing", "contextual"):
        raise ValidationError(f"invalid evidence polarity: {link.polarity!r}")
    _require_non_empty(link.link_id, "link_id", ENTITY_ID_LEN)
    _require_non_empty(link.evidence_id, "evidence_id", ENTITY_ID_LEN)
    _require_utc_datetime(link.recorded_at, "recorded_at")


def _validate_linked_evidence_record(link: EvidenceLink, evidence: EvidenceRecord | None) -> None:
    """Validate optional evidence record consistency with the link."""
    if evidence is None:
        return
    validated = validate_evidence_record(evidence)
    if validated.evidence_id != link.evidence_id:
        raise ValidationError("evidence record id mismatch with link")


def plan_register_evidence(plan: EvidenceRegistrationPlan) -> EvidenceLink:
    """Validate authority/state gates for an append-only evidence link."""
    _validate_evidence_link_scope(plan)
    _validate_evidence_link_fields(plan.link)
    _validate_linked_evidence_record(plan.link, plan.evidence)
    return plan.link


def _lookup_successors(
    node: str,
    successor_chain_lookup: Callable[[str], Sequence[str]] | Mapping[str, Sequence[str]],
) -> Sequence[str]:
    """Resolve successor IDs for ``node`` from a callable or mapping lookup."""
    if callable(successor_chain_lookup):
        return successor_chain_lookup(node)
    return successor_chain_lookup.get(node, ())


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

    seen: set[str] = set()
    stack = [successor_id]
    while stack:
        current = stack.pop()
        if current == predecessor_id:
            raise SupersessionCycle(f"supersession cycle: {predecessor_id} already reachable from {successor_id}")
        if current in seen:
            continue
        seen.add(current)
        stack.extend(_lookup_successors(current, successor_chain_lookup))


def _assertion_fields(assertion: Assertion) -> tuple[object, ...]:
    """Return comparable assertion payload fields."""
    return (
        assertion.assertion_id,
        assertion.predicate_id,
        assertion.subject_id,
        assertion.object_id,
        assertion.method_id,
        assertion.proposition,
        assertion.confidence_status,
        assertion.confidence_bp,
        assertion.confidence_type,
        assertion.confidence_method,
        assertion.effective_from,
        assertion.effective_to,
    )


def _proposal_fields(proposal: AssertionProposal) -> tuple[object, ...]:
    """Return comparable proposal payload fields."""
    return (
        proposal.assertion_id,
        proposal.predicate_id,
        proposal.subject_id,
        proposal.object_id,
        proposal.method_id,
        proposal.proposition,
        proposal.confidence_status,
        proposal.confidence_bp,
        proposal.confidence_type,
        proposal.confidence_method,
        proposal.effective_from,
        proposal.effective_to,
    )


def proposals_equivalent(existing: Assertion, proposal: AssertionProposal) -> bool:
    """Return True when an existing assertion matches a proposal for idempotent create."""
    return _assertion_fields(existing) == _proposal_fields(proposal)


def cast_polarity(value: str) -> EvidencePolarity:
    """Cast a stored polarity string to the domain literal."""
    if value not in ("supporting", "opposing", "contextual"):
        raise ValidationError(f"invalid evidence polarity: {value!r}")
    return cast(EvidencePolarity, value)
