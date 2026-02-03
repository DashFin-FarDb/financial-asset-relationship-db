"""
Tests to verify that context_chunker.py and related functionality
were properly removed from the codebase.

This ensures that the removal was complete and no dangling references remain.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")


REPO_ROOT = Path(__file__).parent.parent.parent
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
SCRIPTS_DIR = REPO_ROOT / ".github" / "scripts"


class TestContextChunkerRemoval:
    """Verify context_chunker.py was completely removed."""

    @staticmethod
    def test_context_chunker_file_does_not_exist() -> None:
        """context_chunker.py should no longer exist."""
        context_chunker = SCRIPTS_DIR / "context_chunker.py"
        assert not context_chunker.exists(), (
            "context_chunker.py should have been removed"
        )

    @staticmethod
    def test_scripts_readme_does_not_exist() -> None:
        """Scripts README documenting chunker should be removed."""
        scripts_readme = SCRIPTS_DIR / "README.md"
        assert not scripts_readme.exists(), "Scripts README should have been removed"

    @staticmethod
    def test_no_imports_of_context_chunker() -> None:
        """No Python files should import context_chunker."""
        python_files = list(REPO_ROOT.rglob("*.py"))

        import_pattern = re.compile(
            r"^\s*(?:from\s+context_chunker\b|import\s+context_chunker\b)",
            re.MULTILINE,
        )

        for py_file in python_files:
            # Skip cache and this test file
            if "__pycache__" in str(py_file) or py_file.name == Path(__file__).name:
                continue

            try:
                content = py_file.read_text(encoding="utf-8")
                assert not import_pattern.search(content), (
                    f"{py_file} imports context_chunker"
                )
            except OSError:
                continue
            except Exception as exc:  # pragma: no cover - defensive
                pytest.fail(f"Unexpected error reading {py_file}: {exc}")

    @staticmethod
    def test_no_references_in_workflows() -> None:
        """Workflow files should not reference context_chunker.py."""
        if not WORKFLOWS_DIR.exists():
            pytest.skip("Workflows directory not found")

        workflow_files = list(WORKFLOWS_DIR.glob("*.yml")) + list(
            WORKFLOWS_DIR.glob("*.yaml")
        )

        for workflow_file in workflow_files:
            content = workflow_file.read_text(encoding="utf-8")

            assert "context_chunker.py" not in content, (
                f"{workflow_file.name} references context_chunker.py"
            )
            assert (
                "context_chunker" not in content.lower()
                and "context chunker" not in content.lower()
            ), f"{workflow_file.name} may reference context chunking functionality"


class TestConfigurationCleanup:
    """Verify configuration was updated to remove chunking references."""

    @staticmethod
    def test_pr_agent_config_no_chunking_section() -> None:
        """PR agent config should not reference the removed context_chunker script."""
        config_file = REPO_ROOT / ".github" / "pr-agent-config.yml"

        if not config_file.exists():
            pytest.skip("PR agent config not found")

        content = config_file.read_text(encoding="utf-8").lower()

        assert "context_chunker" not in content, (
            "PR agent config still references context_chunker script"
        )

    @staticmethod
    def test_pr_agent_config_version_updated() -> None:
        """PR agent config version should match the expected agent version."""
        config_file = REPO_ROOT / ".github" / "pr-agent-config.yml"

        if not config_file.exists():
            pytest.skip("PR agent config not found")

        config = yaml.safe_load(config_file.read_text(encoding="utf-8"))

        assert isinstance(config, dict)
        assert "agent" in config and "version" in config["agent"], (
            "PR agent config must define agent.version"
        )

        version = config["agent"]["version"]
        assert version == "1.1.0", (
            f"PR agent config version should be 1.1.0, found {version}"
        )


class TestWorkflowSimplification:
    """Verify workflows were simplified to remove chunking logic."""

    @staticmethod
    def test_pr_agent_workflow_simplified() -> None:
        """PR agent workflow should be simplified."""
        pr_agent_workflow = WORKFLOWS_DIR / "pr-agent.yml"

        if not pr_agent_workflow.exists():
            pytest.skip("PR agent workflow not found")

        content = pr_agent_workflow.read_text(encoding="utf-8")

        assert "Fetch PR Context with Chunking" not in content
        assert "context_chunker" not in content

    @staticmethod
    def test_pr_agent_workflow_no_duplicate_setup() -> None:
        """PR agent workflow should not have duplicate setup steps."""
        pr_agent_workflow = WORKFLOWS_DIR / "pr-agent.yml"

        if not pr_agent_workflow.exists():
            pytest.skip("PR agent workflow not found")

        content = pr_agent_workflow.read_text(encoding="utf-8")

        setup_python_count = content.count("name: Setup Python")
        assert setup_python_count == 1, (
            f"PR agent workflow has {setup_python_count} 'Setup Python' steps"
        )

    @staticmethod
    def test_no_pyyaml_installation_for_chunking() -> None:
        """Workflows should not install PyYAML for chunking purposes."""
        if not WORKFLOWS_DIR.exists():
            pytest.skip("Workflows directory not found")

        workflow_files = list(WORKFLOWS_DIR.glob("*.yml")) + list(
            WORKFLOWS_DIR.glob("*.yaml")
        )

        for workflow_file in workflow_files:
            content = workflow_file.read_text(encoding="utf-8").lower()

            if "pyyaml" in content:
                assert "context chunker" not in content, (
                    f"{workflow_file.name} installs PyYAML for chunking"
                )


class TestDependenciesCleanup:
    """Verify dependencies were cleaned up."""

    @staticmethod
    def test_requirements_dev_appropriate() -> None:
        """requirements-dev.txt should have appropriate dependencies."""
        req_file = REPO_ROOT / "requirements-dev.txt"

        if not req_file.exists():
            pytest.skip("requirements-dev.txt not found")

        content = req_file.read_text(encoding="utf-8").lower()

        assert "pyyaml" in content
        assert "tiktoken" not in content


class TestDocumentationUpdates:
    """Verify documentation was updated."""

    @staticmethod
    def test_no_chunking_documentation() -> None:
        """Documentation should not describe chunking functionality."""
        doc_files = [
            REPO_ROOT / "README.md",
            REPO_ROOT / ".github" / "copilot-pr-agent.md",
        ]

        for doc_file in doc_files:
            if not doc_file.exists():
                continue

            content = doc_file.read_text(encoding="utf-8").lower()
            assert content.count("chunk") < 5, (
                f"{doc_file.name} still has extensive chunking documentation"
            )


class TestNoRegressionOfFixes:
    """Ensure fixes made in this branch are preserved."""

    def test_no_duplicate_yaml_keys_in_pr_agent(self) -> None:
        """PR agent workflow should not have duplicate YAML keys."""
        pr_agent_workflow = WORKFLOWS_DIR / "pr-agent.yml"

        if not pr_agent_workflow.exists():
            pytest.skip("PR agent workflow not found")

        class DuplicateKeyLoader(yaml.SafeLoader):
            """A YAML loader that raises an error when duplicate keys are encountered in mappings."""

            def construct_mapping(self, node, deep=False):
                """Construct a Python mapping from a YAML mapping node.

                Iterates over each key-value pair in the YAML node, constructs the corresponding
                Python objects, and raises a ConstructorError if a duplicate key is encountered.
                """
                mapping = {}
                for key_node, value_node in node.value:
                    key = self.construct_object(key_node, deep=deep)
                    if key in mapping:
                        raise yaml.constructor.ConstructorError(
                            "while constructing a mapping",
                            node.start_mark,
                            f"found duplicate key: {key}",
                            key_node.start_mark,
                        )
                    mapping[key] = self.construct_object(value_node, deep=deep)
                return mapping

        try:
            yaml.load(
                pr_agent_workflow.read_text(encoding="utf-8"),
                Loader=DuplicateKeyLoader,
            )
        except yaml.constructor.ConstructorError as exc:
            pytest.fail(f"PR agent workflow has duplicate keys: {exc}")

    @staticmethod
    def test_workflow_indentation_fixed() -> None:
        """All workflows should have proper YAML indentation."""
        if not WORKFLOWS_DIR.exists():
            pytest.skip("Workflows directory not found")

        workflow_files = list(WORKFLOWS_DIR.glob("*.yml")) + list(
            WORKFLOWS_DIR.glob("*.yaml")
        )

        for workflow_file in workflow_files:
            lines = workflow_file.read_text(encoding="utf-8").splitlines()

            for i, line in enumerate(lines, start=1):
                if line.strip() and not line.lstrip().startswith("#"):
                    assert "\t" not in line, f"{workflow_file.name}:{i} uses tabs"

                    leading_spaces = len(line) - len(line.lstrip(" "))
                    if leading_spaces > 0:
                        assert leading_spaces % 2 == 0, (
                            f"{workflow_file.name}:{i} has odd indentation"
                        )


class TestCleanCodebase:
    """Verify codebase is clean after removal."""

    @staticmethod
    def test_no_orphaned_comments_about_chunking() -> None:
        """Code should not have orphaned comments about chunking."""
        files_to_check = [
            WORKFLOWS_DIR / "pr-agent.yml",
            REPO_ROOT / ".github" / "pr-agent-config.yml",
        ]

        for file_path in files_to_check:
            if not file_path.exists():
                continue

            content = file_path.read_text(encoding="utf-8")
            comment_lines = [
                line for line in content.splitlines() if line.strip().startswith("#")
            ]

            chunking_comments = [
                line for line in comment_lines if "chunk" in line.lower()
            ]

            assert not chunking_comments, f"{file_path.name} has chunking comments"

    @staticmethod
    def test_labeler_yml_removed() -> None:
        """labeler.yml should be removed."""
        labeler_file = REPO_ROOT / ".github" / "labeler.yml"
        assert not labeler_file.exists()

    @staticmethod
    def test_workflow_checks_simplified() -> None:
        """Workflow checks should be simplified."""
        apisec_workflow = WORKFLOWS_DIR / "apisec-scan.yml"
        if apisec_workflow.exists():
            content = apisec_workflow.read_text(encoding="utf-8")
            assert "Check for APIsec credentials" not in content

        label_workflow = WORKFLOWS_DIR / "label.yml"
        if label_workflow.exists():
            content = label_workflow.read_text(encoding="utf-8")
            assert "Check for labeler config" not in content
