"""
Integration tests for the Bearer security scanning GitHub Actions workflow.

Validates structure, triggers, permissions, steps, SARIF upload,
and security best practices.
"""

import re
from pathlib import Path
from urllib.parse import urlparse

import pytest
import yaml

# -------------------------
# Fixtures
# -------------------------


@pytest.fixture
def bearer_workflow_path() -> Path:
    """Path to the Bearer workflow file."""
    return Path(__file__).parents[2] / ".github" / "workflows" / "bearer.yml"


@pytest.fixture
def bearer_workflow_content(bearer_workflow_path: Path) -> dict:
    """Parsed Bearer workflow YAML."""
    with bearer_workflow_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def bearer_workflow_raw(bearer_workflow_path: Path) -> str:
    """Raw Bearer workflow YAML."""
    return bearer_workflow_path.read_text(encoding="utf-8")


@pytest.fixture
def bearer_steps(bearer_workflow_content: dict) -> list[dict]:
    """Steps for the bearer job."""
    return bearer_workflow_content["jobs"]["bearer"]["steps"]


@pytest.fixture
def bearer_step(bearer_steps: list[dict]) -> dict:
    """Bearer scan step."""
    return next(
        step for step in bearer_steps if "bearer/bearer-action" in step.get("uses", "")
    )


@pytest.fixture
def upload_sarif_step(bearer_steps: list[dict]) -> dict:
    """SARIF upload step."""
    return next(
        step
        for step in bearer_steps
        if "codeql-action/upload-sarif" in step.get("uses", "")
    )


# -------------------------
# Structure tests
# -------------------------


class TestBearerWorkflowStructure:
    def test_workflow_file_exists(self, bearer_workflow_path: Path) -> None:
        assert bearer_workflow_path.exists()
        assert bearer_workflow_path.is_file()

    def test_yaml_is_valid(self, bearer_workflow_content: dict) -> None:
        assert isinstance(bearer_workflow_content, dict)

    def test_workflow_has_name(self, bearer_workflow_content: dict) -> None:
        assert bearer_workflow_content.get("name") == "Bearer"

    def test_workflow_has_triggers(self, bearer_workflow_content: dict) -> None:
        assert isinstance(bearer_workflow_content.get("on"), dict)

    def test_workflow_has_jobs(self, bearer_workflow_content: dict) -> None:
        jobs = bearer_workflow_content.get("jobs")
        assert isinstance(jobs, dict)
        assert jobs


# -------------------------
# Trigger tests
# -------------------------


class TestBearerWorkflowTriggers:
    @pytest.mark.parametrize("trigger", ["push", "pull_request", "schedule"])
    def test_trigger_present(self, bearer_workflow_content: dict, trigger: str) -> None:
        assert trigger in bearer_workflow_content["on"]

    @pytest.mark.parametrize("trigger", ["push", "pull_request"])
    def test_trigger_targets_main(
        self, bearer_workflow_content: dict, trigger: str
    ) -> None:
        assert "main" in bearer_workflow_content["on"][trigger]["branches"]

    def test_schedule_cron(self, bearer_workflow_content: dict) -> None:
        cron = bearer_workflow_content["on"]["schedule"][0]["cron"]
        assert cron.split() == ["16", "8", "*", "*", "1"]


# -------------------------
# Job configuration
# -------------------------


class TestBearerJobConfiguration:
    def test_job_exists(self, bearer_workflow_content: dict) -> None:
        assert "bearer" in bearer_workflow_content["jobs"]

    def test_runs_on_ubuntu(self, bearer_workflow_content: dict) -> None:
        assert bearer_workflow_content["jobs"]["bearer"]["runs-on"] == "ubuntu-latest"

    def test_permissions_defined(self, bearer_workflow_content: dict) -> None:
        permissions = bearer_workflow_content["jobs"]["bearer"]["permissions"]
        assert permissions == {"contents": "read", "security-events": "write"}

    def test_steps_present(self, bearer_steps: list[dict]) -> None:
        assert len(bearer_steps) >= 3


# -------------------------
# Step tests
# -------------------------


class TestBearerSteps:
    def test_checkout_first(self, bearer_steps: list[dict]) -> None:
        assert "actions/checkout@v4" in bearer_steps[0].get("uses", "")

    def test_bearer_action_pinned(self, bearer_step: dict) -> None:
        sha = bearer_step["uses"].split("@")[1]
        assert len(sha) == 40

    def test_bearer_action_configuration(self, bearer_step: dict) -> None:
        with_config = bearer_step["with"]
        assert with_config["format"] == "sarif"
        assert with_config["output"] == "results.sarif"
        assert with_config["exit-code"] == 0
        assert "secrets.BEARER_TOKEN" in with_config["api-key"]

    def test_upload_sarif_configuration(
        self, bearer_step: dict, upload_sarif_step: dict
    ) -> None:
        assert upload_sarif_step["with"]["sarif_file"] == bearer_step["with"]["output"]


# -------------------------
# Documentation & security
# -------------------------


class TestBearerWorkflowSecurity:
    def test_no_hardcoded_secrets(self, bearer_workflow_raw: str) -> None:
        patterns = ("password:", "api_key:", "token:", "secret:")
        for line in bearer_workflow_raw.lower().splitlines():
            if line.strip().startswith("#") or "secrets." in line:
                continue
            assert not any(p in line for p in patterns)

    def test_actions_pinned(self, bearer_steps: list[dict]) -> None:
        for step in bearer_steps:
            if "uses" in step:
                version = step["uses"].split("@")[1]
                assert version not in {"main", "master"}


class TestBearerWorkflowDocumentation:
    def test_header_comment_present(self, bearer_workflow_raw: str) -> None:
        assert bearer_workflow_raw.lstrip().startswith("#")

    def test_bearer_docs_link_present(self, bearer_workflow_raw: str) -> None:
        urls = re.findall(r"https?://[^\s)\"'>]+", bearer_workflow_raw)
        assert any(
            (urlparse(url).hostname or "").endswith("bearer.com") for url in urls
        )
