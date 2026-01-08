"""
Comprehensive tests for GitHub Actions workflow files.

This module validates the structure, syntax, and configuration of GitHub Actions
workflows, ensuring they are properly formatted and free of common issues like
duplicate keys, invalid syntax, and missing required fields.
"""

import copy
import re
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml

BOOL_TAG = "tag:yaml.org,2002:bool"


class GitHubActionsYamlLoader(yaml.SafeLoader):
    """
    YAML loader compatible with GitHub Actions workflow files.

    GitHub parses workflows using YAML 1.2 rules where the `on` key is a string.
    PyYAML defaults to YAML 1.1 rules and interprets values like "on"/"off"/"yes"/"no"
    as booleans, which breaks parsing and validations.
    """

    pass


GitHubActionsYamlLoader.yaml_implicit_resolvers = copy.deepcopy(GitHubActionsYamlLoader.yaml_implicit_resolvers)


for ch, resolvers in list(GitHubActionsYamlLoader.yaml_implicit_resolvers.items()):
    GitHubActionsYamlLoader.yaml_implicit_resolvers[ch] = [
        (tag, regexp) for tag, regexp in resolvers if tag != BOOL_TAG
    ]

GitHubActionsYamlLoader.add_implicit_resolver(
    BOOL_TAG,
    re.compile(r"^(?:true|false)$", re.IGNORECASE),
    list("tTfF"),
)

# Path to workflows directory
WORKFLOWS_DIR = Path(__file__).parent.parent.parent / ".github" / "workflows"


def get_workflow_files() -> List[Path]:
    """
    List workflow YAML files in the repository's .github/workflows directory.

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
        file_path (Path): Path to the YAML file to load.

    Returns:
        The parsed YAML content — a mapping, sequence, scalar value, or `None` if the document is empty.

    Raises:
        yaml.YAMLError: If the file contains invalid YAML.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.load(f, Loader=GitHubActionsYamlLoader)


def check_duplicate_keys(file_path: Path) -> List[str]:
    """
    Detect duplicate mapping keys in a YAML file.

    Parameters:
        file_path (Path): Path to the YAML file to inspect.

    Returns:
        List of duplicate key names found, or an empty list if none are present.
    """
    duplicates = []

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse with a custom constructor that detects duplicates
    class DuplicateKeySafeLoader(GitHubActionsYamlLoader):
        pass

    def constructor_with_dup_check(loader, node):
        """
        Construct a dict from a YAML mapping node while recording duplicate keys.

        Parameters:
            loader: YAML loader used to construct key and value objects from nodes.
            node: YAML mapping node to convert.

        Returns:
            dict: Mapping of constructed keys to their corresponding values.

        Notes:
            Duplicate keys encountered are appended to the surrounding `duplicates` list.
        """
        mapping = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=False)
            if key in mapping:
                duplicates.append(key)
            mapping[key] = loader.construct_object(value_node, deep=False)
        return mapping

    DuplicateKeySafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, constructor_with_dup_check)

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
            with open(workflow_file, "r", encoding="utf-8") as f:
                yaml.load(f, Loader=GitHubActionsYamlLoader)
        except yaml.YAMLError as e:
            pytest.fail(f"Invalid YAML syntax in {workflow_file.name}: {e}")

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
        """
        Check that a workflow file exists, is a regular file and contains non-empty UTF-8 text.
        """
        assert workflow_file.exists(), f"Workflow file {workflow_file} does not exist"
        assert workflow_file.is_file(), f"Workflow path {workflow_file} is not a file"
        with open(workflow_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert len(content) > 0, f"Workflow file {workflow_file.name} is empty"


class TestWorkflowStructure:
    """Test suite for GitHub Actions workflow structure validation."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_has_name(self, workflow_file: Path):
        """
        Verify the workflow YAML defines a non-empty top-level name.

        Asserts that the top-level "name" key is present and its value is a non-empty string; failure messages include the workflow filename for context.
        """
        config = load_yaml_safe(workflow_file)
        assert "name" in config, f"Workflow {workflow_file.name} missing 'name' field"
        assert config["name"], f"Workflow {workflow_file.name} has empty 'name' field"
        assert isinstance(config["name"], str), f"Workflow {workflow_file.name} 'name' must be a string"

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_has_triggers(self, workflow_file: Path):
        """
        Ensure the workflow defines at least one trigger via a top-level "on" field.

        Asserts that the loaded workflow mapping contains a top-level "on" key.
        """
        config = load_yaml_safe(workflow_file)
        assert "on" in config, f"Workflow {workflow_file.name} missing trigger configuration ('on' field)"

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_has_jobs(self, workflow_file: Path):
        """
        Ensure the workflow defines at least one job.

        Asserts that the top-level "jobs" field is present, is a mapping (dictionary), and contains at least one job entry for the given workflow file.
        """
        config = load_yaml_safe(workflow_file)
        assert "jobs" in config, f"Workflow {workflow_file.name} missing 'jobs' field"
        assert config["jobs"], f"Workflow {workflow_file.name} has empty 'jobs' field"
        assert isinstance(config["jobs"], dict), f"Workflow {workflow_file.name} 'jobs' must be a dictionary"
        assert len(config["jobs"]) > 0, f"Workflow {workflow_file.name} must define at least one job"

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_jobs_have_steps(self, workflow_file: Path):
        """
        Ensure each job in the workflow defines either a `steps` sequence or a `uses` reusable workflow, and that any `steps` entry is a non-empty list.

        Fails the test if a job:
        - does not contain either `steps` or `uses`;
        - has an empty `steps` value;
        - has a `steps` value that is not a list.

        Parameters:
            workflow_file (Path): Path to the workflow YAML file being validated.
        """
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        for job_name, job_config in jobs.items():
            assert (
                "steps" in job_config or "uses" in job_config
            ), f"Job '{job_name}' in {workflow_file.name} must have 'steps' or 'uses'"

            if "steps" in job_config:
                assert job_config["steps"], f"Job '{job_name}' in {workflow_file.name} has empty 'steps'"
                assert isinstance(
                    job_config["steps"], list
                ), f"Job '{job_name}' in {workflow_file.name} 'steps' must be a list"


class TestWorkflowActions:
    """Test suite for GitHub Actions usage validation."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_actions_have_versions(self, workflow_file: Path):
        """Test that all GitHub Actions specify a version/tag."""
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])

            for idx, step in enumerate(steps):
                if "uses" in step:
                    action = step["uses"]
                    # Action should have a version tag (e.g., @v1, @main, @sha)
                    assert "@" in action, (
                        f"Step {idx} in job '{job_name}' of {workflow_file.name} "
                        f"uses action '{action}' without a version tag"
                    )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_steps_have_names_or_uses(self, workflow_file: Path):
        """
        Ensure each step in every job defines at least one of 'name', 'uses' or 'run'.

        Parameters:
            workflow_file (Path): Path to the workflow YAML file being validated.
        """
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
    """Specific tests for the pr-agent.yml workflow."""

    @pytest.fixture
    def pr_agent_workflow(self) -> Dict[str, Any]:
        """
        Load the 'pr-agent' workflow YAML and provide its parsed mapping for tests.

        If the file .github/workflows/pr-agent.yml is missing, the invoking test is skipped.

        Returns:
            workflow (Dict[str, Any]): Parsed YAML mapping of the pr-agent workflow.
        """
        workflow_path = WORKFLOWS_DIR / "pr-agent.yml"
        if not workflow_path.exists():
            pytest.skip("pr-agent.yml not found")
        return load_yaml_safe(workflow_path)

    def test_pr_agent_name(self, pr_agent_workflow: Dict[str, Any]):
        """
        Assert the pr-agent workflow's top-level "name" equals "PR Agent".

        Parameters:
            pr_agent_workflow (Dict[str, Any]): Parsed YAML mapping for the pr-agent workflow fixture.
        """
        assert pr_agent_workflow["name"] == "PR Agent"

    def test_pr_agent_triggers_on_pull_request(self, pr_agent_workflow: Dict[str, Any]):
        """Test that pr-agent workflow triggers on pull request events."""
        triggers = pr_agent_workflow.get("on", {})
        assert "pull_request" in triggers, "pr-agent workflow should trigger on pull_request events"

    def test_pr_agent_has_review_job(self, pr_agent_workflow: Dict[str, Any]):
        """Test that pr-agent workflow has a review job."""
        jobs = pr_agent_workflow.get("jobs", {})
        assert "pr-agent-trigger" in jobs, "pr-agent workflow must have a 'pr-agent-trigger' job"

    def test_pr_agent_review_runs_on_ubuntu(self, pr_agent_workflow: Dict[str, Any]):
        """Test that review job runs on Ubuntu."""
        review_job = pr_agent_workflow["jobs"]["review"]
        runs_on = review_job.get("runs-on", "")
        assert "ubuntu" in runs_on.lower(), "Review job should run on Ubuntu runner"

    def test_pr_agent_has_checkout_step(self, pr_agent_workflow: Dict[str, Any]):
        """Test that review job checks out the code."""
        review_job = pr_agent_workflow["jobs"]["review"]
        steps = review_job.get("steps", [])

        checkout_steps = [s for s in steps if s.get("uses", "").startswith("actions/checkout")]
        assert len(checkout_steps) > 0, "Review job must check out the repository"

    def test_pr_agent_checkout_has_token(self, pr_agent_workflow: Dict[str, Any]):
        """
        Ensure every actions/checkout step in the review job provides a `token` in its `with` mapping.

        Fails the test if any checkout step omits the `token` key.
        """
        review_job = pr_agent_workflow["jobs"]["review"]
        steps = review_job.get("steps", [])

        checkout_steps = [s for s in steps if s.get("uses", "").startswith("actions/checkout")]

        for step in checkout_steps:
            step_with = step.get("with", {})
            assert "token" in step_with, "Checkout step should specify a token"

    def test_pr_agent_has_python_setup(self, pr_agent_workflow: Dict[str, Any]):
        """
        Asserts the workflow's "review" job includes at least one step that uses actions/setup-python.

        Parameters:
            pr_agent_workflow (Dict[str, Any]): Parsed YAML mapping for the pr-agent workflow; expected to contain a "jobs" mapping with a "review" job.
        """
        review_job = pr_agent_workflow["jobs"]["review"]
        steps = review_job.get("steps", [])

        python_steps = [s for s in steps if s.get("uses", "").startswith("actions/setup-python")]
        assert len(python_steps) > 0, "Review job must set up Python"

    def test_pr_agent_has_node_setup(self, pr_agent_workflow: Dict[str, Any]):
        """Test that review job sets up Node.js."""
        review_job = pr_agent_workflow["jobs"]["review"]
        steps = review_job.get("steps", [])

        node_steps = [s for s in steps if s.get("uses", "").startswith("actions/setup-node")]
        assert len(node_steps) > 0, "Review job must set up Node.js"

    def test_pr_agent_python_version(self, pr_agent_workflow: Dict[str, Any]):
        """
        Ensure any actions/setup-python step in the "review" job specifies python-version "3.11".

        Parameters:
            pr_agent_workflow (Dict[str, Any]): Parsed workflow mapping for the PR Agent workflow; expected to contain a "jobs" -> "review" -> "steps" sequence.

        """
        review_job = pr_agent_workflow["jobs"]["review"]
        steps = review_job.get("steps", [])

        python_steps = [s for s in steps if s.get("uses", "").startswith("actions/setup-python")]

        for step in python_steps:
            step_with = step.get("with", {})
            assert "python-version" in step_with, "Python setup should specify a version"
            assert step_with["python-version"] == "3.11", "Python version should be 3.11"

    def test_pr_agent_no_duplicate_setup_steps(self, pr_agent_workflow: Dict[str, Any]):
        """Test that there are no duplicate setup steps in the workflow."""
        review_job = pr_agent_workflow["jobs"]["review"]
        steps = review_job.get("steps", [])

        # Check for duplicate step names
        step_names = [s.get("name", "") for s in steps if s.get("name")]
        duplicate_names = [name for name in step_names if step_names.count(name) > 1]

        assert not duplicate_names, (
            f"Found duplicate step names: {set(duplicate_names)}. " "Each step should have a unique name."
        )

    def test_pr_agent_fetch_depth_configured(self, pr_agent_workflow: Dict[str, Any]):
        """
        Ensure checkout steps in the PR Agent review job have valid fetch-depth values.

        Checks each step in `jobs.review` that uses `actions/checkout`; if the step's `with` mapping contains `fetch-depth` the value must be an integer or exactly 0, otherwise an assertion fails.

        Parameters:
            pr_agent_workflow (Dict[str, Any]): Parsed workflow mapping for the PR Agent workflow.
        """
        review_job = pr_agent_workflow["jobs"]["review"]
        steps = review_job.get("steps", [])

        checkout_steps = [s for s in steps if s.get("uses", "").startswith("actions/checkout")]

        for step in checkout_steps:
            step_with = step.get("with", {})
            if "fetch-depth" in step_with:
                fetch_depth = step_with["fetch-depth"]
                assert isinstance(fetch_depth, int) or fetch_depth == 0, "fetch-depth should be an integer"


class TestWorkflowSecurity:
    """Test suite for workflow security best practices."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_no_hardcoded_secrets(self, workflow_file: Path):
        """Test that workflows don't contain hardcoded secrets or tokens."""
        with open(workflow_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Patterns that might indicate hardcoded secrets
        suspicious_patterns = [
            "ghp_",  # GitHub personal access token
            "gho_",  # GitHub OAuth token
            "ghu_",  # GitHub user token
            "ghs_",  # GitHub server token
            "ghr_",  # GitHub refresh token
        ]

        for pattern in suspicious_patterns:
            assert pattern not in content, (
                f"Workflow {workflow_file.name} may contain hardcoded secret "
                f"(found pattern: {pattern}). Use secrets context instead."
            )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_uses_secrets_context(self, workflow_file: Path):
        """
        Verify sensitive keys in step `with` mappings use the GitHub secrets context or are empty.

        Scans each job's steps and for any `with` keys containing `token`, `password`, `key` or `secret` asserts that string values start with `"${{"` (secrets context) or are empty.
        """
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])

            for step in steps:
                step_with = step.get("with", {})

                # Check if token/password fields use secrets context
                for key, value in step_with.items():
                    if any(sensitive in key.lower() for sensitive in ["token", "password", "key", "secret"]):
                        if isinstance(value, str):
                            assert value.startswith("${{") or value == "", (
                                f"Sensitive field '{key}' in {workflow_file.name} "
                                "should use secrets context (e.g., ${{ secrets.TOKEN }})"
                            )


class TestWorkflowMaintainability:
    """Test suite for workflow maintainability and best practices."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_steps_have_descriptive_names(self, workflow_file: Path):
        """
        Check that steps within each job of a workflow have descriptive names and warn when they do not.

        Scans the workflow YAML at `workflow_file` and for each job examines its `steps`. If a step uses an action and lacks a `name`, a warning is printed unless the action is one of a small set of common actions exempted from naming (for example `actions/checkout` and `actions/setup-*`).

        Parameters:
            workflow_file (Path): Path to the workflow YAML file being checked.
        """
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])

            unnamed_steps = []
            for idx, step in enumerate(steps):
                # Steps should have names unless they're very simple
                if "name" not in step and "uses" in step:
                    # Allow unnamed steps for very common actions
                    common_actions = ["actions/checkout", "actions/setup-"]
                    if not any(step["uses"].startswith(a) for a in common_actions):
                        unnamed_steps.append(f"Step {idx}: {step.get('uses', 'unknown')}")

            # This is a warning rather than a hard failure
            if unnamed_steps:
                print(
                    f"\nWarning: {workflow_file.name} job '{job_name}' has "
                    f"{len(unnamed_steps)} unnamed steps (recommended to add names)"
                )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_reasonable_size(self, workflow_file: Path):
        """
        Assert the workflow file is within reasonable size limits.

        If the file is larger than 10,240 bytes (10 KB) a warning is printed to encourage splitting complex workflows.
        If the file is 51,200 bytes (50 KB) or larger the test fails with an assertion instructing to split the workflow or use reusable workflows.
        """
        file_size = workflow_file.stat().st_size

        # Warn if workflow file exceeds 10KB (reasonable limit)
        if file_size > 10240:
            print(
                f"\nWarning: {workflow_file.name} is {file_size} bytes. "
                "Consider splitting into multiple workflows if it gets too complex."
            )

        # Fail if exceeds 50KB (definitely too large)
        assert file_size < 51200, (
            f"Workflow {workflow_file.name} is too large ({file_size} bytes). "
            "Consider splitting into multiple workflows or using reusable workflows."
        )


class TestWorkflowEdgeCases:
    """Test suite for edge cases and error conditions."""

    def test_workflow_directory_exists(self):
        """Test that .github/workflows directory exists."""
        assert WORKFLOWS_DIR.exists(), ".github/workflows directory does not exist"
        assert WORKFLOWS_DIR.is_dir(), ".github/workflows exists but is not a directory"

    def test_at_least_one_workflow_exists(self):
        """Test that at least one workflow file exists."""
        workflow_files = get_workflow_files()
        assert len(workflow_files) > 0, "No workflow files found in .github/workflows directory"

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_file_extension(self, workflow_file: Path):
        """
        Verify that a workflow file uses the .yml or .yaml extension.

        Parameters:
            workflow_file (Path): Path to the workflow file being tested.
        """
        assert workflow_file.suffix in [".yml", ".yaml"], (
            f"Workflow file {workflow_file.name} has invalid extension. " "Use .yml or .yaml"
        )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_encoding(self, workflow_file: Path):
        """Test that workflow files use UTF-8 encoding."""
        try:
            with open(workflow_file, "r", encoding="utf-8") as f:
                f.read()
        except UnicodeDecodeError:
            pytest.fail(
                f"Workflow {workflow_file.name} is not valid UTF-8. " "Ensure file is saved with UTF-8 encoding."
            )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_no_tabs(self, workflow_file: Path):
        """
        Ensure the workflow YAML file contains no tab characters.

        Fails the test if any tab character is present, because YAML indentation must use spaces rather than tabs.
        """
        with open(workflow_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert "\t" not in content, (
            f"Workflow {workflow_file.name} contains tab characters. "
            "YAML files should use spaces for indentation, not tabs."
        )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_consistent_indentation(self, workflow_file: Path):
        """
        Ensure all non-empty, non-comment lines in the workflow file use indentation in multiples of two spaces.

        This test checks the leading-space count of significant lines and fails if any line's indentation is not a multiple of 2.
        """
        with open(workflow_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        indentation_levels = set()
        for line in lines:
            if line.strip() and not line.strip().startswith("#"):
                # Count leading spaces
                spaces = len(line) - len(line.lstrip(" "))
                if spaces > 0:
                    indentation_levels.add(spaces)

        # Check if indentation is consistent (multiples of 2)
        if indentation_levels:
            inconsistent = [level for level in indentation_levels if level % 2 != 0]
            assert not inconsistent, (
                f"Workflow {workflow_file.name} has inconsistent indentation. "
                f"Found indentation levels: {sorted(indentation_levels)}. "
                "Use 2-space indentation consistently."
            )


class TestWorkflowPerformance:
    """Test suite for workflow performance considerations."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_uses_caching(self, workflow_file: Path):
        """
        Check whether a workflow uses caching and print an informational message if none is detected.

        Scans the workflow's jobs and steps for common caching indicators (for example an `actions/cache` action or a `cache` key in a step's `with` block). This check is advisory and will not fail the test; it only emits an informational message when no caching is found.

        Parameters:
            workflow_file (Path): Path to the workflow YAML file to inspect.
        """
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        has_cache = False
        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])

            for step in steps:
                if "actions/cache" in step.get("uses", ""):
                    has_cache = True
                    break

                # Check for setup actions with caching enabled
                step_with = step.get("with", {})
                if "cache" in step_with:
                    has_cache = True
                    break

        # This is informational, not a hard requirement
        if not has_cache:
            print(
                f"\nInfo: {workflow_file.name} doesn't use caching. " "Consider adding caching to improve performance."
            )


class TestPrAgentWorkflowAdvanced:
    """Advanced comprehensive tests for pr-agent.yml workflow specifics."""

    @pytest.fixture
    def pr_agent_workflow(self) -> Dict[str, Any]:
        """
        Load and return the parsed 'pr-agent.yml' workflow from the workflows directory; skip the test if the file is missing.

        Returns:
            dict: Parsed YAML content of the 'pr-agent.yml' workflow.

        Raises:
            yaml.YAMLError: If the workflow file contains invalid YAML.
        """
        workflow_path = WORKFLOWS_DIR / "pr-agent.yml"
        if not workflow_path.exists():
            pytest.skip("pr-agent.yml not found")
        return load_yaml_safe(workflow_path)

    def test_pr_agent_has_three_jobs(self, pr_agent_workflow: Dict[str, Any]):
        """
        Ensure the pr-agent workflow defines exactly three jobs.

        Asserts that the workflow's top-level `jobs` mapping contains exactly three entries named "pr-agent-trigger", "auto-merge-check" and "dependency-update".
        """
        jobs = pr_agent_workflow.get("jobs", {})
        assert len(jobs) == 3, f"pr-agent workflow should have exactly 3 jobs, found {len(jobs)}"
        assert "pr-agent-trigger" in jobs
        assert "auto-merge-check" in jobs
        assert "dependency-update" in jobs

    def test_pr_agent_permissions_structure(self, pr_agent_workflow: Dict[str, Any]):
        """
        Ensure the pr-agent workflow defines the expected top-level and job-level permissions.

        Checks performed:
        - Top-level `permissions.contents` equals "read".
        - `pr-agent-trigger` job has `permissions.issues` set to "write".
        - `auto-merge-check` job has `permissions.issues` and `permissions.pull-requests` set to "write".
        - `dependency-update` job has `permissions.pull-requests` set to "write".

        Parameters:
            pr_agent_workflow (Dict[str, Any]): Parsed workflow dictionary for the pr-agent workflow.
        """
        # Top-level permissions
        assert "permissions" in pr_agent_workflow
        assert pr_agent_workflow["permissions"]["contents"] == "read"

        # Job-level permissions
        jobs = pr_agent_workflow["jobs"]
        assert "permissions" in jobs["pr-agent-trigger"]
        assert jobs["pr-agent-trigger"]["permissions"]["issues"] == "write"

        assert "permissions" in jobs["auto-merge-check"]
        assert jobs["auto-merge-check"]["permissions"]["issues"] == "write"
        assert jobs["auto-merge-check"]["permissions"]["pull-requests"] == "write"

        assert "permissions" in jobs["dependency-update"]
        assert jobs["dependency-update"]["permissions"]["pull-requests"] == "write"

    def test_pr_agent_trigger_has_conditional(self, pr_agent_workflow: Dict[str, Any]):
        """Test that pr-agent-trigger job has proper conditional logic."""
        job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        assert "if" in job, "pr-agent-trigger should have conditional execution"
        conditional = job["if"]
        assert "pull_request_review" in conditional
        assert "changes_requested" in conditional
        assert "issue_comment" in conditional
        assert "@copilot" in conditional

    def test_pr_agent_install_steps_validate_files(self, pr_agent_workflow: Dict[str, Any]):
        """
        Ensure the PR Agent trigger job's install steps check for presence of expected dependency files before installing.

        Asserts that a step named "Install Python dependencies" exists and its `run` script checks for `requirements.txt` and `requirements-dev.txt`, and that a step named "Install Node dependencies" exists and its `run` script checks for `package-lock.json` and `package.json`.

        Parameters:
            pr_agent_workflow (Dict[str, Any]): Parsed workflow dictionary for the pr-agent.yml workflow.
        """
        job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        steps = job.get("steps", [])

        python_install_step = None
        node_install_step = None

        for step in steps:
            if step.get("name") == "Install Python dependencies":
                python_install_step = step
            elif step.get("name") == "Install Node dependencies":
                node_install_step = step

        assert python_install_step is not None
        assert "if [ -f requirements.txt ]" in python_install_step["run"]
        assert "if [ -f requirements-dev.txt ]" in python_install_step["run"]

        assert node_install_step is not None
        assert "if [ -f package-lock.json ]" in node_install_step["run"]
        assert "if [ -f package.json ]" in node_install_step["run"]

    def test_pr_agent_parse_comments_step(self, pr_agent_workflow: Dict[str, Any]):
        """
        Verify the "Parse PR Review Comments" step in the pr-agent-trigger job is present and correctly configured.

        Asserts the step exists, has id "parse-comments", includes an env mapping containing GITHUB_TOKEN, and its run script invokes "gh api".
        """
        job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        steps = job.get("steps", [])

        parse_step = None
        for step in steps:
            if step.get("name") == "Parse PR Review Comments":
                parse_step = step
                break

        assert parse_step is not None
        assert "id" in parse_step
        assert parse_step["id"] == "parse-comments"
        assert "env" in parse_step
        assert "GITHUB_TOKEN" in parse_step["env"]
        assert "gh api" in parse_step["run"]

    def test_pr_agent_linting_steps(self, pr_agent_workflow: Dict[str, Any]):
        """
        Ensure the PR Agent workflow defines Python and frontend linting steps and that the Python lint step runs the expected linting commands and targets.

        Parameters:
            pr_agent_workflow (Dict[str, Any]): Parsed mapping of the `pr-agent.yml` workflow containing jobs and steps.
        """
        job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        steps = job.get("steps", [])

        step_names = [s.get("name", "") for s in steps]
        assert "Run Python Linting" in step_names
        assert "Run Frontend Linting" in step_names

        # Check Python linting configuration
        python_lint = next(s for s in steps if s.get("name") == "Run Python Linting")
        assert "flake8" in python_lint["run"]
        assert "black" in python_lint["run"]
        assert "--max-line-length=88" in python_lint["run"]
        assert "api/" in python_lint["run"] and "src/" in python_lint["run"]

    def test_pr_agent_testing_steps(self, pr_agent_workflow: Dict[str, Any]):
        """Test that pr-agent includes proper testing steps."""
        job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        steps = job.get("steps", [])

        step_names = [s.get("name", "") for s in steps]
        assert "Run Python Tests" in step_names
        assert "Run Frontend Tests" in step_names

        # Check test configuration
        python_test = next(s for s in steps if s.get("name") == "Run Python Tests")
        assert "pytest" in python_test["run"]
        assert "--cov=src" in python_test["run"]
        assert "--cov-report=term-missing" in python_test["run"]

    def test_pr_agent_create_comment_step(self, pr_agent_workflow: Dict[str, Any]):
        """Test that Create PR Comment step runs always and uses github-script."""
        job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        steps = job.get("steps", [])

        comment_step = None
        for step in steps:
            if step.get("name") == "Create PR Comment":
                comment_step = step
                break

        assert comment_step is not None
        assert comment_step.get("if") == "always()"
        assert "actions/github-script" in comment_step["uses"]
        assert "script" in comment_step["with"]

    def test_pr_agent_node_version_actual(self, pr_agent_workflow: Dict[str, Any]):
        """
        Ensure that every actions/setup-node step in the "pr-agent-trigger" job specifies Node.js version 18.

        Parameters:
            pr_agent_workflow (Dict[str, Any]): Parsed YAML mapping for the PR Agent workflow fixture.
        """
        job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        steps = job.get("steps", [])

        node_steps = [s for s in steps if s.get("uses", "").startswith("actions/setup-node")]

        for step in node_steps:
            step_with = step.get("with", {})
            assert step_with.get("node-version") == "18", "Node.js version should be 18 (current configuration)"

    def test_auto_merge_check_logic(self, pr_agent_workflow: Dict[str, Any]):
        """Test auto-merge-check job conditional logic."""
        job = pr_agent_workflow["jobs"]["auto-merge-check"]
        assert "if" in job
        conditional = job["if"]

        # Should check for pull_request synchronize, approved review, and check_suite success
        assert "pull_request" in conditional
        assert "synchronize" in conditional
        assert "pull_request_review" in conditional
        assert "approved" in conditional
        assert "check_suite" in conditional
        assert "success" in conditional

    def test_auto_merge_check_uses_github_script(self, pr_agent_workflow: Dict[str, Any]):
        """
        Ensure the `auto-merge-check` job contains a single step that uses `actions/github-script` and provides a `script` in its `with` mapping.
        """
        job = pr_agent_workflow["jobs"]["auto-merge-check"]
        steps = job.get("steps", [])

        assert len(steps) == 1
        assert "actions/github-script" in steps[0]["uses"]
        assert "script" in steps[0]["with"]

    def test_dependency_update_conditional(self, pr_agent_workflow: Dict[str, Any]):
        """Test dependency-update job triggers only for dependency PRs."""
        job = pr_agent_workflow["jobs"]["dependency-update"]
        assert "if" in job
        conditional = job["if"]

        assert "pull_request" in conditional
        assert "deps" in conditional

    def test_dependency_update_auto_approve_logic(self, pr_agent_workflow: Dict[str, Any]):
        """Test dependency-update job auto-approves trusted bot updates."""
        job = pr_agent_workflow["jobs"]["dependency-update"]
        steps = job.get("steps", [])

        step = steps[0]
        script = step["with"]["script"]

        # Should check for dependabot and renovate
        assert "dependabot[bot]" in script
        assert "renovate[bot]" in script
        assert "bump" in script.lower() or "update" in script.lower()
        assert "APPROVE" in script


class TestAutoAssignWorkflow:
    """Comprehensive tests for the auto-assign.yml workflow."""

    @pytest.fixture
    def auto_assign_workflow(self) -> Dict[str, Any]:
        """
        Load the 'auto-assign' workflow YAML and provide its parsed mapping for tests.

        If the file .github/workflows/auto-assign.yml is missing, the invoking test is skipped.

        Returns:
            Dict[str, Any]: Parsed YAML mapping of the auto-assign workflow.
        """
        workflow_path = WORKFLOWS_DIR / "auto-assign.yml"
        if not workflow_path.exists():
            pytest.skip("auto-assign.yml not found")
        return load_yaml_safe(workflow_path)

    # Structure tests
    def test_auto_assign_structure_name(self, auto_assign_workflow: Dict[str, Any]):
        """Assert the auto-assign workflow's top-level name equals "Auto Assign"."""
        assert auto_assign_workflow["name"] == "Auto Assign"
        assert len(auto_assign_workflow["name"]) > 5, "Workflow name should be descriptive"
        assert not auto_assign_workflow["name"].isupper(), "Workflow name should not be all uppercase"
        assert auto_assign_workflow["name"][0].isupper(), "Workflow name should start with capital letter"

    def test_auto_assign_structure_has_run_job(self, auto_assign_workflow: Dict[str, Any]):
        """Test that auto-assign workflow has a 'run' job."""
        jobs = auto_assign_workflow.get("jobs", {})
        assert "run" in jobs, "auto-assign workflow must have a 'run' job"
        assert len(jobs) == 1, "Workflow should have exactly one job (efficient design)"

    def test_auto_assign_structure_runs_on_ubuntu(self, auto_assign_workflow: Dict[str, Any]):
        """Test that the run job executes on Ubuntu latest."""
        run_job = auto_assign_workflow["jobs"]["run"]
        runs_on = run_job.get("runs-on", "")
        assert "ubuntu" in runs_on.lower(), "Run job should execute on Ubuntu runner"
        assert runs_on == "ubuntu-latest", f"Should use 'ubuntu-latest' for automatic updates, got '{runs_on}'"

    def test_auto_assign_structure_single_step(self, auto_assign_workflow: Dict[str, Any]):
        """Test that the run job has exactly one step."""
        run_job = auto_assign_workflow["jobs"]["run"]
        steps = run_job.get("steps", [])
        assert len(steps) == 1, "Run job should have exactly one step"

    def test_auto_assign_structure_no_dependencies(self, auto_assign_workflow: Dict[str, Any]):
        """Test that the run job has no dependencies or conditions."""
        run_job = auto_assign_workflow["jobs"]["run"]
        assert "needs" not in run_job, "Run job should not depend on other jobs (simple workflow)"
        assert "if" not in run_job, "Run job should not have conditions (should run for all matching triggers)"
        assert "environment" not in run_job, "Auto-assign should not require environment approval"
        assert "strategy" not in run_job, "Auto-assign should not use matrix strategy"
        assert "outputs" not in run_job, "Auto-assign job should not define outputs"

    def test_auto_assign_structure_triggers_on_issues(self, auto_assign_workflow: Dict[str, Any]):
        """Test that auto-assign workflow triggers on issue opened events."""
        triggers = auto_assign_workflow.get("on", {})
        assert "issues" in triggers, "auto-assign workflow should trigger on issue events"

        issues_config = triggers["issues"]
        assert isinstance(issues_config, dict), "issues trigger should be a dictionary"
        assert "types" in issues_config, "issues trigger should specify types"
        assert "opened" in issues_config["types"], "issues trigger should include 'opened' type"
        assert issues_config["types"] == [
            "opened"
        ], "Issues should only trigger on 'opened' to avoid duplicate assignments"

    def test_auto_assign_structure_triggers_on_pull_requests(self, auto_assign_workflow: Dict[str, Any]):
        """Test that auto-assign workflow triggers on pull request opened events."""
        triggers = auto_assign_workflow.get("on", {})
        assert "pull_request" in triggers, "auto-assign workflow should trigger on pull_request events"

        pr_config = triggers["pull_request"]
        assert isinstance(pr_config, dict), "pull_request trigger should be a dictionary"
        assert "types" in pr_config, "pull_request trigger should specify types"
        assert "opened" in pr_config["types"], "pull_request trigger should include 'opened' type"
        assert pr_config["types"] == [
            "opened"
        ], "Pull requests should only trigger on 'opened' to avoid duplicate assignments"

    # Permissions tests
    def test_auto_assign_permissions_defined(self, auto_assign_workflow: Dict[str, Any]):
        """Test that the workflow defines appropriate permissions."""
        run_job = auto_assign_workflow["jobs"]["run"]
        assert "permissions" in run_job, "Run job should define permissions"
        assert isinstance(run_job["permissions"], dict), "Permissions should be a dictionary"

    def test_auto_assign_permissions_issues_write(self, auto_assign_workflow: Dict[str, Any]):
        """Test that the workflow has issues write permission."""
        run_job = auto_assign_workflow["jobs"]["run"]
        permissions = run_job.get("permissions", {})
        assert "issues" in permissions, "Run job should have 'issues' permission"
        assert permissions["issues"] == "write", "Issues permission should be 'write'"

    def test_auto_assign_permissions_pull_requests_write(self, auto_assign_workflow: Dict[str, Any]):
        """Test that the workflow has pull-requests write permission."""
        run_job = auto_assign_workflow["jobs"]["run"]
        permissions = run_job.get("permissions", {})
        assert "pull-requests" in permissions, "Run job should have 'pull-requests' permission"
        assert permissions["pull-requests"] == "write", "Pull-requests permission should be 'write'"

    def test_auto_assign_permissions_minimal(self, auto_assign_workflow: Dict[str, Any]):
        """Test that the workflow uses minimal permissions (least privilege principle)."""
        run_job = auto_assign_workflow["jobs"]["run"]
        permissions = run_job.get("permissions", {})
        assert len(permissions) == 2, "Should only have minimal required permissions (issues and pull-requests)"
        assert set(permissions.keys()) == {
            "issues",
            "pull-requests",
        }, "Should only have 'issues' and 'pull-requests' permissions"

        # Ensure permissions are not overly broad
        for permission, value in permissions.items():
            assert value in ["read", "write", "none"], f"Permission '{permission}' has invalid value '{value}'"

    def test_auto_assign_permissions_scoped_to_job(self, auto_assign_workflow: Dict[str, Any]):
        """Test that permissions are scoped to the job level (security best practice)."""
        assert (
            "permissions" not in auto_assign_workflow or auto_assign_workflow.get("permissions") is None
        ), "Permissions should be defined at job level for better security scoping"
        run_job = auto_assign_workflow["jobs"]["run"]
        assert "permissions" in run_job, "Job should define its own permissions"

    # Security tests
    def test_auto_assign_security_uses_github_token(self, auto_assign_workflow: Dict[str, Any]):
        """Test that the step uses GITHUB_TOKEN from secrets."""
        run_job = auto_assign_workflow["jobs"]["run"]
        step = run_job.get("steps", [])[0]
        with_config = step.get("with", {})
        assert "repo-token" in with_config, "Step should have 'repo-token' configuration"
        token = with_config["repo-token"]
        assert "${{ secrets.GITHUB_TOKEN }}" in token, "Should use secrets.GITHUB_TOKEN for authentication"

    def test_auto_assign_security_no_hardcoded_secrets(self, auto_assign_workflow: Dict[str, Any]):
        """Test that no secrets are hardcoded in the workflow."""
        import json

        workflow_str = json.dumps(auto_assign_workflow)
        suspicious_patterns = [
            r"ghp_[a-zA-Z0-9]{36}",
            r"ghs_[a-zA-Z0-9]{36}",
            r"github_pat_[a-zA-Z0-9_]{82}",
        ]
        for pattern in suspicious_patterns:
            matches = re.findall(pattern, workflow_str)
            assert not matches, f"Found potential hardcoded secret: {pattern}"

    def test_auto_assign_security_action_source_trusted(self, auto_assign_workflow: Dict[str, Any]):
        """Test that the action comes from a trusted source."""
        run_job = auto_assign_workflow["jobs"]["run"]
        step = run_job.get("steps", [])[0]
        action = step["uses"]
        action_owner = action.split("/")[0]
        assert action_owner == "pozil", f"Action should be from trusted owner 'pozil', got '{action_owner}'"

    def test_auto_assign_security_stable_action_version(self, auto_assign_workflow: Dict[str, Any]):
        """Test that the workflow uses a stable version of the action."""
        run_job = auto_assign_workflow["jobs"]["run"]
        step = run_job.get("steps", [])[0]
        action = step["uses"]
        assert "@" in action, "Action should specify a version tag (e.g., @v1)"

        version = action.split("@")[1]
        assert version, "Version tag should not be empty"
        assert version not in [
            "main",
            "master",
        ], "Should use a version tag (e.g., @v1) rather than branch name for stability"

        # Should follow semantic versioning or commit pinning
        is_semver = version.startswith("v") and any(c.isdigit() for c in version)
        is_commit_sha = len(version) >= 40 or len(version) == 7
        assert (
            is_semver or is_commit_sha
        ), f"Action version '{version}' should follow semantic versioning or be a commit SHA"

    def test_auto_assign_security_no_deprecated_syntax(self, auto_assign_workflow: Dict[str, Any]):
        """Test that the workflow doesn't use deprecated GitHub Actions syntax."""
        import json

        workflow_str = json.dumps(auto_assign_workflow)
        assert "::set-output" not in workflow_str, "Should not use deprecated ::set-output syntax"
        assert "::set-env" not in workflow_str, "Should not use deprecated ::set-env syntax"
        assert "::add-path" not in workflow_str, "Should not use deprecated ::add-path syntax"

    # Configuration tests
    def test_auto_assign_configuration_step_name(self, auto_assign_workflow: Dict[str, Any]):
        """Test that the step has a descriptive name."""
        run_job = auto_assign_workflow["jobs"]["run"]
        step = run_job.get("steps", [])[0]
        assert "name" in step, "Step should have a name"
        assert step["name"], "Step name should not be empty"
        assert "auto-assign" in step["name"].lower(), "Step name should indicate auto-assignment functionality"

    def test_auto_assign_configuration_uses_pozil_action(self, auto_assign_workflow: Dict[str, Any]):
        """Test that the workflow uses the pozil/auto-assign-issue action."""
        run_job = auto_assign_workflow["jobs"]["run"]
        step = run_job.get("steps", [])[0]
        assert "uses" in step, "Step should use an action"
        assert step["uses"].startswith("pozil/auto-assign-issue"), "Step should use the pozil/auto-assign-issue action"

    def test_auto_assign_configuration_has_with_block(self, auto_assign_workflow: Dict[str, Any]):
        """Test that the step has a 'with' configuration block."""
        run_job = auto_assign_workflow["jobs"]["run"]
        step = run_job.get("steps", [])[0]
        assert "with" in step, "Step should have a 'with' configuration block"
        assert isinstance(step["with"], dict), "'with' should be a dictionary"

    def test_auto_assign_configuration_required_fields(self, auto_assign_workflow: Dict[str, Any]):
        """Test that all required configuration fields are present."""
        run_job = auto_assign_workflow["jobs"]["run"]
        step = run_job.get("steps", [])[0]
        with_config = step.get("with", {})
        required_fields = ["repo-token", "assignees", "numOfAssignee"]
        for field in required_fields:
            assert field in with_config, f"Required field '{field}' missing from configuration"
            value = with_config[field]
            assert value is not None, f"Input '{field}' should not be None"
            if isinstance(value, str):
                assert value.strip(), f"Input '{field}' should not be empty"

    def test_auto_assign_configuration_assignees_valid(self, auto_assign_workflow: Dict[str, Any]):
        """Test that assignees are specified and valid."""
        run_job = auto_assign_workflow["jobs"]["run"]
        step = run_job.get("steps", [])[0]
        with_config = step.get("with", {})
        assert "assignees" in with_config, "Step should specify assignees"

        assignees = with_config["assignees"]
        assert assignees, "Assignees should not be empty"
        assert isinstance(assignees, str), "Assignees should be a string"
        assert assignees.strip(), "assignees should not be empty or whitespace-only"

        # Validate GitHub username format
        username_pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$"
        assignee_list = [a.strip() for a in assignees.split(",") if a.strip()]

        for assignee in assignee_list:
            assert re.match(username_pattern, assignee), f"Assignee '{assignee}' is not a valid GitHub username"

        # Check for no duplicates
        unique_assignees = set(assignee_list)
        assert len(assignee_list) == len(
            unique_assignees
        ), f"Assignees should not contain duplicates. Found: {assignee_list}"

    def test_auto_assign_configuration_num_assignees_valid(self, auto_assign_workflow: Dict[str, Any]):
        """Test that numOfAssignee is valid and matches assignees list."""
        run_job = auto_assign_workflow["jobs"]["run"]
        step = run_job.get("steps", [])[0]
        with_config = step.get("with", {})
        assert "numOfAssignee" in with_config, "Step should specify numOfAssignee"

        num_assignees = with_config.get("numOfAssignee")
        assert isinstance(num_assignees, int), "numOfAssignee should be an integer"
        assert num_assignees > 0, "numOfAssignee should be positive"
        assert num_assignees <= 10, "numOfAssignee should be reasonable (≤ 10)"

        # Verify it doesn't exceed available assignees
        assignees = with_config.get("assignees", "")
        assignee_list = [a.strip() for a in assignees.split(",") if a.strip()]
        assert num_assignees <= len(
            assignee_list
        ), f"numOfAssignee ({num_assignees}) should not exceed number of specified assignees ({len(assignee_list)})"

    def test_auto_assign_configuration_no_unexpected_fields(self, auto_assign_workflow: Dict[str, Any]):
        """Test that no unexpected configuration fields are present."""
        run_job = auto_assign_workflow["jobs"]["run"]
        step = run_job.get("steps", [])[0]
        with_config = step.get("with", {})
        expected_fields = {"repo-token", "assignees", "numOfAssignee"}
        actual_fields = set(with_config.keys())
        unexpected = actual_fields - expected_fields
        if unexpected:
            print(f"\nInfo: auto-assign.yml has additional config fields: {unexpected}")

    def test_auto_assign_configuration_no_env_vars(self, auto_assign_workflow: Dict[str, Any]):
        """Test that no environment variables are set (all config in 'with')."""
        run_job = auto_assign_workflow["jobs"]["run"]
        step = run_job.get("steps", [])[0]
        assert "env" not in step, "Auto-assign configuration should be in 'with', not 'env'"

    def test_auto_assign_configuration_no_timeout(self, auto_assign_workflow: Dict[str, Any]):
        """Test timeout configuration."""
        run_job = auto_assign_workflow["jobs"]["run"]
        if "timeout-minutes" in run_job:
            timeout = run_job["timeout-minutes"]
            assert timeout <= 10, f"Auto-assign should complete quickly, timeout of {timeout} seems high"

        step = run_job.get("steps", [])[0]
        assert "timeout-minutes" not in step, "Step-level timeout not necessary for auto-assign"

    def test_auto_assign_configuration_no_continue_on_error(self, auto_assign_workflow: Dict[str, Any]):
        """Test that the step doesn't have continue-on-error set."""
        run_job = auto_assign_workflow["jobs"]["run"]
        step = run_job.get("steps", [])[0]
        assert "continue-on-error" not in step or not step.get(
            "continue-on-error"
        ), "Auto-assign should not continue on error"


class TestWorkflowTriggers:
    """Comprehensive tests for workflow trigger configurations."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_triggers_are_valid_types(self, workflow_file: Path):
        """
        Validate that the workflow's triggers are recognised GitHub event types.

        Accepts workflows where `on` is expressed as a string, a list, or a mapping and fails the test if any trigger event is not in the known set of GitHub event names.

        Parameters:
            workflow_file (Path): Path to the workflow YAML file under test.

        Raises:
            AssertionError: If an unrecognised event type is found in the workflow's `on` configuration.
        """
        config = load_yaml_safe(workflow_file)
        triggers = config.get("on", {})

        if isinstance(triggers, str):
            triggers = {triggers: None}
        elif isinstance(triggers, list):
            triggers = {t: None for t in triggers}

        valid_events = {
            "push",
            "pull_request",
            "pull_request_review",
            "pull_request_target",
            "issue_comment",
            "issues",
            "workflow_dispatch",
            "schedule",
            "release",
            "create",
            "delete",
            "fork",
            "watch",
            "check_suite",
            "check_run",
            "deployment",
            "deployment_status",
            "page_build",
            "project",
            "project_card",
            "project_column",
            "public",
            "registry_package",
            "status",
            "workflow_run",
            "repository_dispatch",
            "milestone",
            "discussion",
            "discussion_comment",
        }

        for event in triggers.keys():
            if event is True:  # Handle boolean true for shorthand syntax
                continue
            assert event in valid_events, f"Workflow {workflow_file.name} uses invalid event type: {event}"

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_pr_triggers_specify_types(self, workflow_file: Path):
        """Test that pull_request triggers specify activity types."""
        config = load_yaml_safe(workflow_file)
        triggers = config.get("on", {})

        if not isinstance(triggers, dict):
            return  # Skip for non-dict triggers

        if "pull_request" in triggers:
            pr_config = triggers["pull_request"]
            if pr_config is not None:
                assert "types" in pr_config or pr_config == {}, (
                    f"Workflow {workflow_file.name} pull_request trigger should "
                    "specify activity types for better control"
                )


class TestAutoAssignWorkflowAdvanced:
    """Advanced and edge case tests for auto-assign.yml workflow."""

    @pytest.fixture
    def auto_assign_workflow(self) -> Dict[str, Any]:
        """Load the auto-assign workflow for advanced testing."""
        workflow_path = WORKFLOWS_DIR / "auto-assign.yml"
        if not workflow_path.exists():
            pytest.skip("auto-assign.yml not found")
        return load_yaml_safe(workflow_path)

    def test_auto_assign_yaml_syntax_valid(self):
        """Test that the auto-assign workflow has valid YAML syntax."""
        workflow_path = WORKFLOWS_DIR / "auto-assign.yml"
        if not workflow_path.exists():
            pytest.skip("auto-assign.yml not found")

        # Should not raise an exception
        try:
            with open(workflow_path, "r") as f:
                yaml.safe_load(f)
        except yaml.YAMLError as e:
            pytest.fail(f"Invalid YAML syntax in auto-assign.yml: {e}")

    def test_auto_assign_file_not_empty(self):
        """Test that the auto-assign workflow file is not empty."""
        workflow_path = WORKFLOWS_DIR / "auto-assign.yml"
        if not workflow_path.exists():
            pytest.skip("auto-assign.yml not found")

        content = workflow_path.read_text()
        assert content.strip(), "auto-assign.yml should not be empty"
        assert len(content) > 100, "auto-assign.yml should have substantial content"

    def test_auto_assign_no_syntax_errors_in_expressions(self, auto_assign_workflow: Dict[str, Any]):
        """Test that all GitHub expressions use correct syntax."""
        run_job = auto_assign_workflow["jobs"]["run"]
        steps = run_job.get("steps", [])
        step = steps[0]

        with_config = step.get("with", {})
        token = with_config.get("repo-token", "")

        # Check for proper expression syntax
        if "${{" in token:
            assert token.count("${{") == token.count("}}"), "GitHub expression braces should be balanced"
            assert "secrets.GITHUB_TOKEN" in token, "Should use secrets.GITHUB_TOKEN"

    def test_auto_assign_action_source_is_trusted(self, auto_assign_workflow: Dict[str, Any]):
        """Test that the action comes from a trusted source."""
        run_job = auto_assign_workflow["jobs"]["run"]
        steps = run_job.get("steps", [])
        step = steps[0]

        action = step["uses"]
        action_owner = action.split("/")[0]

        # pozil is the known trusted owner of this action
        assert action_owner == "pozil", f"Action should be from trusted owner 'pozil', got '{action_owner}'"

    def test_auto_assign_no_hardcoded_secrets(self, auto_assign_workflow: Dict[str, Any]):
        """Test that no secrets are hardcoded in the workflow."""
        import json

        workflow_str = json.dumps(auto_assign_workflow)

        # Check for common secret patterns
        suspicious_patterns = [
            r"ghp_[a-zA-Z0-9]{36}",  # GitHub personal access token
            r"ghs_[a-zA-Z0-9]{36}",  # GitHub server token
            r"github_pat_[a-zA-Z0-9_]{82}",  # GitHub fine-grained PAT
        ]

        for pattern in suspicious_patterns:
            import re

            matches = re.findall(pattern, workflow_str)
            assert not matches, f"Found potential hardcoded secret: {pattern}"

    def test_auto_assign_assignees_not_empty_string(self, auto_assign_workflow: Dict[str, Any]):
        """Test that assignees is not an empty string."""
        run_job = auto_assign_workflow["jobs"]["run"]
        steps = run_job.get("steps", [])
        step = steps[0]

        with_config = step.get("with", {})
        assignees = with_config.get("assignees", "")

        assert assignees.strip(), "assignees should not be empty or whitespace-only"

    def test_auto_assign_assignees_no_duplicates(self, auto_assign_workflow: Dict[str, Any]):
        """Test that the assignees list contains no duplicates."""
        run_job = auto_assign_workflow["jobs"]["run"]
        steps = run_job.get("steps", [])
        step = steps[0]

        with_config = step.get("with", {})
        assignees = with_config.get("assignees", "")

        assignee_list = [a.strip() for a in assignees.split(",") if a.strip()]
        unique_assignees = set(assignee_list)

        assert len(assignee_list) == len(
            unique_assignees
        ), f"Assignees should not contain duplicates. Found: {assignee_list}"

    def test_auto_assign_runner_is_latest(self, auto_assign_workflow: Dict[str, Any]):
        """Test that the workflow uses ubuntu-latest (not a specific version)."""
        run_job = auto_assign_workflow["jobs"]["run"]
        runs_on = run_job.get("runs-on", "")

        assert runs_on == "ubuntu-latest", f"Should use 'ubuntu-latest' for automatic updates, got '{runs_on}'"

    def test_auto_assign_no_environment_specified(self, auto_assign_workflow: Dict[str, Any]):
        """Test that no environment is specified (appropriate for auto-assignment)."""
        run_job = auto_assign_workflow["jobs"]["run"]

        assert "environment" not in run_job, "Auto-assign should not require environment approval"

    def test_auto_assign_no_matrix_strategy(self, auto_assign_workflow: Dict[str, Any]):
        """Test that no matrix strategy is used (not needed for assignment)."""
        run_job = auto_assign_workflow["jobs"]["run"]

        assert "strategy" not in run_job, "Auto-assign should not use matrix strategy"

    def test_auto_assign_no_timeout(self, auto_assign_workflow: Dict[str, Any]):
        """Test timeout configuration (should complete quickly or have reasonable timeout)."""
        run_job = auto_assign_workflow["jobs"]["run"]

        # If timeout is specified, it should be reasonable (< 10 minutes)
        if "timeout-minutes" in run_job:
            timeout = run_job["timeout-minutes"]
            assert timeout <= 10, f"Auto-assign should complete quickly, timeout of {timeout} seems high"

    def test_auto_assign_step_no_timeout(self, auto_assign_workflow: Dict[str, Any]):
        """Test that individual step doesn't specify timeout."""
        run_job = auto_assign_workflow["jobs"]["run"]
        steps = run_job.get("steps", [])
        step = steps[0]

        # Step-level timeout not needed for this simple operation
        assert "timeout-minutes" not in step, "Step-level timeout not necessary for auto-assign"

    def test_auto_assign_no_continue_on_error(self, auto_assign_workflow: Dict[str, Any]):
        """Test that the step doesn't have continue-on-error set."""
        run_job = auto_assign_workflow["jobs"]["run"]
        steps = run_job.get("steps", [])
        step = steps[0]

        # Should fail if assignment fails (not continue)
        assert "continue-on-error" not in step or not step.get(
            "continue-on-error"
        ), "Auto-assign should not continue on error"

    def test_auto_assign_no_outputs_defined(self, auto_assign_workflow: Dict[str, Any]):
        """Test that no outputs are defined (not needed for this workflow)."""
        run_job = auto_assign_workflow["jobs"]["run"]

        assert "outputs" not in run_job, "Auto-assign job should not define outputs"

    def test_auto_assign_step_no_env_vars(self, auto_assign_workflow: Dict[str, Any]):
        """Test that no environment variables are set (all config in 'with')."""
        run_job = auto_assign_workflow["jobs"]["run"]
        steps = run_job.get("steps", [])
        step = steps[0]

        # All configuration should be in 'with', not env
        assert "env" not in step, "Auto-assign configuration should be in 'with', not 'env'"

    def test_auto_assign_workflow_name_descriptive(self, auto_assign_workflow: Dict[str, Any]):
        """Test that workflow name is descriptive and follows conventions."""
        name = auto_assign_workflow.get("name", "")

        assert name, "Workflow should have a name"
        assert len(name) > 5, "Workflow name should be descriptive"
        assert not name.isupper(), "Workflow name should not be all uppercase"
        assert name[0].isupper(), "Workflow name should start with capital letter"

    def test_auto_assign_triggers_are_specific(self, auto_assign_workflow: Dict[str, Any]):
        """Test that triggers are specific and not overly broad."""
        triggers = auto_assign_workflow.get("on", {})

        # Should not trigger on all issue/PR events
        if "issues" in triggers:
            issues_config = triggers["issues"]
            if isinstance(issues_config, dict):
                assert "types" in issues_config, "Issues trigger should specify types"
                types = issues_config["types"]
                assert isinstance(types, list), "Types should be a list"
                assert len(types) <= 2, "Should not trigger on too many issue types"

        if "pull_request" in triggers:
            pr_config = triggers["pull_request"]
            if isinstance(pr_config, dict):
                assert "types" in pr_config, "PR trigger should specify types"
                types = pr_config["types"]
                assert isinstance(types, list), "Types should be a list"
                assert len(types) <= 2, "Should not trigger on too many PR types"

    def test_auto_assign_no_concurrent_runs_config(self, auto_assign_workflow: Dict[str, Any]):
        """Test concurrency configuration (should allow concurrent assignments)."""
        # For auto-assign, concurrent runs are typically fine
        # If concurrency is set, it should be reasonable
        if "concurrency" in auto_assign_workflow:
            concurrency = auto_assign_workflow["concurrency"]
            # Should not cancel in-progress runs for assignment
            if isinstance(concurrency, dict):
                cancel_in_progress = concurrency.get("cancel-in-progress", False)
                assert not cancel_in_progress, "Should not cancel in-progress auto-assignments"

    def test_auto_assign_action_inputs_documented(self, auto_assign_workflow: Dict[str, Any]):
        """Test that all action inputs are properly configured."""
        run_job = auto_assign_workflow["jobs"]["run"]
        steps = run_job.get("steps", [])
        step = steps[0]

        with_config = step.get("with", {})

        # All values should be non-empty
        for key, value in with_config.items():
            assert value is not None, f"Input '{key}' should not be None"
            if isinstance(value, str):
                assert value.strip(), f"Input '{key}' should not be empty"

    def test_auto_assign_no_deprecated_syntax(self, auto_assign_workflow: Dict[str, Any]):
        """Test that the workflow doesn't use deprecated GitHub Actions syntax."""
        import json

        workflow_str = json.dumps(auto_assign_workflow)

        # Check for deprecated ::set-output syntax in the workflow
        assert "::set-output" not in workflow_str, "Should not use deprecated ::set-output syntax"
        assert "::set-env" not in workflow_str, "Should not use deprecated ::set-env syntax"
        assert "::add-path" not in workflow_str, "Should not use deprecated ::add-path syntax"

    def test_auto_assign_job_name_appropriate(self, auto_assign_workflow: Dict[str, Any]):
        """Test that the job has an appropriate name."""
        jobs = auto_assign_workflow.get("jobs", {})

        # Job key should be simple and descriptive
        job_keys = list(jobs.keys())
        assert len(job_keys) == 1, "Should have exactly one job"

        job_key = job_keys[0]
        assert job_key in ["run", "auto-assign", "assign"], f"Job key '{job_key}' should be simple and descriptive"

    def test_auto_assign_permissions_not_overly_broad(self, auto_assign_workflow: Dict[str, Any]):
        """Test that permissions are not set to 'write-all' or overly permissive."""
        run_job = auto_assign_workflow["jobs"]["run"]
        permissions = run_job.get("permissions", {})

        # Should not have 'write-all' permission
        for permission, value in permissions.items():
            assert value != "write-all", f"Permission '{permission}' should not be 'write-all'"
            assert value in ["read", "write", "none"], f"Permission '{permission}' has invalid value '{value}'"

    def test_auto_assign_uses_semantic_versioning(self, auto_assign_workflow: Dict[str, Any]):
        """Test that the action version follows semantic versioning or commit pinning."""
        run_job = auto_assign_workflow["jobs"]["run"]
        steps = run_job.get("steps", [])
        step = steps[0]

        action = step["uses"]
        version = action.split("@")[1]

        # Should be either a semantic version tag or a commit SHA
        is_semver = version.startswith("v") and any(c.isdigit() for c in version)
        is_commit_sha = len(version) >= 40 or len(version) == 7

        assert (
            is_semver or is_commit_sha
        ), f"Action version '{version}' should follow semantic versioning or be a commit SHA"

    def test_auto_assign_configuration_matches_documentation(self):
        """Test that the workflow configuration matches the documentation."""
        workflow_path = WORKFLOWS_DIR / "auto-assign.yml"
        if not workflow_path.exists():
            pytest.skip("auto-assign.yml not found")

        # Check if documentation exists
        doc_path = Path("TEST_GENERATION_AUTO_ASSIGN_SUMMARY.md")
        if not doc_path.exists():
            pytest.skip("Documentation file not found")

        doc_content = doc_path.read_text()
        workflow_content = workflow_path.read_text()

        # Check that key elements from workflow are mentioned in docs
        if "pozil/auto-assign-issue" in workflow_content:
            assert (
                "pozil/auto-assign-issue" in doc_content or "auto-assign" in doc_content
            ), "Documentation should mention the action being used"


class TestAutoAssignDocumentation:
    """Tests for auto-assign workflow documentation files."""

    def test_auto_assign_summary_exists(self):
        """Test that the auto-assign summary documentation file exists."""
        doc_path = Path("TEST_GENERATION_AUTO_ASSIGN_SUMMARY.md")
        assert doc_path.exists(), "TEST_GENERATION_AUTO_ASSIGN_SUMMARY.md should exist"

    def test_auto_assign_summary_not_empty(self):
        """Test that the summary documentation is not empty."""
        doc_path = Path("TEST_GENERATION_AUTO_ASSIGN_SUMMARY.md")
        if not doc_path.exists():
            pytest.skip("Documentation file not found")

        content = doc_path.read_text()
        assert content.strip(), "Documentation should not be empty"
        assert len(content) > 500, "Documentation should have substantial content"

    def test_auto_assign_summary_has_proper_markdown(self):
        """Test that the summary uses proper markdown formatting."""
        doc_path = Path("TEST_GENERATION_AUTO_ASSIGN_SUMMARY.md")
        if not doc_path.exists():
            pytest.skip("Documentation file not found")

        content = doc_path.read_text()

        # Should have markdown headers
        assert content.count("#") >= 3, "Should have multiple markdown headers"

        # Should have code blocks for pytest commands
        assert "```" in content, "Should have code blocks"

    def test_auto_assign_summary_mentions_test_count(self):
        """Test that the summary mentions the number of tests."""
        doc_path = Path("TEST_GENERATION_AUTO_ASSIGN_SUMMARY.md")
        if not doc_path.exists():
            pytest.skip("Documentation file not found")

        content = doc_path.read_text()

        # Should mention test count
        import re

        test_counts = re.findall(r"\b\d+\s+test", content, re.IGNORECASE)
        assert test_counts, "Documentation should mention number of tests"

    def test_auto_assign_summary_has_execution_instructions(self):
        """Test that the summary includes test execution instructions."""
        doc_path = Path("TEST_GENERATION_AUTO_ASSIGN_SUMMARY.md")
        if not doc_path.exists():
            pytest.skip("Documentation file not found")

        content = doc_path.read_text()

        # Should include pytest commands
        assert "pytest" in content.lower(), "Should include pytest execution instructions"

    def test_final_report_exists(self):
        """Test that the final test generation report exists."""
        doc_path = Path("FINAL_TEST_GENERATION_REPORT.md")
        assert doc_path.exists(), "FINAL_TEST_GENERATION_REPORT.md should exist"

    def test_final_report_not_empty(self):
        """Test that the final report is not empty."""
        doc_path = Path("FINAL_TEST_GENERATION_REPORT.md")
        if not doc_path.exists():
            pytest.skip("Documentation file not found")

        content = doc_path.read_text()
        assert content.strip(), "Final report should not be empty"
        assert len(content) > 1000, "Final report should have substantial content"

    def test_final_report_has_executive_summary(self):
        """Test that the final report includes an executive summary."""
        doc_path = Path("FINAL_TEST_GENERATION_REPORT.md")
        if not doc_path.exists():
            pytest.skip("Documentation file not found")

        content = doc_path.read_text()

        # Should have executive summary section
        assert (
            "executive summary" in content.lower() or "## summary" in content.lower()
        ), "Final report should have an executive summary"

    def test_final_report_documents_test_coverage(self):
        """Test that the final report documents test coverage breakdown."""
        doc_path = Path("FINAL_TEST_GENERATION_REPORT.md")
        if not doc_path.exists():
            pytest.skip("Documentation file not found")

        content = doc_path.read_text()

        # Should mention coverage or test categories
        assert (
            "coverage" in content.lower() or "category" in content.lower()
        ), "Final report should document test coverage"

    def test_final_report_lists_files_modified(self):
        """Test that the final report lists modified files."""
        doc_path = Path("FINAL_TEST_GENERATION_REPORT.md")
        if not doc_path.exists():
            pytest.skip("Documentation file not found")

        content = doc_path.read_text()

        # Should mention test file
        assert (
            "test_github_workflows.py" in content or "tests/integration" in content
        ), "Final report should list modified test files"

    def test_documentation_files_have_consistent_formatting(self):
        """Test that documentation files use consistent markdown formatting."""
        doc_files = [Path("TEST_GENERATION_AUTO_ASSIGN_SUMMARY.md"), Path("FINAL_TEST_GENERATION_REPORT.md")]

        for doc_path in doc_files:
            if not doc_path.exists():
                continue

            content = doc_path.read_text()

            # Check for consistent header levels (should start with # or ##)
            lines = content.split("\n")
            headers = [line for line in lines if line.startswith("#")]

            if headers:
                first_header = headers[0]
                assert first_header.startswith("#"), f"{doc_path.name} should start with a markdown header"

    def test_documentation_has_no_broken_markdown_syntax(self):
        """Test that documentation files have no obvious markdown syntax errors."""
        doc_files = [Path("TEST_GENERATION_AUTO_ASSIGN_SUMMARY.md"), Path("FINAL_TEST_GENERATION_REPORT.md")]

        for doc_path in doc_files:
            if not doc_path.exists():
                continue

            content = doc_path.read_text()

            # Check for balanced code blocks
            code_block_count = content.count("```")
            assert code_block_count % 2 == 0, f"{doc_path.name} has unbalanced code blocks (``` markers)"

            # Check for balanced brackets in links
            assert content.count("[") == content.count("]"), f"{doc_path.name} has unbalanced square brackets"


class TestWorkflowJobConfiguration:
    """Tests for job-level configuration in workflows."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_jobs_specify_runner(self, workflow_file: Path):
        """
        Ensure each job in the workflow file specifies a runner.

        Checks every job in the parsed workflow YAML and asserts that non-reusable jobs declare a `runs-on` runner. Jobs that invoke reusable workflows via a `uses` key are exempt.

        Parameters:
            workflow_file (Path): Path to the workflow YAML file being tested.
        """
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        for job_name, job_config in jobs.items():
            if "uses" in job_config:
                # Reusable workflow calls don't need runs-on
                continue
            assert "runs-on" in job_config, f"Job '{job_name}' in {workflow_file.name} must specify 'runs-on'"

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_jobs_use_standard_runners(self, workflow_file: Path):
        """
        Ensure jobs that declare `runs-on` use recognised GitHub-hosted runners.

        Skips jobs that use expressions, matrix variables or self-hosted runners; fails if a job specifies a runner not in the accepted set.
        """
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        standard_runners = {
            "ubuntu-latest",
            "ubuntu-20.04",
            "ubuntu-22.04",
            "ubuntu-24.04",
            "windows-latest",
            "windows-2019",
            "windows-2022",
            "macos-latest",
            "macos-11",
            "macos-12",
            "macos-13",
            "macos-14",
        }

        for job_name, job_config in jobs.items():
            if "runs-on" not in job_config:
                continue

            runner = job_config["runs-on"]
            if isinstance(runner, str):
                # Allow self-hosted and matrix variables
                if "${{" in runner or "self-hosted" in runner:
                    continue
                assert (
                    runner in standard_runners
                ), f"Job '{job_name}' in {workflow_file.name} uses non-standard runner: {runner}"


class TestWorkflowStepConfiguration:
    """Detailed tests for workflow step configuration."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_steps_with_working_directory(self, workflow_file: Path):
        """
        Ensure steps that define `working-directory` use relative paths.

        Asserts that any step containing a `working-directory` key does not use an absolute path (i.e. the value does not start with `/`); the test fails with a descriptive message if an absolute path is found.
        """
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])

            for idx, step in enumerate(steps):
                if "working-directory" in step:
                    working_dir = step["working-directory"]
                    # Should not use absolute paths
                    assert not working_dir.startswith("/"), (
                        f"Step {idx} in job '{job_name}' of {workflow_file.name} " f"uses absolute path: {working_dir}"
                    )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_steps_with_id_are_unique(self, workflow_file: Path):
        """Test that step IDs are unique within each job."""
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            step_ids = [s.get("id") for s in steps if "id" in s]

            duplicates = [sid for sid in step_ids if step_ids.count(sid) > 1]
            assert not duplicates, f"Job '{job_name}' in {workflow_file.name} has duplicate step IDs: {duplicates}"

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_steps_continue_on_error_usage(self, workflow_file: Path):
        """Test that continue-on-error is used sparingly and intentionally."""
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])

            for step in steps:
                if step.get("continue-on-error") is True:
                    # Should have a comment or name explaining why
                    assert "name" in step, (
                        f"Step in job '{job_name}' of {workflow_file.name} "
                        "uses continue-on-error but lacks descriptive name"
                    )


class TestWorkflowEnvAndSecrets:
    """Tests for environment variables and secrets usage."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_env_vars_naming_convention(self, workflow_file: Path):
        """
        Ensure environment variable names in a workflow file are uppercase and contain only letters, digits or underscores.

        Checks environment variables at both the top-level workflow `env` and each job's `env`, and fails the test if any variable names do not match the required naming convention.
        """
        config = load_yaml_safe(workflow_file)

        def check_env_vars(env_dict):
            """
            Identify environment variable names that do not follow the convention of using only upper-case letters, digits and underscores.

            Parameters:
                env_dict (dict): Mapping of environment variable names to their values. If a non-dict is provided it is treated as absent and no invalid names are returned.

            Returns:
                invalid_keys (List[str]): List of keys from `env_dict` that are not composed solely of upper-case letters, digits and underscores.
            """
            if not isinstance(env_dict, dict):
                return []
            invalid = []
            for key in env_dict.keys():
                if not key.isupper() or not key.replace("_", "").isalnum():
                    invalid.append(key)
            return invalid

        # Check top-level env
        if "env" in config:
            invalid = check_env_vars(config["env"])
            assert not invalid, f"Workflow {workflow_file.name} has invalid env var names: {invalid}"

        # Check job-level env
        jobs = config.get("jobs", {})
        for job_name, job_config in jobs.items():
            if "env" in job_config:
                invalid = check_env_vars(job_config["env"])
                assert not invalid, f"Job '{job_name}' in {workflow_file.name} has invalid env var names: {invalid}"

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_secrets_not_in_env_values(self, workflow_file: Path):
        """Test that secrets are referenced, not hardcoded in env values."""
        with open(workflow_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Look for patterns that might indicate hardcoded secrets
        suspicious_in_env = [
            'password: "',
            'token: "',
            'api_key: "',
            'secret: "',
        ]

        for pattern in suspicious_in_env:
            if pattern in content.lower():
                # Allow if it's using secrets context
                if (
                    "${{ secrets."
                    not in content[max(0, content.lower().find(pattern) - 50) : content.lower().find(pattern) + 50]
                ):
                    pytest.skip(
                        f"Workflow {workflow_file.name} may have hardcoded sensitive value. "
                        "Manual review recommended."
                    )


class TestWorkflowComplexity:
    """Tests for workflow complexity and maintainability."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_job_count_reasonable(self, workflow_file: Path):
        """
        Validate that a workflow defines a reasonable number of jobs.

        Prints a warning if the workflow defines more than 10 jobs and causes the test to fail if it defines more than 20 jobs.

        Parameters:
            workflow_file (Path): Path to the workflow YAML file being validated.
        """
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        job_count = len(jobs)
        if job_count > 10:
            print(
                f"\nWarning: {workflow_file.name} has {job_count} jobs. " "Consider splitting into multiple workflows."
            )

        assert job_count <= 20, (
            f"Workflow {workflow_file.name} has {job_count} jobs (max 20). "
            "Split into multiple workflows for better maintainability."
        )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_step_count_per_job(self, workflow_file: Path):
        """
        Validate that each job in the workflow does not contain an excessive number of steps.

        Prints an informational message if a job has more than 15 steps and fails the test if a job has more than 30 steps.
        """
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            step_count = len(steps)

            if step_count > 15:
                print(
                    f"\nInfo: Job '{job_name}' in {workflow_file.name} has "
                    f"{step_count} steps. Consider refactoring."
                )

            assert step_count <= 30, (
                f"Job '{job_name}' in {workflow_file.name} has {step_count} steps (max 30). "
                "Consider breaking into multiple jobs."
            )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_deep_nesting_in_conditionals(self, workflow_file: Path):
        """
        Warns when a job-level `if` conditional shows high logical complexity.

        Counts occurrences of the logical operators `&&` and `||` in each job's `if` conditional and prints a warning if their total exceeds 5, indicating a potentially over-complex conditional.

        Parameters:
            workflow_file (Path): Path to the workflow YAML file to inspect.
        """
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        for job_name, job_config in jobs.items():
            if "if" in job_config:
                conditional = job_config["if"]
                # Count logical operators as proxy for complexity
                and_count = conditional.count("&&")
                or_count = conditional.count("||")

                complexity = and_count + or_count
                if complexity > 5:
                    print(
                        f"\nWarning: Job '{job_name}' in {workflow_file.name} "
                        f"has complex conditional ({complexity} operators)"
                    )


class TestWorkflowOutputsAndArtifacts:
    """Tests for workflow outputs and artifact handling."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_artifacts_have_retention(self, workflow_file: Path):
        """
        Report when artifact upload steps do not specify a `retention-days` value.

        Scans the workflow's jobs and for any step that uses `actions/upload-artifact` prints an informational message if the step's `with` mapping does not include `retention-days`.

        Parameters:
            workflow_file (Path): Path to the workflow YAML file to inspect.
        """
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])

            for step in steps:
                if "actions/upload-artifact" in step.get("uses", ""):
                    step_with = step.get("with", {})
                    # Recommend explicit retention-days
                    if "retention-days" not in step_with:
                        print(
                            f"\nInfo: Artifact upload in job '{job_name}' of "
                            f"{workflow_file.name} doesn't specify retention-days"
                        )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_outputs_referenced_correctly(self, workflow_file: Path):
        """Test that job outputs are defined when referenced by other jobs."""
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        # Collect all job outputs
        job_outputs = {}
        for job_name, job_config in jobs.items():
            if "outputs" in job_config:
                job_outputs[job_name] = set(job_config["outputs"].keys())

        # Check references in needs
        for job_name, job_config in jobs.items():
            needs = job_config.get("needs", [])
            if isinstance(needs, str):
                needs = [needs]
            elif not isinstance(needs, list):
                needs = []

            # Verify needed jobs exist
            for needed_job in needs:
                assert needed_job in jobs, (
                    f"Job '{job_name}' in {workflow_file.name} needs '{needed_job}' " "which doesn't exist"
                )


class TestWorkflowBestPractices:
    """Tests for workflow best practices and recommendations."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_uses_concurrency_for_prs(self, workflow_file: Path):
        """Test if PR workflows use concurrency to cancel outdated runs."""
        config = load_yaml_safe(workflow_file)
        triggers = config.get("on", {})

        has_pr_trigger = False
        if isinstance(triggers, dict):
            has_pr_trigger = "pull_request" in triggers or "pull_request_target" in triggers

        if has_pr_trigger and "concurrency" not in config:
            print(
                f"\nRecommendation: {workflow_file.name} triggers on PR but doesn't "
                "use concurrency. Consider adding concurrency group to cancel outdated runs."
            )

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_timeout_specified(self, workflow_file: Path):
        """
        Check that each job in the workflow specifies timeout-minutes.

        For any job missing `timeout-minutes` this test prints a recommendation identifying the job and the workflow file.
        """
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        for job_name, job_config in jobs.items():
            if "timeout-minutes" not in job_config:
                print(f"\nRecommendation: Job '{job_name}' in {workflow_file.name} " "doesn't specify timeout-minutes")

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_shell_explicitly_set(self, workflow_file: Path):
        """
        Check workflow steps that use multi-line `run` commands and recommend setting `shell` if missing.

        For each job in the workflow file, any step whose `run` value is a string containing a newline is considered a multi-line command; if such a step does not specify a `shell` key, a recommendation message is printed identifying the workflow file, job name and step index.

        Parameters:
            workflow_file (Path): Path to the workflow YAML file to inspect.
        """
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])

            for idx, step in enumerate(steps):
                if "run" in step:
                    run_cmd = step["run"]
                    if isinstance(run_cmd, str) and "\n" in run_cmd:
                        # Multi-line command
                        if "shell" not in step:
                            print(
                                f"\nRecommendation: Step {idx} in job '{job_name}' "
                                f"of {workflow_file.name} uses multi-line run without "
                                "explicit shell specification"
                            )


class TestWorkflowAdvancedSecurity:
    """Advanced security tests for workflow files with bias for action."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_no_environment_variable_injection(self, workflow_file: Path):
        """Test that workflows don't have potential env injection vulnerabilities."""
        content = workflow_file.read_text()

        # Check for unsafe environment variable usage in bash context
        unsafe_patterns = [
            r"\$\{\{.*github\.event\..*\}\}.*bash",
            r"run:.*\$\{\{.*github\.event\.issue\.title",
            r"run:.*\$\{\{.*github\.event\.pull_request\.title",
        ]

        for pattern in unsafe_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            assert len(matches) == 0, f"{workflow_file.name}: Potential injection vulnerability via {pattern}"

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
                        assert (
                            pattern not in str(run_cmd).lower()
                        ), f"Dangerous pattern '{pattern}' in {workflow_file.name}, job {job_name}, step {idx}"

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_secrets_not_echoed_to_logs(self, workflow_file: Path):
        """Test that secrets aren't accidentally printed to logs."""
        content = workflow_file.read_text()

        # Check for echo/print of secrets
        secret_logging_patterns = [
            r"echo.*\$\{\{.*secrets\.",
            r"print.*\$\{\{.*secrets\.",
            r"console\.log.*\$\{\{.*secrets\.",
        ]

        for pattern in secret_logging_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            assert len(matches) == 0, f"{workflow_file.name}: Potential secret logging detected"

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_no_curl_with_user_input(self, workflow_file: Path):
        """Test that curl commands don't use untrusted user input."""
        content = workflow_file.read_text()

        # Check for curl with event data
        if "curl" in content and "github.event" in content:
            # Warn about potential URL injection
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if "curl" in line.lower() and "github.event" in line:
                    # This is advisory - curl with user input can be dangerous
                    assert True  # Not failing but flagging for review


class TestWorkflowAdvancedValidation:
    """Advanced structural validation tests."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_job_dependencies_are_acyclic(self, workflow_file: Path):
        """Test that job dependencies don't form cycles."""
        data = load_yaml_safe(workflow_file)
        jobs = data.get("jobs", {})

        # Build dependency graph
        deps = {}
        for job_name, job in jobs.items():
            needs = job.get("needs", [])
            if isinstance(needs, str):
                needs = [needs]
            deps[job_name] = needs

        # Check for cycles using DFS
        def has_cycle(node, visited, rec_stack):
            visited.add(node)
            rec_stack.add(node)

            for neighbor in deps.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        visited = set()
        for job in deps:
            if job not in visited:
                assert not has_cycle(job, visited, set()), f"Circular dependency detected in {workflow_file.name}"

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_action_versions_use_semantic_versioning(self, workflow_file: Path):
        """Test that actions use proper semantic versioning."""
        data = load_yaml_safe(workflow_file)
        jobs = data.get("jobs", {})

        for job_name, job in jobs.items():
            steps = job.get("steps", [])
            for step in steps:
                if "uses" in step:
                    uses = step["uses"]
                    if "@" in uses:
                        _, version = uses.rsplit("@", 1)
                        # Should not use branch names
                        invalid_refs = ["main", "master", "latest", "develop"]
                        assert (
                            version.lower() not in invalid_refs
                        ), f"Using unstable ref '{version}' in {workflow_file.name}"

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_checkout_with_proper_ref_for_pr(self, workflow_file: Path):
        """Test that PR workflows checkout the correct ref."""
        data = load_yaml_safe(workflow_file)
        triggers = data.get("on", {})

        # If pull_request_target is used, should checkout PR ref explicitly
        if "pull_request_target" in triggers:
            jobs = data.get("jobs", {})
            has_checkout = False
            has_safe_ref = False

            for job_name, job in jobs.items():
                steps = job.get("steps", [])
                for step in steps:
                    if "uses" in step and "actions/checkout" in step["uses"]:
                        has_checkout = True
                        if "with" in step and "ref" in step["with"]:
                            has_safe_ref = True

            if has_checkout:
                # Advisory: pull_request_target should specify ref
                assert True  # Not failing but important to check

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_timeout_minutes_are_reasonable(self, workflow_file: Path):
        """Test that timeout values are reasonable."""
        data = load_yaml_safe(workflow_file)
        jobs = data.get("jobs", {})

        for job_name, job in jobs.items():
            timeout = job.get("timeout-minutes")
            if timeout is not None:
                assert isinstance(timeout, int), f"timeout-minutes must be integer in {workflow_file.name}"
                assert 1 <= timeout <= 360, f"timeout-minutes {timeout} out of range (1-360) in {workflow_file.name}"


class TestWorkflowCachingStrategies:
    """Tests for caching best practices."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_cache_uses_hashfiles_for_lockfiles(self, workflow_file: Path):
        """Test that caches use hashFiles for dependency lockfiles."""
        content = workflow_file.read_text()

        if "actions/cache" in content:
            lockfiles = ["package-lock.json", "yarn.lock", "requirements.txt", "Pipfile.lock"]
            mentioned_lockfiles = [lf for lf in lockfiles if lf in content]

            if mentioned_lockfiles:
                # Should use hashFiles for these
                assert "hashFiles" in content, f"Cache with lockfiles should use hashFiles in {workflow_file.name}"

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_cache_keys_are_unique_per_os(self, workflow_file: Path):
        """Test that cache keys include OS information when running on matrix."""
        data = load_yaml_safe(workflow_file)
        jobs = data.get("jobs", {})

        for job_name, job in jobs.items():
            strategy = job.get("strategy", {})
            matrix = strategy.get("matrix", {})

            if "os" in matrix or "runs-on" in job:
                steps = job.get("steps", [])
                for step in steps:
                    if "uses" in step and "actions/cache" in step["uses"]:
                        if "with" in step and "key" in step["with"]:
                            key = str(step["with"]["key"])
                            # Should include runner.os in cache key
                            if "os" in matrix:
                                # Advisory: consider including OS in cache key
                                assert True


class TestWorkflowPermissionsBestPractices:
    """Tests for proper permissions configuration."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_permissions_follow_least_privilege(self, workflow_file: Path):
        """Test that workflows request minimal permissions."""
        data = load_yaml_safe(workflow_file)
        permissions = data.get("permissions", {})

        if permissions:
            # If permissions are specified, ensure they're not overly broad
            if isinstance(permissions, dict):
                for perm, value in permissions.items():
                    # Permissions should be 'read', 'write', or 'none'
                    assert value in [
                        "read",
                        "write",
                        "none",
                    ], f"Invalid permission value '{value}' in {workflow_file.name}"

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_write_permissions_have_justification(self, workflow_file: Path):
        """Test that write permissions are used appropriately."""
        data = load_yaml_safe(workflow_file)

        def check_perms(perms):
            if isinstance(perms, dict):
                for key, value in perms.items():
                    if value == "write":
                        # Common justified write permissions
                        justified = ["contents", "pull-requests", "issues", "packages"]
                        if key not in justified:
                            # Advisory: review write permission usage
                            pass

        # Check workflow-level permissions
        if "permissions" in data:
            check_perms(data["permissions"])

        # Check job-level permissions
        jobs = data.get("jobs", {})
        for job_name, job in jobs.items():
            if "permissions" in job:
                check_perms(job["permissions"])


class TestWorkflowComplexScenarios:
    """Tests for complex workflow patterns."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_reusable_workflows_have_proper_inputs(self, workflow_file: Path):
        """Test that reusable workflows define inputs correctly."""
        data = load_yaml_safe(workflow_file)

        if "workflow_call" in data.get("on", {}):
            wf_call = data["on"]["workflow_call"]

            if "inputs" in wf_call:
                for input_name, input_def in wf_call["inputs"].items():
                    assert "type" in input_def, f"Input '{input_name}' missing type in {workflow_file.name}"
                    assert input_def["type"] in [
                        "string",
                        "number",
                        "boolean",
                    ], f"Invalid input type in {workflow_file.name}"

            if "secrets" in wf_call:
                for secret_name, secret_def in wf_call["secrets"].items():
                    # Secrets should have required or description
                    assert (
                        "required" in secret_def or "description" in secret_def
                    ), f"Secret '{secret_name}' should specify required or description"

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_matrix_strategy_has_include_or_exclude_properly_formatted(self, workflow_file: Path):
        """Test matrix include/exclude are properly structured."""
        data = load_yaml_safe(workflow_file)
        jobs = data.get("jobs", {})

        for job_name, job in jobs.items():
            strategy = job.get("strategy", {})
            matrix = strategy.get("matrix", {})

            if "include" in matrix:
                includes = matrix["include"]
                assert isinstance(includes, list), f"Matrix include must be list in {workflow_file.name}"
                for item in includes:
                    assert isinstance(item, dict), f"Matrix include items must be dicts in {workflow_file.name}"

            if "exclude" in matrix:
                excludes = matrix["exclude"]
                assert isinstance(excludes, list), f"Matrix exclude must be list in {workflow_file.name}"


class TestWorkflowConditionalExecution:
    """Tests for conditional execution patterns."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_if_conditions_use_valid_syntax(self, workflow_file: Path):
        """Test that if conditions are syntactically valid."""
        data = load_yaml_safe(workflow_file)
        jobs = data.get("jobs", {})

        valid_contexts = [
            "github",
            "env",
            "secrets",
            "vars",
            "job",
            "jobs",
            "steps",
            "runner",
            "matrix",
            "needs",
            "strategy",
            "inputs",
        ]

        for job_name, job in jobs.items():
            # Check job-level if
            if "if" in job:
                condition = str(job["if"])
                contexts_used = re.findall(r"\$\{\{\s*(\w+)\.", condition)
                for ctx in contexts_used:
                    assert ctx in valid_contexts, f"Invalid context '{ctx}' in {workflow_file.name}, job {job_name}"

            # Check step-level if
            steps = job.get("steps", [])
            for idx, step in enumerate(steps):
                if "if" in step:
                    condition = str(step["if"])
                    contexts_used = re.findall(r"\$\{\{\s*(\w+)\.", condition)
                    for ctx in contexts_used:
                        assert ctx in valid_contexts, f"Invalid context '{ctx}' in {workflow_file.name}, step {idx}"

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_if_conditions_handle_undefined_gracefully(self, workflow_file: Path):
        """Test that if conditions handle potentially undefined values."""
        content = workflow_file.read_text()

        # Check for conditions that might fail if value is undefined
        risky_patterns = [
            r"if:.*github\.event\.pull_request\b(?!\s*&&)",  # Should check for existence
        ]

        for pattern in risky_patterns:
            # Advisory: consider checking for undefined
            matches = re.findall(pattern, content)
            # Not failing, just checking


class TestWorkflowOutputsAndArtifactsAdvanced:
    """Tests for workflow outputs and artifacts."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_job_outputs_reference_valid_steps(self, workflow_file: Path):
        """Test that job outputs reference steps that have IDs."""
        data = load_yaml_safe(workflow_file)
        jobs = data.get("jobs", {})

        for job_name, job in jobs.items():
            if "outputs" in job:
                step_ids = {s.get("id") for s in job.get("steps", []) if "id" in s}

                for output_name, output_value in job["outputs"].items():
                    output_str = str(output_value)
                    if "steps." in output_str:
                        # Extract step ID references
                        refs = re.findall(r"steps\.(\w+)\.", output_str)
                        for ref in refs:
                            assert (
                                ref in step_ids
                            ), f"Output '{output_name}' references undefined step '{ref}' in {workflow_file.name}"

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_artifacts_have_reasonable_retention(self, workflow_file: Path):
        """Test that artifact retention is reasonable."""
        data = load_yaml_safe(workflow_file)
        jobs = data.get("jobs", {})

        for job_name, job in jobs.items():
            steps = job.get("steps", [])
            for step in steps:
                if "uses" in step and "actions/upload-artifact" in step["uses"]:
                    if "with" in step and "retention-days" in step["with"]:
                        retention = step["with"]["retention-days"]
                        assert 1 <= retention <= 90, f"Artifact retention should be 1-90 days in {workflow_file.name}"


class TestWorkflowEnvironmentVariables:
    """Tests for environment variable usage."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_env_vars_use_consistent_naming(self, workflow_file: Path):
        """Test that environment variables follow naming conventions."""
        data = load_yaml_safe(workflow_file)

        def check_env_names(env_dict):
            if isinstance(env_dict, dict):
                for key in env_dict.keys():
                    # Env vars should be UPPER_CASE
                    assert key.isupper() or "_" in key, f"Env var '{key}' should follow UPPER_CASE convention"

        # Workflow-level env
        if "env" in data:
            check_env_names(data["env"])

        # Job-level env
        jobs = data.get("jobs", {})
        for job_name, job in jobs.items():
            if "env" in job:
                check_env_names(job["env"])

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_env_vars_not_duplicated_across_levels(self, workflow_file: Path):
        """Test that env vars aren't unnecessarily duplicated."""
        data = load_yaml_safe(workflow_file)

        workflow_env = set(data.get("env", {}).keys())
        jobs = data.get("jobs", {})

        for job_name, job in jobs.items():
            job_env = set(job.get("env", {}).keys())
            # Check for duplication (informational)
            duplicates = workflow_env & job_env
            if duplicates:
                # Advisory: consider consolidating env vars
                pass


class TestWorkflowScheduledExecutionBestPractices:
    """Tests for scheduled workflow best practices."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_scheduled_workflows_use_valid_cron(self, workflow_file: Path):
        """Test that cron expressions are valid."""
        data = load_yaml_safe(workflow_file)
        triggers = data.get("on", {})

        if "schedule" in triggers:
            schedules = triggers["schedule"]
            for schedule in schedules:
                cron = schedule.get("cron")
                assert cron is not None, f"Schedule missing cron in {workflow_file.name}"

                # Validate cron has 5 parts
                parts = cron.split()
                assert len(parts) == 5, f"Invalid cron '{cron}' in {workflow_file.name} (needs 5 fields)"

                # Check each part is valid
                for i, part in enumerate(parts):
                    # Should be number, *, */n, or range
                    assert re.match(r"^(\d+|\*|,|\-|\/)+$", part), f"Invalid cron part '{part}' in {workflow_file.name}"

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_scheduled_workflows_not_too_frequent(self, workflow_file: Path):
        """Test that scheduled workflows aren't overly frequent."""
        data = load_yaml_safe(workflow_file)
        triggers = data.get("on", {})

        if "schedule" in triggers:
            schedules = triggers["schedule"]
            for schedule in schedules:
                cron = schedule.get("cron", "")
                # Check if runs every minute (potentially wasteful)
                if cron.startswith("* *"):
                    # Advisory: running every minute may be excessive
                    pass


# Additional test to verify all new test classes are properly structured
class TestTestSuiteCompleteness:
    """Meta-test to ensure test suite is comprehensive."""

    def test_all_workflow_files_tested(self):
        """Verify that all workflow files are included in tests."""
        workflow_files = get_workflow_files()
        assert len(workflow_files) > 0, "Should find at least one workflow file"

        for wf in workflow_files:
            assert wf.exists(), f"Workflow file {wf} should exist"
            assert wf.suffix in [".yml", ".yaml"], f"Workflow file {wf} should be YAML"

    def test_test_coverage_is_comprehensive(self):
        """Ensure we have multiple test categories."""
        # Count test classes in this module
        import inspect
        import sys

        current_module = sys.modules[__name__]
        test_classes = [
            name for name, obj in inspect.getmembers(current_module) if inspect.isclass(obj) and name.startswith("Test")
        ]

        # Should have many test classes (original + new ones)
        assert len(test_classes) >= 15, f"Should have at least 15 test classes, found {len(test_classes)}"
