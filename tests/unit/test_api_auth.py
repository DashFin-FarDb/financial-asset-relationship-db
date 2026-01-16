"""
Comprehensive unit tests for api/auth.py module.

Tests cover:
- Password hashing and verification
- User authentication
- JWT token creation and validation
- User repository operations
- OAuth2 integration
- Error handling and edge cases
"""

import os
from datetime import timedelta
from unittest.mock import Mock, patch

import jwt
import pytest
from fastapi import HTTPException
from jwt import InvalidTokenError

from api.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    SECRET_KEY,
    UserRepository,
    authenticate_user,
    create_access_token,
    get_current_active_user,
    get_current_user,
    get_password_hash,
    get_user,
    verify_password,
)
from api.models import UserInDB


class TestPasswordHandling:
    """Test password hashing and verification functions."""

    def test_password_hash_generates_hash(self):
        """Test that password hashing generates a non-empty hash."""
        password = "test_password_123"
        hashed = get_password_hash(password)

        assert hashed is not None
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        assert hashed != password  # Hash should not equal plaintext

    def test_password_hash_is_deterministic_per_run(self):
        """Test that hashing same password twice produces different hashes (salt)."""
        password = "test_password_123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        # With salt, hashes should be different
        assert hash1 != hash2

    def test_verify_password_correct_password(self):
        """Test that correct password verification returns True."""
        password = "correct_password"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect_password(self):
        """Test that incorrect password verification returns False."""
        password = "correct_password"
        wrong_password = "wrong_password"
        hashed = get_password_hash(password)

        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_empty_password(self):
        """Test verification with empty password."""
        password = "test_password"
        hashed = get_password_hash(password)

        assert verify_password("", hashed) is False

    def test_verify_password_case_sensitive(self):
        """Test that password verification is case-sensitive."""
        password = "TestPassword"
        hashed = get_password_hash(password)

        assert verify_password("testpassword", hashed) is False
        assert verify_password("TESTPASSWORD", hashed) is False
        assert verify_password("TestPassword", hashed) is True


class TestUserRepository:
    """Test UserRepository database operations."""

    @patch("api.auth.fetch_one")
    def test_get_user_existing_user(self, mock_fetch_one):
        """Test retrieving an existing user."""
        mock_fetch_one.return_value = {
            "username": "testuser",
            "email": "test@example.com",
            "full_name": "Test User",
            "hashed_password": "hashed_pwd",
            "disabled": 0,
        }

        repo = UserRepository()
        user = repo.get_user("testuser")

        assert user is not None
        assert isinstance(user, UserInDB)
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.disabled is False

    @patch("api.auth.fetch_one")
    def test_get_user_nonexistent_user(self, mock_fetch_one):
        """Test retrieving a non-existent user returns None."""
        mock_fetch_one.return_value = None

        repo = UserRepository()
        user = repo.get_user("nonexistent")

        assert user is None

    @patch("api.auth.fetch_one")
    def test_get_user_disabled_user(self, mock_fetch_one):
        """Test retrieving a disabled user."""
        mock_fetch_one.return_value = {
            "username": "disabled_user",
            "email": "disabled@example.com",
            "full_name": "Disabled User",
            "hashed_password": "hashed_pwd",
            "disabled": 1,
        }

        repo = UserRepository()
        user = repo.get_user("disabled_user")

        assert user is not None
        assert user.disabled is True

    @patch("api.auth.fetch_value")
    def test_has_users_with_users(self, mock_fetch_value):
        """Test has_users returns True when users exist."""
        mock_fetch_value.return_value = 1

        repo = UserRepository()
        assert repo.has_users() is True

    @patch("api.auth.fetch_value")
    def test_has_users_without_users(self, mock_fetch_value):
        """Test has_users returns False when no users exist."""
        mock_fetch_value.return_value = None

        repo = UserRepository()
        assert repo.has_users() is False

    @patch("api.auth.execute")
    def test_create_or_update_user_new_user(self, mock_execute):
        """Test creating a new user."""
        repo = UserRepository()
        repo.create_or_update_user(
            username="newuser",
            hashed_password="hashed_pwd",
            user_email="new@example.com",
            user_full_name="New User",
            is_disabled=False,
        )

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "INSERT INTO user_credentials" in call_args[0]
        assert call_args[1][0] == "newuser"
        assert call_args[1][3] == "hashed_pwd"

    @patch("api.auth.execute")
    def test_create_or_update_user_disabled(self, mock_execute):
        """Test creating a disabled user."""
        repo = UserRepository()
        repo.create_or_update_user(
            username="disableduser", hashed_password="hashed_pwd", is_disabled=True
        )

        call_args = mock_execute.call_args[0]
        assert call_args[1][4] == 1  # disabled flag

    @patch("api.auth.execute")
    def test_create_or_update_user_minimal_fields(self, mock_execute):
        """Test creating user with only required fields."""
        repo = UserRepository()
        repo.create_or_update_user(username="minimaluser", hashed_password="hashed_pwd")

        call_args = mock_execute.call_args[0]
        assert call_args[1][0] == "minimaluser"
        assert call_args[1][1] is None  # email
        assert call_args[1][2] is None  # full_name


class TestAuthentication:
    """Test user authentication functions."""

    @patch("api.auth.get_user")
    @patch("api.auth.verify_password")
    def test_authenticate_user_success(self, mock_verify, mock_get_user):
        """Test successful user authentication."""
        mock_user = UserInDB(
            username="testuser", hashed_password="hashed_pwd", disabled=False
        )
        mock_get_user.return_value = mock_user
        mock_verify.return_value = True

        result = authenticate_user("testuser", "correct_password")

        assert result is not False
        assert isinstance(result, UserInDB)
        assert result.username == "testuser"

    @patch("api.auth.get_user")
    def test_authenticate_user_nonexistent(self, mock_get_user):
        """Test authentication with non-existent user."""
        mock_get_user.return_value = None

        result = authenticate_user("nonexistent", "password")

        assert result is False

    @patch("api.auth.get_user")
    @patch("api.auth.verify_password")
    def test_authenticate_user_wrong_password(self, mock_verify, mock_get_user):
        """Test authentication with wrong password."""
        mock_user = UserInDB(
            username="testuser", hashed_password="hashed_pwd", disabled=False
        )
        mock_get_user.return_value = mock_user
        mock_verify.return_value = False

        result = authenticate_user("testuser", "wrong_password")

        assert result is False

    @patch("api.auth.get_user")
    @patch("api.auth.verify_password")
    def test_authenticate_disabled_user(self, mock_verify, mock_get_user):
        """Test authentication of disabled user."""
        mock_user = UserInDB(
            username="testuser", hashed_password="hashed_pwd", disabled=True
        )
        mock_get_user.return_value = mock_user
        mock_verify.return_value = True

        # Authentication should succeed, but user will be disabled
        result = authenticate_user("testuser", "correct_password")

        assert isinstance(result, UserInDB)
        assert result.disabled is True


class TestJWTTokens:
    """Test JWT token creation and validation."""

    def test_create_access_token_basic(self):
        """Test creating a basic access token."""
        data = {"sub": "testuser"}
        token = create_access_token(data)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_with_expiry(self):
        """Test creating token with custom expiry."""
        data = {"sub": "testuser"}
        expires_delta = timedelta(minutes=15)
        token = create_access_token(data, expires_delta)

        # Decode to verify expiry was set
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload
        assert "sub" in payload
        assert payload["sub"] == "testuser"

    def test_create_access_token_includes_all_data(self):
        """Test that token includes all provided data."""
        data = {"sub": "testuser", "custom_field": "custom_value", "another_field": 123}
        token = create_access_token(data)

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"
        assert payload["custom_field"] == "custom_value"
        assert payload["another_field"] == 123

    def test_token_can_be_decoded(self):
        """Test that created token can be decoded with correct secret."""
        data = {"sub": "testuser"}
        token = create_access_token(data)

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"

    def test_token_cannot_be_decoded_with_wrong_secret(self):
        """Test that token cannot be decoded with wrong secret."""
        data = {"sub": "testuser"}
        token = create_access_token(data)

        with pytest.raises(InvalidTokenError):
            jwt.decode(token, "wrong_secret", algorithms=[ALGORITHM])

    def test_token_expiration(self):
        """Test that token includes expiration time."""
        data = {"sub": "testuser"}
        token = create_access_token(data, timedelta(minutes=30))

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload
        assert payload["exp"] > 0


class TestGetCurrentUser:
    """Test get_current_user dependency."""

    @patch("api.auth.get_user")
    async def test_get_current_user_valid_token(self, mock_get_user):
        """Test get_current_user with valid token."""
        mock_user = UserInDB(
            username="testuser", hashed_password="hashed_pwd", disabled=False
        )
        mock_get_user.return_value = mock_user

        # Create valid token
        token = create_access_token({"sub": "testuser"})

        user = await get_current_user(token)

        assert user is not None
        assert user.username == "testuser"

    async def test_get_current_user_invalid_token(self):
        """Test get_current_user with invalid token."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("invalid_token")

        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail

    async def test_get_current_user_expired_token(self):
        """Test get_current_user with expired token."""
        # Create token that expires immediately
        token = create_access_token({"sub": "testuser"}, timedelta(seconds=-1))

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token)

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    @patch("api.auth.get_user")
    async def test_get_current_user_no_username(self, mock_get_user):
        """Test get_current_user with token missing username."""
        token = create_access_token({"other_field": "value"})

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token)

        assert exc_info.value.status_code == 401

    @patch("api.auth.get_user")
    async def test_get_current_user_nonexistent_user(self, mock_get_user):
        """Test get_current_user when user doesn't exist in DB."""
        mock_get_user.return_value = None
        token = create_access_token({"sub": "nonexistent"})

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token)

        assert exc_info.value.status_code == 401


class TestGetCurrentActiveUser:
    """Test get_current_active_user dependency."""

    async def test_get_current_active_user_active(self):
        """Test getting active user."""
        mock_user = Mock()
        mock_user.disabled = False
        mock_user.username = "testuser"

        result = await get_current_active_user(mock_user)

        assert result == mock_user

    async def test_get_current_active_user_disabled(self):
        """Test that disabled user raises exception."""
        mock_user = Mock()
        mock_user.disabled = True
        mock_user.username = "testuser"

        with pytest.raises(HTTPException):
            await get_current_active_user(mock_user)

    def test_algorithm_is_hs256(self):
        """Test that ALGORITHM is set to HS256."""
        assert ALGORITHM == "HS256"

    def test_access_token_expire_minutes_is_set(self):
        """Test that ACCESS_TOKEN_EXPIRE_MINUTES is set."""
        assert ACCESS_TOKEN_EXPIRE_MINUTES is not None
        assert isinstance(ACCESS_TOKEN_EXPIRE_MINUTES, int)
        assert ACCESS_TOKEN_EXPIRE_MINUTES > 0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_username(self):
        """Test handling of empty username."""
        with patch("api.auth.fetch_one") as mock_fetch:
            mock_fetch.return_value = None
            repo = UserRepository()
            user = repo.get_user("")
            assert user is None

    def test_very_long_password(self):
        """Test hashing very long password."""
        long_password = "a" * 10000
        hashed = get_password_hash(long_password)

        assert hashed is not None
        assert verify_password(long_password, hashed) is True

    def test_special_characters_in_password(self):
        """Test password with special characters."""
        special_password = "p@$$w0rd!#%^&*()"
        hashed = get_password_hash(special_password)

        assert verify_password(special_password, hashed) is True

    def test_unicode_in_username(self):
        """Test handling unicode characters in username."""
        with patch("api.auth.fetch_one") as mock_fetch:
            mock_fetch.return_value = {
                "username": "用户",
                "email": "test@example.com",
                "full_name": "Unicode User",
                "hashed_password": "hashed",
                "disabled": 0,
            }
            repo = UserRepository()
            user = repo.get_user("用户")

            assert user is not None
            assert user.username == "用户"
