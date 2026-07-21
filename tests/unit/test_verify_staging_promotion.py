"""Unit tests for the staging promotion verification script."""

import os
from unittest.mock import patch

import pytest

from scripts.verify_staging_promotion import (
    _check_database_boundaries,
    _check_hardening_foundation,
    _check_operational_evidence,
    _check_persistence_proof,
    _check_provider_labels,
    _check_urls,
    _read_evidence_file,
    verify_staging_promotion,
)

HARDENING_IDS = "hardening_ids: H-P0-01, H-P0-02, H-P0-03, H-P0-04, H-P0-06"
TOPOLOGY_MARKER = "topology: jobs=asset_graph; locks=coordination"
HARDENING_MARKERS = f"{HARDENING_IDS}\n{TOPOLOGY_MARKER}\ndb_authz: PASS|run-123\n"
DB_AUTHZ_REQUIRED_MSG = "db_authz: PASS|<opaque-ref> (bare PASS is not accepted)"
DB_AUTHZ_OPAQUE_REF_ERROR = (
    "db_authz opaque ref must match run-<digits>, artifact-<digits>, "
    "<prefix>-run-<digits>, or a numeric workflow run id (>=6 digits)"
)
OPERATIONAL_EVIDENCE = (
    "asset smoke evidence hosted readiness --require-persistence health json named owners scanner summary"
)


def _hardening_content(db_authz_line: str, hardening_ids: str = HARDENING_IDS) -> str:
    """Build a minimal hardening marker block for foundation checks."""
    return f"{hardening_ids}\n{TOPOLOGY_MARKER}\n{db_authz_line}"


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
def test_check_hardening_foundation_accepts_required_markers():
    """Test that P0 hardening markers satisfy the foundation check."""
    missing = []
    _check_hardening_foundation(HARDENING_MARKERS, missing)
    assert not missing


@pytest.mark.unit
def test_check_hardening_foundation_rejects_bare_db_authz_pass():
    """Test that bare db_authz: PASS is rejected without an opaque ref."""
    missing = []
    _check_hardening_foundation(_hardening_content("db_authz: PASS\n"), missing)
    assert DB_AUTHZ_REQUIRED_MSG in missing


@pytest.mark.unit
@pytest.mark.parametrize(
    "db_authz_line",
    [
        "db_authz: PASS|TBD\n",
        "db_authz: PASS|TODO\n",
        "db_authz: PASS|N/A\n",
        "db_authz: PASS|pending\n",
        "db_authz: PASS|<replace-with-workflow-run-id>\n",
        "db_authz: PASS|REPLACE-WITH-WORKFLOW-RUN-ID\n",
        "db_authz: PASS|run-12\n",  # too few digits
        "db_authz: PASS|12345\n",  # bare numeric id too short
    ],
)
def test_check_hardening_foundation_rejects_invalid_opaque_ref(db_authz_line):
    """Test that placeholder and non-shaped opaque refs are rejected by allowlist."""
    missing = []
    _check_hardening_foundation(_hardening_content(db_authz_line), missing)
    assert DB_AUTHZ_OPAQUE_REF_ERROR in missing


@pytest.mark.unit
@pytest.mark.parametrize(
    "opaque_ref",
    ["run-123", "artifact-456", "1506-run-123456", "1234567890"],
)
def test_check_hardening_foundation_accepts_shaped_opaque_refs(opaque_ref):
    """Test that allowlisted run/artifact opaque refs are accepted."""
    missing = []
    _check_hardening_foundation(
        _hardening_content(f"db_authz: PASS|{opaque_ref}\n"),
        missing,
    )
    assert not missing


@pytest.mark.unit
def test_check_hardening_foundation_requires_ids_topology_and_db_authz():
    """Test that missing hardening markers are reported distinctly."""
    missing = []
    _check_hardening_foundation("no hardening markers here", missing)
    assert "hardening_ids marker with P0 foundation IDs" in missing
    assert "topology: jobs=asset_graph; locks=coordination" in missing
    assert DB_AUTHZ_REQUIRED_MSG in missing

    missing = []
    _check_hardening_foundation(
        _hardening_content(
            "db_authz: FAIL\n",
            hardening_ids="hardening_ids: H-P0-01, H-P0-02",
        ),
        missing,
    )
    assert any("hardening_ids missing required IDs" in item for item in missing)
    assert DB_AUTHZ_REQUIRED_MSG in missing


@pytest.mark.unit
@pytest.mark.parametrize(
    "db_authz_line",
    [
        "db_authz: PASSED\n",
        "db_authz: PASSWORD\n",
        "db_authz: PASSAGE\n",
        "db_authz: PASS\n",
    ],
)
def test_check_hardening_foundation_rejects_non_exact_db_authz_pass(db_authz_line):
    """Test that db_authz only accepts PASS|<opaque-ref> markers."""
    missing = []
    _check_hardening_foundation(_hardening_content(db_authz_line), missing)
    assert DB_AUTHZ_REQUIRED_MSG in missing


@pytest.mark.unit
@pytest.mark.parametrize("invalid_id", ["H-P0-06-deferred", "H-P0-060"])
def test_check_hardening_foundation_requires_exact_hardening_ids(invalid_id):
    """Test that hardening IDs are validated as discrete identifiers."""
    missing = []
    _check_hardening_foundation(
        _hardening_content(
            "db_authz: PASS|run-123\n",
            hardening_ids=("hardening_ids: H-P0-01, H-P0-02, H-P0-03, H-P0-04, " + invalid_id),
        ),
        missing,
    )
    assert "hardening_ids missing required IDs: H-P0-06" in missing


@pytest.mark.unit
def test_check_hardening_foundation_ignores_comment_text_after_comma_tokens():
    """Test that comma tokenization keeps only exact ID tokens."""
    missing = []
    _check_hardening_foundation(
        _hardening_content(
            "db_authz: PASS|run-123\n",
            hardening_ids=f"{HARDENING_IDS} # H-P0-99 elsewhere",
        ),
        missing,
    )
    assert not missing


@pytest.mark.unit
def test_check_operational_evidence():
    """Test that operational evidence like smoke tests are correctly checked."""
    missing = []
    _check_operational_evidence(OPERATIONAL_EVIDENCE, missing)
    assert not missing

    missing = []
    _check_operational_evidence("no evidence", missing)
    assert "Asset smoke evidence" in missing
    assert "hosted readiness" in missing
    assert "health JSON" in missing

    missing = []
    _check_operational_evidence(
        f"{OPERATIONAL_EVIDENCE} secret: supersecretvalue",
        missing,
    )
    assert "Non-redacted evidence found (secrets/tokens must be redacted)" in missing

    missing = []
    _check_operational_evidence(
        f"{OPERATIONAL_EVIDENCE} secret: benign-narrative-string",
        missing,
    )
    assert "Non-redacted evidence found (secrets/tokens must be redacted)" in missing

    missing = []
    _check_operational_evidence(
        f"{OPERATIONAL_EVIDENCE} secret: {'a' * 10000}",
        missing,
    )
    assert "Non-redacted evidence found (secrets/tokens must be redacted)" in missing


@pytest.mark.unit
def test_verify_staging_promotion_success(tmp_path):
    """Test successful staging promotion verification."""
    evidence_path = tmp_path / "evidence.md"
    evidence_path.write_text(
        HARDENING_MARKERS + "supabase vercel mapping database_url asset_graph_database_url "
        "distinct asset_graph_database_url shared-boundary statement "
        "durable preview "
        "https://github.com/org/repo/actions/runs/123 "
        f"{OPERATIONAL_EVIDENCE} "
        "```json\n"
        "{\n"
        '    "graph_persistence_configured": true,\n'
        '    "graph": {\n'
        '        "persistence_enabled": true,\n'
        '        "persistence_loaded": true,\n'
        '        "startup_source": "persisted"\n'
        "    }\n"
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
