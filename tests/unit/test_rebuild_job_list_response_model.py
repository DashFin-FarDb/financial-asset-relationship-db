"""Unit tests for rebuild job-list API response contracts."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from api.api_models import RebuildJobListResponse, RebuildJobResponse, RebuildJobStatus


def _job_response(job_id: str) -> RebuildJobResponse:
    """Build a minimal rebuild job response for list model tests."""
    now = datetime.now(timezone.utc)
    return RebuildJobResponse(
        job_id=job_id,
        status=RebuildJobStatus.PENDING,
        source="sample",
        requested_by="operator",
        created_at=now,
        updated_at=now,
        started_at=None,
        completed_at=None,
        duration_ms=None,
        node_count=None,
        edge_count=None,
        failure_category=None,
        failure_message=None,
    )


def test_rebuild_job_list_response_exposes_truncation_contract() -> None:
    """Rebuild job list responses should expose page count, total, and has_more."""
    response = RebuildJobListResponse(
        jobs=[_job_response("job-1")],
        count=1,
        total=2,
        hasMore=True,
    )

    assert response.model_dump()["jobs"][0]["job_id"] == "job-1"
    assert response.count == 1
    assert response.total == 2
    assert response.has_more is True


def test_rebuild_job_list_response_requires_truncation_fields() -> None:
    """The additive contract fields should be required for new API responses."""
    with pytest.raises(ValidationError):
        RebuildJobListResponse(jobs=[], count=0)  # type: ignore[call-arg]
