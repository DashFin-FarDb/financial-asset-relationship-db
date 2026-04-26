"""Authentication API routes."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from ..auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    Token,
    User,
    authenticate_user,
    create_access_token,
    get_current_active_user,
)
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
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires,
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
    return UserPublic.model_validate(current_user.model_dump())
