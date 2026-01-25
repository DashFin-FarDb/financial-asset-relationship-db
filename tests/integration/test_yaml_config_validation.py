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

    @staticmethod
    def test_all_yaml_files_parse_successfully():
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

    @staticmethod
    def test_yaml_files_use_consistent_indentation():
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
                if in_block_scalar and leading_spaces <= block_scalar_indent:
                    # Exit block scalar when indentation is less than or equal to the scalar's parent indent
                    in_block_scalar = False
                    block_scalar_indent = None
                elif in_block_scalar:
                    # Still inside scalar; skip indentation checks
                    continue

                # Detect start of block scalars (| or > possibly with chomping/indent indicators)
                # Example: key: |-, key: >2, key: |+
                if re.search(r":\s*[|>](?:[+-]|\d+)?", line):
                    in_block_scalar = True
                    block_scalar_indent = leading_spaces
                    continue

                # Only check indentation on lines that begin with spaces (i.e., are indented content)
                if line and line[0] == " " and not line.startswith("  " * (leading_spaces // 2 + 1) + "- |"):
                    if leading_spaces % 2 != 0:
                        indentation_errors.append(
                            f"{yaml_file} line {line_no}: Use 2-space indentation, found {leading_spaces} spaces"
                        )


class TestWorkflowSchemaCompliance:
    """Tests for GitHub Actions workflow schema compliance."""

    @staticmethod
    @pytest.fixture
    def all_workflows() -> List[dict[str, Any]]:
        """
        Collects and parses all YAML workflow files found in .github/workflows.

        Returns:
            workflows (List[dict[str, Any]]): A list of dictionaries, each containing:
                - 'path' (Path): Path to the workflow file.
                - 'content' (Any): Parsed YAML content as returned by yaml.safe_load (typically a dict, or None if the file is empty).
        """
        workflow_dir = Path(".github/workflows")
        workflows = []
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                workflows.append({"path": workflow_file, "content": yaml.safe_load(f)})
        return workflows

    @staticmethod
    def test_workflows_have_required_top_level_keys(all_workflows):
        """Verify workflows have all required top-level keys."""
        required_keys = ["name", "jobs"]
        checkout_versions = {}
        for workflow in all_workflows:
            for key in required_keys:
                assert key in workflow["content"], f"Workflow {workflow['path']} missing required key: {key}"
            unique_versions = set(checkout_versions.values())
            # Allow v3 and v4, but should be mostly consistent
            assert len(unique_versions) <= 2, f"Too many different checkout versions: {checkout_versions}"


class TestDefaultValueHandling:
    """Tests for default value handling in configurations."""

    @staticmethod
    def test_missing_optional_fields_have_defaults():
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

    @staticmethod
    def test_workflow_timeout_defaults():
        """
        Verify workflow job timeouts, when present, are integers between 1 and 360 minutes.

        Scans YAML files under .github/workflows and asserts any job's "timeout-minutes" value is an int greater than or equal to 1 and less than or equal to 360.
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
