"""Test package initialization to configure environment for
authentication tests.
"""

import os
from pathlib import Path

# Ensure a clean SQLite database for the authentication layer before any modules import it.
_db_path = Path(__file__).resolve().parent / "test_auth.db"
if _db_path.exists():
    _db_path.unlink()

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_db_path}")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "changeme")
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("ADMIN_FULL_NAME", "Test Admin")
os.environ.setdefault("ADMIN_DISABLED", "false")
