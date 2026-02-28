"""
Comprehensive unit tests for api/auth.py

Tests cover authentication, JWT token generation, password hashing,
user repository, and environment-based user seeding.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from jwt import InvalidTokenError

# Import the module to test
from api.auth import (
    Token,
    TokenData,
    User,
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
from api.models import UserInDB


class TestIsTruthy:
    """Test _is_truthy helper function."""

    def test_is_truthy_with_true(self):
        """_is_truthy returns True for 'true' (case-insensitive)."""
        assert _is_truthy("true") is True
        assert _is_truthy("TRUE") is True
        assert _is_truthy("True") is True

    def test_is_truthy_with_one(self):
        """_is_truthy returns True for '1'."""
        assert _is_truthy("1") is True

    def test_is_truthy_with_yes(self):
        """_is_truthy returns True for 'yes' (case-insensitive)."""
        assert _is_truthy("yes") is True
        assert _is_truthy("YES") is True
        assert _is_truthy("Yes") is True

    def test_is_truthy_with_on(self):
        """_is_truthy returns True for 'on' (case-insensitive)."""
        assert _is_truthy("on") is True
        assert _is_truthy("ON") is True
        assert _is_truthy("On") is True

    def test_is_truthy_with_false(self):
        """_is_truthy returns False for 'false'."""
        assert _is_truthy("false") is False
        assert _is_truthy("FALSE") is False

    def test_is_truthy_with_zero(self):
        """_is_truthy returns False for '0'."""
        assert _is_truthy("0") is False

    def test_is_truthy_with_no(self):
        """_is_truthy returns False for 'no'."""
        assert _is_truthy("no") is False
        assert _is_truthy("NO") is False

    def test_is_truthy_with_none(self):
        """_is_truthy returns False for None."""
        assert _is_truthy(None) is False

    def test_is_truthy_with_empty_string(self):
        """_is_truthy returns False for empty string."""
        assert _is_truthy("") is False

    def test_is_truthy_with_invalid_value(self):
        """_is_truthy returns False for unrecognized values."""
        assert _is_truthy("invalid") is False
        assert _is_truthy("2") is False
        assert _is_truthy("maybe") is False


class TestPasswordHashing:
    """Test password hashing and verification functions."""

    def test_get_password_hash_creates_hash(self):
        """get_password_hash creates a hashed password."""
        password = "SecurePassword123"
        hashed = get_password_hash(password)

        assert hashed is not None
        assert hashed != password
        assert len(hashed) > 0

    def test_verify_password_with_correct_password(self):
        """verify_password returns True for correct password."""
        password = "TestPassword456"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_with_incorrect_password(self):
        """verify_password returns False for incorrect password."""
        password = "CorrectPassword"
        wrong_password = "WrongPassword"
        hashed = get_password_hash(password)

        assert verify_password(wrong_password, hashed) is False

    def test_password_hash_is_unique(self):
        """get_password_hash generates unique hashes for same password."""
        password = "SamePassword"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        # Hashes should be different due to salting
        assert hash1 != hash2
        # But both should verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True

    def test_verify_password_with_empty_password(self):
        """verify_password handles empty password."""
        hashed = get_password_hash("")
        assert verify_password("", hashed) is True
        assert verify_password("nonempty", hashed) is False


class TestUserRepository:
    """Test UserRepository class."""

    @patch("api.auth.fetch_one")
    def test_get_user_found(self, mock_fetch_one):
        """get_user returns UserInDB when user exists."""
        mock_row = {
            "username": "testuser",
            "email": "test@example.com",
            "full_name": "Test User",
            "hashed_password": "hashed_pw",
            "disabled": 0,
        }
        mock_fetch_one.return_value = mock_row

        repository = UserRepository()
        user = repository.get_user("testuser")

        assert user is not None
        assert isinstance(user, UserInDB)
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.hashed_password == "hashed_pw"
        assert user.disabled is False

    @patch("api.auth.fetch_one")
    def test_get_user_not_found(self, mock_fetch_one):
        """get_user returns None when user doesn't exist."""
        mock_fetch_one.return_value = None

        repository = UserRepository()
        user = repository.get_user("nonexistent")

        assert user is None

    @patch("api.auth.fetch_one")
    def test_get_user_disabled_flag_true(self, mock_fetch_one):
        """get_user correctly converts disabled flag to boolean."""
        mock_row = {
            "username": "disabled_user",
            "email": "disabled@example.com",
            "full_name": "Disabled User",
            "hashed_password": "hashed_pw",
            "disabled": 1,  # Should be converted to True
        }
        mock_fetch_one.return_value = mock_row

        repository = UserRepository()
        user = repository.get_user("disabled_user")

        assert user is not None
        assert user.disabled is True

    @patch("api.auth.fetch_value")
    def test_has_users_returns_true(self, mock_fetch_value):
        """has_users returns True when users exist."""
        mock_fetch_value.return_value = 1

        repository = UserRepository()
        result = repository.has_users()

        assert result is True

    @patch("api.auth.fetch_value")
    def test_has_users_returns_false(self, mock_fetch_value):
        """has_users returns False when no users exist."""
        mock_fetch_value.return_value = None

        repository = UserRepository()
        result = repository.has_users()

        assert result is False

    @patch("api.auth.execute")
    def test_create_or_update_user_new_user(self, mock_execute):
        """create_or_update_user inserts new user."""
        repository = UserRepository()

        repository.create_or_update_user(
            username="newuser",
            hashed_password="hashed123",
            user_email="new@example.com",
            user_full_name="New User",
            is_disabled=False,
        )

        # Verify execute was called with correct SQL and parameters
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]

        assert "INSERT INTO user_credentials" in sql
        assert params == ("newuser", "new@example.com", "New User", "hashed123", 0)

    @patch("api.auth.execute")
    def test_create_or_update_user_disabled_true(self, mock_execute):
        """create_or_update_user converts is_disabled to integer."""
        repository = UserRepository()

        repository.create_or_update_user(
            username="user",
            hashed_password="hash",
            is_disabled=True,  # Should be converted to 1
        )

        call_args = mock_execute.call_args
        params = call_args[0][1]
        # Last parameter should be 1 for disabled=True
        assert params[-1] == 1

    @patch("api.auth.execute")
    def test_create_or_update_user_with_optional_fields_none(self, mock_execute):
        """create_or_update_user handles None for optional fields."""
        repository = UserRepository()

        repository.create_or_update_user(
            username="minuser",
            hashed_password="hash",
            user_email=None,
            user_full_name=None,
        )

        call_args = mock_execute.call_args
        params = call_args[0][1]

        # email and full_name should be None
        assert params[1] is None  # email
        assert params[2] is None  # full_name


class TestGetUser:
    """Test get_user function."""

    @patch("api.auth.user_repository")
    def test_get_user_uses_default_repository(self, mock_repo):
        """get_user uses module-level repository by default."""
        mock_user = UserInDB(
            username="test",
            hashed_password="hash",
        )
        mock_repo.get_user.return_value = mock_user

        user = get_user("test")

        assert user == mock_user
        mock_repo.get_user.assert_called_once_with("test")

    def test_get_user_uses_provided_repository(self):
        """get_user uses provided repository when given."""
        custom_repo = Mock(spec=UserRepository)
        mock_user = UserInDB(username="custom", hashed_password="hash")
        custom_repo.get_user.return_value = mock_user

        user = get_user("custom", repository=custom_repo)

        assert user == mock_user
        custom_repo.get_user.assert_called_once_with("custom")


class TestAuthenticateUser:
    """Test authenticate_user function."""

    @patch("api.auth.get_user")
    def test_authenticate_user_success(self, mock_get_user):
        """authenticate_user returns user for valid credentials."""
        password = "ValidPassword123"
        hashed = get_password_hash(password)

        mock_user = UserInDB(
            username="validuser",
            hashed_password=hashed,
        )
        mock_get_user.return_value = mock_user

        result = authenticate_user("validuser", password)

        assert result == mock_user
        assert isinstance(result, UserInDB)

    @patch("api.auth.get_user")
    def test_authenticate_user_user_not_found(self, mock_get_user):
        """authenticate_user returns False when user doesn't exist."""
        mock_get_user.return_value = None

        result = authenticate_user("nonexistent", "anypassword")

        assert result is False

    @patch("api.auth.get_user")
    def test_authenticate_user_wrong_password(self, mock_get_user):
        """authenticate_user returns False for incorrect password."""
        correct_password = "CorrectPassword"
        hashed = get_password_hash(correct_password)

        mock_user = UserInDB(
            username="user",
            hashed_password=hashed,
        )
        mock_get_user.return_value = mock_user

        result = authenticate_user("user", "WrongPassword")

        assert result is False

    def test_authenticate_user_with_custom_repository(self):
        """authenticate_user uses custom repository when provided."""
        custom_repo = Mock(spec=UserRepository)
        password = "TestPass"
        hashed = get_password_hash(password)

        mock_user = UserInDB(username="user", hashed_password=hashed)
        custom_repo.get_user.return_value = mock_user

        with patch("api.auth.get_user", return_value=mock_user) as mock_get_user:
            result = authenticate_user("user", password, repository=custom_repo)

        assert isinstance(result, UserInDB)
        mock_get_user.assert_called_once_with("user", repository=custom_repo)


class TestCreateAccessToken:
    """Test create_access_token function."""

    @patch("api.auth.datetime")
    def test_create_access_token_with_default_expiry(self, mock_datetime):
        """create_access_token creates token with default expiry."""
        fixed_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = fixed_time

        data = {"sub": "testuser"}
        token = create_access_token(data)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    @patch("api.auth.datetime")
    def test_create_access_token_with_custom_expiry(self, mock_datetime):
        """create_access_token creates token with custom expiry delta."""
        fixed_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = fixed_time

        data = {"sub": "testuser"}
        expires_delta = timedelta(minutes=60)

        token = create_access_token(data, expires_delta=expires_delta)

        assert token is not None
        assert isinstance(token, str)

    def test_create_access_token_includes_exp_claim(self):
        """create_access_token includes exp claim in payload."""
        import jwt

        data = {"sub": "testuser", "custom": "value"}
        token = create_access_token(data)

        # Decode without verification to check claims
        from api.auth import ALGORITHM, SECRET_KEY

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        assert "exp" in payload
        assert payload["sub"] == "testuser"
        assert payload["custom"] == "value"

    def test_create_access_token_preserves_data(self):
        """create_access_token preserves original data dict."""
        import jwt

        original_data = {"sub": "user", "role": "admin"}
        token = create_access_token(original_data.copy())

        from api.auth import ALGORITHM, SECRET_KEY

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        assert payload["sub"] == "user"
        assert payload["role"] == "admin"


class TestGetCurrentUser:
    """Test get_current_user async function."""

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self):
        """get_current_user returns user for valid token."""
        # Create a valid token
        user_data = {"sub": "testuser"}
        token = create_access_token(user_data)

        # Mock get_user to return a user
        mock_user = UserInDB(
            username="testuser",
            hashed_password="hash",
            email="test@example.com",
        )

        with patch("api.auth.get_user", return_value=mock_user):
            user = await get_current_user(token)

        assert user == mock_user
        assert user.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token(self):
        """get_current_user raises HTTPException for expired token."""
        # Create an expired token
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        data = {"sub": "testuser", "exp": past_time}

        import jwt

        from api.auth import ALGORITHM, SECRET_KEY

        expired_token = jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(expired_token)

        assert exc_info.value.status_code == 401
        assert "Token has expired" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self):
        """get_current_user raises HTTPException for invalid token."""
        invalid_token = "invalid.token.here"

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(invalid_token)

        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_missing_sub_claim(self):
        """get_current_user raises HTTPException when sub claim is missing."""
        # Token without 'sub' claim

        # Override to remove sub
        import jwt

        from api.auth import ALGORITHM, SECRET_KEY

        payload = {
            "other": "value",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token)

        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_user_not_found(self):
        """get_current_user raises HTTPException when user doesn't exist."""
        data = {"sub": "nonexistentuser"}
        token = create_access_token(data)

        with patch("api.auth.get_user", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token)

        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail


class TestGetCurrentActiveUser:
    """Test get_current_active_user async function."""

    @pytest.mark.asyncio
    async def test_get_current_active_user_active_user(self):
        """get_current_active_user returns user when not disabled."""
        active_user = UserInDB(
            username="activeuser",
            hashed_password="hash",
            disabled=False,
        )

        result = await get_current_active_user(active_user)

        assert result == active_user

    @pytest.mark.asyncio
    async def test_get_current_active_user_disabled_user(self):
        """get_current_active_user raises HTTPException for disabled user."""
        disabled_user = UserInDB(
            username="disableduser",
            hashed_password="hash",
            disabled=True,
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(disabled_user)

        assert exc_info.value.status_code == 400
        assert "Inactive user" in exc_info.value.detail


class TestSeedCredentialsFromEnv:
    """Test _seed_credentials_from_env function."""

    @patch("api.auth.get_password_hash")
    def test_seed_credentials_from_env_creates_user(self, mock_hash, monkeypatch):
        """_seed_credentials_from_env creates user from environment variables."""
        monkeypatch.setenv("ADMIN_USERNAME", "admin")
        monkeypatch.setenv("ADMIN_PASSWORD", "password123")
        monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
        monkeypatch.setenv("ADMIN_FULL_NAME", "Admin User")
        monkeypatch.setenv("ADMIN_DISABLED", "false")

        mock_hash.return_value = "hashed_password"

        mock_repo = Mock(spec=UserRepository)

        _seed_credentials_from_env(mock_repo)

        mock_repo.create_or_update_user.assert_called_once_with(
            username="admin",
            hashed_password="hashed_password",
            user_email="admin@example.com",
            user_full_name="Admin User",
            is_disabled=False,
        )

    def test_seed_credentials_from_env_missing_username(self, monkeypatch):
        """_seed_credentials_from_env does nothing when username is missing."""
        monkeypatch.delenv("ADMIN_USERNAME", raising=False)
        monkeypatch.setenv("ADMIN_PASSWORD", "password")

        mock_repo = Mock(spec=UserRepository)

        _seed_credentials_from_env(mock_repo)

        mock_repo.create_or_update_user.assert_not_called()

    def test_seed_credentials_from_env_missing_password(self, monkeypatch):
        """_seed_credentials_from_env does nothing when password is missing."""
        monkeypatch.setenv("ADMIN_USERNAME", "admin")
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

        mock_repo = Mock(spec=UserRepository)

        _seed_credentials_from_env(mock_repo)

        mock_repo.create_or_update_user.assert_not_called()

    @patch("api.auth.get_password_hash")
    def test_seed_credentials_from_env_disabled_true(self, mock_hash, monkeypatch):
        """_seed_credentials_from_env handles ADMIN_DISABLED=true."""
        monkeypatch.setenv("ADMIN_USERNAME", "admin")
        monkeypatch.setenv("ADMIN_PASSWORD", "pass")
        monkeypatch.setenv("ADMIN_DISABLED", "true")

        mock_hash.return_value = "hash"

        mock_repo = Mock(spec=UserRepository)

        _seed_credentials_from_env(mock_repo)

        call_args = mock_repo.create_or_update_user.call_args
        assert call_args[1]["is_disabled"] is True

    @patch("api.auth.get_password_hash")
    def test_seed_credentials_from_env_minimal_fields(self, mock_hash, monkeypatch):
        """_seed_credentials_from_env works with minimal required fields."""
        monkeypatch.setenv("ADMIN_USERNAME", "admin")
        monkeypatch.setenv("ADMIN_PASSWORD", "pass")
        # No email, full_name, or disabled

        mock_hash.return_value = "hash"

        mock_repo = Mock(spec=UserRepository)

        _seed_credentials_from_env(mock_repo)

        mock_repo.create_or_update_user.assert_called_once()
        call_args = mock_repo.create_or_update_user.call_args

        assert call_args[1]["username"] == "admin"
        assert call_args[1]["user_email"] is None
        assert call_args[1]["user_full_name"] is None
        assert call_args[1]["is_disabled"] is False  # Default


class TestPydanticModels:
    """Test Pydantic model definitions."""

    def test_token_model(self):
        """Token model validates correctly."""
        token = Token(access_token="abc123", token_type="bearer")

        assert token.access_token == "abc123"
        assert token.token_type == "bearer"

    def test_token_data_model_with_username(self):
        """TokenData model accepts username."""
        token_data = TokenData(username="testuser")

        assert token_data.username == "testuser"

    def test_token_data_model_without_username(self):
        """TokenData model allows None for username."""
        token_data = TokenData()

        assert token_data.username is None

    def test_user_model_minimal(self):
        """User model works with minimal fields."""
        user = User(username="user", hashed_password="hash")

        assert user.username == "user"
        assert user.hashed_password == "hash"
        assert user.email is None
        assert user.full_name is None
        assert user.disabled is None

    def test_user_model_full(self):
        """User model works with all fields."""
        user = User(
            username="fulluser",
            email="full@example.com",
            full_name="Full User",
            disabled=False,
            hashed_password="hash",
        )

        assert user.username == "fulluser"
        assert user.email == "full@example.com"
        assert user.full_name == "Full User"
        assert user.disabled is False


class TestRegressionAndEdgeCases:
    """Test edge cases and potential regressions."""

    def test_verify_password_with_special_characters(self):
        """verify_password handles passwords with special characters."""
        password = "P@ssw0rd!#$%^&*()_+-=[]{}|;:',.<>?/`~"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_with_unicode(self):
        """verify_password handles unicode characters."""
        password = "пароль密码🔐"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    @pytest.mark.asyncio
    async def test_get_current_user_with_algorithm_confusion_attack(self):
        """get_current_user prevents algorithm confusion attacks."""
        import jwt

        from api.auth import SECRET_KEY

        # Try to create token with 'none' algorithm
        payload = {"sub": "attacker"}
        malicious_token = jwt.encode(payload, None, algorithm="none")

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(malicious_token)

        assert exc_info.value.status_code == 401

    def test_create_access_token_large_payload(self):
        """create_access_token handles large data payloads."""
        large_data = {
            "sub": "user",
            "roles": ["admin", "user", "moderator"] * 100,
            "permissions": list(range(1000)),
        }

        token = create_access_token(large_data)

        assert token is not None
        assert isinstance(token, str)

    @patch("api.auth.fetch_one")
    def test_get_user_with_null_email_and_name(self, mock_fetch_one):
        """get_user handles NULL email and full_name from database."""
        mock_row = {
            "username": "minuser",
            "email": None,
            "full_name": None,
            "hashed_password": "hash",
            "disabled": 0,
        }
        mock_fetch_one.return_value = mock_row

        repository = UserRepository()
        user = repository.get_user("minuser")

        assert user is not None
        assert user.email is None
        assert user.full_name is None
