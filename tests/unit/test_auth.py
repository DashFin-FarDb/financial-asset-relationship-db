"""Comprehensive unit tests for api/auth.py authentication module.

This module provides extensive test coverage for:
- UserRepository CRUD operations
- Password hashing and verification
- JWT token creation and validation
- User authentication flow
- Environment variable seeding
- Edge cases and error conditions
- Security validations
"""

from __future__ import annotations

import importlib
import os
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

import api.auth as auth_module


@pytest.fixture
def clean_auth_env(monkeypatch):
    """
    Prepare a clean authentication environment for tests by setting a test SECRET_KEY and clearing admin-related environment variables.

    Reloads the authentication module to apply the environment changes before yielding control to the test and reloads it again after the test completes.
    """
    # Set required SECRET_KEY
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-min-32-chars-long-for-security")
    # Clear any admin credentials
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("ADMIN_FULL_NAME", raising=False)
    monkeypatch.delenv("ADMIN_DISABLED", raising=False)

    # Reload the module to pick up new environment
    importlib.reload(auth_module)
    yield
    importlib.reload(auth_module)


class TestIsTruthyHelper:
    """Test the _is_truthy helper function."""

    @staticmethod
    def test_is_truthy_with_true_string():
        """Test that 'true' string returns True."""
        assert auth_module._is_truthy("true") is True
        assert auth_module._is_truthy("TRUE") is True
        assert auth_module._is_truthy("True") is True

    @staticmethod
    def test_is_truthy_with_one():
        """Test that '1' returns True."""
        assert auth_module._is_truthy("1") is True

    @staticmethod
    def test_is_truthy_with_yes():
        """Test that 'yes' returns True."""
        assert auth_module._is_truthy("yes") is True
        assert auth_module._is_truthy("YES") is True
        assert auth_module._is_truthy("Yes") is True

    @staticmethod
    def test_is_truthy_with_on():
        """Test that 'on' returns True."""
        assert auth_module._is_truthy("on") is True
        assert auth_module._is_truthy("ON") is True

    @staticmethod
    def test_is_truthy_with_false_string():
        """Test that 'false' string returns False."""
        assert auth_module._is_truthy("false") is False
        assert auth_module._is_truthy("FALSE") is False

    @staticmethod
    def test_is_truthy_with_zero():
        """Test that '0' returns False."""
        assert auth_module._is_truthy("0") is False

    @staticmethod
    def test_is_truthy_with_no():
        """Test that 'no' returns False."""
        assert auth_module._is_truthy("no") is False
        assert auth_module._is_truthy("NO") is False

    @staticmethod
    def test_is_truthy_with_none():
        """Test that None returns False."""
        assert auth_module._is_truthy(None) is False

    @staticmethod
    def test_is_truthy_with_empty_string():
        """
        Check _is_truthy behavior for an empty string input.

        Asserts that the helper returns False when given an empty string.
        """
        assert auth_module._is_truthy("") is False

    @staticmethod
    def test_is_truthy_with_random_string():
        """Test that unrecognized strings return False."""
        assert auth_module._is_truthy("random") is False
        assert auth_module._is_truthy("maybe") is False


class TestPasswordHashing:
    """Test password hashing and verification functions."""

    @staticmethod
    def test_hash_password_creates_hash():
        """Test that password hashing creates a non-empty hash."""
        password = "test_password_123"
        hashed = auth_module.get_password_hash(password)
        assert hashed is not None
        assert len(hashed) > 0
        assert hashed != password  # Hash should not equal plaintext

    @staticmethod
    def test_verify_password_with_correct_password():
        """Test password verification with correct password."""
        password = "correct_password"
        hashed = auth_module.get_password_hash(password)
        assert auth_module.verify_password(password, hashed) is True

    @staticmethod
    def test_verify_password_with_incorrect_password():
        """Test password verification with incorrect password."""
        correct_password = "correct_password"
        wrong_password = "wrong_password"
        hashed = auth_module.get_password_hash(correct_password)
        assert auth_module.verify_password(wrong_password, hashed) is False

    @staticmethod
    def test_hash_password_different_for_same_input():
        """Test that hashing the same password twice produces different hashes."""
        password = "test_password"
        hash1 = auth_module.get_password_hash(password)
        hash2 = auth_module.get_password_hash(password)
        # Hashes should be different due to salt
        assert hash1 != hash2

    @staticmethod
    def test_verify_password_with_empty_password():
        """Test password verification with empty password."""
        password = ""
        hashed = auth_module.get_password_hash(password)
        assert auth_module.verify_password(password, hashed) is True

    @staticmethod
    def test_hash_special_characters():
        """Test password hashing with special characters."""
        password = "p@ssw0rd!#$%^&*()"
        hashed = auth_module.get_password_hash(password)
        assert auth_module.verify_password(password, hashed) is True


class TestUserRepository:
    """Test UserRepository database operations."""

    @staticmethod
    @patch("api.auth.fetch_one")
    def test_get_user_existing(mock_fetch):
        """Test retrieving an existing user."""
        mock_fetch.return_value = {
            "username": "testuser",
            "email": "test@example.com",
            "full_name": "Test User",
            "hashed_password": "hashed",
            "disabled": 0,
        }

        repo = auth_module.UserRepository()
        user = repo.get_user("testuser")

        assert user is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.disabled is False

    @staticmethod
    @patch("api.auth.fetch_one")
    def test_get_user_nonexistent(mock_fetch):
        """Test retrieving a non-existent user returns None."""
        mock_fetch.return_value = None

        repo = auth_module.UserRepository()
        user = repo.get_user("nonexistent")

        assert user is None

    @staticmethod
    @patch("api.auth.fetch_value")
    def test_has_users_returns_true(mock_fetch_value):
        """Test has_users returns True when users exist."""
        mock_fetch_value.return_value = 1

        repo = auth_module.UserRepository()
        assert repo.has_users() is True

    @staticmethod
    @patch("api.auth.fetch_value")
    def test_has_users_returns_false(mock_fetch_value):
        """Test has_users returns False when no users exist."""
        mock_fetch_value.return_value = None

        repo = auth_module.UserRepository()
        assert repo.has_users() is False

    @staticmethod
    @patch("api.auth.execute")
    def test_create_or_update_user_minimal_fields(mock_execute):
        """Test creating a user with only required fields."""
        repo = auth_module.UserRepository()
        repo.create_or_update_user(username="testuser", hashed_password="hashed_pwd")

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        params = call_args[1]
        assert params[0] == "testuser"
        assert params[3] == "hashed_pwd"
        assert params[4] == 0  # disabled = False

    @staticmethod
    @patch("api.auth.execute")
    def test_create_or_update_user_all_fields(mock_execute):
        """Test creating a user with all fields populated."""
        repo = auth_module.UserRepository()
        repo.create_or_update_user(
            username="admin",
            hashed_password="hashed_pwd",
            user_email="admin@example.com",
            user_full_name="Admin User",
            is_disabled=True,
        )

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        params = call_args[1]
        assert params[0] == "admin"
        assert params[1] == "admin@example.com"
        assert params[2] == "Admin User"
        assert params[3] == "hashed_pwd"
        assert params[4] == 1  # disabled = True


class TestSeedCredentialsFromEnv:
    """Test environment-based credential seeding."""

    @staticmethod
    @patch("api.auth.UserRepository.create_or_update_user")
    def test_seed_with_username_and_password(mock_create):
        """Test seeding creates user when credentials are provided."""
        with patch.dict(
            os.environ, {"ADMIN_USERNAME": "admin", "ADMIN_PASSWORD": "admin123"}
        ):
            repo = MagicMock()
            auth_module._seed_credentials_from_env(repo)
            repo.create_or_update_user.assert_called_once()

    @staticmethod
    @patch("api.auth.UserRepository.create_or_update_user")
    def test_seed_with_missing_username(mock_create):
        """Test seeding does nothing when username is missing."""
        with patch.dict(os.environ, {"ADMIN_PASSWORD": "admin123"}, clear=True):
            repo = MagicMock()
            auth_module._seed_credentials_from_env(repo)
            repo.create_or_update_user.assert_not_called()

    @staticmethod
    @patch("api.auth.UserRepository.create_or_update_user")
    def test_seed_with_missing_password(mock_create):
        """Test seeding does nothing when password is missing."""
        with patch.dict(os.environ, {"ADMIN_USERNAME": "admin"}, clear=True):
            repo = MagicMock()
            auth_module._seed_credentials_from_env(repo)
            repo.create_or_update_user.assert_not_called()

    @staticmethod
    @patch("api.auth.UserRepository.create_or_update_user")
    def test_seed_with_all_optional_fields(mock_create):
        """Test seeding includes all optional fields when provided."""
        with patch.dict(
            os.environ,
            {
                "ADMIN_USERNAME": "admin",
                "ADMIN_PASSWORD": "admin123",
                "ADMIN_EMAIL": "admin@example.com",
                "ADMIN_FULL_NAME": "Administrator",
                "ADMIN_DISABLED": "true",
            },
        ):
            repo = MagicMock()
            auth_module._seed_credentials_from_env(repo)
            repo.create_or_update_user.assert_called_once()
            call_kwargs = repo.create_or_update_user.call_args[1]
            assert call_kwargs["email"] == "admin@example.com"
            assert call_kwargs["full_name"] == "Administrator"
            assert call_kwargs["disabled"] is True


class TestAuthenticateUser:
    """Test user authentication flow."""

    @staticmethod
    @patch("api.auth.get_user")
    @patch("api.auth.verify_password")
    def test_authenticate_valid_credentials(mock_verify, mock_get_user):
        """Test authentication with valid credentials."""
        mock_user = auth_module.UserInDB(
            username="testuser", hashed_password="hashed", disabled=False
        )
        mock_get_user.return_value = mock_user
        mock_verify.return_value = True

        result = auth_module.authenticate_user("testuser", "password")
        assert result == mock_user

    @staticmethod
    @patch("api.auth.get_user")
    def test_authenticate_nonexistent_user(mock_get_user):
        """Test authentication with non-existent user."""
        mock_get_user.return_value = None

        result = auth_module.authenticate_user("nonexistent", "password")
        assert result is False

    @staticmethod
    @patch("api.auth.get_user")
    @patch("api.auth.verify_password")
    def test_authenticate_wrong_password(mock_verify, mock_get_user):
        """Test authentication with wrong password."""
        mock_user = auth_module.UserInDB(
            username="testuser", hashed_password="hashed", disabled=False
        )
        mock_get_user.return_value = mock_user
        mock_verify.return_value = False

        result = auth_module.authenticate_user("testuser", "wrongpassword")
        assert result is False


class TestJWTTokens:
    """Test JWT token creation and validation."""

    @staticmethod
    def test_create_access_token_with_default_expiry():
        """Test creating token with default expiry."""
        data = {"sub": "testuser"}
        token = auth_module.create_access_token(data)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    @staticmethod
    def test_create_access_token_with_custom_expiry():
        """Test creating token with custom expiry."""
        data = {"sub": "testuser"}
        expires_delta = timedelta(minutes=60)
        token = auth_module.create_access_token(data, expires_delta)

        assert token is not None
        assert isinstance(token, str)

    @staticmethod
    def test_create_access_token_preserves_data():
        """Test that token preserves original data."""
        import jwt

        data = {"sub": "testuser", "role": "admin"}
        token = auth_module.create_access_token(data)

        decoded = jwt.decode(
            token, auth_module.SECRET_KEY, algorithms=[auth_module.ALGORITHM]
        )
        assert decoded["sub"] == "testuser"
        assert decoded["role"] == "admin"
        assert "exp" in decoded


class TestGetCurrentUser:
    """Test JWT-based user retrieval."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_get_current_user_valid_token():
        """Test getting current user with valid token."""
        data = {"sub": "testuser"}
        token = auth_module.create_access_token(data)

        with patch("api.auth.get_user") as mock_get_user:
            mock_user = auth_module.UserInDB(
                username="testuser", hashed_password="hashed", disabled=False
            )
            mock_get_user.return_value = mock_user

            user = await auth_module.get_current_user(token)
            assert user == mock_user

    @staticmethod
    @pytest.mark.asyncio
    async def test_get_current_user_missing_subject():
        """Test error when token is missing subject claim."""
        data = {}  # No 'sub'
        token = auth_module.create_access_token(data)

        with pytest.raises(HTTPException) as exc_info:
            await auth_module.get_current_user(token)

        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail

    @staticmethod
    @pytest.mark.asyncio
    async def test_get_current_user_expired_token():
        """Test error with expired token."""
        data = {"sub": "testuser"}
        # Create token with negative expiry
        token = auth_module.create_access_token(data, timedelta(seconds=-10))

        with pytest.raises(HTTPException) as exc_info:
            await auth_module.get_current_user(token)

        assert exc_info.value.status_code == 401
        assert "Token has expired" in exc_info.value.detail

    @staticmethod
    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token():
        """Test error with malformed token."""
        invalid_token = "invalid.token.string"

        with pytest.raises(HTTPException) as exc_info:
            await auth_module.get_current_user(invalid_token)

        assert exc_info.value.status_code == 401

    @staticmethod
    @pytest.mark.asyncio
    async def test_get_current_user_nonexistent_user():
        """Test error when token user doesn't exist in database."""
        data = {"sub": "nonexistent"}
        token = auth_module.create_access_token(data)

        with patch("api.auth.get_user") as mock_get_user:
            mock_get_user.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await auth_module.get_current_user(token)

            assert exc_info.value.status_code == 401


class TestGetCurrentActiveUser:
    """Test active user validation."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_get_active_user_when_enabled():
        """Test getting active user when account is enabled."""
        mock_user = auth_module.User(
            username="testuser", hashed_password="hashed", disabled=False
        )

        result = await auth_module.get_current_active_user(mock_user)
        assert result == mock_user

    @staticmethod
    @pytest.mark.asyncio
    async def test_get_active_user_when_disabled():
        """Test error when user account is disabled."""
        mock_user = auth_module.User(
            username="disabled_user", hashed_password="hashed", disabled=True
        )

        with pytest.raises(HTTPException) as exc_info:
            await auth_module.get_current_active_user(mock_user)

        assert exc_info.value.status_code == 400
        assert "Inactive user" in exc_info.value.detail


class TestModuleInitialization:
    """Test module-level initialization and configuration."""

    @staticmethod
    def test_secret_key_env_required():
        """Test that SECRET_KEY environment variable is required."""
        # This is tested by the fixture setup, but we verify the constant exists
        assert auth_module.SECRET_KEY is not None
        assert len(auth_module.SECRET_KEY) > 0

    @staticmethod
    def test_algorithm_is_hs256():
        """Test that ALGORITHM is set to HS256."""
        assert auth_module.ALGORITHM == "HS256"

    @staticmethod
    def test_token_expire_minutes_set():
        """Test that ACCESS_TOKEN_EXPIRE_MINUTES is configured."""
        assert auth_module.ACCESS_TOKEN_EXPIRE_MINUTES > 0
        assert isinstance(auth_module.ACCESS_TOKEN_EXPIRE_MINUTES, int)
