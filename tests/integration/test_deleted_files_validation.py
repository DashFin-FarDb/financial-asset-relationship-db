from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List

import pytest
import yaml

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]
GITHUB_DIR = PROJECT_ROOT / ".github"
WORKFLOWS_DIR = GITHUB_DIR / "workflows"
SCRIPTS_DIR = GITHUB_DIR / "scripts"


# -----------------------------------------------------------------------------
# Generic helpers
# -----------------------------------------------------------------------------


def read_text(path: Path) -> str:
    """Read text from a file at the given path."""
    return path.read_text(encoding="utf-8")


def load_yaml(path: Path) -> Dict:
    """Load a YAML file and return its contents as a dictionary."""
    return yaml.safe_load(read_text(path))


def iter_workflow_steps(workflow: Dict) -> Iterable[Dict]:
    """Yields each step from the jobs in the given workflow."""
    for job in workflow.get("jobs", {}).values():
        for step in job.get("steps", []):
            yield step


def scan_files(
    suffixes: set[str],
    exclude_dirs: set[str] | None = None,
) -> Iterable[Path]:
    """Scan for files with specific suffixes while excluding certain directories.

    This function recursively searches through the directory tree starting  from
    PROJECT_ROOT, yielding paths of files that match the specified  suffixes. It
    skips any directories listed in exclude_dirs and only  processes files that
    have the desired suffixes. The function utilizes  the rglob method for
    efficient file searching.

    Args:
        suffixes (set[str]): A set of file suffixes to include in the search.
        exclude_dirs (set[str] | None): A set of directory names to exclude
            from the search. If None, no directories are excluded.
    """
    exclude_dirs = exclude_dirs or set()
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in suffixes:
            continue
        if any(part in exclude_dirs for part in path.parts):
            continue
        yield path


# -----------------------------------------------------------------------------
# label.yml workflow
# -----------------------------------------------------------------------------


@pytest.fixture(scope="session")
def label_workflow() -> Dict:
    """Load the label.yml workflow if it exists."""
    path = WORKFLOWS_DIR / "label.yml"
    if not path.exists():
        pytest.skip("label.yml not found")
    return load_yaml(path)


class TestLabelWorkflowUpdated:
    def test_no_checkout_step(self, label_workflow: Dict) -> None:
        """Verify that no steps in the workflow use 'checkout'."""
        assert not any("checkout" in step.get("uses", "").lower() for step in iter_workflow_steps(label_workflow))

    def test_no_config_check_step(self, label_workflow: Dict) -> None:
        """Assert that no workflow step contains 'check' and 'config' in its name."""
        assert not any(
            "check" in step.get("name", "").lower() and "config" in step.get("name", "").lower()
            for step in iter_workflow_steps(label_workflow)
        )

    def test_labeler_not_conditional(self, label_workflow: Dict) -> None:
        """Verify that steps using a labeler do not contain 'if' statements."""
        for step in iter_workflow_steps(label_workflow):
            if "labeler" in step.get("uses", "").lower():
                assert "if" not in step

    def test_minimal_steps(self, label_workflow: Dict) -> None:
        """Assert that each job in the workflow has at most two steps."""
        jobs = label_workflow.get("jobs", {})
        for job in jobs.values():
            assert len(job.get("steps", [])) <= 2


# -----------------------------------------------------------------------------
# pr-agent workflow
# -----------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pr_agent_path() -> Path:
    """Return the path to the pr-agent.yml file if it exists."""
    path = WORKFLOWS_DIR / "pr-agent.yml"
    if not path.exists():
        pytest.skip("pr-agent.yml not found")
    return path


@pytest.fixture(scope="session")
def pr_agent_workflow(pr_agent_path: Path) -> Dict:
    """Load and return the YAML configuration for the PR agent."""
    return load_yaml(pr_agent_path)


@pytest.fixture(scope="session")
def pr_agent_text(pr_agent_path: Path) -> str:
    return read_text(pr_agent_path)


class TestPRAgentWorkflowCleaned:
    def test_no_context_chunker_reference(self, pr_agent_text: str) -> None:
        """Verify that 'context_chunker' is not present in the given text."""
        assert "context_chunker" not in pr_agent_text.lower()

    def test_no_tiktoken_reference(self, pr_agent_text: str) -> None:
        """Assert that 'tiktoken' is not present in the given text."""
        assert "tiktoken" not in pr_agent_text.lower()

    def test_no_chunking_steps(self, pr_agent_workflow: Dict) -> None:
        """Verify that no steps contain 'chunk' in their name."""
        assert not any("chunk" in step.get("name", "").lower() for step in iter_workflow_steps(pr_agent_workflow))

    def test_no_context_files_or_size_logic(self, pr_agent_workflow: Dict) -> None:
        """Verify that no context files or size logic are present in the workflow steps."""
        for step in iter_workflow_steps(pr_agent_workflow):
            run = step.get("run", "")
            assert "pr_context.json" not in run.lower()
            assert "context_size" not in run.lower()

    def test_no_inline_pyyaml_install(self, pr_agent_text: str) -> None:
        for line in pr_agent_text.splitlines():
            assert not ("pip install" in line.lower() and "pyyaml" in line.lower())


# -----------------------------------------------------------------------------
# Orphaned references
# -----------------------------------------------------------------------------


class TestNoOrphanedReferences:
    def test_no_labeler_file_reference(self) -> None:
        """Verify that no labeler file reference exists in specified files."""
        for path in scan_files({".yml", ".yaml", ".md"}):
            assert ".github/labeler.yml" not in read_text(path)


# -----------------------------------------------------------------------------
# Codecov cleanup
# -----------------------------------------------------------------------------


class TestCodecovCleanup:
    def test_no_codecov_configs(self) -> None:
        """Verify that no codecov configuration files exist."""
        for name in (".codecov.yml", ".codecov.yaml", "codecov.yml"):
            assert not (PROJECT_ROOT / name).exists()

    def test_no_codecov_action_usage(self) -> None:
        """Check that no Codecov action is used in CI configuration files."""
        for path in scan_files({".yml", ".yaml"}):
            if path.name == "ci.yml":
                continue
            assert "uses: codecov/" not in read_text(path).lower()


# -----------------------------------------------------------------------------
# Greetings workflow
# -----------------------------------------------------------------------------


@pytest.fixture(scope="session")
def greetings_workflow() -> Dict:
    """Load the greetings workflow from a YAML file."""
    path = WORKFLOWS_DIR / "greetings.yml"
    if not path.exists():
        pytest.skip("greetings.yml not found")
    return load_yaml(path)


class TestGreetingsWorkflowStructure:
    def test_single_step(self, greetings_workflow: Dict) -> None:
        """Verify that the greetings workflow has exactly one step."""
        steps = next(iter(greetings_workflow["jobs"].values()))["steps"]
        assert len(steps) == 1


# -----------------------------------------------------------------------------
# Dependencies
# -----------------------------------------------------------------------------


class TestDependencyCleanup:
    def test_requirements_dev(self) -> None:
        """Check the development requirements in requirements-dev.txt."""
        path = PROJECT_ROOT / "requirements-dev.txt"
        if not path.exists():
            pytest.skip("requirements-dev.txt not found")

        content = read_text(path)
        assert "pyyaml" in content.lower()
        assert "tiktoken" not in content.lower()


# -----------------------------------------------------------------------------
# Project structure
# -----------------------------------------------------------------------------


class TestProjectStructureIntegrity:
    def test_github_dirs_exist(self) -> None:
        """Check if the GitHub directories exist."""
        assert GITHUB_DIR.is_dir()
        assert WORKFLOWS_DIR.is_dir()

    def test_sufficient_workflows(self) -> None:
        """Check that there are at least three workflow files."""
        workflows = list(WORKFLOWS_DIR.glob("*.yml")) + list(WORKFLOWS_DIR.glob("*.yaml"))
        assert len(workflows) >= 3

    def test_pr_agent_config_exists(self) -> None:
        """Check if the pr-agent-config.yml file exists in the GITHUB_DIR."""
        assert (GITHUB_DIR / "pr-agent-config.yml").exists()
