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
from unittest.mock import Mock, patch

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
        """
        Provide a fresh UserRepository instance for tests.
        
        Returns:
            repo (UserRepository): A new UserRepository instance for use in a test.
        """
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
        from api.auth import SECRET_KEY, ALGORITHM
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    
        assert "exp" in decoded
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
        """
        Provides a mock UserInDB for tests.
        
        Returns:
            UserInDB: A mock user with username "testuser", email "test@example.com", full_name "Test User", a hashed password for "correctpassword", and disabled set to False.
        """
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
        """
        Provide a JWT access token with the subject "testuser".

        Returns:
            token (str): A JWT access token string whose `sub` claim equals "testuser".
        """
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
        """
        Create a mock UserInDB instance for tests.

        Returns:
            UserInDB: A user with username "testuser", email "test@example.com", hashed_password "hashed", and disabled=False.
        """
        return UserInDB(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed",
            disabled=False,
        )

    @patch("api.auth.user_repository.get_user")
    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self, mock_get_user, valid_token, mock_user):
        """Test getting current user with valid token."""
        mock_get_user.return_value = mock_user

        user = await get_current_user(valid_token)

        assert user.username == "testuser"
        assert isinstance(user, UserInDB)
class TestGetCurrentUser:
    """Test get_current_user dependency."""

    @pytest.fixture
    def valid_token(self):
        """
        Provide a JWT access token with the subject "testuser".

        Returns:
            token (str): A JWT access token string whose `sub` claim equals "testuser".
        """
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
        """
        Create a mock UserInDB instance for tests.

        Returns:
            UserInDB: A user with username "testuser", email "test@example.com", hashed_password "hashed", and disabled=False.
        """
        return UserInDB(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed",
            disabled=False,
        )

    @patch("api.auth.user_repository.get_user")
    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self, mock_get_user, valid_token, mock_user):
        """Test getting current user with valid token."""
        mock_get_user.return_value = mock_user

        user = await get_current_user(valid_token)

        assert user.username == "testuser"
        assert isinstance(user, UserInDB)

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self):
        """Test that invalid token raises HTTPException."""
        invalid_token = "invalid.jwt.token"

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(invalid_token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Could not validate credentials" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token(self, expired_token):
        """Test that expired token raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(expired_token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_current_user_no_username_in_token(self):
        """Test token without username raises HTTPException."""
        data = {"sub": None}
        token = create_access_token(data)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetCurrentActiveUser:
    """Test get_current_active_user dependency."""

    @pytest.fixture
    def active_user(self):
        """Fixture providing an active user."""
        return User(
            username="activeuser",
            email="active@example.com",
            disabled=False,
        )

    @pytest.fixture
    def disabled_user(self):
        """
        Provides a disabled User model instance for tests.

        Returns:
            User: A User with username "disableduser", email "disabled@example.com", and `disabled` set to True.
        """
        return User(
            username="disableduser",
            email="disabled@example.com",
            disabled=True,
        )

    @pytest.mark.asyncio
    async def test_get_current_active_user_success(self, active_user):
        """Test getting active user succeeds."""
        user = await get_current_active_user(active_user)

        assert user.username == "activeuser"
        assert user.disabled is False

    @pytest.mark.asyncio
    async def test_get_current_active_user_disabled(self, disabled_user):
        """Test that disabled user raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(disabled_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Inactive user" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_active_user_none_disabled(self):
        """Test user with None disabled field is treated as active."""
        user = User(username="user", disabled=None)

        result = await get_current_active_user(user)

        assert result.username == "user"
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
        """
        Provides a disabled User model instance for tests.
        
        Returns:
            User: A User with username "disableduser", email "disabled@example.com", and `disabled` set to True.
        """
        return User(
            username="disableduser",
            email="disabled@example.com",
            disabled=True
        )

    @pytest.mark.asyncio
    async def test_get_current_active_user_success(self, active_user):
        """Test getting active user succeeds."""
        user = await get_current_active_user(active_user)
        
        assert user.username == "activeuser"
        assert user.disabled is False

    `@pytest.mark.asyncio`
    async def test_get_current_active_user_disabled(self, disabled_user):
        """Test that disabled user raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(disabled_user)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Inactive user" in exc_info.value.detail

    `@pytest.mark.asyncio`
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

class TestUserRepositoryParameterNameChanges:
    """Test UserRepository with new parameter names (email, full_name, disabled)."""

    @patch('api.auth.execute')
    @patch('api.auth.fetch_one')
    def test_create_or_update_user_with_new_parameter_names(self, mock_fetch, mock_execute):
        """Test create_or_update_user uses new parameter names correctly."""
        repository = UserRepository()
        
        repository.create_or_update_user(
            username="testuser",
            hashed_password="hashed_pass",
            email="test@example.com",
            full_name="Test User",
            disabled=False
        )
        
        # Verify execute was called with correct parameters
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args
        assert "testuser" in call_args[0][1]
        assert "test@example.com" in call_args[0][1]
        assert "Test User" in call_args[0][1]
        assert "hashed_pass" in call_args[0][1]
        assert 0 in call_args[0][1]  # disabled=False should be 0

    @patch('api.auth.execute')
    def test_create_or_update_user_disabled_true(self, mock_execute):
        """Test that disabled=True is converted to 1."""
        repository = UserRepository()
        
        repository.create_or_update_user(
            username="disableduser",
            hashed_password="hashed",
            disabled=True
        )
        
        call_args = mock_execute.call_args[0][1]
        assert 1 in call_args  # disabled=True should be 1

    @patch('api.auth.execute')
    def test_create_or_update_user_with_none_optionals(self, mock_execute):
        """Test create_or_update_user with None for optional fields."""
        repository = UserRepository()
        
        repository.create_or_update_user(
            username="minimaluser",
            hashed_password="hash",
            email=None,
            full_name=None,
            disabled=False
        )
        
        call_args = mock_execute.call_args[0][1]
        assert None in call_args  # email and full_name should be None

    @patch('api.auth.execute')
    def test_create_or_update_user_minimal_kwargs(self, mock_execute):
        """Test create_or_update_user with only required parameters."""
        repository = UserRepository()
        
        repository.create_or_update_user(
            username="minimal",
            hashed_password="hash"
        )
        
        # Should use default values for optional parameters
        mock_execute.assert_called_once()


class TestUserRepositoryInstanceMethods:
    """Test that UserRepository methods are now instance methods."""

    def test_get_user_is_instance_method(self):
        """Test that get_user is an instance method."""
        repository = UserRepository()
        assert hasattr(repository, 'get_user')
        assert callable(repository.get_user)

    def test_has_users_is_instance_method(self):
        """Test that has_users is an instance method."""
        repository = UserRepository()
        assert hasattr(repository, 'has_users')
        assert callable(repository.has_users)

    def test_create_or_update_user_is_instance_method(self):
        """Test that create_or_update_user is an instance method."""
        repository = UserRepository()
        assert hasattr(repository, 'create_or_update_user')
        assert callable(repository.create_or_update_user)

    @patch('api.auth.fetch_one')
    def test_multiple_repository_instances_independent(self, mock_fetch):
        """Test that multiple UserRepository instances work independently."""
        mock_fetch.return_value = None
        
        repo1 = UserRepository()
        repo2 = UserRepository()
        
        # Both should work independently
        result1 = repo1.get_user("user1")
        result2 = repo2.get_user("user2")
        
        assert result1 is None
        assert result2 is None
        assert mock_fetch.call_count == 2


class TestUserInDBSeparateClass:
    """Test UserInDB as a separate class inheriting from User."""

    def test_userindb_inherits_from_user(self):
        """Test that UserInDB inherits from User."""
        assert issubclass(UserInDB, User)

    def test_userindb_has_hashed_password(self):
        """Test that UserInDB has hashed_password field."""
        user = UserInDB(
            username="test",
            hashed_password="hash123"
        )
        assert user.hashed_password == "hash123"

    def test_userindb_has_user_fields(self):
        """Test that UserInDB has all User fields."""
        user = UserInDB(
            username="test",
            email="test@example.com",
            full_name="Test User",
            disabled=False,
            hashed_password="hash"
        )
        assert user.username == "test"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.disabled is False

    def test_userindb_optional_fields_default_none(self):
        """Test that optional fields default to None."""
        user = UserInDB(username="test", hashed_password="hash")
        assert user.email is None
        assert user.full_name is None
        assert user.disabled is None

    def test_userindb_can_convert_to_user(self):
        """Test that UserInDB can be converted to User."""
        user_in_db = UserInDB(
            username="test",
            email="test@example.com",
            full_name="Test User",
            disabled=False,
            hashed_password="secret"
        )
        
        # Convert to User (without hashed_password)
        user_dict = user_in_db.dict(exclude={'hashed_password'})
        user = User(**user_dict)
        
        assert user.username == user_in_db.username
        assert user.email == user_in_db.email
        assert user.full_name == user_in_db.full_name
        assert user.disabled == user_in_db.disabled


class TestPasswordHashingEdgeCases:
    """Additional edge cases for password hashing."""

    def test_hash_empty_string(self):
        """Test hashing an empty string."""
        hashed = get_password_hash("")
        assert len(hashed) > 0
        assert verify_password("", hashed)

    def test_hash_very_long_password(self):
        """Test hashing a very long password (10KB)."""
        long_pass = "a" * 10000
        hashed = get_password_hash(long_pass)
        assert verify_password(long_pass, hashed)

    def test_hash_special_characters(self):
        """Test hashing passwords with various special characters."""
        special_passwords = [
            "!@#$%^&*()",
            "password\n\r\t",
            "pass\x00word",
            "🔐🔑🗝️",
            "Москва",
            "北京",
            "مرحبا"
        ]
        
        for pwd in special_passwords:
            hashed = get_password_hash(pwd)
            assert verify_password(pwd, hashed), f"Failed for password: {pwd}"

    def test_verify_with_corrupted_hash(self):
        """Test verification with corrupted hash."""
        password = "testpass"
        hashed = get_password_hash(password)
        
        # Corrupt the hash
        corrupted = hashed[:-5] + "xxxxx"
        assert not verify_password(password, corrupted)

    def test_hash_deterministic_salting(self):
        """Test that same password produces different hashes (salted)."""
        password = "test123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        # Hashes should be different due to salt
        assert hash1 != hash2
        # But both should verify
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)


class TestSeedCredentialsParameterNameChanges:
    """Test _seed_credentials_from_env with new parameter names."""

    @patch.dict(os.environ, {
        'ADMIN_USERNAME': 'admin',
        'ADMIN_PASSWORD': 'adminpass',
        'ADMIN_EMAIL': 'admin@example.com',
        'ADMIN_FULL_NAME': 'Admin User',
        'ADMIN_DISABLED': 'false'
    })
    @patch('api.auth.get_password_hash')
    def test_seed_uses_new_parameter_names(self, mock_hash):
        """Test that _seed_credentials_from_env uses new parameter names."""
        mock_hash.return_value = "hashed_adminpass"
        mock_repo = Mock(spec=UserRepository)
        
        from api.auth import _seed_credentials_from_env
        _seed_credentials_from_env(mock_repo)
        
        # Verify create_or_update_user was called with new parameter names
        mock_repo.create_or_update_user.assert_called_once_with(
            username='admin',
            hashed_password='hashed_adminpass',
            email='admin@example.com',
            full_name='Admin User',
            disabled=False
        )

    @patch.dict(os.environ, {
        'ADMIN_USERNAME': 'admin',
        'ADMIN_PASSWORD': 'pass',
        'ADMIN_DISABLED': 'true'
    })
    @patch('api.auth.get_password_hash')
    def test_seed_disabled_true(self, mock_hash):
        """Test seeding with ADMIN_DISABLED=true."""
        mock_hash.return_value = "hashed"
        mock_repo = Mock(spec=UserRepository)
        
        from api.auth import _seed_credentials_from_env
        _seed_credentials_from_env(mock_repo)
        
        call_kwargs = mock_repo.create_or_update_user.call_args[1]
        assert call_kwargs['disabled'] is True

    @patch.dict(os.environ, {
        'ADMIN_USERNAME': 'admin',
        'ADMIN_PASSWORD': 'pass',
        'ADMIN_DISABLED': '1'
    })
    @patch('api.auth.get_password_hash')
    def test_seed_disabled_numeric_true(self, mock_hash):
        """Test seeding with ADMIN_DISABLED=1."""
        mock_hash.return_value = "hashed"
        mock_repo = Mock(spec=UserRepository)
        
        from api.auth import _seed_credentials_from_env
        _seed_credentials_from_env(mock_repo)
        
        call_kwargs = mock_repo.create_or_update_user.call_args[1]
        assert call_kwargs['disabled'] is True


class TestIsTruthyAdditionalCases:
    """Additional test cases for _is_truthy helper."""

    def test_mixed_case_combinations(self):
        """Test various mixed case combinations."""
        truthy_cases = [
            "TrUe", "tRuE", "TRUE", "true",
            "YeS", "yEs", "YES", "yes",
            "On", "oN", "ON", "on"
        ]
        for value in truthy_cases:
            assert _is_truthy(value), f"Failed for {value}"

    def test_numeric_strings(self):
        """Test numeric string handling."""
        assert _is_truthy("1")
        assert not _is_truthy("0")
        assert not _is_truthy("2")
        assert not _is_truthy("-1")
        assert not _is_truthy("1.0")

    def test_whitespace_variations(self):
        """Test whitespace handling."""
        assert not _is_truthy("  ")
        assert not _is_truthy("\t\t")
        assert not _is_truthy("\n\n")
        assert not _is_truthy("   ")

    def test_truthy_with_surrounding_whitespace(self):
        """Test that whitespace around truthy values matters."""
        # These should NOT be truthy (whitespace is not stripped by _is_truthy)
        assert not _is_truthy(" true")
        assert not _is_truthy("true ")
        assert not _is_truthy(" 1 ")

    def test_partial_matches(self):
        """Test that partial matches don't count."""
        assert not _is_truthy("truex")
        assert not _is_truthy("xtrue")
        assert not _is_truthy("yes!")
        assert not _is_truthy("!yes")


class TestAuthenticationEdgeCases:
    """Additional edge cases for authentication flow."""

    @patch('api.auth.user_repository.get_user')
    def test_authenticate_with_empty_password(self, mock_get_user):
        """Test authentication with empty password."""
        mock_user = UserInDB(
            username="test",
            hashed_password=get_password_hash("realpass")
        )
        mock_get_user.return_value = mock_user
        
        result = authenticate_user("test", "")
        assert result is False

    @patch('api.auth.user_repository.get_user')
    def test_authenticate_with_none_password(self, mock_get_user):
        """Test authentication with None password raises appropriate error."""
        mock_get_user.return_value = UserInDB(
            username="test",
            hashed_password="hash"
        )
        
        # verify_password should handle None gracefully or raise
        try:
            result = authenticate_user("test", None)
            # If it doesn't raise, it should return False
            assert result is False
        except (TypeError, AttributeError):
            # It's acceptable to raise for None password
            pass

    @patch('api.auth.user_repository.get_user')
    def test_authenticate_nonexistent_user_case_sensitive(self, mock_get_user):
        """Test that username lookup is case-sensitive."""
        mock_get_user.return_value = None
        
        result = authenticate_user("Admin", "password")
        assert result is False
        
        # Verify it was called with exact case
        mock_get_user.assert_called_with("Admin")


class TestTokenCreationEdgeCases:
    """Additional edge cases for token creation."""

    def test_create_token_with_empty_data(self):
        """Test creating token with empty data dict."""
        token = create_access_token(data={})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_token_with_special_characters_in_data(self):
        """Test token creation with special characters in data."""
        data = {
            "sub": "user@example.com",
            "custom": "value with spaces & special!@#"
        }
        token = create_access_token(data)
        assert isinstance(token, str)

    def test_create_token_with_unicode_data(self):
        """Test token creation with unicode data."""
        data = {"sub": "用户名", "name": "Имя"}
        token = create_access_token(data)
        assert isinstance(token, str)

    def test_create_token_with_very_long_expiry(self):
        """Test creating token with very long expiry."""
        delta = timedelta(days=365 * 10)  # 10 years
        token = create_access_token({"sub": "test"}, expires_delta=delta)
        assert isinstance(token, str)

    def test_create_token_with_negative_expiry(self):
        """Test creating token with negative expiry (already expired)."""
        delta = timedelta(minutes=-30)
        token = create_access_token({"sub": "test"}, expires_delta=delta)
        
        # Token should be created but immediately expired
        with pytest.raises(ExpiredSignatureError):
            import jwt
            from api.auth import SECRET_KEY, ALGORITHM
            jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


class TestGetCurrentUserEdgeCases:
    """Additional edge cases for get_current_user."""

    @pytest.mark.asyncio
    async def test_get_current_user_with_malformed_token(self):
        """Test get_current_user with malformed token."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("not.a.valid.jwt.token.format.here")
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_current_user_with_empty_token(self):
        """Test get_current_user with empty token."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("")
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    @patch('api.auth.user_repository.get_user')
    async def test_get_current_user_token_missing_sub(self, mock_get_user):
        """Test get_current_user with token missing 'sub' claim."""
        import jwt
        from api.auth import SECRET_KEY, ALGORITHM
        
        # Create token without 'sub'
        token_data = {"exp": datetime.utcnow() + timedelta(minutes=30)}
        token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


# Additional integration-style tests
class TestAuthenticationIntegrationFlow:
    """Test complete authentication flow with all components."""

    @patch('api.auth.execute')
    @patch('api.auth.fetch_one')
    def test_full_user_registration_and_auth_flow(self, mock_fetch, mock_execute):
        """Test complete flow: create user, authenticate, get user."""
        # Step 1: Create user
        repository = UserRepository()
        plain_password = "secure_password_123"
        hashed = get_password_hash(plain_password)
        
        repository.create_or_update_user(
            username="newuser",
            hashed_password=hashed,
            email="new@example.com",
            full_name="New User",
            disabled=False
        )
        
        # Step 2: Simulate retrieval
        mock_fetch.return_value = {
            "username": "newuser",
            "email": "new@example.com",
            "full_name": "New User",
            "hashed_password": hashed,
            "disabled": 0
        }
        
        retrieved_user = repository.get_user("newuser")
        assert retrieved_user is not None
        assert retrieved_user.username == "newuser"
        
        # Step 3: Authenticate
        authenticated = authenticate_user("newuser", plain_password)
        assert authenticated is not False
        assert authenticated.username == "newuser"

    @patch('api.auth.fetch_one')
    def test_disabled_user_cannot_become_active_user(self, mock_fetch):
        """Test that disabled users are filtered out."""
        mock_fetch.return_value = {
            "username": "disabled_user",
            "email": "test@test.com",
            "full_name": "Disabled",
            "hashed_password": "hash",
            "disabled": 1
        }
        
        repository = UserRepository()
        user = repository.get_user("disabled_user")
        
        # User exists but is disabled
        assert user is not None
        assert user.disabled is True

