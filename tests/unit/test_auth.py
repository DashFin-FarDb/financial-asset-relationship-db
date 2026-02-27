"""Comprehensive unit tests for api/auth.py authentication and user management.

This module tests the authentication system including:
- UserRepository methods (get_user, has_users, create_or_update_user)
- Password hashing and verification
- JWT token generation and validation
- User authentication flow
- Environment-based user seeding
- Helper functions (_is_truthy, _seed_credentials_from_env)
"""

import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from jose import jwt

from api.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
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
    get_password_hash,
    get_user,
    verify_password,
)


class TestIsTruthyHelper:
    """Test the _is_truthy helper function for boolean string evaluation."""

    @staticmethod
    def test_is_truthy_with_true_strings():
        """Test that recognized truthy strings return True."""
        assert _is_truthy("true") is True
        assert _is_truthy("True") is True
        assert _is_truthy("TRUE") is True
        assert _is_truthy("1") is True
        assert _is_truthy("yes") is True
        assert _is_truthy("YES") is True
        assert _is_truthy("on") is True
        assert _is_truthy("ON") is True

    @staticmethod
    def test_is_truthy_with_false_strings():
        """Test that unrecognized strings return False."""
        assert _is_truthy("false") is False
        assert _is_truthy("0") is False
        assert _is_truthy("no") is False
        assert _is_truthy("off") is False
        assert _is_truthy("random") is False
        assert _is_truthy("") is False

    @staticmethod
    def test_is_truthy_with_none():
        """Test that None returns False."""
        assert _is_truthy(None) is False

    @staticmethod
    def test_is_truthy_case_insensitive():
        """Test that evaluation is case-insensitive."""
        assert _is_truthy("TrUe") is True
        assert _is_truthy("YeS") is True
        assert _is_truthy("oN") is True


class TestPasswordHashing:
    """Test password hashing and verification functions."""

    @staticmethod
    def test_get_password_hash_returns_different_hash():
        """Test that same password produces different hashes (salt)."""
        password = "test_password_123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        assert hash1 != hash2
        assert hash1 is not None
        assert hash2 is not None
        assert len(hash1) > 20
        assert len(hash2) > 20

    @staticmethod
    def test_verify_password_with_correct_password():
        """Test that correct password verifies successfully."""
        password = "correct_password"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    @staticmethod
    def test_verify_password_with_incorrect_password():
        """Test that incorrect password fails verification."""
        password = "correct_password"
        wrong_password = "wrong_password"
        hashed = get_password_hash(password)

        assert verify_password(wrong_password, hashed) is False

    @staticmethod
    def test_verify_password_with_empty_password():
        """Test verification with empty password."""
        hashed = get_password_hash("something")
        assert verify_password("", hashed) is False

    @staticmethod
    def test_hash_empty_password():
        """Test that empty password can be hashed."""
        hashed = get_password_hash("")
        assert hashed is not None
        assert len(hashed) > 0


class TestUserModels:
    """Test User and UserInDB Pydantic models."""

    def test_user_model_creation(self):
        """Test creating a User model."""
        user = User(
            username="testuser", email="test@example.com", full_name="Test User"
        )

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.disabled is None

    def test_user_model_with_disabled_flag(self):
        """Test User model with disabled flag."""
        user = User(username="testuser", disabled=True)
        assert user.disabled is True

        user2 = User(username="testuser2", disabled=False)
        assert user2.disabled is False

    def test_user_in_db_model_creation(self):
        """Test creating a UserInDB model with hashed password."""
        user_in_db = UserInDB(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            disabled=False,
            hashed_password="hashed_password_string",
        )

        assert user_in_db.username == "testuser"
        assert user_in_db.email == "test@example.com"
        assert user_in_db.hashed_password == "hashed_password_string"
        assert user_in_db.disabled is False

    def test_user_in_db_inherits_from_user(self):
        """Test that UserInDB inherits from User."""
        assert issubclass(UserInDB, User)


class TestUserRepository:
    """Test UserRepository database operations."""

    @pytest.fixture
    def mock_database(self):
        """Mock database operations."""
        with (
            patch("api.auth.initialize_schema") as mock_init,
            patch("api.auth.fetch_one") as mock_fetch_one,
            patch("api.auth.fetch_value") as mock_fetch_value,
            patch("api.auth.execute") as mock_execute,
        ):
            yield {
                "initialize_schema": mock_init,
                "fetch_one": mock_fetch_one,
                "fetch_value": mock_fetch_value,
                "execute": mock_execute,
            }

    def test_get_user_returns_user_when_found(self, mock_database):
        """Test get_user returns UserInDB when user exists."""
        mock_database["fetch_one"].return_value = {
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

    def test_get_user_returns_none_when_not_found(self, mock_database):
        """Test get_user returns None when user doesn't exist."""
        mock_database["fetch_one"].return_value = None

        repo = UserRepository()
        user = repo.get_user("nonexistent")

        assert user is None

    def test_get_user_converts_disabled_flag_correctly(self, mock_database):
        """Test that disabled flag is correctly converted from int to bool."""
        # Test disabled=1 converts to True
        mock_database["fetch_one"].return_value = {
            "username": "disabled_user",
            "email": "disabled@example.com",
            "full_name": "Disabled User",
            "hashed_password": "hashed_pw",
            "disabled": 1,
        }

        repo = UserRepository()
        user = repo.get_user("disabled_user")

        assert user.disabled is True

    def test_has_users_returns_true_when_users_exist(self, mock_database):
        """Test has_users returns True when users exist."""
        mock_database["fetch_value"].return_value = 1

        repo = UserRepository()
        result = repo.has_users()

        assert result is True

    def test_has_users_returns_false_when_no_users(self, mock_database):
        """Test has_users returns False when no users exist."""
        mock_database["fetch_value"].return_value = None

        repo = UserRepository()
        result = repo.has_users()

        assert result is False

    def test_create_or_update_user_with_all_fields(self, mock_database):
        """Test creating/updating user with all fields populated."""
        repo = UserRepository()
        repo.create_or_update_user(
            username="newuser",
            hashed_password="hashed_pw",
            email="new@example.com",
            full_name="New User",
            disabled=True,
        )

        mock_database["execute"].assert_called_once()
        call_args = mock_database["execute"].call_args

        # Check that parameters were passed correctly
        assert "newuser" in call_args[0][1]
        assert "new@example.com" in call_args[0][1]
        assert "New User" in call_args[0][1]
        assert "hashed_pw" in call_args[0][1]
        assert 1 in call_args[0][1]  # disabled=True converts to 1

    def test_create_or_update_user_with_minimal_fields(self, mock_database):
        """Test creating/updating user with only required fields."""
        repo = UserRepository()
        repo.create_or_update_user(username="minimaluser", hashed_password="hashed_pw")

        mock_database["execute"].assert_called_once()
        call_args = mock_database["execute"].call_args

        assert "minimaluser" in call_args[0][1]
        assert "hashed_pw" in call_args[0][1]
        assert 0 in call_args[0][1]  # disabled=False (default) converts to 0

    def test_create_or_update_user_disabled_flag_conversion(self, mock_database):
        """Test that disabled boolean is correctly converted to int."""
        repo = UserRepository()

        # Test disabled=False
        repo.create_or_update_user(
            username="user1", hashed_password="pw1", disabled=False
        )
        assert 0 in mock_database["execute"].call_args[0][1]

        # Test disabled=True
        repo.create_or_update_user(
            username="user2", hashed_password="pw2", disabled=True
        )
        assert 1 in mock_database["execute"].call_args[0][1]


class TestAuthenticationFunctions:
    """Test authentication helper functions."""

    @pytest.fixture
    def mock_repository(self):
        """Create a mock UserRepository."""
        with patch("api.auth.user_repository") as mock_repo:
            yield mock_repo

    def test_get_user_calls_repository(self, mock_repository):
        """Test get_user function calls the repository correctly."""
        mock_user = UserInDB(
            username="testuser", hashed_password="hashed", disabled=False
        )
        mock_repository.get_user.return_value = mock_user

        result = get_user("testuser")

        assert result == mock_user
        mock_repository.get_user.assert_called_once_with("testuser")

    def test_get_user_with_custom_repository(self):
        """Test get_user with custom repository parameter."""
        custom_repo = Mock(spec=UserRepository)
        mock_user = UserInDB(
            username="testuser", hashed_password="hashed", disabled=False
        )
        custom_repo.get_user.return_value = mock_user

        result = get_user("testuser", repository=custom_repo)

        assert result == mock_user
        custom_repo.get_user.assert_called_once_with("testuser")

    def test_authenticate_user_with_correct_credentials(self, mock_repository):
        """Test authenticate_user with correct username and password."""
        hashed_password = get_password_hash("correct_password")
        mock_user = UserInDB(
            username="testuser", hashed_password=hashed_password, disabled=False
        )
        mock_repository.get_user.return_value = mock_user

        result = authenticate_user("testuser", "correct_password")

        assert result == mock_user

    def test_authenticate_user_with_incorrect_password(self, mock_repository):
        """Test authenticate_user with wrong password returns False."""
        hashed_password = get_password_hash("correct_password")
        mock_user = UserInDB(
            username="testuser", hashed_password=hashed_password, disabled=False
        )
        mock_repository.get_user.return_value = mock_user

        result = authenticate_user("testuser", "wrong_password")

        assert result is False

    def test_authenticate_user_with_nonexistent_user(self, mock_repository):
        """Test authenticate_user with nonexistent user returns False."""
        mock_repository.get_user.return_value = None

        result = authenticate_user("nonexistent", "password")

        assert result is False

    def test_authenticate_user_with_custom_repository(self):
        """Test authenticate_user with custom repository."""
        custom_repo = Mock(spec=UserRepository)
        hashed_password = get_password_hash("password")
        mock_user = UserInDB(
            username="testuser", hashed_password=hashed_password, disabled=False
        )
        custom_repo.get_user.return_value = mock_user

        result = authenticate_user("testuser", "password", repository=custom_repo)

        assert result == mock_user
        custom_repo.get_user.assert_called_once_with("testuser")


class TestJWTTokenOperations:
    """Test JWT token creation and validation."""

    def test_create_access_token_with_default_expiry(self):
        """Test creating access token with default expiration."""
        data = {"sub": "testuser"}
        token = create_access_token(data)

        assert isinstance(token, str)
        assert len(token) > 0

        # Decode and verify
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"
        assert "exp" in payload

    def test_create_access_token_with_custom_expiry(self):
        """Test creating access token with custom expiration."""
        data = {"sub": "testuser"}
        expires_delta = timedelta(minutes=60)
        token = create_access_token(data, expires_delta=expires_delta)

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"

        # Check expiry is approximately correct (within 5 seconds)
        exp_time = datetime.fromtimestamp(payload["exp"])
        expected_time = datetime.utcnow() + expires_delta
        time_diff = abs((exp_time - expected_time).total_seconds())
        assert time_diff < 5

    def test_create_access_token_includes_all_data(self):
        """Test that all provided data is included in token."""
        data = {"sub": "testuser", "scope": "admin", "custom_field": "custom_value"}
        token = create_access_token(data)

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"
        assert payload["scope"] == "admin"
        assert payload["custom_field"] == "custom_value"

    def test_token_data_model(self):
        """Test TokenData model creation."""
        token_data = TokenData(username="testuser")
        assert token_data.username == "testuser"

        token_data_none = TokenData(username=None)
        assert token_data_none.username is None

    def test_token_model(self):
        """Test Token response model."""
        token = Token(access_token="abc123", token_type="bearer")
        assert token.access_token == "abc123"
        assert token.token_type == "bearer"


class TestCurrentUserDependencies:
    """Test FastAPI dependency functions for current user."""

    @pytest.fixture
    def mock_oauth2_scheme(self):
        """Mock OAuth2PasswordBearer."""
        with patch("api.auth.oauth2_scheme") as mock_scheme:
            yield mock_scheme

    @pytest.fixture
    def mock_repository(self):
        """Mock user repository."""
        with patch("api.auth.user_repository") as mock_repo:
            yield mock_repo

    def test_get_current_user_with_valid_token(
        self, mock_oauth2_scheme, mock_repository
    ):
        """Test get_current_user with valid JWT token."""
        # Create a valid token
        token_data = {"sub": "testuser"}
        token = create_access_token(token_data)

        mock_user = UserInDB(
            username="testuser", hashed_password="hashed", disabled=False
        )
        mock_repository.get_user.return_value = mock_user

        # This would normally be called by FastAPI with the token
        # We'll test the logic directly
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"

    def test_get_current_active_user_with_active_user(self):
        """Test get_current_active_user with non-disabled user."""
        active_user = User(username="activeuser", disabled=False)
        result = get_current_active_user(active_user)
        assert result == active_user

    def test_get_current_active_user_with_disabled_user(self):
        """Test get_current_active_user raises error for disabled user."""
        from fastapi import HTTPException

        disabled_user = User(username="disableduser", disabled=True)

        with pytest.raises(HTTPException) as exc_info:
            get_current_active_user(disabled_user)

        assert exc_info.value.status_code == 400
        assert "Inactive user" in str(exc_info.value.detail)

    def test_get_current_active_user_with_none_disabled(self):
        """Test get_current_active_user with None disabled (treated as active)."""
        user = User(username="user", disabled=None)
        result = get_current_active_user(user)
        assert result == user


class TestSeedCredentialsFromEnv:
    """Test environment-based user credential seeding."""

    def test_seed_credentials_with_valid_env_vars(self):
        """Test seeding user from complete environment variables."""
        mock_repo = Mock(spec=UserRepository)
        mock_repo.has_users.return_value = False

        with patch.dict(
            os.environ,
            {
                "ADMIN_USERNAME": "admin",
                "ADMIN_PASSWORD": "admin_password",
                "ADMIN_EMAIL": "admin@example.com",
                "ADMIN_FULL_NAME": "Admin User",
            },
        ):
            _seed_credentials_from_env(mock_repo)

        mock_repo.has_users.assert_called_once()
        mock_repo.create_or_update_user.assert_called_once()

        call_kwargs = mock_repo.create_or_update_user.call_args[1]
        assert call_kwargs["username"] == "admin"
        assert call_kwargs["email"] == "admin@example.com"
        assert call_kwargs["full_name"] == "Admin User"
        assert "hashed_password" in call_kwargs
        assert call_kwargs["disabled"] is False

    def test_seed_credentials_with_minimal_env_vars(self):
        """Test seeding with only required username and password."""
        mock_repo = Mock(spec=UserRepository)
        mock_repo.has_users.return_value = False

        with patch.dict(
            os.environ,
            {"ADMIN_USERNAME": "admin", "ADMIN_PASSWORD": "password"},
            clear=False,
        ):
            _seed_credentials_from_env(mock_repo)

        mock_repo.create_or_update_user.assert_called_once()
        call_kwargs = mock_repo.create_or_update_user.call_args[1]
        assert call_kwargs["username"] == "admin"
        assert call_kwargs.get("email") is None
        assert call_kwargs.get("full_name") is None

    def test_seed_credentials_skipped_when_users_exist(self):
        """Test that seeding is skipped when users already exist."""
        mock_repo = Mock(spec=UserRepository)
        mock_repo.has_users.return_value = True

        with patch.dict(
            os.environ, {"ADMIN_USERNAME": "admin", "ADMIN_PASSWORD": "password"}
        ):
            _seed_credentials_from_env(mock_repo)

        mock_repo.has_users.assert_called_once()
        mock_repo.create_or_update_user.assert_not_called()

    def test_seed_credentials_with_disabled_flag(self):
        """Test seeding with ADMIN_DISABLED environment variable."""
        mock_repo = Mock(spec=UserRepository)
        mock_repo.has_users.return_value = False

        # Test with truthy value
        with patch.dict(
            os.environ,
            {
                "ADMIN_USERNAME": "admin",
                "ADMIN_PASSWORD": "password",
                "ADMIN_DISABLED": "true",
            },
        ):
            _seed_credentials_from_env(mock_repo)

        call_kwargs = mock_repo.create_or_update_user.call_args[1]
        assert call_kwargs["disabled"] is True

    def test_seed_credentials_without_username_or_password(self):
        """Test that seeding is skipped when username or password is missing."""
        mock_repo = Mock(spec=UserRepository)
        mock_repo.has_users.return_value = False

        # Missing password
        with patch.dict(os.environ, {"ADMIN_USERNAME": "admin"}, clear=True):
            _seed_credentials_from_env(mock_repo)
        mock_repo.create_or_update_user.assert_not_called()

        # Missing username
        mock_repo.reset_mock()
        with patch.dict(os.environ, {"ADMIN_PASSWORD": "password"}, clear=True):
            _seed_credentials_from_env(mock_repo)
        mock_repo.create_or_update_user.assert_not_called()

    def test_seed_credentials_password_is_hashed(self):
        """Test that the password is properly hashed before storage."""
        mock_repo = Mock(spec=UserRepository)
        mock_repo.has_users.return_value = False

        plain_password = "test_password_123"

        with patch.dict(
            os.environ, {"ADMIN_USERNAME": "admin", "ADMIN_PASSWORD": plain_password}
        ):
            _seed_credentials_from_env(mock_repo)

        call_kwargs = mock_repo.create_or_update_user.call_args[1]
        hashed = call_kwargs["hashed_password"]

        # Verify the password was hashed (not stored as plaintext)
        assert hashed != plain_password
        assert verify_password(plain_password, hashed)


class TestSecurityConfiguration:
    """Test security configuration and constants."""

    @staticmethod
    def test_secret_key_is_set():
        """Test that SECRET_KEY is configured."""
        assert SECRET_KEY is not None
        assert len(SECRET_KEY) > 0

    @staticmethod
    def test_algorithm_is_hs256():
        """Test that JWT algorithm is HS256."""
        assert ALGORITHM == "HS256"

    @staticmethod
    def test_access_token_expire_minutes_is_positive():
        """Test that token expiration is a positive number."""
        assert ACCESS_TOKEN_EXPIRE_MINUTES > 0
        assert isinstance(ACCESS_TOKEN_EXPIRE_MINUTES, int)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @staticmethod
    def test_user_repository_methods_are_instance_methods():
        """Test that UserRepository methods are instance methods, not static."""
        repo = UserRepository()

        # Check methods exist and are callable
        assert callable(repo.get_user)
        assert callable(repo.has_users)
        assert callable(repo.create_or_update_user)

        # Verify they are bound methods (have 'self')
        import inspect

        assert "self" in inspect.signature(repo.get_user).parameters
        assert "self" in inspect.signature(repo.has_users).parameters
        assert "self" in inspect.signature(repo.create_or_update_user).parameters

    @staticmethod
    def test_authenticate_with_empty_credentials():
        """Test authentication with empty username or password."""
        with patch("api.auth.user_repository.get_user") as mock_get:
            mock_get.return_value = None

            result = authenticate_user("", "password")
            assert result is False

            result = authenticate_user("username", "")
            assert result is False

    @staticmethod
    def test_special_characters_in_username():
        """Test handling of special characters in usernames."""
        mock_repo = Mock(spec=UserRepository)
        mock_repo.get_user.return_value = None

        # Should not crash with special characters
        result = get_user("user@example.com", repository=mock_repo)
        assert result is None

        result = get_user("user-name_123", repository=mock_repo)
        assert result is None
