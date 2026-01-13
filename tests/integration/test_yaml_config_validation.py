"""
Comprehensive YAML configuration validation tests.

Validates:
1. YAML syntax and structure
2. Schema compliance
3. Edge cases and boundary conditions
4. Configuration consistency
5. Default value handling
"""

import re
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml


class TestYAMLSyntaxAndStructure:
    """Tests for YAML syntax and structural validity."""

    def test_all_yaml_files_parse_successfully(self):
        """Verify all YAML files have valid syntax."""
        yaml_files = []

        # Find all YAML files in .github
        for yaml_file in Path(".github").rglob("*.yml"):
            yaml_files.append(yaml_file)
        for yaml_file in Path(".github").rglob("*.yaml"):
            yaml_files.append(yaml_file)

        parse_errors = []
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, "r") as f:
                    yaml.safe_load(f)
            except yaml.YAMLError as e:
                parse_errors.append(f"{yaml_file}: {str(e)}")

        assert len(parse_errors) == 0, f"YAML parse errors:\n" + "\n".join(parse_errors)

    def test_yaml_files_use_consistent_indentation(self):
        """Ensure YAML files use consistent 2-space indentation, respecting block scalars."""
        yaml_files = list(Path(".github").rglob("*.yml")) + list(Path(".github").rglob("*.yaml"))
        indentation_errors = []

        for yaml_file in yaml_files:
            try:
                content = Path(yaml_file).read_text(encoding="utf-8")
            except Exception as e:
                indentation_errors.append(f"{yaml_file}: unable to read file: {e}")
                continue

            lines = content.split("\n")
            in_block_scalar = False
            block_scalar_indent = None

            for line_no, line in enumerate(lines, 1):
                stripped = line.lstrip(" ")
                leading_spaces = len(line) - len(stripped)

                # Skip empty lines and full-line comments
                if not stripped or stripped.startswith("#"):
                    continue

                # If currently inside a block scalar, continue until indentation returns
                if in_block_scalar:
                    # Exit block scalar when indentation is less than or equal to the scalar's parent indent
                    if leading_spaces <= block_scalar_indent:
                        in_block_scalar = False
                        block_scalar_indent = None
                    else:
                        # Still inside scalar; skip indentation checks
                        continue

                # Detect start of block scalars (| or > possibly with chomping/indent indicators)
                # Example: key: |-, key: >2, key: |+
                if re.search(r":\s*[|>](?:[+-]|\d+)?", line):
                    in_block_scalar = True
                    block_scalar_indent = leading_spaces
                    continue

                # Only check indentation on lines that begin with spaces (i.e., are indented content)
                if line[0] == " " and not line.startswith("  " * (leading_spaces // 2 + 1) + "- |"):
                    if leading_spaces % 2 != 0:
                        indentation_errors.append(
                            f"{yaml_file} line {line_no}: Use 2-space indentation, found {leading_spaces} spaces"
                        )

            # Reset flags per file (handled by reinitialization each loop)

        assert not indentation_errors, "Indentation errors found:\n" + "\n".join(indentation_errors)

    def test_no_duplicate_keys_in_yaml(self):
        """
        Check that no YAML files under .github contain duplicate keys by loading each file with ruamel.yaml's strict parser.

        Scans all .yml and .yaml files under the .github directory and attempts to load each with ruamel.yaml (typ="safe"). If ruamel.yaml is not installed, the test is skipped. Any parse or duplicate-key errors are collected and cause the test to fail with a consolidated error message.
        """
        try:
            from ruamel.yaml import YAML
        except ImportError:
            pytest.skip("ruamel.yaml not installed; skip strict duplicate key detection")

        yaml_files = list(Path(".github").rglob("*.yml")) + list(Path(".github").rglob("*.yaml"))
        parser = YAML(typ="safe")
        parse_errors = []

        for yaml_file in yaml_files:
            try:
                with open(yaml_file, "r") as f:
                    parser.load(f)
            except Exception as e:
                parse_errors.append(f"{yaml_file}: {e}")

        assert not parse_errors, "Duplicate keys or YAML errors detected:\n" + "\n".join(parse_errors)


class TestWorkflowSchemaCompliance:
    """Tests for GitHub Actions workflow schema compliance."""

    @pytest.fixture
    def all_workflows(self) -> List[Dict[str, Any]]:
        """
        Collects and parses all YAML workflow files found in .github/workflows.

        Returns:
            workflows (List[Dict[str, Any]]): A list of dictionaries, each containing:
                - 'path' (Path): Path to the workflow file.
                - 'content' (Any): Parsed YAML content as returned by yaml.safe_load (typically a dict, or None if the file is empty).
        """
        workflow_dir = Path(".github/workflows")
        workflows = []
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                workflows.append({"path": workflow_file, "content": yaml.safe_load(f)})
        return workflows

    def test_workflows_have_required_top_level_keys(self, all_workflows):
        """Verify workflows have all required top-level keys."""
        required_keys = ["name", "jobs"]

        for workflow in all_workflows:
            for key in required_keys:
                assert key in workflow["content"], f"Workflow {workflow['path']} missing required key: {key}"

    def test_workflow_triggers_valid_format(self, all_workflows):
        """Verify workflow triggers use valid format."""
        for workflow in all_workflows:
            # Check for 'on' or '"on"' key
            has_trigger = "on" in workflow["content"]
            assert has_trigger, f"Workflow {workflow['path']} missing trigger ('on' key)"

            triggers = workflow["content"].get("on") or workflow["content"].get('"on"')

            # Triggers can be: string, list, or dict
            assert isinstance(triggers, (str, list, dict)), f"Workflow {workflow['path']} has invalid trigger format"

    def test_job_definitions_valid(self, all_workflows):
        """
        Validate that each workflow defines at least one job and that each job contains required fields.

        For every workflow in `all_workflows` this test asserts:
        - the workflow defines at least one job,
        - each job has either a 'runs-on' key or a 'uses' key (for reusable workflows),
        - if a job includes 'steps', the 'steps' value is a list.

        Parameters:
            all_workflows (list): Sequence of workflow dictionaries, each containing 'path' (str) and 'content' (dict) with the parsed YAML.
        """
        for workflow in all_workflows:
            jobs = workflow["content"].get("jobs", {})

            assert len(jobs) > 0, f"Workflow {workflow['path']} has no jobs defined"

            for job_id, job_config in jobs.items():
                # Each job must have runs-on or uses
                has_runs_on = "runs-on" in job_config
                has_uses = "uses" in job_config  # For reusable workflows

                assert has_runs_on or has_uses, f"Job '{job_id}' in {workflow['path']} missing 'runs-on' or 'uses'"

                # If has steps, must be a list
                if "steps" in job_config:
                    assert isinstance(
                        job_config["steps"], list
                    ), f"Job '{job_id}' steps must be a list in {workflow['path']}"

    def test_step_definitions_valid(self, all_workflows):
        """
        Assert that every workflow step has a valid step definition: each step must include either the `uses` key or the `run` key, and must not include both.

        Parameters:
                all_workflows (list): Iterable of workflow mappings where each item is a dict with keys:
                        - 'path' (str): filesystem path of the workflow file
                        - 'content' (dict): parsed YAML content of the workflow
        """
        for workflow in all_workflows:
            jobs = workflow["content"].get("jobs", {})

            for job_id, job_config in jobs.items():
                steps = job_config.get("steps", [])

                for step_idx, step in enumerate(steps):
                    # Each step must have 'uses' or 'run'
                    has_uses = "uses" in step
                    has_run = "run" in step

                    assert has_uses or has_run, (
                        f"Step {step_idx} in job '{job_id}' of {workflow['path']} " f"must have 'uses' or 'run'"
                    )

                    # Steps should not have both uses and run
                    assert not (has_uses and has_run), (
                        f"Step {step_idx} in job '{job_id}' of {workflow['path']} " f"cannot have both 'uses' and 'run'"
                    )


class TestConfigurationEdgeCases:
    """Tests for edge cases in configuration files."""

    def test_pr_agent_config_handles_missing_sections_gracefully(self):
        """
        Ensure the PR agent YAML configuration contains required top-level sections.

        Asserts that .github/pr-agent-config.yml defines the top-level keys 'agent', 'monitoring', and 'limits'. If any are missing, the test fails with an assertion indicating the missing section.
        """
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        # Should have main sections
        expected_sections = ["agent", "monitoring", "limits"]
        for section in expected_sections:
            assert section in config, f"Missing section: {section}"

    def test_numeric_values_in_config_are_valid(self):
        """
        Validate numeric fields in .github/pr-agent-config.yml.

        Ensures that when present `monitoring.check_interval` is an integer between 1 and 60 (minutes) and `limits.rate_limit_requests` is an integer between 1 and 1000.
        """
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        # Check monitoring interval
        monitoring = config.get("monitoring", {})
        if "check_interval" in monitoring:
            interval = monitoring["check_interval"]
            assert isinstance(interval, int), "check_interval should be integer"
            assert 1 <= interval <= 60, "check_interval should be 1-60 minutes"

        # Check rate limits
        limits = config.get("limits", {})
        if "rate_limit_requests" in limits:
            rate_limit = limits["rate_limit_requests"]
            assert isinstance(rate_limit, int), "rate_limit_requests should be integer"
            assert 1 <= rate_limit <= 1000, "rate_limit_requests should be reasonable"

    def test_version_strings_follow_semver(self):
        """
        Check that the `agent.version` value in .github/pr-agent-config.yml, if present, follows semantic versioning in the form X.Y.Z.

        Raises:
            AssertionError: If `agent.version` exists and does not match the `X.Y.Z` pattern.
        """
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        agent_config = config.get("agent", {})
        if "version" in agent_config:
            version = agent_config["version"]
            # Should match semver pattern: X.Y.Z
            assert re.match(r"^\d+\.\d+\.\d+$", version), f"Version should follow semver (X.Y.Z): {version}"

    def test_empty_or_null_values_handled(self):
        """
        Ensure critical YAML fields are not null in files under .github.

        Recursively loads every `.yml` file under the `.github` directory and asserts that critical keys (`name`, `runs-on`, `uses`, `run`) are not `None`. Assertion messages include the YAML file path and the dotted/key-index path to the null value.
        """
        yaml_files = list(Path(".github").rglob("*.yml"))

        for yaml_file in yaml_files:
            with open(yaml_file, "r") as f:
                content = yaml.safe_load(f)

            # Check for null values in critical places
            def check_nulls(obj, path=""):
                """
                Recursively checks a parsed YAML structure for null values in critical keys and fails the test if any are found.

                Traverses dictionaries and lists within `obj`. If a dictionary contains any of the critical keys 'name', 'runs-on', 'uses', or 'run' with a value of `None`, an AssertionError is raised identifying the full key path. The error message includes the key path and the surrounding `yaml_file` identifier from the enclosing scope.

                Parameters:
                    obj: The parsed YAML fragment (dict, list, or scalar) to inspect.
                    path (str): Dot-and-index-separated path prefix used to report the location of a null value (defaults to the empty string).
                """
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        current_path = f"{path}.{key}" if path else key

                        # Critical keys should not be null
                        critical_keys = ["name", "runs-on", "uses", "run"]
                        if key in critical_keys:
                            assert value is not None, f"Critical key '{current_path}' is null in {yaml_file}"

                        check_nulls(value, current_path)
                elif isinstance(obj, list):
                    for idx, item in enumerate(obj):
                        check_nulls(item, f"{path}[{idx}]")

            check_nulls(content)


class TestConfigurationConsistency:
    """Tests for configuration consistency across files."""

    def test_python_version_consistent_across_workflows(self):
        """Verify Python version is consistent across all workflows."""
        workflow_dir = Path(".github/workflows")
        python_versions = {}

        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                workflow = yaml.safe_load(f)

            jobs = workflow.get("jobs", {})
            for _, job_config in jobs.items():
                steps = job_config.get("steps", [])
                for step in steps:
                    if "actions/setup-python" in step.get("uses", ""):
                        version = step.get("with", {}).get("python-version")
                        if version:
                            python_versions[workflow_file.name] = version

        # All should use same Python version
        if python_versions:
            unique_versions = set(python_versions.values())
            assert len(unique_versions) == 1, f"Inconsistent Python versions across workflows: {python_versions}"

    def test_node_version_consistent_across_workflows(self):
        """Verify Node.js version is consistent across all workflows."""
        workflow_dir = Path(".github/workflows")
        node_versions = {}

        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                workflow = yaml.safe_load(f)

            jobs = workflow.get("jobs", {})
            for _, job_config in jobs.items():
                steps = job_config.get("steps", [])
                for step in steps:
                    if "actions/setup-node" in step.get("uses", ""):
                        version = step.get("with", {}).get("node-version")
                        if version:
                            node_versions[workflow_file.name] = str(version)

        # All should use same Node version
        if node_versions:
            unique_versions = set(node_versions.values())
            assert len(unique_versions) == 1, f"Inconsistent Node versions across workflows: {node_versions}"

    def test_checkout_action_version_consistent(self):
        """
        Ensure actions/checkout versions used across workflows are consistent.

        Scans all YAML files in .github/workflows for occurrences of `actions/checkout@<version>`,
        collects the versions per workflow file, and asserts there are at most two distinct
        versions found (allows minor variation such as v3 and v4).
        """
        workflow_dir = Path(".github/workflows")
        checkout_versions = {}

        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                workflow = yaml.safe_load(f)

            jobs = workflow.get("jobs", {})
            for _, job_config in jobs.items():
                steps = job_config.get("steps", [])
                for step in steps:
                    uses = step.get("uses", "")
                    if "actions/checkout@" in uses:
                        version = uses.split("@")[1]
                        checkout_versions[workflow_file.name] = version

        # Should be consistent
        if checkout_versions:
            unique_versions = set(checkout_versions.values())
            # Allow v3 and v4, but should be mostly consistent
            assert len(unique_versions) <= 2, f"Too many different checkout versions: {checkout_versions}"


class TestDefaultValueHandling:
    """Tests for default value handling in configurations."""

    def test_missing_optional_fields_have_defaults(self):
        """
        Ensure optional fields in .github/pr-agent-config.yml are handled and validated.

        Asserts that if the top-level `agent` section includes an `enabled` key, its value is a boolean; omission of `enabled` is permitted and treated as the configuration's default.
        """
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        # These fields should have defaults if not specified
        agent_config = config.get("agent", {})

        # If enabled is not specified, should default to true
        if "enabled" in agent_config:
            assert isinstance(agent_config["enabled"], bool)

    def test_workflow_timeout_defaults(self):
        """
        Ensure job-level workflow timeouts, when specified, are integers between 1 and 360 minutes.

        Checks each YAML file in .github/workflows for jobs that include 'timeout-minutes' and asserts the value is an int and within the range 1–360.
        """
        workflow_dir = Path(".github/workflows")

        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                workflow = yaml.safe_load(f)

            jobs = workflow.get("jobs", {})
            for job_id, job_config in jobs.items():
                if "timeout-minutes" in job_config:
                    timeout = job_config["timeout-minutes"]
                    assert isinstance(timeout, int), f"Timeout should be integer in {workflow_file} job '{job_id}'"
                    assert 1 <= timeout <= 360, f"Timeout should be 1-360 minutes in {workflow_file} job '{job_id}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
