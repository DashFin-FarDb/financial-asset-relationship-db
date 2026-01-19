"""
Comprehensive unit tests for api/auth.py refactoring changes.

This module tests the refactored authentication module, focusing on:
- UserRepository instance methods (changed from @staticmethod)
- Parameter name changes in create_or_update_user
- UserInDB model moved to auth module
- Edge cases and boundary conditions
- Thread safety of repository methods
"""

import os
import sqlite3
import threading
from unittest.mock import Mock, patch, MagicMock
import pytest
from api.auth import (
    UserRepository,
    User,
    UserInDB,
    _is_truthy,
    _seed_credentials_from_env,
    verify_password,
    get_password_hash,
    authenticate_user,
    get_user,
    create_access_token,
)
from api.database import execute, fetch_one, fetch_value, initialize_schema


class TestUserInDBModel:
    """Test UserInDB model structure and inheritance."""

    def test_user_in_db_inherits_from_user(self):
        """UserInDB should inherit from User model."""
        user_in_db = UserInDB(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            disabled=False,
            hashed_password="hashed123"
        )
        assert isinstance(user_in_db, User)
        assert hasattr(user_in_db, 'username')
        assert hasattr(user_in_db, 'hashed_password')

    def test_user_in_db_required_fields(self):
        """UserInDB should require username and hashed_password."""
        user_in_db = UserInDB(username="testuser", hashed_password="hash123")
        assert user_in_db.username == "testuser"
        assert user_in_db.hashed_password == "hash123"
        assert user_in_db.email is None
        assert user_in_db.full_name is None
        assert user_in_db.disabled is None

    def test_user_in_db_all_fields(self):
        """UserInDB should accept all optional fields."""
        user_in_db = UserInDB(
            username="admin",
            email="admin@example.com",
            full_name="Admin User",
            disabled=True,
            hashed_password="$pbkdf2-sha256$..."
        )
        assert user_in_db.username == "admin"
        assert user_in_db.email == "admin@example.com"
        assert user_in_db.full_name == "Admin User"
        assert user_in_db.disabled is True
        assert user_in_db.hashed_password == "$pbkdf2-sha256$..."


class TestIsTruthyHelper:
    """Test _is_truthy helper function."""

    def test_is_truthy_with_none(self):
        """Should return False for None."""
        assert _is_truthy(None) is False

    def test_is_truthy_with_empty_string(self):
        """Should return False for empty string."""
        assert _is_truthy("") is False
        assert _is_truthy("   ") is False

    def test_is_truthy_with_true_values(self):
        """
        Verify that _is_truthy recognizes common string representations of truth.
        """
        assert _is_truthy("true") is True
        assert _is_truthy("TRUE") is True
        assert _is_truthy("True") is True
        assert _is_truthy("1") is True
        assert _is_truthy("yes") is True
        assert _is_truthy("YES") is True
        assert _is_truthy("on") is True
        assert _is_truthy("ON") is True

    def test_is_truthy_with_false_values(self):
        """
        Verifies _is_truthy identifies common false-like string inputs.
        """
        assert _is_truthy("false") is False
        assert _is_truthy("0") is False
        assert _is_truthy("no") is False
        assert _is_truthy("off") is False
        assert _is_truthy("random") is False

    def test_is_truthy_case_insensitive(self):
        """Should handle case-insensitive matching."""
        assert _is_truthy("TrUe") is True
        assert _is_truthy("YeS") is True
        assert _is_truthy("oN") is True


class TestUserRepositoryInstanceMethods:
    """Test UserRepository instance methods (changed from static methods)."""

    @pytest.fixture
    def repository(self):
        """
        Provide a fresh UserRepository with an initialized database schema for a test.
        
        Returns:
            UserRepository: A new repository instance after the database schema has been initialized.
        """
        initialize_schema()
        return UserRepository()

    @pytest.fixture
    def sample_user_data(self):
        """
        Return a sample user payload used by tests.
        
        Returns:
            dict: A user dictionary with the following keys:
                - username (str): "testuser"
                - hashed_password (str): hashed form of "password123"
                - email (str): "test@example.com"
                - full_name (str): "Test User"
                - disabled (bool): False
        """
        return {
            "username": "testuser",
            "hashed_password": get_password_hash("password123"),
            "email": "test@example.com",
            "full_name": "Test User",
            "disabled": False
        }

    def test_repository_is_instance(self, repository):
        """Repository should be instantiable."""
        assert isinstance(repository, UserRepository)

    def test_get_user_is_instance_method(self, repository):
        """get_user should be an instance method, not static."""
        import inspect
        assert not isinstance(inspect.getattr_static(UserRepository, 'get_user'), staticmethod)

    def test_has_users_is_instance_method(self, repository):
        """has_users should be an instance method, not static."""
        import inspect
        assert not isinstance(inspect.getattr_static(UserRepository, 'has_users'), staticmethod)

    def test_create_or_update_user_is_instance_method(self, repository):
        """create_or_update_user should be an instance method, not static."""
        import inspect
        assert not isinstance(inspect.getattr_static(UserRepository, 'create_or_update_user'), staticmethod)

    def test_multiple_repository_instances(self, sample_user_data):
        """Multiple repository instances should access the same database."""
        repo1 = UserRepository()
        repo2 = UserRepository()
        
        repo1.create_or_update_user(**sample_user_data)
        user = repo2.get_user(sample_user_data["username"])
        
        assert user is not None
        assert user.username == sample_user_data["username"]

    def test_repository_thread_safety(self, sample_user_data):
        """Repository operations should be thread-safe."""
        repository = UserRepository()
        errors = []
        
        def create_user(username):
            """
            Create or update a user in the repository using the shared sample_user_data with the provided username.
            
            This function copies the module-level `sample_user_data`, replaces its "username" with the given value, and calls `repository.create_or_update_user` to persist the user. If an exception occurs, it is appended to the module-level `errors` list.
            """
            try:
                data = sample_user_data.copy()
                data["username"] = username
                repository.create_or_update_user(**data)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=create_user, args=(f"user{i}",)) for i in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        
        assert len(errors) == 0
        assert repository.has_users() is True


class TestCreateOrUpdateUserParameterNames:
    """Test parameter name changes in create_or_update_user."""

    @pytest.fixture
    def repository(self):
        """
        Provide a fresh UserRepository with an initialized database schema for tests.
        
        Returns:
            UserRepository: A new repository instance backed by a freshly initialized schema.
        """
        initialize_schema()
        return UserRepository()

    def test_parameter_name_email_instead_of_user_email(self, repository):
        """Should use 'email' parameter instead of 'user_email'."""
        repository.create_or_update_user(
            username="test",
            hashed_password="hash",
            email="test@example.com"  # New parameter name
        )
        user = repository.get_user("test")
        assert user.email == "test@example.com"

    def test_parameter_name_full_name_instead_of_user_full_name(self, repository):
        """Should use 'full_name' parameter instead of 'user_full_name'."""
        repository.create_or_update_user(
            username="test",
            hashed_password="hash",
            full_name="Test User"  # New parameter name
        )
        user = repository.get_user("test")
        assert user.full_name == "Test User"

    def test_parameter_name_disabled_instead_of_is_disabled(self, repository):
        """Should use 'disabled' parameter instead of 'is_disabled'."""
        repository.create_or_update_user(
            username="test",
            hashed_password="hash",
            disabled=True  # New parameter name
        )
        user = repository.get_user("test")
        assert user.disabled is True

    def test_all_parameters_with_new_names(self, repository):
        """Should work with all new parameter names."""
        repository.create_or_update_user(
            username="admin",
            hashed_password=get_password_hash("admin123"),
            email="admin@example.com",
            full_name="Admin User",
            disabled=False
        )
        user = repository.get_user("admin")
        assert user.username == "admin"
        assert user.email == "admin@example.com"
        assert user.full_name == "Admin User"
        assert user.disabled is False


class TestSeedCredentialsFromEnv:
    """Test _seed_credentials_from_env with new parameter names."""

    @pytest.fixture
    def repository(self):
        """
        Provide a fresh UserRepository with an initialized database schema for tests.
        
        Returns:
            UserRepository: A new repository instance backed by a freshly initialized schema.
        """
        initialize_schema()
        return UserRepository()

    def test_seed_with_all_environment_variables(self, repository, monkeypatch):
        """Should seed user with all environment variables set."""
        monkeypatch.setenv("ADMIN_USERNAME", "admin")
        monkeypatch.setenv("ADMIN_PASSWORD", "admin123")
        monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
        monkeypatch.setenv("ADMIN_FULL_NAME", "Administrator")
        monkeypatch.setenv("ADMIN_DISABLED", "false")
        
        _seed_credentials_from_env(repository)
        
        user = repository.get_user("admin")
        assert user is not None
        assert user.email == "admin@example.com"
        assert user.full_name == "Administrator"
        assert user.disabled is False

    def test_seed_with_minimal_environment_variables(self, repository, monkeypatch):
        """Should seed user with only required environment variables."""
        monkeypatch.setenv("ADMIN_USERNAME", "admin")
        monkeypatch.setenv("ADMIN_PASSWORD", "admin123")
        monkeypatch.delenv("ADMIN_EMAIL", raising=False)
        monkeypatch.delenv("ADMIN_FULL_NAME", raising=False)
        monkeypatch.delenv("ADMIN_DISABLED", raising=False)
        
        _seed_credentials_from_env(repository)
        
        user = repository.get_user("admin")
        assert user is not None
        assert user.email is None
        assert user.full_name is None
        assert user.disabled is False

    def test_seed_with_disabled_user(self, repository, monkeypatch):
        """Should handle ADMIN_DISABLED correctly."""
        monkeypatch.setenv("ADMIN_USERNAME", "disabled_admin")
        monkeypatch.setenv("ADMIN_PASSWORD", "pass123")
        monkeypatch.setenv("ADMIN_DISABLED", "true")
        
        _seed_credentials_from_env(repository)
        
        user = repository.get_user("disabled_admin")
        assert user is not None
        assert user.disabled is True

    def test_seed_updates_existing_user(self, repository, monkeypatch):
        """Should update existing user when seeding."""
        # Create initial user
        repository.create_or_update_user(
            username="admin",
            hashed_password="old_hash",
            email="old@example.com"
        )
        
        # Seed with new data
        monkeypatch.setenv("ADMIN_USERNAME", "admin")
        monkeypatch.setenv("ADMIN_PASSWORD", "new_password")
        monkeypatch.setenv("ADMIN_EMAIL", "new@example.com")
        
        _seed_credentials_from_env(repository)
        
        user = repository.get_user("admin")
        assert user.email == "new@example.com"
        assert verify_password("new_password", user.hashed_password)


class TestPasswordOperations:
    """Test password hashing and verification."""

    def test_password_hash_is_different_from_plaintext(self):
        """Hashed password should differ from plaintext."""
        password = "mypassword123"
        hashed = get_password_hash(password)
        assert hashed != password
        assert len(hashed) > len(password)

    def test_password_hash_is_deterministic_per_call(self):
        """Same password should produce different hashes (due to salt)."""
        password = "mypassword123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        # Different hashes due to unique salts
        assert hash1 != hash2

    def test_verify_correct_password(self):
        """Should verify correct password."""
        password = "correct_password"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_verify_incorrect_password(self):
        """Should reject incorrect password."""
        password = "correct_password"
        hashed = get_password_hash(password)
        assert verify_password("wrong_password", hashed) is False

    def test_verify_empty_password(self):
        """Should handle empty passwords."""
        hashed = get_password_hash("")
        assert verify_password("", hashed) is True
        assert verify_password("nonempty", hashed) is False

    def test_verify_special_characters_in_password(self):
        """Should handle special characters in passwords."""
        password = "p@ssw0rd!#$%^&*()"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_verify_unicode_password(self):
        """Should handle Unicode characters in passwords."""
        password = "пароль密码🔐"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True


class TestAuthenticateUserFunction:
    """Test authenticate_user function with repository parameter."""

    @pytest.fixture
    def repository(self):
        """
        Create a UserRepository instance initialized with a single test user.
        
        Returns:
            UserRepository: repository containing a pre-created user with username "testuser", email "test@example.com", and a hashed password.
        """
        initialize_schema()
        repo = UserRepository()
        repo.create_or_update_user(
            username="testuser",
            hashed_password=get_password_hash("password123"),
            email="test@example.com",
            disabled=False
        )
        return repo

    def test_authenticate_with_correct_credentials(self, repository):
        """Should authenticate user with correct credentials."""
        user = authenticate_user("testuser", "password123", repository)
        assert user is not False
        assert isinstance(user, UserInDB)
        assert user.username == "testuser"

    def test_authenticate_with_incorrect_password(self, repository):
        """Should reject incorrect password."""
        user = authenticate_user("testuser", "wrongpassword", repository)
        assert user is False

    def test_authenticate_with_nonexistent_user(self, repository):
        """Should reject nonexistent user."""
        user = authenticate_user("nonexistent", "password123", repository)
        assert user is False

    def test_authenticate_with_disabled_user(self):
        """Should reject disabled user."""
        initialize_schema()
        repo = UserRepository()
        repo.create_or_update_user(
            username="disabled_user",
            hashed_password=get_password_hash("password123"),
            disabled=True
        )
        user = authenticate_user("disabled_user", "password123", repo)
        assert user is False

    def test_authenticate_without_repository_parameter(self):
        """Should use default repository when none provided."""
        # This tests backwards compatibility
        user = authenticate_user("admin", "wrongpass")
        assert user is False or isinstance(user, UserInDB)


class TestGetUserFunction:
    """Test get_user function with optional repository parameter."""

    @pytest.fixture
    def repository(self):
        """
        Create a UserRepository instance pre-populated with a test user.
        
        Returns:
            UserRepository: Repository containing a user with username "testuser", hashed_password "hash123", and email "test@example.com".
        """
        initialize_schema()
        repo = UserRepository()
        repo.create_or_update_user(
            username="testuser",
            hashed_password="hash123",
            email="test@example.com"
        )
        return repo

    def test_get_user_with_repository_parameter(self, repository):
        """Should retrieve user using provided repository."""
        user = get_user("testuser", repository)
        assert user is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"

    def test_get_user_without_repository_parameter(self):
        """Should use default repository when none provided."""
        user = get_user("someuser")
        # Should not raise error
        assert user is None or isinstance(user, UserInDB)

    def test_get_nonexistent_user(self, repository):
        """Should return None for nonexistent user."""
        user = get_user("nonexistent", repository)
        assert user is None


class TestEdgeCasesAndBoundaryConditions:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def repository(self):
        """
        Initialize the database schema and return a new UserRepository instance.
        
        Returns:
            UserRepository: A new repository backed by a freshly initialized schema.
        """
        initialize_schema()
        return UserRepository()

    def test_username_with_special_characters(self, repository):
        """Should handle usernames with special characters."""
        username = "user@#$%^&*()"
        repository.create_or_update_user(
            username=username,
            hashed_password="hash"
        )
        user = repository.get_user(username)
        assert user.username == username

    def test_very_long_username(self, repository):
        """
        Verifies the repository accepts and correctly retrieves a username of 1000 characters.
        """
        username = "a" * 1000
        repository.create_or_update_user(
            username=username,
            hashed_password="hash"
        )
        user = repository.get_user(username)
        assert user.username == username

    def test_unicode_username(self, repository):
        """Should handle Unicode usernames."""
        username = "用户名🔐"
        repository.create_or_update_user(
            username=username,
            hashed_password="hash"
        )
        user = repository.get_user(username)
        assert user.username == username

    def test_empty_email(self, repository):
        """Should handle None vs empty string for email."""
        repository.create_or_update_user(
            username="user1",
            hashed_password="hash",
            email=None
        )
        user = repository.get_user("user1")
        assert user.email is None

    def test_update_user_disabled_status(self, repository):
        """Should correctly update disabled status."""
        repository.create_or_update_user(
            username="user",
            hashed_password="hash",
            disabled=False
        )
        repository.create_or_update_user(
            username="user",
            hashed_password="hash",
            disabled=True
        )
        user = repository.get_user("user")
        assert user.disabled is True

    def test_concurrent_user_creation(self, repository):
        """Should handle concurrent user creation safely."""
        def create_users():
            """
            Create ten users in the module-level repository.
            
            Each created user has username "user0" through "user9" and a hashed_password value of "hash".
            """
            for i in range(10):
                repository.create_or_update_user(
                    username=f"user{i}",
                    hashed_password="hash"
                )
        
        threads = [threading.Thread(target=create_users) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should have created users without errors
        assert repository.has_users() is True


class TestSecurityConfiguration:
    """Test security configuration and constants."""

    def test_secret_key_required(self):
        """SECRET_KEY environment variable should be required."""
        # This is tested at module import time
        from api.auth import SECRET_KEY
        assert SECRET_KEY is not None
        assert len(SECRET_KEY) > 0

    def test_algorithm_constant(self):
        """ALGORITHM should be set correctly."""
        from api.auth import ALGORITHM
        assert ALGORITHM == "HS256"

    def test_access_token_expire_minutes(self):
        """
        Verify that the access token expiry is configured to a positive value.
        
        Asserts that ACCESS_TOKEN_EXPIRE_MINUTES is an integer greater than zero.
        """
        from api.auth import ACCESS_TOKEN_EXPIRE_MINUTES
        assert isinstance(ACCESS_TOKEN_EXPIRE_MINUTES, int)
        assert ACCESS_TOKEN_EXPIRE_MINUTES > 0

    def test_password_context_configuration(self):
        """Password context should use pbkdf2_sha256."""
        from api.auth import pwd_context
        assert "pbkdf2_sha256" in pwd_context.schemes()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])