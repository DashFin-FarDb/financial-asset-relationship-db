"""Append-only repository for GRAC v1 assertion lifecycle and evidence.

INSERT-only against the PR3 ORM tables. Lifecycle decisions are planned in
``relationship_assertion_lifecycle``; this module persists them and enforces
expected-sequence concurrency and atomic supersession.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import cast
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.data.relationship_assertion_db_models import (
    RelationshipAssertionEventORM,
    RelationshipAssertionEvidenceORM,
    RelationshipAssertionORM,
    RelationshipEvidenceORM,
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
    LifecycleState,
    SupersessionCycle,
    ValidationError,
    Visibility,
)
from src.governance.relationship_assertion_lifecycle import (
    assert_no_cycle,
    cast_polarity,
    plan_accept,
    plan_propose,
    plan_register_evidence,
    plan_supersede,
    plan_transition,
    proposals_equivalent,
    resolve_state,
    validate_evidence_record,
)

UTC = timezone.utc


def _utcnow() -> datetime:
    """Server-recorded UTC timestamp."""
    return datetime.now(tz=UTC)


def _new_id() -> str:
    """Allocate a UUID string primary key."""
    return str(uuid4())


def _as_utc(value: datetime | None) -> datetime | None:
    """Normalize SQLite naive datetimes to timezone-aware UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _event_from_orm(row: RelationshipAssertionEventORM) -> AssertionEvent:
    """Map an ORM event row to the domain DTO."""
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
    """Map an ORM evidence row to the domain DTO."""
    recorded_at = _as_utc(row.recorded_at)
    if recorded_at is None:
        raise ValidationError("evidence recorded_at missing")
    return EvidenceRecord(
        evidence_id=row.id,
        source_ref=row.source_ref,
        content_sha256=row.content_sha256,
        media_type=row.media_type,
        visibility=cast(Visibility, row.visibility),
        custody_id=row.custody_id,
        recorded_at=recorded_at,
        observed_at=_as_utc(row.observed_at),
        issued_at=_as_utc(row.issued_at),
        licensing=row.licensing,
        reuse_policy=row.reuse_policy,
    )


def _link_from_orm(row: RelationshipAssertionEvidenceORM) -> EvidenceLink:
    """Map an ORM evidence-link row to the domain DTO."""
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
    """Map ORM assertion with correct confidence_status typing."""
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

    def propose(
        self,
        proposal: AssertionProposal,
        ctx: AuthorityContext,
        *,
        recorded_at: datetime | None = None,
        event_id: str | None = None,
    ) -> tuple[Assertion, AssertionEvent]:
        """Create an assertion + Proposed event, or return the existing identical proposal."""
        existing = self._session.get(RelationshipAssertionORM, proposal.assertion_id)
        if existing is not None:
            domain = _fix_assertion_mapping(existing)
            if not proposals_equivalent(domain, proposal):
                raise ValidationError(f"assertion {proposal.assertion_id} already exists with a different proposition")
            events = self._load_events(proposal.assertion_id)
            if not events:
                raise ValidationError(f"assertion {proposal.assertion_id} missing propose event")
            return domain, events[0]

        stamp = recorded_at or self._clock()
        assertion, event = plan_propose(proposal, ctx, recorded_at=stamp, event_id=event_id)
        self._session.add(
            RelationshipAssertionORM(
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
        )
        try:
            # Flush assertion before the event so SQLite FK checks see the parent row.
            self._session.flush()
            self._insert_event_orm(event)
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raced = self._session.get(RelationshipAssertionORM, proposal.assertion_id)
            if raced is None:
                raise ValidationError(f"propose failed for {proposal.assertion_id}: {exc}") from exc
            domain = _fix_assertion_mapping(raced)
            if not proposals_equivalent(domain, proposal):
                raise ValidationError(
                    f"assertion {proposal.assertion_id} already exists with a different proposition"
                ) from exc
            events = self._load_events(proposal.assertion_id)
            if not events:
                raise ValidationError(
                    f"assertion {proposal.assertion_id} missing propose event after conflict"
                ) from exc
            return domain, events[0]
        return assertion, event

    def append_event(
        self,
        assertion_id: str,
        event: AssertionEvent,
        *,
        expected_sequence: int,
    ) -> AssertionEvent:
        """INSERT a planned event only when ``expected_sequence`` matches current max."""
        if event.assertion_id != assertion_id:
            raise ValidationError("event assertion_id mismatch")
        if event.sequence != expected_sequence + 1:
            raise ConcurrencyConflict(
                f"event.sequence {event.sequence} != expected_sequence+1 ({expected_sequence + 1})"
            )
        current_max = self._max_sequence(assertion_id)
        if current_max != expected_sequence:
            raise ConcurrencyConflict(f"expected_sequence {expected_sequence} but current max is {current_max}")
        if self._session.get(RelationshipAssertionORM, assertion_id) is None:
            raise ValidationError(f"unknown assertion_id: {assertion_id}")
        self._insert_event_orm(event)
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConcurrencyConflict(f"sequence conflict for assertion {assertion_id} at {event.sequence}") from exc
        return event

    def transition(
        self,
        assertion_id: str,
        to_state: LifecycleState,
        ctx: AuthorityContext,
        *,
        expected_sequence: int,
        rationale: str,
        successor_assertion_id: str | None = None,
        recorded_at: datetime | None = None,
        event_id: str | None = None,
    ) -> AssertionEvent:
        """Plan and append a matrix transition under the concurrency guard."""
        current = self._current_state(assertion_id)
        stamp = recorded_at or self._clock()
        if to_state == "Superseded":
            if successor_assertion_id is None:
                raise ValidationError("supersession requires successor_assertion_id")
            event = plan_supersede(
                assertion_id,
                current,
                ctx,
                expected_sequence=expected_sequence,
                rationale=rationale,
                recorded_at=stamp,
                successor_assertion_id=successor_assertion_id,
                successor_chain_lookup=self._successor_chain_lookup,
                event_id=event_id,
            )
        else:
            event = plan_transition(
                assertion_id,
                current,
                to_state,
                ctx,
                expected_sequence=expected_sequence,
                rationale=rationale,
                recorded_at=stamp,
                successor_assertion_id=successor_assertion_id,
                event_id=event_id,
            )
        return self.append_event(assertion_id, event, expected_sequence=expected_sequence)

    def register_evidence(
        self,
        assertion_id: str,
        evidence: EvidenceRecord,
        polarity: EvidencePolarity,
        ctx: AuthorityContext,
        *,
        link_id: str | None = None,
        recorded_at: datetime | None = None,
    ) -> tuple[EvidenceRecord, EvidenceLink]:
        """Register immutable evidence (digest-validated) and an append-only polarity link."""
        stamp = recorded_at or self._clock()
        normalized = validate_evidence_record(
            EvidenceRecord(
                evidence_id=evidence.evidence_id,
                source_ref=evidence.source_ref,
                content_sha256=evidence.content_sha256,
                media_type=evidence.media_type,
                visibility=evidence.visibility,
                custody_id=evidence.custody_id,
                recorded_at=stamp,
                observed_at=evidence.observed_at,
                issued_at=evidence.issued_at,
                licensing=evidence.licensing,
                reuse_policy=evidence.reuse_policy,
            )
        )

        state = self._current_state(assertion_id)
        link = EvidenceLink(
            link_id=link_id or _new_id(),
            assertion_id=assertion_id,
            evidence_id=normalized.evidence_id,
            polarity=polarity,
            recorded_at=stamp,
        )
        plan_register_evidence(assertion_id, state, link, ctx, evidence=normalized)

        stored_evidence = self._upsert_evidence(normalized)
        existing_link = self._session.execute(
            select(RelationshipAssertionEvidenceORM).where(
                RelationshipAssertionEvidenceORM.assertion_id == assertion_id,
                RelationshipAssertionEvidenceORM.evidence_id == normalized.evidence_id,
            )
        ).scalar_one_or_none()
        if existing_link is not None:
            if existing_link.polarity != polarity:
                raise ValidationError(
                    "evidence link already exists with a different polarity "
                    f"({existing_link.polarity} != {polarity})"
                )
            return stored_evidence, _link_from_orm(existing_link)

        self._session.add(
            RelationshipAssertionEvidenceORM(
                id=link.link_id,
                assertion_id=link.assertion_id,
                evidence_id=link.evidence_id,
                polarity=link.polarity,
                recorded_at=link.recorded_at,
            )
        )
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConcurrencyConflict("concurrent evidence link insert conflicted") from exc
        return stored_evidence, link

    def supersede_atomic(
        self,
        predecessor_id: str,
        successor_proposal: AssertionProposal,
        ctx: AuthorityContext,
        *,
        expected_sequence: int,
        rationale: str,
        recorded_at: datetime | None = None,
        accept_rationale: str = "accept successor",
    ) -> tuple[Assertion, AssertionEvent, AssertionEvent, AssertionEvent]:
        """Atomically accept a successor and supersede the predecessor.

        Same transaction:
        1. propose successor (seq=1 Proposed)
        2. accept successor (seq=2 Accepted)
        3. supersede predecessor (→ Superseded with successor_assertion_id)

        On failure neither orphan successor nor superseded-without-successor is visible.
        """
        stamp = recorded_at or self._clock()
        pred_state = self._current_state(predecessor_id)
        if pred_state not in ("Accepted", "Disputed"):
            raise ValidationError(
                f"predecessor {predecessor_id} must be Accepted or Disputed to supersede " f"(current={pred_state})"
            )
        if predecessor_id == successor_proposal.assertion_id:
            raise SupersessionCycle("self-supersession is forbidden")
        assert_no_cycle(predecessor_id, successor_proposal.assertion_id, self._successor_chain_lookup)

        if self._max_sequence(predecessor_id) != expected_sequence:
            raise ConcurrencyConflict(
                f"expected_sequence {expected_sequence} but current max is " f"{self._max_sequence(predecessor_id)}"
            )
        if self._session.get(RelationshipAssertionORM, successor_proposal.assertion_id) is not None:
            raise ValidationError(f"successor assertion {successor_proposal.assertion_id} already exists")

        successor, propose_event = self.propose(successor_proposal, ctx, recorded_at=stamp)
        # Fresh propose always yields seq=1; accept at expected_sequence=1.
        accept_event = plan_accept(
            successor.assertion_id,
            "Proposed",
            ctx,
            expected_sequence=1,
            rationale=accept_rationale,
            recorded_at=stamp,
        )
        self.append_event(successor.assertion_id, accept_event, expected_sequence=1)

        supersede_event = plan_supersede(
            predecessor_id,
            pred_state,
            ctx,
            expected_sequence=expected_sequence,
            rationale=rationale,
            recorded_at=stamp,
            successor_assertion_id=successor.assertion_id,
            successor_chain_lookup=self._successor_chain_lookup,
        )
        self.append_event(predecessor_id, supersede_event, expected_sequence=expected_sequence)
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
        known = _as_utc(known_at)
        if known is None:
            raise ValidationError("known_at is required")
        if assertion.recorded_at > known:
            return None
        if effective_at is not None:
            effective = _as_utc(effective_at)
            if effective is None:
                raise ValidationError("effective_at is required when provided")
            if assertion.effective_from > effective:
                return None
            if assertion.effective_to is not None and assertion.effective_to < effective:
                return None
        else:
            effective = None

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

    def current_state(self, assertion_id: str) -> LifecycleState:
        """Return the latest lifecycle state for ``assertion_id``."""
        return self._current_state(assertion_id)

    def max_sequence(self, assertion_id: str) -> int:
        """Return the highest event sequence for ``assertion_id`` (0 if none)."""
        return self._max_sequence(assertion_id)

    def _current_state(self, assertion_id: str) -> LifecycleState:
        events = self._load_events(assertion_id)
        if not events:
            raise ValidationError(f"unknown or eventless assertion_id: {assertion_id}")
        return resolve_state(events)

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
        self._session.add(
            RelationshipAssertionEventORM(
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
        )

    def _upsert_evidence(self, evidence: EvidenceRecord) -> EvidenceRecord:
        existing = self._session.get(RelationshipEvidenceORM, evidence.evidence_id)
        if existing is not None:
            domain = _evidence_from_orm(existing)
            if (
                domain.source_ref != evidence.source_ref
                or domain.content_sha256 != evidence.content_sha256
                or domain.media_type != evidence.media_type
                or domain.visibility != evidence.visibility
                or domain.custody_id != evidence.custody_id
            ):
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
        """Return successor IDs recorded on Superseded events for ``assertion_id``."""
        rows = self._session.execute(
            select(RelationshipAssertionEventORM.successor_assertion_id).where(
                RelationshipAssertionEventORM.assertion_id == assertion_id,
                RelationshipAssertionEventORM.to_state == "Superseded",
                RelationshipAssertionEventORM.successor_assertion_id.is_not(None),
            )
        ).scalars()
        return [successor for successor in rows if successor is not None]
