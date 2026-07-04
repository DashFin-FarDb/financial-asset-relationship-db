"""Unit tests for the staging promotion verification script."""

from unittest.mock import patch

import pytest

from scripts.verify_staging_promotion import (
    _check_database_boundaries,
    _check_operational_evidence,
    _check_persistence_proof,
    _check_provider_labels,
    _check_urls,
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
    """Test that durability/persistence proofs are correctly checked via JSON payloads."""
    # Positive case: valid JSON block
    missing = []
    valid_json = """
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
    """
    _check_persistence_proof(valid_json, missing)
    assert not missing

    # Positive case: hosted-readiness JSON with observed_fields dot-keys
    missing = []
    observed_fields_json = """
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
    """
    _check_persistence_proof(observed_fields_json, missing)
    assert not missing

    # Negative case: missing completely
    missing = []
    _check_persistence_proof("missing proof", missing)
    assert (
        "Complete durable graph proof in a single JSON block (requires graph_persistence_configured, graph.persistence_enabled, graph.persistence_loaded, and graph.startup_source == 'persisted')"
        in missing
    )
    assert "Durable/non-durable preview label" in missing

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
    assert (
        "Complete durable graph proof in a single JSON block (requires graph_persistence_configured, graph.persistence_enabled, graph.persistence_loaded, and graph.startup_source == 'persisted')"
        in missing
    )

    # Negative case: bare field outside of `graph` object
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
    assert (
        "Complete durable graph proof in a single JSON block (requires graph_persistence_configured, graph.persistence_enabled, graph.persistence_loaded, and graph.startup_source == 'persisted')"
        in missing
    )

    # Negative case: prose only (does not contain actual JSON object)
    missing = []
    prose_evidence = """
    We expect graph_persistence_configured == true.
    Also graph.persistence_enabled: true and graph.persistence_loaded: true.
    The graph.startup_source should be "persisted".
    durable preview
    """
    _check_persistence_proof(prose_evidence, missing)
    assert (
        "Complete durable graph proof in a single JSON block (requires graph_persistence_configured, graph.persistence_enabled, graph.persistence_loaded, and graph.startup_source == 'persisted')"
        in missing
    )

    # Negative case: required fields split across separate JSON blocks
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
    assert (
        "Complete durable graph proof in a single JSON block (requires graph_persistence_configured, graph.persistence_enabled, graph.persistence_loaded, and graph.startup_source == 'persisted')"
        in missing
    )


def test_check_urls():
    """Test that URLs are correctly checked."""
    missing = []
    _check_urls("https://github.com/org/repo/actions/runs/123", missing)
    assert not missing

    missing = []
    _check_urls("https://github.com/org/repo/actions", missing)
    assert "Specific workflow run URL or artifact URL" in missing
    assert "Generic Actions URLs are not allowed" in missing


def test_check_operational_evidence():
    """Test that operational evidence like smoke tests are correctly checked."""
    missing = []
    _check_operational_evidence(
        "asset smoke evidence hosted readiness health json named owners scanner summary", missing
    )
    assert not missing

    missing = []
    _check_operational_evidence("no evidence", missing)
    assert "Asset smoke evidence" in missing
    assert "hosted readiness" in missing
    assert "health JSON" in missing

    missing = []
    _check_operational_evidence(
        "asset smoke evidence hosted readiness health json named owners scanner summary secret: supersecretvalue",
        missing,
    )
    assert "Non-redacted evidence found (secrets/tokens must be redacted)" in missing


def test_verify_staging_promotion_success(tmp_path):
    """Test successful staging promotion verification."""
    evidence_path = tmp_path / "evidence.md"
    evidence_path.write_text(
        "supabase vercel mapping database_url asset_graph_database_url distinct asset_graph_database_url shared-boundary statement "
        "durable preview "
        "https://github.com/org/repo/actions/runs/123 asset smoke evidence hosted readiness health json named owners scanner summary "
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

    evidence_path_str = str(evidence_path)
    with patch("scripts.verify_staging_promotion.Path.is_relative_to", return_value=True), pytest.raises(SystemExit) as exc_info:
        verify_staging_promotion(evidence_path_str)
    assert exc_info.value.code == 0


def test_verify_staging_promotion_failure(tmp_path):
    """Test failed staging promotion verification."""
    evidence_path = tmp_path / "evidence.md"
    evidence_path.write_text("missing almost everything", encoding="utf-8")

    # tmp_path is outside the repo root, so bypass the repo-relative constraint for this unit test.
    evidence_path_str = str(evidence_path)
    with patch("scripts.verify_staging_promotion.Path.is_relative_to", return_value=True), pytest.raises(SystemExit) as exc_info:
        verify_staging_promotion(evidence_path_str)
    assert exc_info.value.code == 1


@patch("scripts.verify_staging_promotion.Path.exists", return_value=True)
@patch("scripts.verify_staging_promotion.Path.is_file", return_value=False)
def test_verify_staging_promotion_directory(mock_is_file, mock_exists):
    """Test that providing a directory instead of a file raises a clean error."""
    with pytest.raises(SystemExit) as exc_info:
        verify_staging_promotion("some_directory")
    assert exc_info.value.code == 1
