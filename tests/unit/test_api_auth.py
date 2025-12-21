"""Comprehensive unit tests for api/auth.py authentication and authorization module.

This module provides extensive test coverage for:
- User model validation and structure
- Password hashing and verification
- JWT token creation and validation
- User repository operations (CRUD)
- Authentication flows
- Environment variable seeding
- Token expiration handling
- Security edge cases
"""

import os
import sqlite3
import time
from datetime import timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi import HTTPException
from jose import jwt

from api.auth import (
    SECRET_KEY,
    ALGORITHM,
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
    get_user,
    verify_password,
    _seed_credentials_from_env,
)


class TestIsTruthy:
    """Test the _is_truthy helper function for boolean string evaluation."""

    def test_is_truthy_with_true_lowercase(self):
        """Test that 'true' (lowercase) is recognized as truthy."""
        assert _is_truthy('true') is True

    def test_is_truthy_with_true_uppercase(self):
        """Test that 'TRUE' (uppercase) is recognized as truthy."""
        assert _is_truthy('TRUE') is True

    def test_is_truthy_with_true_mixedcase(self):
        """Test that 'TrUe' (mixed case) is recognized as truthy."""
        assert _is_truthy('TrUe') is True

    def test_is_truthy_with_one(self):
        """Test that '1' is recognized as truthy."""
        assert _is_truthy('1') is True

    def test_is_truthy_with_yes_lowercase(self):
        """Test that 'yes' is recognized as truthy."""
        assert _is_truthy('yes') is True

    def test_is_truthy_with_yes_uppercase(self):
        """Test that 'YES' is recognized as truthy."""
        assert _is_truthy('YES') is True

    def test_is_truthy_with_on(self):
        """Test that 'on' is recognized as truthy."""
        assert _is_truthy('on') is True

    def test_is_truthy_with_on_uppercase(self):
        """Test that 'ON' is recognized as truthy."""
        assert _is_truthy('ON') is True

    def test_is_truthy_with_false(self):
        """Test that 'false' is recognized as falsy."""
        assert _is_truthy('false') is False

    def test_is_truthy_with_zero(self):
        """Test that '0' is recognized as falsy."""
        assert _is_truthy('0') is False

    def test_is_truthy_with_no(self):
        """Test that 'no' is recognized as falsy."""
        assert _is_truthy('no') is False

    def test_is_truthy_with_off(self):
        """Test that 'off' is recognized as falsy."""
        assert _is_truthy('off') is False

    def test_is_truthy_with_none(self):
        """Test that None is recognized as falsy."""
        assert _is_truthy(None) is False

    def test_is_truthy_with_empty_string(self):
        """Test that empty string is recognized as falsy."""
        assert _is_truthy('') is False

    def test_is_truthy_with_whitespace_string(self):
        """Test that whitespace-only string is recognized as falsy."""
        assert _is_truthy('   ') is False

    def test_is_truthy_with_random_string(self):
        """Test that arbitrary strings are recognized as falsy."""
        assert _is_truthy('random') is False
        assert _is_truthy('enabled') is False


class TestUserModels:
    """Test Pydantic user models for structure and validation."""

    def test_token_model_structure(self):
        """Test Token model has correct fields."""
        token = Token(access_token="test_token", token_type="bearer")
        assert token.access_token == "test_token"
        assert token.token_type == "bearer"

    def test_token_data_model_structure(self):
        """Test TokenData model with username."""
        token_data = TokenData(username="testuser")
        assert token_data.username == "testuser"

    def test_token_data_model_optional_username(self):
        """Test TokenData allows None username."""
        token_data = TokenData(username=None)
        assert token_data.username is None

    def test_user_model_basic_fields(self):
        """Test User model with required fields."""
        user = User(username="testuser", email="test@example.com")
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name is None
        assert user.disabled is False

    def test_user_model_all_fields(self):
        """Test User model with all fields populated."""
        user = User(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            disabled=True
        )
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.disabled is True

    def test_user_model_optional_email(self):
        """Test User model allows None email."""
        user = User(username="testuser", email=None)
        assert user.username == "testuser"
        assert user.email is None

    def test_user_in_db_inherits_from_user(self):
        """Test UserInDB includes hashed_password."""
        user_in_db = UserInDB(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_pwd_123"
        )
        assert user_in_db.username == "testuser"
        assert user_in_db.email == "test@example.com"
        assert user_in_db.hashed_password == "hashed_pwd_123"


class TestPasswordHashing:
    """Test password hashing and verification functions."""

    def test_get_password_hash_returns_string(self):
        """Test password hashing returns a string."""
        hashed = get_password_hash("mypassword")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_get_password_hash_different_for_same_password(self):
        """Test same password produces different hashes (salt)."""
        hash1 = get_password_hash("mypassword")
        hash2 = get_password_hash("mypassword")
        # Due to salting, hashes should be different
        assert hash1 != hash2

    def test_verify_password_correct_password(self):
        """Test password verification with correct password."""
        password = "correct_password"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect_password(self):
        """Test password verification with incorrect password."""
        password = "correct_password"
        hashed = get_password_hash(password)
        assert verify_password("wrong_password", hashed) is False

    def test_verify_password_empty_password(self):
        """Test password verification with empty password."""
        password = "correct_password"
        hashed = get_password_hash(password)
        assert verify_password("", hashed) is False

    def test_verify_password_special_characters(self):
        """Test password hashing and verification with special characters."""
        password = "P@ssw0rd!#$%^&*()"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_unicode_characters(self):
        """Test password hashing with unicode characters."""
        password = "pässwörd123密码"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_very_long_password(self):
        """Test password hashing with very long password."""
        password = "a" * 1000
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True


class TestUserRepository:
    """Test UserRepository database operations."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database for testing."""
        db_path = tmp_path / "test_auth.db"
        with patch.dict(os.environ, {"DATABASE_URL": f"sqlite:///{db_path}"}):
            # Import after patching environment
            import api.database as db_module
            db_module.initialize_schema()
            yield db_module
            # Cleanup
            if db_path.exists():
                db_path.unlink()

    @pytest.fixture
    def repo(self, temp_db):
        """Create a UserRepository instance for testing."""
        return UserRepository()

    def test_repository_initialization(self, repo):
        """Test UserRepository can be instantiated."""
        assert repo is not None
        assert hasattr(repo, 'get_user')
        assert hasattr(repo, 'has_users')
        assert hasattr(repo, 'upsert_user')

    def test_get_user_nonexistent(self, repo):
        """Test getting a user that doesn't exist returns None."""
        user = repo.get_user("nonexistent_user")
        assert user is None

    def test_upsert_user_creates_new_user(self, repo):
        """Test upserting a new user creates the record."""
        repo.upsert_user(
            username="newuser",
            hashed_password="hashed123",
            email="new@example.com",
            full_name="New User",
            disabled=False
        )
        user = repo.get_user("newuser")
        assert user is not None
        assert user.username == "newuser"
        assert user.email == "new@example.com"
        assert user.full_name == "New User"
        assert user.disabled is False

    def test_upsert_user_updates_existing_user(self, repo):
        """Test upserting existing user updates the record."""
        # Create initial user
        repo.upsert_user(
            username="testuser",
            hashed_password="hash1",
            email="old@example.com"
        )
        
        # Update the user
        repo.upsert_user(
            username="testuser",
            hashed_password="hash2",
            email="new@example.com",
            full_name="Updated Name"
        )
        
        user = repo.get_user("testuser")
        assert user is not None
        assert user.email == "new@example.com"
        assert user.full_name == "Updated Name"

    def test_has_users_empty_database(self, repo):
        """Test has_users returns False for empty database."""
        assert repo.has_users() is False

    def test_has_users_with_users(self, repo):
        """Test has_users returns True when users exist."""
        repo.upsert_user(
            username="testuser",
            hashed_password="hash123"
        )
        assert repo.has_users() is True

    def test_upsert_user_with_minimal_fields(self, repo):
        """Test upserting user with only required fields."""
        repo.upsert_user(
            username="minimaluser",
            hashed_password="hash123"
        )
        user = repo.get_user("minimaluser")
        assert user is not None
        assert user.username == "minimaluser"
        assert user.email is None
        assert user.full_name is None

    def test_upsert_user_disabled_flag(self, repo):
        """Test upserting user with disabled flag."""
        repo.upsert_user(
            username="disableduser",
            hashed_password="hash123",
            disabled=True
        )
        user = repo.get_user("disableduser")
        assert user is not None
        assert user.disabled is True

    def test_get_user_returns_user_in_db_model(self, repo):
        """Test get_user returns UserInDB instance."""
        repo.upsert_user(
            username="testuser",
            hashed_password="hash123"
        )
        user = repo.get_user("testuser")
        assert isinstance(user, UserInDB)
        assert hasattr(user, 'hashed_password')


class TestSeedCredentialsFromEnv:
    """Test environment variable credential seeding."""

    def test_seed_with_admin_credentials(self, tmp_path):
        """Test seeding admin credentials from environment."""
        db_path = tmp_path / "test_seed.db"
        with patch.dict(os.environ, {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD": "adminpass",
            "ADMIN_EMAIL": "admin@example.com",
            "ADMIN_FULL_NAME": "Admin User"
        }):
            import api.database as db_module
            db_module.initialize_schema()
            
            repo = UserRepository()
            _seed_credentials_from_env(repo)
            
            user = repo.get_user("admin")
            assert user is not None
            assert user.username == "admin"
            assert user.email == "admin@example.com"
            assert user.full_name == "Admin User"

    def test_seed_without_credentials_does_nothing(self, tmp_path):
        """Test seeding without credentials doesn't create users."""
        db_path = tmp_path / "test_no_seed.db"
        with patch.dict(os.environ, {
            "DATABASE_URL": f"sqlite:///{db_path}"
        }, clear=True):
            import api.database as db_module
            db_module.initialize_schema()
            
            repo = UserRepository()
            _seed_credentials_from_env(repo)
            
            assert repo.has_users() is False

    def test_seed_with_disabled_flag_true(self, tmp_path):
        """Test seeding with ADMIN_DISABLED=true."""
        db_path = tmp_path / "test_disabled.db"
        with patch.dict(os.environ, {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD": "adminpass",
            "ADMIN_DISABLED": "true"
        }):
            import api.database as db_module
            db_module.initialize_schema()
            
            repo = UserRepository()
            _seed_credentials_from_env(repo)
            
            user = repo.get_user("admin")
            assert user is not None
            assert user.disabled is True

    def test_seed_with_disabled_flag_false(self, tmp_path):
        """Test seeding with ADMIN_DISABLED=false."""
        db_path = tmp_path / "test_enabled.db"
        with patch.dict(os.environ, {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD": "adminpass",
            "ADMIN_DISABLED": "false"
        }):
            import api.database as db_module
            db_module.initialize_schema()
            
            repo = UserRepository()
            _seed_credentials_from_env(repo)
            
            user = repo.get_user("admin")
            assert user is not None
            assert user.disabled is False


class TestGetUser:
    """Test the get_user convenience function."""

    @pytest.fixture
    def mock_repo(self):
        """Create a mock UserRepository."""
        repo = Mock(spec=UserRepository)
        return repo

    def test_get_user_with_default_repository(self, mock_repo):
        """Test get_user uses default repository when none provided."""
        mock_user = UserInDB(
            username="testuser",
            email="test@example.com",
            hashed_password="hash123"
        )
        mock_repo.get_user.return_value = mock_user
        
        with patch('api.auth.user_repository', mock_repo):
            user = get_user("testuser")
            assert user == mock_user
            mock_repo.get_user.assert_called_once_with("testuser")

    def test_get_user_with_custom_repository(self, mock_repo):
        """Test get_user with explicitly provided repository."""
        mock_user = UserInDB(
            username="testuser",
            email="test@example.com",
            hashed_password="hash123"
        )
        mock_repo.get_user.return_value = mock_user
        
        user = get_user("testuser", repository=mock_repo)
        assert user == mock_user
        mock_repo.get_user.assert_called_once_with("testuser")

    def test_get_user_nonexistent_returns_none(self, mock_repo):
        """Test get_user returns None for nonexistent user."""
        mock_repo.get_user.return_value = None
        
        user = get_user("nonexistent", repository=mock_repo)
        assert user is None


class TestAuthenticateUser:
    """Test user authentication function."""

    @pytest.fixture
    def mock_repo(self):
        """Create a mock repository with a test user."""
        repo = Mock(spec=UserRepository)
        hashed = get_password_hash("correct_password")
        mock_user = UserInDB(
            username="testuser",
            email="test@example.com",
            hashed_password=hashed,
            disabled=False
        )
        repo.get_user.return_value = mock_user
        return repo

    def test_authenticate_user_correct_credentials(self, mock_repo):
        """Test authentication with correct credentials."""
        user = authenticate_user("testuser", "correct_password", repository=mock_repo)
        assert user is not False
        assert user.username == "testuser"

    def test_authenticate_user_wrong_password(self, mock_repo):
        """Test authentication with wrong password returns False."""
        user = authenticate_user("testuser", "wrong_password", repository=mock_repo)
        assert user is False

    def test_authenticate_user_nonexistent_user(self):
        """Test authentication with nonexistent user returns False."""
        repo = Mock(spec=UserRepository)
        repo.get_user.return_value = None
        
        user = authenticate_user("nonexistent", "any_password", repository=repo)
        assert user is False

    def test_authenticate_user_empty_password(self, mock_repo):
        """Test authentication with empty password returns False."""
        user = authenticate_user("testuser", "", repository=mock_repo)
        assert user is False

    def test_authenticate_user_special_characters_in_password(self):
        """Test authentication with special characters in password."""
        repo = Mock(spec=UserRepository)
        password = "P@ssw0rd!#$"
        hashed = get_password_hash(password)
        mock_user = UserInDB(
            username="testuser",
            email="test@example.com",
            hashed_password=hashed
        )
        repo.get_user.return_value = mock_user
        
        user = authenticate_user("testuser", password, repository=repo)
        assert user is not False
        assert user.username == "testuser"


class TestCreateAccessToken:
    """Test JWT token creation."""

    def test_create_access_token_basic(self):
        """Test creating a token with basic data."""
        data = {"sub": "testuser"}
        token = create_access_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Decode and verify
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"
        assert "exp" in payload

    def test_create_access_token_with_custom_expiry(self):
        """Test creating a token with custom expiration."""
        data = {"sub": "testuser"}
        expires_delta = timedelta(minutes=1)
        token = create_access_token(data, expires_delta=expires_delta)
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"
        assert "exp" in payload

    def test_create_access_token_includes_expiry(self):
        """Test that created token includes expiry claim."""
        data = {"sub": "testuser", "role": "admin"}
        token = create_access_token(data)
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload
        assert payload["exp"] > time.time()

    def test_create_access_token_preserves_custom_claims(self):
        """Test that custom claims are preserved in token."""
        data = {"sub": "testuser", "role": "admin", "scope": "read:write"}
        token = create_access_token(data)
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"
        assert payload["role"] == "admin"
        assert payload["scope"] == "read:write"

    def test_create_access_token_default_expiration(self):
        """Test that default expiration is set correctly."""
        data = {"sub": "testuser"}
        token = create_access_token(data)
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp_time = payload["exp"]
        current_time = time.time()
        
        # Should expire in approximately 15 minutes (default)
        time_diff = exp_time - current_time
        assert 14 * 60 < time_diff < 16 * 60  # 14-16 minutes


class TestGetCurrentUser:
    """Test JWT token validation and current user extraction."""

    @pytest.fixture
    def valid_token(self):
        """Create a valid JWT token for testing."""
        data = {"sub": "testuser"}
        return create_access_token(data)

    @pytest.fixture
    def mock_get_user(self):
        """Mock the get_user function."""
        mock_user = User(
            username="testuser",
            email="test@example.com",
            disabled=False
        )
        with patch('api.auth.get_user', return_value=mock_user) as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self, valid_token, mock_get_user):
        """Test getting current user with valid token."""
        user = await get_current_user(valid_token)
        assert user.username == "testuser"
        mock_get_user.assert_called_once_with("testuser")

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self):
        """Test getting current user with invalid token raises exception."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("invalid_token")
        
        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token(self):
        """Test getting current user with expired token raises exception."""
        data = {"sub": "testuser"}
        # Create token that expires immediately
        expired_token = create_access_token(data, expires_delta=timedelta(seconds=-1))
        
        # Wait a moment to ensure expiration
        time.sleep(0.1)
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(expired_token)
        
        assert exc_info.value.status_code == 401
        assert "Token has expired" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_missing_subject(self):
        """Test token without subject claim raises exception."""
        # Create token without 'sub' claim
        data = {"role": "admin"}
        token = jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token)
        
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_nonexistent_user(self, valid_token):
        """Test token for nonexistent user raises exception."""
        with patch('api.auth.get_user', return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(valid_token)
            
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_empty_token(self):
        """Test empty token raises exception."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("")
        
        assert exc_info.value.status_code == 401


class TestGetCurrentActiveUser:
    """Test active user validation."""

    @pytest.mark.asyncio
    async def test_get_current_active_user_enabled_user(self):
        """Test getting active user for enabled account."""
        active_user = User(
            username="testuser",
            email="test@example.com",
            disabled=False
        )
        
        result = await get_current_active_user(active_user)
        assert result == active_user

    @pytest.mark.asyncio
    async def test_get_current_active_user_disabled_user(self):
        """Test getting active user for disabled account raises exception."""
        disabled_user = User(
            username="disableduser",
            email="disabled@example.com",
            disabled=True
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(disabled_user)
        
        assert exc_info.value.status_code == 400
        assert "Inactive user" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_active_user_preserves_user_data(self):
        """Test that user data is preserved when validation passes."""
        user = User(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            disabled=False
        )
        
        result = await get_current_active_user(user)
        assert result.username == "testuser"
        assert result.email == "test@example.com"
        assert result.full_name == "Test User"


class TestIntegrationScenarios:
    """Integration tests for complete authentication workflows."""

    @pytest.fixture
    def setup_db(self, tmp_path):
        """Set up a test database with a user."""
        db_path = tmp_path / "test_integration.db"
        with patch.dict(os.environ, {"DATABASE_URL": f"sqlite:///{db_path}"}):
            import api.database as db_module
            db_module.initialize_schema()
            
            repo = UserRepository()
            hashed = get_password_hash("testpassword")
            repo.upsert_user(
                username="integrationuser",
                hashed_password=hashed,
                email="integration@example.com",
                disabled=False
            )
            
            yield repo

    def test_full_authentication_flow(self, setup_db):
        """Test complete authentication flow from credentials to user."""
        repo = setup_db
        
        # Authenticate user
        authenticated = authenticate_user("integrationuser", "testpassword", repository=repo)
        assert authenticated is not False
        assert authenticated.username == "integrationuser"
        
        # Create token
        token_data = {"sub": authenticated.username}
        token = create_access_token(token_data)
        assert isinstance(token, str)
        
        # Verify token can be decoded
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "integrationuser"

    def test_failed_authentication_flow(self, setup_db):
        """Test authentication flow with wrong credentials."""
        repo = setup_db
        
        # Attempt authentication with wrong password
        authenticated = authenticate_user("integrationuser", "wrongpassword", repository=repo)
        assert authenticated is False

    def test_update_user_credentials(self, setup_db):
        """Test updating user credentials through repository."""
        repo = setup_db
        
        # Update user with new password
        new_hashed = get_password_hash("newpassword")
        repo.upsert_user(
            username="integrationuser",
            hashed_password=new_hashed,
            email="newemail@example.com"
        )
        
        # Old password should fail
        authenticated = authenticate_user("integrationuser", "testpassword", repository=repo)
        assert authenticated is False
        
        # New password should work
        authenticated = authenticate_user("integrationuser", "newpassword", repository=repo)
        assert authenticated is not False
        assert authenticated.email == "newemail@example.com"