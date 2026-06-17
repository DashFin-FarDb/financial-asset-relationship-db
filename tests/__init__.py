"""Test package initialization."""

import os

# Enforce hermeticity for test runs across the entire suite
os.environ["SECRET_KEY"] = "test-secret-key-at-least-32-bytes-long"
