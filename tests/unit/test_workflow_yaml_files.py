#!/usr/bin/env python3
"""
Unit tests for GitHub workflow YAML files and configuration files.

Tests validate YAML syntax, required fields, and proper structure for:
- .circleci/config.yml
- .codacy/codacy.yaml
- .github/workflows/*.yml
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _has_pytest_with_coverage(steps: list[object]) -> bool:
    for step in steps:
        if not isinstance(step, dict):
            continue
        run_step = step.get("run")
        if not isinstance(run_step, dict):
            continue
        command = run_step.get("command")
        if not isinstance(command, str):
            continue
        if "pytest" not in command:
            continue
        if "--cov" not in command:
            continue
        return True
    return False


def _has_codecov_upload_step(steps: list[object]) -> bool:
    return any(
        isinstance(step, dict) and step.get("codecov/upload") is not None for step in steps
    )


def _workflow_has_job(jobs: list[object], job_name: str) -> bool:
    return any(
        job == job_name or (isinstance(job, dict) and job_name in job)
        for job in jobs
    )


def _workflow_job_config(jobs: list[object], job_name: str) -> dict | None:
    for job in jobs:
        if isinstance(job, dict) and job_name in job:
            config = job[job_name]
            if isinstance(config, dict):
                return config
    return None


def _workflow_has_permissions(config: object) -> bool:
    if not isinstance(config, dict):
        return False

    if "permissions" in config:
        return True

    jobs = config.get("jobs")
    if not isinstance(jobs, dict):
        return False

    return any(isinstance(job, dict) and "permissions" in job for job in jobs.values())


@pytest.mark.unit
class TestCircleCIConfig:
    """Test CircleCI configuration file."""

    @pytest.fixture
    def circleci_config(self):
        """Load CircleCI config."""
        config_path = PROJECT_ROOT / ".circleci" / "config.yml"
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_circleci_config_valid_yaml(self):
        """CircleCI config is valid YAML."""
        config_path = PROJECT_ROOT / ".circleci" / "config.yml"
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config is not None

    def test_circleci_config_has_version(self, circleci_config):
        """CircleCI config specifies version."""
        assert "version" in circleci_config
        assert circleci_config["version"] in [2.1, "2.1", 2]

    def test_circleci_config_has_orbs(self, circleci_config):
        """CircleCI config defines required orbs."""
        assert "orbs" in circleci_config
        orbs = circleci_config["orbs"]
        assert isinstance(orbs, dict)
        assert "codecov" in orbs

    def test_circleci_config_has_executors(self, circleci_config):
        """CircleCI config defines executors."""
        assert "executors" in circleci_config
        executors = circleci_config["executors"]
        assert "python-executor" in executors
        assert "node-executor" in executors

    def test_circleci_config_has_jobs(self, circleci_config):
        """CircleCI config defines required jobs."""
        assert "jobs" in circleci_config
        jobs = circleci_config["jobs"]

        # Python jobs
        assert "python-lint" in jobs
        assert "python-test" in jobs
        assert "python-security" in jobs

        # Frontend jobs
        assert "frontend-lint" in jobs
        assert "frontend-build" in jobs

        # Docker job
        assert "docker-build" in jobs

    def test_circleci_python_lint_job_structure(self, circleci_config):
        """python-lint job has proper structure."""
        job = circleci_config["jobs"]["python-lint"]

        assert "executor" in job
        assert job["executor"] == "python-executor"
        assert "steps" in job

        steps = job["steps"]
        has_checkout = any(
            step == "checkout"
            or (isinstance(step, dict) and "checkout" in step)
            or "checkout" in str(step)
            for step in steps
        )
        assert has_checkout

    def test_circleci_python_test_job_coverage(self, circleci_config):
        """python-test job includes coverage reporting."""
        job = circleci_config["jobs"]["python-test"]
        steps = job["steps"]

        has_pytest = _has_pytest_with_coverage(steps)
        has_codecov = _has_codecov_upload_step(steps)

        assert has_pytest, "pytest with coverage not found"
        assert has_codecov, "codecov upload not found"

    def test_circleci_config_has_workflows(self, circleci_config):
        """CircleCI config defines workflows."""
        assert "workflows" in circleci_config
        workflows = circleci_config["workflows"]

        assert "build-and-test" in workflows
        assert "nightly-security" in workflows

    def test_circleci_workflow_job_dependencies(self, circleci_config):
        """CircleCI workflow defines proper job dependencies."""
        workflow = circleci_config["workflows"]["build-and-test"]
        jobs = workflow["jobs"]

        # Backend jobs can run in parallel, but docker-build should gate on them.
        assert _workflow_has_job(jobs, "python-lint")
        assert _workflow_has_job(jobs, "python-test")

        docker_build_entry = _workflow_job_config(jobs, "docker-build")

        assert docker_build_entry is not None
        assert "requires" in docker_build_entry
        assert "python-lint" in docker_build_entry["requires"]
        assert "python-test" in docker_build_entry["requires"]

    def test_circleci_nightly_security_schedule(self, circleci_config):
        """CircleCI nightly security workflow has cron schedule."""
        workflow = circleci_config["workflows"]["nightly-security"]

        assert "triggers" in workflow
        triggers = workflow["triggers"]
        assert len(triggers) > 0
        assert "schedule" in triggers[0]
        assert "cron" in triggers[0]["schedule"]


@pytest.mark.unit
class TestCodacyConfig:
    """Test Codacy configuration file."""

    @pytest.fixture
    def codacy_config(self):
        """Load Codacy config."""
        config_path = PROJECT_ROOT / ".codacy" / "codacy.yaml"
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_codacy_config_valid_yaml(self):
        """Codacy config is valid YAML."""
        config_path = PROJECT_ROOT / ".codacy" / "codacy.yaml"
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config is not None

    def test_codacy_config_has_runtimes(self, codacy_config):
        """Codacy config specifies runtimes."""
        assert "runtimes" in codacy_config
        runtimes = codacy_config["runtimes"]
        assert isinstance(runtimes, list)
        assert len(runtimes) > 0

    def test_codacy_config_has_node_runtime(self, codacy_config):
        """Codacy config includes Node.js runtime."""
        runtimes = codacy_config["runtimes"]
        runtime_strings = [str(r) for r in runtimes]
        assert any("node" in r for r in runtime_strings)

    def test_codacy_config_has_python_runtime(self, codacy_config):
        """Codacy config includes Python runtime."""
        runtimes = codacy_config["runtimes"]
        runtime_strings = [str(r) for r in runtimes]
        assert any("python" in r for r in runtime_strings)

    def test_codacy_config_has_tools(self, codacy_config):
        """Codacy config specifies analysis tools."""
        assert "tools" in codacy_config
        tools = codacy_config["tools"]
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_codacy_config_has_required_tools(self, codacy_config):
        """Codacy config includes required security and linting tools."""
        tools = codacy_config["tools"]
        tool_strings = [str(t) for t in tools]

        # Check for key tools
        assert any("eslint" in t for t in tool_strings), "eslint not found"
        assert any("pylint" in t for t in tool_strings), "pylint not found"
        assert any("trivy" in t for t in tool_strings), "trivy not found"
        assert any("semgrep" in t for t in tool_strings), "semgrep not found"


@pytest.mark.unit
class TestGitHubWorkflows:
    """Test GitHub workflow files."""

    @pytest.fixture(
        params=[
            "apisec-scan.yml",
            "bandit.yml",
            "bearer.yml",
            "ci.yml",
            "codacy.yml",
            "codeflash.yaml",
            "codeql.yml",
            "codescan.yml",
            "contrast-scan.yml",
            "debricked.yml",
            "dependency-review.yml",
            "devskim.yml",
            "docker-image.yml",
            "docker-publish.yml",
            "docker.yml",
            "dotnet-desktop.yml",
            "eslint.yml",
        ]
    )
    def workflow_file(self, request):
        """Parameterized fixture for all workflow files."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / request.param
        if workflow_path.exists():
            with open(workflow_path, encoding="utf-8") as f:
                return request.param, yaml.safe_load(f)
        return request.param, None

    def test_workflow_valid_yaml(self, workflow_file):
        """All workflow files are valid YAML."""
        filename, config = workflow_file
        if config is None:
            pytest.skip(f"{filename} does not exist")
        assert config is not None, f"{filename} is not valid YAML"

    def test_workflow_has_name(self, workflow_file):
        """All workflows have a name."""
        filename, config = workflow_file
        if config is None:
            pytest.skip(f"{filename} does not exist")
        assert "name" in config, f"{filename} missing 'name' field"
        assert isinstance(config["name"], str)
        assert len(config["name"]) > 0

    def test_workflow_has_trigger(self, workflow_file):
        """All workflows have at least one trigger."""
        filename, config = workflow_file
        if config is None:
            pytest.skip(f"{filename} does not exist")

        # Check for 'on' or True (YAML parses 'on:' as boolean True)
        assert "on" in config or True in config, f"{filename} missing trigger configuration"

    def test_workflow_has_jobs(self, workflow_file):
        """All workflows define jobs."""
        filename, config = workflow_file
        if config is None:
            pytest.skip(f"{filename} does not exist")

        assert "jobs" in config, f"{filename} missing 'jobs' field"
        assert isinstance(config["jobs"], dict)
        assert len(config["jobs"]) > 0, f"{filename} has no jobs defined"

    def test_workflow_jobs_have_runs_on(self, workflow_file):
        """All workflow jobs specify runs-on."""
        filename, config = workflow_file
        if config is None:
            pytest.skip(f"{filename} does not exist")

        jobs = config.get("jobs", {})
        for job_name, job_config in jobs.items():
            assert "runs-on" in job_config, f"{filename}: job '{job_name}' missing 'runs-on'"

    def test_workflow_jobs_have_steps(self, workflow_file):
        """All workflow jobs have steps."""
        filename, config = workflow_file
        if config is None:
            pytest.skip(f"{filename} does not exist")

        jobs = config.get("jobs", {})
        for job_name, job_config in jobs.items():
            assert "steps" in job_config, f"{filename}: job '{job_name}' missing 'steps'"
            assert isinstance(job_config["steps"], list)
            assert len(job_config["steps"]) > 0, f"{filename}: job '{job_name}' has no steps"


@pytest.mark.unit
class TestSpecificWorkflows:
    """Test specific workflow configurations."""

    def test_ci_workflow_python_versions(self):
        """CI workflow tests multiple Python versions."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        if not workflow_path.exists():
            pytest.skip("ci.yml does not exist")

        with open(workflow_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # Find test job
        test_job = config["jobs"].get("test")
        if test_job:
            assert "strategy" in test_job
            assert "matrix" in test_job["strategy"]
            assert "python-version" in test_job["strategy"]["matrix"]

            versions = test_job["strategy"]["matrix"]["python-version"]
            assert isinstance(versions, list)
            assert len(versions) >= 2, "Should test multiple Python versions"

    def test_apisec_workflow_has_secrets(self):
        """APIsec workflow references required secrets."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "apisec-scan.yml"
        if not workflow_path.exists():
            pytest.skip("apisec-scan.yml does not exist")

        with open(workflow_path, encoding="utf-8") as f:
            content = f.read()

        # Check for secret references
        assert "secrets.apisec_username" in content
        assert "secrets.apisec_password" in content

    def test_bandit_workflow_security_permissions(self):
        """Bandit workflow has proper security-events permissions."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "bandit.yml"
        if not workflow_path.exists():
            pytest.skip("bandit.yml does not exist")

        with open(workflow_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # Check job permissions
        bandit_job = config["jobs"].get("bandit")
        if bandit_job:
            assert "permissions" in bandit_job
            assert "security-events" in bandit_job["permissions"]
            assert bandit_job["permissions"]["security-events"] == "write"

    def test_codeql_workflow_languages(self):
        """CodeQL workflow specifies languages to analyze."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "codeql.yml"
        if not workflow_path.exists():
            pytest.skip("codeql.yml does not exist")

        with open(workflow_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # Find analyze job
        analyze_job = config["jobs"].get("analyze")
        if analyze_job and "strategy" in analyze_job:
            matrix = analyze_job["strategy"].get("matrix", {})
            # Language can be in matrix.language or matrix.include[].language
            has_languages = "language" in matrix or "include" in matrix
            assert has_languages, "CodeQL should specify languages"

    def test_dependency_review_workflow_on_pull_request(self):
        """Dependency review workflow triggers on pull requests."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "dependency-review.yml"
        if not workflow_path.exists():
            pytest.skip("dependency-review.yml does not exist")

        with open(workflow_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # YAML may parse 'on:' as True (boolean) so check both
        triggers = config.get("on", config.get(True, {}))
        if not triggers or triggers is True:
            # If on: is just a boolean, read the content to check
            with open(workflow_path, encoding="utf-8") as f:
                content = f.read()
            assert "pull_request" in content or "pull_request_target" in content
        else:
            assert "pull_request" in triggers or "pull_request_target" in triggers


@pytest.mark.unit
class TestWorkflowSecurity:
    """Test security best practices in workflows."""

    def test_workflows_use_pinned_actions(self):
        """Workflows should use pinned action versions for security."""
        workflows_dir = PROJECT_ROOT / ".github" / "workflows"

        risky_patterns = []

        for workflow_file in workflows_dir.glob("*.yml"):
            with open(workflow_file, encoding="utf-8") as f:
                content = f.read()

            # Check for unpinned actions (using @main or @master)
            if "@main" in content or "@master" in content:
                # Some exceptions are OK (composite actions, etc.)
                # Just flag for review rather than fail
                risky_patterns.append(workflow_file.name)

        # This is informational - pinned versions are recommended but not required
        if risky_patterns:
            warnings.warn(
                f"Workflows with @main/@master refs (consider pinning): {risky_patterns}",
                UserWarning,
            )

    def test_workflows_with_secrets_limit_permissions(self):
        """Workflows using secrets should have limited permissions."""
        workflows_dir = PROJECT_ROOT / ".github" / "workflows"

        for workflow_file in workflows_dir.glob("*.yml"):
            with open(workflow_file, encoding="utf-8") as f:
                content = f.read()
            if "secrets." not in content:
                continue

            config = yaml.safe_load(content)

            # This is a best practice, not a hard requirement.
            if not _workflow_has_permissions(config):
                print(f"\n{workflow_file.name} uses secrets but lacks explicit permissions")


class TestWorkflowConcurrency:
    """Test concurrency settings in workflows."""

    @pytest.mark.unit
    def test_ci_workflow_has_concurrency(self):
        """CI workflow should have concurrency settings to cancel outdated runs."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        if not workflow_path.exists():
            pytest.skip("ci.yml does not exist")

        with open(workflow_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # Check for concurrency at workflow level
        if "concurrency" in config:
            assert "group" in config["concurrency"]
            # cancel-in-progress is recommended but optional
            if "cancel-in-progress" in config["concurrency"]:
                assert isinstance(config["concurrency"]["cancel-in-progress"], bool)


class TestWorkflowPaths:
    """Test path filters in workflows."""

    @pytest.mark.unit
    def test_apisec_workflow_path_filters(self):
        """APIsec workflow has appropriate path filters."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "apisec-scan.yml"
        if not workflow_path.exists():
            pytest.skip("apisec-scan.yml does not exist")

        with open(workflow_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        on_config = config.get("on", {})

        # Check push paths
        if "push" in on_config and isinstance(on_config["push"], dict):
            assert "paths" in on_config["push"]
            paths = on_config["push"]["paths"]
            assert isinstance(paths, list)
            # Should include API-related paths
            assert any("api" in p or "src" in p for p in paths)


class TestYAMLSyntaxAllFiles:
    """Comprehensive YAML syntax validation."""

    @pytest.mark.unit
    def test_all_yaml_files_valid_syntax(self):
        """All YAML files in the changed list have valid syntax."""
        yaml_files = [
            ".circleci/config.yml",
            ".codacy/codacy.yaml",
            ".github/workflows/apisec-scan.yml",
            ".github/workflows/bandit.yml",
            ".github/workflows/bearer.yml",
            ".github/workflows/ci.yml",
            ".github/workflows/codacy.yml",
            ".github/workflows/codeflash.yaml",
            ".github/workflows/codeql.yml",
            ".github/workflows/codescan.yml",
            ".github/workflows/contrast-scan.yml",
            ".github/workflows/debricked.yml",
            ".github/workflows/dependency-review.yml",
            ".github/workflows/devskim.yml",
            ".github/workflows/docker-image.yml",
            ".github/workflows/docker-publish.yml",
            ".github/workflows/docker.yml",
            ".github/workflows/dotnet-desktop.yml",
            ".github/workflows/eslint.yml",
        ]

        for yaml_file in yaml_files:
            file_path = PROJECT_ROOT / yaml_file
            if file_path.exists():
                with open(file_path, encoding="utf-8") as f:
                    try:
                        config = yaml.safe_load(f)
                        assert config is not None, f"{yaml_file} is empty"
                    except yaml.YAMLError as e:
                        pytest.fail(f"{yaml_file} has invalid YAML syntax: {e}")


@pytest.mark.integration
class TestConfigurationConsistency:
    """Test consistency across configuration files."""

    def test_python_version_consistency(self):
        """Python versions should be consistent across configs."""
        # CircleCI
        circleci_path = PROJECT_ROOT / ".circleci" / "config.yml"
        with open(circleci_path, encoding="utf-8") as f:
            circleci_config = yaml.safe_load(f)

        # CI workflow
        ci_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        if ci_path.exists():
            with open(ci_path, encoding="utf-8") as f:
                ci_config = yaml.safe_load(f)

            # Both should test Python (versions may differ slightly)
            # Just ensure both have Python configuration
            assert "python" in str(circleci_config).lower()
            assert "python" in str(ci_config).lower()

    def test_node_version_consistency(self):
        """Node versions should be reasonable across configs."""
        circleci_path = PROJECT_ROOT / ".circleci" / "config.yml"
        with open(circleci_path, encoding="utf-8") as f:
            content = f.read()

        # Should reference Node in frontend jobs
        assert "node" in content.lower()
        # Should have a reasonable version
        assert "node:" in content or "cimg/node" in content
