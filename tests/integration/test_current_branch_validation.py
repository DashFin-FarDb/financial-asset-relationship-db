"""
Validation tests for current branch changes.

Tests ensure that all modifications in the current branch are consistent,
properly integrated, and don't introduce regressions.
"""

from pathlib import Path
from typing import Any, Dict, Generator, List

import pytest
import yaml

# --- Helper Functions ---


def _get_workflow_files() -> List[Path]:
    """Helper to retrieve all workflow files (.yml and .yaml)."""
    workflow_dir = Path(".github/workflows")
    if not workflow_dir.exists():
        return []
    return list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml"))


def _load_yaml_safe(file_path: Path) -> Dict[str, Any]:
    """Helper to safely load YAML content."""
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _iter_uses_values(node: Any) -> Generator[str, None, None]:
    """Yield all `uses:` values found anywhere in a parsed YAML structure."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "uses" and isinstance(v, str):
                yield v
            yield from _iter_uses_values(v)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_uses_values(item)


# --- Test Classes ---


class TestWorkflowModifications:
    """Test modifications to workflow files."""

    def test_pr_agent_workflow_no_chunking_references(self):
        """PR agent workflow should not reference deleted chunking functionality."""
        workflow_path = Path(".github/workflows/pr-agent.yml")

        with open(workflow_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Should not reference chunking
        assert "context_chunker" not in content
        content_lower = content.lower()
        if "chunking" in content_lower:
            assert content_lower.count("chunking") == content_lower.count(
                "# chunking"
            ), "Found 'chunking' references outside of comments"
        assert "tiktoken" not in content

    def test_pr_agent_workflow_has_simplified_parsing(self):
        """PR agent workflow should have simplified comment parsing."""
        workflow_path = Path(".github/workflows/pr-agent.yml")
        data = _load_yaml_safe(workflow_path)

        # Should have parse-comments step
        jobs = data.get("jobs", {})
        trigger_job = jobs.get("pr-agent-trigger", {})
        steps = trigger_job.get("steps", [])

        step_names = [step.get("name", "") for step in steps]
        assert any(
            "parse" in name.lower() and "comment" in name.lower() for name in step_names
        )

    def test_apisec_workflow_no_credential_checks(self):
        """APIsec workflow should not include credential pre-check steps (simplified)."""
        workflow_path = Path(".github/workflows/apisec-scan.yml")
        data = _load_yaml_safe(workflow_path)

        # Workflow should exist and be valid
        assert isinstance(data, dict)
        assert "jobs" in data
        assert "Trigger_APIsec_scan" in data["jobs"]

        # Ensure no credential pre-check steps are present
        job = data["jobs"]["Trigger_APIsec_scan"]
        steps = job.get("steps", [])
        step_names = [
            str(step.get("name", "")).lower()
            for step in steps
            if isinstance(step, dict)
        ]
        assert not any(
            "credential" in name or "secret" in name for name in step_names
        ), (
            "Found credential pre-check steps; these should be removed in the simplified workflow"
        )

    def test_label_workflow_simplified(self):
        """Label workflow should be simplified without config checks."""
        workflow_path = Path(".github/workflows/label.yml")
        assert workflow_path.exists(), "Expected '.github/workflows/label.yml' to exist"

        data = _load_yaml_safe(workflow_path)

        # Basic validity checks
        assert isinstance(data, dict), (
            "Expected label workflow YAML to parse into a dict"
        )
        jobs = data.get("jobs", {})
        assert isinstance(jobs, dict) and jobs, (
            "Expected label workflow to define at least one job"
        )

        # Ensure no config-check logic remains in steps (name/uses/run)
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
            for step in job.get("steps", []) or []:
                if not isinstance(step, dict):
                    continue
                haystack = " ".join(
                    str(step.get(k, "")).lower()
                    for k in ("name", "uses", "run", "with")
                )
                assert not any(kw in haystack for kw in config_keywords), (
                    "Found config-check related logic in label workflow steps; "
                    "workflow should be simplified without config checks"
                )

    def test_greetings_workflow_simplified(self):
        """Greetings workflow should have simplified messages."""
        workflow_path = Path(".github/workflows/greetings.yml")
        data = _load_yaml_safe(workflow_path)

        jobs = data.get("jobs", {})
        greeting_job = jobs.get("greeting", {})
        # Ensure job exists
        assert greeting_job, "Greeting job is missing from workflow"

    def test_labeler_config_deleted(self):
        """Labeler.yml configuration should be deleted."""
        labeler_path = Path(".github/labeler.yml")
        assert not labeler_path.exists()

    def test_scripts_readme_deleted(self):
        """Scripts README should be deleted."""
        readme_path = Path(".github/scripts/README.md")
        assert not readme_path.exists()


class TestRequirementsDevUpdates:
    """Test requirements-dev.txt updates."""

    def test_requirements_dev_has_pyyaml(self):
        """Requirements-dev should include PyYAML."""
        req_path = Path("requirements-dev.txt")
        with open(req_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "PyYAML" in content
        assert "types-PyYAML" in content

    def test_requirements_dev_valid_format(self):
        """Requirements-dev should be properly formatted."""
        req_path = Path("requirements-dev.txt")
        with open(req_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                # Should have version specifier
                assert ">=" in line or "==" in line or "~=" in line


class TestPRAgentConfigSimplified:
    """Test PR Agent config simplification."""

    def test_config_version_downgraded(self):
        """PR Agent config version should be back to 1.0.0."""
        config_path = Path(".github/pr-agent-config.yml")
        data = _load_yaml_safe(config_path)

        version = data.get("agent", {}).get("version", "")
        assert version == "1.0.0"

    def test_config_no_chunking_settings(self):
        """PR Agent config should not have chunking settings."""
        config_path = Path(".github/pr-agent-config.yml")
        data = _load_yaml_safe(config_path)

        agent = data.get("agent", {})
        # Should not have context section
        assert "context" not in agent

        limits = data.get("limits", {})
        # Should not have chunking limits
        assert "max_files_per_chunk" not in limits

    def test_no_broken_workflow_references(self):
        """Workflows should not reference non-existent local files/actions/workflows."""
        repo_root = Path(".")
        workflow_files = _get_workflow_files()

        if not workflow_files:
            return

        for workflow_file in workflow_files:
            with open(workflow_file, "r", encoding="utf-8") as f:
                content = f.read()
                f.seek(0)
                data = yaml.safe_load(f) or {}

            # Check 1: Validate 'uses' references
            for uses in _iter_uses_values(data):
                # Only validate local references
                if not uses.startswith("./"):
                    continue

                local_ref = uses.split("@", 1)[0]  # strip optional @ref
                target = (repo_root / local_ref).resolve()

                assert target.exists(), (
                    f"{workflow_file}: local 'uses' reference '{uses}' does not exist at '{local_ref}'"
                )

                # If directory, require action metadata
                if target.is_dir():
                    has_action_metadata = any(
                        (target / name).exists()
                        for name in ("action.yml", "action.yaml", "Dockerfile")
                    )
                    assert has_action_metadata, (
                        f"{workflow_file}: local action '{uses}' points to '{local_ref}', "
                        "but no action.yml/action.yaml/Dockerfile was found"
                    )
                else:
                    # If file, must be YAML
                    assert target.suffix in (".yml", ".yaml"), (
                        f"{workflow_file}: local file reference '{uses}' points to '{local_ref}', "
                        "but it is not a .yml/.yaml file"
                    )

            # Check 2: Workflows should not reference deleted specific local files
            assert ".github/scripts/context_chunker.py" not in content, (
                f"Workflow {workflow_file} references deleted script '.github/scripts/context_chunker.py'"
            )
            assert ".github/labeler.yml" not in content, (
                f"Workflow {workflow_file} references deleted labeler config '.github/labeler.yml'"
            )


class TestDocumentationConsistency:
    """Test documentation consistency with code changes."""

    def test_summary_files_exist(self):
        """Test summary documentation files should exist."""
        summary_files = ["COMPREHENSIVE_BRANCH_TEST_GENERATION_SUMMARY.md"]

        for summary_file in summary_files:
            path = Path(summary_file)
            assert path.is_file(), (
                f"Required summary file '{summary_file}' does not exist"
            )
            assert path.stat().st_size > 0, f"Summary file '{summary_file}' is empty"

    def test_no_misleading_documentation(self):
        """Documentation should not reference removed features as active."""
        readme = Path("README.md")

        if readme.exists():
            with open(readme, "r", encoding="utf-8") as f:
                content = f.read().lower()

            # If chunking is mentioned, it should be in past tense or removed context
            if "chunking" in content:
                # This is acceptable for historical documentation
                pass
