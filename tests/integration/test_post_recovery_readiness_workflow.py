"""Contract tests for post-recovery-readiness.yml (H-P1-03)."""

from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/post-recovery-readiness.yml"


@pytest.fixture(name="post_recovery_workflow")
def post_recovery_workflow_fixture() -> dict:
    """Load post-recovery-readiness.yml with the ``on`` key normalised for PyYAML 1.1."""
    with open(WORKFLOW_PATH, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert isinstance(data, dict), "post-recovery-readiness.yml must parse to a mapping"
    if True in data and "on" not in data:
        data["on"] = data.pop(True)
    return data


@pytest.fixture(name="post_recovery_raw")
def post_recovery_raw_fixture() -> str:
    """Return the raw post-recovery-readiness.yml text."""
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def test_post_recovery_workflow_exists() -> None:
    """H-P1-03 requires a dedicated post-recovery re-smoke workflow."""
    assert WORKFLOW_PATH.is_file()
    assert WORKFLOW_PATH.read_text(encoding="utf-8").startswith("---\n")


def test_post_recovery_is_manual_dispatch_only(post_recovery_workflow: dict) -> None:
    """Recovery re-smoke must be an explicit operator dispatch, not automatic."""
    assert set(post_recovery_workflow["on"]) == {"workflow_dispatch"}
    inputs = post_recovery_workflow["on"]["workflow_dispatch"]["inputs"]
    assert "recovery_context" in inputs
    assert "target_environment" in inputs
    assert "base_url" in inputs
    assert "timeout" in inputs
    assert "base_url_label" in inputs


def test_post_recovery_context_options(post_recovery_workflow: dict) -> None:
    """Recovery context must be limited to post-rollback and post-restore."""
    options = post_recovery_workflow["on"]["workflow_dispatch"]["inputs"]["recovery_context"]["options"]
    assert options == ["post-rollback", "post-restore"]


def test_post_recovery_target_environment_options(post_recovery_workflow: dict) -> None:
    """Target environment must resolve to staging or production Environments."""
    options = post_recovery_workflow["on"]["workflow_dispatch"]["inputs"]["target_environment"]["options"]
    assert options == ["staging", "production"]
    env_name = post_recovery_workflow["jobs"]["recovery-readiness"]["environment"]
    if isinstance(env_name, dict):
        env_name = env_name.get("name", "")
    assert "target_environment" in str(env_name)


def test_post_recovery_uses_job_level_permissions(post_recovery_workflow: dict) -> None:
    """Permissions must stay minimal and job-scoped."""
    assert "permissions" not in post_recovery_workflow
    assert post_recovery_workflow["jobs"]["recovery-readiness"]["permissions"] == {"contents": "read"}


def test_post_recovery_enforces_persistence_and_assets_smoke(post_recovery_raw: str) -> None:
    """Mandatory re-smoke must use --require-persistence (assets-smoke auto-enabled)."""
    assert "check_hosted_readiness.py" in post_recovery_raw
    assert "--json" in post_recovery_raw
    assert "--require-persistence" in post_recovery_raw
    assert "checks.assets_smoke.passed" in post_recovery_raw
    assert "assets.total" in post_recovery_raw
    assert '[ "$total" -gt 0 ]' in post_recovery_raw or '"$total" -gt 0' in post_recovery_raw


def test_post_recovery_fails_closed_without_base_url(post_recovery_raw: str) -> None:
    """Missing URL must fail; thin hosted-readiness skip path is not allowed."""
    assert "hosted readiness base URL is required" in post_recovery_raw
    assert "Hosted readiness check skipped" not in post_recovery_raw


def test_post_recovery_writes_metadata_and_placeholders(post_recovery_raw: str) -> None:
    """Artifact bundle must include recovery metadata and empty-file placeholders."""
    assert "recovery-metadata.json" in post_recovery_raw
    assert "H-P1-03" in post_recovery_raw
    assert "[ ! -s readiness-output.json ]" in post_recovery_raw
    assert "[ ! -s recovery-metadata.json ]" in post_recovery_raw


def test_post_recovery_uploads_context_named_artifact(
    post_recovery_workflow: dict,
    post_recovery_raw: str,
) -> None:
    """Artifact name must encode recovery context, not promotion names."""
    upload_steps = [
        step
        for step in post_recovery_workflow["jobs"]["recovery-readiness"]["steps"]
        if str(step.get("uses", "")).startswith("actions/upload-artifact@")
    ]
    assert len(upload_steps) == 1
    assert upload_steps[0].get("if") == "always()"
    assert upload_steps[0]["with"]["name"] == "${{ inputs.recovery_context }}-readiness"
    assert "staging-readiness" not in post_recovery_raw
    assert "production-readiness" not in post_recovery_raw
    assert "release-evidence" not in post_recovery_raw


def test_post_recovery_upload_paths_exclude_secrets(post_recovery_workflow: dict) -> None:
    """Upload-artifact steps must not reference repository secrets."""
    for step in post_recovery_workflow["jobs"]["recovery-readiness"]["steps"]:
        if "actions/upload-artifact" in str(step.get("uses", "")):
            assert "secrets." not in str(step)
