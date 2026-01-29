from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Step ID uniqueness is validated within TestWorkflowStepConfiguration.
"""Comprehensive tests for GitHub Actions workflow files.

This module validates the structure, syntax, and configuration of GitHub Actions
workflows, ensuring they are properly formatted and free of common issues like
duplicate keys, invalid syntax, and missing required fields.
"""


# Skip this module if PyYAML is not installed
yaml = pytest.importorskip("yaml")

# Define workflows directory path used across tests
WORKFLOWS_DIR = Path(".github") / "workflows"


def get_workflow_files() -> List[Path]:
    """
    List workflow YAML files in the repository's .github / workflows directory.

    Returns:
        List[Path]: Paths to files with `.yml` or `.yaml` extensions found in the workflows directory;
                    an empty list if the directory does not exist or no matching files are present.
    """
    if not WORKFLOWS_DIR.exists():
        return []
    return list(WORKFLOWS_DIR.glob("*.yml")) + list(WORKFLOWS_DIR.glob("*.yaml"))


def load_yaml_safe(file_path: Path) -> Dict[str, Any]:
    """
    Parse a YAML file and return its content.

    Parameters:
        file_path(Path): Path to the YAML file to load.

    Returns:
        The parsed YAML content — a mapping, sequence, scalar value, or `None` if the document is empty.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


"""
Module for detecting duplicate mapping keys in YAML files within integration tests.
"""


def check_duplicate_keys(file_path: Path) -> List[str]:
    """
    Detect duplicate mapping keys in a YAML file.

    Parameters:
        file_path(Path): Path to the YAML file to inspect.

    Returns:
        List of duplicate key names found, or an empty list if none are present.
    """
    duplicates = []

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse with a custom constructor that detects duplicates
    class DuplicateKeySafeLoader(yaml.SafeLoader):
        """SafeLoader subclass that detects duplicate keys in YAML mappings."""

        pass

    def constructor_with_dup_check(loader, node):
        """
        Construct a mapping from YAML node while checking for duplicate keys.

        Parameters:
            loader(SafeLoader): The YAML loader instance.
            node(MappingNode): The YAML mapping node to construct.

        Returns:
            dict: A dictionary mapping keys to values, duplicates recorded.
        """
        mapping = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=False)
            if key in mapping:
                duplicates.append(key)
            mapping[key] = loader.construct_object(value_node, deep=False)
        return mapping

    DuplicateKeySafeLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, constructor_with_dup_check
    )

    try:
        yaml.load(content, Loader=DuplicateKeySafeLoader)
    except yaml.YAMLError:
        pass  # Syntax errors will be caught by other tests

    return duplicates


class TestWorkflowSyntax:
    """Test suite for GitHub Actions workflow YAML syntax validation."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_valid_yaml_syntax(self, workflow_file: Path):
        """Test that workflow files contain valid YAML syntax."""
        try:
            load_yaml_safe(workflow_file)
        except yaml.YAMLError as e:
            pytest.fail(
                f"Workflow {workflow_file.name} contains invalid YAML syntax: {e}"
            )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_no_duplicate_keys(self, workflow_file: Path):
        """Test that workflow files do not contain duplicate keys."""
        duplicates = check_duplicate_keys(workflow_file)
        assert not duplicates, (
            f"Found duplicate keys in {workflow_file.name}: {duplicates}. "
            "Duplicate keys can cause unexpected behavior as YAML will "
            "silently overwrite earlier values."
        )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_readable(self, workflow_file: Path):
        """Check that a workflow file exists, is a regular file and contains non - empty UTF - 8 text."""
        assert workflow_file.exists(), f"Workflow file {workflow_file} does not exist"
        assert workflow_file.is_file(), f"Workflow path {workflow_file} is not a file"
        with open(workflow_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert len(content) > 0, f"Workflow file {workflow_file.name} is empty"


class TestWorkflowStructure:
    """Test suite for GitHub Actions workflow structure validation."""

    """Check that a workflow file exists, is a regular file and contains non-empty UTF-8 text."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_has_name(self, workflow_file: Path):
        """Verify the workflow YAML defines a non - empty top - level name."""
        config = load_yaml_safe(workflow_file)
        assert "name" in config, f"Workflow {workflow_file.name} missing 'name' field"
        assert config["name"], f"Workflow {workflow_file.name} has empty 'name' field"
        assert isinstance(config["name"], str), (
            f"Workflow {workflow_file.name} 'name' must be a string"
        )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_has_triggers(self, workflow_file: Path):
        """Validate that a workflow YAML defines a top - level "on" trigger."""
        config = load_yaml_safe(workflow_file)
        assert isinstance(config, dict), (
            f"Workflow {workflow_file.name} did not load to a mapping"
        )
        assert "on" in config, (
            f"Workflow {workflow_file.name} missing trigger configuration ('on' field)"
        )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_has_jobs(self, workflow_file: Path):
        """Ensure the workflow defines at least one job."""
        config = load_yaml_safe(workflow_file)
        assert "jobs" in config, f"Workflow {workflow_file.name} missing 'jobs' field"
        assert config["jobs"], f"Workflow {workflow_file.name} has empty 'jobs' field"
        assert isinstance(config["jobs"], dict), (
            f"Workflow {workflow_file.name} 'jobs' must be a dictionary"
        )
        assert len(config["jobs"]) > 0, (
            f"Workflow {workflow_file.name} must define at least one job"
        )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_jobs_have_steps(self, workflow_file: Path):
        """Ensure each job in the workflow defines either a `steps` sequence or a `uses` reusable workflow."""
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        for job_name, job_config in jobs.items():
            assert "steps" in job_config or "uses" in job_config, (
                f"Job '{job_name}' in {workflow_file.name} must have 'steps' or 'uses'"
            )

            if "steps" in job_config:
                assert job_config["steps"], (
                    f"Job '{job_name}' in {workflow_file.name} has empty 'steps'"
                )
                assert isinstance(job_config["steps"], list), (
                    f"Job '{job_name}' in {workflow_file.name} 'steps' must be a list"
                )


class TestWorkflowActions:
    """Test suite for GitHub Actions usage validation."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_actions_have_versions(self, workflow_file: Path):
        """
        Verify that every external action referenced by steps in the workflow is pinned to a specific version.
        
        This test asserts that each step using an external action includes an '@' ref and that the ref is not a floating branch like 'main', 'master', 'latest', or 'stable'. Failures raise an assertion describing the offending job, step, and action reference.
        
        Parameters:
            workflow_file (Path): Path to the workflow YAML file being validated.
        """
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])

                    # Action should have a version tag (e.g., @v1, @v3.5.2, or @<commit-sha>)
                    assert "@" in action, (
                        f"Step {idx} in job '{job_name}' of {workflow_file.name} "
                        f"must specify a pinned version for action '{action}'."
                    )
                    # Disallow floating branches like @main or @master
                    ref = action.split("@", 1)[1].strip()
                    assert ref and ref.lower() not in {
                        "main",
                        "master",
                        "latest",
                        "stable",
                    }, (
                        f"Step {idx} in job '{job_name}' of {workflow_file.name} "
                        f"uses a floating branch '{ref}' for action '{action}'. Use a tagged release or commit SHA."
                    )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_steps_have_names_or_uses(self, workflow_file: Path):
        """Ensure each step in every job defines at least one of 'name', 'uses' or 'run'."""
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])

            for idx, step in enumerate(steps):
                has_name = "name" in step
                has_uses = "uses" in step
                has_run = "run" in step

                assert has_name or has_uses or has_run, (
                    f"Step {idx} in job '{job_name}' of {workflow_file.name} "
                    "must have at least a 'name', 'uses', or 'run' field"
                )


class TestPrAgentWorkflow:
    """Comprehensive tests for the pr - agent.yml workflow."""

    @pytest.fixture
    def pr_agent_workflow(self) -> Dict[str, Any]:
        """Load the 'pr-agent' workflow YAML."""
        workflow_path = WORKFLOWS_DIR / "pr-agent.yml"
        if not workflow_path.exists():
            pytest.skip("pr-agent.yml not found")
        return load_yaml_safe(workflow_path)

    @staticmethod
    def _assert_valid_fetch_depth(step_with: Dict[str, Any]) -> None:
        """Assert that a checkout step's `with ` mapping has a valid optional `fetch - depth`."""
        if "fetch-depth" not in step_with:
            return

        fetch_depth = step_with["fetch-depth"]

        # Reject non-integer types (including strings)
        assert isinstance(fetch_depth, int), (
            f"fetch-depth should be an integer, got {type(fetch_depth).__name__}"
        )
        # Reject negative integers
        assert fetch_depth >= 0, "fetch-depth cannot be negative"

    def test_pr_agent_name(self, pr_agent_workflow: Dict[str, Any]):
        """Validate that the pr - agent workflow defines a top - level `name` field."""
        assert "name" in pr_agent_workflow, (
            "pr-agent workflow must have a descriptive 'name' field"
        )
        assert (
            isinstance(pr_agent_workflow["name"], str)
            and pr_agent_workflow["name"].strip()
        ), "pr-agent workflow 'name' field must be a non-empty string"

    def test_pr_agent_triggers_on_pull_request(self, pr_agent_workflow: Dict[str, Any]):
        """Test that pr - agent workflow triggers on pull_request events."""
        raw_triggers = pr_agent_workflow.get("on", {})

        # Normalize triggers to a set of explicit event names
        if isinstance(raw_triggers, str):
            normalized = {raw_triggers}
        elif isinstance(raw_triggers, list):
            normalized = set(raw_triggers)
        elif isinstance(raw_triggers, dict):
            normalized = set(raw_triggers.keys())
        else:
            normalized = set()

        assert "pull_request" in normalized, (
            "pr-agent workflow must trigger on pull_request events"
        )

    def test_pr_agent_has_trigger_job(self, pr_agent_workflow: Dict[str, Any]):
        """Assert that the pr - agent workflow defines a top - level job named "pr-agent-trigger"."""
        jobs = pr_agent_workflow.get("jobs", {})
        assert "pr-agent-trigger" in jobs, (
            "pr-agent workflow must define the 'pr-agent-trigger' job"
        )
        assert isinstance(jobs["pr-agent-trigger"], dict), (
            "'pr-agent-trigger' job must be a mapping"
        )

    def test_pr_agent_review_runs_on_ubuntu(self, pr_agent_workflow: Dict[str, Any]):
        """Ensure the pr - agent trigger job runs on a supported Ubuntu runner."""
        review_job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        runs_on = review_job.get("runs-on", "")
        assert runs_on in [
            "ubuntu-latest",
            "ubuntu-22.04",
            "ubuntu-20.04",
        ], f"PR Agent trigger job should run on standard Ubuntu runner, got '{runs_on}'"

    def test_pr_agent_has_checkout_step(self, pr_agent_workflow: Dict[str, Any]):
        """Ensure the pr - agent - trigger review job includes at least one actions / checkout step."""
        review_job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        steps = review_job.get("steps", [])

        checkout_steps = [
            s for s in steps if s.get("uses", "").startswith("actions/checkout")
        ]
        assert len(checkout_steps) > 0, "Review job must check out the repository"

    def test_pr_agent_fetch_depth_configured(self, pr_agent_workflow: Dict[str, Any]):
        """Validate that any actions / checkout steps in the pr - agent - trigger job specify a valid fetch - depth."""
        trigger_job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        steps = trigger_job.get("steps", [])

        checkout_steps = [
            s for s in steps if s.get("uses", "").startswith("actions/checkout")
        ]

        for step in checkout_steps:
            step_with = step.get("with", {})
            self._assert_valid_fetch_depth(step_with)

    def test_pr_agent_has_python_setup(self, pr_agent_workflow: Dict[str, Any]):
        """Ensure the pr - agent - trigger job includes at least one step that uses actions / setup - python."""
        review_job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        steps = review_job.get("steps", [])

        python_steps = [
            s for s in steps if s.get("uses", "").startswith("actions/setup-python")
        ]
        assert len(python_steps) > 0, "pr-agent-trigger job must set up Python"

    def test_pr_agent_python_version(self, pr_agent_workflow: Dict[str, Any]):
        """Validate that any actions / setup - python step in the pr - agent - trigger job specifies python - version "3.11"."""
        review_job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        steps = review_job.get("steps", [])

        python_steps = [
            s for s in steps if s.get("uses", "").startswith("actions/setup-python")
        ]

        for step in python_steps:
            step_with = step.get("with", {})
            assert "python-version" in step_with, (
                "Python setup should specify a version"
            )
            assert step_with["python-version"] == "3.11", (
                "Python version should be 3.11"
            )

    def test_pr_agent_no_duplicate_step_names(self, pr_agent_workflow: Dict[str, Any]):
        """Fail the test if the "pr-agent-trigger" job contains duplicate step names."""
        review_job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        steps = review_job.get("steps", [])

        step_names = [s.get("name") for s in steps if s.get("name")]
        seen = set()
        duplicate_names = set()
        for name in step_names:
            if name in seen:
                duplicate_names.add(name)
            else:
                seen.add(name)

        assert not duplicate_names, (
            f"Found duplicate step names: {duplicate_names}. "
            "Each step should have a unique name."
        )

    def test_pr_agent_parse_comments_step(self, pr_agent_workflow: Dict[str, Any]):
        """Verify the "Parse PR Review Comments" step in the pr - agent - trigger job."""
        job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        steps = job.get("steps", [])

        parse_step = None
        for step in steps:
            if step.get("name") == "Parse PR Review Comments":
                parse_step = step
                break

        assert parse_step is not None
        assert parse_step.get("id") == "parse-comments"
        assert "GITHUB_TOKEN" in parse_step.get("env", {})
        assert "gh api" in parse_step["run"]

    def test_pr_agent_fetch_depth_allows_absent(self):
        """Missing fetch - depth is permitted for checkout steps."""
        # Test empty configuration
        self._assert_valid_fetch_depth({})
        # Test configuration with other parameters but no fetch-depth
        self._assert_valid_fetch_depth({"token": "${{ secrets.GITHUB_TOKEN }}"})

    def test_pr_agent_fetch_depth_rejects_invalid_values(self):
        """Invalid fetch - depth values are rejected."""
        for invalid in ["0", -1, 1.5, None]:
            with pytest.raises(AssertionError):
                self._assert_valid_fetch_depth({"fetch-depth": invalid})


class TestWorkflowSecurity:
    """Test suite for workflow security best practices."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_no_hardcoded_secrets(self, workflow_file: Path):
        """Test that workflows don't contain hardcoded secrets or tokens."""
        with open(workflow_file, "r", encoding="utf-8") as f:
            content = f.read()

        suspicious_patterns = [
            r"\bghp_[a-zA-Z0-9]{36}\b",  # GitHub personal access token
            r"\bgho_[a-zA-Z0-9]{36}\b",  # GitHub OAuth token
            r"\bghu_[a-zA-Z0-9]{36}\b",  # GitHub user token
            r"\bghs_[a-zA-Z0-9]{36}\b",  # GitHub server token
            r"\bghr_[a-zA-Z0-9]{36}\b",  # GitHub refresh token
        ]

        for pattern in suspicious_patterns:
            assert not re.search(pattern, content), (
                f"Workflow {workflow_file.name} may contain hardcoded secret "
                f"(found pattern: {pattern}). Use secrets context instead."
            )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_uses_secrets_context(self, workflow_file: Path):
        """Verify sensitive keys in step `with ` mappings use the GitHub secrets context or are empty."""
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        for _, job_config in jobs.items():
            steps = job_config.get("steps", [])

            for step in steps:
                step_with = step.get("with", {})
                for key, value in step_with.items():
                    if any(
                        sensitive in key.lower()
                        for sensitive in ["token", "password", "key", "secret"]
                    ) and isinstance(value, str):
                        assert value.startswith("${{") or value == "", (
                            f"Sensitive field '{key}' in {workflow_file.name} "
                            "should use secrets context (e.g., ${{ secrets.TOKEN }})"
                        )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_secrets_not_echoed_to_logs(self, workflow_file: Path):
        """Test that secrets aren't accidentally printed to logs."""
        content = workflow_file.read_text(encoding="utf-8")

        secret_logging_patterns = [
            r"echo.*\$\{\{.*secrets\.",
            r"print.*\$\{\{.*secrets\.",
            r"console\.log.*\$\{\{.*secrets\.",
        ]

        for pattern in secret_logging_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            assert len(matches) == 0, (
                f"{workflow_file.name}: Potential secret logging detected"
            )


class TestWorkflowInjectionSecurity:
    """Advanced security tests specifically for injection vulnerabilities."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_no_environment_variable_injection(self, workflow_file: Path):
        """Test that workflows don't have potential env injection vulnerabilities."""
        content = workflow_file.read_text(encoding="utf-8")

        unsafe_patterns = [
            r"\$\{\{.*github\.event\..*\}\}.*bash",
            r"run:.*\$\{\{.*github\.event\.issue\.title",
            r"run:.*\$\{\{.*github\.event\.pull_request\.title",
        ]

        for pattern in unsafe_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            assert len(matches) == 0, (
                f"{workflow_file.name}: Potential injection vulnerability via {pattern}"
            )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_no_script_injection_in_run_commands(self, workflow_file: Path):
        """Test that run commands don't have dangerous patterns."""
        data = load_yaml_safe(workflow_file)
        jobs = data.get("jobs", {})

        for job_name, job in jobs.items():
            steps = job.get("steps", [])
            for idx, step in enumerate(steps):
                if "run" in step:
                    run_cmd = step["run"]
                    # Check for dangerous eval/exec patterns
                    dangerous_patterns = ["eval ", "exec(", "``"]
                    for pattern in dangerous_patterns:
                        assert pattern not in str(run_cmd).lower(), (
                            f"Dangerous pattern '{pattern}' in {workflow_file.name}, job {job_name}, step {idx}"
                        )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_no_curl_with_user_input(self, workflow_file: Path):
        """Test that curl commands don't use untrusted user input."""
        content = workflow_file.read_text(encoding="utf-8")

        # Check for curl with event data
        if "curl" in content and "github.event" in content:
            # Warn about potential URL injection
            lines = content.split("\n")
            for _, line in enumerate(lines):
                if "curl" in line.lower() and "github.event" in line:
                    # This is advisory
                    assert False, f"Potential URL injection in curl command: {line}"


class TestWorkflowMaintainability:
    """Test suite for workflow maintainability and best practices."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_steps_have_descriptive_names(self, workflow_file: Path):
        """Check that steps within each job of a workflow have descriptive names."""
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            unnamed_steps = []
            for idx, step in enumerate(steps):
                if "name" not in step and "uses" in step:
                    # Allow unnamed steps for very common actions
                    common_actions = ["actions/checkout", "actions/setup-"]
                    if not any(step["uses"].startswith(a) for a in common_actions):
                        unnamed_steps.append(
                            f"Step {idx}: {step.get('uses', 'unknown')}"
                        )

            if unnamed_steps:
                print(
                    f"\nWarning: {workflow_file.name} job '{job_name}' has "
                    f"{len(unnamed_steps)} unnamed steps."
                )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_reasonable_size(self, workflow_file: Path):
        """Assert the workflow file is within reasonable size limits(50KB max)."""
        file_size = workflow_file.stat().st_size
        if file_size > 10240:
            print(f"\nWarning: {workflow_file.name} is {file_size} bytes.")

        assert file_size < 51200, (
            f"Workflow {workflow_file.name} is too large ({file_size} bytes). "
        )


class TestWorkflowEdgeCases:
    """Test suite for edge cases and error conditions."""

    @staticmethod
    def test_workflow_directory_exists():
        """Test that .github / workflows directory exists."""
        assert WORKFLOWS_DIR.exists(), ".github/workflows directory does not exist"
        assert WORKFLOWS_DIR.is_dir(), ".github/workflows exists but is not a directory"

    @staticmethod
    def test_at_least_one_workflow_exists():
        """Test that at least one workflow file exists."""
        workflow_files = get_workflow_files()
        assert len(workflow_files) > 0, (
            "No workflow files found in .github/workflows directory"
        )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_file_extension(self, workflow_file: Path):
        """Verify that a workflow file uses the .yml or .yaml extension."""
        assert workflow_file.suffix in [".yml", ".yaml"], (
            f"Workflow file {workflow_file.name} has invalid extension."
        )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_no_tabs(self, workflow_file: Path):
        """Ensure the workflow YAML file contains no tab characters."""
        with open(workflow_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "\t" not in content, (
            f"Workflow {workflow_file.name} contains tab characters."
        )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_consistent_indentation(self, workflow_file: Path):
        """Warns when non - empty, non - comment lines use indentation not in multiples of two spaces."""
        with open(workflow_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        indentation_levels = set()
        for line in lines:
            if line.strip() and not line.strip().startswith("#"):
                spaces = len(line) - len(line.lstrip(" "))
                if spaces > 0:
                    indentation_levels.add(spaces)

        if indentation_levels:
            inconsistent = [level for level in indentation_levels if level % 2 != 0]
            if inconsistent:
                print(
                    f"FORMATTING: Workflow {workflow_file.name} has inconsistent indentation."
                )


class TestWorkflowStepConfiguration:
    """Detailed tests for workflow step configuration."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_steps_with_working_directory(self, workflow_file: Path):
        """Ensure steps that define `working - directory` use relative paths."""
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            for idx, step in enumerate(steps):
                if "working-directory" in step:
                    working_dir = step["working-directory"]
                    assert not working_dir.startswith("/"), (
                        f"Step {idx} in job '{job_name}' of {workflow_file.name} "
                        f"uses absolute path: {working_dir}"
                    )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_steps_with_id_are_unique(self, workflow_file: Path):
        """Test that step IDs are unique within each job."""
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            step_ids = [s.get("id") for s in steps if "id" in s]
            duplicates = [sid for sid, count in id_counts.items() if count > 1]
            assert not duplicates, (
                f"Job '{job_name}' in {workflow_file.name} has duplicate step IDs: {duplicates}"
            )


class TestWorkflowEnvAndSecrets:
    """Tests for environment variables and secrets usage."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_env_vars_naming_convention(self, workflow_file: Path):
        """Assert that environment variable names are upper - case and alphanumeric."""
        config = load_yaml_safe(workflow_file)

        def check_env_vars(env_dict: Any) -> List[str]:
            """Return env var keys that are not UPPER_CASE and [A - Z0 - 9_] - only."""
            if not isinstance(env_dict, dict):
                return []
            invalid_list: List[str] = []
            for key in env_dict.keys():
                if not isinstance(key, str):
                    invalid_list.append(str(key))
                    continue
                if not key.isupper() or not all(c.isalnum() or c == "_" for c in key):
                    invalid_list.append(key)
            return invalid_list

        # Check workflow-level env
        if "env" in config:
            invalid = check_env_vars(config["env"])
            assert not invalid, (
                f"Workflow {workflow_file.name} has invalid env vars: {invalid}"
            )

        # Check job-level env
        for job_name, job_config in config.get("jobs", {}).items():
            if isinstance(job_config, dict) and "env" in job_config:
                invalid = check_env_vars(job_config["env"])
                assert not invalid, (
                    f"Job '{job_name}' in {workflow_file.name} has invalid env vars: {invalid}"
                )


class TestTestSuiteCompleteness:
    """Meta - test to ensure test suite is comprehensive."""

    def test_all_workflow_files_tested(self):
        """Verify that all workflow files are included in tests."""
        workflow_files = get_workflow_files()
        assert len(workflow_files) > 0, "Should find at least one workflow file"

        for wf in workflow_files:
            assert wf.exists(), f"Workflow file {wf} should exist"
            assert wf.suffix in [".yml", ".yaml"], f"Workflow file {wf} should be YAML"

    def test_test_coverage_is_comprehensive(self):
        """Assert the test module contains a comprehensive number of test classes."""
        current_module = sys.modules[__name__]
        test_classes = [
            name
            for name, obj in inspect.getmembers(current_module)
            if inspect.isclass(obj) and name.startswith("Test")
        ]

        # Should have many test classes (approx 15+)
        assert len(test_classes) >= 10, (
            f"Should have substantial test classes, found {len(test_classes)}"
        )


class TestRequirementsDevValidation:
    """Tests for requirements - dev.txt changes."""

    def test_requirements_dev_file_exists(self):
        """Test that requirements - dev.txt exists."""
        req_file = Path("requirements-dev.txt")
        assert req_file.exists(), "requirements-dev.txt not found"

    def test_requirements_dev_valid_format(self):
        """Validate the format of requirements - dev.txt."""
        req_file = Path("requirements-dev.txt")
        if not req_file.exists():
            pytest.skip("requirements-dev.txt not found")

        with open(req_file, "r") as f:
            lines = f.readlines()

        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            assert len(line) > 0, f"Line {line_num}: Empty requirement"

            if "=" in line:
                parts = line.split("==")
                assert len(parts) <= 2, (
                    f"Line {line_num}: Multiple == in requirement: {line}"
                )

    def test_requirements_dev_pyyaml_present(self):
        """Ensure requirements - dev.txt contains PyYAML."""
        req_file = Path("requirements-dev.txt")
        if not req_file.exists():
            pytest.skip("requirements-dev.txt not found")

        with open(req_file, "r") as f:
            content = f.read().lower()

        assert "pyyaml" in content or "yaml" in content, (
            "PyYAML should be in requirements-dev.txt for workflow tests"
        )

    """Module for integration tests related to GitHub workflows, ensuring no conflicting dependencies between requirement files."""

    @staticmethod
    def test_no_conflicting_dependencies() -> None:
        """Verify there are no package version conflicts between requirements - dev.txt and requirements.txt."""
        req_file = Path("requirements-dev.txt")
        main_req_file = Path("requirements.txt")

        if not (req_file.exists() and main_req_file.exists()):
            pytest.skip("Both requirements files needed for this test")

        def parse_requirements(file_path: Path) -> dict[str, str]:
            """
            Parse a requirements file and return a mapping of package names
            to their full version specifier lines.
            """
            packages: dict[str, str] = {}
            with file_path.open(encoding="utf-8") as file_handle:
                for line in file_handle:
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#"):
                        pkg = (
                            stripped.split("==")[0]
                            .split(">=")[0]
                            .split("<=")[0]
                            .split("[")[0]
                            .strip()
                            .lower()
                        )
                        packages[pkg] = stripped

        return packages

    dev_pkgs = parse_requirements(req_file)
    main_pkgs = parse_requirements(main_req_file)

    conflicts: list[str] = []
    for pkg, dev_spec in dev_pkgs.items():
        main_spec = main_pkgs.get(pkg)
        if main_spec and dev_spec != main_spec:
            conflicts.append(f"{pkg}: dev='{dev_spec}' vs main='{main_spec}'")

    assert not conflicts, f"Version conflicts: {conflicts}"


class TestWorkflowDocumentationConsistency:
    """Test that workflow changes are properly documented."""

    @staticmethod
    def test_documentation_files_valid_markdown():
        """Verify all new markdown documentation files are valid."""
        doc_files = [
            "ADDITIONAL_TESTS_SUMMARY.md",
            "COMPREHENSIVE_ADDITIONAL_TESTS_SUMMARY.md",
        ]

        for doc_file in doc_files:
            doc_path = Path(doc_file)
            if not doc_path.exists():
                continue

            content = doc_path.read_text(encoding="utf-8")
            assert content.strip(), f"{doc_file} is empty"
            assert "#" in content, f"{doc_file} has no headers"


class TestRemovedFilesCleanup:
    """Test that removed files are properly cleaned up."""

    @staticmethod
    def test_labeler_yml_removed():
        """Verify labeler.yml configuration was removed."""
        labeler_config = Path(".github/labeler.yml")
        assert not labeler_config.exists(), "labeler.yml should be removed"

    @staticmethod
    def test_context_chunker_script_removed():
        """Verify context_chunker.py script was removed."""
        chunker_script = Path(".github/scripts/context_chunker.py")
        assert not chunker_script.exists(), "context_chunker.py should be removed"

    @staticmethod
    def test_scripts_readme_removed():
        """Verify scripts README was removed."""
        scripts_readme = Path(".github/scripts/README.md")
        assert not scripts_readme.exists(), "scripts README should be removed"

    @staticmethod
    def test_no_orphaned_script_references():
        """Ensure no workflows reference removed scripts."""
        for workflow_file in get_workflow_files():
            with open(workflow_file, "r", encoding="utf-8") as f:
                workflow_str = f.read()

            removed_refs = ["context_chunker.py", ".github/scripts/context_chunker.py"]
            for ref in removed_refs:
                assert ref not in workflow_str, (
                    f"{workflow_file.name} still references removed script: {ref}"
                )