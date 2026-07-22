"""Contract tests for production-container.yml persistence smoke (H-P1-05)."""

from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "production-container.yml"
COMPOSE_PATH = REPO_ROOT / "docker-compose.production.yml"

GRADIO_WORKFLOWS = (
    REPO_ROOT / ".github" / "workflows" / "docker.yml",
    REPO_ROOT / ".github" / "workflows" / "docker-image.yml",
    REPO_ROOT / ".github" / "workflows" / "docker-publish.yml",
)


@pytest.fixture(name="production_container_raw")
def production_container_raw_fixture() -> str:
    """Return raw production-container.yml text."""
    return WORKFLOW_PATH.read_text(encoding="utf-8")


@pytest.fixture(name="production_container_workflow")
def production_container_workflow_fixture() -> dict:
    """Load production-container.yml with ``on`` normalised for PyYAML 1.1."""
    with open(WORKFLOW_PATH, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert isinstance(data, dict), "production-container.yml must parse to a mapping"
    if True in data and "on" not in data:
        data["on"] = data.pop(True)
    return data


def test_production_container_workflow_exists() -> None:
    """H-P1-05 requires the production container CI workflow."""
    assert WORKFLOW_PATH.is_file()


def test_required_job_id_unchanged(production_container_workflow: dict) -> None:
    """H-P1-04 required check name must remain build-and-smoke-test."""
    assert "build-and-smoke-test" in production_container_workflow["jobs"]


def test_builds_production_dockerfiles(production_container_raw: str) -> None:
    """Production smoke must build API and frontend Dockerfiles, not Gradio."""
    assert "Dockerfile.api" in production_container_raw
    assert "Dockerfile.frontend" in production_container_raw
    assert "-f Dockerfile " not in production_container_raw
    assert "--file Dockerfile " not in production_container_raw


def test_persistence_smoke_uses_durable_volume(production_container_raw: str) -> None:
    """API persistence smoke must mount a durable volume under /data."""
    assert "docker volume create" in production_container_raw
    assert "/data" in production_container_raw
    assert "ASSET_GRAPH_DATABASE_URL" in production_container_raw
    assert "sqlite:////data/fardb.db" in production_container_raw


def test_persistence_smoke_rebuilds_then_restarts(production_container_raw: str) -> None:
    """Prove rebuild+persist then container restart before persistence asserts."""
    assert "/api/graph/rebuild" in production_container_raw
    assert "/token" in production_container_raw
    assert "api_persist_seed" in production_container_raw
    assert "api_persist_reload" in production_container_raw


def test_persistence_fields_asserted_after_reload(production_container_raw: str) -> None:
    """Local curl/jq asserts must match hosted persistence gate fields."""
    for marker in (
        "graph_persistence_configured",
        "graph.persistence_enabled",
        "graph.persistence_loaded",
        "graph.startup_source",
        "persisted",
        "/api/assets?per_page=1",
    ):
        assert marker in production_container_raw, f"Missing persistence assert marker: {marker}"


def test_evidence_boundary_excludes_hosted_promotion(production_container_raw: str) -> None:
    """Workflow header must not claim hosted promotion evidence."""
    assert "DOES NOT PROVE" in production_container_raw
    assert "HOSTED_READINESS_BASE_URL" in production_container_raw or "hosted" in production_container_raw.lower()
    assert "staging-promotion.yml" in production_container_raw
    assert "production-promotion.yml" in production_container_raw


def test_does_not_invoke_loopback_hosted_readiness_script(production_container_raw: str) -> None:
    """Hosted readiness script rejects loopback; CI must not invoke it as a step command."""
    assert "python scripts/check_hosted_readiness.py" not in production_container_raw
    assert "python3 scripts/check_hosted_readiness.py" not in production_container_raw
    # Comment may mention the script to explain why curl/jq is used instead.
    assert "rejects loopback" in production_container_raw


def test_validates_production_compose_config(production_container_raw: str) -> None:
    """CI must validate docker-compose.production.yml renders."""
    assert "docker-compose.production.yml" in production_container_raw
    assert "docker compose -f docker-compose.production.yml config" in production_container_raw


def test_production_compose_declares_persistence_defaults() -> None:
    """Production compose must default graph + auth DB URLs onto the data volume."""
    text = COMPOSE_PATH.read_text(encoding="utf-8")
    assert "api-data:/data" in text or "api-data" in text
    assert "ASSET_GRAPH_DATABASE_URL" in text
    assert "sqlite:////data/fardb.db" in text


@pytest.mark.parametrize("workflow_path", GRADIO_WORKFLOWS, ids=lambda p: p.name)
def test_gradio_docker_workflows_labeled_non_production(workflow_path: Path) -> None:
    """Gradio Docker workflows must be explicitly labeled non-production."""
    assert workflow_path.is_file()
    text = workflow_path.read_text(encoding="utf-8")
    assert "non-production" in text.lower()
    assert "Gradio" in text
    assert "production-container.yml" in text


def test_gradio_dockerfile_marked_non_production() -> None:
    """Root Dockerfile must declare Gradio as non-production."""
    text = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "NON-PRODUCTION" in text
    assert "Dockerfile.api" in text
