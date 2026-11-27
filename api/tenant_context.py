"""Tenant context resolution and cross-tenant boundary enforcement for FarDB APIs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from src.config.settings import Settings, get_settings

from .auth import User, get_current_active_user
from .metrics import record_auth_access_denied

DEFAULT_TENANT_ID = "default"
_TENANT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


@dataclass(frozen=True)
class TenantContext:
    """Verified tenant boundary bound to the current authenticated request."""

    tenant_id: str
    actor_id: str
    isolation_enforced: bool


def normalize_tenant_id(raw: str | None) -> str:
    """Normalize and validate a tenant identifier."""
    if raw is None:
        return DEFAULT_TENANT_ID
    cleaned = raw.strip().lower()
    if not cleaned or not _TENANT_ID_PATTERN.match(cleaned):
        raise ValueError(
            "Invalid tenant_id format: must be 1-64 lowercase alphanumeric, hyphen, or underscore characters"
        )
    return cleaned


def get_tenant_context(
    current_user: Annotated[User, Depends(get_current_active_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
) -> TenantContext:
    """Resolve and validate the request's TenantContext against the caller's bound tenant."""
    enforced = bool(getattr(settings, "tenant_isolation_enforced", False))
    raw_user_tenant = getattr(current_user, "tenant_id", None)
    if enforced and (not isinstance(raw_user_tenant, str) or not raw_user_tenant.strip()):
        record_auth_access_denied("tenant_boundary")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant context is required when tenant isolation is enforced.",
        )

    try:
        user_tenant = normalize_tenant_id(raw_user_tenant)
    except ValueError as exc:
        record_auth_access_denied("tenant_boundary")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    if x_tenant_id is not None:
        try:
            requested_tenant = normalize_tenant_id(x_tenant_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        if requested_tenant != user_tenant:
            record_auth_access_denied("tenant_boundary")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-tenant access denied.",
            )

    return TenantContext(
        tenant_id=user_tenant,
        actor_id=current_user.username,
        isolation_enforced=enforced,
    )


def require_tenant_access(target_tenant_id: str, context: TenantContext) -> None:
    """Reject cross-tenant resource access with HTTP 403 and emit a boundary denial metric."""
    try:
        normalized_target = normalize_tenant_id(target_tenant_id)
    except ValueError as exc:
        record_auth_access_denied("tenant_boundary")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    if normalized_target != context.tenant_id:
        record_auth_access_denied("tenant_boundary")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-tenant access denied.",
        )
