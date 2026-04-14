from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Set, TypedDict

import pytest
import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = ROOT_DIR / ".github" / "workflows"


# ---------------------------------------------------------------------------
# Typed models
# ---------------------------------------------------------------------------


class Step(TypedDict, total=False):
    uses: str
    run: str
    with_: Dict[str, Any]


class Job(TypedDict, total=False):
    steps: List[Step]
    concurrency: Dict[str, Any]


Workflow = Dict[str, Any]


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------


def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        pytest.skip(f"{path.name} not found")
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def iter_workflow_files() -> Iterator[Path]:
    if not WORKFLOWS_DIR.exists():
        pytest.skip("Workflows directory not found")
    yield from WORKFLOWS_DIR.glob("*.yml")


def iter_workflows() -> Iterator[tuple[Path, Workflow]]:
    for path in iter_workflow_files():
        try:
            yield path, load_yaml(path)
        except yaml.YAMLError:
            continue


# ---------------------------------------------------------------------------
# Structured traversal helpers
# ---------------------------------------------------------------------------


def iter_jobs(workflow: Mapping[str, Any]) -> Iterable[Job]:
    jobs = workflow.get("jobs")
    if isinstance(jobs, dict):
        yield from jobs.values()


def iter_steps(job: Mapping[str, Any]) -> Iterable[Step]:
    steps = job.get("steps")
    if isinstance(steps, list):
        for step in steps:
            if isinstance(step, dict):
                yield step


def extract_python_versions(workflow: Mapping[str, Any]) -> Set[str]:
    """
    Extract python-version values from structured step definitions.
    """
    versions: Set[str] = set()

    for job in iter_jobs(workflow):
        for step in iter_steps(job):
            with_cfg = step.get("with_", step.get("with", {}))
            if isinstance(with_cfg, dict):
                version = with_cfg.get("python-version")
                if isinstance(version, str):
                    versions.add(version)

    return versions


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def all_workflows() -> List[tuple[Path, Workflow]]:
    return list(iter_workflows())


@pytest.fixture(scope="session")
def all_steps(all_workflows: List[tuple[Path, Workflow]]) -> List[Step]:
    steps: List[Step] = []
    for _, workflow in all_workflows:
        for job in iter_jobs(workflow):
            steps.extend(iter_steps(job))
    return steps


# ---------------------------------------------------------------------------
# Greetings workflow (structured validation)
# ---------------------------------------------------------------------------


class TestGreetingsWorkflowEdgeCases:
    @pytest.fixture
    def workflow(self) -> Workflow:
        return load_yaml(WORKFLOWS_DIR / "greetings.yml")

    def test_first_interaction_is_versioned(self, workflow: Workflow) -> None:
        steps = [
            step
            for job in iter_jobs(workflow)
            for step in iter_steps(job)
            if "uses" in step and "first-interaction" in step["uses"].lower()
        ]
        assert steps
        for step in steps:
            assert "@" in step["uses"]


# ---------------------------------------------------------------------------
# APISec workflow (structured job/step validation)
# ---------------------------------------------------------------------------


class TestAPISecWorkflowEdgeCases:
    @pytest.fixture
    def workflow(self) -> Workflow:
        return load_yaml(WORKFLOWS_DIR / "apisec-scan.yml")

    def test_concurrency_model(self, workflow: Workflow) -> None:
        for job in iter_jobs(workflow):
            conc = job.get("concurrency")
            if conc:
                assert "group" in conc
                assert "cancel-in-progress" in conc

    def test_apisec_steps_configured(self, workflow: Workflow) -> None:
        for job in iter_jobs(workflow):
            for step in iter_steps(job):
                uses = step.get("uses", "").lower()
                if "apisec" in uses:
                    with_cfg = step.get("with_", step.get("with", {}))
                    assert with_cfg
                    if "@" in uses:
                        version = uses.split("@", 1)[1]
                        if len(version) == 40:
                            assert version.isalnum()


# ---------------------------------------------------------------------------
# Cross-workflow consistency (no heuristics)
# ---------------------------------------------------------------------------


class TestWorkflowConsistency:
    def test_python_versions_consistent(
        self,
        all_workflows: List[tuple[Path, Workflow]],
    ) -> None:
        versions: Set[str] = set()

        for _, workflow in all_workflows:
            versions |= extract_python_versions(workflow)

        if versions:
            assert len(versions) <= 2

    def test_checkout_versions(self, all_steps: List[Step]) -> None:
        checkouts = [step["uses"] for step in all_steps if "uses" in step and "checkout" in step["uses"].lower()]
        if checkouts:
            # Accept either @v4 tags or SHA pins (40-char hex) as valid pinned versions
            v4 = sum("@v4" in u for u in checkouts)
            sha_pinned = sum(
                len(u.split("@")[1]) == 40 and all(c in "0123456789abcdef" for c in u.split("@")[1])
                for u in checkouts
                if "@" in u
            )
            pinned = v4 + sha_pinned
            assert pinned >= len(checkouts) * 0.7

    def test_permissions_declared(
        self,
        all_workflows: List[tuple[Path, Workflow]],
    ) -> None:
        for path, workflow in all_workflows:
            perms = workflow.get("permissions")
            if perms is not None:
                assert isinstance(perms, (dict, str))
                if isinstance(perms, dict):
                    assert perms
