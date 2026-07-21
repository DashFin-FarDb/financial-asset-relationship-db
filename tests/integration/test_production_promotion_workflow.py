"""Contract tests for the production-promotion.yml GitHub Actions workflow (H-P1-02)."""

from pathlib import Path
from unittest import TestCase

import pytest
import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/production-promotion.yml"
EXTERNAL_REFERENCE_MARKERS = ("scripts/", ".github/")
ASSERTIONS = TestCase()


@pytest.fixture(name="production_promotion_workflow")
def production_promotion_workflow_fixture() -> dict:
    """Load production-promotion.yml with the ``on`` key normalised for PyYAML 1.1."""
    with open(WORKFLOW_PATH, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    ASSERTIONS.assertIsInstance(data, dict, "production-promotion.yml must parse to a mapping")
    if True in data and "on" not in data:
        data["on"] = data.pop(True)
    return data


@pytest.fixture(name="production_promotion_raw")
def production_promotion_raw_fixture() -> str:
    """Return the raw production-promotion.yml text."""
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _environment_name(environment: object) -> str:
    """Return the environment name whether configured as a string or mapping."""
    if isinstance(environment, dict):
        return str(environment.get("name", ""))
    return str(environment)


def _step_references_external_path(step: dict) -> bool:
    """Return whether a workflow step references repository scripts or local actions."""
    step_refs = (str(step.get("run") or ""), str(step.get("uses") or ""))
    return any(marker in step_ref for step_ref in step_refs for marker in EXTERNAL_REFERENCE_MARKERS)


def test_production_promotion_workflow_exists() -> None:
    """H-P1-02 requires a production twin workflow file."""
    ASSERTIONS.assertTrue(WORKFLOW_PATH.is_file())


def test_production_promotion_is_manual_dispatch_only(production_promotion_workflow: dict) -> None:
    """Production promotion must be an explicit operator dispatch, not automatic."""
    ASSERTIONS.assertEqual({"workflow_dispatch"}, set(production_promotion_workflow["on"]))
    inputs = production_promotion_workflow["on"]["workflow_dispatch"]["inputs"]
    ASSERTIONS.assertIn("evidence_file", inputs)
    ASSERTIONS.assertIn("base_url", inputs)
    ASSERTIONS.assertIn("tags", inputs)


def test_production_promotion_requires_main_before_environment(
    production_promotion_workflow: dict,
) -> None:
    """Environment-gated job must wait for a main-ref guard with no Environment secrets."""
    jobs = production_promotion_workflow["jobs"]
    ASSERTIONS.assertIn("require-main", jobs)
    ASSERTIONS.assertNotIn("environment", jobs["require-main"])
    ASSERTIONS.assertEqual({}, jobs["require-main"]["permissions"])
    needs = jobs["promotion-gate"]["needs"]
    if isinstance(needs, list):
        ASSERTIONS.assertIn("require-main", needs)
    else:
        ASSERTIONS.assertEqual("require-main", needs)
    ASSERTIONS.assertIn("refs/heads/main", WORKFLOW_PATH.read_text(encoding="utf-8"))


def test_production_promotion_uses_job_level_permissions(production_promotion_workflow: dict) -> None:
    """Production permissions must be scoped to the job that needs repository contents."""
    ASSERTIONS.assertNotIn("permissions", production_promotion_workflow)
    ASSERTIONS.assertEqual({"contents": "read"}, production_promotion_workflow["jobs"]["promotion-gate"]["permissions"])


def test_production_promotion_targets_production_environments(
    production_promotion_workflow: dict,
) -> None:
    """Job environment must resolve to production or production-manual-gate."""
    env_name = _environment_name(production_promotion_workflow["jobs"]["promotion-gate"]["environment"])
    ASSERTIONS.assertIn("production-manual-gate", env_name)
    ASSERTIONS.assertIn("production", env_name)
    ASSERTIONS.assertNotIn("staging", env_name)


def test_production_promotion_binds_readiness_to_environment_secret(
    production_promotion_raw: str,
) -> None:
    """Production readiness must use HOSTED_READINESS_BASE_URL, not an unchecked override."""
    ASSERTIONS.assertIn("HOSTED_READINESS_BASE_URL secret is required", production_promotion_raw)
    ASSERTIONS.assertIn("base_url must match HOSTED_READINESS_BASE_URL", production_promotion_raw)
    ASSERTIONS.assertIn('URL="$HOSTED_READINESS_BASE_URL"', production_promotion_raw)
    ASSERTIONS.assertNotIn("BASE_URL_INPUT:-$HOSTED_READINESS_BASE_URL", production_promotion_raw)


def test_production_promotion_enforces_persistence_and_assets_smoke(
    production_promotion_raw: str,
) -> None:
    """Live readiness must use --require-persistence (assets-smoke auto-enabled)."""
    ASSERTIONS.assertIn("check_hosted_readiness.py", production_promotion_raw)
    ASSERTIONS.assertIn("--require-persistence", production_promotion_raw)
    ASSERTIONS.assertIn("checks.assets_smoke.passed", production_promotion_raw)
    ASSERTIONS.assertIn("assets.total", production_promotion_raw)
    ASSERTIONS.assertTrue(
        '[ "$total" -gt 0 ]' in production_promotion_raw or '"$total" -gt 0' in production_promotion_raw
    )


def test_production_promotion_reuses_evidence_verifier(production_promotion_raw: str) -> None:
    """Reuse the shared evidence verifier; do not invent a production-only copy."""
    ASSERTIONS.assertIn("verify_staging_promotion.py", production_promotion_raw)
    ASSERTIONS.assertIn("check_database_authorization.py", production_promotion_raw)


def test_production_promotion_requires_graph_and_coordination_db_secrets(
    production_promotion_raw: str,
) -> None:
    """Authz must not pass when only app/postgres URLs are configured."""
    ASSERTIONS.assertIn("missing_asset_graph_database_url", production_promotion_raw)
    ASSERTIONS.assertIn("missing_auth_database_url", production_promotion_raw)
    ASSERTIONS.assertIn("missing_coordination_database_url", production_promotion_raw)
    ASSERTIONS.assertIn("ASSET_GRAPH_DATABASE_URL on production", production_promotion_raw)
    ASSERTIONS.assertIn("COORDINATION_DATABASE_URL on production", production_promotion_raw)
    ASSERTIONS.assertNotIn("no_database_url_configured", production_promotion_raw)


def test_production_promotion_limits_external_script_steps(
    production_promotion_workflow: dict,
) -> None:
    """Branch coherence: at most two steps may reference scripts/ or local .github paths."""
    external_refs = sum(
        1
        for step in production_promotion_workflow["jobs"]["promotion-gate"]["steps"]
        if _step_references_external_path(step)
    )
    ASSERTIONS.assertLessEqual(external_refs, 2)


def test_production_promotion_uploads_production_artifacts(
    production_promotion_workflow: dict,
) -> None:
    """Artifact bundle must be named for production, not staging."""
    upload_steps = [
        step
        for step in production_promotion_workflow["jobs"]["promotion-gate"]["steps"]
        if str(step.get("uses", "")).startswith("actions/upload-artifact@")
    ]
    ASSERTIONS.assertEqual(1, len(upload_steps))
    ASSERTIONS.assertEqual("production-readiness", upload_steps[0]["with"]["name"])


def test_production_promotion_placeholder_rejects_empty_artifacts(
    production_promotion_raw: str,
) -> None:
    """Empty readiness/authz files must be replaced with skipped placeholders."""
    ASSERTIONS.assertIn("[ ! -s readiness-output.json ]", production_promotion_raw)
    ASSERTIONS.assertIn("[ ! -s db-authz-output.json ]", production_promotion_raw)
