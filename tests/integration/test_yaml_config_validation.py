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

        assert len(parse_errors) == 0, "YAML parse errors:\n" + "\n".join(parse_errors)

    @staticmethod
    def test_yaml_files_use_consistent_indentation():
        """
        Check that YAML files under .github use 2-space indentation while ignoring block scalar contents.

        Scans all .yml and .yaml files under .github and reports any non-empty, non-comment lines whose leading indentation is not a multiple of two spaces. Lines inside block scalars (introduced with `|` or `>`, including optional chomping or indent indicators) are excluded from indentation checks. The test fails with a consolidated list of file paths and line numbers for each indentation violation.
        """
        yaml_files = list(Path(".github").rglob("*.yml")) + list(
            Path(".github").rglob("*.yaml")
        )
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
                    if leading_spaces <= block_scalar_indent:
                        # Exit block scalar when indentation is less than or equal to the scalar's parent indent
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
                if line[0] == " " and not (
                    stripped.startswith("- |") or stripped.startswith("- >")
                ):
                    if leading_spaces % 2 != 0:
                        indentation_errors.append(
                            f"{yaml_file} line {line_no}: Use 2-space indentation, found {leading_spaces} spaces"
                        )

            # Reset flags per file (handled by reinitialization each loop)

        assert not indentation_errors, "Indentation errors found:\n" + "\n".join(
            indentation_errors
        )


def test_no_duplicate_keys_in_yaml():
    """
    Check that YAML files under .github parse without duplicate keys or other YAML parsing errors using ruamel.yaml.

    Attempts to import ruamel.yaml and skips the test if unavailable. Collects all `.yml` and `.yaml` files under `.github` and records any YAML parsing errors, file system errors, or unexpected exceptions encountered while loading each file; the test fails if any such errors are found.
    """
    try:
        from ruamel.yaml import YAML, YAMLError
    except ImportError:
        pytest.skip("ruamel.yaml not installed; skip strict duplicate key detection")

    yaml_files = list(Path(".github").rglob("*.yml")) + list(
        Path(".github").rglob("*.yaml")
    )
    parser = YAML(typ="safe")
    parse_errors = []

    for yaml_file in yaml_files:
        try:
            with open(yaml_file, "r") as f:
                parser.load(f)
        except YAMLError as e:
            parse_errors.append(f"{yaml_file}: YAML error - {e}")
        except OSError as e:
            # Report but don't fail the test on file system errors
            parse_errors.append(f"{yaml_file}: File system error - {e}")
        except Exception as e:
            parse_errors.append(f"{yaml_file}: Unexpected error - {e}")

    assert not parse_errors, "YAML errors found:\n" + "\n".join(parse_errors)


class TestWorkflowSchemaCompliance:
    """Tests for GitHub Actions workflow schema compliance."""

    @staticmethod
    @pytest.fixture
    def all_workflows() -> List[Dict[str, Any]]:
        """
        Collects and parses all GitHub Actions workflow files from .github/workflows.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries for each workflow file with:
                - 'path' (Path): Path to the workflow file.
                - 'content' (Any): Parsed YAML content (typically a dict, or `None` if the file is empty).
        """
        workflow_dir = Path(".github/workflows")
        workflows = []
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                workflows.append({"path": workflow_file, "content": yaml.safe_load(f)})
        return workflows

    def test_workflows_have_required_top_level_keys(self, all_workflows):
        """
        Ensure each workflow defines required top-level keys and that checkout action versions are reasonably consistent.

        Asserts that every workflow's parsed content contains the top-level keys "name" and "jobs". Collects observed checkout action versions across workflows and fails if more than two unique versions are present; the assertion failure includes the observed `checkout_versions`.

        Parameters:
            all_workflows (List[Dict[str, Any]]): Iterable of workflow descriptors where each item contains:
                - 'path' (Path | str): filesystem path to the workflow file
                - 'content' (dict | None): parsed YAML content of the workflow
        """
        required_keys = ["name", "jobs"]
        checkout_versions = {}
        for workflow in all_workflows:
            for key in required_keys:
                assert key in workflow["content"], (
                    f"Workflow {workflow['path']} missing required key: {key}"
                )
            unique_versions = set(checkout_versions.values())
            # Allow v3 and v4, but should be mostly consistent
            for job_name, job in workflow["content"].get("jobs", {}).items():
                for step in job.get("steps", []):
                    uses = step.get("uses", "")
                    if "actions/checkout@" in uses:
                        version = uses.split("@")[-1]
                        checkout_versions[str(workflow["path"])] = version

        unique_versions = set(checkout_versions.values())
        # Allow v3 and v4, but should be mostly consistent
        assert len(unique_versions) <= 2, f"Too many different checkout versions: {checkout_versions}"


class TestDefaultValueHandling:
    """Tests for default value handling in configurations."""

    @staticmethod
    def test_missing_optional_fields_have_defaults() -> None:
        """
        Ensure optional fields in `.github / pr - agent - config.yml` are handled and validated.

        Asserts that if the top - level 'agent' section includes an 'enabled' key,
        its value is a boolean. Omission of 'enabled' is permitted and treated
        as the configuration default.
        """
        config_path = Path(".github/pr-agent-config.yml")

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # These fields should have defaults if not specified
        agent_config = config.get("agent", {})

        # If enabled is specified, it must be a boolean
        if "enabled" in agent_config:
            assert isinstance(agent_config["enabled"], bool)

    @staticmethod
    def test_workflow_timeout_defaults():
        """
        Check that job `timeout-minutes` values in workflows under .github/workflows are valid.

        For each job that defines `timeout-minutes`, assert the value is an `int` and is between 1 and 360 (inclusive). Assertion messages include the workflow file path and the job id.
        """
        workflow_dir = Path(".github/workflows")

        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                workflow = yaml.safe_load(f)

            jobs = workflow.get("jobs", {})
            for job_id, job_config in jobs.items():
                if "timeout-minutes" in job_config:
                    timeout = job_config["timeout-minutes"]
                    assert isinstance(timeout, int), (
                        f"Timeout should be integer in {workflow_file} job '{job_id}'"
                    )
                    assert 1 <= timeout <= 360, (
                        f"Timeout should be 1-360 minutes in {workflow_file} job '{job_id}'"
                    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
