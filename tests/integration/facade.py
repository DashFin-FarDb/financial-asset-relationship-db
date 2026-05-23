"""Test-facing facade exposing selected integration dependencies.

This module intentionally re-exports a narrow subset of symbols used by
integration tests so test modules avoid direct imports from implementation
packages.
"""

from src.data.database import create_session_factory, init_db
from src.data.distributed_lock import DistributedLock, LockState
from src.data.repository import AssetGraphRepository, session_scope
from src.logic.recovery_gate import ExecutionBlockedError, RecoveryGate

__all__ = [
    "AssetGraphRepository",
    "DistributedLock",
    "ExecutionBlockedError",
    "LockState",
    "RecoveryGate",
    "create_session_factory",
    "init_db",
    "session_scope",
]
