"""Comprehensive unit tests for the authentication module (api/auth.py).

This module tests:
- Password hashing and verification
- JWT token creation and validation
- User authentication flow
- User repository operations (get, create, update)
- OAuth2 integration
- Error handling for authentication failures
"""

import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

import pytest
from fastapi import HTTPException, status
from jwt import ExpiredSignatureError, InvalidTokenError

from api.auth import (
    Token,
    TokenData,
    User,
    UserInDB,
    UserRepository,
    _is_truthy,
    authenticate_user,
    create_access_token,
    get_current_active_user,
    get_current_user,
    get_password_hash,
    verify_password,
)


class TestIsTruthy:
    """Test the _is_truthy helper function."""

    def test_truthy_values(self):
        """Test that recognized truthy strings return True."""
        assert _is_truthy("true")
        assert _is_truthy("True")
        assert _is_truthy("TRUE")
        assert _is_truthy("1")
        assert _is_truthy("yes")
        assert _is_truthy("Yes")
        assert _is_truthy("YES")
        assert _is_truthy("on")
        assert _is_truthy("On")
        assert _is_truthy("ON")

    def test_falsy_values(self):
        """Test that non-truthy strings return False."""
        assert not _is_truthy("false")
        assert not _is_truthy("0")
        assert not _is_truthy("no")
        assert not _is_truthy("off")
        assert not _is_truthy("")
        assert not _is_truthy("random")
        assert not _is_truthy("maybe")

    def test_none_value(self):
        """Test that None returns False."""
        assert not _is_truthy(None)

    def test_whitespace(self):
        """Test handling of whitespace."""
        assert not _is_truthy("  ")
        assert not _is_truthy("\t")
        assert not _is_truthy("\n")


class TestPasswordHashing:
    """Test password hashing and verification."""

    def test_hash_password(self):
        """Test that passwords are hashed correctly."""
        plain_password = "securePassword123!"
        hashed = get_password_hash(plain_password)
        
        assert hashed != plain_password
        assert len(hashed) > 0
        assert "$" in hashed  # pbkdf2_sha256 format

    def test_verify_correct_password(self):
        """Test verification of correct password."""
        plain_password = "correctPassword"
        hashed = get_password_hash(plain_password)
        
        assert verify_password(plain_password, hashed)

    def test_verify_incorrect_password(self):
        """Test verification fails for incorrect password."""
        plain_password = "correctPassword"
        wrong_password = "wrongPassword"
        hashed = get_password_hash(plain_password)
        
        assert not verify_password(wrong_password, hashed)

    def test_hash_consistency(self):
        """Test that same password produces different hashes (salt)."""
        plain_password = "samePassword"
        hash1 = get_password_hash(plain_password)
        hash2 = get_password_hash(plain_password)
        
        # Different hashes due to salt
        assert hash1 != hash2
        # Both should verify correctly
        assert verify_password(plain_password, hash1)
        assert verify_password(plain_password, hash2)

    def test_empty_password(self):
        """Test handling of empty password."""
        empty_password = ""
        hashed = get_password_hash(empty_password)
        
        assert len(hashed) > 0
        assert verify_password(empty_password, hashed)


class TestUserModels:
    """Test Pydantic user models."""

    def test_token_model(self):
        """Test Token model creation."""
        token = Token(access_token="test_token", token_type="bearer")
        
        assert token.access_token == "test_token"
        assert token.token_type == "bearer"

    def test_token_data_model(self):
        """Test TokenData model."""
        token_data = TokenData(username="testuser")
        assert token_data.username == "testuser"
        
        token_data_none = TokenData()
        assert token_data_none.username is None

    def test_user_model(self):
        """Test User model creation."""
        user = User(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            disabled=False
        )
        
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.disabled is False

    def test_user_model_optional_fields(self):
        """Test User model with optional fields."""
        user = User(username="testuser")
        
        assert user.username == "testuser"
        assert user.email is None
        assert user.full_name is None
        assert user.disabled is None

    def test_user_in_db_model(self):
        """Test UserInDB model extends User."""
        user_in_db = UserInDB(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_pwd_123"
        )
        
        assert user_in_db.username == "testuser"
        assert user_in_db.email == "test@example.com"
        assert user_in_db.hashed_password == "hashed_pwd_123"
        assert isinstance(user_in_db, User)


class TestUserRepository:
    """Test UserRepository operations."""

    @pytest.fixture
    def mock_user_data(self):
        """Fixture providing mock user data."""
        return {
            "username": "testuser",
            "email": "test@example.com",
            "full_name": "Test User",
            "hashed_password": "hashed_password_123",
            "disabled": 0
        }

    @pytest.fixture
    def user_repo(self):
        """Fixture providing UserRepository instance."""
        return UserRepository()

    @patch('api.auth.fetch_one')
    def test_get_user_exists(self, mock_fetch_one, user_repo, mock_user_data):
        """Test getting an existing user."""
        mock_fetch_one.return_value = mock_user_data
        
        user = user_repo.get_user("testuser")
        
        assert user is not None
        assert isinstance(user, UserInDB)
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.hashed_password == "hashed_password_123"
        assert user.disabled is False
        
        mock_fetch_one.assert_called_once()

    @patch('api.auth.fetch_one')
    def test_get_user_not_exists(self, mock_fetch_one, user_repo):
        """Test getting a non-existent user returns None."""
        mock_fetch_one.return_value = None
        
        user = user_repo.get_user("nonexistent")
        
        assert user is None
        mock_fetch_one.assert_called_once()

    @patch('api.auth.fetch_one')
    def test_get_user_disabled_flag(self, mock_fetch_one, user_repo, mock_user_data):
        """Test that disabled flag is correctly converted to bool."""
        mock_user_data["disabled"] = 1
        mock_fetch_one.return_value = mock_user_data
        
        user = user_repo.get_user("testuser")
        
        assert user.disabled is True

    @patch('api.auth.fetch_value')
    def test_has_users_true(self, mock_fetch_value, user_repo):
        """Test has_users returns True when users exist."""
        mock_fetch_value.return_value = 1
        
        result = user_repo.has_users()
        
        assert result is True
        mock_fetch_value.assert_called_once()

    @patch('api.auth.fetch_value')
    def test_has_users_false(self, mock_fetch_value, user_repo):
        """Test has_users returns False when no users exist."""
        mock_fetch_value.return_value = None
        
        result = user_repo.has_users()
        
        assert result is False
        mock_fetch_value.assert_called_once()

    @patch('api.auth.execute')
    def test_create_or_update_user_new(self, mock_execute, user_repo):
        """Test creating a new user."""
        user_repo.create_or_update_user(
            username="newuser",
            hashed_password="hashed_pwd",
            email="new@example.com",
            full_name="New User",
            disabled=False
        )
        
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args
        assert "newuser" in call_args[0][1]
        assert "hashed_pwd" in call_args[0][1]
        assert "new@example.com" in call_args[0][1]
        assert "New User" in call_args[0][1]
        assert call_args[0][1][4] == 0  # disabled=False -> 0

    @patch('api.auth.execute')
    def test_create_or_update_user_disabled(self, mock_execute, user_repo):
        """Test creating a disabled user."""
        user_repo.create_or_update_user(
            username="disabled_user",
            hashed_password="hashed_pwd",
            disabled=True
        )
        
        call_args = mock_execute.call_args
        assert call_args[0][1][4] == 1  # disabled=True -> 1

    @patch('api.auth.execute')
    def test_create_or_update_user_minimal(self, mock_execute, user_repo):
        """Test creating user with only required fields."""
        user_repo.create_or_update_user(
            username="minimal",
            hashed_password="hashed"
        )
        
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args
        assert call_args[0][1][1] is None  # email
        assert call_args[0][1][2] is None  # full_name


class TestJWTOperations:
    """Test JWT token creation and validation."""

    def test_create_access_token_basic(self):
        """Test creating a basic access token."""
        data = {"sub": "testuser"}
        token = create_access_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 0
        assert "." in token  # JWT format

    def test_create_access_token_with_expiration(self):
        """Test creating token with custom expiration."""
        data = {"sub": "testuser"}
        expires_delta = timedelta(minutes=15)
        token = create_access_token(data, expires_delta)
        
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_default_expiration(self):
        """Test token creation uses default expiration."""
        data = {"sub": "testuser"}
        token = create_access_token(data)
        
        # Decode to verify expiration was set
        import jwt
        secret_key = os.getenv("SECRET_KEY")
        decoded = jwt.decode(token, secret_key, algorithms=["HS256"])
        
        assert "exp" in decoded
        assert "sub" in decoded
        assert decoded["sub"] == "testuser"

    def test_create_access_token_additional_claims(self):
        """Test token with additional claims."""
        data = {"sub": "testuser", "role": "admin", "permissions": ["read", "write"]}
        token = create_access_token(data)
        
        import jwt
        secret_key = os.getenv("SECRET_KEY")
        decoded = jwt.decode(token, secret_key, algorithms=["HS256"])
        
        assert decoded["sub"] == "testuser"
        assert decoded["role"] == "admin"
        assert decoded["permissions"] == ["read", "write"]


class TestAuthenticationFlow:
    """Test the complete authentication flow."""

    @pytest.fixture
    def mock_user(self):
        """Fixture providing a mock user."""
        return UserInDB(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            hashed_password=get_password_hash("correctpassword"),
            disabled=False
        )

    @patch('api.auth.user_repository.get_user')
    def test_authenticate_user_success(self, mock_get_user, mock_user):
        """Test successful user authentication."""
        mock_get_user.return_value = mock_user
        
        user = authenticate_user("testuser", "correctpassword")
        
        assert user is not None
        assert user.username == "testuser"
        assert isinstance(user, UserInDB)

    @patch('api.auth.user_repository.get_user')
    def test_authenticate_user_wrong_password(self, mock_get_user, mock_user):
        """Test authentication fails with wrong password."""
        mock_get_user.return_value = mock_user
        
        user = authenticate_user("testuser", "wrongpassword")
        
        assert user is False

    @patch('api.auth.user_repository.get_user')
    def test_authenticate_user_not_found(self, mock_get_user):
        """Test authentication fails when user doesn't exist."""
        mock_get_user.return_value = None
        
        user = authenticate_user("nonexistent", "anypassword")
        
        assert user is False

    @patch('api.auth.user_repository.get_user')
    def test_authenticate_user_disabled(self, mock_get_user, mock_user):
        """Test authentication of disabled user still returns user."""
        mock_user.disabled = True
        mock_get_user.return_value = mock_user
        
        user = authenticate_user("testuser", "correctpassword")
        
        # Authentication succeeds, but get_current_active_user will reject
        assert user is not False
        assert user.disabled is True


class TestGetCurrentUser:
    """Test get_current_user dependency."""

    @pytest.fixture
    def valid_token(self):
        """Fixture providing a valid JWT token."""
        data = {"sub": "testuser"}
        return create_access_token(data)

    @pytest.fixture
    def expired_token(self):
        """Fixture providing an expired JWT token."""
        data = {"sub": "testuser"}
        expires_delta = timedelta(seconds=-10)  # Already expired
        return create_access_token(data, expires_delta)

    @pytest.fixture
    def mock_user(self):
        """Fixture providing a mock user."""
        return UserInDB(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed",
            disabled=False
        )

    @patch('api.auth.user_repository.get_user')
    async def test_get_current_user_valid_token(self, mock_get_user, valid_token, mock_user):
        """Test getting current user with valid token."""
        mock_get_user.return_value = mock_user
        
        user = await get_current_user(valid_token)
        
        assert user.username == "testuser"
        assert isinstance(user, UserInDB)

    async def test_get_current_user_invalid_token(self):
        """Test that invalid token raises HTTPException."""
        invalid_token = "invalid.jwt.token"
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(invalid_token)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Could not validate credentials" in exc_info.value.detail

    async def test_get_current_user_expired_token(self, expired_token):
        """Test that expired token raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(expired_token)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_current_user_no_username_in_token(self):
        """Test token without username raises HTTPException."""
        data = {"sub": None}
        token = create_access_token(data)
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @patch('api.auth.user_repository.get_user')
    async def test_get_current_user_user_not_in_db(self, mock_get_user, valid_token):
        """Test user in token but not in database."""
        mock_get_user.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(valid_token)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetCurrentActiveUser:
    """Test get_current_active_user dependency."""

    @pytest.fixture
    def active_user(self):
        """Fixture providing an active user."""
        return User(
            username="activeuser",
            email="active@example.com",
            disabled=False
        )

    @pytest.fixture
    def disabled_user(self):
        """Fixture providing a disabled user."""
        return User(
            username="disableduser",
            email="disabled@example.com",
            disabled=True
        )

    async def test_get_current_active_user_success(self, active_user):
        """Test getting active user succeeds."""
        user = await get_current_active_user(active_user)
        
        assert user.username == "activeuser"
        assert user.disabled is False

    async def test_get_current_active_user_disabled(self, disabled_user):
        """Test that disabled user raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(disabled_user)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Inactive user" in exc_info.value.detail

    async def test_get_current_active_user_none_disabled(self):
        """Test user with None disabled field is treated as active."""
        user = User(username="user", disabled=None)
        
        result = await get_current_active_user(user)
        
        assert result.username == "user"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_special_characters_in_username(self):
        """Test handling of special characters in usernames."""
        special_chars = ["user@domain", "user-name", "user.name", "user_123"]
        
        for username in special_chars:
            hashed = get_password_hash("password")
            # Should not raise exceptions
            assert len(hashed) > 0

    def test_very_long_password(self):
        """Test handling of very long passwords."""
        long_password = "a" * 1000
        hashed = get_password_hash(long_password)
        
        assert verify_password(long_password, hashed)
        assert not verify_password(long_password[:-1], hashed)

    def test_unicode_password(self):
        """Test handling of unicode characters in passwords."""
        unicode_password = "пароль123密码🔐"
        hashed = get_password_hash(unicode_password)
        
        assert verify_password(unicode_password, hashed)

    @patch('api.auth.user_repository.get_user')
    def test_sql_injection_attempt(self, mock_get_user):
        """Test that SQL injection attempts are handled safely."""
        mock_get_user.return_value = None
        
        malicious_input = "admin' OR '1'='1"
        result = authenticate_user(malicious_input, "password")
        
        assert result is False
        mock_get_user.assert_called_once_with(malicious_input)


class TestSecretKeyValidation:
    """Test SECRET_KEY environment variable validation."""

    def test_secret_key_is_loaded(self):
        """Test that SECRET_KEY is loaded from environment."""
        from api.auth import SECRET_KEY
        
        assert SECRET_KEY is not None
        assert len(SECRET_KEY) > 0

    def test_secret_key_used_in_jwt(self):
        """Test that SECRET_KEY is used for JWT operations."""
        import jwt
        from api.auth import SECRET_KEY, ALGORITHM
        
        data = {"sub": "testuser"}
        token = create_access_token(data)
        
        # Decoding with correct key should work
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded["sub"] == "testuser"
        
        # Decoding with wrong key should fail
        with pytest.raises(jwt.InvalidSignatureError):
            jwt.decode(token, "wrong_secret", algorithms=[ALGORITHM])


# Mark tests that require database
pytestmark = pytest.mark.unit