"""Unit tests for the staging promotion verification script."""

from unittest.mock import patch

import pytest

from scripts.verify_staging_promotion import (
    _check_database_boundaries,
    _check_operational_evidence,
    _check_persistence_proof,
    _check_provider_labels,
    verify_staging_promotion,
)


def test_check_provider_labels():
    """Test that provider and hosting labels are correctly checked."""
    missing = []
    _check_provider_labels("supabase vercel mapping", missing)
    assert not missing

    missing = []
    _check_provider_labels("some random text", missing)
    assert "Supabase provider label" in missing
    assert "Vercel mapping (frontend/backend traffic)" in missing


def test_check_database_boundaries():
    """Test that database boundary confirmations are correctly checked."""
    missing = []
    _check_database_boundaries(
        "database_url asset_graph_database_url distinct asset_graph_database_url shared-boundary statement", missing
    )
    assert not missing

    missing = []
    _check_database_boundaries("missing boundary confirmation", missing)
    assert "DATABASE_URL boundary confirmation" in missing
    assert "ASSET_GRAPH_DATABASE_URL boundary confirmation" in missing


def test_check_persistence_proof():
    """Test that durability/persistence proofs are correctly checked."""
    missing = []
    _check_persistence_proof("persistence_loaded == true durable preview", missing)
    assert not missing

    missing = []
    _check_persistence_proof("missing proof", missing)
    assert "Persistence-loaded proof (graph.persistence_loaded == true)" in missing
    assert "Durable/non-durable preview label" in missing


def test_check_operational_evidence():
    """Test that operational evidence like smoke tests are correctly checked."""
    missing = []
    _check_operational_evidence("asset smoke evidence named owners scanner summary", missing)
    assert not missing

    missing = []
    _check_operational_evidence("no evidence", missing)
    assert "Asset smoke evidence" in missing


def test_verify_staging_promotion_success(tmp_path):
    """Test successful staging promotion verification."""
    evidence_path = tmp_path / "evidence.md"
    evidence_path.write_text(
        "supabase vercel mapping database_url asset_graph_database_url distinct asset_graph_database_url shared-boundary statement "
        "persistence_loaded == true durable preview asset smoke evidence named owners scanner summary",
        encoding="utf-8",
    )

    with patch("scripts.verify_staging_promotion.Path.is_relative_to", return_value=True), pytest.raises(SystemExit) as exc_info:
        verify_staging_promotion(str(evidence_path))
    assert exc_info.value.code == 0


def test_verify_staging_promotion_failure(tmp_path):
    """Test failed staging promotion verification."""
    evidence_path = tmp_path / "evidence.md"
    evidence_path.write_text("missing almost everything", encoding="utf-8")

    # tmp_path is outside the repo root, so bypass the repo-relative constraint for this unit test.
    with patch("scripts.verify_staging_promotion.Path.is_relative_to", return_value=True), pytest.raises(SystemExit) as exc_info:
        verify_staging_promotion(str(evidence_path))
    assert exc_info.value.code == 1


@patch("scripts.verify_staging_promotion.Path.exists", return_value=True)
@patch("scripts.verify_staging_promotion.Path.is_file", return_value=False)
def test_verify_staging_promotion_directory(mock_is_file, mock_exists):
    """Test that providing a directory instead of a file raises a clean error."""
    with pytest.raises(SystemExit) as exc_info:
        verify_staging_promotion("some_directory")
    assert exc_info.value.code == 1
