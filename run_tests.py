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
    """
    Check whether the given string contains any disallowed control characters (NUL, LF, CR).
    
    Parameters:
        value (str): The string to inspect.
    
    Returns:
        bool: `True` if `value` contains NUL (`\x00`), newline (`\n`), or carriage return (`\r`); `False` otherwise.
    """
    return any(char in value for char in ("\x00", "\n", "\r"))


def _validate_pytest_args(args: list[str]) -> list[str]:
    """
    Validate pytest command-line arguments for allowed characters and control characters.
    
    Parameters:
        args (list[str]): Candidate pytest command-line arguments (typically sys.argv[1:]).
    
    Returns:
        validated (list[str]): The input arguments in the same order after validation.
    
    Raises:
        ValueError: If any argument contains NUL, newline, or carriage return characters,
                    or if an argument contains characters outside the allowed set.
    """
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
