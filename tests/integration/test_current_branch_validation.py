"""
Validation tests for current branch changes.

Tests ensure that all modifications in the current branch are consistent,
properly integrated, and don't introduce regressions.
"""

from pathlib import Path
from typing import Any, Dict, Generator, List

import yaml

# --- Helper Functions ---


def _get_workflow_files() -> List[Path]:
    """Retrieve all workflow files (.yml and .yaml)."""
    workflow_dir = Path(".github/workflows")
    if not workflow_dir.exists():
        return []
    return [*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")]


def _load_yaml_safe(file_path: Path) -> Dict[str, Any]:
    """Safely load YAML content, returning an empty dict if null."""
    with open(file_path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data if isinstance(data, dict) else {}


def _iter_uses_values(node: Any) -> Generator[str, None, None]:
    """Yield all `uses:` values found anywhere in a parsed YAML structure."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "uses" and isinstance(value, str):
                yield value
            yield from _iter_uses_values(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_uses_values(item)


# --- Test Classes ---


class TestWorkflowModifications:
    """Tests covering workflow file modifications."""

    @staticmethod
    def test_pr_agent_workflow_no_chunking_references() -> None:
        """PR agent workflow should not reference deleted chunking functionality."""
        workflow_path = Path(".github/workflows/pr-agent.yml")

        with open(workflow_path, "r", encoding="utf-8") as handle:
            content = handle.read()

        assert "context_chunker" not in content
        assert "tiktoken" not in content

        content_lower = content.lower()
        if "chunking" in content_lower:
            assert content_lower.count("chunking") == content_lower.count(
                "# chunking"
            ), "Found 'chunking' references outside of comments"

    @staticmethod
    def test_pr_agent_workflow_has_simplified_parsing() -> None:
        """PR agent workflow should have simplified comment parsing."""
        workflow_path = Path(".github/workflows/pr-agent.yml")
        data = _load_yaml_safe(workflow_path)

        jobs = data.get("jobs", {})
        trigger_job = jobs.get("pr-agent-trigger", {})
        steps = trigger_job.get("steps", [])

        step_names = [step.get("name", "") for step in steps if isinstance(step, dict)]
        assert any(
            "parse" in name.lower() and "comment" in name.lower() for name in step_names
        )

    @staticmethod
    def test_apisec_workflow_no_credential_checks() -> None:
        """APIsec workflow should not include credential pre-check steps."""
        workflow_path = Path(".github/workflows/apisec-scan.yml")
        data = _load_yaml_safe(workflow_path)

        assert "jobs" in data
        assert "Trigger_APIsec_scan" in data["jobs"]

        job = data["jobs"]["Trigger_APIsec_scan"]
        steps = job.get("steps", [])

        step_names = [
            str(step.get("name", "")).lower()
            for step in steps
            if isinstance(step, dict)
        ]

        assert not any(
            "credential" in name or "secret" in name for name in step_names
        ), "Credential pre-check steps should not be present"

    @staticmethod
    def test_label_workflow_simplified() -> None:
        """Label workflow should be simplified without config checks."""
        workflow_path = Path(".github/workflows/label.yml")
        assert workflow_path.exists()

        data = _load_yaml_safe(workflow_path)
        jobs = data.get("jobs", {})
        assert jobs

        config_keywords = (
            "config",
            "pr-agent-config",
            "validate",
            "validation",
            "check config",
            "config check",
        )

        for job in jobs.values():
            if not isinstance(job, dict):
                continue

            for step in job.get("steps") or []:
                if not isinstance(step, dict):
                    continue

                haystack = " ".join(
                    str(step.get(key, "")).lower()
                    for key in ("name", "uses", "run", "with")
                )
                assert not any(keyword in haystack for keyword in config_keywords)

    @staticmethod
    def test_greetings_workflow_simplified() -> None:
        """Greetings workflow should exist and parse correctly."""
        workflow_path = Path(".github/workflows/greetings.yml")
        data = _load_yaml_safe(workflow_path)

        jobs = data.get("jobs", {})
        assert jobs.get("greeting")

    @staticmethod
    def test_labeler_config_deleted() -> None:
        """Labeler.yml configuration should be deleted."""
        assert not Path(".github/labeler.yml").exists()

    @staticmethod
    def test_scripts_readme_deleted() -> None:
        """Scripts README should be deleted."""
        assert not Path(".github/scripts/README.md").exists()


class TestRequirementsDevUpdates:
    """Tests for requirements-dev.txt updates."""

    @staticmethod
    def test_requirements_dev_has_pyyaml() -> None:
        """requirements-dev.txt should include PyYAML."""
        req_path = Path("requirements-dev.txt")

        with open(req_path, "r", encoding="utf-8") as handle:
            content = handle.read()

        assert "PyYAML" in content
        assert "types-PyYAML" in content

    @staticmethod
    def test_requirements_dev_valid_format() -> None:
        """requirements-dev.txt entries should include version specifiers."""
        req_path = Path("requirements-dev.txt")

        with open(req_path, "r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    assert any(op in stripped for op in (">=", "==", "~="))


class TestPRAgentConfigSimplified:
    """Tests covering PR agent configuration simplification."""


class TestConfigValidation:
    """Tests validating the PR agent configuration file for semantic versioning, required chunking settings, and valid workflow references."""

    @staticmethod
    def test_config_version_uses_semantic_versioning() -> None:
        """PR agent config version should use semantic versioning."""
        config_path = Path(".github/pr-agent-config.yml")
        data = _load_yaml_safe(config_path)

        version = data.get("agent", {}).get("version")
        assert isinstance(version, str)

        parts = version.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)

    @staticmethod
    def test_config_chunking_settings_present() -> None:
        """PR agent config should define chunking settings used by the workflow."""
        config_path = Path(".github/pr-agent-config.yml")
        data = _load_yaml_safe(config_path)

        assert "context" in data.get("agent", {})
        assert "max_files_per_chunk" in data.get("limits", {})

    @staticmethod
    def test_no_broken_workflow_references() -> None:
        """Workflows should not reference missing local files or actions."""
        repo_root = Path(".").resolve()
        workflow_files = _get_workflow_files()

        for workflow_file in workflow_files:
            with open(workflow_file, "r", encoding="utf-8") as handle:
                content = handle.read()
                data = yaml.safe_load(content) or {}

            for uses in _iter_uses_values(data):
                if not uses.startswith("./"):
                    continue

                local_ref = uses.split("@", 1)[0]
                target = (repo_root / local_ref).resolve()

                assert target.exists(), (
                    f"{workflow_file}: local 'uses' reference '{uses}' does not exist"
                )

                if target.is_dir():
                    assert any(
                        (target / name).exists()
                        for name in ("action.yml", "action.yaml", "Dockerfile")
                    )
                else:
                    assert target.suffix in {".yml", ".yaml"}

            assert ".github/scripts/context_chunker.py" not in content
            assert ".github/labeler.yml" not in content


class TestDocumentationConsistency:
    """Tests ensuring documentation matches current functionality."""

    @staticmethod
    def test_summary_files_exist() -> None:
        """Summary documentation files must exist and be non-empty."""
        summary_path = Path("COMPREHENSIVE_BRANCH_TEST_GENERATION_SUMMARY.md")
        assert summary_path.is_file()
        assert summary_path.stat().st_size > 0

    @staticmethod
    def test_no_misleading_documentation() -> None:
        """Documentation should not present removed features as active."""
        readme = Path("README.md")

        if readme.exists():
            with open(readme, "r", encoding="utf-8") as handle:
                content = handle.read().lower()

            # Historical mentions are acceptable
            assert "chunking" not in content, (
                "Removed feature 'chunking' should not be mentioned in README.md"
            )
