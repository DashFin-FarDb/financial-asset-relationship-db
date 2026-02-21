"""Test runner that sets required environment variables before running pytest."""
import os
import subprocess
import sys

env = {
    **os.environ,
    "DATABASE_URL": "sqlite:///:memory:",
    "SECRET_KEY": "test-secret-key-for-ci",
    "ADMIN_USERNAME": "admin",
    "ADMIN_PASSWORD": "adminpass",
}

result = subprocess.run(
    [sys.executable, "-m", "pytest"] + sys.argv[1:],
    env=env,
)
sys.exit(result.returncode)
