"""Comprehensive unit tests for api/auth.py authentication module.

This module provides extensive test coverage for:
- UserRepository operations (get_user, has_users, create_or_update_user)
- Password hashing and verification
- JWT token creation and validation
- User authentication flows
- Environment-based credential seeding
- Edge cases and error conditions
"""

import os
from datetime import timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from jose import JWTError, jwt

# Import the module under test
from api.auth import (
    ALGORITHM,
    SECRET_KEY,
    Token,
    TokenData,
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


@pytest.mark.unit
class TestIsTruthy:
    """Test suite for the _is_truthy helper function."""

    def test_is_truthy_with_true_string(self):
        """Test that 'true' string is recognized as truthy."""
        assert _is_truthy("true") is True
        assert _is_truthy("True") is True
        assert _is_truthy("TRUE") is True
        assert _is_truthy("TrUe") is True

    def test_is_truthy_with_one_string(self):
        """Test that '1' string is recognized as truthy."""
        assert _is_truthy("1") is True

    def test_is_truthy_with_yes_string(self):
        """Test that 'yes' string is recognized as truthy."""
        assert _is_truthy("yes") is True
        assert _is_truthy("Yes") is True
        assert _is_truthy("YES") is True

    def test_is_truthy_with_on_string(self):
        """Test that 'on' string is recognized as truthy."""
        assert _is_truthy("on") is True
        assert _is_truthy("On") is True
        assert _is_truthy("ON") is True

    def test_is_truthy_with_false_string(self):
        """Test that 'false' and other strings are not truthy."""
        assert _is_truthy("false") is False
        assert _is_truthy("False") is False
        assert _is_truthy("0") is False
        assert _is_truthy("no") is False
        assert _is_truthy("off") is False

    def test_is_truthy_with_empty_string(self):
        """Test that empty string is not truthy."""
        assert _is_truthy("") is False

    def test_is_truthy_with_none(self):
        """Test that None is not truthy."""
        assert _is_truthy(None) is False

    def test_is_truthy_with_whitespace(self):
        """Test that whitespace-only strings are not truthy."""
        assert _is_truthy("   ") is False

    def test_is_truthy_with_arbitrary_strings(self):
        """Test that arbitrary strings are not truthy."""
        assert _is_truthy("maybe") is False
        assert _is_truthy("enabled") is False
        assert _is_truthy("2") is False


@pytest.mark.unit
class TestPasswordHashing:
    """Test suite for password hashing and verification."""

    def test_get_password_hash_returns_string(self):
        """Test that password hashing returns a string."""
        password = "test_password_123"
        hashed = get_password_hash(password)
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_get_password_hash_produces_different_hashes(self):
        """Test that same password produces different hashes (due to salt)."""
        password = "test_password_123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        # Hashes should be different due to random salt
        assert hash1 != hash2

    def test_verify_password_with_correct_password(self):
        """Test password verification with correct password."""
        password = "correct_password"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_with_incorrect_password(self):
        """Test password verification with incorrect password."""
        password = "correct_password"
        wrong_password = "wrong_password"
        hashed = get_password_hash(password)
        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_with_empty_password(self):
        """Test password verification with empty password."""
        hashed = get_password_hash("some_password")
        assert verify_password("", hashed) is False

    def test_verify_password_case_sensitive(self):
        """Test that password verification is case-sensitive."""
        password = "TestPassword"
        hashed = get_password_hash(password)
        assert verify_password("testpassword", hashed) is False
        assert verify_password("TESTPASSWORD", hashed) is False

    def test_verify_password_with_special_characters(self):
        """Test password verification with special characters."""
        password = "p@ssw0rd!#$%^&*()"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_with_unicode_characters(self):
        """Test password verification with unicode characters."""
        password = "пароль密码🔐"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True


@pytest.mark.unit
class TestUserRepository:
    """Test suite for UserRepository class."""

    @patch("api.auth.fetch_one")
    def test_get_user_existing_user(self, mock_fetch_one):
        """Test retrieving an existing user."""
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
        assert isinstance(user, UserInDB)
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.hashed_password == "hashed_pw"
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
            "hashed_password": "hashed_pw",
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
            hashed_password="hashed_pw",
            email="new@example.com",
            full_name="New User",
            disabled=False,
        )

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args
        assert "newuser" in call_args[0][1]
        assert "new@example.com" in call_args[0][1]
        assert "New User" in call_args[0][1]
        assert "hashed_pw" in call_args[0][1]

    @patch("api.auth.execute")
    def test_create_or_update_user_with_disabled_true(self, mock_execute):
        """Test creating a disabled user."""
        repo = UserRepository()
        repo.create_or_update_user(username="disableduser", hashed_password="hashed_pw", disabled=True)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args
        # Check that disabled is set to 1
        assert call_args[0][1][-1] == 1

    @patch("api.auth.execute")
    def test_create_or_update_user_with_optional_fields_none(self, mock_execute):
        """Test creating a user with optional fields as None."""
        repo = UserRepository()
        repo.create_or_update_user(username="minimaluser", hashed_password="hashed_pw")

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args
        # email and full_name should be None
        assert call_args[0][1][1] is None  # email
        assert call_args[0][1][2] is None  # full_name


@pytest.mark.unit
class TestSeedCredentialsFromEnv:
    """Test suite for environment-based credential seeding."""

    @patch("api.auth.get_password_hash")
    @patch("api.auth.os.getenv")
    def test_seed_credentials_with_complete_env(self, mock_getenv, mock_hash):
        """Test seeding with complete environment variables."""
        mock_getenv.side_effect = lambda key, default=None: {
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD": "admin_pass",
            "ADMIN_EMAIL": "admin@example.com",
            "ADMIN_FULL_NAME": "Administrator",
            "ADMIN_DISABLED": "false",
        }.get(key, default)
        mock_hash.return_value = "hashed_admin_pass"

        mock_repo = Mock(spec=UserRepository)
        _seed_credentials_from_env(mock_repo)

        mock_repo.create_or_update_user.assert_called_once_with(
            username="admin",
            hashed_password="hashed_admin_pass",
            email="admin@example.com",
            full_name="Administrator",
            disabled=False,
        )

    @patch("api.auth.os.getenv")
    def test_seed_credentials_missing_username(self, mock_getenv):
        """Test seeding with missing username does nothing."""
        mock_getenv.side_effect = lambda key, default=None: {"ADMIN_PASSWORD": "admin_pass"}.get(key, default)

        mock_repo = Mock(spec=UserRepository)
        _seed_credentials_from_env(mock_repo)

        mock_repo.create_or_update_user.assert_not_called()

    @patch("api.auth.os.getenv")
    def test_seed_credentials_missing_password(self, mock_getenv):
        """Test seeding with missing password does nothing."""
        mock_getenv.side_effect = lambda key, default=None: {"ADMIN_USERNAME": "admin"}.get(key, default)

        mock_repo = Mock(spec=UserRepository)
        _seed_credentials_from_env(mock_repo)

        mock_repo.create_or_update_user.assert_not_called()

    @patch("api.auth.get_password_hash")
    @patch("api.auth.os.getenv")
    def test_seed_credentials_with_disabled_true(self, mock_getenv, mock_hash):
        """Test seeding with disabled flag set to true."""
        mock_getenv.side_effect = lambda key, default=None: {
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD": "admin_pass",
            "ADMIN_DISABLED": "true",
        }.get(key, default)
        mock_hash.return_value = "hashed_admin_pass"

        mock_repo = Mock(spec=UserRepository)
        _seed_credentials_from_env(mock_repo)

        call_kwargs = mock_repo.create_or_update_user.call_args[1]
        assert call_kwargs["disabled"] is True

    @patch("api.auth.get_password_hash")
    @patch("api.auth.os.getenv")
    def test_seed_credentials_with_disabled_variations(self, mock_getenv, mock_hash):
        """Test seeding with various disabled flag values."""
        for disabled_value in ["1", "yes", "on", "YES", "On"]:
            mock_getenv.side_effect = lambda key, default=None: {
                "ADMIN_USERNAME": "admin",
                "ADMIN_PASSWORD": "admin_pass",
                "ADMIN_DISABLED": disabled_value,
            }.get(key, default)
            mock_hash.return_value = "hashed_admin_pass"

            mock_repo = Mock(spec=UserRepository)
            _seed_credentials_from_env(mock_repo)

            call_kwargs = mock_repo.create_or_update_user.call_args[1]
            assert call_kwargs["disabled"] is True


@pytest.mark.unit
class TestGetUser:
    """Test suite for get_user function."""

    @patch("api.auth.user_repository")
    def test_get_user_with_default_repository(self, mock_repo):
        """Test get_user uses default repository when none provided."""
        mock_user = UserInDB(username="testuser", email="test@example.com", hashed_password="hashed", disabled=False)
        mock_repo.get_user.return_value = mock_user

        user = get_user("testuser")

        assert user == mock_user
        mock_repo.get_user.assert_called_once_with("testuser")

    def test_get_user_with_custom_repository(self):
        """Test get_user with custom repository."""
        mock_repo = Mock(spec=UserRepository)
        mock_user = UserInDB(username="testuser", email="test@example.com", hashed_password="hashed", disabled=False)
        mock_repo.get_user.return_value = mock_user

        user = get_user("testuser", repository=mock_repo)

        assert user == mock_user
        mock_repo.get_user.assert_called_once_with("testuser")


@pytest.mark.unit
class TestAuthenticateUser:
    """Test suite for authenticate_user function."""

    @patch("api.auth.verify_password")
    @patch("api.auth.get_user")
    def test_authenticate_user_success(self, mock_get_user, mock_verify):
        """Test successful user authentication."""
        mock_user = UserInDB(username="testuser", email="test@example.com", hashed_password="hashed_pw", disabled=False)
        mock_get_user.return_value = mock_user
        mock_verify.return_value = True

        result = authenticate_user("testuser", "correct_password")

        assert result == mock_user
        mock_get_user.assert_called_once()
        mock_verify.assert_called_once_with("correct_password", "hashed_pw")

    @patch("api.auth.get_user")
    def test_authenticate_user_nonexistent_user(self, mock_get_user):
        """Test authentication fails for non-existent user."""
        mock_get_user.return_value = None

        result = authenticate_user("nonexistent", "password")

        assert result is False

    @patch("api.auth.verify_password")
    @patch("api.auth.get_user")
    def test_authenticate_user_wrong_password(self, mock_get_user, mock_verify):
        """Test authentication fails with wrong password."""
        mock_user = UserInDB(username="testuser", email="test@example.com", hashed_password="hashed_pw", disabled=False)
        mock_get_user.return_value = mock_user
        mock_verify.return_value = False

        result = authenticate_user("testuser", "wrong_password")

        assert result is False

    @patch("api.auth.verify_password")
    @patch("api.auth.get_user")
    def test_authenticate_user_with_custom_repository(self, mock_get_user, mock_verify):
        """Test authentication with custom repository."""
        mock_repo = Mock(spec=UserRepository)
        mock_user = UserInDB(username="testuser", email="test@example.com", hashed_password="hashed_pw", disabled=False)
        mock_get_user.return_value = mock_user
        mock_verify.return_value = True

        result = authenticate_user("testuser", "password", repository=mock_repo)

        assert result == mock_user
        # Verify repository was passed through
        mock_get_user.assert_called_once_with("testuser", repository=mock_repo)


@pytest.mark.unit
class TestCreateAccessToken:
    """Test suite for create_access_token function."""

    def test_create_access_token_returns_string(self):
        """Test that create_access_token returns a JWT string."""
        token = create_access_token({"sub": "testuser"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_contains_claims(self):
        """Test that created token contains the provided claims."""
        data = {"sub": "testuser", "role": "admin"}
        token = create_access_token(data)

        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded["sub"] == "testuser"
        assert decoded["role"] == "admin"
        assert "exp" in decoded

    def test_create_access_token_with_custom_expiry(self):
        """Test creating token with custom expiration time."""
        from datetime import datetime, timezone

        data = {"sub": "testuser"}
        expires_delta = timedelta(minutes=30)
        token = create_access_token(data, expires_delta=expires_delta)

        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp_timestamp = decoded["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        now = datetime.now(timezone.utc)

        # Expiry should be approximately 30 minutes from now
        time_diff = (exp_datetime - now).total_seconds()
        assert 29 * 60 < time_diff < 31 * 60

    def test_create_access_token_with_default_expiry(self):
        """Test creating token with default expiration time."""
        from datetime import datetime, timezone

        data = {"sub": "testuser"}
        token = create_access_token(data)

        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp_timestamp = decoded["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        now = datetime.now(timezone.utc)

        # Default is 15 minutes
        time_diff = (exp_datetime - now).total_seconds()
        assert 14 * 60 < time_diff < 16 * 60

    def test_create_access_token_overrides_exp(self):
        """Test that create_access_token overrides any exp claim in data."""
        data = {"sub": "testuser", "exp": 12345}  # This should be overridden
        token = create_access_token(data)

        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded["exp"] != 12345  # Should be overridden with actual expiry

    def test_create_access_token_with_empty_data(self):
        """Test creating token with minimal data."""
        token = create_access_token({})
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in decoded


@pytest.mark.unit
class TestGetCurrentUser:
    """Test suite for get_current_user dependency."""

    @patch("api.auth.get_user")
    def test_get_current_user_valid_token(self, mock_get_user):
        """Test get_current_user with valid token."""
        # Create a valid token
        token = create_access_token({"sub": "testuser"})

        mock_user = UserInDB(username="testuser", email="test@example.com", hashed_password="hashed", disabled=False)
        mock_get_user.return_value = mock_user

        user = get_current_user(token)

        assert user == mock_user

    def test_get_current_user_invalid_token(self):
        """Test get_current_user with invalid token."""
        from fastapi import HTTPException

        invalid_token = "invalid.token.here"

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(invalid_token)

        assert exc_info.value.status_code == 401

    def test_get_current_user_expired_token(self):
        """Test get_current_user with expired token."""
        from datetime import timedelta

        from fastapi import HTTPException

        # Create an expired token
        token = create_access_token({"sub": "testuser"}, expires_delta=timedelta(seconds=-1))  # Already expired

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token)

        assert exc_info.value.status_code == 401

    @patch("api.auth.get_user")
    def test_get_current_user_missing_username(self, mock_get_user):
        """Test get_current_user with token missing username claim."""
        from fastapi import HTTPException

        # Create token without 'sub' claim
        token = create_access_token({"role": "admin"})

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token)

        assert exc_info.value.status_code == 401

    @patch("api.auth.get_user")
    def test_get_current_user_nonexistent_user(self, mock_get_user):
        """Test get_current_user when user doesn't exist in database."""
        from fastapi import HTTPException

        token = create_access_token({"sub": "nonexistent"})
        mock_get_user.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token)

        assert exc_info.value.status_code == 401


@pytest.mark.unit
class TestGetCurrentActiveUser:
    """Test suite for get_current_active_user dependency."""

    def test_get_current_active_user_active_user(self):
        """Test with active (non-disabled) user."""
        active_user = User(username="activeuser", email="active@example.com", disabled=False)

        result = get_current_active_user(active_user)

        assert result == active_user

    def test_get_current_active_user_disabled_user(self):
        """Test with disabled user raises exception."""
        from fastapi import HTTPException

        disabled_user = User(username="disableduser", email="disabled@example.com", disabled=True)

        with pytest.raises(HTTPException) as exc_info:
            get_current_active_user(disabled_user)

        assert exc_info.value.status_code == 400
        assert "Inactive user" in str(exc_info.value.detail)


@pytest.mark.unit
class TestUserModels:
    """Test suite for User data models."""

    def test_user_model_creation(self):
        """Test User model creation with all fields."""
        user = User(username="testuser", email="test@example.com", full_name="Test User", disabled=False)

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.disabled is False

    def test_user_model_optional_fields(self):
        """Test User model with optional fields as None."""
        user = User(username="testuser")

        assert user.username == "testuser"
        assert user.email is None
        assert user.full_name is None
        assert user.disabled is False

    def test_user_in_db_model(self):
        """Test UserInDB model includes hashed_password."""
        user = UserInDB(
            username="testuser", email="test@example.com", hashed_password="hashed_pw_string", disabled=False
        )

        assert user.username == "testuser"
        assert user.hashed_password == "hashed_pw_string"

    def test_token_model_creation(self):
        """Test Token model creation."""
        token = Token(access_token="token_string", token_type="bearer")

        assert token.access_token == "token_string"
        assert token.token_type == "bearer"

    def test_token_data_model(self):
        """Test TokenData model."""
        token_data = TokenData(username="testuser")
        assert token_data.username == "testuser"

    def test_token_data_model_optional_username(self):
        """Test TokenData with optional username."""
        token_data = TokenData()
        assert token_data.username is None


@pytest.mark.unit
class TestAuthenticationIntegration:
    """Integration tests for complete authentication flows."""

    @patch("api.auth.user_repository")
    def test_complete_login_flow(self, mock_repo):
        """Test complete login flow from password to token to user retrieval."""
        # Setup
        password = "test_password"
        hashed_password = get_password_hash(password)

        mock_user = UserInDB(
            username="testuser", email="test@example.com", hashed_password=hashed_password, disabled=False
        )
        mock_repo.get_user.return_value = mock_user

        # Step 1: Authenticate user
        authenticated = authenticate_user("testuser", password, repository=mock_repo)
        assert authenticated == mock_user

        # Step 2: Create access token
        token = create_access_token({"sub": authenticated.username})
        assert isinstance(token, str)

        # Step 3: Retrieve user from token
        retrieved_user = get_current_user(token)
        assert retrieved_user.username == "testuser"

        # Step 4: Verify user is active
        active_user = get_current_active_user(retrieved_user)
        assert active_user == retrieved_user

    @patch("api.auth.user_repository")
    def test_disabled_user_flow(self, mock_repo):
        """Test that disabled users cannot access protected resources."""
        from fastapi import HTTPException

        password = "test_password"
        hashed_password = get_password_hash(password)

        disabled_user = UserInDB(
            username="disableduser", email="disabled@example.com", hashed_password=hashed_password, disabled=True
        )
        mock_repo.get_user.return_value = disabled_user

        # User can authenticate
        authenticated = authenticate_user("disableduser", password, repository=mock_repo)
        assert authenticated == disabled_user

        # Can create token
        token = create_access_token({"sub": authenticated.username})

        # Can retrieve user
        retrieved_user = get_current_user(token)
        assert retrieved_user.disabled is True

        # But cannot access protected resources
        with pytest.raises(HTTPException) as exc_info:
            get_current_active_user(retrieved_user)
        assert exc_info.value.status_code == 400


@pytest.mark.unit
class TestAuthenticationEdgeCases:
    """Test edge cases and error conditions."""

    def test_password_with_only_special_characters(self):
        """Test password containing only special characters."""
        password = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_very_long_password(self):
        """Test authentication with very long password."""
        password = "a" * 1000
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_password_with_null_bytes(self):
        """Test password containing null bytes."""
        password = "pass\x00word"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    @patch("api.auth.jwt.decode")
    def test_get_current_user_jwt_error(self, mock_decode):
        """Test get_current_user handles JWT errors gracefully."""
        from fastapi import HTTPException
        from jose import JWTError

        mock_decode.side_effect = JWTError("Invalid token")

        with pytest.raises(HTTPException) as exc_info:
            get_current_user("invalid_token")

        assert exc_info.value.status_code == 401

    def test_token_created_at_exact_expiry(self):
        """Test token behavior at exact expiry time."""
        from datetime import timedelta

        # Create token that expires in 1 second
        token = create_access_token({"sub": "testuser"}, expires_delta=timedelta(seconds=1))

        # Should be valid immediately
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded["sub"] == "testuser"
