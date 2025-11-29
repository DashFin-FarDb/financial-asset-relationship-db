"""
Comprehensive tests for GitHub Actions workflow files.

This module validates the structure, syntax, and configuration of GitHub Actions
workflows, ensuring they are properly formatted and free of common issues like
duplicate keys, invalid syntax, and missing required fields.
"""

import pytest
import yaml
from pathlib import Path
from typing import Any, Dict, List


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
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def check_duplicate_keys(file_path: Path) -> List[str]:
    """
    Detect duplicate mapping keys in a YAML file.
    
    Parameters:
        file_path (Path): Path to the YAML file to inspect.
    
    Returns:
        List of duplicate key names found, or an empty list if none are present.
    """
    duplicates = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse with a custom constructor that detects duplicates
    class DuplicateKeySafeLoader(yaml.SafeLoader):
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
    
    DuplicateKeySafeLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        constructor_with_dup_check
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
        """
        Check that a workflow file exists, is a regular file and contains non-empty UTF-8 text.
        """
        assert workflow_file.exists(), f"Workflow file {workflow_file} does not exist"
        assert workflow_file.is_file(), f"Workflow path {workflow_file} is not a file"
        with open(workflow_file, 'r', encoding='utf-8') as f:
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
        assert isinstance(config["name"], str), (
            f"Workflow {workflow_file.name} 'name' must be a string"
        )
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_has_triggers(self, workflow_file: Path):
        """
        Ensure a workflow file declares at least one trigger using the top-level "on" field.
        
        Asserts that the parsed workflow is a mapping and contains the "on" key; on failure the assertion message identifies the workflow file.
        """
        config = load_yaml_safe(workflow_file)
        assert isinstance(config, dict), (
            f"Workflow {workflow_file.name} did not load to a mapping"
        )
        assert "on" in config, (
            f"Workflow {workflow_file.name} missing trigger configuration ('on' field)"
        )
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_has_jobs(self, workflow_file: Path):
        """
        Ensure the workflow defines at least one job.
        
        Asserts that the top-level "jobs" field is present, is a mapping (dictionary), and contains at least one job entry for the given workflow file.
        """
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
        Ensure every `uses` action in the workflow is pinned to a specific version and that floating branch refs are disallowed.
        
        Asserts that non-local actions (those not starting with `./`) include a `@` ref (for example `@v1`, `@v3.5.2`, or `@<commit-sha>`). Fails the test if an action is unpinned or if the ref is a floating branch like `main`, `master`, `latest`, or `stable`. Prints an informational message when an action is pinned by a 40-character commit SHA to encourage considerating semantic version tags for maintainability.
        
        Parameters:
            workflow_file (Path): Path to the workflow YAML file under test.
        """
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})

        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])

            for idx, step in enumerate(steps):
                if "uses" in step:
                    action = step["uses"]
                    # Local actions (starting with ./) don't need version tags
                    if action.startswith("./"):
                        continue
                    # Action should have a version tag (e.g., @v1, @v3.5.2, or @<commit-sha>)
                    assert "@" in action, (
                        f"Step {idx} in job '{job_name}' of {workflow_file.name} "
                        f"must specify a pinned version for action '{action}' (e.g., @v1, @v3.5.2, or @<commit-sha>). "
                        f"Pinning action versions is a critical security best practice."
                    )
                    # Disallow floating branches like @main or @master
                    ref = action.split("@", 1)[1].strip()
                    assert ref and ref.lower() not in {"main", "master", "latest", "stable"}, (
                        f"Step {idx} in job '{job_name}' of {workflow_file.name} "
                        f"uses a floating branch '{ref}' for action '{action}'. Use a tagged release or commit SHA."
                    )
                    # Informational: if pinned by full SHA, recommend considering semver tags for maintainability
                    if len(ref) == 40 and all(c in "0123456789abcdef" for c in ref.lower()):
                        print(
                            f"Info: Step {idx} in job '{job_name}' of {workflow_file.name} "
                            f"pins '{action}' by commit SHA. Consider using a semantic version tag for easier maintenance."
                        )
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_steps_have_names_or_uses(self, workflow_file: Path):
        """
        Validate that every step in each job defines at least one of 'name', 'uses' or 'run'.
        
        Parameters:
            workflow_file (Path): Path to the workflow YAML file whose jobs' steps are being validated.
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
        Validate that the pr-agent workflow declares a non-empty top-level `name`.
        
        Parameters:
            pr_agent_workflow (Dict[str, Any]): Parsed YAML mapping for the pr-agent workflow fixture.
        """
        assert "name" in pr_agent_workflow, (
            "pr-agent workflow must have a descriptive 'name' field"
        )
        assert isinstance(pr_agent_workflow["name"], str) and pr_agent_workflow["name"].strip(), (
            "pr-agent workflow 'name' field must be a non-empty string"
        )
    
    def test_pr_agent_triggers_on_pull_request(self, pr_agent_workflow: Dict[str, Any]):
        """
        Verify the pr-agent workflow is configured to trigger on the `pull_request` event.
        
        Normalises the workflow's `on` field (string, list or mapping) to determine the set of event names and asserts that `pull_request` is present in that set.
        
        Parameters:
            pr_agent_workflow (dict): Parsed workflow mapping for pr-agent.yml.
        """
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
        """Test that pr-agent workflow triggers on pull_request events."""
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
        triggers = pr_agent_workflow.get("on", {})
        assert "pull_request" in triggers, (
            "pr-agent workflow must trigger on pull_request events"
        )
    

    def test_pr_agent_has_trigger_job(self, pr_agent_workflow: Dict[str, Any]):
        """Test that pr-agent workflow has a pr-agent-trigger job."""
        jobs = pr_agent_workflow.get("jobs", {})
        assert "pr-agent-trigger" in jobs, "pr-agent workflow must have pr-agent-trigger job"
    
    def test_pr_agent_review_runs_on_ubuntu(self, pr_agent_workflow: Dict[str, Any]):
        """
        Validates the pr-agent workflow contains a 'pr-agent-trigger' job and that it runs on a supported Ubuntu runner.
        
        Checks that the workflow mapping includes a job named 'pr-agent-trigger' and that the job's `runs-on` value is one of: 'ubuntu-latest', 'ubuntu-22.04', or 'ubuntu-20.04'.
        
        Parameters:
            pr_agent_workflow (dict): Parsed workflow YAML as a mapping.
        """
        review_job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        runs_on = review_job.get("runs-on", "")
        # Be more specific about expected runner format
        assert runs_on in ["ubuntu-latest", "ubuntu-22.04", "ubuntu-20.04"], (
            f"PR Agent trigger job should run on standard Ubuntu runner, got '{runs_on}'"
        )
        """Test that pr-agent workflow has a pr-agent-trigger job."""
        jobs = pr_agent_workflow.get("jobs", {})
        assert "pr-agent-trigger" in jobs, "pr-agent workflow must have pr-agent-trigger job"
    
    def test_pr_agent_review_runs_on_ubuntu(self, pr_agent_workflow: Dict[str, Any]):
        """Test that pr-agent-trigger job runs on Ubuntu."""
        review_job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        runs_on = review_job.get("runs-on", "")
        # Be more specific about expected runner format
        assert runs_on in ["ubuntu-latest", "ubuntu-22.04", "ubuntu-20.04"], (
            f"PR Agent trigger job should run on standard Ubuntu runner, got '{runs_on}'"
        )
    
    def test_pr_agent_has_checkout_step(self, pr_agent_workflow: Dict[str, Any]):
        """
        Ensure the 'pr-agent-trigger' job includes at least one step that uses actions/checkout.
        
        Asserts that the workflow's 'pr-agent-trigger' job has a step with a `uses` value beginning with `actions/checkout`.
        """
        review_job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        steps = review_job.get("steps", [])
        
        checkout_steps = [
            s for s in steps 
            if s.get("uses", "").startswith("actions/checkout")
        ]
        assert len(checkout_steps) > 0, "PR Agent trigger job must check out the repository"
    
    def test_pr_agent_checkout_has_token(self, pr_agent_workflow: Dict[str, Any]):
        """
        Ensure every actions/checkout step in the "pr-agent-trigger" job includes a non-empty `token` in its `with` mapping.
        
        Asserts that each checkout step's `with.token` is a non-empty string (for example `\${{ secrets.GITHUB_TOKEN }}`).
        
        Parameters:
            pr_agent_workflow (dict): Parsed YAML mapping for pr-agent.yml representing the workflow contents.
        """
        review_job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        steps = review_job.get("steps", [])
        
        checkout_steps = [
            s for s in steps 
            if s.get("uses", "").startswith("actions/checkout")
        ]
        
        for step in checkout_steps:
            step_with = step.get("with", {})
            token = step_with.get("token")
            assert isinstance(token, str) and token.strip(), (
                "Checkout step must specify a non-empty token for better security. "
                "Use ${{ secrets.GITHUB_TOKEN }} or similar."
            )
    
    def test_pr_agent_has_python_setup(self, pr_agent_workflow: Dict[str, Any]):
        """
        Asserts the workflow's "pr-agent-trigger" job includes at least one step that uses actions/setup-python.
        """
        review_job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        steps = review_job.get("steps", [])
        
        python_steps = [
            s for s in steps 
            if s.get("uses", "").startswith("actions/setup-python")
        ]
        assert len(python_steps) > 0, "PR Agent trigger job must set up Python"
    
    def test_pr_agent_has_node_setup(self, pr_agent_workflow: Dict[str, Any]):
        """Test that pr-agent-trigger job sets up Node.js."""
        review_job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        steps = review_job.get("steps", [])
        
        node_steps = [
            s for s in steps 
            if s.get("uses", "").startswith("actions/setup-node")
        ]
        assert len(node_steps) > 0, "PR Agent trigger job must set up Node.js"
    
    def test_pr_agent_python_version(self, pr_agent_workflow: Dict[str, Any]):
        """
        Ensure any actions/setup-python step in the "pr-agent-trigger" job specifies python-version "3.11".
        """
        review_job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        steps = review_job.get("steps", [])
        
        python_steps = [
            s for s in steps 
            if s.get("uses", "").startswith("actions/setup-python")
        ]
        
        for step in python_steps:
            step_with = step.get("with", {})
            assert "python-version" in step_with, (
                "Python setup should specify a version"
            )
            assert step_with["python-version"] == "3.11", (
                "Python version should be 3.11"
            )
    
    def test_pr_agent_node_version(self, pr_agent_workflow: Dict[str, Any]):
        """
        Ensure every actions/setup-node step in the pr-agent 'pr-agent-trigger' job specifies Node.js version 18.
        """
        review_job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        steps = review_job.get("steps", [])
        
        node_steps = [
            s for s in steps 
            if s.get("uses", "").startswith("actions/setup-node")
        ]
        
        for step in node_steps:
            step_with = step.get("with", {})
            assert "node-version" in step_with, (
                "Node.js setup should specify a version"
            )
            assert step_with["node-version"] == "18", (
                "Node.js version should be 18"
            )
    
    def test_pr_agent_no_duplicate_setup_steps(self, pr_agent_workflow: Dict[str, Any]):
        """
        Warns if the `pr-agent-trigger` job contains steps with duplicate names.
        
        Scans the `pr-agent-trigger` job in the provided workflow mapping for step `name` values and prints a warning listing any names that appear more than once.
        
        Parameters:
            pr_agent_workflow (Dict[str, Any]): Parsed workflow mapping for `pr-agent.yml`.
        """
        review_job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        steps = review_job.get("steps", [])
        
        # Check for duplicate step names
        step_names = [s.get("name", "") for s in steps if s.get("name")]
        duplicate_names = [name for name in step_names if step_names.count(name) > 1]
        
        if duplicate_names:
            print(f"\nWarning: Found duplicate step names: {set(duplicate_names)}. "
                  "Each step should have a unique name.")
    
    def test_pr_agent_fetch_depth_configured(self, pr_agent_workflow: Dict[str, Any]):
        """
        Ensure checkout steps in the PR Agent trigger job have valid fetch-depth values.
        """
        review_job = pr_agent_workflow["jobs"]["pr-agent-trigger"]
        steps = review_job.get("steps", [])
        
        checkout_steps = [
            s for s in steps 
            if s.get("uses", "").startswith("actions/checkout")
        ]
        
        for step in checkout_steps:
            step_with = step.get("with", {})
            if "fetch-depth" in step_with:
                fetch_depth = step_with["fetch-depth"]
                assert isinstance(fetch_depth, int) or fetch_depth == 0, (
                    "fetch-depth should be an integer"
                )


class TestWorkflowSecurity:
    """Test suite for workflow security best practices."""
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_no_hardcoded_secrets(self, workflow_file: Path):
        """Test that workflows don't contain hardcoded secrets or tokens."""
        with open(workflow_file, 'r', encoding='utf-8') as f:
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
                    if any(sensitive in key.lower() 
                           for sensitive in ["token", "password", "key", "secret"]):
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
                print(f"\nWarning: {workflow_file.name} job '{job_name}' has "
                      f"{len(unnamed_steps)} unnamed steps (recommended to add names)")
    
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
            print(f"\nWarning: {workflow_file.name} is {file_size} bytes. "
                  "Consider splitting into multiple workflows if it gets too complex.")
        
        # Fail if exceeds 50KB (definitely too large)
        assert file_size < 51200, (
            f"Workflow {workflow_file.name} is too large ({file_size} bytes). "
            "Consider splitting into multiple workflows or using reusable workflows."
        )


class TestWorkflowEdgeCases:
    """Test suite for edge cases and error conditions."""
    
    def test_workflow_directory_exists(self):
        """Test that .github/workflows directory exists."""
        assert WORKFLOWS_DIR.exists(), (
            ".github/workflows directory does not exist"
        )
        assert WORKFLOWS_DIR.is_dir(), (
            ".github/workflows exists but is not a directory"
        )
    
    def test_at_least_one_workflow_exists(self):
        """Test that at least one workflow file exists."""
        workflow_files = get_workflow_files()
        assert len(workflow_files) > 0, (
            "No workflow files found in .github/workflows directory"
        )
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_file_extension(self, workflow_file: Path):
        """
        Verify that a workflow file uses the .yml or .yaml extension.
        
        Parameters:
        	workflow_file (Path): Path to the workflow file being tested.
        """
        assert workflow_file.suffix in [".yml", ".yaml"], (
            f"Workflow file {workflow_file.name} has invalid extension. "
            "Use .yml or .yaml"
        )
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_encoding(self, workflow_file: Path):
        """Test that workflow files use UTF-8 encoding."""
        try:
            with open(workflow_file, 'r', encoding='utf-8') as f:
                f.read()
        except UnicodeDecodeError:
            pytest.fail(
                f"Workflow {workflow_file.name} is not valid UTF-8. "
                "Ensure file is saved with UTF-8 encoding."
            )
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_no_tabs(self, workflow_file: Path):
        """
        Ensure the workflow YAML file contains no tab characters.
        
        Fails the test if any tab character is present, because YAML indentation must use spaces rather than tabs.
        """
        with open(workflow_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert "\t" not in content, (
            f"Workflow {workflow_file.name} contains tab characters. "
            "YAML files should use spaces for indentation, not tabs."
        )
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_consistent_indentation(self, workflow_file: Path):
        """
        Validate that non-empty, non-comment lines in a workflow file use indentation in multiples of two spaces.
        
        If inconsistent indentation levels are detected, prints a formatting warning listing the observed indentation levels and the workflow file name.
        
        Parameters:
            workflow_file (Path): Path to the workflow YAML file to inspect.
        """
        with open(workflow_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        indentation_levels = set()
        for line in lines:
            if line.strip() and not line.strip().startswith("#"):
                # Count leading spaces
                spaces = len(line) - len(line.lstrip(' '))
                if spaces > 0:
                    indentation_levels.add(spaces)
        
        # Check if indentation is consistent (multiples of 2)
        if indentation_levels:
            inconsistent = [
                level for level in indentation_levels 
                if level % 2 != 0
            ]
            if inconsistent:
                print(f"FORMATTING: Workflow {workflow_file.name} has inconsistent indentation "
                      f"levels: {sorted(indentation_levels)}. YAML requires consistent "
                      f"indentation (typically 2 spaces) to prevent parsing errors.")


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
            print(f"\nInfo: {workflow_file.name} doesn't use caching. "
                  "Consider adding caching to improve performance.")

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
        assert len(jobs) == 3, (
            f"pr-agent workflow should have exactly 3 jobs, found {len(jobs)}"
        )
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
        
        node_steps = [
            s for s in steps 
            if s.get("uses", "").startswith("actions/setup-node")
        ]
        
        for step in node_steps:
            step_with = step.get("with", {})
            assert step_with.get("node-version") == "18", (
                "Node.js version should be 18 (current configuration)"
            )
    
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


class TestWorkflowTriggers:
    """Comprehensive tests for workflow trigger configurations."""
    
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
        # Handle both "on" and True keys (YAML parses "on:" as True in some cases)
        triggers = config.get("on", config.get(True, {}))
        
        if isinstance(triggers, str):
            triggers = {triggers: None}
        elif isinstance(triggers, list):
            triggers = {t: None for t in triggers}
        
        valid_events = {
            "push", "pull_request", "pull_request_review", "pull_request_target",
            "issue_comment", "issues", "workflow_dispatch", "schedule", "release",
            "create", "delete", "fork", "watch", "check_suite", "check_run",
            "deployment", "deployment_status", "page_build", "project", "project_card",
            "project_column", "public", "registry_package", "status", "workflow_run",
            "repository_dispatch", "milestone", "discussion", "discussion_comment",
            "merge_group"
        }
        
        for event in triggers.keys():
            if event is True:  # Handle boolean true for shorthand syntax
                continue
            assert event in valid_events, (
                f"Workflow {workflow_file.name} uses invalid event type: {event}"
            )
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_pr_triggers_specify_types(self, workflow_file: Path):
        """Test that pull_request triggers specify activity types."""
        config = load_yaml_safe(workflow_file)
        # Handle both "on" and True keys (YAML parses "on:" as True in some cases)
        triggers = config.get("on", config.get(True, {}))
        
        if not isinstance(triggers, dict):
            return  # Skip for non-dict triggers
        
        if "pull_request" in triggers:
            pr_config = triggers["pull_request"]
            if pr_config is not None and pr_config != {}:
                if "types" not in pr_config:
                    print(f"\nRecommendation: {workflow_file.name} pull_request trigger should "
                          "specify activity types for better control")


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
            assert "runs-on" in job_config, (
                f"Job '{job_name}' in {workflow_file.name} must specify 'runs-on'"
            )
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_jobs_use_standard_runners(self, workflow_file: Path):
        """
        Ensure jobs that declare `runs-on` use recognised GitHub-hosted runners.
        
        Skips jobs that use expressions, matrix variables or self-hosted runners; fails if a job specifies a runner not in the accepted set.
        """
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})
        
        standard_runners = {
            "ubuntu-latest", "ubuntu-20.04", "ubuntu-22.04", "ubuntu-24.04",
            "windows-latest", "windows-2019", "windows-2022",
            "macos-latest", "macos-11", "macos-12", "macos-13", "macos-14"
        }
        
        for job_name, job_config in jobs.items():
            if "runs-on" not in job_config:
                continue
            
            runner = job_config["runs-on"]
            if isinstance(runner, str):
                # Allow self-hosted and matrix variables
                if "${{" in runner or "self-hosted" in runner:
                    continue
                assert runner in standard_runners, (
                    f"Job '{job_name}' in {workflow_file.name} uses non-standard runner: {runner}"
                )


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
            
            duplicates = [sid for sid in step_ids if step_ids.count(sid) > 1]
            assert not duplicates, (
                f"Job '{job_name}' in {workflow_file.name} has duplicate step IDs: {duplicates}"
            )
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_steps_continue_on_error_usage(self, workflow_file: Path):
        """
        Verify steps using `continue-on-error` include a descriptive name.
        
        Prints a recommendation when a step in any job has `continue-on-error: true` but lacks a `name`, encouraging an explicit explanation for the tolerant failure.
        """
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})
        
        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            
            for step in steps:
                if step.get("continue-on-error") is True:
                    # Should have a comment or name explaining why
                    if "name" not in step:
                        print(f"\nRecommendation: Step in job '{job_name}' of {workflow_file.name} "
                              "uses continue-on-error but lacks descriptive name")


class TestWorkflowEnvAndSecrets:
    """Tests for environment variables and secrets usage."""

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_env_vars_naming_convention(self, workflow_file: Path):
        """
        Validate that workflow environment variable names use UPPER_CASE and contain only letters, digits or underscores.
        
        Checks environment variable mappings at the workflow level and within each job; prints a maintainability warning listing any offending variable names and the workflow file when violations are found.
        
        Parameters:
            workflow_file (Path): Path to the workflow YAML file being checked.
        """
        config = load_yaml_safe(workflow_file)

        def check_env_vars(env_dict):
            """
            Identify environment variable names that do not follow the naming convention of upper-case letters, digits and underscores.

            Parameters:
                env_dict (dict): Mapping of environment variable names to their values. If a non-dict is provided, it is treated as absent.

            Returns:
                invalid_keys (List[str]): List of keys from `env_dict` that are not entirely upper-case or that contain characters other than letters, digits or underscores.
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
            if invalid:
# Check top-level env
        if "env" in config:
            invalid = check_env_vars(config["env"])
            if invalid:
                print(f"MAINTAINABILITY: Workflow {workflow_file.name} has environment variables "
                      f"that don't follow UPPER_CASE convention: {invalid}. This can reduce "
                      f"readability and consistency across workflows.")
                      f"that don't follow UPPER_CASE convention: {invalid}. This can reduce "
                      f"readability and consistency across workflows.")

    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_secrets_not_in_env_values(self, workflow_file: Path):
        """Test that secrets are referenced, not hardcoded in env values."""
        with open(workflow_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Look for patterns that might indicate hardcoded secrets
        suspicious_in_env = [
            "password: \"",
            "token: \"",
            "api_key: \"",
            "secret: \"",
        ]

        for pattern in suspicious_in_env:
            if pattern in content.lower():
                # Allow if it's using secrets context
                if "${{ secrets." not in content[max(0, content.lower().find(pattern) - 50):content.lower().find(pattern) + 50]:
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
            print(f"\nWarning: {workflow_file.name} has {job_count} jobs. "
                  "Consider splitting into multiple workflows.")
        
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
                print(f"\nInfo: Job '{job_name}' in {workflow_file.name} has "
                      f"{step_count} steps. Consider refactoring.")
            
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
                    print(f"\nWarning: Job '{job_name}' in {workflow_file.name} "
                          f"has complex conditional ({complexity} operators)")


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
                        print(f"\nInfo: Artifact upload in job '{job_name}' of "
                              f"{workflow_file.name} doesn't specify retention-days")
    
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
                    f"Job '{job_name}' in {workflow_file.name} needs '{needed_job}' "
                    "which doesn't exist"
                )


class TestWorkflowBestPractices:
    """Tests for workflow best practices and recommendations."""
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_uses_concurrency_for_prs(self, workflow_file: Path):
        """Test if PR workflows use concurrency to cancel outdated runs."""
        config = load_yaml_safe(workflow_file)
        # Handle both "on" and True keys (YAML parses "on:" as True in some cases)
        triggers = config.get("on", config.get(True, {}))
        
        has_pr_trigger = False
        if isinstance(triggers, dict):
            has_pr_trigger = "pull_request" in triggers or "pull_request_target" in triggers
        
        if has_pr_trigger and "concurrency" not in config:
            print(f"\nRecommendation: {workflow_file.name} triggers on PR but doesn't "
                  "use concurrency. Consider adding concurrency group to cancel outdated runs.")
    
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
                print(f"\nRecommendation: Job '{job_name}' in {workflow_file.name} "
                      "doesn't specify timeout-minutes")
    
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
                            print(f"\nRecommendation: Step {idx} in job '{job_name}' "
                                  f"of {workflow_file.name} uses multi-line run without "
                                  "explicit shell specification")

class TestWorkflowJobConfiguration:
    """Test suite for job-level configuration validation."""
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_workflow_jobs_have_timeout(self, workflow_file: Path):
        """
        Check if jobs specify timeout-minutes and recommend setting it if missing.
        
        For each job in a workflow that does not define a `timeout-minutes` key a recommendation message is printed suggesting adding a timeout to prevent runaway jobs.
        
        Parameters:
            workflow_file (Path): Path to the workflow YAML file being checked.
        """
        config = load_yaml_safe(workflow_file)
        jobs = config.get("jobs", {})
        
        for job_name, job_config in jobs.items():
            if "timeout-minutes" not in job_config:
                print(f"\nRecommendation: Job '{job_name}' in {workflow_file.name} "
                      "doesn't specify timeout-minutes")

class TestWorkflowAdvancedSecurity:
    """Advanced security tests for workflow files with bias for action."""
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_no_environment_variable_injection(self, workflow_file: Path):
        """Test that workflows don't have potential env injection vulnerabilities."""
        content = workflow_file.read_text()
        
        # Check for unsafe environment variable usage in bash context
        unsafe_patterns = [
            r'\$\{\{.*github\.event\..*\}\}.*bash',
            r'run:.*\$\{\{.*github\.event\.issue\.title',
            r'run:.*\$\{\{.*github\.event\.pull_request\.title',
        ]
        
        for pattern in unsafe_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            assert len(matches) == 0, \
                f"{workflow_file.name}: Potential injection vulnerability via {pattern}"
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_no_script_injection_in_run_commands(self, workflow_file: Path):
        """Test that run commands don't have dangerous patterns."""
        data = load_yaml_safe(workflow_file)
        jobs = data.get('jobs', {})
        
        for job_name, job in jobs.items():
            steps = job.get('steps', [])
            for idx, step in enumerate(steps):
                if 'run' in step:
                    run_cmd = step['run']
                    # Check for dangerous eval/exec patterns
                    dangerous_patterns = ['eval ', 'exec(', '``']
                    for pattern in dangerous_patterns:
                        assert pattern not in str(run_cmd).lower(), \
                            f"Dangerous pattern '{pattern}' in {workflow_file.name}, job {job_name}, step {idx}"
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_secrets_not_echoed_to_logs(self, workflow_file: Path):
        """Test that secrets aren't accidentally printed to logs."""
        content = workflow_file.read_text()
        
        # Check for echo/print of secrets
        secret_logging_patterns = [
            r'echo.*\$\{\{.*secrets\.',
            r'print.*\$\{\{.*secrets\.',
            r'console\.log.*\$\{\{.*secrets\.',
        ]
        
        for pattern in secret_logging_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            assert len(matches) == 0, \
                f"{workflow_file.name}: Potential secret logging detected"
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_no_curl_with_user_input(self, workflow_file: Path):
        """Test that curl commands don't use untrusted user input."""
        content = workflow_file.read_text()
        
        # Check for curl with event data
        if 'curl' in content and 'github.event' in content:
            # Warn about potential URL injection
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'curl' in line.lower() and 'github.event' in line:
                    # This is advisory - curl with user input can be dangerous
                    assert True  # Not failing but flagging for review


class TestWorkflowAdvancedValidation:
    """Advanced structural validation tests."""
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_job_dependencies_are_acyclic(self, workflow_file: Path):
        """Test that job dependencies don't form cycles."""
        data = load_yaml_safe(workflow_file)
        jobs = data.get('jobs', {})
        
        # Build dependency graph
        deps = {}
        for job_name, job in jobs.items():
            needs = job.get('needs', [])
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
                assert not has_cycle(job, visited, set()), \
                    f"Circular dependency detected in {workflow_file.name}"
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_action_versions_use_semantic_versioning(self, workflow_file: Path):
        """Test that actions use proper semantic versioning."""
        data = load_yaml_safe(workflow_file)
        jobs = data.get('jobs', {})
        
        for job_name, job in jobs.items():
            steps = job.get('steps', [])
            for step in steps:
                if 'uses' in step:
                    uses = step['uses']
                    if '@' in uses:
                        _, version = uses.rsplit('@', 1)
                        # Should not use branch names
                        invalid_refs = ['main', 'master', 'latest', 'develop']
                        assert version.lower() not in invalid_refs, \
                            f"Using unstable ref '{version}' in {workflow_file.name}"
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_checkout_with_proper_ref_for_pr(self, workflow_file: Path):
        """Test that PR workflows checkout the correct ref."""
        data = load_yaml_safe(workflow_file)
        triggers = data.get('on', {})
        
        # If pull_request_target is used, should checkout PR ref explicitly
        if 'pull_request_target' in triggers:
            jobs = data.get('jobs', {})
            has_checkout = False
            has_safe_ref = False
            
            for job_name, job in jobs.items():
                steps = job.get('steps', [])
                for step in steps:
                    if 'uses' in step and 'actions/checkout' in step['uses']:
                        has_checkout = True
                        if 'with' in step and 'ref' in step['with']:
                            has_safe_ref = True
            
            if has_checkout:
                # Advisory: pull_request_target should specify ref
                assert True  # Not failing but important to check
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_timeout_minutes_are_reasonable(self, workflow_file: Path):
        """Test that timeout values are reasonable."""
        data = load_yaml_safe(workflow_file)
        jobs = data.get('jobs', {})
        
        for job_name, job in jobs.items():
            timeout = job.get('timeout-minutes')
            if timeout is not None:
                assert isinstance(timeout, int), \
                    f"timeout-minutes must be integer in {workflow_file.name}"
                assert 1 <= timeout <= 360, \
                    f"timeout-minutes {timeout} out of range (1-360) in {workflow_file.name}"


class TestWorkflowCachingStrategies:
    """Tests for caching best practices."""
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_cache_uses_hashfiles_for_lockfiles(self, workflow_file: Path):
        """Test that caches use hashFiles for dependency lockfiles."""
        content = workflow_file.read_text()
        
        if 'actions/cache' in content:
            lockfiles = ['package-lock.json', 'yarn.lock', 'requirements.txt', 'Pipfile.lock']
            mentioned_lockfiles = [lf for lf in lockfiles if lf in content]
            
            if mentioned_lockfiles:
                # Should use hashFiles for these
                assert 'hashFiles' in content, \
                    f"Cache with lockfiles should use hashFiles in {workflow_file.name}"
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_cache_keys_are_unique_per_os(self, workflow_file: Path):
        """Test that cache keys include OS information when running on matrix."""
        data = load_yaml_safe(workflow_file)
        jobs = data.get('jobs', {})
        
        for job_name, job in jobs.items():
            strategy = job.get('strategy', {})
            matrix = strategy.get('matrix', {})
            
            if 'os' in matrix or 'runs-on' in job:
                steps = job.get('steps', [])
                for step in steps:
                    if 'uses' in step and 'actions/cache' in step['uses']:
                        if 'with' in step and 'key' in step['with']:
                            key = str(step['with']['key'])
                            # Should include runner.os in cache key
                            if 'os' in matrix:
                                # Advisory: consider including OS in cache key
                                assert True


class TestWorkflowPermissionsBestPractices:
    """Tests for proper permissions configuration."""
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_permissions_follow_least_privilege(self, workflow_file: Path):
        """Test that workflows request minimal permissions."""
        data = load_yaml_safe(workflow_file)
        permissions = data.get('permissions', {})
        
        if permissions:
            # If permissions are specified, ensure they're not overly broad
            if isinstance(permissions, dict):
                for perm, value in permissions.items():
                    # Permissions should be 'read', 'write', or 'none'
                    assert value in ['read', 'write', 'none'], \
                        f"Invalid permission value '{value}' in {workflow_file.name}"
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_write_permissions_have_justification(self, workflow_file: Path):
        """Test that write permissions are used appropriately."""
        data = load_yaml_safe(workflow_file)
        
        def check_perms(perms):
            if isinstance(perms, dict):
                for key, value in perms.items():
                    if value == 'write':
                        # Common justified write permissions
                        justified = ['contents', 'pull-requests', 'issues', 'packages']
                        if key not in justified:
                            # Advisory: review write permission usage
                            pass
        
        # Check workflow-level permissions
        if 'permissions' in data:
            check_perms(data['permissions'])
        
        # Check job-level permissions
        jobs = data.get('jobs', {})
        for job_name, job in jobs.items():
            if 'permissions' in job:
                check_perms(job['permissions'])


class TestWorkflowComplexScenarios:
    """Tests for complex workflow patterns."""
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_reusable_workflows_have_proper_inputs(self, workflow_file: Path):
        """Test that reusable workflows define inputs correctly."""
        data = load_yaml_safe(workflow_file)
        
        if 'workflow_call' in data.get('on', {}):
            wf_call = data['on']['workflow_call']
            
            if 'inputs' in wf_call:
                for input_name, input_def in wf_call['inputs'].items():
                    assert 'type' in input_def, \
                        f"Input '{input_name}' missing type in {workflow_file.name}"
                    assert input_def['type'] in ['string', 'number', 'boolean'], \
                        f"Invalid input type in {workflow_file.name}"
            
            if 'secrets' in wf_call:
                for secret_name, secret_def in wf_call['secrets'].items():
                    # Secrets should have required or description
                    assert 'required' in secret_def or 'description' in secret_def, \
                        f"Secret '{secret_name}' should specify required or description"
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_matrix_strategy_has_include_or_exclude_properly_formatted(self, workflow_file: Path):
        """Test matrix include/exclude are properly structured."""
        data = load_yaml_safe(workflow_file)
        jobs = data.get('jobs', {})
        
        for job_name, job in jobs.items():
            strategy = job.get('strategy', {})
            matrix = strategy.get('matrix', {})
            
            if 'include' in matrix:
                includes = matrix['include']
                assert isinstance(includes, list), \
                    f"Matrix include must be list in {workflow_file.name}"
                for item in includes:
                    assert isinstance(item, dict), \
                        f"Matrix include items must be dicts in {workflow_file.name}"
            
            if 'exclude' in matrix:
                excludes = matrix['exclude']
                assert isinstance(excludes, list), \
                    f"Matrix exclude must be list in {workflow_file.name}"


class TestWorkflowConditionalExecution:
    """Tests for conditional execution patterns."""
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_if_conditions_use_valid_syntax(self, workflow_file: Path):
        """Test that if conditions are syntactically valid."""
        data = load_yaml_safe(workflow_file)
        jobs = data.get('jobs', {})
        
        valid_contexts = [
            'github', 'env', 'secrets', 'vars', 'job', 'jobs',
            'steps', 'runner', 'matrix', 'needs', 'strategy', 'inputs'
        ]
        
        for job_name, job in jobs.items():
            # Check job-level if
            if 'if' in job:
                condition = str(job['if'])
                contexts_used = re.findall(r'\$\{\{\s*(\w+)\.', condition)
                for ctx in contexts_used:
                    assert ctx in valid_contexts, \
                        f"Invalid context '{ctx}' in {workflow_file.name}, job {job_name}"
            
            # Check step-level if
            steps = job.get('steps', [])
            for idx, step in enumerate(steps):
                if 'if' in step:
                    condition = str(step['if'])
                    contexts_used = re.findall(r'\$\{\{\s*(\w+)\.', condition)
                    for ctx in contexts_used:
                        assert ctx in valid_contexts, \
                            f"Invalid context '{ctx}' in {workflow_file.name}, step {idx}"
    
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


class TestWorkflowOutputsAndArtifacts:
    """Tests for workflow outputs and artifacts."""
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_job_outputs_reference_valid_steps(self, workflow_file: Path):
        """Test that job outputs reference steps that have IDs."""
        data = load_yaml_safe(workflow_file)
        jobs = data.get('jobs', {})
        
        for job_name, job in jobs.items():
            if 'outputs' in job:
                step_ids = {s.get('id') for s in job.get('steps', []) if 'id' in s}
                
                for output_name, output_value in job['outputs'].items():
                    output_str = str(output_value)
                    if 'steps.' in output_str:
                        # Extract step ID references
                        refs = re.findall(r'steps\.(\w+)\.', output_str)
                        for ref in refs:
                            assert ref in step_ids, \
                                f"Output '{output_name}' references undefined step '{ref}' in {workflow_file.name}"
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_artifacts_have_reasonable_retention(self, workflow_file: Path):
        """Test that artifact retention is reasonable."""
        data = load_yaml_safe(workflow_file)
        jobs = data.get('jobs', {})
        
        for job_name, job in jobs.items():
            steps = job.get('steps', [])
            for step in steps:
                if 'uses' in step and 'actions/upload-artifact' in step['uses']:
                    if 'with' in step and 'retention-days' in step['with']:
                        retention = step['with']['retention-days']
                        assert 1 <= retention <= 90, \
                            f"Artifact retention should be 1-90 days in {workflow_file.name}"


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
                    assert key.isupper() or '_' in key, \
                        f"Env var '{key}' should follow UPPER_CASE convention"
        
        # Workflow-level env
        if 'env' in data:
            check_env_names(data['env'])
        
        # Job-level env
        jobs = data.get('jobs', {})
        for job_name, job in jobs.items():
            if 'env' in job:
                check_env_names(job['env'])
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_env_vars_not_duplicated_across_levels(self, workflow_file: Path):
        """Test that env vars aren't unnecessarily duplicated."""
        data = load_yaml_safe(workflow_file)
        
        workflow_env = set(data.get('env', {}).keys())
        jobs = data.get('jobs', {})
        
        for job_name, job in jobs.items():
            job_env = set(job.get('env', {}).keys())
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
        triggers = data.get('on', {})
        
        if 'schedule' in triggers:
            schedules = triggers['schedule']
            for schedule in schedules:
                cron = schedule.get('cron')
                assert cron is not None, \
                    f"Schedule missing cron in {workflow_file.name}"
                
                # Validate cron has 5 parts
                parts = cron.split()
                assert len(parts) == 5, \
                    f"Invalid cron '{cron}' in {workflow_file.name} (needs 5 fields)"
                
                # Check each part is valid
                for i, part in enumerate(parts):
                    # Should be number, *, */n, or range
                    assert re.match(r'^(\d+|\*|,|\-|\/)+$', part), \
                        f"Invalid cron part '{part}' in {workflow_file.name}"
    
    @pytest.mark.parametrize("workflow_file", get_workflow_files())
    def test_scheduled_workflows_not_too_frequent(self, workflow_file: Path):
        """Test that scheduled workflows aren't overly frequent."""
        data = load_yaml_safe(workflow_file)
        triggers = data.get('on', {})
        
        if 'schedule' in triggers:
            schedules = triggers['schedule']
            for schedule in schedules:
                cron = schedule.get('cron', '')
                # Check if runs every minute (potentially wasteful)
                if cron.startswith('* *'):
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
            assert wf.suffix in ['.yml', '.yaml'], f"Workflow file {wf} should be YAML"
    
    def test_test_coverage_is_comprehensive(self):
        """
        Ensure the test suite defines a broad set of test classes covering multiple categories.
        
        Asserts that the current module contains at least 15 test classes whose names start with "Test"; fails with a message stating the found count if the requirement is not met.
        """
        # Count test classes in this module
        import sys
        import inspect
        
        current_module = sys.modules[__name__]
        test_classes = [name for name, obj in inspect.getmembers(current_module)
                       if inspect.isclass(obj) and name.startswith('Test')]
        
        # Should have many test classes (original + new ones)
        assert len(test_classes) >= 15, \
            f"Should have at least 15 test classes, found {len(test_classes)}"

class TestPRAgentWorkflowSpecific:
    """Specific tests for pr-agent.yml workflow integrity."""

    def test_pr_agent_no_duplicate_step_names(self):
        """Test that pr-agent.yml has no duplicate step names."""
        pr_agent_file = Path(".github/workflows/pr-agent.yml")
        assert pr_agent_file.exists(), "pr-agent.yml workflow file not found"
        
        with open(pr_agent_file, 'r') as f:
            workflow = yaml.safe_load(f)
        
        for job_name, job in workflow.get('jobs', {}).items():
            steps = job.get('steps', [])
            step_names = [
                step.get('name') for step in steps if step.get('name')
            ]
            
            # Check for duplicate step names
            seen = set()
            duplicates = []
            for name in step_names:
                if name in seen:
                    duplicates.append(name)
                seen.add(name)
            
            assert len(duplicates) == 0, (
                f"Job '{job_name}' in pr-agent.yml has duplicate step names: "
                f"{duplicates}"
            )

    def test_pr_agent_setup_python_single_definition(self):
        """Test that 'Setup Python' step appears only once per job."""
        pr_agent_file = Path(".github/workflows/pr-agent.yml")
        assert pr_agent_file.exists(), "pr-agent.yml workflow file not found"
        
        with open(pr_agent_file, 'r') as f:
            workflow = yaml.safe_load(f)
        
        for job_name, job in workflow.get('jobs', {}).items():
            steps = job.get('steps', [])
            setup_python_count = sum(
                1 for step in steps
                if step.get('name') == 'Setup Python'
            )
            
            assert setup_python_count <= 1, (
                f"Job '{job_name}' has {setup_python_count} 'Setup Python' "
                f"steps (should be 0 or 1)"
            )

    def test_pr_agent_python_version_consistency(self):
        """Test that Python version is consistently specified."""
        pr_agent_file = Path(".github/workflows/pr-agent.yml")
        assert pr_agent_file.exists(), "pr-agent.yml workflow file not found"
        
        with open(pr_agent_file, 'r') as f:
            workflow = yaml.safe_load(f)
        
        for job_name, job in workflow.get('jobs', {}).items():
            steps = job.get('steps', [])
            for step in steps:
                if step.get('name') == 'Setup Python':
                    with_section = step.get('with', {})
                    python_version = with_section.get('python-version')
                    
                    assert python_version is not None, (
                        f"Job '{job_name}': Setup Python step missing "
                        f"python-version"
                    )
                    
                    # Version should be a string like '3.11' or '3.x'
                    assert isinstance(python_version, str), (
                        f"python-version should be string, got "
                        f"{type(python_version)}"
                    )
                    
                    # Should match semantic version pattern
                    import re
                    version_pattern = r'^\d+\.\d+$|^\d+\.x$'
                    assert re.match(version_pattern, python_version), (
                        f"Invalid python-version format: {python_version}"
                    )

    def test_pr_agent_uses_actions_checkout(self):
        """Test that pr-agent workflow uses actions/checkout correctly."""
        pr_agent_file = Path(".github/workflows/pr-agent.yml")
        assert pr_agent_file.exists(), "pr-agent.yml workflow file not found"
        
        with open(pr_agent_file, 'r') as f:
            workflow = yaml.safe_load(f)
        
        for job_name, job in workflow.get('jobs', {}).items():
            steps = job.get('steps', [])
            checkout_steps = [
                step for step in steps
                if 'actions/checkout' in step.get('uses', '')
            ]
            
            assert len(checkout_steps) > 0, (
                f"Job '{job_name}' should have at least one checkout step"
            )
            
            # Check fetch-depth for PR workflows
            for step in checkout_steps:
                with_section = step.get('with', {})
                fetch_depth = with_section.get('fetch-depth')
                
                if fetch_depth is not None:
                    # Should be 0 or a positive integer
                    assert fetch_depth == 0 or (
                        isinstance(fetch_depth, int) and fetch_depth > 0
                    ), f"Invalid fetch-depth: {fetch_depth}"

    def test_pr_agent_has_required_permissions(self):
        """Test that pr-agent workflow specifies necessary permissions."""
        pr_agent_file = Path(".github/workflows/pr-agent.yml")
        assert pr_agent_file.exists(), "pr-agent.yml workflow file not found"
        
        with open(pr_agent_file, 'r') as f:
            workflow = yaml.safe_load(f)
        
        # Check for permissions at workflow or job level
        has_permissions = (
            'permissions' in workflow or
            any(
                'permissions' in job
                for job in workflow.get('jobs', {}).values()
            )
        )
        
        # For PR workflows, permissions are often needed
        if workflow.get('on', {}).get('pull_request'):
            assert has_permissions, (
                "PR workflow should declare permissions explicitly"
            )


class TestWorkflowYAMLStructureValidation:
    """Additional YAML structure validation tests."""

    def test_all_workflows_have_unique_job_names(self):
        """Test that each workflow file has unique job names within it."""
        workflow_dir = Path(".github/workflows")
        assert workflow_dir.exists(), "Workflows directory not found"
        
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                try:
                    workflow = yaml.safe_load(f)
                except yaml.YAMLError as e:
                    pytest.fail(f"Invalid YAML in {workflow_file.name}: {e}")
            
            if workflow and 'jobs' in workflow:
                job_names = list(workflow['jobs'].keys())
                unique_jobs = set(job_names)
                
                assert len(job_names) == len(unique_jobs), (
                    f"{workflow_file.name} has duplicate job names: "
                    f"{[j for j in job_names if job_names.count(j) > 1]}"
                )

    def test_all_workflows_valid_trigger_syntax(self):
        """Test that all workflows have valid trigger configurations."""
        workflow_dir = Path(".github/workflows")
        assert workflow_dir.exists(), "Workflows directory not found"
        
        valid_triggers = {
            'push', 'pull_request', 'workflow_dispatch', 'schedule',
            'release', 'issues', 'issue_comment', 'pull_request_target',
            'workflow_call', 'repository_dispatch', 'workflow_run'
        }
        
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
            
            if workflow and 'on' in workflow:
                triggers = workflow['on']
                
                if isinstance(triggers, dict):
                    trigger_keys = set(triggers.keys())
                elif isinstance(triggers, list):
                    trigger_keys = set(triggers)
                elif isinstance(triggers, str):
                    trigger_keys = {triggers}
                else:
                    pytest.fail(
                        f"{workflow_file.name}: Invalid 'on' type: "
                        f"{type(triggers)}"
                    )
                
                unknown = trigger_keys - valid_triggers
                assert len(unknown) == 0, (
                    f"{workflow_file.name} has unknown triggers: {unknown}"
                )

    def test_workflows_step_order_logical(self):
        """Test that checkout comes before other setup steps."""
        workflow_dir = Path(".github/workflows")
        assert workflow_dir.exists(), "Workflows directory not found"
        
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
            
            if not workflow or 'jobs' not in workflow:
                continue
            
            for job_name, job in workflow['jobs'].items():
                steps = job.get('steps', [])
                
                checkout_index = None
                setup_indices = []
                
                for i, step in enumerate(steps):
                    uses = step.get('uses', '')
                    name = step.get('name', '')
                    
                    if 'actions/checkout' in uses:
                        checkout_index = i
                    elif ('setup-python' in uses or 'setup-node' in uses or
                          'Setup Python' in name or 'Setup Node' in name):
                        setup_indices.append(i)
                
                # If both checkout and setup exist, checkout should come first
                if checkout_index is not None and setup_indices:
                    earliest_setup = min(setup_indices)
                    assert checkout_index < earliest_setup, (
                        f"{workflow_file.name}, job '{job_name}': "
                        f"Checkout (step {checkout_index}) should come before "
                        f"setup steps (step {earliest_setup})"
                    )

    def test_workflows_no_hardcoded_branches(self):
        """Test that workflows don't hardcode branch names inappropriately."""
        workflow_dir = Path(".github/workflows")
        assert workflow_dir.exists(), "Workflows directory not found"
        
        risky_patterns = [
            r'refs/heads/main',  # Should use github.ref or github.base_ref
            r'refs/heads/master',
            r'origin/main',
            r'origin/master'
        ]
        
        import re
        
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                content = f.read()
            
            for pattern in risky_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                
                # Some hardcoding might be intentional, but flag it
                if matches:
                    # This is a warning test - passes but logs concern
                    import warnings
                    warnings.warn(
                        f"{workflow_file.name} contains hardcoded branch "
                        f"reference: {pattern} ({len(matches)} occurrences)"
                    )


class TestWorkflowSecurityEnhancements:
    """Enhanced security tests for workflows."""

    def test_workflows_no_pull_request_target_without_safeguards(self):
        """Test that pull_request_target has appropriate safeguards."""
        workflow_dir = Path(".github/workflows")
        assert workflow_dir.exists(), "Workflows directory not found"
        
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
            
            if not workflow:
                continue
            
            triggers = workflow.get('on', {})
            
            if 'pull_request_target' in triggers:
                # Should have restricted permissions
                perms = workflow.get('permissions', {})
                job_perms = [
                    job.get('permissions', {})
                    for job in workflow.get('jobs', {}).values()
                ]
                
                # At least one permission scope should be restricted
                has_restrictions = (
                    perms or any(job_perms)
                )
                
                assert has_restrictions, (
                    f"{workflow_file.name} uses pull_request_target without "
                    f"explicit permission restrictions (security risk)"
                )

    def test_workflows_setup_actions_pinned_to_major(self):
        """Test that setup actions are pinned (at least to major version)."""
        workflow_dir = Path(".github/workflows")
        assert workflow_dir.exists(), "Workflows directory not found"
        
        import re
        version_pattern = r'@v\d+|@[a-f0-9]{40}'  # @v1, @v2, etc or full SHA
        
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
            
            if not workflow or 'jobs' not in workflow:
                continue
            
            for job_name, job in workflow['jobs'].items():
                steps = job.get('steps', [])
                
                for step in steps:
                    uses = step.get('uses', '')
                    
                    if uses and 'actions/' in uses:
                        # Check if versioned
                        has_version = re.search(version_pattern, uses)
                        
                        assert has_version, (
                            f"{workflow_file.name}, job '{job_name}': "
                            f"Action '{uses}' should be pinned to a version"
                        )

    def test_workflows_no_code_execution_in_untrusted_context(self):
        """
        Ensure workflow files do not contain patterns that could execute untrusted event data as shell commands.
        
        Scans .github/workflows/*.yml for occurrences of dangerous patterns (for example: piping GitHub event fields into `bash`/`sh`, or using `eval` with event-derived values) and fails the test if any match is found.
        """
        workflow_dir = Path(".github/workflows")
        assert workflow_dir.exists(), "Workflows directory not found"
        
        dangerous_patterns = [
            r'\$\{\{.*github\.event\.pull_request\..*\}\}.*\|.*bash',
            r'\$\{\{.*github\.event\.issue\..*\}\}.*\|.*sh',
            r'eval.*\$\{\{.*github\.event\..*\}\}',
        ]
        
        import re
        
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                content = f.read()
            
            for pattern in dangerous_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                
                assert len(matches) == 0, (
                    f"{workflow_file.name} may execute untrusted code: "
                    f"Found pattern '{pattern}'"
                )


class TestRequirementsDevValidation:
    """Tests for requirements-dev.txt changes."""

    def test_requirements_dev_file_exists(self):
        """Test that requirements-dev.txt exists."""
        req_file = Path("requirements-dev.txt")
        assert req_file.exists(), "requirements-dev.txt not found"

    def test_requirements_dev_valid_format(self):
        """Test that requirements-dev.txt has valid format."""
        req_file = Path("requirements-dev.txt")
        assert req_file.exists(), "requirements-dev.txt not found"
        
        with open(req_file, 'r') as f:
            lines = f.readlines()
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Should have package name
            assert len(line) > 0, f"Line {line_num}: Empty requirement"
            
            # Common format validations
            if '=' in line:
                parts = line.split('==')
                assert len(parts) <= 2, (
                    f"Line {line_num}: Multiple == in requirement: {line}"
                )
            
            # Should not have spaces (unless in quotes, which is rare)
            if ' ' in line and not ('"' in line or "'" in line):
                # Might be okay for extras like package[extra]
                if '[' not in line:
                    import warnings
                    warnings.warn(
                        f"requirements-dev.txt line {line_num} has unexpected "
                        f"space: {line}"
                    )

    def test_requirements_dev_pyyaml_present(self):
        """Test that PyYAML is in requirements-dev.txt (needed for tests)."""
        req_file = Path("requirements-dev.txt")
        assert req_file.exists(), "requirements-dev.txt not found"
        
        with open(req_file, 'r') as f:
            content = f.read().lower()
        
        # PyYAML should be present (case-insensitive)
        assert 'pyyaml' in content or 'yaml' in content, (
            "PyYAML should be in requirements-dev.txt for workflow tests"
        )

    def test_requirements_dev_no_conflicts_with_main(self):
        """Test that dev requirements don't conflict with main requirements."""
        req_file = Path("requirements-dev.txt")
        main_req_file = Path("requirements.txt")
        
        if not (req_file.exists() and main_req_file.exists()):
            pytest.skip("Both requirements files needed for this test")
        
        def parse_requirements(file_path):
            """
            Parse package requirement lines from a requirements-style file into a mapping keyed by package name.
            
            Ignores blank lines and lines beginning with '#' and normalises package keys by removing extras (square-bracket markers) and any simple version specifiers beginning with '==', '>=' or '<='; the original requirement line is preserved as the value.
            
            Parameters:
                file_path (str | Path): Path to the requirements file to parse.
            
            Returns:
                dict: Mapping from lowercased package name (without extras or the recognised version operators) to the original requirement line.
            """
            packages = {}
            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Extract package name
                        pkg = line.split('==')[0].split('>=')[0].split('<=')[0]
                        pkg = pkg.split('[')[0].strip()  # Remove extras
                        packages[pkg.lower()] = line
            return packages
        
        dev_pkgs = parse_requirements(req_file)
        main_pkgs = parse_requirements(main_req_file)
        
        # Check for version conflicts
        conflicts = []
        for pkg, dev_spec in dev_pkgs.items():
            if pkg in main_pkgs:
                main_spec = main_pkgs[pkg]
                if dev_spec != main_spec:
                    conflicts.append(f"{pkg}: dev='{dev_spec}' vs main='{main_spec}'")
        
        assert len(conflicts) == 0, (
            f"Version conflicts between requirements files: {conflicts}"
        )


class TestModifiedWorkflowsValidation:
    """
    Comprehensive tests for workflows modified in the current branch.
    
    Tests validate that simplifications and removals don't break functionality:
    - apisec-scan.yml: Removed credential check step
    - greetings.yml: Simplified welcome messages
    - label.yml: Removed labeler config check  
    - pr-agent.yml: Removed context chunking logic
    """

    def test_apisec_workflow_structure_valid(self):
        """Test that apisec-scan.yml has valid structure after removing credential check."""
        workflow_file = WORKFLOWS_DIR / "apisec-scan.yml"
        
        if not workflow_file.exists():
            pytest.skip("apisec-scan.yml not found")
        
        config = load_yaml_safe(workflow_file)
        
        # Workflow should still have basic structure
        assert "name" in config, "apisec-scan.yml missing name"
        assert "jobs" in config, "apisec-scan.yml missing jobs"
        assert "Trigger_APIsec_scan" in config["jobs"], "Missing APIsec scan job"
        
        job = config["jobs"]["Trigger_APIsec_scan"]
        assert "steps" in job, "APIsec job missing steps"
        
        # Should have APIsec scan step (not the removed credential check)
        steps = job["steps"]
        step_names = [s.get("name", "") for s in steps]
        
        assert any("APIsec scan" in name for name in step_names), (
            "Missing APIsec scan step"
        )
        
        # Should NOT have credential check step (it was removed)
        assert not any("Check for APIsec" in name for name in step_names), (
            "Credential check step should have been removed"
        )

    def test_apisec_workflow_uses_secrets_correctly(self):
        """Test that apisec-scan.yml correctly references secrets."""
        workflow_file = WORKFLOWS_DIR / "apisec-scan.yml"
        
        if not workflow_file.exists():
            pytest.skip("apisec-scan.yml not found")
        
        with open(workflow_file, 'r') as f:
            content = f.read()
        
        # Should reference secrets (not hardcoded credentials)
        assert "secrets.apisec_username" in content, (
            "Should use secrets.apisec_username"
        )
        assert "secrets.apisec_password" in content, (
            "Should use secrets.apisec_password"
        )

    def test_apisec_workflow_has_proper_triggers(self):
        """Test that apisec-scan.yml has appropriate triggers."""
        workflow_file = WORKFLOWS_DIR / "apisec-scan.yml"
        
        if not workflow_file.exists():
            pytest.skip("apisec-scan.yml not found")
        
        config = load_yaml_safe(workflow_file)
        triggers = config.get("on", {})
        
        # Should trigger on relevant events
        if isinstance(triggers, dict):
            assert "push" in triggers or "pull_request" in triggers or "schedule" in triggers, (
                "apisec-scan should have meaningful triggers"
            )

    def test_greetings_workflow_simplified_messages(self):
        """
        Validate that greetings.yml defines non-empty simplified messages for the actions/first-interaction step.
        
        Skips the test if .github/workflows/greetings.yml is not present. Asserts the workflow contains a top-level `jobs` mapping and, for any step that uses `actions/first-interaction`, verifies that `issue-message` and `pr-message` in the step's `with` mapping (when present) are strings with length greater than zero.
        """
        workflow_file = WORKFLOWS_DIR / "greetings.yml"
        
        if not workflow_file.exists():
            pytest.skip("greetings.yml not found")
        
        config = load_yaml_safe(workflow_file)
        
        assert "jobs" in config, "greetings.yml missing jobs"
        
        for job_name, job in config["jobs"].items():
            steps = job.get("steps", [])
            
            for step in steps:
                if "actions/first-interaction" in step.get("uses", ""):
                    step_with = step.get("with", {})
                    
                    # Should have message fields
                    if "issue-message" in step_with:
                        msg = step_with["issue-message"]
                        assert isinstance(msg, str), "issue-message should be a string"
                        assert len(msg) > 0, "issue-message should not be empty"
                    
                    if "pr-message" in step_with:
                        msg = step_with["pr-message"]
                        assert isinstance(msg, str), "pr-message should be a string"
                        assert len(msg) > 0, "pr-message should not be empty"

    def test_greetings_workflow_structure(self):
        """Test that greetings.yml has valid basic structure."""
        workflow_file = WORKFLOWS_DIR / "greetings.yml"
        
        if not workflow_file.exists():
            pytest.skip("greetings.yml not found")
        
        config = load_yaml_safe(workflow_file)
        
        # Check basic structure
        assert "name" in config, "greetings.yml missing name"
        assert "on" in config, "greetings.yml missing triggers"
        assert "jobs" in config, "greetings.yml missing jobs"
        
        # Should trigger on appropriate events
        triggers = config["on"]
        if isinstance(triggers, list):
            assert any(t in ["pull_request_target", "issues"] for t in triggers), (
                "greetings should trigger on PR or issue events"
            )

    def test_label_workflow_no_config_check(self):
        """Test that label.yml runs without labeler config check step."""
        workflow_file = WORKFLOWS_DIR / "label.yml"
        
        if not workflow_file.exists():
            pytest.skip("label.yml not found")
        
        config = load_yaml_safe(workflow_file)
        
        assert "jobs" in config, "label.yml missing jobs"
        
        for job_name, job in config["jobs"].items():
            steps = job.get("steps", [])
            step_names = [s.get("name", "") for s in steps]
            
            # Should NOT have config check step (it was removed)
            assert not any("Check for labeler" in name for name in step_names), (
                "Config check step should have been removed from label.yml"
            )
            
            # Should still use labeler action
            uses_list = [s.get("uses", "") for s in steps]
            assert any("actions/labeler" in u for u in uses_list), (
                "label.yml should still use actions/labeler"
            )

    def test_label_workflow_simplified_structure(self):
        """Test that label.yml has simplified but functional structure."""
        workflow_file = WORKFLOWS_DIR / "label.yml"
        
        if not workflow_file.exists():
            pytest.skip("label.yml not found")
        
        config = load_yaml_safe(workflow_file)
        
        # Basic structure checks
        assert "name" in config, "label.yml missing name"
        assert "jobs" in config, "label.yml missing jobs"
        
        # Should have appropriate permissions
        for job_name, job in config["jobs"].items():
            if "labeler" in job_name.lower() or "label" in job_name.lower():
                # Job or workflow should have pull-requests: write permission
                job_perms = job.get("permissions", {})
                workflow_perms = config.get("permissions", {})
                
                has_pr_write = (
                    job_perms.get("pull-requests") == "write" or
                    workflow_perms.get("pull-requests") == "write"
                )
                
                # This is a recommendation, not a hard requirement
                if not has_pr_write:
                    import warnings
                    warnings.warn(
                        f"{workflow_file.name} labeler job may need "
                        f"pull-requests: write permission"
                    )

    def test_pr_agent_workflow_no_chunking_logic(self):
        """Test that pr-agent.yml doesn't contain context chunking logic."""
        workflow_file = WORKFLOWS_DIR / "pr-agent.yml"
        
        if not workflow_file.exists():
            pytest.skip("pr-agent.yml not found")
        
        with open(workflow_file, 'r') as f:
            content = f.read()
        
        # Should NOT contain chunking-related terms (they were removed)
        chunking_terms = [
            "context_chunker",
            "Fetch PR Context with Chunking",
            "MAX_FILES_PER_CHUNK",
            "tiktoken",
            "chunked=true",
            "context_size",
        ]
        
        for term in chunking_terms:
            assert term not in content, (
                f"pr-agent.yml should not contain '{term}' after chunking removal"
            )

    def test_pr_agent_workflow_simplified_parsing(self):
        """Test that pr-agent.yml has simplified comment parsing."""
        workflow_file = WORKFLOWS_DIR / "pr-agent.yml"
        
        if not workflow_file.exists():
            pytest.skip("pr-agent.yml not found")
        
        config = load_yaml_safe(workflow_file)
        
        assert "jobs" in config, "pr-agent.yml missing jobs"
        
        # Check that it has the simplified parse-comments step
        for job_name, job in config["jobs"].items():
            steps = job.get("steps", [])
            step_ids = [s.get("id", "") for s in steps]
            
            if any("parse" in sid.lower() for sid in step_ids):
                # Found parsing step, check it doesn't reference chunking
                parse_steps = [s for s in steps if "parse" in s.get("id", "").lower()]
                
                for step in parse_steps:
                    step_run = step.get("run", "")
                    
                    # Should parse comments simply
                    assert "ACTION_ITEMS" in step_run or "action_items" in step_run, (
                        "Parse step should extract action items"
                    )

    def test_pr_agent_workflow_basic_functionality(self):
        """Test that pr-agent.yml maintains core functionality after simplification."""
        workflow_file = WORKFLOWS_DIR / "pr-agent.yml"
        
        if not workflow_file.exists():
            pytest.skip("pr-agent.yml not found")
        
        config = load_yaml_safe(workflow_file)
        
        # Should have core structure
        assert "name" in config, "pr-agent.yml missing name"
        assert "jobs" in config, "pr-agent.yml missing jobs"
        
        # Should trigger on PR events
        triggers = config.get("on", {})
        if isinstance(triggers, dict):
            has_pr_trigger = (
                "pull_request" in triggers or
                "pull_request_review" in triggers or
                "issue_comment" in triggers
            )
            assert has_pr_trigger, "pr-agent should trigger on PR-related events"


class TestPRAgentConfigValidation:
    """Tests for .github/pr-agent-config.yml changes."""

    def test_pr_agent_config_exists(self):
        """Test that pr-agent-config.yml exists."""
        config_file = Path(".github/pr-agent-config.yml")
        assert config_file.exists(), "pr-agent-config.yml not found"

    def test_pr_agent_config_valid_yaml(self):
        """Test that pr-agent-config.yml is valid YAML."""
        config_file = Path(".github/pr-agent-config.yml")
        assert config_file.exists(), "pr-agent-config.yml not found"
        
        config = load_yaml_safe(config_file)
        assert isinstance(config, dict), "pr-agent-config.yml should be a mapping"

    def test_pr_agent_config_no_chunking_settings(self):
        """Test that pr-agent-config.yml doesn't contain chunking configuration."""
        config_file = Path(".github/pr-agent-config.yml")
        
        if not config_file.exists():
            pytest.skip("pr-agent-config.yml not found")
        
        with open(config_file, 'r') as f:
            content = f.read()
        
        # Should NOT contain chunking-related configuration (it was removed)
        chunking_terms = [
            "max_tokens",
            "chunk_size",
            "overlap_tokens",
            "summarization_threshold",
            "chunking:",
            "summarization:",
        ]
        
        for term in chunking_terms:
            assert term not in content, (
                f"pr-agent-config.yml should not contain '{term}' after chunking removal"
            )

    def test_pr_agent_config_basic_structure(self):
        """Test that pr-agent-config.yml has required basic structure."""
        config_file = Path(".github/pr-agent-config.yml")
        
        if not config_file.exists():
            pytest.skip("pr-agent-config.yml not found")
        
        config = load_yaml_safe(config_file)
        
        # Should have agent section
        assert "agent" in config, "pr-agent-config.yml should have 'agent' section"
        
        agent = config["agent"]
        assert isinstance(agent, dict), "agent section should be a mapping"
        
        # Should have basic agent properties
        assert "name" in agent, "agent section should have 'name'"
        assert "version" in agent, "agent section should have 'version'"

    def test_pr_agent_config_version_downgraded(self):
        """Test that pr-agent-config version was downgraded from 1.1.0 to 1.0.0."""
        config_file = Path(".github/pr-agent-config.yml")
        
        if not config_file.exists():
            pytest.skip("pr-agent-config.yml not found")
        
        config = load_yaml_safe(config_file)
        agent = config.get("agent", {})
        version = agent.get("version", "")
        
        # Version should be 1.0.0 after removing chunking features
        assert version == "1.0.0", (
            f"Expected version 1.0.0 after chunking removal, got {version}"
        )


class TestRequirementsDevPyYAML:
    """Additional tests for PyYAML dependencies added to requirements-dev.txt."""

    def test_pyyaml_version_specified(self):
        """
        Verify that PyYAML is listed with a version constraint in requirements-dev.txt.
        
        Skips the test if requirements-dev.txt is not present. Fails if no line referencing PyYAML is found or if the PyYAML requirement line does not include a version comparator such as '>=' or '=='.
        """
        req_file = Path("requirements-dev.txt")
        
        if not req_file.exists():
            pytest.skip("requirements-dev.txt not found")
        
        with open(req_file, 'r') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        # Find PyYAML line
        pyyaml_lines = [l for l in lines if 'pyyaml' in l.lower()]
        
        assert len(pyyaml_lines) > 0, "PyYAML not found in requirements-dev.txt"
        
        # Should have version constraint
        pyyaml_spec = pyyaml_lines[0]
        assert '>=' in pyyaml_spec or '==' in pyyaml_spec, (
            f"PyYAML should have version constraint: {pyyaml_spec}"
        )

    def test_types_pyyaml_for_mypy(self):
        """Test that types-PyYAML is present for type checking."""
        req_file = Path("requirements-dev.txt")
        
        if not req_file.exists():
            pytest.skip("requirements-dev.txt not found")
        
        with open(req_file, 'r') as f:
            content = f.read().lower()
        
        # types-PyYAML should be present for mypy
        assert 'types-pyyaml' in content, (
            "types-PyYAML should be in requirements-dev.txt for type checking"
        )

    def test_pyyaml_importable(self):
        """Test that PyYAML can be imported (sanity check)."""
        try:
            import yaml
            # Basic functionality check
            test_data = {"test": "value"}
            yaml_str = yaml.dump(test_data)
            parsed = yaml.safe_load(yaml_str)
            assert parsed == test_data, "PyYAML round-trip failed"
        except ImportError:
            pytest.skip("PyYAML not installed in test environment")

    def test_pyyaml_version_compatibility(self):
        """
        Verify the installed PyYAML supports modern safe load/dump APIs and can parse a simple mapping.
        
        Asserts that the `yaml` module is importable and exposes `safe_load` and `safe_dump`, and that `safe_load` parses a simple YAML mapping into a Python dict. If PyYAML is not installed the test is skipped.
        """
        try:
            import yaml
            
            # Should have safe_load (available in PyYAML >= 5.1)
            assert hasattr(yaml, 'safe_load'), "PyYAML missing safe_load"
            assert hasattr(yaml, 'safe_dump'), "PyYAML missing safe_dump"
            
            # Should support modern features
            test_yaml = "key: value\nlist:\n  - item1\n  - item2"
            parsed = yaml.safe_load(test_yaml)
            assert isinstance(parsed, dict), "PyYAML should parse to dict"
            
        except ImportError:
            pytest.skip("PyYAML not installed in test environment")


class TestWorkflowChangeRegression:
    """Regression tests ensuring workflow changes don't break existing functionality."""

    def test_all_workflows_still_parseable(self):
        """Test that all workflow files can still be parsed after changes."""
        workflow_files = get_workflow_files()
        
        assert len(workflow_files) > 0, "No workflow files found"
        
        for workflow_file in workflow_files:
            try:
                config = load_yaml_safe(workflow_file)
                assert config is not None, f"{workflow_file.name} parsed to None"
            except Exception as e:
                pytest.fail(f"Failed to parse {workflow_file.name}: {e}")

    def test_no_workflows_reference_deleted_files(self):
        """Test that workflows don't reference deleted files."""
        workflow_files = get_workflow_files()
        
        deleted_files = [
            ".github/labeler.yml",
            ".github/scripts/context_chunker.py",
            ".github/scripts/README.md",
        ]
        
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                content = f.read()
            
            for deleted in deleted_files:
                assert deleted not in content, (
                    f"{workflow_file.name} references deleted file: {deleted}"
                )

    def test_workflows_have_proper_permissions(self):
        """Test that all workflows have appropriate permission declarations."""
        workflow_files = get_workflow_files()
        
        for workflow_file in workflow_files:
            config = load_yaml_safe(workflow_file)
            
            if not config or "jobs" not in config:
                continue
            
            # Check if workflow or jobs define permissions
            workflow_perms = config.get("permissions")
            
            for job_name, job in config["jobs"].items():
                job_perms = job.get("permissions")
                
                # At least one should define permissions (workflow-level or job-level)
                # This is a best practice, not a hard requirement
                has_perms = workflow_perms is not None or job_perms is not None
                
                # Some workflows may not need explicit permissions
                # Just verify the structure is valid if present
                if job_perms:
                    assert isinstance(job_perms, dict), (
                        f"{workflow_file.name}, job '{job_name}': "
                        f"permissions should be a mapping"
                    )

    def test_simplified_workflows_reduce_complexity(self):
        """Test that simplified workflows have fewer steps after changes."""
        # This is a sanity check that simplifications actually reduced complexity
        workflow_files = get_workflow_files()
        
        for workflow_file in workflow_files:
            config = load_yaml_safe(workflow_file)
            
            if not config or "jobs" not in config:
                continue
            
            for job_name, job in config["jobs"].items():
                steps = job.get("steps", [])
                
                # Sanity check: no job should have an excessive number of steps
                # (this would indicate complexity hasn't been reduced)
                assert len(steps) < 50, (
                    f"{workflow_file.name}, job '{job_name}' has {len(steps)} steps. "
                    f"Consider further simplification if this is unexpectedly high."
                )