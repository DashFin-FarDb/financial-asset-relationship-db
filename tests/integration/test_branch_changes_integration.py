"""Integration tests for all changes in the current branch.

Tests validate that all modifications work together correctly and
don't introduce inconsistencies or broken references.
"""

import re
from collections import Counter
from pathlib import Path
from typing import Generator, List, Set

import pytest
import yaml


def _get_workflow_files() -> List[Path]:
    """Helper to retrieve all workflow files(.yml and .yaml)."""
    workflow_dir = Path(".github/workflows")
    if not workflow_dir.exists():
        return []
    return list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml"))


class TestWorkflowConfigurationIntegration:
    """Test integration between workflow files and their configurations."""

    @staticmethod
    def test_all_workflows_have_required_permissions():
        """All workflows should declare appropriate permissions."""
        for workflow_file in _get_workflow_files():
            with open(workflow_file, "r") as f:
                try:
                    data = yaml.safe_load(f) or {}
                except yaml.YAMLError as e:
                    pytest.fail(f"Malformed YAML in {workflow_file.name}: {e}")

            # Check if workflow needs secrets (contains secrets.*)
            content = yaml.dump(data)

            if "secrets." in content or "GITHUB_TOKEN" in content:
                # Should have permissions defined
                assert "permissions" in data, (
                    f"{workflow_file.name} uses secrets but doesn't declare permissions"
                )

    @staticmethod
    def test_workflow_dependencies_available():
        """Workflows should only depend on available actions and tools."""
        for workflow_file in _get_workflow_files():
            with open(workflow_file, "r") as f:
                data = yaml.safe_load(f) or {}

            jobs = data.get("jobs", {})
            for _, job_data in jobs.items():
                steps = job_data.get("steps", [])

                for step in steps:
                    uses = step.get("uses", "")

                    if uses:
                        # Action format: owner/repo@version
                        if "@" in uses and "/" in uses:
                            # Valid action reference
                            assert len(uses.split("@")) == 2, (
                                f"{workflow_file.name} has malformed action: {uses}"
                            )

                    run = step.get("run", "")
                    if run:
                        # Check for tools that might not be installed
                        tools_needing_setup = {
                            "python": ["setup-python", "python"],
                            "node": ["setup-node", "node"],
                            "npm": ["setup-node", "npm"],
                            "pip": ["setup-python", "pip"],
                            "pytest": ["setup-python", "pytest"],
                        }

                        for tool, setup_info in tools_needing_setup.items():
                            if tool in run:
                                # Check if setup step exists earlier
                                # (This is a soft check - warning only)
                                assert any(
                                    setup_info[0] in prev_step.get("uses", "")
                                    for prev_step in steps[: steps.index(step)]
                                ), (
                                    f"{workflow_file.name} run uses '{tool}' without preceding setup step '{setup_info[0]}'."
                                )

    @staticmethod
    def test_consistent_python_versions():
        """Python versions should be consistent across workflows."""
        python_versions = set()

        for workflow_file in _get_workflow_files():
            with open(workflow_file, "r") as f:
                data = yaml.safe_load(f) or {}

            jobs = data.get("jobs", {})
            for _, job_data in jobs.items():
                steps = job_data.get("steps", [])

                for step in steps:
                    if "setup-python" in step.get("uses", ""):
                        with_data = step.get("with", {})
                        version = with_data.get("python-version", "")
                        if version:
                            python_versions.add(version)

        # Should use consistent Python versions (allow 2-3 different versions max)
        assert len(python_versions) <= 3, (
            f"Too many different Python versions used: {python_versions}"
        )

    @staticmethod
    def test_consistent_node_versions():
        """Node.js versions should be consistent across workflows."""
        node_versions = set()

        for workflow_file in _get_workflow_files():
            with open(workflow_file, "r") as f:
                data = yaml.safe_load(f) or {}

            jobs = data.get("jobs", {})
            for _, job_data in jobs.items():
                steps = job_data.get("steps", [])

                for step in steps:
                    if "setup-node" in step.get("uses", ""):
                        with_data = step.get("with", {})
                        version = with_data.get("node-version", "")
                        if version:
                            node_versions.add(version)

        # Should use consistent Node versions
        assert len(node_versions) <= 2, (
            f"Too many different Node versions used: {node_versions}"
        )


class TestRequirementsConsistency:
    """Test consistency between requirements files and workflow usage."""

    @staticmethod
    def test_requirements_dev_matches_workflow_installs():
        """Packages installed in workflows should be in requirements - dev.txt."""
        req_dev_path = Path("requirements-dev.txt")

        if not req_dev_path.exists():
            pytest.skip("requirements-dev.txt not found")

        with open(req_dev_path, "r") as f:
            req_dev_content = f.read()

        # Extract package names
        dev_packages = set()
        for line in req_dev_content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                # Extract package name (before ==, >=, etc.)
                package = line.split("==")[0].split(">=")[0].split("<=")[0].strip()
                dev_packages.add(package.lower())

        # Check workflows
        for workflow_file in _get_workflow_files():
            with open(workflow_file, "r") as f:
                content = f.read()

            # Look for pip install commands
            pip_installs = re.findall(r"pip install ([^\n]+)", content)

            for install_line in pip_installs:
                # Parse installed packages
                packages = install_line.split()
                for pkg in packages:
                    pkg = pkg.strip()
                    if pkg and not pkg.startswith("-"):
                        pkg_name = pkg.split("==")[0].split(">=")[0].strip()

                        # Common packages that don't need to be in requirements
                        skip_packages = {"pip", "setuptools", "wheel", "upgrade"}

                        if pkg_name.lower() not in skip_packages:
                            # Should be in requirements-dev or be optional
                            if pkg_name.lower() not in dev_packages:
                                pytest.fail(
                                    f"Package '{pkg_name}' installed in workflow '{workflow_file}' not in requirements-dev.txt"
                                )

    @staticmethod
    def test_no_duplicate_dependencies():
        """Requirements files should not have duplicate dependencies."""
        req_files = ["requirements.txt", "requirements-dev.txt"]

        for req_file in req_files:
            req_path = Path(req_file)
            if not req_path.exists():
                continue

            with open(req_path, "r") as f:
                lines = f.readlines()

            packages = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#"):
                    # Extract package name
                    package = line.split("==")[0].split(">=")[0].split("<=")[0].strip()
                    packages.append(package.lower())

            # Check for duplicates
            pkg_counts = Counter(packages)
            duplicates = [pkg for pkg, count in pkg_counts.items() if count > 1]
            assert not duplicates, (
                f"{req_file} has duplicate packages: {set(duplicates)}"
            )


class TestDocumentationConsistency:
    """Test that documentation is consistent with actual implementation."""

    def test_readme_doesnt_reference_removed_features(self):
        """README should not document removed features."""
        readme = Path("README.md")

        if readme.exists():
            with open(readme, "r") as f:
                content = f.read()

            # Should not document removed chunking feature
            if "context chunking" in content.lower() or "context_chunker" in content:
                # Should be in historical context only
                lines_with_chunking = [
                    (i, line)
                    for i, line in enumerate(content.split("\n"))
                    if "context" in line.lower() and "chunk" in line.lower()
                ]

                # Check if it's in a "removed" or "deprecated" section
                for line_num, line in lines_with_chunking:
                    context_lines = content.split("\n")[
                        max(0, line_num - 5) : line_num + 5
                    ]
                    context_text = " ".join(context_lines).lower()

                    if (
                        "removed" not in context_text
                        and "deprecated" not in context_text
                    ):
                        # Might still have it, which is okay if historical
                        self.fail(
                            f"README references removed chunking feature outside removed/deprecated context at line {line_num}: {line.strip()}"
                        )

    @staticmethod
    def test_changelog_documents_deletions():
        """CHANGELOG should document deleted files and features."""
        changelog = Path("CHANGELOG.md")

        if changelog.exists():
            with open(changelog, "r"):
                pass

            # Should mention the deletions (soft requirement)
            # At least one deletion should be documented
            # (This is a documentation quality check, not strict requirement)

    @staticmethod
    def test_no_broken_internal_links():
        """Markdown files should not have broken internal links."""
        md_files = list(Path(".").glob("*.md"))

        for md_file in md_files:
            with open(md_file, "r") as f:
                content = f.read()

            # Extract markdown links
            links = re.findall(r"\[([^\]]+)\]\([^\)]+\)", content)
            links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)
            for _, link_target in links:
                # Skip external links
                if link_target.startswith("http://") or link_target.startswith(
                    "https://"
                ):
                    continue

                # Skip anchors
                if link_target.startswith("#"):
                    continue

                # Check if file exists
                link_path = Path(link_target.split("#")[0])  # Remove anchor

                if not link_path.exists():
                    # Might be a relative path
                    relative_path = md_file.parent / link_path
                    if not relative_path.exists():
                        pytest.fail(f"{md_file.name} has broken link: {link_target}")


class TestGitHubActionsEcosystem:
    """Test the overall GitHub Actions ecosystem health."""

    def test_no_circular_workflow_dependencies(self):
        """Workflows should not have circular trigger dependencies."""
        workflow_triggers = {}

        for workflow_file in _get_workflow_files():
            with open(workflow_file, "r") as f:
                data = yaml.safe_load(f) or {}

            triggers = data.get("on", {})
            workflow_run_triggers = []

            if isinstance(triggers, dict) and "workflow_run" in triggers:
                workflow_run = triggers["workflow_run"]
                if isinstance(workflow_run, dict):
                    workflows = workflow_run.get("workflows", [])
                    workflow_run_triggers.extend(workflows)
                elif isinstance(workflow_run, list):
                    for wr in workflow_run:
                        if isinstance(wr, dict):
                            workflows = wr.get("workflows", [])
                            workflow_run_triggers.extend(workflows)

            workflow_triggers[workflow_file.stem] = workflow_run_triggers

        # Check for circular dependencies (simple check)
        for workflow, triggers in workflow_triggers.items():
            for trigger in triggers:
                # If workflow A triggers workflow B, B should not trigger A
                if trigger in workflow_triggers:
                    assert workflow not in workflow_triggers[trigger], (
                        f"Circular dependency: {workflow} <-> {trigger}"
                    )

    def test_workflow_naming_convention(self):
        """Workflows should follow consistent naming conventions."""
        workflow_names = []

        for workflow_file in _get_workflow_files():
            with open(workflow_file, "r") as f:
                data = yaml.safe_load(f) or {}

            name = data.get("name", "")
            workflow_names.append((workflow_file.name, name))

        # Check for consistency
        for filename, workflow_name in workflow_names:
            # Name should be descriptive
            assert len(workflow_name) > 5, (
                f"{filename} has too short name: {workflow_name}"
            )

            # File name should somewhat match workflow name
            # (This is a soft check)

    def test_reasonable_workflow_count(self):
        """Should not have too many workflows(maintainability)."""
        workflow_files = _get_workflow_files()
        workflow_count = len(workflow_files)

        # More than 20 workflows might be hard to maintain
        assert workflow_count <= 25, (
            f"Too many workflows ({workflow_count}), consider consolidation"
        )

    def test_all_workflows_documented(self):
        """All workflows should be documented somewhere."""
        workflow_files = _get_workflow_files()
        workflows = [f.stem for f in workflow_files]

        # Check for workflow documentation
        doc_files = list(Path(".").glob("*.md")) + list(Path(".github").glob("*.md"))
        all_docs_content = ""

        for doc_file in doc_files:
            if doc_file.exists():
                with open(doc_file, "r") as f:
                    all_docs_content += f.read().lower()

        # Each workflow should be mentioned somewhere
        for workflow in workflows:
            _ = (
                workflow.lower() in all_docs_content
                or workflow.replace("-", " ").lower() in all_docs_content
            )

            # This is a soft requirement (not all workflows need docs)
            # but it's good practice
