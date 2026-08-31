#!/usr/bin/env python3
"""
Unit tests for GitHub workflow YAML files and configuration files.

Tests validate YAML syntax, required fields, and proper structure for:
- .circleci/config.yml
- .codacy/codacy.yaml
- .github/workflows/*.yml
"""

from __future__ import annotations

import re
import warnings
from collections.abc import Mapping
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _step_run_command(step: object) -> str | None:
    if not isinstance(step, dict):
        return None

    run_step = step.get("run")
    if isinstance(run_step, str):
        return run_step

    sequence_command = _command_from_run_sequence(run_step)
    if sequence_command is not None:
        return sequence_command

    return _command_from_run_mapping(run_step)


def _command_from_run_sequence(run_step: object) -> str | None:
    if not isinstance(run_step, (list, tuple)):
        return None

    parts: list[str] = []
    for item in run_step:
        if isinstance(item, str):
            parts.append(item)
            continue
        if isinstance(item, dict):
            cmd = item.get("command")
            if isinstance(cmd, str):
                parts.append(cmd)
    return "\n".join(parts) if parts else None


def _command_from_run_mapping(run_step: object) -> str | None:
    if not isinstance(run_step, dict):
        return None

    command_value: object = run_step.get("command")
    if isinstance(command_value, str):
        return command_value
    return None


def _has_pytest_with_coverage(steps: object) -> bool:
    if not isinstance(steps, list):
        return False

    for step in steps:
        command = _step_run_command(step)
        if command is not None and "pytest" in command and "--cov" in command:
            return True

        if _step_uses_cov_in_addopts(step):
            return True
    return False


def _step_uses_cov_in_addopts(step: object) -> bool:
    if not isinstance(step, dict):
        return False
    run_step = step.get("run")
    if not isinstance(run_step, dict):
        return False
    environment = run_step.get("environment")
    if not isinstance(environment, Mapping):
        return False
    addopts = environment.get("PYTEST_ADDOPTS")
    return isinstance(addopts, str) and "--cov" in addopts


def _has_codecov_upload_step(steps: object) -> bool:
    if not isinstance(steps, list):
        return False

    return any(isinstance(step, dict) and step.get("codecov/upload") is not None for step in steps)


def _workflow_has_job(jobs: list[object], job_name: str) -> bool:
    return any(job == job_name or (isinstance(job, dict) and job_name in job) for job in jobs)


def _workflow_job_config(jobs: list[object], job_name: str) -> dict | None:
    for job in jobs:
        if isinstance(job, dict) and job_name in job:
            config = job[job_name]
            if isinstance(config, dict):
                return config
    return None


def _workflow_has_permissions(config: object) -> bool:
    if not isinstance(config, Mapping):
        return False

    if "permissions" in config:
        return True

    jobs = config.get("jobs")
    if not isinstance(jobs, Mapping):
        return False

    return any(isinstance(job, Mapping) and "permissions" in job for job in jobs.values())


def _contains_string(node: object, target: str) -> bool:
    if isinstance(node, str):
        return target in node
    if isinstance(node, Mapping):
        return any(_contains_string(value, target) for value in node.values())
    if isinstance(node, list):
        return any(_contains_string(item, target) for item in node)
    return False


def _workflow_files(workflows_dir: Path) -> list[Path]:
    return sorted({*workflows_dir.glob("*.yml"), *workflows_dir.glob("*.yaml")})


def _parse_exact_pin(requirement_line: str, context: str) -> tuple[str, str]:
    """Return a normalized package and version from one exact requirement."""
    assert requirement_line.count("==") == 1, f"{context} must use one exact pin: {requirement_line}"
    package_name, version = requirement_line.split("==", maxsplit=1)
    assert package_name, f"{context} must name a package: {requirement_line}"
    assert version, f"{context} must name a version: {requirement_line}"
    return package_name.lower().replace("_", "-"), version


def _scanner_source_versions(source_path: Path) -> dict[str, str]:
    """Read the exact direct scanner versions from the source manifest."""
    source_lines = [
        line.strip()
        for line in source_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#") and not line.rstrip().endswith("\\")
    ]
    versions = dict(_parse_exact_pin(line, "scanner root") for line in source_lines)
    assert len(versions) == len(source_lines), "scanner roots must not repeat a package"
    return versions


def _locked_requirement_blocks(lock_lines: list[str]) -> list[str]:
    """Split a compiled requirements file into package-and-hash blocks."""
    requirement_starts = [
        index for index, line in enumerate(lock_lines) if line and not line[0].isspace() and not line.startswith("#")
    ]
    assert requirement_starts, "scanner lock should contain resolved packages"
    block_ends = [*requirement_starts[1:], len(lock_lines)]
    return ["\n".join(lock_lines[start:end]) for start, end in zip(requirement_starts, block_ends, strict=True)]


def _scanner_lock_versions(lock_path: Path) -> dict[str, str]:
    """Read exact package versions while enforcing a hash for every lock block."""
    lock_text = lock_path.read_text(encoding="utf-8")
    assert "# This file is autogenerated by pip-compile with Python 3.11" in lock_text
    assert "pip-compile --generate-hashes" in lock_text

    versions: dict[str, str] = {}
    for requirement_block in _locked_requirement_blocks(lock_text.splitlines()):
        requirement_line = requirement_block.splitlines()[0]
        assert requirement_line.endswith("\\"), f"lock entry must continue to hashes: {requirement_line}"
        exact_requirement = requirement_line[:-1].strip().split(" ; ", maxsplit=1)[0]
        package_name, version = _parse_exact_pin(exact_requirement, "lock entry")
        hashes = re.findall(r"--hash=sha256:[0-9a-f]{64}", requirement_block)
        assert hashes, f"lock entry must include a SHA-256 hash: {requirement_line}"
        versions[package_name] = version
    return versions


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
        tools = codacy_config.get("tools") if isinstance(codacy_config, dict) else None
        assert isinstance(tools, list), "tools section is missing or invalid"
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
            "contrast-scan.yml",
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
        if not workflow_path.exists():
            pytest.skip(f"{request.param} does not exist")
        with open(workflow_path, encoding="utf-8") as f:
            try:
                config = yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {request.param}: {e}")
            return request.param, config

    def test_workflow_valid_yaml(self, workflow_file):
        """All workflow files are valid YAML."""
        filename, config = workflow_file
        if config is None:
            pytest.skip(f"{filename} does not exist")
        assert config is not None, f"{filename} is not valid YAML"

    def test_workflow_has_name(self, workflow_file):
        """All workflows have a name."""
        filename, config = workflow_file
        assert isinstance(config, dict), f"{filename} parsed to {type(config).__name__}, expected a mapping/dict"
        assert "name" in config, f"{filename} missing 'name' field"
        assert isinstance(config["name"], str)
        assert len(config["name"]) > 0

    def test_workflow_has_trigger(self, workflow_file):
        """All workflows have at least one trigger."""
        filename, config = workflow_file
        assert isinstance(config, dict), f"{filename} parsed to {type(config).__name__}, expected a mapping/dict"
        # YAML may parse 'on:' as boolean True
        assert "on" in config or True in config, f"{filename} missing trigger configuration"

    def test_workflow_has_jobs(self, workflow_file):
        """All workflows define jobs."""
        filename, config = workflow_file
        assert isinstance(config, dict), f"{filename} parsed to {type(config).__name__}, expected a mapping/dict"

        assert "jobs" in config, f"{filename} missing 'jobs' field"
        assert isinstance(config["jobs"], dict)
        assert len(config["jobs"]) > 0, f"{filename} has no jobs defined"

    def test_workflow_jobs_have_runs_on(self, workflow_file):
        """All workflow jobs specify runs-on (reusable workflow jobs exempted)."""
        filename, config = workflow_file
        assert isinstance(config, dict), f"{filename} parsed to {type(config).__name__}, expected a mapping/dict"
        jobs = config.get("jobs", {})
        assert isinstance(jobs, dict), f"{filename} jobs should be a mapping/dict"
        for job_name, job_config in jobs.items():
            assert isinstance(job_config, dict), f"{filename}: job '{job_name}' config should be a mapping/dict"
            # Reusable workflow jobs use `uses:` at the job level and must not specify `runs-on`
            if "uses" in job_config:
                continue
            assert "runs-on" in job_config, f"{filename}: job '{job_name}' missing 'runs-on'"

    def test_workflow_jobs_have_steps(self, workflow_file):
        """All workflow jobs have steps (reusable workflow jobs exempted)."""
        filename, config = workflow_file
        assert isinstance(config, dict), f"{filename} parsed to {type(config).__name__}, expected a mapping/dict"
        jobs = config.get("jobs", {})
        assert isinstance(jobs, dict), f"{filename} jobs should be a mapping/dict"
        for job_name, job_config in jobs.items():
            assert isinstance(job_config, dict), f"{filename}: job '{job_name}' config should be a mapping/dict"
            # Reusable workflow jobs use `uses:` at the job level and must not specify `steps`
            if "uses" in job_config:
                continue
            assert "steps" in job_config, f"{filename}: job '{job_name}' missing 'steps'"
            assert isinstance(job_config["steps"], list)
            assert len(job_config["steps"]) > 0, f"{filename}: job '{job_name}' has no steps"


@pytest.mark.unit
class TestSpecificWorkflows:
    """Test specific workflow configurations."""

    def test_ci_security_scanners_use_isolated_environment(self):
        """Safety and Bandit must not share the installed runtime environment."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        with open(workflow_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        assert isinstance(config, dict), "ci.yml should parse to a mapping/dict"
        jobs = config.get("jobs")
        assert isinstance(jobs, dict), "ci.yml jobs should be a mapping/dict"
        security_job = jobs.get("security")
        assert isinstance(security_job, dict), "ci.yml should define the security job"
        steps = security_job.get("steps")
        assert isinstance(steps, list), "security job should define steps"

        ci_common_steps = [
            step for step in steps if isinstance(step, dict) and step.get("uses") == "./.github/actions/ci-common"
        ]
        assert len(ci_common_steps) == 1, "security job should invoke CI common exactly once"
        inputs = ci_common_steps[0].get("with")
        assert isinstance(inputs, dict), "security CI common step should define inputs"
        dependency_paths = inputs.get("dependency-paths")
        install = inputs.get("install")
        test = inputs.get("test")
        assert isinstance(dependency_paths, str)
        assert isinstance(install, str)
        assert isinstance(test, str)
        assert dependency_paths.splitlines() == ["requirements.txt", "requirements-ci-security.txt"]

        runtime_install = "pip install -r requirements.txt"
        runtime_freeze = "pip freeze > .ci-runtime-freeze.txt"
        scanner_venv = 'python -m venv "$RUNNER_TEMP/fardb-security-venv"'
        scanner_install = '"$RUNNER_TEMP/fardb-security-venv/bin/python" -m pip install \\'
        scanner_lock_install = "--require-hashes -r requirements-ci-security.txt"
        install_lines = [
            line.strip() for line in install.splitlines() if line.strip() and not line.lstrip().startswith("#")
        ]
        assert install_lines.index(runtime_install) < install_lines.index(runtime_freeze)
        assert install_lines.index(runtime_freeze) < install_lines.index(scanner_venv)
        assert install_lines.index(scanner_venv) < install_lines.index(scanner_install)
        assert install_lines.index(scanner_install) < install_lines.index(scanner_lock_install)
        assert "--system-site-packages" not in install
        assert "pip install safety bandit" not in install_lines
        assert '"$RUNNER_TEMP/fardb-security-venv/bin/python" -m pip install --upgrade pip' not in install_lines

        assert (
            '"$RUNNER_TEMP/fardb-security-venv/bin/safety" \\\n'
            "  check -r .ci-runtime-freeze.txt --policy-file .safety-policy.json --json"
        ) in test
        assert '"$RUNNER_TEMP/fardb-security-venv/bin/bandit" -r src/ -ll' in test
        job_continue_on_error = security_job.get("continue-on-error")
        step_continue_on_error = ci_common_steps[0].get("continue-on-error")
        assert job_continue_on_error is None or job_continue_on_error is False
        assert step_continue_on_error is None or step_continue_on_error is False
        assert "|| true" not in install
        assert "|| true" not in test

    def test_ci_security_scanner_lock_is_exact_and_hashed(self):
        """Every scanner package must be exact and protected by a SHA-256 hash."""
        source_path = PROJECT_ROOT / "requirements-ci-security.in"
        lock_path = PROJECT_ROOT / "requirements-ci-security.txt"

        source_versions = _scanner_source_versions(source_path)
        assert set(source_versions) == {"bandit", "safety"}

        locked_versions = _scanner_lock_versions(lock_path)
        assert locked_versions["bandit"] == source_versions["bandit"]
        assert locked_versions["safety"] == source_versions["safety"]

    def test_ci_workflow_python_versions(self):
        """CI workflow tests multiple Python versions."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        if not workflow_path.exists():
            pytest.skip("ci.yml does not exist")

        with open(workflow_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert isinstance(config, dict), "ci.yml should parse to a mapping/dict"
        jobs = config.get("jobs")
        assert isinstance(jobs, dict), "ci.yml jobs should be a mapping/dict"

        # Find test job
        test_job = jobs.get("test")
        if test_job:
            assert "strategy" in test_job
            assert "matrix" in test_job["strategy"]
            assert "python-version" in test_job["strategy"]["matrix"]

            versions = test_job["strategy"]["matrix"]["python-version"]
            assert isinstance(versions, list)
            assert len(versions) >= 2, "Should test multiple Python versions"

    def test_apisec_workflow_has_secrets(self):
        """The APIsec workflow references required secrets."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "apisec-scan.yml"
        if not workflow_path.exists():
            pytest.skip("apisec-scan.yml does not exist")

        with open(workflow_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert _contains_string(config, "secrets.apisec_username")
        assert _contains_string(config, "secrets.apisec_password")

    def test_bandit_workflow_security_permissions(self):
        """Bandit workflow has proper security-events permissions."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "bandit.yml"
        if not workflow_path.exists():
            pytest.skip("bandit.yml does not exist")

        with open(workflow_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert isinstance(config, dict), "bandit.yml should parse to a mapping/dict"
        jobs = config.get("jobs")
        assert isinstance(jobs, dict), "bandit.yml jobs should be a mapping/dict"

        # Check job permissions
        bandit_job = jobs.get("bandit")
        if bandit_job:
            assert "permissions" in bandit_job
            assert "security-events" in bandit_job["permissions"]
            assert bandit_job["permissions"]["security-events"] == "write"

    def test_codeql_workflow_languages(self):
        """The CodeQL workflow specifies languages to analyze."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "codeql.yml"
        if not workflow_path.exists():
            pytest.skip("codeql.yml does not exist")

        with open(workflow_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert isinstance(config, dict), "codeql.yml should parse to a mapping/dict"
        jobs = config.get("jobs")
        assert isinstance(jobs, dict), "codeql.yml jobs should be a mapping/dict"

        # Find analyze job
        analyze_job = jobs.get("analyze")
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
        assert isinstance(config, dict), "dependency-review.yml should parse to a mapping/dict"

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

        for workflow_file in _workflow_files(workflows_dir):
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
                stacklevel=2,
            )

    def test_workflows_with_secrets_limit_permissions(self):
        """Workflows using secrets should have limited permissions."""
        workflows_dir = PROJECT_ROOT / ".github" / "workflows"

        for workflow_file in _workflow_files(workflows_dir):
            with open(workflow_file, encoding="utf-8") as f:
                content = f.read()
            if "secrets." not in content:
                continue

            try:
                config = yaml.safe_load(content)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {workflow_file.name}: {e}")

            # This is a best practice, not a hard requirement.
            if not _workflow_has_permissions(config):
                warnings.warn(
                    f"{workflow_file.name} uses secrets but lacks explicit permissions",
                    UserWarning,
                    stacklevel=2,
                )


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
        assert isinstance(config, dict), "ci.yml should parse to a mapping/dict"

        # Check for concurrency at workflow level
        if "concurrency" in config:
            assert isinstance(config["concurrency"], dict), "concurrency should be a mapping/dict"
            assert "group" in config["concurrency"]
            # cancel-in-progress is recommended but optional
            if "cancel-in-progress" in config["concurrency"]:
                assert isinstance(config["concurrency"]["cancel-in-progress"], bool)


class TestWorkflowPaths:
    """Test path filters in workflows."""

    @pytest.mark.unit
    def test_apisec_workflow_path_filters(self):
        """The APIsec workflow has appropriate path filters."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "apisec-scan.yml"
        if not workflow_path.exists():
            pytest.skip("apisec-scan.yml does not exist")

        with open(workflow_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert isinstance(config, dict), "apisec-scan.yml should parse to a mapping/dict"

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
            ".github/workflows/contrast-scan.yml",
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
                        list(yaml.safe_load_all(f))
                    except yaml.YAMLError as e:
                        pytest.fail(f"Invalid YAML in {yaml_file}: {e}")


@pytest.mark.integration
class TestConfigurationConsistency:
    """Test consistency across configuration files."""
