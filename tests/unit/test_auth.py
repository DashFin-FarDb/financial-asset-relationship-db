"""Comprehensive unit tests for api/auth.py authentication module.

This module tests:
- Password hashing and verification
- User repository operations (CRUD)
- JWT token creation and validation
- User authentication flows
- Environment-based user seeding
- Edge cases and security scenarios
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import jwt
import pytest
from fastapi import HTTPException, status
from passlib.context import CryptContext

from api.auth import (
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
    pwd_context,
    user_repository,
    verify_password,
    ALGORITHM,
    SECRET_KEY,
)


class TestIsTruthy:
    """Test the _is_truthy utility function for boolean string parsing."""

    def test_is_truthy_true_lowercase(self):
        """Test 'true' (lowercase) returns True."""
        assert _is_truthy('true') is True

    def test_is_truthy_true_uppercase(self):
        """Test 'TRUE' (uppercase) returns True."""
        assert _is_truthy('TRUE') is True

    def test_is_truthy_true_mixed_case(self):
        """Test 'TrUe' (mixed case) returns True."""
        assert _is_truthy('TrUe') is True

    def test_is_truthy_one(self):
        """Test '1' returns True."""
        assert _is_truthy('1') is True

    def test_is_truthy_yes_lowercase(self):
        """Test 'yes' returns True."""
        assert _is_truthy('yes') is True

    def test_is_truthy_yes_uppercase(self):
        """Test 'YES' returns True."""
        assert _is_truthy('YES') is True

    def test_is_truthy_on_lowercase(self):
        """Test 'on' returns True."""
        assert _is_truthy('on') is True

    def test_is_truthy_on_uppercase(self):
        """Test 'ON' returns True."""
        assert _is_truthy('ON') is True

    def test_is_truthy_false_lowercase(self):
        """Test 'false' returns False."""
        assert _is_truthy('false') is False

    def test_is_truthy_zero(self):
        """Test '0' returns False."""
        assert _is_truthy('0') is False

    def test_is_truthy_no(self):
        """Test 'no' returns False."""
        assert _is_truthy('no') is False

    def test_is_truthy_off(self):
        """Test 'off' returns False."""
        assert _is_truthy('off') is False

    def test_is_truthy_empty_string(self):
        """
        Verify _is_truthy rejects empty-string inputs.
        
        Asserts that calling _is_truthy('') returns False.
        """
        assert _is_truthy('') is False

    def test_is_truthy_none(self):
        """Test None returns False."""
        assert _is_truthy(None) is False

    def test_is_truthy_random_string(self):
        """Test arbitrary string returns False."""
        assert _is_truthy('random') is False

    def test_is_truthy_whitespace(self):
        """
        Verify that a string containing only whitespace is considered falsy by _is_truthy.
        """
        assert _is_truthy('   ') is False


class TestPasswordHashingAndVerification:
    """Test password hashing and verification functions."""

    def test_get_password_hash_returns_string(self):
        """Test that get_password_hash returns a string."""
        hashed = get_password_hash("testpassword")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_get_password_hash_different_for_same_password(self):
        """Verifies that hashing the same password twice yields different hash strings."""
        hash1 = get_password_hash("testpassword")
        hash2 = get_password_hash("testpassword")
        assert hash1 != hash2  # Different salts

    def test_verify_password_correct_password(self):
        """Test that verify_password returns True for correct password."""
        password = "mySecurePassword123!"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect_password(self):
        """Test that verify_password returns False for incorrect password."""
        password = "mySecurePassword123!"
        hashed = get_password_hash(password)
        assert verify_password("wrongpassword", hashed) is False

    def test_verify_password_empty_password(self):
        """Test that verify_password handles empty passwords."""
        hashed = get_password_hash("nonempty")
        assert verify_password("", hashed) is False

    def test_verify_password_case_sensitive(self):
        """Test that password verification is case-sensitive."""
        password = "Password123"
        hashed = get_password_hash(password)
        assert verify_password("password123", hashed) is False
        assert verify_password("PASSWORD123", hashed) is False

    def test_password_hash_uses_pbkdf2_sha256(self):
        """Test that the password context uses pbkdf2_sha256 scheme."""
        assert "pbkdf2_sha256" in pwd_context.schemes()


class TestPydanticModels:
    """Test Pydantic model validation and serialization."""

    def test_token_model_valid(self):
        """Test Token model with valid data."""
        token = Token(access_token="abc123", token_type="bearer")
        assert token.access_token == "abc123"
        assert token.token_type == "bearer"

    def test_token_data_model_with_username(self):
        """Test TokenData model with username."""
        token_data = TokenData(username="testuser")
        assert token_data.username == "testuser"

    def test_token_data_model_without_username(self):
        """Test TokenData model defaults to None username."""
        token_data = TokenData()
        assert token_data.username is None

    def test_user_model_minimal(self):
        """Test User model with minimal required fields."""
        user = User(username="testuser")
        assert user.username == "testuser"
        assert user.email is None
        assert user.full_name is None
        assert user.disabled is None

    def test_user_model_full(self):
        """Test User model with all fields."""
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

    def test_user_in_db_includes_hashed_password(self):
        """Test UserInDB extends User with hashed_password."""
        user = UserInDB(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            disabled=False,
            hashed_password="$pbkdf2-sha256$..."
        )
        assert user.username == "testuser"
        assert user.hashed_password == "$pbkdf2-sha256$..."


class TestUserRepository:
    """Test UserRepository database operations."""

    @pytest.fixture
    def mock_fetch_one(self):
        """
        Provide a patched mock for api.auth.fetch_one.
        
        Returns:
            mock (unittest.mock.Mock): The mock object that replaces api.auth.fetch_one for the duration of the fixture.
        """
        with patch('api.auth.fetch_one') as mock:
            yield mock

    @pytest.fixture
    def mock_fetch_value(self):
        """
        Provide a patched `api.auth.fetch_value` mock for tests.
        
        Yields:
            mock: The patched `fetch_value` mock object created by `unittest.mock.patch`.
        """
        with patch('api.auth.fetch_value') as mock:
            yield mock

    @pytest.fixture
    def mock_execute(self):
        """
        Provide a pytest fixture that yields a mock patch for the `api.auth.execute` function.
        
        Returns:
            mock: The patched mock object for `api.auth.execute`.
        """
        with patch('api.auth.execute') as mock:
            yield mock

    @pytest.fixture
    def repository(self):
        """
        Instantiate a new UserRepository.
        
        Returns:
            repository (UserRepository): A new UserRepository instance.
        """
        return UserRepository()

    def test_get_user_existing_user(self, repository, mock_fetch_one):
        """Test get_user returns UserInDB for existing user."""
        mock_fetch_one.return_value = {
            'username': 'testuser',
            'email': 'test@example.com',
            'full_name': 'Test User',
            'hashed_password': '$pbkdf2$...',
            'disabled': 0
        }
        
        user = repository.get_user('testuser')
        
        assert user is not None
        assert isinstance(user, UserInDB)
        assert user.username == 'testuser'
        assert user.email == 'test@example.com'
        assert user.full_name == 'Test User'
        assert user.hashed_password == '$pbkdf2$...'
        assert user.disabled is False

    def test_get_user_nonexistent_user(self, repository, mock_fetch_one):
        """Test get_user returns None for nonexistent user."""
        mock_fetch_one.return_value = None
        
        user = repository.get_user('nonexistent')
        
        assert user is None

    def test_get_user_disabled_user(self, repository, mock_fetch_one):
        """Test get_user correctly handles disabled flag."""
        mock_fetch_one.return_value = {
            'username': 'disabled_user',
            'email': 'disabled@example.com',
            'full_name': 'Disabled User',
            'hashed_password': '$pbkdf2$...',
            'disabled': 1
        }
        
        user = repository.get_user('disabled_user')
        
        assert user is not None
        assert user.disabled is True

    def test_has_users_returns_true(self, repository, mock_fetch_value):
        """Test has_users returns True when users exist."""
        mock_fetch_value.return_value = 1
        
        assert repository.has_users() is True

    def test_has_users_returns_false(self, repository, mock_fetch_value):
        """Test has_users returns False when no users exist."""
        mock_fetch_value.return_value = None
        
        assert repository.has_users() is False

    def test_create_or_update_user_minimal(self, repository, mock_execute):
        """Test create_or_update_user with minimal fields."""
        repository.create_or_update_user(
            username='newuser',
            hashed_password='$pbkdf2$...'
        )
        
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args
        assert 'newuser' in call_args[0][1]
        assert '$pbkdf2$...' in call_args[0][1]

    def test_create_or_update_user_full(self, repository, mock_execute):
        """Test create_or_update_user with all fields."""
        repository.create_or_update_user(
            username='fulluser',
            hashed_password='$pbkdf2$...',
            email='full@example.com',
            full_name='Full User',
            disabled=True
        )
        
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args
        params = call_args[0][1]
        assert params[0] == 'fulluser'
        assert params[1] == 'full@example.com'
        assert params[2] == 'Full User'
        assert params[3] == '$pbkdf2$...'
        assert params[4] == 1  # disabled=True converted to 1

    def test_create_or_update_user_disabled_false(self, repository, mock_execute):
        """Test create_or_update_user correctly converts disabled=False to 0."""
        repository.create_or_update_user(
            username='activeuser',
            hashed_password='$pbkdf2$...',
            disabled=False
        )
        
        call_args = mock_execute.call_args
        params = call_args[0][1]
        assert params[4] == 0  # disabled=False converted to 0


class TestGetUser:
    """Test the get_user helper function."""

    @pytest.fixture
    def mock_repository(self):
        """
        Create a Mock object configured with the UserRepository spec for use in tests.
        
        Returns:
            Mock: A Mock instance with its spec set to UserRepository.
        """
        return Mock(spec=UserRepository)

    def test_get_user_uses_default_repository(self, mock_repository):
        """Test get_user uses the module-level repository by default."""
        with patch('api.auth.user_repository', mock_repository):
            mock_repository.get_user.return_value = UserInDB(
                username='testuser',
                hashed_password='hash'
            )
            
            user = get_user('testuser')
            
            mock_repository.get_user.assert_called_once_with('testuser')
            assert user.username == 'testuser'

    def test_get_user_uses_provided_repository(self, mock_repository):
        """Test get_user uses the provided repository when specified."""
        mock_repository.get_user.return_value = UserInDB(
            username='testuser',
            hashed_password='hash'
        )
        
        user = get_user('testuser', repository=mock_repository)
        
        mock_repository.get_user.assert_called_once_with('testuser')
        assert user.username == 'testuser'


class TestAuthenticateUser:
    """Test the authenticate_user function."""

    @pytest.fixture
    def mock_repository(self):
        """
        Create a Mock configured to match the UserRepository interface for use in tests.
        
        Returns:
            repo (Mock): A Mock instance with UserRepository as its spec.
        """
        repo = Mock(spec=UserRepository)
        return repo

    def test_authenticate_user_success(self, mock_repository):
        """Test successful user authentication."""
        password = "correctpassword"
        hashed = get_password_hash(password)
        
        mock_repository.get_user.return_value = UserInDB(
            username='testuser',
            hashed_password=hashed,
            disabled=False
        )
        
        result = authenticate_user('testuser', password, repository=mock_repository)
        
        assert result is not False
        assert isinstance(result, UserInDB)
        assert result.username == 'testuser'

    def test_authenticate_user_wrong_password(self, mock_repository):
        """Test authentication fails with wrong password."""
        correct_password = "correctpassword"
        hashed = get_password_hash(correct_password)
        
        mock_repository.get_user.return_value = UserInDB(
            username='testuser',
            hashed_password=hashed,
            disabled=False
        )
        
        result = authenticate_user('testuser', 'wrongpassword', repository=mock_repository)
        
        assert result is False

    def test_authenticate_user_nonexistent_user(self, mock_repository):
        """Test authentication fails for nonexistent user."""
        mock_repository.get_user.return_value = None
        
        result = authenticate_user('nonexistent', 'anypassword', repository=mock_repository)
        
        assert result is False

    def test_authenticate_user_disabled_user_authenticates(self, mock_repository):
        """Test disabled user can still authenticate (check happens elsewhere)."""
        password = "correctpassword"
        hashed = get_password_hash(password)
        
        mock_repository.get_user.return_value = UserInDB(
            username='disableduser',
            hashed_password=hashed,
            disabled=True
        )
        
        result = authenticate_user('disableduser', password, repository=mock_repository)
        
        assert result is not False
        assert result.disabled is True


class TestCreateAccessToken:
    """Test JWT access token creation."""

    def test_create_access_token_with_custom_expiry(self):
        """Test creating a token with custom expiration time."""
        data = {"sub": "testuser"}
        expires_delta = timedelta(minutes=30)
        
        token = create_access_token(data, expires_delta=expires_delta)
        
        assert isinstance(token, str)
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded["sub"] == "testuser"
        assert "exp" in decoded

    def test_create_access_token_with_default_expiry(self):
        """Test creating a token with default 15-minute expiration."""
        data = {"sub": "testuser"}
        
        token = create_access_token(data)
        
        assert isinstance(token, str)
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded["sub"] == "testuser"
        
        # Check expiry is approximately 15 minutes from now
        exp = datetime.utcfromtimestamp(decoded["exp"])
        now = datetime.utcnow()
        delta = exp - now
        assert timedelta(minutes=14) < delta < timedelta(minutes=16)

    def test_create_access_token_preserves_extra_claims(self):
        """Test that extra claims in data are preserved in token."""
        data = {"sub": "testuser", "role": "admin", "scope": "read write"}
        
        token = create_access_token(data)
        
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded["sub"] == "testuser"
        assert decoded["role"] == "admin"
        assert decoded["scope"] == "read write"

    def test_create_access_token_overrides_exp_in_data(self):
        """Test that function overrides any 'exp' in the input data."""
        data = {"sub": "testuser", "exp": datetime.utcnow() + timedelta(days=365)}
        expires_delta = timedelta(minutes=5)
        
        token = create_access_token(data, expires_delta=expires_delta)
        
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp = datetime.utcfromtimestamp(decoded["exp"])
        now = datetime.utcnow()
        delta = exp - now
        # Should be ~5 minutes, not 365 days
        assert delta < timedelta(minutes=10)


class TestGetCurrentUser:
    """Test the get_current_user dependency function."""

    @pytest.fixture
    def mock_get_user_func(self):
        """
        Provide a fixture that patches api.auth.get_user and yields the mock.
        
        Returns:
            mock (unittest.mock.Mock): The patched `get_user` mock.
        """
        with patch('api.auth.get_user') as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self, mock_get_user_func):
        """Test get_current_user with a valid token."""
        data = {"sub": "testuser"}
        token = create_access_token(data, expires_delta=timedelta(minutes=30))
        
        mock_get_user_func.return_value = User(
            username='testuser',
            email='test@example.com'
        )
        
        user = await get_current_user(token)
        
        assert user.username == 'testuser'
        mock_get_user_func.assert_called_once_with('testuser')

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token(self):
        """Test get_current_user raises HTTPException for expired token."""
        data = {"sub": "testuser"}
        # Create token that expired 1 minute ago
        token = create_access_token(data, expires_delta=timedelta(minutes=-1))
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "Token has expired"

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self):
        """Test get_current_user raises HTTPException for malformed token."""
        invalid_token = "not.a.valid.token"
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(invalid_token)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "Could not validate credentials"

    @pytest.mark.asyncio
    async def test_get_current_user_token_without_sub(self):
        """Test get_current_user raises HTTPException for token without 'sub' claim."""
        # Create token without 'sub' claim
        token = jwt.encode(
            {"exp": datetime.utcnow() + timedelta(minutes=30)},
            SECRET_KEY,
            algorithm=ALGORITHM
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "Could not validate credentials"

    @pytest.mark.asyncio
    async def test_get_current_user_nonexistent_user(self, mock_get_user_func):
        """Test get_current_user raises HTTPException when user doesn't exist."""
        data = {"sub": "nonexistent"}
        token = create_access_token(data, expires_delta=timedelta(minutes=30))
        
        mock_get_user_func.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "Could not validate credentials"

    @pytest.mark.asyncio
    async def test_get_current_user_wrong_algorithm(self):
        """Test get_current_user rejects token with wrong algorithm."""
        # Create token with different algorithm
        token = jwt.encode(
            {"sub": "testuser", "exp": datetime.utcnow() + timedelta(minutes=30)},
            SECRET_KEY,
            algorithm="HS512"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetCurrentActiveUser:
    """Test the get_current_active_user dependency function."""

    @pytest.mark.asyncio
    async def test_get_current_active_user_active(self):
        """Test get_current_active_user returns user when not disabled."""
        current_user = User(username='activeuser', disabled=False)
        
        user = await get_current_active_user(current_user)
        
        assert user.username == 'activeuser'

    @pytest.mark.asyncio
    async def test_get_current_active_user_not_disabled(self):
        """Test get_current_active_user returns user when disabled is None."""
        current_user = User(username='user', disabled=None)
        
        user = await get_current_active_user(current_user)
        
        assert user.username == 'user'

    @pytest.mark.asyncio
    async def test_get_current_active_user_disabled(self):
        """Test get_current_active_user raises HTTPException for disabled user."""
        current_user = User(username='disableduser', disabled=True)
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(current_user)
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Inactive user"


class TestSeedCredentialsFromEnv:
    """Test the _seed_credentials_from_env function."""

    @pytest.fixture
    def mock_repository(self):
        """
        Create a Mock object configured with the UserRepository spec for use in tests.
        
        Returns:
            Mock: A Mock instance with its spec set to UserRepository.
        """
        return Mock(spec=UserRepository)

    def test_seed_credentials_both_env_vars_set(self, mock_repository):
        """Test seeding credentials when both username and password are set."""
        env_vars = {
            'ADMIN_USERNAME': 'admin',
            'ADMIN_PASSWORD': 'securepass123',
            'ADMIN_EMAIL': 'admin@example.com',
            'ADMIN_FULL_NAME': 'Admin User',
            'ADMIN_DISABLED': 'false'
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            _seed_credentials_from_env(mock_repository)
        
        mock_repository.create_or_update_user.assert_called_once()
        call_kwargs = mock_repository.create_or_update_user.call_args.kwargs
        assert call_kwargs['username'] == 'admin'
        assert call_kwargs['email'] == 'admin@example.com'
        assert call_kwargs['full_name'] == 'Admin User'
        assert call_kwargs['disabled'] is False
        # Check that password was hashed
        assert call_kwargs['hashed_password'] != 'securepass123'

    def test_seed_credentials_minimal_env_vars(self, mock_repository):
        """Test seeding credentials with only username and password."""
        env_vars = {
            'ADMIN_USERNAME': 'admin',
            'ADMIN_PASSWORD': 'securepass123'
        }
        
        # Clear optional env vars if they exist
        for key in ['ADMIN_EMAIL', 'ADMIN_FULL_NAME', 'ADMIN_DISABLED']:
            if key in os.environ:
                del os.environ[key]
        
        with patch.dict(os.environ, env_vars, clear=False):
            _seed_credentials_from_env(mock_repository)
        
        mock_repository.create_or_update_user.assert_called_once()
        call_kwargs = mock_repository.create_or_update_user.call_args.kwargs
        assert call_kwargs['username'] == 'admin'
        assert call_kwargs['email'] is None
        assert call_kwargs['full_name'] is None
        assert call_kwargs['disabled'] is False

    def test_seed_credentials_disabled_true(self, mock_repository):
        """Test seeding credentials with disabled=true."""
        env_vars = {
            'ADMIN_USERNAME': 'admin',
            'ADMIN_PASSWORD': 'securepass123',
            'ADMIN_DISABLED': 'true'
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            _seed_credentials_from_env(mock_repository)
        
        call_kwargs = mock_repository.create_or_update_user.call_args.kwargs
        assert call_kwargs['disabled'] is True

    def test_seed_credentials_disabled_various_truthy(self, mock_repository):
        """Test seeding credentials with various truthy values for disabled."""
        for truthy_value in ['1', 'yes', 'YES', 'on', 'ON']:
            mock_repository.reset_mock()
            env_vars = {
                'ADMIN_USERNAME': 'admin',
                'ADMIN_PASSWORD': 'securepass123',
                'ADMIN_DISABLED': truthy_value
            }
            
            with patch.dict(os.environ, env_vars, clear=False):
                _seed_credentials_from_env(mock_repository)
            
            call_kwargs = mock_repository.create_or_update_user.call_args.kwargs
            assert call_kwargs['disabled'] is True, f"Failed for value: {truthy_value}"

    def test_seed_credentials_missing_username(self, mock_repository):
        """Test seeding does nothing when username is missing."""
        env_vars = {
            'ADMIN_PASSWORD': 'securepass123'
        }
        
        if 'ADMIN_USERNAME' in os.environ:
            del os.environ['ADMIN_USERNAME']
        
        with patch.dict(os.environ, env_vars, clear=False):
            _seed_credentials_from_env(mock_repository)
        
        mock_repository.create_or_update_user.assert_not_called()

    def test_seed_credentials_missing_password(self, mock_repository):
        """Test seeding does nothing when password is missing."""
        env_vars = {
            'ADMIN_USERNAME': 'admin'
        }
        
        if 'ADMIN_PASSWORD' in os.environ:
            del os.environ['ADMIN_PASSWORD']
        
        with patch.dict(os.environ, env_vars, clear=False):
            _seed_credentials_from_env(mock_repository)
        
        mock_repository.create_or_update_user.assert_not_called()

    def test_seed_credentials_missing_both(self, mock_repository):
        """Test seeding does nothing when both username and password are missing."""
        for key in ['ADMIN_USERNAME', 'ADMIN_PASSWORD']:
            if key in os.environ:
                del os.environ[key]
        
        _seed_credentials_from_env(mock_repository)
        
        mock_repository.create_or_update_user.assert_not_called()


class TestSecurityConfiguration:
    """Test security configuration and constants."""

    def test_secret_key_is_set(self):
        """Test that SECRET_KEY is configured from environment."""
        assert SECRET_KEY is not None
        assert len(SECRET_KEY) > 0

    def test_algorithm_is_hs256(self):
        """Test that JWT algorithm is HS256."""
        assert ALGORITHM == "HS256"

    def test_access_token_expire_minutes(self):
        """Test that ACCESS_TOKEN_EXPIRE_MINUTES is set."""
        from api.auth import ACCESS_TOKEN_EXPIRE_MINUTES
        assert ACCESS_TOKEN_EXPIRE_MINUTES == 30

    def test_pwd_context_configuration(self):
        """Test that password context uses correct scheme."""
        assert "pbkdf2_sha256" in pwd_context.schemes()
        assert "auto" in pwd_context.deprecated

    def test_module_initialization(self):
        """Test that module-level objects are initialized."""
        assert user_repository is not None
        assert isinstance(user_repository, UserRepository)


class TestEdgeCasesAndSecurity:
    """Test edge cases and security scenarios."""

    def test_password_with_special_characters(self):
        """Test password hashing and verification with special characters."""
        password = "p@$$w0rd!#%&*()_+-=[]{}|;':,.<>?/"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_password_with_unicode(self):
        """Test password hashing with unicode characters."""
        password = "пароль密码🔒"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_very_long_password(self):
        """Test password hashing with very long password."""
        password = "a" * 1000
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_empty_password_hash(self):
        """Test that empty password can be hashed (even if not recommended)."""
        password = ""
        hashed = get_password_hash(password)
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    @pytest.mark.asyncio
    async def test_token_with_tampered_payload(self):
        """Test that tampering with token payload is detected."""
        data = {"sub": "testuser"}
        token = create_access_token(data, expires_delta=timedelta(minutes=30))
        
        # Tamper with the token by changing a character
        tampered_token = token[:-10] + "X" + token[-9:]
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(tampered_token)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_token_signed_with_wrong_key(self):
        """Test that token signed with wrong key is rejected."""
        data = {"sub": "testuser", "exp": datetime.utcnow() + timedelta(minutes=30)}
        wrong_token = jwt.encode(data, "wrong_secret_key", algorithm=ALGORITHM)
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(wrong_token)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_username_with_sql_injection_attempt(self):
        """Test that username with SQL injection attempt is handled safely."""
        mock_repo = Mock(spec=UserRepository)
        mock_repo.get_user.return_value = None
        
        # This should be handled safely by parameterized queries
        malicious_username = "admin' OR '1'='1"
        result = authenticate_user(malicious_username, "password", repository=mock_repo)
        
        assert result is False
        mock_repo.get_user.assert_called_once_with(malicious_username)