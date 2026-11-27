"""Unit tests for H-P2-02: fencing token verification on graph/job writes."""

from __future__ import annotations

from pathlib import Path

import pytest

from api.routers.graph_admin import _DistributedLockLostError, _guard_publication_lock
from src.data.database import create_engine_from_url, create_session_factory, init_db
from src.data.distributed_lock import DistributedLock
from src.data.repository import CoordinationLockRepository


def test_fencing_token_property_and_repository_verification(tmp_path: Path) -> None:
    """CoordinationLockRepository.verify_fencing_token accepts the active token and rejects stale tokens."""
    engine = create_engine_from_url(f"sqlite:///{tmp_path / 'hp202.db'}")
    try:
        init_db(engine)
        session_factory = create_session_factory(engine)
        lock = DistributedLock(
            coordination_session_factory=session_factory,
            lock_name="graph_rebuild",
            ttl_seconds=60,
            holder_id="worker-a",
        )
        lease = lock.acquire()
        assert lease.fencing_token > 0
        assert lock.fencing_token == lease.fencing_token

        with session_factory() as session:
            repo = CoordinationLockRepository(session)
            assert repo.verify_fencing_token(
                lock_name="graph_rebuild",
                holder_id="worker-a",
                expected_fencing_token=lock.fencing_token,
            )
            # Stale fencing token (lower or zero) is rejected
            assert not repo.verify_fencing_token(
                lock_name="graph_rebuild",
                holder_id="worker-a",
                expected_fencing_token=lock.fencing_token - 1,
            )
            assert not repo.verify_fencing_token(
                lock_name="graph_rebuild",
                holder_id="worker-a",
                expected_fencing_token=0,
            )
            # Wrong holder with same token is rejected
            assert not repo.verify_fencing_token(
                lock_name="graph_rebuild",
                holder_id="worker-b",
                expected_fencing_token=lock.fencing_token,
            )
    finally:
        engine.dispose()


def test_publication_lock_guard_rejects_stale_fencing_token_and_advances_valid_token(tmp_path: Path) -> None:
    """_guard_publication_lock rejects stale tokens with _DistributedLockLostError and advances valid tokens."""
    engine = create_engine_from_url(f"sqlite:///{tmp_path / 'hp202_guard.db'}")
    try:
        init_db(engine)
        session_factory = create_session_factory(engine)
        lock = DistributedLock(
            coordination_session_factory=session_factory,
            lock_name="graph_rebuild",
            ttl_seconds=60,
            holder_id="worker-a",
        )
        lock.acquire()
        initial_token = lock.fencing_token

        with session_factory() as session:
            with pytest.raises(_DistributedLockLostError, match="fencing token"):
                _guard_publication_lock(
                    session,
                    "worker-a",
                    60,
                    "publication-pre-commit",
                    expected_fencing_token=initial_token - 1,
                )

            renewed_token = _guard_publication_lock(
                session,
                "worker-a",
                60,
                "publication-transaction-start",
                expected_fencing_token=initial_token,
            )
            assert renewed_token is not None
            assert renewed_token >= initial_token

            next_token = _guard_publication_lock(
                session,
                "worker-a",
                60,
                "publication-pre-commit",
                expected_fencing_token=renewed_token,
            )
            assert next_token is not None
            assert next_token >= renewed_token
            session.commit()
    finally:
        engine.dispose()
