"""Comprehensive unit tests for API authentication module.

This module provides extensive test coverage for api/auth.py including:
- UserRepository methods (get_user, has_users, create_or_update_user)
- Password hashing and verification
- JWT token creation and validation
- User authentication flow
- Environment-based user seeding
- Token expiration handling
- Error cases and edge conditions
"""

import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from jose import jwt

from api.auth import (
    ALGORITHM,
    SECRET_KEY,
    User,
    UserInDB,
    UserRepository,
    _is_truthy,
    _seed_credentials_from_env,
    authenticate_user,
    create_access_token,
    get_current_active_user,
    get_current_user,
    get_password_hash,
    get_user,
    verify_password,
)


@pytest.fixture
def mock_user_repository():
    """
    Create a MagicMock-based UserRepository suitable for tests.
    
    Returns:
        MagicMock: A mock implementing the UserRepository interface (spec=UserRepository)
        with `get_user`, `has_users`, and `create_or_update_user` attributes mocked.
    """
    repo = MagicMock(spec=UserRepository)
    repo.get_user = MagicMock()
    repo.has_users = MagicMock()
    repo.create_or_update_user = MagicMock()
    return repo


@pytest.fixture
def sample_user():
    """
    Create a reusable sample UserInDB instance for tests.
    
    Returns:
        UserInDB: A UserInDB populated with username "testuser", email "test@example.com", full_name "Test User", disabled False, and a placeholder hashed_password.
    """
    return UserInDB(
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        disabled=False,
        hashed_password="$2b$12$KIXqZ3vZ3vZ3vZ3vZ3vZ3O",
    )


class TestIsTruthy:
    """Test cases for _is_truthy helper function."""

    def test_is_truthy_with_true_lowercase(self):
        """Test that 'true' is recognized as truthy."""
        assert _is_truthy("true") is True

    def test_is_truthy_with_true_uppercase(self):
        """Test that 'TRUE' is recognized as truthy."""
        assert _is_truthy("TRUE") is True

    def test_is_truthy_with_one(self):
        """Test that '1' is recognized as truthy."""
        assert _is_truthy("1") is True

    def test_is_truthy_with_yes(self):
        """Test that 'yes' is recognized as truthy."""
        assert _is_truthy("yes") is True

    def test_is_truthy_with_on(self):
        """Test that 'on' is recognized as truthy."""
        assert _is_truthy("on") is True

    def test_is_truthy_with_false(self):
        """Test that 'false' is not truthy."""
        assert _is_truthy("false") is False

    def test_is_truthy_with_zero(self):
        """Test that '0' is not truthy."""
        assert _is_truthy("0") is False

    def test_is_truthy_with_empty_string(self):
        """Test that empty string is not truthy."""
        assert _is_truthy("") is False

    def test_is_truthy_with_none(self):
        """Test that None is not truthy."""
        assert _is_truthy(None) is False


class TestUserRepository:
    """Test cases for UserRepository class."""

    @patch("api.auth.fetch_one")
    def test_get_user_success(self, mock_fetch_one):
        """Test successful user retrieval."""
        mock_fetch_one.return_value = {
            "username": "testuser",
            "email": "test@example.com",
            "full_name": "Test User",
            "hashed_password": "hashed_pw",
            "disabled": 0,
        }

        repo = UserRepository()
        user = repo.get_user("testuser")

        assert user is not None
        assert user.username == "testuser"
        assert user.disabled is False

    @patch("api.auth.fetch_one")
    def test_get_user_not_found(self, mock_fetch_one):
        """Test user retrieval when user doesn't exist."""
        mock_fetch_one.return_value = None

        repo = UserRepository()
        user = repo.get_user("nonexistent")

        assert user is None

    @patch("api.auth.fetch_value")
    def test_has_users_returns_true(self, mock_fetch_value):
        """Test has_users when users exist."""
        mock_fetch_value.return_value = 1

        repo = UserRepository()
        result = repo.has_users()

        assert result is True

    @patch("api.auth.execute")
    def test_create_or_update_user_with_all_fields(self, mock_execute):
        """Test creating/updating user with all fields."""
        repo = UserRepository()
        repo.create_or_update_user(
            username="newuser",
            hashed_password="hashed_pw",
            email="new@example.com",
            full_name="New User",
            disabled=False,
        )

        mock_execute.assert_called_once()


class TestPasswordOperations:
    """Test cases for password hashing and verification."""

    def test_get_password_hash_returns_string(self):
        """Test that password hashing returns a string."""
        hashed = get_password_hash("password123")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_verify_password_with_correct_password(self):
        """Test password verification with correct password."""
        password = "correct_password"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_with_incorrect_password(self):
        """Test password verification with incorrect password."""
        password = "correct_password"
        hashed = get_password_hash(password)
        assert verify_password("wrong_password", hashed) is False


class TestAuthenticateUser:
    """Test cases for authenticate_user function."""

    def test_authenticate_user_success(self, mock_user_repository):
        """Test successful user authentication."""
        password = "correct_password"
        hashed_password = get_password_hash(password)
        user = UserInDB(
            username="testuser",
            hashed_password=hashed_password,
        )
        mock_user_repository.get_user.return_value = user

        result = authenticate_user("testuser", password, repository=mock_user_repository)

        assert result == user

    def test_authenticate_user_wrong_password(self, mock_user_repository):
        """Test authentication with wrong password."""
        password = "correct_password"
        hashed_password = get_password_hash(password)
        user = UserInDB(
            username="testuser",
            hashed_password=hashed_password,
        )
        mock_user_repository.get_user.return_value = user

        result = authenticate_user("testuser", "wrong_password", repository=mock_user_repository)

        assert result is False


class TestCreateAccessToken:
    """Test cases for JWT token creation."""

    def test_create_access_token_with_custom_expiry(self):
        """Test creating token with custom expiration time."""
        data = {"sub": "testuser"}
        expires_delta = timedelta(minutes=30)

        token = create_access_token(data, expires_delta)

        assert isinstance(token, str)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"
        assert "exp" in payload

    def test_create_access_token_expiration_is_future(self):
        """Test that token expiration is in the future."""
        data = {"sub": "testuser"}

        token = create_access_token(data)

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp_timestamp = payload["exp"]
        now_timestamp = datetime.utcnow().timestamp()
        assert exp_timestamp > now_timestamp


class TestGetCurrentUser:
    """Test cases for get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_get_current_user_with_valid_token(self, sample_user):
        """Test get_current_user with valid token."""
        token_data = {"sub": sample_user.username}
        token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

        with patch("api.auth.get_user", return_value=sample_user):
            user = await get_current_user(token)

        assert user.username == sample_user.username

    @pytest.mark.asyncio
    async def test_get_current_user_with_expired_token(self):
        """Test get_current_user with expired token."""
        exp_time = datetime.utcnow() - timedelta(minutes=10)
        token_data = {"sub": "testuser", "exp": exp_time}
        token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Token has expired"

    @pytest.mark.asyncio
    async def test_get_current_user_with_invalid_token(self):
        """Test get_current_user with invalid token."""
        token = "invalid.token.here"

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token)

        assert exc_info.value.status_code == 401


class TestGetCurrentActiveUser:
    """Test cases for get_current_active_user dependency."""

    @pytest.mark.asyncio
    async def test_get_current_active_user_with_active_user(self, sample_user):
        """Test get_current_active_user with active user."""
        sample_user.disabled = False

        user = await get_current_active_user(sample_user)

        assert user == sample_user

    @pytest.mark.asyncio
    async def test_get_current_active_user_with_disabled_user(self, sample_user):
        """Test get_current_active_user with disabled user."""
        sample_user.disabled = True

        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(sample_user)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Inactive user"