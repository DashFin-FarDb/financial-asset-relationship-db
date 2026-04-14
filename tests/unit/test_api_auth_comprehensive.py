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
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException

from api.auth import (
    ALGORITHM,
    SECRET_KEY,
    User,
    UserInDB,
    UserRepository,
    _build_credentials_exception,
    _build_expired_exception,
    _decode_username_from_token,
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
            user_email="new@example.com",
            user_full_name="New User",
            is_disabled=False,
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
        now_timestamp = datetime.now(timezone.utc).timestamp()
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
        exp_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        token_data = {"sub": "testuser", "exp": int(exp_time.timestamp())}
        token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail

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


# ---------------------------------------------------------------------------
# New helpers added in this PR
# ---------------------------------------------------------------------------


class TestBuildCredentialsException:
    """Tests for _build_credentials_exception (new in this PR)."""

    def test_returns_http_exception(self):
        """Return value is an HTTPException instance."""
        exc = _build_credentials_exception()
        assert isinstance(exc, HTTPException)

    def test_status_code_is_401(self):
        """Status code must be 401 Unauthorized."""
        exc = _build_credentials_exception()
        assert exc.status_code == 401

    def test_detail_message(self):
        """Detail message must be 'Could not validate credentials'."""
        exc = _build_credentials_exception()
        assert exc.detail == "Could not validate credentials"

    def test_www_authenticate_header(self):
        """WWW-Authenticate header must be set to 'Bearer'."""
        exc = _build_credentials_exception()
        assert exc.headers is not None
        assert exc.headers.get("WWW-Authenticate") == "Bearer"

    def test_returns_new_instance_each_call(self):
        """Each call returns a distinct HTTPException object."""
        exc1 = _build_credentials_exception()
        exc2 = _build_credentials_exception()
        assert exc1 is not exc2


class TestBuildExpiredException:
    """Tests for _build_expired_exception (new in this PR)."""

    def test_returns_http_exception(self):
        """Return value is an HTTPException instance."""
        exc = _build_expired_exception()
        assert isinstance(exc, HTTPException)

    def test_status_code_is_401(self):
        """Status code must be 401 Unauthorized."""
        exc = _build_expired_exception()
        assert exc.status_code == 401

    def test_detail_message(self):
        """Detail message must be 'Token has expired'."""
        exc = _build_expired_exception()
        assert exc.detail == "Token has expired"

    def test_www_authenticate_header(self):
        """WWW-Authenticate header must be set to 'Bearer'."""
        exc = _build_expired_exception()
        assert exc.headers is not None
        assert exc.headers.get("WWW-Authenticate") == "Bearer"

    def test_detail_differs_from_credentials_exception(self):
        """The expired exception has a different detail than the credentials exception."""
        cred_exc = _build_credentials_exception()
        exp_exc = _build_expired_exception()
        assert cred_exc.detail != exp_exc.detail

    def test_returns_new_instance_each_call(self):
        """Each call returns a distinct HTTPException object."""
        exc1 = _build_expired_exception()
        exc2 = _build_expired_exception()
        assert exc1 is not exc2


class TestDecodeUsernameFromToken:
    """Tests for _decode_username_from_token (new in this PR)."""

    def _make_token(self, payload: dict) -> str:
        """Encode a JWT using the module's SECRET_KEY and ALGORITHM."""
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    def _make_exceptions(self):
        """Create the two exception objects expected by _decode_username_from_token."""
        cred_exc = _build_credentials_exception()
        exp_exc = _build_expired_exception()
        return cred_exc, exp_exc

    def test_valid_token_returns_username(self):
        """A valid token with a 'sub' claim returns that claim value."""
        from datetime import datetime, timedelta, timezone

        payload = {
            "sub": "alice",
            "exp": (datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp(),
        }
        token = self._make_token(payload)
        cred_exc, exp_exc = self._make_exceptions()

        username = _decode_username_from_token(
            token=token,
            credentials_exception=cred_exc,
            expired_exception=exp_exc,
        )
        assert username == "alice"

    def test_missing_sub_raises_credentials_exception(self):
        """A token without a 'sub' claim raises the credentials exception."""
        from datetime import datetime, timedelta, timezone

        payload = {"exp": (datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp()}
        token = self._make_token(payload)
        cred_exc, exp_exc = self._make_exceptions()

        with pytest.raises(HTTPException) as exc_info:
            _decode_username_from_token(
                token=token,
                credentials_exception=cred_exc,
                expired_exception=exp_exc,
            )
        assert exc_info.value.detail == "Could not validate credentials"

    def test_expired_token_raises_expired_exception(self):
        """An expired token raises the expired exception."""
        from datetime import datetime, timedelta, timezone

        payload = {
            "sub": "bob",
            "exp": (datetime.now(timezone.utc) - timedelta(minutes=10)).timestamp(),
        }
        token = self._make_token(payload)
        cred_exc, exp_exc = self._make_exceptions()

        with pytest.raises(HTTPException) as exc_info:
            _decode_username_from_token(
                token=token,
                credentials_exception=cred_exc,
                expired_exception=exp_exc,
            )
        assert exc_info.value.detail == "Token has expired"

    def test_invalid_token_string_raises_credentials_exception(self):
        """A completely invalid token string raises the credentials exception."""
        cred_exc, exp_exc = self._make_exceptions()

        with pytest.raises(HTTPException) as exc_info:
            _decode_username_from_token(
                token="not.a.valid.jwt",
                credentials_exception=cred_exc,
                expired_exception=exp_exc,
            )
        assert exc_info.value.detail == "Could not validate credentials"

    def test_tampered_token_raises_credentials_exception(self):
        """A token with an invalid signature raises the credentials exception."""
        from datetime import datetime, timedelta, timezone

        payload = {"sub": "eve", "exp": (datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp()}
        token = jwt.encode(payload, "wrong-secret", algorithm=ALGORITHM)
        cred_exc, exp_exc = self._make_exceptions()

        with pytest.raises(HTTPException) as exc_info:
            _decode_username_from_token(
                token=token,
                credentials_exception=cred_exc,
                expired_exception=exp_exc,
            )
        assert exc_info.value.detail == "Could not validate credentials"

    def test_return_type_is_string(self):
        """The return value is always a plain str."""
        from datetime import datetime, timedelta, timezone

        payload = {"sub": "charlie", "exp": (datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp()}
        token = self._make_token(payload)
        cred_exc, exp_exc = self._make_exceptions()

        result = _decode_username_from_token(token=token, credentials_exception=cred_exc, expired_exception=exp_exc)
        assert isinstance(result, str)


class TestCreateOrUpdateUserNewSignature:
    """Tests for UserRepository.create_or_update_user new user_profile signature (this PR)."""

    @patch("api.auth.execute")
    def test_user_profile_dict_style(self, mock_execute):
        """user_profile dict is accepted and mapped to execute call."""
        repo = UserRepository()
        repo.create_or_update_user(
            username="alice",
            hashed_password="hashed_pw",
            user_profile={
                "user_email": "alice@example.com",
                "user_full_name": "Alice",
                "is_disabled": False,
            },
        )
        mock_execute.assert_called_once()
        positional_args, _ = mock_execute.call_args
        # execute("SQL", (username, email, full_name, hashed_password, disabled))
        params = positional_args[1]
        assert params[0] == "alice"
        assert params[1] == "alice@example.com"
        assert params[2] == "Alice"
        assert params[4] == 0  # is_disabled=False → 0

    @patch("api.auth.execute")
    def test_user_profile_none_uses_defaults(self, mock_execute):
        """Passing user_profile=None defaults to empty email, name, and not disabled."""
        repo = UserRepository()
        repo.create_or_update_user(
            username="bob",
            hashed_password="hpw",
            user_profile=None,
        )
        mock_execute.assert_called_once()
        positional_args, _ = mock_execute.call_args
        params = positional_args[1]
        assert params[0] == "bob"
        assert params[1] is None  # email
        assert params[2] is None  # full_name
        assert params[4] == 0  # not disabled

    @patch("api.auth.execute")
    def test_legacy_fields_override_user_profile(self, mock_execute):
        """Legacy keyword fields override values in user_profile when both are provided."""
        repo = UserRepository()
        repo.create_or_update_user(
            username="carol",
            hashed_password="hpw",
            user_profile={
                "user_email": "original@example.com",
                "user_full_name": "Original",
                "is_disabled": False,
            },
            user_email="override@example.com",
            user_full_name="Override Name",
            is_disabled=True,
        )
        mock_execute.assert_called_once()
        positional_args, _ = mock_execute.call_args
        params = positional_args[1]
        assert params[1] == "override@example.com"
        assert params[2] == "Override Name"
        assert params[4] == 1  # is_disabled=True → 1

    @patch("api.auth.execute")
    def test_unexpected_legacy_key_raises_type_error(self, mock_execute):
        """Unexpected keyword arguments raise a TypeError."""
        repo = UserRepository()
        with pytest.raises(TypeError, match="Unexpected legacy profile field"):
            repo.create_or_update_user(
                username="dave",
                hashed_password="hpw",
                unknown_field="oops",
            )

    @patch("api.auth.execute")
    def test_legacy_none_email_stored_as_none(self, mock_execute):
        """Passing user_email=None via legacy fields stores None in the database."""
        repo = UserRepository()
        repo.create_or_update_user(
            username="erin",
            hashed_password="hpw",
            user_email=None,
        )
        mock_execute.assert_called_once()
        positional_args, _ = mock_execute.call_args
        params = positional_args[1]
        assert params[1] is None

    @patch("api.auth.execute")
    def test_is_disabled_true_stores_one(self, mock_execute):
        """is_disabled=True is stored as integer 1 in the disabled column."""
        repo = UserRepository()
        repo.create_or_update_user(
            username="frank",
            hashed_password="hpw",
            user_profile={"is_disabled": True},
        )
        mock_execute.assert_called_once()
        positional_args, _ = mock_execute.call_args
        params = positional_args[1]
        assert params[4] == 1

    @patch("api.auth.execute")
    def test_is_disabled_false_stores_zero(self, mock_execute):
        """is_disabled=False is stored as integer 0 in the disabled column."""
        repo = UserRepository()
        repo.create_or_update_user(
            username="grace",
            hashed_password="hpw",
            user_profile={"is_disabled": False},
        )
        mock_execute.assert_called_once()
        positional_args, _ = mock_execute.call_args
        params = positional_args[1]
        assert params[4] == 0

    @patch("api.auth.execute")
    def test_multiple_unexpected_keys_listed_in_error(self, mock_execute):
        """TypeError message includes all unexpected key names."""
        repo = UserRepository()
        with pytest.raises(TypeError) as exc_info:
            repo.create_or_update_user(
                username="harry",
                hashed_password="hpw",
                foo="bar",
                baz="qux",
            )
        msg = str(exc_info.value)
        assert "baz" in msg
        assert "foo" in msg

    @patch("api.auth.execute")
    def test_no_profile_no_legacy_uses_all_defaults(self, mock_execute):
        """Calling with only username and hashed_password uses all default profile values."""
        repo = UserRepository()
        repo.create_or_update_user(
            username="ivan",
            hashed_password="hpw",
        )
        mock_execute.assert_called_once()
        positional_args, _ = mock_execute.call_args
        params = positional_args[1]
        assert params[0] == "ivan"
        assert params[1] is None  # email default
        assert params[2] is None  # full_name default
        assert params[4] == 0  # disabled default


class TestUserProfileTypedDict:
    """Tests for UserRepository.UserProfile TypedDict (new in this PR)."""

    def test_user_profile_is_accessible_as_nested_class(self):
        """UserProfile is accessible as UserRepository.UserProfile."""
        assert hasattr(UserRepository, "UserProfile")

    def test_user_profile_has_expected_fields(self):
        """UserProfile TypedDict has user_email, user_full_name, is_disabled annotations."""
        annotations = UserRepository.UserProfile.__annotations__
        assert "user_email" in annotations
        assert "user_full_name" in annotations
        assert "is_disabled" in annotations

    def test_user_profile_total_false_makes_all_keys_optional(self):
        """UserProfile is declared with total=False making all keys optional."""
        # A TypedDict with total=False has __total__ attribute set to False.
        assert UserRepository.UserProfile.__total__ is False
