"""Unit test configuration — sets required environment variables before collection."""

import os
import sys

# These must be set before api.main is imported (happens at collection time).
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-for-ci"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "adminpass"

print(
    f"[unit conftest] DATABASE_URL set to {os.environ['DATABASE_URL']}", file=sys.stderr
)
