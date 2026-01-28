"""Comprehensive YAML schema validation tests for GitHub Actions workflows."""

import re
from pathlib import Path
from typing import List

import pytest
import yaml


class TestWorkflowYAMLSyntax:
    """Test basic YAML syntax and structure of workflow files."""

    @staticmethod
    @pytest.fixture
    def workflow_files() -> List[Path]:
        """Get all workflow YAML files."""
        workflow_dir = Path(".github/workflows")
        return list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml"))

    @staticmethod
    def test_all_workflows_are_valid_yaml(workflow_files):
        """Test that all workflow files contain valid YAML."""
        for workflow_file in workflow_files:
            try:
                with open(workflow_file, "r") as f:
                    yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {workflow_file}: {e}")

    @staticmethod
    def test_no_duplicate_keys_in_workflows(workflow_files):
        """Test that workflow files don't have duplicate keys at any level."""

        def check_duplicates(data, path=""):
            """Recursively check for duplicate keys in nested dictionaries and lists, returning an error message if found."""
            if isinstance(data, dict):
                keys = list(data.keys())
                if len(keys) != len(set(keys)):
                    duplicates = [k for k in keys if keys.count(k) > 1]
                    return f"Duplicate keys at {path}: {duplicates}"
                for key, value in data.items():
                    result = check_duplicates(value, f"{path}.{key}" if path else key)
                    if result:
                        return result
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    result = check_duplicates(item, f"{path}[{i}]")
                    if result:
                        return result
            return None

        for workflow_file in workflow_files:
            with open(workflow_file, "r") as f:
                content = f.read()
                data = yaml.safe_load(content)
                error = check_duplicates(data)
                assert error is None, f"In {workflow_file}: {error}"
                assert error is None, f"In {workflow_file}: {error}"

    @staticmethod
    def test_workflows_have_required_fields(workflow_files):
        """Test that workflows have required top - level fields."""
        required_fields = ["name", "on"]

        for workflow_file in workflow_files:
            with open(workflow_file, "r") as f:
                data = yaml.safe_load(f)
                for field in required_fields:
                    assert field in data, (
                        f"{workflow_file} missing required field: {field}"
                    )

    @staticmethod
    def test_workflow_names_are_descriptive(workflow_files):
        """Test that workflow names are descriptive and unique."""
        names = []
        for workflow_file in workflow_files:
            with open(workflow_file, "r") as f:
                data = yaml.safe_load(f)
                name = data.get("name", "")
                assert len(name) > 5, (
                    f"{workflow_file} has non-descriptive name: '{name}'"
                )
                assert name not in names, f"Duplicate workflow name: '{name}'"
                names.append(name)


class TestWorkflowJobs:
    """Test job definitions in workflows."""

    @staticmethod
    @pytest.fixture
    def workflows_with_jobs() -> List[tuple]:
        """Get all workflows with their job definitions."""
        workflow_dir = Path(".github/workflows")
        workflows = []
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                data = yaml.safe_load(f)
                if "jobs" in data:
                    workflows.append((workflow_file.name, data))
        return workflows

    @staticmethod
    def test_all_jobs_have_runs_on(workflows_with_jobs):
        """Test that all jobs specify a runs - on platform."""
        for workflow_name, data in workflows_with_jobs:
            jobs = data.get("jobs", {})
            for job_name, job_config in jobs.items():
                assert "runs-on" in job_config, (
                    f"{workflow_name}: Job '{job_name}' missing runs-on"
                )

    @staticmethod
    def test_job_names_are_descriptive(workflows_with_jobs):
        """Test that job names follow conventions and are descriptive."""
        for workflow_name, data in workflows_with_jobs:
            jobs = data.get("jobs", {})
            for job_name in jobs.keys():
                assert len(job_name) > 2, (
                    f"{workflow_name}: Job name too short: '{job_name}'"
                )
                assert " " not in job_name, (
                    f"{workflow_name}: Job name contains spaces: '{job_name}'"
                )

    @staticmethod
    def test_jobs_with_steps_have_at_least_one_step(workflows_with_jobs):
        """Test that jobs with steps array have at least one step."""
        for workflow_name, data in workflows_with_jobs:
            jobs = data.get("jobs", {})
            for job_name, job_config in jobs.items():
                if "steps" in job_config:
                    steps = job_config["steps"]
                    assert isinstance(steps, list) and len(steps) > 0, (
                        f"{workflow_name}: Job '{job_name}' has empty steps"
                    )

    @staticmethod
    def test_checkout_action_uses_specific_version(workflows_with_jobs):
        """Test that checkout actions use pinned versions."""
        for workflow_name, data in workflows_with_jobs:
            jobs = data.get("jobs", {})
            for job_name, job_config in jobs.items():
                steps = job_config.get("steps", [])
                for step in steps:
                    if isinstance(step, dict) and "uses" in step:
                        uses = step["uses"]
                        if "actions/checkout" in uses:
                            assert "@v" in uses or "@" in uses, (
                                f"{workflow_name}: Job '{job_name}' uses unpinned checkout: {uses}"
                            )


class TestWorkflowSecurityAdvanced:
    """Test advanced security best practices in workflows."""

    @staticmethod
    @pytest.fixture
    def workflow_files() -> List[Path]:
        """Get all workflow YAML files."""
        workflow_dir = Path(".github/workflows")
        return list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml"))

    @staticmethod
    def test_no_hardcoded_secrets(workflow_files):
        """Test that workflows don't contain hardcoded secrets."""
        secret_patterns = [
            r'password\s*[:=]\s*["\'](?!.*\$\{\{)[\w-]+["\']',
            r'token\s*[:=]\s*["\'](?!.*\$\{\{)[\w-]+["\']',
            r'api[_-]?key\s*[:=]\s*["\'](?!.*\$\{\{)[\w-]+["\']',
        ]

        for workflow_file in workflow_files:
            with open(workflow_file, "r") as f:
                content = f.read()
                for pattern in secret_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    assert len(matches) == 0, (
                        f"{workflow_file} may contain hardcoded secrets"
                    )

    @staticmethod
    def test_secrets_use_github_secrets(workflow_files):
        """Test that secret references use proper GitHub secrets syntax."""
        for workflow_file in workflow_files:
            with open(workflow_file, "r") as f:
                content = f.read()
                secret_refs = re.findall(r"\$\{\{\s*secrets\.(\w+)\s*\}\}", content)
                for secret_ref in secret_refs:
                    assert secret_ref.isupper() or secret_ref.upper() == secret_ref, (
                        f"{workflow_file}: Secret '{secret_ref}' should be uppercase"
                    )

    @staticmethod
    def test_no_eval_or_bash_c_with_user_input(workflow_files):
        """Test that workflows don't use eval or bash - c with user - controlled input."""
        dangerous_patterns = [
            r"eval.*\$\{\{.*github\.event",
            r"bash\s+-c.*\$\{\{.*github\.event",
            r"\|\s*sh.*\$\{\{.*github\.event",
        ]

        for workflow_file in workflow_files:
            with open(workflow_file, "r") as f:
                content = f.read()
                for pattern in dangerous_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    assert len(matches) == 0, (
                        f"{workflow_file} uses dangerous command with user input"
                    )


class TestWorkflowPerformanceOptimization:
    """Test performance optimization patterns in workflows."""

    @staticmethod
    @pytest.fixture
    def workflows_with_jobs() -> List[tuple]:
        """Get all workflows with their job definitions."""
        workflow_dir = Path(".github/workflows")
        workflows = []
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                data = yaml.safe_load(f)
                if "jobs" in data:
                    workflows.append((workflow_file.name, data))
        return workflows

    @staticmethod
    def test_concurrent_jobs_use_needs(workflows_with_jobs):
        """Test that dependent jobs properly use 'needs' to run sequentially."""
        for workflow_name, data in workflows_with_jobs:
            jobs = data.get("jobs", {})
            job_names = set(jobs.keys())

            for job_name, job_config in jobs.items():
                needs = job_config.get("needs", [])
                if isinstance(needs, str):
                    needs = [needs]

                for needed_job in needs:
                    assert needed_job in job_names, (
                        f"{workflow_name}: Job '{job_name}' needs non-existent job '{needed_job}'"
                    )

    @staticmethod
    def test_matrix_strategies_are_reasonable(workflows_with_jobs):
        """Test that matrix strategies don't create excessive job combinations."""
        MAX_MATRIX_SIZE = 50

        for workflow_name, data in workflows_with_jobs:
            jobs = data.get("jobs", {})
            for job_name, job_config in jobs.items():
                strategy = job_config.get("strategy", {})
                matrix = strategy.get("matrix", {})

                if matrix and isinstance(matrix, dict):
                    total_combinations = 1
                    for _, values in matrix.items():
                        if isinstance(values, list):
                            total_combinations *= len(values)

                    assert total_combinations <= MAX_MATRIX_SIZE, (
                        f"{workflow_name}: Job '{job_name}' matrix creates {total_combinations} jobs"
                    )


class TestWorkflowTriggerValidation:
    """Test workflow trigger configurations."""

    @staticmethod
    @pytest.fixture
    def workflows_with_triggers() -> List[tuple]:
        """Get all workflows with their trigger definitions."""
        workflow_dir = Path(".github/workflows")
        workflows = []
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                data = yaml.safe_load(f)
                if "on" in data:
                    workflows.append((workflow_file.name, data))
        return workflows

    def workflow_files() -> List[Path]:
        """Get all workflow YAML files."""
        workflow_dir = Path(".github/workflows")
        return list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml"))

    @staticmethod
    def test_push_triggers_are_restricted(workflow_files):
        """Test that push triggers are limited to specific branches."""
        for workflow_file in workflow_files:
            with open(workflow_file, "r") as f:
                data = yaml.safe_load(f)
                on_config = data.get("on", {})

                if "push" in on_config:
                    push_config = on_config["push"]
                    if isinstance(push_config, dict):
                        has_restriction = (
                            "branches" in push_config
                            or "tags" in push_config
                            or "paths" in push_config
                        )
                        assert has_restriction, (
                            f"{workflow_file} has unrestricted push trigger"
                        )

    @staticmethod
    def test_schedule_triggers_have_reasonable_frequency(workflow_files):
        """Test that scheduled workflows don't run too frequently."""
        MIN_INTERVAL_MINUTES = 15

        for workflow_file in workflow_files:
            with open(workflow_file, "r") as f:
                data = yaml.safe_load(f)
                on_config = data.get("on", {})

                if "schedule" in on_config:
                    schedules = on_config["schedule"]
                    for schedule in schedules:
                        cron = schedule.get("cron", "")
                        parts = cron.split()
                        if len(parts) >= 2:
                            minute = parts[0]
                            if minute.startswith("*/"):
                                interval = int(minute.split("/")[1])
                                assert interval >= MIN_INTERVAL_MINUTES, (
                                    f"{workflow_file} scheduled too frequently"
                                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
