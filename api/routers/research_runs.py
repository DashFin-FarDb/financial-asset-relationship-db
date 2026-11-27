"""REST API routes for immutable ResearchRun provenance records."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.config.settings import get_settings
from src.data.database import create_engine_from_url
from src.data.research_run_repository import (
    ResearchRunConflictError,
    ResearchRunNotFoundError,
    ResearchRunRepository,
)
from src.governance.research_run import ResearchRunCreate, ResearchRunRecord

from ..auth import User, get_current_active_user, require_roles
from ..metrics import record_research_run_created
from ..tenant_context import TenantContext, get_tenant_context

router = APIRouter(prefix="/api/research-runs", tags=["research-runs"])

_cached_url: str | None = None
_cached_repo: ResearchRunRepository | None = None


def _resolve_research_run_db_url() -> str:
    """Resolve the database URL used for ResearchRun persistence."""
    settings = get_settings()
    for candidate in (
        getattr(settings, "asset_graph_database_url", None),
        getattr(settings, "database_url", None),
    ):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return "sqlite:///:memory:"


def get_research_run_repository() -> ResearchRunRepository:
    """Return a cached ResearchRunRepository for the configured DB."""
    global _cached_url, _cached_repo
    db_url = _resolve_research_run_db_url()
    if _cached_repo is not None and _cached_url == db_url:
        return _cached_repo
    engine = create_engine_from_url(db_url)
    repo = ResearchRunRepository(engine)
    if db_url.startswith("sqlite"):
        repo.ensure_sqlite_schema()
    _cached_url = db_url
    _cached_repo = repo
    return repo


class ResearchRunCreateRequest(BaseModel):
    """Request body for POST /api/research-runs."""

    model_config = ConfigDict(extra="forbid")

    run_id: str | None = Field(default=None, min_length=1, max_length=128)
    domain_id: str = Field(min_length=1, max_length=128)
    method_id: str = Field(min_length=1, max_length=128)
    input_digest_sha256: str = Field(min_length=64, max_length=64)
    parameters: dict[str, Any] = Field(default_factory=dict)


class ResearchRunResponse(BaseModel):
    """Serialized immutable ResearchRun record."""

    run_id: str
    contract_version: str
    domain_id: str
    method_id: str
    input_digest_sha256: str
    parameters: dict[str, Any]
    actor_id: str
    tenant_id: str
    created_at: str
    canonical_digest: str
    linked_assertion_ids: list[str] = Field(default_factory=list)


class ResearchRunListResponse(BaseModel):
    """Paginated list of ResearchRun records."""

    items: list[ResearchRunResponse]
    count: int
    total: int
    has_more: bool


class LinkAssertionRequest(BaseModel):
    """Request body for linking an assertion ID to a ResearchRun."""

    model_config = ConfigDict(extra="forbid")

    assertion_id: str = Field(min_length=1, max_length=128)


def _to_response(record: ResearchRunRecord, linked: list[str] | None = None) -> ResearchRunResponse:
    """Convert a ResearchRunRecord to its API response model."""
    return ResearchRunResponse(
        run_id=record.run_id,
        contract_version=record.contract_version,
        domain_id=record.domain_id,
        method_id=record.method_id,
        input_digest_sha256=record.input_digest_sha256,
        parameters=record.parameters,
        actor_id=record.actor_id,
        tenant_id=record.tenant_id,
        created_at=record.created_at,
        canonical_digest=record.canonical_digest,
        linked_assertion_ids=linked if linked is not None else [],
    )


@router.post("", response_model=ResearchRunResponse, status_code=status.HTTP_201_CREATED)
async def create_research_run(
    body: ResearchRunCreateRequest,
    current_user: Annotated[User, Depends(require_roles("analyst", "operator", "admin"))],
    tenant_ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    repo: Annotated[ResearchRunRepository, Depends(get_research_run_repository)],
) -> ResearchRunResponse:
    """Record an immutable ResearchRun provenance entry."""
    kwargs: dict[str, Any] = {
        "domain_id": body.domain_id,
        "method_id": body.method_id,
        "input_digest_sha256": body.input_digest_sha256,
        "parameters": body.parameters,
        "actor_id": current_user.username,
        "tenant_id": tenant_ctx.tenant_id,
    }
    if body.run_id is not None:
        kwargs["run_id"] = body.run_id

    try:
        payload = ResearchRunCreate(**kwargs)
        record = repo.create_run(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ResearchRunConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    record_research_run_created(record.domain_id)
    return _to_response(record, linked=repo.list_linked_assertions(record.run_id, tenant_id=record.tenant_id))


@router.get("", response_model=ResearchRunListResponse)
async def list_research_runs(
    _current_user: Annotated[User, Depends(get_current_active_user)],
    tenant_ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    repo: Annotated[ResearchRunRepository, Depends(get_research_run_repository)],
    domain_id: Annotated[str | None, Query(max_length=128)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ResearchRunListResponse:
    """List immutable ResearchRun records scoped to the caller's tenant."""
    tenant_id = tenant_ctx.tenant_id
    records, total = repo.list_runs(domain_id=domain_id, tenant_id=tenant_id, limit=limit, offset=offset)
    items = [_to_response(rec, linked=repo.list_linked_assertions(rec.run_id, tenant_id=tenant_id)) for rec in records]
    return ResearchRunListResponse(
        items=items,
        count=len(items),
        total=total,
        has_more=(offset + len(items)) < total,
    )


@router.get("/{run_id}", response_model=ResearchRunResponse)
async def get_research_run(
    run_id: str,
    _current_user: Annotated[User, Depends(get_current_active_user)],
    tenant_ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    repo: Annotated[ResearchRunRepository, Depends(get_research_run_repository)],
) -> ResearchRunResponse:
    """Fetch a single immutable ResearchRun by ID within the caller's tenant."""
    tenant_id = tenant_ctx.tenant_id
    record = repo.get_run(run_id, tenant_id=tenant_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ResearchRun not found")
    return _to_response(record, linked=repo.list_linked_assertions(record.run_id, tenant_id=tenant_id))


@router.post("/{run_id}/assertions", response_model=ResearchRunResponse, status_code=status.HTTP_201_CREATED)
async def link_assertion_to_research_run(
    run_id: str,
    body: LinkAssertionRequest,
    _current_user: Annotated[User, Depends(require_roles("analyst", "operator", "admin"))],
    tenant_ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    repo: Annotated[ResearchRunRepository, Depends(get_research_run_repository)],
) -> ResearchRunResponse:
    """Immutably associate a proposed assertion ID with an existing ResearchRun."""
    tenant_id = tenant_ctx.tenant_id
    try:
        repo.link_assertion(run_id, body.assertion_id, tenant_id=tenant_id)
    except ResearchRunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    record = repo.get_run(run_id, tenant_id=tenant_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ResearchRun not found")
    return _to_response(record, linked=repo.list_linked_assertions(record.run_id, tenant_id=tenant_id))
