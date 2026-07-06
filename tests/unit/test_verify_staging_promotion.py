"""Unit tests for the staging promotion verification script."""

import os
from unittest.mock import patch

import pytest

from scripts.verify_staging_promotion import (
    _check_database_boundaries,
    _check_operational_evidence,
    _check_persistence_proof,
    _check_provider_labels,
    _check_urls,
    _read_evidence_file,
    verify_staging_promotion,
)


@pytest.mark.unit
def test_check_provider_labels():
    """Test that provider and hosting labels are correctly checked."""
    missing = []
    _check_provider_labels("supabase vercel mapping", missing)
    assert not missing

    missing = []
    _check_provider_labels("some random text", missing)
    assert "Supabase provider label" in missing
    assert "Vercel mapping (frontend/backend traffic)" in missing


@pytest.mark.unit
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


@pytest.mark.unit
def test_check_database_boundaries_requires_distinct_near_asset_graph_url():
    """Test that unrelated distinct wording does not confirm database separation."""
    missing = []
    _check_database_boundaries(
        "database_url asset_graph_database_url coordination_database_url\n"
        + ("operational evidence " * 8)
        + "a distinct operational checklist item appears elsewhere",
        missing,
    )
    assert "Distinct ASSET_GRAPH_DATABASE_URL boundary or approved exception" in missing


@pytest.mark.unit
def test_check_database_boundaries_accepts_nearby_distinct_boundary():
    """Test that nearby natural-language distinct wording still satisfies the boundary check."""
    missing = []
    _check_database_boundaries(
        "database_url asset_graph_database_url coordination_database_url\n"
        "asset_graph_database_url is distinct from coordination_database_url within this deployment boundary",
        missing,
    )
    assert "Distinct ASSET_GRAPH_DATABASE_URL boundary or approved exception" not in missing


@pytest.mark.unit
@pytest.mark.parametrize(
    "proof_json",
    [
        """
        ```json
        {
          "graph_persistence_configured": true,
          "graph": {
            "persistence_enabled": true,
            "persistence_loaded": true,
            "startup_source": "persisted"
          }
        }
        ```
        durable preview
        """,
        """
        ```json
        {
          "observed_fields": {
            "graph_persistence_configured": true,
            "graph.persistence_enabled": true,
            "graph.persistence_loaded": true,
            "graph.startup_source": "persisted"
          }
        }
        ```
        durable preview
        """,
    ],
)
def test_persistence_proof_valid_json(proof_json):
    """Test valid persistence proofs with supported JSON shapes."""
    missing = []
    _check_persistence_proof(proof_json, missing)
    assert not missing


@pytest.mark.unit
def test_persistence_proof_missing():
    """Test missing persistence proofs entirely."""
    missing = []
    _check_persistence_proof("missing proof", missing)
    assert any("Complete durable graph proof in a single JSON block" in m for m in missing)
    assert "Durable/non-durable preview label" in missing


@pytest.mark.unit
def test_persistence_proof_invalid_data():
    """Test invalid JSON data for persistence proofs (false values, wrong source, prose)."""
    # Negative cases: false boolean values and wrong startup_source
    missing = []
    false_json = """
    {
      "graph_persistence_configured": false,
      "graph": {
        "persistence_enabled": false,
        "persistence_loaded": false,
        "startup_source": "sample"
      }
    }
    durable preview
    """
    _check_persistence_proof(false_json, missing)
    assert any("Complete durable graph proof in a single JSON block" in m for m in missing)

    missing = []
    bare_json = """
    {
      "graph_persistence_configured": true,
      "persistence_enabled": true,
      "persistence_loaded": true,
      "startup_source": "persisted",
      "graph": {}
    }
    durable preview
    """
    _check_persistence_proof(bare_json, missing)
    assert any("Complete durable graph proof in a single JSON block" in m for m in missing)

    missing = []
    prose_evidence = """
    We expect graph_persistence_configured == true.
    Also graph.persistence_enabled: true and graph.persistence_loaded: true.
    The graph.startup_source should be "persisted".
    durable preview
    """
    _check_persistence_proof(prose_evidence, missing)
    assert any("Complete durable graph proof in a single JSON block" in m for m in missing)

    missing = []
    split_json = """
    Here is the first block:
    ```json
    {
      "graph_persistence_configured": true
    }
    ```
    And the second block:
    ```json
    {
      "graph": {
        "persistence_enabled": true,
        "persistence_loaded": true,
        "startup_source": "persisted"
      }
    }
    ```
    durable preview
    """
    _check_persistence_proof(split_json, missing)
    assert any("Complete durable graph proof in a single JSON block" in m for m in missing)


@pytest.mark.unit
def test_check_urls():
    """Test that URLs are correctly checked."""
    missing = []
    _check_urls("https://github.com/org/repo/actions/runs/123", missing)
    assert not missing

    missing = []
    _check_urls("https://github.com/org/repo/actions", missing)
    assert "Specific workflow run URL or artifact URL" in missing
    assert "Generic Actions URLs are not allowed" in missing


@pytest.mark.unit
def test_check_operational_evidence():
    """Test that operational evidence like smoke tests are correctly checked."""
    missing = []
    _check_operational_evidence(
        "asset smoke evidence hosted readiness --require-persistence health json named owners scanner summary", missing
    )
    assert not missing

    missing = []
    _check_operational_evidence("no evidence", missing)
    assert "Asset smoke evidence" in missing
    assert "hosted readiness" in missing
    assert "health JSON" in missing

    missing = []
    _check_operational_evidence(
        "asset smoke evidence hosted readiness --require-persistence health json named owners scanner summary secret: supersecretvalue",
        missing,
    )
    assert "Non-redacted evidence found (secrets/tokens must be redacted)" in missing

    missing = []
    _check_operational_evidence(
        "asset smoke evidence hosted readiness --require-persistence health json named owners scanner summary "
        "secret: benign-narrative-string",
        missing,
    )
    assert "Non-redacted evidence found (secrets/tokens must be redacted)" in missing

    missing = []
    _check_operational_evidence(
        "asset smoke evidence hosted readiness --require-persistence health json named owners scanner summary "
        f"secret: {'a' * 10000}",
        missing,
    )
    assert "Non-redacted evidence found (secrets/tokens must be redacted)" in missing


@pytest.mark.unit
def test_verify_staging_promotion_success(tmp_path):
    """Test successful staging promotion verification."""
    evidence_path = tmp_path / "evidence.md"
    evidence_path.write_text(
        "supabase vercel mapping database_url asset_graph_database_url distinct asset_graph_database_url shared-boundary statement "
        "durable preview "
        "https://github.com/org/repo/actions/runs/123 asset smoke evidence hosted readiness --require-persistence health json named owners scanner summary "
        "```json\n"
        "{\n"
        '  "graph_persistence_configured": true,\n'
        '  "graph": {\n'
        '    "persistence_enabled": true,\n'
        '    "persistence_loaded": true,\n'
        '    "startup_source": "persisted"\n'
        "  }\n"
        "}\n"
        "```",
        encoding="utf-8",
    )

    with (
        patch("scripts.verify_staging_promotion.REPO_ROOT", tmp_path),
        pytest.raises(SystemExit) as exc_info,
    ):
        verify_staging_promotion("evidence.md")
    assert exc_info.value.code == 0


@pytest.mark.unit
def test_verify_staging_promotion_failure(tmp_path):
    """Test failed staging promotion verification."""
    evidence_path = tmp_path / "evidence.md"
    evidence_path.write_text("missing almost everything", encoding="utf-8")

    with (
        patch("scripts.verify_staging_promotion.REPO_ROOT", tmp_path),
        pytest.raises(SystemExit) as exc_info,
    ):
        verify_staging_promotion("evidence.md")
    assert exc_info.value.code == 1


@pytest.mark.unit
@patch("scripts.verify_staging_promotion.Path.exists", return_value=True)
@patch("scripts.verify_staging_promotion.Path.is_file", return_value=False)
def test_verify_staging_promotion_directory(mock_is_file, mock_exists):
    """Test that providing a directory instead of a file raises a clean error."""
    with pytest.raises(SystemExit) as exc_info:
        verify_staging_promotion("some_directory")
    assert exc_info.value.code == 1


@pytest.mark.unit
def test_verify_staging_promotion_rejects_traversal_before_filesystem_access():
    """Test that path traversal is rejected before symlink checks touch the filesystem."""
    with patch("scripts.verify_staging_promotion.Path.is_symlink", side_effect=AssertionError("unexpected access")):
        exc_info = pytest.raises(SystemExit, verify_staging_promotion, "../outside.md")
    assert exc_info.value.code == 1


@pytest.mark.unit
def test_verify_staging_promotion_rejects_absolute_path_before_filesystem_access(tmp_path):
    """Test that absolute paths are rejected before symlink checks touch the filesystem."""
    absolute_path = str(tmp_path / "evidence.md")
    with patch("scripts.verify_staging_promotion.Path.is_symlink", side_effect=AssertionError("unexpected access")):
        exc_info = pytest.raises(SystemExit, verify_staging_promotion, absolute_path)
    assert exc_info.value.code == 1


@pytest.mark.unit
def test_verify_staging_promotion_symlink(tmp_path):
    """Test that providing a real symlink raises a clean error before path resolution."""
    target = tmp_path / "evidence.md"
    target.write_text("supabase vercel mapping", encoding="utf-8")
    symlink = tmp_path / "evidence-link.md"
    try:
        symlink.symlink_to(target)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Symlink creation is not supported in this environment: {exc}")

    with patch("scripts.verify_staging_promotion.REPO_ROOT", tmp_path):
        exc_info = pytest.raises(SystemExit, verify_staging_promotion, "evidence-link.md")
    assert exc_info.value.code == 1


@pytest.mark.unit
def test_read_evidence_file_rejects_fifo_without_blocking(tmp_path):
    """Test that a FIFO is rejected without waiting for a writer."""
    if not hasattr(os, "mkfifo"):
        pytest.skip("FIFO creation is not supported in this environment")

    fifo_path = tmp_path / "evidence.fifo"
    os.mkfifo(fifo_path)

    with patch("scripts.verify_staging_promotion.REPO_ROOT", tmp_path):
        with pytest.raises(OSError):
            _read_evidence_file("evidence.fifo")
