"""Cross-boundary restore skew checker comparing Graph and Coordination persistence (H-P2-05).

Verifies that the Graph (``rebuild_jobs``) and Coordination (``distributed_locks``)
database boundaries are consistent after a disaster-recovery restore (or during live
operation with ``--allow-active``), failing closed on leftover running jobs, stale
locks, holder mismatches, or cross-boundary timestamp skew.

Outputs redacted JSON only; never prints connection URLs, credentials, or hostnames.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from src.data.database import create_engine_from_url, create_session_factory
from src.data.db_models import DistributedLockORM, RebuildJobORM, RebuildJobStatus

UTC = timezone.utc

SUCCESS = 0
CHECK_FAILED = 1
USAGE_ERROR = 2


@dataclass(frozen=True)
class BoundarySkewReport:
    """Redacted cross-boundary restore skew evaluation report."""

    status: str
    same_boundary: bool
    running_jobs_count: int
    active_locks_count: int
    total_locks_count: int
    boundary_skew_seconds: float | None
    max_skew_seconds: float
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report to a redacted JSON-compatible dictionary."""
        return {
            "status": self.status,
            "same_boundary": self.same_boundary,
            "running_jobs_count": self.running_jobs_count,
            "active_locks_count": self.active_locks_count,
            "total_locks_count": self.total_locks_count,
            "boundary_skew_seconds": self.boundary_skew_seconds,
            "max_skew_seconds": self.max_skew_seconds,
            "reasons": list(self.reasons),
        }


def _to_aware_utc(value: datetime | None) -> datetime | None:
    """Normalize a datetime value to timezone-aware UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _urls_point_to_same_boundary(graph_url: str, coordination_url: str) -> bool:
    """Return True if both URLs resolve to the same database target."""
    try:
        return make_url(graph_url) == make_url(coordination_url)
    except Exception:
        return graph_url == coordination_url


def evaluate_restore_boundary_skew(
    graph_url: str,
    coordination_url: str,
    *,
    max_skew_seconds: float = 300.0,
    allow_active: bool = False,
    now: datetime | None = None,
) -> BoundarySkewReport:
    """Inspect Graph and Coordination boundaries and evaluate cross-boundary restore skew."""
    if max_skew_seconds < 0:
        raise ValueError("max_skew_seconds must be non-negative")

    current_time = _to_aware_utc(now) if now is not None else datetime.now(UTC)
    same_boundary = _urls_point_to_same_boundary(graph_url, coordination_url)

    graph_engine = create_engine_from_url(graph_url)
    coord_engine = graph_engine if same_boundary else create_engine_from_url(coordination_url)

    try:
        graph_sf = create_session_factory(graph_engine)
        coord_sf = graph_sf if same_boundary else create_session_factory(coord_engine)

        with graph_sf() as graph_session:
            running_jobs = list(
                graph_session.execute(
                    select(RebuildJobORM).where(RebuildJobORM.status == RebuildJobStatus.RUNNING.value)
                )
                .scalars()
                .all()
            )
            graph_latest = _to_aware_utc(graph_session.execute(select(func.max(RebuildJobORM.updated_at))).scalar())

        with coord_sf() as coord_session:
            all_locks = list(coord_session.execute(select(DistributedLockORM)).scalars().all())
            coord_latest = _to_aware_utc(
                coord_session.execute(select(func.max(DistributedLockORM.updated_at))).scalar()
            )
    finally:
        if coord_engine is not graph_engine:
            coord_engine.dispose()
        graph_engine.dispose()

    active_locks = [
        lock
        for lock in all_locks
        if lock.expires_at is not None and _to_aware_utc(lock.expires_at) > current_time  # type: ignore[operator]
    ]
    running_worker_ids = {job.active_worker_id for job in running_jobs if job.active_worker_id}
    active_lock_holders = {lock.holder_id for lock in active_locks if lock.holder_id}

    skew_seconds: float | None = None
    if graph_latest is not None and coord_latest is not None:
        skew_seconds = round(abs((graph_latest - coord_latest).total_seconds()), 3)

    reasons: list[str] = []
    if allow_active:
        if len(running_jobs) > 1:
            reasons.append(f"multiple_running_jobs:{len(running_jobs)}")
        elif len(running_jobs) == 1 and not running_worker_ids.intersection(active_lock_holders):
            reasons.append("running_job_without_matching_active_lock")
        elif len(running_jobs) == 0 and len(active_locks) > 0:
            reasons.append(f"active_lock_without_running_job:{len(active_locks)}")
    else:
        if len(running_jobs) > 0:
            reasons.append(f"post_restore_running_jobs_present:{len(running_jobs)}")
        if len(active_locks) > 0:
            reasons.append(f"post_restore_active_locks_present:{len(active_locks)}")

    if skew_seconds is not None and skew_seconds > max_skew_seconds:
        reasons.append(f"boundary_timestamp_skew_exceeded:{skew_seconds}s>{max_skew_seconds}s")

    return BoundarySkewReport(
        status="PASS" if not reasons else "FAIL",
        same_boundary=same_boundary,
        running_jobs_count=len(running_jobs),
        active_locks_count=len(active_locks),
        total_locks_count=len(all_locks),
        boundary_skew_seconds=skew_seconds,
        max_skew_seconds=max_skew_seconds,
        reasons=tuple(reasons),
    )


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Check Graph vs Coordination database boundaries for restore skew (H-P2-05)."
    )
    parser.add_argument(
        "--graph-url",
        default=None,
        help="Graph database URL (defaults to ASSET_GRAPH_DATABASE_URL env var).",
    )
    parser.add_argument(
        "--coordination-url",
        default=None,
        help="Coordination database URL (defaults to COORDINATION_DATABASE_URL or graph URL).",
    )
    parser.add_argument(
        "--max-skew-seconds",
        type=float,
        default=300.0,
        help="Maximum tolerated timestamp skew between latest Graph and Coordination activity (default: 300).",
    )
    parser.add_argument(
        "--allow-active",
        action="store_true",
        help="Allow a single matched RUNNING job + active lock (live check instead of post-restore check).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point returning 0 on PASS, 1 on FAIL, 2 on usage/configuration error."""
    args = _build_parser().parse_args(argv)
    graph_url = (args.graph_url or os.getenv("ASSET_GRAPH_DATABASE_URL") or "").strip()
    if not graph_url:
        print(
            json.dumps({"status": "ERROR", "reason": "ASSET_GRAPH_DATABASE_URL or --graph-url is required"}),
            file=sys.stderr,
        )
        return USAGE_ERROR
    coordination_url = (args.coordination_url or os.getenv("COORDINATION_DATABASE_URL") or graph_url).strip()

    try:
        report = evaluate_restore_boundary_skew(
            graph_url,
            coordination_url,
            max_skew_seconds=args.max_skew_seconds,
            allow_active=args.allow_active,
        )
    except ValueError as exc:
        print(json.dumps({"status": "ERROR", "reason": str(exc)}), file=sys.stderr)
        return USAGE_ERROR
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "reason": f"database_check_error:{type(exc).__name__}"}), file=sys.stderr)
        return CHECK_FAILED

    print(json.dumps(report.to_dict(), indent=2))
    return SUCCESS if report.status == "PASS" else CHECK_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
