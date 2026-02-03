"""
Tests to ensure that deleted files don't break existing functionality.

This test suite validates that removal of:
- .github / scripts / context_chunker.py
- .github / scripts / README.md
- .github / labeler.yml

Does not cause any regressions or broken references.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Union

import pytest
import yaml


def _get_workflow_files() -> List[Path]:
    """Retrieve all workflow files(.yml and .yaml)."""
    workflow_dir = Path(".github/workflows")
    if not workflow_dir.exists():
        return []
    return [*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")]


class TestDeletedContextChunker:
    """Validate that context_chunker.py removal doesn't break workflows."""

    @staticmethod
    def test_no_references_to_context_chunker_in_workflows() -> None:
        """Workflows should not reference the deleted context_chunker.py."""
        for workflow_file in _get_workflow_files():
            with open(workflow_file, "r", encoding="utf-8") as handle:
                content = handle.read()

            assert "context_chunker" not in content, (
                f"{workflow_file.name} still references deleted context_chunker.py"
            )
            assert ".github/scripts/context_chunker" not in content, (
                f"{workflow_file.name} references deleted chunker script"
            )

    @staticmethod
    def test_workflows_dont_depend_on_chunking_functionality() -> None:
        """Workflows should operate without chunking functionality."""
        pr_agent_workflow = Path(".github/workflows/pr-agent.yml")

        if not pr_agent_workflow.exists():
            return

        with open(pr_agent_workflow, "r", encoding="utf-8") as handle:
            content = handle.read()

        problematic_terms = [
            "chunk_size",
            "token_count",
            "tiktoken",
            "context_overflow",
            "summarization",
        ]

        for term in problematic_terms:
            if term not in content:
                continue

            lines_with_term = [
                line
                for line in content.splitlines()
                if term in line and not line.strip().startswith("#")
            ]

            assert not lines_with_term, (
                f"PR agent workflow still has chunking logic: {term}"
            )

    @staticmethod
    def test_no_python_dependencies_for_chunking() -> None:
        """Dev requirements should not include chunking - only dependencies."""
        req_dev = Path("requirements-dev.txt")

        if not req_dev.exists():
            return

        with open(req_dev, "r", encoding="utf-8") as handle:
            content = handle.read()

        forbidden_packages = ("tiktoken",)
        for package in forbidden_packages:
            assert package not in content, (
                f"requirements-dev.txt should not include {package}"
            )

    @staticmethod
    def test_scripts_directory_exists_or_empty() -> None:
        """Scripts directory should not contain deleted chunker artifacts."""
        scripts_dir = Path(".github/scripts")

        if not scripts_dir.exists():
            return

        assert not (scripts_dir / "context_chunker.py").exists(), (
            "context_chunker.py should be deleted"
        )

        readme = scripts_dir / "README.md"
        if readme.exists():
            with open(readme, "r", encoding="utf-8") as handle:
                content = handle.read()

            assert "chunking" not in content.lower(), (
                "Scripts README still documents chunking"
            )


class TestDeletedLabelerConfig:
    """Validate that labeler.yml removal doesn't break label workflow."""

    @staticmethod
    def test_label_workflow_doesnt_require_config() -> None:
        """Label workflow should handle missing labeler config gracefully."""
        label_workflow = Path(".github/workflows/label.yml")

        if not label_workflow.exists():
            return

        with open(label_workflow, "r", encoding="utf-8") as handle:
            content = handle.read()

        if "labeler.yml" in content:
            assert "exists" in content or "check" in content, (
                "Label workflow references labeler.yml without checking existence"
            )

    @staticmethod
    def test_labeler_yml_deleted() -> None:
        """Labeler configuration file should be deleted."""
        assert not Path(".github/labeler.yml").exists(), "labeler.yml should be deleted"

    @staticmethod
    def test_label_workflow_still_functional() -> None:
        """Label workflow should exist and be valid YAML."""
        label_workflow = Path(".github/workflows/label.yml")
        assert label_workflow.exists(), "Label workflow should exist"

        with open(label_workflow, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)

        assert isinstance(data, dict)
        assert "jobs" in data

    @staticmethod
    def test_no_broken_labeler_action_calls() -> None:
        """Labeler action should not be invoked without config or conditions."""
        label_workflow = Path(".github/workflows/label.yml")

        if not label_workflow.exists():
            return

        with open(label_workflow, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}

        jobs = data.get("jobs", {})
        for job_data in jobs.values():
            steps = job_data.get("steps", [])
            for step in steps:
                if not isinstance(step, dict):
                    continue

                uses = str(step.get("uses", ""))
                if "labeler" not in uses:
                    continue

                step_if = step.get("if")
                with_config = step.get("with")

                assert step_if or with_config, (
                    "Labeler action used without condition or inline configuration"
                )


class TestDeletedScriptsReadme:
    """Validate that scripts README removal doesn't break documentation."""

    @staticmethod
    def test_main_docs_dont_reference_scripts_readme() -> None:
        """Main documentation should not reference deleted scripts README."""
        doc_files = [
            "README.md",
            "CONTRIBUTING.md",
            "ARCHITECTURE.md",
            ".github/copilot-pr-agent.md",
        ]

        for doc_file in doc_files:
            doc_path = Path(doc_file)
            if not doc_path.exists():
                continue

            with open(doc_path, "r", encoding="utf-8") as handle:
                content = handle.read()

            assert ".github/scripts/README.md" not in content, (
                f"{doc_file} references deleted scripts README"
            )

    @staticmethod
    def test_no_orphaned_script_documentation() -> None:
        """Documentation should not provide instructions for deleted scripts."""
        for doc_file in Path(".").glob("*.md"):
            with open(doc_file, "r", encoding="utf-8") as handle:
                content = handle.read()

            if "context_chunker" not in content.lower():
                continue

            if doc_file.name in {"CHANGELOG.md", "CHANGELOG_BRANCH_CLEANUP.md"}:
                continue

            for line in content.splitlines():
                if "context_chunker" not in line.lower():
                    continue

                assert "pip install" not in line
                assert "python .github/scripts/context_chunker" not in line


class TestWorkflowConfigConsistency:
    """Test consistency between workflows and configs after deletions."""

    def _contains_chunking_settings(self, obj: Union[Dict, List, str]) -> bool:
        """Recursively detect chunking - related keys or values."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if "chunk" in str(key).lower():
                    return True
                if self._contains_chunking_settings(value):
                    return True
        elif isinstance(obj, list):
            for item in obj:
                if self._contains_chunking_settings(item):
                    return True
        elif isinstance(obj, str):
            return "chunk" in obj.lower()
        return False

    def test_pr_agent_config_matches_workflow(self) -> None:
        """PR Agent config should align with simplified workflow."""
        workflow_path = Path(".github/workflows/pr-agent.yml")
        config_path = Path(".github/pr-agent.yml")

        if not workflow_path.exists() or not config_path.exists():
            pytest.skip("PR Agent workflow or config not found")

        with open(config_path, "r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle)

        with open(workflow_path, "r", encoding="utf-8") as handle:
            workflow = yaml.safe_load(handle)

        assert isinstance(config, dict)
        assert isinstance(workflow, dict)
        assert "jobs" in workflow

        if not self._contains_chunking_settings(workflow):
            assert not self._contains_chunking_settings(config), (
                "Config contains chunking settings unused by workflow"
            )

    @staticmethod
    def test_no_missing_config_files_referenced() -> None:
        """Workflows should not reference missing config files."""
        for workflow_file in _get_workflow_files():
            with open(workflow_file, "r", encoding="utf-8") as handle:
                content = handle.read()

            file_patterns = re.findall(r"\.github/[^\s\'\"]+", content)
            for raw_path in file_patterns:
                cleaned = raw_path.rstrip(",")
                path = Path(cleaned)

                if "://" in cleaned:
                    continue

                if path.exists():
                    continue

                for line in content.splitlines():
                    if cleaned not in line:
                        continue
                    if not line.strip().startswith("#"):
                        assert "if" in line.lower() or "exists" in line.lower(), (
                            f"{workflow_file.name} references missing file: {cleaned}"
                        )


class TestBackwardCompatibility:
    """Ensure removals do not break backward compatibility."""

    @staticmethod
    def test_environment_variables_still_valid() -> None:
        """Env vars should not reference deleted scripts or configs."""
        for workflow_file in _get_workflow_files():
            with open(workflow_file, "r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}

            jobs = data.get("jobs", {})
            for job_data in jobs.values():
                job_env = job_data.get("env", {})
                for key, value in job_env.items():
                    if isinstance(value, str):
                        assert "context_chunker" not in value, (
                            f"{workflow_file.name} env var {key} references deleted script"
                        )

    @staticmethod
    def test_action_inputs_valid() -> None:
        """Action inputs should not reference deleted files."""
        for workflow_file in _get_workflow_files():
            with open(workflow_file, "r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}

            jobs = data.get("jobs", {})
            for job_data in jobs.values():
                steps = job_data.get("steps", [])
                for step in steps:
                    if not isinstance(step, dict):
                        continue

                    with_data = step.get("with", {})
                    for value in with_data.values():
                        if isinstance(value, str):
                            assert ".github/scripts/context_chunker" not in value
                            assert "labeler.yml" not in value
