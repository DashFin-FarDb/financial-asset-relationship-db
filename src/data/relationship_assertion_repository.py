"""Append-only GRAC v1 assertion lifecycle repository (INSERT-only ORM persistence)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import NoReturn, cast
from uuid import uuid4

from sqlalchemy import func, select, union_all
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.data.db_models import RebuildJobORM
from src.data.relationship_assertion_db_models import (
    RelationshipAssertionEventORM,
    RelationshipAssertionEvidenceORM,
    RelationshipAssertionORM,
    RelationshipEvidenceORM,
    RelationshipProjectionPublicationORM,
    RelationshipProjectionRevisionORM,
)
from src.data.relationship_projection_persistence import (
    PersistedProjectionRevision,
    PersistProjectionRequest,
    ProjectionRevisionStore,
)
from src.governance.relationship_assertion import (
    Assertion,
    AssertionAsOf,
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
from src.governance.relationship_assertion_lifecycle import (
    EvidenceRegistrationPlan,
    SupersedePlan,
    TransitionPlan,
    TransitionTiming,
    assert_no_cycle,
    cast_polarity,
    plan_accept,
    plan_propose,
    plan_register_evidence,
    plan_supersede,
    plan_transition,
    proposals_equivalent,
    resolve_state,
    validate_authority,
    validate_evidence_record,
)
from src.logic.reconciliation_engine import RebuildCancelledError
from src.logic.relationship_projection import GovernedScope

UTC = timezone.utc
_SUPERSESSION_LOCK_NAMESPACE = 0x46415244
_SUPERSESSION_LOCK_RESOURCE = 0x47524143

__all__ = [
    "FinalizeProjectionPublicationRequest",
    "PersistProjectionRequest",
    "PersistedProjectionRevision",
    "ProjectionSourceSnapshot",
    "PublishedProjectionRevision",
    "RegisterEvidenceRequest",
    "RelationshipAssertionRepository",
    "RepositoryTransitionRequest",
    "SupersedeAtomicRequest",
]


@dataclass(frozen=True)
class RepositoryTransitionRequest:
    """Inputs for planning and appending a repository lifecycle transition."""

    assertion_id: str
    to_state: LifecycleState
    ctx: AuthorityContext
    expected_sequence: int
    rationale: str
    successor_assertion_id: str | None = None
    event_id: str | None = None


@dataclass(frozen=True)
class RegisterEvidenceRequest:
    """Inputs for immutable evidence registration and linking."""

    assertion_id: str
    evidence: EvidenceRecord
    polarity: EvidencePolarity
    ctx: AuthorityContext
    link_id: str | None = None


@dataclass(frozen=True)
class SupersedeAtomicRequest:
    """Inputs for atomic successor acceptance and predecessor supersession."""

    predecessor_id: str
    successor_proposal: AssertionProposal
    proposal_ctx: AuthorityContext
    determination_ctx: AuthorityContext
    expected_sequence: int
    rationale: str
    accept_rationale: str = "accept successor"


@dataclass(frozen=True)
class ProjectionSourceSnapshot:
    """Deterministically ordered assertion data consumed by the projector."""

    assertions: tuple[Assertion, ...]
    events: tuple[AssertionEvent, ...]
    evidence: tuple[EvidenceRecord, ...]
    evidence_links: tuple[EvidenceLink, ...]


@dataclass(frozen=True)
class FinalizeProjectionPublicationRequest:
    """Inputs for the sole atomic rebuild-success publication path."""

    projection: PersistProjectionRequest
    rebuild_job_id: str
    execution_id: str
    node_count: int
    edge_count: int
    duration_ms: int
    publication_id: str | None = None
    published_at: datetime | None = None


@dataclass(frozen=True)
class PublishedProjectionRevision:
    """Projection revision and publication committed by one rebuild."""

    persisted: PersistedProjectionRevision
    publication_id: str
    rebuild_job_id: str
    execution_id: str
    published_at: datetime


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


def _raise_validation(message: str, exc: IntegrityError | None) -> NoReturn:
    """Raise ValidationError, optionally chaining a prior IntegrityError."""
    if exc is None:
        raise ValidationError(message)
    raise ValidationError(message) from exc


def _new_id() -> str:
    return str(uuid4())


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _server_utc(value: object) -> datetime:
    """Normalize a trusted repository clock value to timezone-aware UTC."""
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError("repository clock must return a timezone-aware datetime")
    return value.astimezone(UTC)


def _check_rebuild_cancelled(cancel_check: Callable[[], bool] | None) -> None:
    """Raise the rebuild cancellation signal when requested."""
    if cancel_check is not None and cancel_check():
        raise RebuildCancelledError("Rebuild cancelled while loading projection source snapshot")


def _event_from_orm(row: RelationshipAssertionEventORM) -> AssertionEvent:
    recorded_at = _as_utc(row.recorded_at)
    if recorded_at is None:
        raise ValidationError("event recorded_at missing")
    return AssertionEvent(
        event_id=row.id,
        assertion_id=row.assertion_id,
        sequence=row.sequence,
        from_state=cast(LifecycleState | None, row.from_state),
        to_state=cast(LifecycleState, row.to_state),
        authority=cast(AuthorityRole, row.authority),
        actor_id=row.actor_id,
        rationale=row.rationale,
        policy_version=row.policy_version,
        recorded_at=recorded_at,
        successor_assertion_id=row.successor_assertion_id,
        correlation_id=row.correlation_id,
    )


def _evidence_from_orm(row: RelationshipEvidenceORM) -> EvidenceRecord:
    recorded_at = _as_utc(row.recorded_at)
    if recorded_at is None:
        raise ValidationError("evidence recorded_at missing")
    return EvidenceRecord(
        evidence_id=row.id,
        source_ref=row.source_ref,
        content_sha256=row.content_sha256,
        media_type=row.media_type,
        visibility=cast(Visibility, evidence.visibility) if False else cast(Visibility, row.visibility),
        custody_id=row.custody_id,
        recorded_at=recorded_at,
        observed_at=_as_utc(row.observed_at),
        issued_at=_as_utc(row.issued_at),
        licensing=row.licensing,
        reuse_policy=row.reuse_policy,
    )


def _link_from_orm(row: RelationshipAssertionEvidenceORM) -> EvidenceLink:
    recorded_at = _as_utc(row.recorded_at)
    if recorded_at is None:
        raise ValidationError("evidence link recorded_at missing")
    return EvidenceLink(
        link_id=row.id,
        assertion_id=row.assertion_id,
        evidence_id=row.evidence_id,
        polarity=cast_polarity(row.polarity),
        recorded_at=recorded_at,
    )


def _fix_assertion_mapping(row: RelationshipAssertionORM) -> Assertion:
    status = row.confidence_status
    if status not in ("assessed", "not_assessed"):
        raise ValidationError(f"invalid confidence_status in store: {status!r}")
    effective_from = _as_utc(row.effective_from)
    recorded_at = _as_utc(row.recorded_at)
    if effective_from is None or recorded_at is None:
        raise ValidationError("assertion timestamps missing")
    return Assertion(
        assertion_id=row.id,
        predicate_id=row.predicate_id,
        subject_id=row.subject_id,
        object_id=row.object_id,
        method_id=row.method_id,
        proposition=row.proposition,
        confidence_status=status,  # type: ignore[arg-type]
        confidence_bp=row.confidence_bp,
        confidence_type=row.confidence_type,
        confidence_method=row.confidence_method,
        effective_from=effective_from,
        effective_to=_as_utc(row.effective_to),
        recorded_at=recorded_at,
    )


def _evidence_identity_tuple(evidence: EvidenceRecord) -> tuple[object, ...]:
    """Return comparable immutable evidence metadata for all persisted fields."""
    return (
        evidence.source_ref,
        evidence.content_sha256,
        evidence.media_type,
        evidence.visibility,
        evidence.custody_id,
        evidence.observed_at,
        evidence.issued_at,
        evidence.licensing,
        evidence.reuse_policy,
    )


def _with_recorded_at(evidence: EvidenceRecord, recorded_at: datetime) -> EvidenceRecord:
    """Return typed evidence with its repository-assigned recording timestamp."""
    return cast(EvidenceRecord, replace(evidence, recorded_at=recorded_at))


def _is_foreign_key_integrity_error(exc: IntegrityError) -> bool:
    """Return True when ``exc`` looks like a foreign-key violation."""
    detail = str(getattr(exc, "orig", None) or exc).lower()
    return "foreign key" in detail or "foreignkeyviolation" in detail


def _parse_known_at(known_at: datetime, assertion: Assertion) -> datetime | None:
    known = _as_utc(known_at)
    if known is None:
        raise ValidationError("known_at is required")
    if assertion.recorded_at > known:
        return None
    return known


def _effective_at_visible(assertion: Assertion, effective: datetime) -> bool:
    if assertion.effective_from > effective:
        return False
    return not (assertion.effective_to is not None and assertion.effective_to < effective)


def _resolve_as_of_bounds(
    assertion: Assertion,
    known_at: datetime,
    effective_at: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    known = _parse_known_at(known_at, assertion)
    if known is None:
        return None, None
    if effective_at is None:
        return known, None
    effective = _as_utc(effective_at)
    if effective is None:
        raise ValidationError("effective_at is required when provided")
    if not _effective_at_visible(assertion, effective):
        return None, None
    return known, effective


def _validate_event_identity(assertion_id: str, event: AssertionEvent) -> None:
    if event.assertion_id != assertion_id:
        raise ValidationError("event assertion_id mismatch")


def _validate_event_sequence(
    event: AssertionEvent,
    expected_sequence: int,
    current_max: int,
) -> None:
    if event.sequence != expected_sequence + 1:
        raise ConcurrencyConflict(f"event.sequence {event.sequence} != expected_sequence+1 ({expected_sequence + 1})")
    if current_max != expected_sequence:
        raise ConcurrencyConflict(f"expected_sequence {expected_sequence} but current max is {current_max}")


def _validate_event_recorded_at(event: AssertionEvent, previous_recorded_at: datetime | None) -> None:
    """Reject an event that does not advance its assertion stream clock."""
    if previous_recorded_at is not None and event.recorded_at <= previous_recorded_at:
        raise ValidationError("event.recorded_at must be strictly increasing within an assertion stream")


def _validate_supersede_state(predecessor_id: str, pred_state: LifecycleState) -> None:
    if pred_state not in ("Accepted", "Disputed"):
        raise ValidationError(
            f"predecessor {predecessor_id} must be Accepted or Disputed to supersede (current={pred_state})"
        )


def _validate_supersede_ids(request: SupersedeAtomicRequest) -> None:
    if request.predecessor_id == request.successor_proposal.assertion_id:
        raise SupersessionCycle("self-supersession is forbidden")


def _validate_supersede_sequence(request: SupersedeAtomicRequest, current_max: int) -> None:
    if current_max != request.expected_sequence:
        raise ConcurrencyConflict(f"expected_sequence {request.expected_sequence} but current max is {current_max}")


def _assertion_orm(assertion: Assertion) -> RelationshipAssertionORM:
    return RelationshipAssertionORM(
        id=assertion.assertion_id,
        predicate_id=assertion.predicate_id,
        subject_id=assertion.subject_id,
        object_id=assertion.object_id,
        method_id=assertion.method_id,
        proposition=assertion.proposition,
        confidence_bp=assertion.confidence_bp,
        confidence_type=assertion.confidence_type,
        confidence_method=assertion.confidence_method,
        confidence_status=assertion.confidence_status,
        effective_from=assertion.effective_from,
        effective_to=assertion.effective_to,
        recorded_at=assertion.recorded_at,
    )


def _event_orm(event: AssertionEvent) -> RelationshipAssertionEventORM:
    return RelationshipAssertionEventORM(
        id=event.event_id,
        assertion_id=event.assertion_id,
        sequence=event.sequence,
        from_state=event.from_state,
        to_state=event.to_state,
        authority=event.authority,
        actor_id=event.actor_id,
        rationale=event.rationale,
        policy_version=event.policy_version,
        recorded_at=event.recorded_at,
        successor_assertion_id=event.successor_assertion_id,
        correlation_id=event.correlation_id,
    )


def _plan_repository_transition(
    request: RepositoryTransitionRequest,
    current: LifecycleState,
    stamp: datetime,
    proposer_actor_id: str,
    successor_chain_lookup: Callable[[str], Sequence[str]],
) -> AssertionEvent:
    timing = TransitionTiming(
        expected_sequence=request.expected_sequence,
        rationale=request.rationale,
        recorded_at=stamp,
        event_id=request.event_id,
    )
    plan = TransitionPlan(
        assertion_id=request.assertion_id,
        current=current,
        to_state=request.to_state,
        ctx=request.ctx,
        timing=timing,
        successor_assertion_id=request.successor_assertion_id,
        proposer_actor_id=proposer_actor_id,
    )
    if request.to_state == "Superseded":
        if request.successor_assertion_id is None:
            raise ValidationError("supersession requires successor_assertion_id")
        return plan_supersede(SupersedePlan(transition=plan, successor_chain_lookup=successor_chain_lookup))
    return plan_transition(plan)


class RelationshipAssertionRepository:
    """INSERT-only persistence for governed assertions, events, and evidence."""

    def __init__(
        self,
        session: Session,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Bind a SQLAlchemy session and optional injectable clock."""
        self._session = session
        self._clock = clock or _utcnow

    def _server_time(self) -> datetime:
        """Read and normalize the trusted repository clock."""
        return _server_utc(self._clock())

    def _latest_assertion_recorded_at(self, assertion_id: str) -> datetime | None:
        """Return the latest event or evidence-link time for one assertion."""
        timeline = union_all(
            select(RelationshipAssertionEventORM.recorded_at.label("recorded_at")).where(
                RelationshipAssertionEventORM.assertion_id == assertion_id
            ),
            select(RelationshipAssertionEvidenceORM.recorded_at.label("recorded_at")).where(
                RelationshipAssertionEvidenceORM.assertion_id == assertion_id
            ),
        ).subquery()
        value = self._session.execute(
            select(timeline.c.recorded_at).order_by(timeline.c.recorded_at.desc()).limit(1)
        ).scalar_one_or_none()
        return _as_utc(value)

    def _next_assertion_time(self, assertion_id: str, *, after: datetime | None = None) -> datetime:
        """Allocate a timestamp after the assertion's event/evidence timeline."""
        candidate = self._server_time()
        latest = self._latest_assertion_recorded_at(assertion_id)
        floor = latest
        if after is not None:
            normalized_after = _server_utc(after)
            if floor is None or normalized_after > floor:
                floor = normalized_after
        if floor is None or candidate > floor:
            return candidate
        try:
            return floor + timedelta(microseconds=1)
        except OverflowError as exc:
            raise ValidationError("assertion event time cannot advance beyond datetime.max") from exc

    def propose(
        self,
        proposal: AssertionProposal,
        ctx: AuthorityContext,
        *,
        event_id: str | None = None,
    ) -> tuple[Assertion, AssertionEvent]:
        """Create an assertion + Proposed event, or return the existing identical proposal."""
        validate_authority(ctx, "proposer")
        existing = self._session.get(RelationshipAssertionORM, proposal.assertion_id)
        if existing is not None:
            return self._existing_proposal(existing, proposal, ctx)

        stamp = self._next_assertion_time(proposal.assertion_id)
        assertion, event = plan_propose(proposal, ctx, recorded_at=stamp, event_id=event_id)
        return self._insert_new_proposal(assertion, event, proposal, ctx)

    def _propose_new(
        self,
        proposal: AssertionProposal,
        ctx: AuthorityContext,
        *,
        after: datetime,
    ) -> tuple[Assertion, AssertionEvent]:
        """Insert a new proposal without adopting an idempotent race winner."""
        validate_authority(ctx, "proposer")
        stamp = self._next_assertion_time(proposal.assertion_id, after=after)
        assertion, event = plan_propose(proposal, ctx, recorded_at=stamp)
        return self._insert_new_proposal(
            assertion,
            event,
            proposal,
            ctx,
            reuse_existing=False,
        )

    def _append_event(
        self,
        assertion_id: str,
        event: AssertionEvent,
        *,
        expected_sequence: int,
    ) -> AssertionEvent:
        """INSERT a planner-produced event when ``expected_sequence`` matches current max.

        Private on purpose: callers must go through ``transition`` / ``supersede_atomic``
        so matrix authority and successor checks cannot be bypassed with a fabricated event.
        """
        _validate_event_identity(assertion_id, event)
        _validate_event_sequence(event, expected_sequence, self._max_sequence(assertion_id))
        _validate_event_recorded_at(event, self._latest_assertion_recorded_at(assertion_id))
        if self._session.get(RelationshipAssertionORM, assertion_id) is None:
            raise ValidationError(f"unknown assertion_id: {assertion_id}")
        try:
            with self._session.begin_nested():
                self._insert_event_orm(event)
                self._session.flush()
        except IntegrityError as exc:
            error: Exception
            if _is_foreign_key_integrity_error(exc):
                error = ValidationError(
                    f"event foreign-key violation for assertion {assertion_id} "
                    f"(check successor_assertion_id and related rows)"
                )
            else:
                error = ConcurrencyConflict(f"sequence conflict for assertion {assertion_id} at {event.sequence}")
            raise error from exc
        return event

    def transition(self, request: RepositoryTransitionRequest) -> AssertionEvent:
        """Plan and append a matrix transition under the concurrency guard."""
        if request.to_state == "Superseded":
            raise IllegalTransition("Superseded is available only through supersede_atomic")
        self._lock_assertions(request.assertion_id)
        current, proposer_actor_id, _tail = self._stream_summary(request.assertion_id)
        stamp = self._next_assertion_time(request.assertion_id)
        event = _plan_repository_transition(
            request,
            current,
            stamp,
            proposer_actor_id,
            self._successor_chain_lookup,
        )
        return self._append_event(request.assertion_id, event, expected_sequence=request.expected_sequence)

    def register_evidence(self, request: RegisterEvidenceRequest) -> tuple[EvidenceRecord, EvidenceLink]:
        """Register immutable evidence (digest-validated) and an append-only polarity link."""
        self._lock_assertions(request.assertion_id)
        stamp = self._next_assertion_time(request.assertion_id)
        normalized = validate_evidence_record(_with_recorded_at(request.evidence, stamp))
        link = self._plan_evidence_link(request, normalized, stamp)
        stored_evidence = self._upsert_evidence(normalized)
        existing = self._find_evidence_link(request.assertion_id, normalized.evidence_id)
        if existing is not None:
            return self._reuse_evidence_link(existing, request.polarity)
        self._insert_evidence_link(link)
        return stored_evidence, link

    def _plan_evidence_link(
        self,
        request: RegisterEvidenceRequest,
        normalized: EvidenceRecord,
        stamp: datetime,
    ) -> EvidenceLink:
        link = EvidenceLink(
            link_id=request.link_id or _new_id(),
            assertion_id=request.assertion_id,
            evidence_id=normalized.evidence_id,
            polarity=request.polarity,
            recorded_at=stamp,
        )
        plan_register_evidence(
            EvidenceRegistrationPlan(
                assertion_id=request.assertion_id,
                state=self._current_state(request.assertion_id),
                link=link,
                ctx=request.ctx,
                evidence=normalized,
            )
        )
        return link

    def _find_evidence_link(
        self,
        assertion_id: str,
        evidence_id: str,
    ) -> RelationshipAssertionEvidenceORM | None:
        return self._session.execute(
            select(RelationshipAssertionEvidenceORM).where(
                RelationshipAssertionEvidenceORM.assertion_id == assertion_id,
                RelationshipAssertionEvidenceORM.evidence_id == evidence_id,
            )
        ).scalar_one_or_none()

    def _reuse_evidence_link(
        self,
        existing_link: RelationshipAssertionEvidenceORM,
        polarity: EvidencePolarity,
    ) -> tuple[EvidenceRecord, EvidenceLink]:
        if existing_link.polarity != polarity:
            raise ValidationError(
                f"evidence link already exists with a different polarity ({existing_link.polarity} != {polarity})"
            )
        evidence_row = self._session.get(RelationshipEvidenceORM, existing_link.evidence_id)
        if evidence_row is None:
            raise ValidationError(f"evidence {existing_link.evidence_id} missing for existing link")
        return _evidence_from_orm(evidence_row), _link_from_orm(existing_link)

    def _insert_evidence_link(self, link: EvidenceLink) -> None:
        try:
            with self._session.begin_nested():
                self._session.add(
                    RelationshipAssertionEvidenceORM(
                        id=link.link_id,
                        assertion_id=link.assertion_id,
                        evidence_id=link.evidence_id,
                        polarity=link.polarity,
                        recorded_at=link.recorded_at,
                    )
                )
                self._session.flush()
        except IntegrityError as exc:
            raise ConcurrencyConflict("concurrent evidence link insert conflicted") from exc

    def supersede_atomic(
        self,
        request: SupersedeAtomicRequest,
    ) -> tuple[Assertion, AssertionEvent, AssertionEvent, AssertionEvent]:
        """Atomically accept a successor and supersede the predecessor."""
        # Savepoint so a late failure releases graph locks without losing unrelated outer work.
        with self._session.begin_nested():
            self._lock_supersession_graph()
            self._lock_assertions(request.predecessor_id, request.successor_proposal.assertion_id)
            pred_state, pred_proposer_actor_id, pred_tail = self._stream_summary(request.predecessor_id)
            self._validate_supersede_preconditions(request, pred_state)
            successor, propose_event = self._propose_new(
                request.successor_proposal,
                request.proposal_ctx,
                after=pred_tail,
            )
            accept_timing = TransitionTiming(
                1,
                request.accept_rationale,
                self._next_assertion_time(successor.assertion_id),
            )
            accept_event = plan_accept(
                successor.assertion_id,
                "Proposed",
                request.determination_ctx,
                timing=accept_timing,
                proposer_actor_id=request.proposal_ctx.actor_id,
            )
            self._append_event(successor.assertion_id, accept_event, expected_sequence=1)
            supersede_stamp = self._next_assertion_time(
                request.predecessor_id,
                after=accept_event.recorded_at,
            )
            supersede_event = _plan_repository_transition(
                RepositoryTransitionRequest(
                    assertion_id=request.predecessor_id,
                    to_state="Superseded",
                    ctx=request.determination_ctx,
                    expected_sequence=request.expected_sequence,
                    rationale=request.rationale,
                    successor_assertion_id=successor.assertion_id,
                ),
                pred_state,
                supersede_stamp,
                pred_proposer_actor_id,
                self._successor_chain_lookup,
            )
            self._append_event(request.predecessor_id, supersede_event, expected_sequence=request.expected_sequence)
            self._session.flush()
        return successor, propose_event, accept_event, supersede_event

    def get_as_of(
        self,
        assertion_id: str,
        *,
        known_at: datetime,
        effective_at: datetime | None = None,
    ) -> AssertionAsOf | None:
        """Reconstruct assertion state from events/links with ``recorded_at <= known_at``."""
        row = self._session.get(RelationshipAssertionORM, assertion_id)
        if row is None:
            return None
        assertion = _fix_assertion_mapping(row)
        known, effective = _resolve_as_of_bounds(assertion, known_at, effective_at)
        if known is None:
            return None
        events = tuple(event for event in self._load_events(assertion_id) if event.recorded_at <= known)
        if not events:
            return None
        link_rows = self._session.execute(
            select(RelationshipAssertionEvidenceORM)
            .where(RelationshipAssertionEvidenceORM.assertion_id == assertion_id)
            .order_by(RelationshipAssertionEvidenceORM.recorded_at)
        ).scalars()
        links = tuple(
            link for link in (_link_from_orm(link_row) for link_row in link_rows) if link.recorded_at <= known
        )
        return AssertionAsOf(
            assertion=assertion,
            state=resolve_state(events),
            events=events,
            evidence_links=links,
            effective_at=effective,
            known_at=known,
        )

    def persist_projection_revision(self, request: PersistProjectionRequest) -> PersistedProjectionRevision:
        """INSERT a candidate projection revision and its edges (publication is separate)."""
        return ProjectionRevisionStore(self._session, clock=self._clock).persist(request)

    def get_projection_revision(self, revision_id: str) -> PersistedProjectionRevision | None:
        """Load a persisted candidate revision and its ordered edges."""
        return ProjectionRevisionStore(self._session, clock=self._clock).get(revision_id)

    def load_projection_source_snapshot(
        self,
        *,
        cancel_check: Callable[[], bool] | None = None,
    ) -> ProjectionSourceSnapshot:
        """Load all append-only projector inputs from one deterministic snapshot."""
        bind = self._session.get_bind()
        if bind.dialect.name == "postgresql" and not self._session.in_transaction():
            self._session.connection(execution_options={"isolation_level": "REPEATABLE READ"})

        _check_rebuild_cancelled(cancel_check)
        assertion_rows = self._session.execute(
            select(RelationshipAssertionORM).order_by(RelationshipAssertionORM.id)
        ).scalars()
        assertions = []
        for row in assertion_rows:
            _check_rebuild_cancelled(cancel_check)
            assertions.append(_fix_assertion_mapping(row))

        event_rows = self._session.execute(
            select(RelationshipAssertionEventORM).order_by(
                RelationshipAssertionEventORM.assertion_id,
                RelationshipAssertionEventORM.sequence,
                RelationshipAssertionEventORM.id,
            )
        ).scalars()
        events = []
        for row in event_rows:
            _check_rebuild_cancelled(cancel_check)
            events.append(_event_from_orm(row))

        evidence_rows = self._session.execute(
            select(RelationshipEvidenceORM).order_by(RelationshipEvidenceORM.id)
        ).scalars()
        evidence = []
        for row in evidence_rows:
            _check_rebuild_cancelled(cancel_check)
            evidence.append(_evidence_from_orm(row))

        link_rows = self._session.execute(
            select(RelationshipAssertionEvidenceORM).order_by(
                RelationshipAssertionEvidenceORM.assertion_id,
                RelationshipAssertionEvidenceORM.evidence_id,
                RelationshipAssertionEvidenceORM.id,
            )
        ).scalars()
        evidence_links = []
        for row in link_rows:
            _check_rebuild_cancelled(cancel_check)
            evidence_links.append(_link_from_orm(row))
        _check_rebuild_cancelled(cancel_check)
        return ProjectionSourceSnapshot(
            assertions=tuple(assertions),
            events=tuple(events),
            evidence=tuple(evidence),
            evidence_links=tuple(evidence_links),
        )

    def latest_published_scopes(self, purpose: str) -> tuple[GovernedScope, ...]:
        """Load scopes from the latest successfully published revision."""
        return ProjectionRevisionStore(self._session, clock=self._clock).latest_published_scopes(purpose)

    def _require_publication_execution_id(self, execution_id: str | None) -> str:
        """Return a persisted publication execution id or fail closed."""
        if not isinstance(execution_id, str) or not execution_id.strip():
            raise ValidationError("published projection execution_id must be non-null and non-empty")
        return execution_id

    def _published_projection_from_orm(
        self,
        publication: RelationshipProjectionPublicationORM,
    ) -> PublishedProjectionRevision:
        """Map one succeeded publication ORM row into the read model contract."""
        persisted = self.get_projection_revision(publication.revision_id)
        if persisted is None:
            raise ValidationError("published projection references missing revision")
        published_at = _as_utc(publication.published_at)
        if published_at is None:
            raise ValidationError("published projection published_at is required")
        return PublishedProjectionRevision(
            persisted=persisted,
            publication_id=publication.id,
            rebuild_job_id=publication.rebuild_job_id,
            execution_id=self._require_publication_execution_id(publication.execution_id),
            published_at=published_at,
        )

    def _require_single_publication_for_rebuild_job(self, purpose: str, rebuild_job_id: str) -> None:
        """Fail closed when one succeeded rebuild owns multiple publication rows."""
        count = self._session.execute(
            select(func.count())
            .select_from(RelationshipProjectionPublicationORM)
            .join(
                RelationshipProjectionRevisionORM,
                RelationshipProjectionRevisionORM.id == RelationshipProjectionPublicationORM.revision_id,
            )
            .join(
                RebuildJobORM,
                RebuildJobORM.job_id == RelationshipProjectionPublicationORM.rebuild_job_id,
            )
            .where(RelationshipProjectionRevisionORM.purpose == purpose)
            .where(RebuildJobORM.status == "succeeded")
            .where(RelationshipProjectionPublicationORM.rebuild_job_id == rebuild_job_id)
        ).scalar_one()
        if count > 1:
            raise ValidationError(
                f"published projection has impossible cardinality for rebuild job {rebuild_job_id}: {count}"
            )

    def get_published_projection(self, publication_id: str) -> PublishedProjectionRevision | None:
        """Load one succeeded publication by publication id."""
        publication = self._session.execute(
            select(RelationshipProjectionPublicationORM)
            .join(
                RebuildJobORM,
                RebuildJobORM.job_id == RelationshipProjectionPublicationORM.rebuild_job_id,
            )
            .where(RelationshipProjectionPublicationORM.id == publication_id)
            .where(RebuildJobORM.status == "succeeded")
        ).scalar_one_or_none()
        if publication is None:
            return None
        published = self._published_projection_from_orm(publication)
        self._require_single_publication_for_rebuild_job(
            published.persisted.revision.purpose,
            published.rebuild_job_id,
        )
        return published

    def latest_published_projection_record(self, purpose: str) -> PublishedProjectionRevision | None:
        """Load the latest succeeded publication record for ``purpose``."""
        publication = self._session.execute(
            select(RelationshipProjectionPublicationORM)
            .join(
                RelationshipProjectionRevisionORM,
                RelationshipProjectionRevisionORM.id == RelationshipProjectionPublicationORM.revision_id,
            )
            .join(
                RebuildJobORM,
                RebuildJobORM.job_id == RelationshipProjectionPublicationORM.rebuild_job_id,
            )
            .where(RelationshipProjectionRevisionORM.purpose == purpose)
            .where(RebuildJobORM.status == "succeeded")
            .order_by(
                RelationshipProjectionPublicationORM.published_at.desc(),
                RelationshipProjectionPublicationORM.rebuild_job_id.desc(),
                RelationshipProjectionPublicationORM.id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()
        if publication is None:
            return None
        self._require_single_publication_for_rebuild_job(purpose, publication.rebuild_job_id)
        return self._published_projection_from_orm(publication)

    def latest_published_projection(self, purpose: str) -> PersistedProjectionRevision | None:
        """Load the latest successful projection publication for ``purpose``."""
        published = self.latest_published_projection_record(purpose)
        return None if published is None else published.persisted

    def next_publication_time(self, purpose: str) -> datetime:
        """Return a database-derived timestamp ordered after prior successful publications."""
        database_now: datetime | None
        if self._session.get_bind().dialect.name == "sqlite":
            raw_database_now = self._session.execute(select(func.strftime("%Y-%m-%d %H:%M:%f", "now"))).scalar_one()
            database_now = datetime.fromisoformat(raw_database_now).replace(tzinfo=UTC)
        else:
            database_now = _as_utc(self._session.execute(select(func.current_timestamp())).scalar_one())
        if database_now is None:
            raise ValidationError("database current timestamp is required for publication")
        latest = _as_utc(
            self._session.execute(
                select(func.max(RelationshipProjectionPublicationORM.published_at))
                .join(
                    RelationshipProjectionRevisionORM,
                    RelationshipProjectionRevisionORM.id == RelationshipProjectionPublicationORM.revision_id,
                )
                .join(
                    RebuildJobORM,
                    RebuildJobORM.job_id == RelationshipProjectionPublicationORM.rebuild_job_id,
                )
                .where(RelationshipProjectionRevisionORM.purpose == purpose)
                .where(RebuildJobORM.status == "succeeded")
            ).scalar_one()
        )
        if latest is not None and latest >= database_now:
            return latest + timedelta(microseconds=1)
        return database_now

    def finalize_projection_publication(
        self,
        request: FinalizeProjectionPublicationRequest,
        *,
        pre_success_check: Callable[[], None],
        pre_commit_check: Callable[[], None],
    ) -> PublishedProjectionRevision:
        """Atomically persist one candidate, succeed its owner job, and publish it.

        The existing owner-guarded ``RUNNING -> SUCCEEDED`` update serializes
        concurrent first publishers for the rebuild job. Any failure rolls the
        candidate, success transition, and publication back together.
        """
        execution_id = request.execution_id
        if not isinstance(execution_id, str) or not execution_id.strip():
            raise ValidationError("publication execution_id must be non-null and non-empty")

        pre_success_check()

        from src.data.repository import AssetGraphRepository  # pylint: disable=import-outside-toplevel

        AssetGraphRepository(self._session).mark_rebuild_job_succeeded(
            request.rebuild_job_id,
            execution_id=execution_id,
            node_count=request.node_count,
            edge_count=request.edge_count,
            duration_ms=request.duration_ms,
        )
        persisted = self.persist_projection_revision(request.projection)

        publication_id = request.publication_id or str(uuid4())
        published_at = self._server_time() if request.published_at is None else _server_utc(request.published_at)
        try:
            with self._session.begin_nested():
                self._session.add(
                    RelationshipProjectionPublicationORM(
                        id=publication_id,
                        revision_id=persisted.revision_id,
                        rebuild_job_id=request.rebuild_job_id,
                        execution_id=execution_id,
                        published_at=published_at,
                    )
                )
                self._session.flush()
        except IntegrityError as exc:
            raise ConcurrencyConflict(f"publication insert conflicted for rebuild {request.rebuild_job_id}") from exc

        pre_commit_check()
        return PublishedProjectionRevision(
            persisted=persisted,
            publication_id=publication_id,
            rebuild_job_id=request.rebuild_job_id,
            execution_id=execution_id,
            published_at=published_at,
        )

    def current_state(self, assertion_id: str) -> LifecycleState:
        """Return the latest lifecycle state for ``assertion_id``."""
        return self._current_state(assertion_id)

    def max_sequence(self, assertion_id: str) -> int:
        """Return the highest event sequence for ``assertion_id`` (0 if none)."""
        return self._max_sequence(assertion_id)

    def _existing_proposal(
        self,
        row: RelationshipAssertionORM,
        proposal: AssertionProposal,
        ctx: AuthorityContext,
        *,
        exc: IntegrityError | None = None,
        missing_event_suffix: str = "",
    ) -> tuple[Assertion, AssertionEvent]:
        validate_authority(ctx, "proposer")
        domain = _fix_assertion_mapping(row)
        if not proposals_equivalent(domain, proposal):
            _raise_validation(
                f"assertion {proposal.assertion_id} already exists with a different proposition",
                exc,
            )
        events = self._load_events(proposal.assertion_id)
        if not events:
            _raise_validation(
                f"assertion {proposal.assertion_id} missing propose event{missing_event_suffix}",
                exc,
            )
        resolve_state(events)
        if events[0].actor_id != ctx.actor_id:
            error = UnauthorizedTransition("idempotent proposal reuse requires the proposer of record")
            if exc is not None:
                raise error from exc
            raise error
        return domain, events[0]

    def _insert_new_proposal(
        self,
        assertion: Assertion,
        event: AssertionEvent,
        proposal: AssertionProposal,
        ctx: AuthorityContext,
        *,
        reuse_existing: bool = True,
    ) -> tuple[Assertion, AssertionEvent]:
        try:
            with self._session.begin_nested():
                self._session.add(_assertion_orm(assertion))
                self._session.flush()
                self._insert_event_orm(event)
                self._session.flush()
        except IntegrityError as exc:
            if not reuse_existing:
                raise ConcurrencyConflict(
                    f"concurrent successor proposal insert conflicted for {proposal.assertion_id}"
                ) from exc
            raced = self._session.get(RelationshipAssertionORM, proposal.assertion_id)
            if raced is None:
                raise ValidationError(f"propose failed for {proposal.assertion_id}: {exc}") from exc
            return self._existing_proposal(
                raced,
                proposal,
                ctx,
                exc=exc,
                missing_event_suffix=" after conflict",
            )
        return assertion, event

    def _validate_supersede_preconditions(
        self,
        request: SupersedeAtomicRequest,
        pred_state: LifecycleState,
    ) -> None:
        _validate_supersede_state(request.predecessor_id, pred_state)
        _validate_supersede_ids(request)
        assert_no_cycle(
            request.predecessor_id,
            request.successor_proposal.assertion_id,
            self._successor_chain_lookup,
        )
        _validate_supersede_sequence(request, self._max_sequence(request.predecessor_id))
        if self._session.get(RelationshipAssertionORM, request.successor_proposal.assertion_id) is not None:
            raise ValidationError(f"successor assertion {request.successor_proposal.assertion_id} already exists")

    def _lock_assertions(self, *assertion_ids: str) -> None:
        """Lock rows in sorted order for transition and supersession checks.

        PostgreSQL provides the required concurrency guarantees for ``SELECT FOR
        UPDATE``. SQLite ignores the clause; it remains supported for compatible
        local persistence and tests, without equivalent row-level serialization.
        """
        for assertion_id in sorted({item for item in assertion_ids if item}):
            self._session.execute(
                select(RelationshipAssertionORM.id).where(RelationshipAssertionORM.id == assertion_id).with_for_update()
            ).scalar_one_or_none()

    def _lock_supersession_graph(self) -> None:
        """Serialize supersession graph checks for the atomic savepoint.

        PostgreSQL first takes a stable transaction-scoped advisory lock, then
        locks rows in deterministic id order. Successful savepoint release keeps
        the locks through the enclosing transaction; rollback releases them.
        SQLite skips the advisory lock and retains its compatible, single-writer
        test behavior.
        """
        bind = self._session.get_bind()
        if bind.dialect.name == "postgresql":
            self._session.connection().execute(
                select(func.pg_advisory_xact_lock(_SUPERSESSION_LOCK_NAMESPACE, _SUPERSESSION_LOCK_RESOURCE))
            ).scalar_one()
        self._session.execute(
            select(RelationshipAssertionORM.id).order_by(RelationshipAssertionORM.id).with_for_update()
        ).scalars().all()

    def _stream_summary(self, assertion_id: str) -> tuple[LifecycleState, str, datetime]:
        """Resolve one stream into state, proposer of record, and tail time."""
        events = self._load_events(assertion_id)
        if not events:
            raise ValidationError(f"unknown or eventless assertion_id: {assertion_id}")
        return resolve_state(events), events[0].actor_id, events[-1].recorded_at

    def _current_state(self, assertion_id: str) -> LifecycleState:
        return self._stream_summary(assertion_id)[0]

    def _max_sequence(self, assertion_id: str) -> int:
        value = self._session.execute(
            select(func.coalesce(func.max(RelationshipAssertionEventORM.sequence), 0)).where(
                RelationshipAssertionEventORM.assertion_id == assertion_id
            )
        ).scalar_one()
        return int(value)

    def _load_events(self, assertion_id: str) -> list[AssertionEvent]:
        rows = self._session.execute(
            select(RelationshipAssertionEventORM)
            .where(RelationshipAssertionEventORM.assertion_id == assertion_id)
            .order_by(RelationshipAssertionEventORM.sequence)
        ).scalars()
        return [_event_from_orm(row) for row in rows]

    def _insert_event_orm(self, event: AssertionEvent) -> None:
        self._session.add(_event_orm(event))

    def _upsert_evidence(self, evidence: EvidenceRecord) -> EvidenceRecord:
        existing = self._session.get(RelationshipEvidenceORM, evidence.evidence_id)
        if existing is not None:
            domain = _evidence_from_orm(existing)
            if _evidence_identity_tuple(domain) != _evidence_identity_tuple(evidence):
                raise ValidationError(f"evidence {evidence.evidence_id} already exists with different metadata")
            return domain
        self._session.add(
            RelationshipEvidenceORM(
                id=evidence.evidence_id,
                source_ref=evidence.source_ref,
                content_sha256=evidence.content_sha256,
                media_type=evidence.media_type,
                observed_at=evidence.observed_at,
                issued_at=evidence.issued_at,
                visibility=evidence.visibility,
                licensing=evidence.licensing,
                reuse_policy=evidence.reuse_policy,
                custody_id=evidence.custody_id,
                recorded_at=evidence.recorded_at,
            )
        )
        self._session.flush()
        return evidence

    def _successor_chain_lookup(self, assertion_id: str) -> Sequence[str]:
        rows = self._session.execute(
            select(RelationshipAssertionEventORM.successor_assertion_id).where(
                RelationshipAssertionEventORM.assertion_id == assertion_id,
                RelationshipAssertionEventORM.to_state == "Superseded",
                RelationshipAssertionEventORM.successor_assertion_id.is_not(None),
            )
        ).scalars()
        return [successor for successor in rows if successor is not None]
