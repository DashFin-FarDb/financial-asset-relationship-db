"""Unit test configuration — sets required environment variables before collection."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci")
os.environ.setdefault("ADMIN_USERNAME", "admin")

if "ADMIN_PASSWORD" not in os.environ:
    pytest.skip(
        "ADMIN_PASSWORD not set; skipping API tests that require auth.",
        allow_module_level=True,
    )
"""Unit test configuration — sets required environment variables before collection."""

import os

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci")
os.environ.setdefault("ADMIN_USERNAME", "admin")

if "ADMIN_PASSWORD" not in os.environ:
    pytest.skip(
        "ADMIN_PASSWORD not set; skipping API tests that require auth.",
        allow_module_level=True,
    )
