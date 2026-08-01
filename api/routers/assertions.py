"""Governed assertion command and explanation API routes."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.data.database import create_engine_from_url, create_session_factory, init_db
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
    ConcurrencyConflict,
    IllegalTransition,
    UnauthorizedTransition,
    ValidationError,
)
from src.governance.relationship_assertion_contract import CONTRACT_VERSION

from ..assertion_models import (
    AssertionCommandResponse,
    AssertionDecisionRequest,
    AssertionEventResponse,
    AssertionEvidenceMetadataResponse,
    AssertionHistoryResponse,
    AssertionProposalRequest,
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
    GraphPersistenceNonDurableError,
    GraphPersistenceNotConfiguredError,
    get_graph_lifecycle_settings,
    resolve_durable_graph_persistence_url,
    resolve_hosted_graph_database_url,
)

router = APIRouter()
_UTC = timezone.utc


def _authority_context(actor_id: str, role: str, request: Request) -> AuthorityContext:
    correlation = request.headers.get("x-correlation-id")
    return AuthorityContext(
        actor_id=actor_id,
        roles=frozenset({role}),  # type: ignore[arg-type]
        policy_version=CONTRACT_VERSION,
        correlation_id=correlation,
    )


def _event_response(event: AssertionEvent) -> AssertionEventResponse:
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


def _raise_domain_error(exc: Exception) -> None:
    if isinstance(exc, ConcurrencyConflict):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if isinstance(exc, UnauthorizedTransition):
        detail = str(exc)
        if "proposer of record" in detail or "must differ from the assertion proposer" in detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail) from exc
    if isinstance(exc, ValidationError):
        detail = str(exc)
        if "unknown assertion_id" in detail or "unknown or eventless assertion_id" in detail:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail) from exc
    if isinstance(exc, IllegalTransition):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@contextmanager
def _assertion_repository_session() -> Iterator[Session]:
    settings = get_graph_lifecycle_settings()
    engine = None
    try:
        hosted_url = resolve_hosted_graph_database_url(settings)
        fallback_url = getattr(settings, "database_url", None)
        persistence_url = resolve_durable_graph_persistence_url(hosted_url or fallback_url)
        engine = create_engine_from_url(persistence_url)
        init_db(engine)
        session_factory = create_session_factory(engine)
        with session_scope(session_factory) as session:
            yield session
    except HTTPException:
        raise
    except (GraphPersistenceNotConfiguredError, GraphPersistenceNonDurableError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph persistence database not configured",
        ) from exc
    finally:
        if engine is not None:
            engine.dispose()


def _assertion_evidence(
    as_of: AssertionAsOf,
    repo: RelationshipAssertionRepository,
) -> list[AssertionEvidenceMetadataResponse]:
    evidence_by_id = {
        item.evidence_id: item
        for item in repo.load_evidence_by_ids([link.evidence_id for link in as_of.evidence_links])
    }
    rows: list[AssertionEvidenceMetadataResponse] = []
    for link in as_of.evidence_links:
        evidence = evidence_by_id.get(link.evidence_id)
        if evidence is None:
            rows.append(
                AssertionEvidenceMetadataResponse(
                    evidence_id=link.evidence_id,
                    polarity=link.polarity,
                    visibility="restricted",
                    redacted=True,
                )
            )
            continue
        is_public = evidence.visibility == "public"
        rows.append(
            AssertionEvidenceMetadataResponse(
                evidence_id=evidence.evidence_id,
                polarity=link.polarity,
                visibility=evidence.visibility,
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
        )
    return rows


def _assertion_read_response(
    as_of: AssertionAsOf,
    repo: RelationshipAssertionRepository,
) -> AssertionReadResponse:
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
        sequence=as_of.events[-1].sequence,
        proposer_actor_id=as_of.events[0].actor_id,
        evidence=_assertion_evidence(as_of, repo),
    )


def _resolve_proposer_user_from_token(token: str, request: Request) -> User:
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


@router.post("/api/assertions", response_model=AssertionCommandResponse)
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
            existed = repo.max_sequence(payload.assertion_id) > 0
            _assertion, event = repo.propose(proposal, ctx)
            return AssertionCommandResponse(
                assertion_id=payload.assertion_id,
                event=_event_response(event),
                state=repo.current_state(payload.assertion_id),
                idempotent_reuse=existed,
            )
        except Exception as exc:  # pragma: no cover - defensive mapping
            _raise_domain_error(exc)
            raise


@router.post("/api/assertions/{assertion_id}/decisions", response_model=AssertionCommandResponse)
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
        reviewer = get_current_rebuild_operator_user(  # type: ignore[arg-type]
            current_user=current_user,
            settings=get_settings(),
        )
        role_by_state = {
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
            raise


@router.post("/api/assertions/{assertion_id}/supersessions", response_model=AssertionCommandResponse)
async def supersede_assertion(
    assertion_id: str,
    payload: AssertionSupersessionRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> AssertionCommandResponse:
    """Atomically create a successor assertion and supersede the predecessor."""
    reviewer = get_current_rebuild_operator_user(  # type: ignore[arg-type]
        current_user=current_user,
        settings=get_settings(),
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
            raise


@router.get("/api/assertions/{assertion_id}", response_model=AssertionReadResponse)
async def get_assertion(
    assertion_id: str,
    known_at: datetime | None = Query(default=None),
    effective_at: datetime | None = Query(default=None),
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
        return _assertion_read_response(as_of, repo)


@router.get("/api/assertions/{assertion_id}/history", response_model=AssertionHistoryResponse)
async def get_assertion_history(
    assertion_id: str,
    known_at: datetime | None = Query(default=None),
    effective_at: datetime | None = Query(default=None),
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
        events = [_event_response(event) for event in as_of.events]
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
