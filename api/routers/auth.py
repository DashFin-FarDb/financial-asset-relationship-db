"""Authentication API routes."""

import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from src.config.settings import get_settings

from ..auth import (
    _SECURITY_AUDIT_LOGIN_FAILURE,
    _SECURITY_AUDIT_LOGIN_SUCCESS,
    _SECURITY_AUDIT_LOGOUT,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    Token,
    User,
    _log_security_event,
    _SecurityAuditEvent,
    authenticate_user,
    create_access_token,
    get_current_active_user,
    oauth2_scheme,
    resolve_user_roles,
    resolve_user_tenant,
    revoke_access_token,
)
from ..metrics import record_auth_login, record_auth_token_revocation
from ..models import UserPublic
from ..rate_limit import limiter

router = APIRouter()


@router.post("/token", response_model=Token)
@limiter.limit("5/minute")
async def login_for_access_token(
    request: Request,  # Required by slowapi for rate-limit key extraction.
    form_data: OAuth2PasswordRequestForm = Depends(),  # noqa: B008
) -> Token:
    """
    Issue a JWT access token for valid user credentials.

    Parameters:
        request (Request): Included so slowapi can extract the rate-limit key for this request.
        form_data (OAuth2PasswordRequestForm): OAuth2 password form containing `username` and `password`.

    Returns:
        Token: A `Token` object containing the JWT in `access_token` and `token_type` set to "bearer".
    """
    user = authenticate_user(form_data.username, form_data.password)
    if user is None or user is False:
        record_auth_login("failure")
        _log_security_event(
            _SecurityAuditEvent(
                event_slug=_SECURITY_AUDIT_LOGIN_FAILURE,
                attempted_username=form_data.username,
                request=request,
                metadata={"rate_limit_policy": "5/minute"},
                level=logging.WARNING,
            )
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    auth_settings = get_settings()
    user_roles = sorted(resolve_user_roles(user.username, auth_settings))  # type: ignore[union-attr]
    user_tenant = resolve_user_tenant(user.username, auth_settings)  # type: ignore[union-attr]
    access_token = create_access_token(
        data={"sub": user.username, "roles": user_roles, "tenant_id": user_tenant},  # type: ignore[union-attr]
        expires_delta=access_token_expires,
    )
    record_auth_login("success")
    _log_security_event(
        _SecurityAuditEvent(
            event_slug=_SECURITY_AUDIT_LOGIN_SUCCESS,
            username=user.username,  # type: ignore[union-attr]
            request=request,
            metadata={"rate_limit_policy": "5/minute"},
            level=logging.INFO,
        )
    )
    return Token(access_token=access_token, token_type="bearer")


@router.get("/api/users/me", response_model=UserPublic)
@limiter.limit("10/minute")
async def read_users_me(
    request: Request,  # Required by slowapi for rate-limit key extraction.
    current_user: User = Depends(get_current_active_user),  # noqa: B008
) -> UserPublic:
    """
    Retrieve the authenticated active user as a public response model.

    Parameters:
        request (Request): Included for rate-limit key extraction by the request middleware.
        current_user (User): The authenticated active user resolved by dependency injection.

    Returns:
        UserPublic: Public user profile without credential-bearing fields.
    """
    # Defense in depth: current_user may be a UserInDB at runtime.
    return UserPublic.model_validate(current_user.model_dump(exclude={"hashed_password"}))


@router.post("/api/auth/logout")
@limiter.limit("20/minute")
async def logout_current_token(
    request: Request,  # Required by slowapi for rate-limit key extraction.
    token: str = Depends(oauth2_scheme),  # noqa: B008
    current_user: User = Depends(get_current_active_user),  # noqa: B008
) -> dict[str, str]:
    """Revoke the caller's active JWT access token via its ``jti`` claim."""
    revoke_access_token(token)
    record_auth_token_revocation()
    _log_security_event(
        _SecurityAuditEvent(
            event_slug=_SECURITY_AUDIT_LOGOUT,
            username=current_user.username,
            request=request,
            metadata={"reason": "user_logout"},
            level=logging.INFO,
        )
    )
    return {"status": "logged_out"}
