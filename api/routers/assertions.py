"""Governed assertion command and explanation API routes."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Annotated, NoReturn, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.data.database import create_engine_from_url, create_session_factory
from src.data.relationship_assertion_db_models import RelationshipAssertionORM, RelationshipEvidenceORM
from src.data.relationship_assertion_repository import (
    RelationshipAssertionRepository,
    RepositoryTransitionRequest,
    SupersedeAtomicRequest,
)
from src.data.repository import session_scope
from src.governance.relationship_assertion import (
    AssertionAsOf,
    AssertionEvent,
    AssertionProposal,
    AuthorityContext,
    AuthorityRole,
    ConcurrencyConflict,
    EvidenceLink,
    IllegalTransition,
    SupersessionCycle,
    UnauthorizedTransition,
    ValidationError,
    Visibility,
)
from src.governance.relationship_assertion_contract import CONTRACT_VERSION

from ..assertion_models import (
    AssertionCommandResponse,
    AssertionDecisionRequest,
    AssertionEventResponse,
    AssertionEvidenceMetadataResponse,
    AssertionHistoryResponse,
    AssertionProposalRequest,
    AssertionPublicEventResponse,
    AssertionReadResponse,
    AssertionSupersessionRequest,
)
from ..auth import (
    User,
    _build_credentials_exception,
    _build_expired_exception,
    _decode_username_from_token,
    get_current_active_user,
    get_current_rebuild_operator_user,
    get_user,
)
from ..graph_lifecycle_providers import (
    GraphPersistenceInvalidUrlError,
    GraphPersistenceNonDurableError,
    GraphPersistenceNotConfiguredError,
    get_graph_lifecycle_settings,
    resolve_durable_graph_persistence_url,
    resolve_hosted_graph_database_url,
)

router = APIRouter()
_UTC = timezone.utc
_INTERNAL_ERROR_DETAIL = "An internal error occurred. Please try again later."
_DOMAIN_ERROR_STATUSES: dict[type[Exception], int] = {
    ConcurrencyConflict: status.HTTP_409_CONFLICT,
    SupersessionCycle: status.HTTP_409_CONFLICT,
    UnauthorizedTransition: status.HTTP_409_CONFLICT,
    ValidationError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    IllegalTransition: status.HTTP_422_UNPROCESSABLE_ENTITY,
}


def _authority_context(actor_id: str, role: AuthorityRole, request: Request) -> AuthorityContext:
    """Build the domain authority context recorded for one API command."""
    correlation = request.headers.get("x-correlation-id")
    return AuthorityContext(
        actor_id=actor_id,
        roles=frozenset({role}),
        policy_version=CONTRACT_VERSION,
        correlation_id=correlation,
    )


def _event_response(event: AssertionEvent) -> AssertionEventResponse:
    """Convert a domain lifecycle event into its API response model."""
    return AssertionEventResponse(
        event_id=event.event_id,
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


def _public_event_response(event: AssertionEvent) -> AssertionPublicEventResponse:
    """Convert a lifecycle event into its identity-redacted public view."""
    return AssertionPublicEventResponse(
        event_id=event.event_id,
        assertion_id=event.assertion_id,
        sequence=event.sequence,
        from_state=event.from_state,
        to_state=event.to_state,
        authority=event.authority,
        recorded_at=event.recorded_at,
        successor_assertion_id=event.successor_assertion_id,
    )


def _raise_domain_error(exc: Exception) -> NoReturn:
    """Raise the bounded HTTP error corresponding to a repository command failure."""
    status_code = _DOMAIN_ERROR_STATUSES.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
    detail = _INTERNAL_ERROR_DETAIL if status_code == status.HTTP_500_INTERNAL_SERVER_ERROR else str(exc)
    raise HTTPException(
        status_code=status_code,
        detail=detail,
    ) from exc


@contextmanager
def _assertion_repository_session() -> Iterator[Session]:
    """Yield a repository session bound only to durable graph persistence."""
    settings = get_graph_lifecycle_settings()
    engine: Engine | None = None
    try:
        hosted_url = resolve_hosted_graph_database_url(settings)
        legacy_url = (
            getattr(settings, "database_url", None) if not hasattr(settings, "asset_graph_database_url") else None
        )
        persistence_url = resolve_durable_graph_persistence_url(hosted_url or legacy_url)
        engine = create_engine_from_url(persistence_url)
        session_factory = create_session_factory(engine)
        with session_scope(session_factory) as session:
            yield session
    except HTTPException:
        raise
    except (
        GraphPersistenceInvalidUrlError,
        GraphPersistenceNotConfiguredError,
        GraphPersistenceNonDurableError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph persistence database not configured",
        ) from exc
    finally:
        if engine is not None:
            engine.dispose()


def _load_evidence_by_id(
    evidence_ids: set[str],
    session: Session,
) -> dict[str, RelationshipEvidenceORM]:
    """Load the bounded evidence subset linked to one assertion view."""
    if not evidence_ids:
        return {}
    evidence_rows = session.execute(
        select(RelationshipEvidenceORM).where(RelationshipEvidenceORM.id.in_(sorted(evidence_ids)))
    ).scalars()
    return {item.id: item for item in evidence_rows}


def _evidence_response(
    link: EvidenceLink,
    evidence_by_id: Mapping[str, RelationshipEvidenceORM],
) -> AssertionEvidenceMetadataResponse:
    """Return one public evidence row, redacting missing or non-public metadata."""
    evidence = evidence_by_id.get(link.evidence_id)
    if evidence is None:
        return AssertionEvidenceMetadataResponse(
            evidence_id=link.evidence_id,
            polarity=link.polarity,
            visibility="restricted",
            redacted=True,
        )
    visibility = cast(Visibility, evidence.visibility)
    is_public = visibility == "public"
    return AssertionEvidenceMetadataResponse(
        evidence_id=evidence.id,
        polarity=link.polarity,
        visibility=visibility,
        redacted=not is_public,
        source_ref=evidence.source_ref if is_public else None,
        media_type=evidence.media_type if is_public else None,
        content_sha256=evidence.content_sha256 if is_public else None,
        observed_at=evidence.observed_at if is_public else None,
        issued_at=evidence.issued_at if is_public else None,
        licensing=evidence.licensing if is_public else None,
        reuse_policy=evidence.reuse_policy if is_public else None,
        recorded_at=evidence.recorded_at if is_public else None,
    )


def _assertion_evidence(
    as_of: AssertionAsOf,
    session: Session,
) -> list[AssertionEvidenceMetadataResponse]:
    """Load and redact only evidence linked to the requested assertion view."""
    evidence_ids = {link.evidence_id for link in as_of.evidence_links}
    evidence_by_id = _load_evidence_by_id(evidence_ids, session)
    return [_evidence_response(link, evidence_by_id) for link in as_of.evidence_links]


def _require_assertion_events(as_of: AssertionAsOf) -> tuple[AssertionEvent, ...]:
    """Return the reconstructed event stream or fail closed on an invalid repository view."""
    if not as_of.events:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=_INTERNAL_ERROR_DETAIL)
    return as_of.events


def _require_assertion_exists(session: Session, assertion_id: str) -> None:
    """Raise the public not-found response before executing a repository command."""
    if session.get(RelationshipAssertionORM, assertion_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"unknown assertion_id: {assertion_id}")


def _assertion_read_response(
    as_of: AssertionAsOf,
    session: Session,
) -> AssertionReadResponse:
    """Build a public explanation from a validated non-empty event view."""
    events = _require_assertion_events(as_of)
    return AssertionReadResponse(
        assertion_id=as_of.assertion.assertion_id,
        predicate_id=as_of.assertion.predicate_id,
        subject_id=as_of.assertion.subject_id,
        object_id=as_of.assertion.object_id,
        method_id=as_of.assertion.method_id,
        proposition=as_of.assertion.proposition,
        confidence_status=as_of.assertion.confidence_status,
        confidence_bp=as_of.assertion.confidence_bp,
        confidence_type=as_of.assertion.confidence_type,
        confidence_method=as_of.assertion.confidence_method,
        effective_from=as_of.assertion.effective_from,
        effective_to=as_of.assertion.effective_to,
        recorded_at=as_of.assertion.recorded_at,
        state=as_of.state,
        known_at=as_of.known_at,
        effective_at=as_of.effective_at,
        sequence=events[-1].sequence,
        evidence=_assertion_evidence(as_of, session),
    )


def _resolve_proposer_user_from_token(token: str, request: Request) -> User:
    """Resolve and validate the separately authenticated supersession proposer."""
    username = _decode_username_from_token(
        token=token,
        credentials_exception=_build_credentials_exception(),
        expired_exception=_build_expired_exception(),
        request=request,
    )
    user = get_user(username)
    if user is None or user.disabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid proposal bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@router.post("/api/assertions")
async def create_assertion(
    payload: AssertionProposalRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> AssertionCommandResponse:
    """Create an assertion proposal or idempotently reuse the same proposer's prior proposal."""
    proposal = AssertionProposal(
        assertion_id=payload.assertion_id,
        predicate_id=payload.predicate_id,
        subject_id=payload.subject_id,
        object_id=payload.object_id,
        method_id=payload.method_id,
        proposition=payload.proposition,
        confidence_status=payload.confidence_status,
        confidence_bp=payload.confidence_bp,
        confidence_type=payload.confidence_type,
        confidence_method=payload.confidence_method,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
    )
    ctx = _authority_context(current_user.username, "proposer", request)
    with _assertion_repository_session() as session:
        repo = RelationshipAssertionRepository(session)
        try:
            proposed_event_id = str(uuid4())
            _assertion, event = repo.propose(proposal, ctx, event_id=proposed_event_id)
            return AssertionCommandResponse(
                assertion_id=payload.assertion_id,
                event=_event_response(event),
                state=repo.current_state(payload.assertion_id),
                idempotent_reuse=event.event_id != proposed_event_id,
            )
        except Exception as exc:  # pragma: no cover - defensive mapping
            _raise_domain_error(exc)


@router.post("/api/assertions/{assertion_id}/decisions")
async def decide_assertion(
    assertion_id: str,
    payload: AssertionDecisionRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> AssertionCommandResponse:
    """Apply a governed lifecycle decision against an existing assertion."""
    if payload.to_state == "Withdrawn":
        ctx = _authority_context(current_user.username, "proposer", request)
    else:
        reviewer = get_current_rebuild_operator_user(
            current_user=current_user,
            settings=get_settings(),
            request=request,
        )
        role_by_state: dict[str, AuthorityRole] = {
            "Accepted": "acceptor",
            "Rejected": "acceptor",
            "Disputed": "disputer",
            "Retracted": "retractor",
        }
        ctx = _authority_context(reviewer.username, role_by_state[payload.to_state], request)

    transition = RepositoryTransitionRequest(
        assertion_id=assertion_id,
        to_state=payload.to_state,
        ctx=ctx,
        expected_sequence=payload.expected_sequence,
        rationale=payload.rationale,
    )
    with _assertion_repository_session() as session:
        _require_assertion_exists(session, assertion_id)
        repo = RelationshipAssertionRepository(session)
        try:
            event = repo.transition(transition)
            return AssertionCommandResponse(
                assertion_id=assertion_id,
                event=_event_response(event),
                state=repo.current_state(assertion_id),
            )
        except Exception as exc:  # pragma: no cover - defensive mapping
            _raise_domain_error(exc)


@router.post("/api/assertions/{assertion_id}/supersessions")
async def supersede_assertion(
    assertion_id: str,
    payload: AssertionSupersessionRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> AssertionCommandResponse:
    """Atomically create a successor assertion and supersede the predecessor."""
    reviewer = get_current_rebuild_operator_user(
        current_user=current_user,
        settings=get_settings(),
        request=request,
    )
    proposer_user = _resolve_proposer_user_from_token(payload.proposal_bearer_token, request)
    proposal_ctx = _authority_context(proposer_user.username, "proposer", request)
    determination_ctx = _authority_context(reviewer.username, "acceptor", request)
    successor = AssertionProposal(
        assertion_id=payload.successor_proposal.assertion_id,
        predicate_id=payload.successor_proposal.predicate_id,
        subject_id=payload.successor_proposal.subject_id,
        object_id=payload.successor_proposal.object_id,
        method_id=payload.successor_proposal.method_id,
        proposition=payload.successor_proposal.proposition,
        confidence_status=payload.successor_proposal.confidence_status,
        confidence_bp=payload.successor_proposal.confidence_bp,
        confidence_type=payload.successor_proposal.confidence_type,
        confidence_method=payload.successor_proposal.confidence_method,
        effective_from=payload.successor_proposal.effective_from,
        effective_to=payload.successor_proposal.effective_to,
    )
    command = SupersedeAtomicRequest(
        predecessor_id=assertion_id,
        successor_proposal=successor,
        proposal_ctx=proposal_ctx,
        determination_ctx=determination_ctx,
        expected_sequence=payload.expected_sequence,
        rationale=payload.rationale,
        accept_rationale=payload.accept_rationale,
    )
    with _assertion_repository_session() as session:
        _require_assertion_exists(session, assertion_id)
        repo = RelationshipAssertionRepository(session)
        try:
            _succ, _propose, _accept, supersede = repo.supersede_atomic(command)
            return AssertionCommandResponse(
                assertion_id=assertion_id,
                event=_event_response(supersede),
                state=repo.current_state(assertion_id),
            )
        except Exception as exc:  # pragma: no cover - defensive mapping
            _raise_domain_error(exc)


@router.get("/api/assertions/{assertion_id}")
async def get_assertion(
    assertion_id: str,
    known_at: Annotated[datetime | None, Query()] = None,
    effective_at: Annotated[datetime | None, Query()] = None,
) -> AssertionReadResponse:
    """Return a redacted assertion explanation as-of the requested bitemporal bounds."""
    with _assertion_repository_session() as session:
        repo = RelationshipAssertionRepository(session)
        as_of = repo.get_as_of(
            assertion_id,
            known_at=(known_at or datetime.now(tz=_UTC)),
            effective_at=effective_at,
        )
        if as_of is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"unknown assertion_id: {assertion_id}")
        return _assertion_read_response(as_of, session)


@router.get("/api/assertions/{assertion_id}/history")
async def get_assertion_history(
    assertion_id: str,
    known_at: Annotated[datetime | None, Query()] = None,
    effective_at: Annotated[datetime | None, Query()] = None,
) -> AssertionHistoryResponse:
    """Return immutable ordered lifecycle events with bitemporal bounds."""
    with _assertion_repository_session() as session:
        repo = RelationshipAssertionRepository(session)
        as_of = repo.get_as_of(
            assertion_id,
            known_at=(known_at or datetime.now(tz=_UTC)),
            effective_at=effective_at,
        )
        if as_of is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"unknown assertion_id: {assertion_id}")
        events = [_public_event_response(event) for event in _require_assertion_events(as_of)]
        return AssertionHistoryResponse(
            assertion_id=assertion_id,
            effective_from=as_of.assertion.effective_from,
            effective_to=as_of.assertion.effective_to,
            recorded_at=as_of.assertion.recorded_at,
            state=as_of.state,
            known_at=as_of.known_at,
            effective_at=as_of.effective_at,
            events=events,
        )
