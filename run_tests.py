"""
Test runner that sets required environment variables before running pytest.
"""

import os
import re
import secrets
import subprocess
import sys

SAFE_PYTEST_ARG_RE = re.compile(r"^[A-Za-z0-9_./:=,@+\-\[\]]+$")


def _has_control_chars(value: str) -> bool:
    """Return True when value contains disallowed control characters."""
    return any(char in value for char in ("\x00", "\n", "\r"))


def _validate_pytest_args(args: list[str]) -> list[str]:
    """Allow only safe pytest argument characters before subprocess use."""
    validated: list[str] = []
    for arg in args:
        if _has_control_chars(arg):
            raise ValueError("Invalid control characters in pytest arguments")
        if not SAFE_PYTEST_ARG_RE.fullmatch(arg):
            raise ValueError(f"Unsafe pytest argument: {arg}")
        validated.append(arg)
    return validated


pytest_args = _validate_pytest_args(sys.argv[1:])
env = {
    **os.environ,
    "DATABASE_URL": "sqlite:///:memory:",
    "SECRET_KEY": os.getenv("TEST_SECRET_KEY") or secrets.token_urlsafe(32),
    "ADMIN_USERNAME": "admin",
    "ADMIN_PASSWORD": "adminpass",
}

result = subprocess.run(
    [sys.executable, "-m", "pytest"] + pytest_args,
    env=env,
    check=False,
)
sys.exit(result.returncode)
