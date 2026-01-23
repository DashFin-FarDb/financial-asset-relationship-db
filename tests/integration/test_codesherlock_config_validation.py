"""
Integration tests for codesherlock.yaml configuration validation.

This module validates the codesherlock configuration file structure,
content, and adherence to expected patterns.
"""

import os
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml


@pytest.fixture
def codesherlock_config_path() -> Path:
    """
    Get the Path to the repository's codesherlock.yaml file.

    Returns:
        path (Path): Path to codesherlock.yaml located at the repository root.
    """
    repo_root = Path(__file__).parent.parent.parent
    return repo_root / "codesherlock.yaml"


@pytest.fixture
def codesherlock_config(codesherlock_config_path: Path) -> Dict[str, Any]:
    """
    Load the codesherlock.yaml file and parse it into a dictionary.

    Parameters:
        codesherlock_config_path (Path): Path to the codesherlock.yaml file at the repository root.

    Returns:
        config (Dict[str, Any]): Parsed YAML content as a dictionary.
    """
    with open(codesherlock_config_path, "r") as f:
        return yaml.safe_load(f)


class TestCodeSherlockConfigStructure:
    """Test suite for codesherlock.yaml configuration structure."""

    @staticmethod
    def test_config_file_exists(codesherlock_config_path: Path):
        """Verify that codesherlock.yaml exists in the repository root."""
        assert codesherlock_config_path.exists(), "codesherlock.yaml should exist"
        assert codesherlock_config_path.is_file(), "codesherlock.yaml should be a file"

    @staticmethod
    def test_config_is_valid_yaml(codesherlock_config_path: Path):
        """
        Verify that the repository's codesherlock.yaml parses as valid YAML.

        Asserts that the file at `codesherlock_config_path` loads to a non-None mapping (dict) and fails the test on YAML syntax errors.

        Parameters:
            codesherlock_config_path (Path): Path to the codesherlock.yaml file in the repository root.
        """
        try:
            with open(codesherlock_config_path, "r") as f:
                config = yaml.safe_load(f)
            assert config is not None, "Config should not be None"
            assert isinstance(config, dict), "Config should be a dictionary"
        except yaml.YAMLError as e:
            pytest.fail(f"Invalid YAML syntax: {e}")

    def test_config_has_required_fields(self, codesherlock_config: Dict[str, Any]):
        """
        Ensure the top-level required fields are present in the Codesherlock configuration.

        Parameters:
            codesherlock_config (Dict[str, Any]): Parsed contents of `codesherlock.yaml` as a mapping.

        This test fails if any of the expected top-level keys are missing from the configuration.
        """
        assert "target_branches" in codesherlock_config, (
            "target_branches field is required"
        )
        assert "preferred_characteristics" in codesherlock_config, (
            "preferred_characteristics field is required"
        )

    def test_target_branches_is_list(self, codesherlock_config: Dict[str, Any]):
        """Verify that target_branches is a list."""
        assert isinstance(codesherlock_config["target_branches"], list), (
            "target_branches should be a list"
        )

    def test_target_branches_not_empty(self, codesherlock_config: Dict[str, Any]):
        """Verify that target_branches list is not empty."""
        assert len(codesherlock_config["target_branches"]) > 0, (
            "target_branches should not be empty"
        )

    def test_target_branches_contains_main(self, codesherlock_config: Dict[str, Any]):
        """Verify that 'main' is included in target_branches."""
        assert "main" in codesherlock_config["target_branches"], (
            "target_branches should include 'main'"
        )

    def test_preferred_characteristics_is_list(
        self, codesherlock_config: Dict[str, Any]
    ):
        """Verify that preferred_characteristics is a list."""
        assert isinstance(codesherlock_config["preferred_characteristics"], list), (
            "preferred_characteristics should be a list"
        )

    def test_preferred_characteristics_not_empty(
        self, codesherlock_config: Dict[str, Any]
    ):
        """Verify that preferred_characteristics list is not empty."""
        assert len(codesherlock_config["preferred_characteristics"]) > 0, (
            "preferred_characteristics should not be empty"
        )


class TestCodeSherlockConfigContent:
    """Test suite for codesherlock.yaml configuration content validation."""

    def test_target_branches_are_strings(self, codesherlock_config: Dict[str, Any]):
        """
        Verify that all target branches are non-empty strings.

        Asserts that every entry in `target_branches` is a Python `str` and has length greater than zero.
        """
        for branch in codesherlock_config["target_branches"]:
            assert isinstance(branch, str), f"Branch '{branch}' should be a string"
            assert len(branch) > 0, "Branch name should not be empty"

    def test_target_branches_no_duplicates(self, codesherlock_config: Dict[str, Any]):
        """Verify that target_branches contains no duplicates."""
        branches = codesherlock_config["target_branches"]
        assert len(branches) == len(set(branches)), (
            "target_branches should not contain duplicates"
        )

    def test_preferred_characteristics_are_strings(
        self, codesherlock_config: Dict[str, Any]
    ):
        """
        Check that each entry in preferred_characteristics is a non-empty string.

        Asserts that every characteristic is an instance of `str` and has length greater than zero.

        Parameters:
            codesherlock_config (Dict[str, Any]): Parsed codesherlock.yaml configuration.
        """
        for characteristic in codesherlock_config["preferred_characteristics"]:
            assert isinstance(characteristic, str), (
                f"Characteristic '{characteristic}' should be a string"
            )
            assert len(characteristic) > 0, "Characteristic name should not be empty"

    def test_preferred_characteristics_no_duplicates(
        self, codesherlock_config: Dict[str, Any]
    ):
        """Verify that preferred_characteristics contains no duplicates."""
        characteristics = codesherlock_config["preferred_characteristics"]
        assert len(characteristics) == len(set(characteristics)), (
            "preferred_characteristics should not contain duplicates"
        )

    def test_preferred_characteristics_valid_values(
        self, codesherlock_config: Dict[str, Any]
    ):
        """Verify that preferred characteristics contain valid values."""
        valid_characteristics = {
            "Modularity",
            "Resource Utilization",
            "Exception Handling",
            "Monitoring and Logging",
            "Dependency Injection",
            "Code Injection",
            "Input Validation",
        }

        for characteristic in codesherlock_config["preferred_characteristics"]:
            assert characteristic in valid_characteristics, (
                f"Characteristic '{characteristic}' is not a recognized value. "
                f"Valid values: {valid_characteristics}"
            )

    def test_additional_instructions_optional(
        self, codesherlock_config: Dict[str, Any]
    ):
        """Verify that additional_instructions field is optional."""
        # Should not fail if additional_instructions is missing
        if "additional_instructions" in codesherlock_config:
            assert isinstance(codesherlock_config["additional_instructions"], list), (
                "additional_instructions should be a list when present"
            )


class TestCodeSherlockConfigBestPractices:
    """Test suite for codesherlock.yaml best practices and recommendations."""

    def test_covers_key_security_characteristics(
        self, codesherlock_config: Dict[str, Any]
    ):
        """Verify that security-related characteristics are included."""
        security_characteristics = {
            "Input Validation",
            "Code Injection",
            "Exception Handling",
        }
        configured_characteristics = set(
            codesherlock_config["preferred_characteristics"]
        )

        for security_char in security_characteristics:
            assert security_char in configured_characteristics, (
                f"Security characteristic '{security_char}' should be included"
            )

    def test_covers_code_quality_characteristics(
        self, codesherlock_config: Dict[str, Any]
    ):
        """
        Ensure the configuration includes key code quality characteristics.

        Asserts that the `preferred_characteristics` list contains "Modularity" and "Dependency Injection".

        Parameters:
            codesherlock_config (Dict[str, Any]): Parsed codesherlock.yaml configuration.
        """
        quality_characteristics = {"Modularity", "Dependency Injection"}
        configured_characteristics = set(
            codesherlock_config["preferred_characteristics"]
        )

        for quality_char in quality_characteristics:
            assert quality_char in configured_characteristics, (
                f"Code quality characteristic '{quality_char}' should be included"
            )

    def test_covers_operational_characteristics(
        self, codesherlock_config: Dict[str, Any]
    ):
        """Verify that operational characteristics are included."""
        operational_characteristics = {"Monitoring and Logging", "Resource Utilization"}
        configured_characteristics = set(
            codesherlock_config["preferred_characteristics"]
        )

        for operational_char in operational_characteristics:
            assert operational_char in configured_characteristics, (
                f"Operational characteristic '{operational_char}' should be included"
            )

    def test_reasonable_number_of_characteristics(
        self, codesherlock_config: Dict[str, Any]
    ):
        """Validate the number of preferred characteristics in the configuration.

        Ensures the `preferred_characteristics` list contains a reasonable number of
        items (between 3 and 10 inclusive) to keep reviews focused and manageable.

        Parameters:
            codesherlock_config (Dict[str, Any]): Parsed codesherlock.yaml configuration.
        """
        num_characteristics = len(codesherlock_config["preferred_characteristics"])
        assert 3 <= num_characteristics <= 10, (
            f"Number of characteristics ({num_characteristics}) should be between 3 and 10 for focused reviews"
        )

    def test_includes_common_development_branches(
        self, codesherlock_config: Dict[str, Any]
    ):
        """Verify that common development branches are considered."""
        branches = set(codesherlock_config["target_branches"])

        # At least one of the common branch names should be present
        common_branches = {"main", "master", "develop", "development"}
        assert any(branch in branches for branch in common_branches), (
            "At least one common development branch (main, master, develop) should be included"
        )


class TestCodeSherlockConfigEdgeCases:
    """Test suite for edge cases in codesherlock.yaml configuration."""

    def test_config_handles_whitespace_in_values(
        self, codesherlock_config: Dict[str, Any]
    ):
        """Verify that configuration values handle whitespace appropriately."""
        for branch in codesherlock_config["target_branches"]:
            assert branch == branch.strip(), (
                f"Branch '{branch}' should not have leading/trailing whitespace"
            )

        for characteristic in codesherlock_config["preferred_characteristics"]:
            # Characteristics may contain internal spaces (e.g., "Input Validation")
            assert characteristic == characteristic.strip(), (
                f"Characteristic '{characteristic}' should not have leading/trailing whitespace"
            )

    def test_config_handles_special_characters_in_branch_names(
        self, codesherlock_config: Dict[str, Any]
    ):
        """
        Ensure branch names do not contain disallowed characters.

        Branch names should not contain spaces, tabs, newlines, or any of the characters:
        ~, ^, :, ?, *, [, \\.

        Parameters:
            codesherlock_config (dict): Parsed codesherlock.yaml containing the "target_branches" list.
        """
        for branch in codesherlock_config["target_branches"]:
            # Branch names should not contain certain invalid characters
            invalid_chars = [" ", "\t", "\n", "~", "^", ":", "?", "*", "[", "\\"]
            for char in invalid_chars:
                assert char not in branch, (
                    f"Branch '{branch}' should not contain '{char}'"
                )

    def test_config_file_size_reasonable(self, codesherlock_config_path: Path):
        """
        Ensure that the codesherlock.yaml file remains reasonably small.
        Parameters:
            codesherlock_config_path (Path): Path to the repository's codesherlock.yaml file.
        """
        file_size = codesherlock_config_path.stat().st_size
        assert file_size < 10240, (
            f"Config file size ({file_size} bytes) should be less than 10KB"
        )

    def test_config_yaml_formatting(self, codesherlock_config_path: Path):
        """
        Verify the YAML file uses 2-space indentation for all indented lines.

        Asserts that every line with leading spaces has a number of leading spaces divisible by two.

        Parameters:
            codesherlock_config_path (Path): Path to the repository's codesherlock.yaml file.
        """
        with open(codesherlock_config_path, "r") as f:
            content = f.read()

        # Check for consistent indentation (2 spaces)
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            if line and line[0] == " ":
                # Count leading spaces
                leading_spaces = len(line) - len(line.lstrip())
                assert leading_spaces % 2 == 0, (
                    f"Line {i} should use 2-space indentation"
                )


class TestCodeSherlockConfigIntegration:
    """Integration tests for codesherlock.yaml with the project."""

    def test_config_aligns_with_project_branches(
        self, codesherlock_config: Dict[str, Any]
    ):
        """
        Verify that configured branch names meet length constraints.

        Ensures that all branch names are between 1 and 255 characters long.
        Parameters:
            codesherlock_config (dict): Parsed codesherlock.yaml mapping; must contain a "target_branches" list of branch name strings.
        """
        branches = codesherlock_config["target_branches"]

        # These are either standard branches or should exist in the project
        for branch in branches:
            # We can't easily check remote branches in tests, but we can verify format
            assert len(branch) >= 1, f"Branch name '{branch}' is too short"
            assert len(branch) <= 255, f"Branch name '{branch}' is too long"

    def test_config_characteristics_match_project_needs(
        self, codesherlock_config: Dict[str, Any]
    ):
        """
        Assert that the configuration includes critical characteristics required for a financial application.

        Checks that 'Input Validation', 'Exception Handling', and 'Monitoring and Logging'
        appear in `preferred_characteristics`. The test fails with a message listing any
        missing characteristics.

        Parameters:
            codesherlock_config (Dict[str, Any]): Parsed codesherlock.yaml configuration.
        """
        characteristics = set(codesherlock_config["preferred_characteristics"])

        # For a financial application, certain characteristics are critical
        financial_critical_characteristics = {
            "Input Validation",
            "Exception Handling",
            "Monitoring and Logging",
        }

        missing_critical = financial_critical_characteristics - characteristics
        assert not missing_critical, (
            f"Critical characteristics for financial applications are missing: {missing_critical}"
        )


class TestCodeSherlockConfigDocumentation:
    """Test suite for documentation and comments in codesherlock.yaml."""

    def test_config_has_inline_documentation(self, codesherlock_config_path: Path):
        """Verify that the configuration file includes helpful comments."""
        with open(codesherlock_config_path, "r") as f:
            content = f.read()

        # Should have at least some comment lines
        comment_lines = [
            line for line in content.split("\n") if line.strip().startswith("#")
        ]
        assert len(comment_lines) >= 3, (
            "Config file should include explanatory comments"
        )

    def test_config_documents_target_branches(self, codesherlock_config_path: Path):
        """
        Check that the YAML file documents the `target_branches` section with explanatory comments.

        Searches the repository's codesherlock.yaml for the `target_branches:` key and asserts there is at least one comment line (a line starting with `#`) within the five lines immediately preceding that key.

        Parameters:
            codesherlock_config_path (Path): Path to the codesherlock.yaml file to inspect.
        """
        with open(codesherlock_config_path, "r") as f:
            content = f.read()

        # Should have comments explaining target_branches before the field
        lines = content.split("\n")
        target_branches_line_idx = None
        for i, line in enumerate(lines):
            if "target_branches:" in line:
                target_branches_line_idx = i
                break

        assert target_branches_line_idx is not None, (
            "target_branches field should be present"
        )

        # Check for comments in the lines before target_branches
        preceding_lines = lines[
            max(0, target_branches_line_idx - 5) : target_branches_line_idx
        ]
        has_comment = any(line.strip().startswith("#") for line in preceding_lines)
        assert has_comment, "target_branches section should have explanatory comments"

    def test_config_documents_preferred_characteristics(
        self, codesherlock_config_path: Path
    ):
        """Ensure the preferred_characteristics section in the config file has explanatory comments."""
        lines = codesherlock_config_path.read_text().splitlines()
        preferred_char_line_idx = None
        for idx, line in enumerate(lines):
            if "preferred_characteristics" in line:
                preferred_char_line_idx = idx
                break
        assert preferred_char_line_idx is not None, (
            "preferred_characteristics field should be present"
        )
        preceding_lines = lines[
            max(0, preferred_char_line_idx - 5) : preferred_char_line_idx
        ]
        has_comment = any(line.strip().startswith("#") for line in preceding_lines)
        assert has_comment, (
            "preferred_characteristics section should have explanatory comments"
        )
