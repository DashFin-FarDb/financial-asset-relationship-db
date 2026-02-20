from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable

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
    return path.read_text(encoding="utf-8")


def load_yaml(path: Path) -> Dict:
    return yaml.safe_load(read_text(path))


def iter_workflow_steps(workflow: Dict) -> Iterable[Dict]:
    for job in workflow.get("jobs", {}).values():
        for step in job.get("steps", []):
            yield step


def scan_files(
    suffixes: set[str],
    exclude_dirs: set[str] | None = None,
) -> Iterable[Path]:
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
# Deleted files
# -----------------------------------------------------------------------------

class TestDeletedFilesRemoved:
    def test_labeler_yml_deleted(self) -> None:
        assert not (GITHUB_DIR / "labeler.yml").exists()

    def test_context_chunker_deleted(self) -> None:
        assert not (SCRIPTS_DIR / "context_chunker.py").exists()

    def test_codecov_workflow_deleted(self) -> None:
        assert not (WORKFLOWS_DIR / "codecov.yaml").exists()

    def test_scripts_readme_deleted(self) -> None:
        assert not (SCRIPTS_DIR / "README.md").exists()


# -----------------------------------------------------------------------------
# label.yml workflow
# -----------------------------------------------------------------------------

@pytest.fixture(scope="session")
def label_workflow() -> Dict:
    path = WORKFLOWS_DIR / "label.yml"
    if not path.exists():
        pytest.skip("label.yml not found")
    return load_yaml(path)


class TestLabelWorkflowUpdated:
    def test_no_checkout_step(self, label_workflow: Dict) -> None:
        assert not any(
            "checkout" in step.get("uses", "").lower()
            for step in iter_workflow_steps(label_workflow)
        )

    def test_no_config_check_step(self, label_workflow: Dict) -> None:
        assert not any(
            "check" in step.get("name", "").lower()
            and "config" in step.get("name", "").lower()
            for step in iter_workflow_steps(label_workflow)
        )

    def test_labeler_not_conditional(self, label_workflow: Dict) -> None:
        for step in iter_workflow_steps(label_workflow):
            if "labeler" in step.get("uses", "").lower():
                assert "if" not in step

    def test_minimal_steps(self, label_workflow: Dict) -> None:
        jobs = label_workflow.get("jobs", {})
        for job in jobs.values():
            assert len(job.get("steps", [])) <= 2


# -----------------------------------------------------------------------------
# pr-agent workflow
# -----------------------------------------------------------------------------

@pytest.fixture(scope="session")
def pr_agent_path() -> Path:
    path = WORKFLOWS_DIR / "pr-agent.yml"
    if not path.exists():
        pytest.skip("pr-agent.yml not found")
    return path


@pytest.fixture(scope="session")
def pr_agent_workflow(pr_agent_path: Path) -> Dict:
    return load_yaml(pr_agent_path)


@pytest.fixture(scope="session")
def pr_agent_text(pr_agent_path: Path) -> str:
    return read_text(pr_agent_path)


class TestPRAgentWorkflowCleaned:
    def test_no_context_chunker_reference(self, pr_agent_text: str) -> None:
        assert "context_chunker" not in pr_agent_text.lower()

    def test_no_tiktoken_reference(self, pr_agent_text: str) -> None:
        assert "tiktoken" not in pr_agent_text.lower()

    def test_no_chunking_steps(self, pr_agent_workflow: Dict) -> None:
        assert not any(
            "chunk" in step.get("name", "").lower()
            for step in iter_workflow_steps(pr_agent_workflow)
        )

    def test_no_context_files_or_size_logic(self, pr_agent_workflow: Dict) -> None:
        for step in iter_workflow_steps(pr_agent_workflow):
            run = step.get("run", "")
            assert "pr_context.json" not in run.lower()
            assert "context_size" not in run.lower()

    def test_no_inline_pyyaml_install(self, pr_agent_text: str) -> None:
        for line in pr_agent_text.splitlines():
            assert not (
                "pip install" in line.lower()
                and "pyyaml" in line.lower()
            )


# -----------------------------------------------------------------------------
# Orphaned references
# -----------------------------------------------------------------------------

class TestNoOrphanedReferences:
    def test_no_context_chunker_anywhere(self) -> None:
        for path in scan_files(
            {".py", ".yml", ".yaml", ".md", ".sh"},
            exclude_dirs={"venv", ".venv", ".tox", "__pycache__", "build", "dist"},
        ):
            assert "context_chunker" not in read_text(path)

    def test_no_labeler_file_reference(self) -> None:
        for path in scan_files({".yml", ".yaml", ".md"}):
            assert ".github/labeler.yml" not in read_text(path)


# -----------------------------------------------------------------------------
# Codecov cleanup
# -----------------------------------------------------------------------------

class TestCodecovCleanup:
    def test_no_codecov_configs(self) -> None:
        for name in (".codecov.yml", ".codecov.yaml", "codecov.yml"):
            assert not (PROJECT_ROOT / name).exists()

    def test_no_codecov_action_usage(self) -> None:
        for path in scan_files({".yml", ".yaml"}):
            if path.name == "ci.yml":
                continue
            assert "uses: codecov/" not in read_text(path).lower()


# -----------------------------------------------------------------------------
# Greetings workflow
# -----------------------------------------------------------------------------

@pytest.fixture(scope="session")
def greetings_workflow() -> Dict:
    path = WORKFLOWS_DIR / "greetings.yml"
    if not path.exists():
        pytest.skip("greetings.yml not found")
    return load_yaml(path)


@pytest.fixture(scope="session")
def greetings_text() -> str:
    path = WORKFLOWS_DIR / "greetings.yml"
    if not path.exists():
        pytest.skip("greetings.yml not found")
    return read_text(path)


class TestGreetingsWorkflowSimplified:
    def test_single_step(self, greetings_workflow: Dict) -> None:
        steps = next(iter(greetings_workflow["jobs"].values()))["steps"]
        assert len(steps) == 1

    def test_messages_concise(self, greetings_workflow: Dict) -> None:
        with_cfg = next(
            iter(greetings_workflow["jobs"].values())
        )["steps"][0]["with"]

        assert len(with_cfg.get("issue-message", "")) < 100
        assert len(with_cfg.get("pr-message", "")) < 100

    def test_no_resource_links(self, greetings_text: str) -> None:
        for link in ("CONTRIBUTING.md", "QUICK_START.md", "TESTING_GUIDE.md"):
            assert link not in greetings_text


# -----------------------------------------------------------------------------
# Dependencies
# -----------------------------------------------------------------------------

class TestDependencyCleanup:
    def test_requirements_dev(self) -> None:
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
        assert GITHUB_DIR.is_dir()
        assert WORKFLOWS_DIR.is_dir()

    def test_sufficient_workflows(self) -> None:
        workflows = list(WORKFLOWS_DIR.glob("*.yml")) + list(
            WORKFLOWS_DIR.glob("*.yaml")
        )
        assert len(workflows) >= 3

    def test_pr_agent_config_exists(self) -> None:
        assert (GITHUB_DIR / "pr-agent-config.yml").exists()
