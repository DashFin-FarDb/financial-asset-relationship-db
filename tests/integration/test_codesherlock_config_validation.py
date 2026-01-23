"""
Integration tests for codesherlock.yaml configuration validation.

This module validates the codesherlock configuration file structure,
content, and adherence to expected patterns.
"""

from pathlib import Path
from typing import Any, Dict

import pytest
import yaml


@pytest.fixture
def codesherlock_config_path() -> Path:
    """Return the path to the repository's codesherlock.yaml file."""
    repo_root = Path(__file__).parent.parent.parent
    return repo_root / "codesherlock.yaml"


@pytest.fixture
def codesherlock_config(
    codesherlock_config_path: Path,
) -> Dict[str, Any]:
    """Load and parse the codesherlock.yaml file."""
    with codesherlock_config_path.open("r") as f:
        return yaml.safe_load(f)


class TestCodeSherlockConfigFile:
    """Tests for existence and YAML validity."""

    def test_config_file_exists(self, codesherlock_config_path: Path) -> None:
        assert codesherlock_config_path.exists()
        assert codesherlock_config_path.is_file()

    def test_config_is_valid_yaml(self, codesherlock_config_path: Path) -> None:
        """Verify that codesherlock.yaml parses as valid YAML."""
        try:
            with codesherlock_config_path.open("r") as f:
                config = yaml.safe_load(f)
            assert isinstance(config, dict)
        except yaml.YAMLError as exc:
            pytest.fail(f"Invalid YAML syntax: {exc}")

    def test_config_has_required_fields(
        self, codesherlock_config: Dict[str, Any]
    ) -> None:
        assert "target_branches" in codesherlock_config
        assert "preferred_characteristics" in codesherlock_config

    def test_target_branches_is_list(self, codesherlock_config: Dict[str, Any]) -> None:
        assert isinstance(codesherlock_config["target_branches"], list)

    def test_target_branches_not_empty(
        self, codesherlock_config: Dict[str, Any]
    ) -> None:
        assert codesherlock_config["target_branches"]

    def test_target_branches_contains_main(
        self, codesherlock_config: Dict[str, Any]
    ) -> None:
        assert "main" in codesherlock_config["target_branches"]

    def test_preferred_characteristics_is_list(
        self, codesherlock_config: Dict[str, Any]
    ) -> None:
        assert isinstance(codesherlock_config["preferred_characteristics"], list)

    def test_preferred_characteristics_not_empty(
        self, codesherlock_config: Dict[str, Any]
    ) -> None:
        assert codesherlock_config["preferred_characteristics"]


class TestCodeSherlockConfigContent:
    """Tests for configuration content validation."""

    def test_target_branches_are_strings(
        self, codesherlock_config: Dict[str, Any]
    ) -> None:
        for branch in codesherlock_config["target_branches"]:
            assert isinstance(branch, str)
            assert branch

    def test_target_branches_no_duplicates(
        self, codesherlock_config: Dict[str, Any]
    ) -> None:
        branches = codesherlock_config["target_branches"]
        assert len(branches) == len(set(branches))

    def test_preferred_characteristics_are_strings(
        self, codesherlock_config: Dict[str, Any]
    ) -> None:
        for characteristic in codesherlock_config["preferred_characteristics"]:
            assert isinstance(characteristic, str)
            assert characteristic

    def test_preferred_characteristics_no_duplicates(
        self, codesherlock_config: Dict[str, Any]
    ) -> None:
        chars = codesherlock_config["preferred_characteristics"]
        assert len(chars) == len(set(chars))

    def test_preferred_characteristics_valid_values(
        self, codesherlock_config: Dict[str, Any]
    ) -> None:
        valid = {
            "Modularity",
            "Resource Utilization",
            "Exception Handling",
            "Monitoring and Logging",
            "Dependency Injection",
            "Code Injection",
            "Input Validation",
        }
        for characteristic in codesherlock_config["preferred_characteristics"]:
            assert characteristic in valid

    def test_additional_instructions_optional(
        self, codesherlock_config: Dict[str, Any]
    ) -> None:
        if "additional_instructions" in codesherlock_config:
            assert isinstance(codesherlock_config["additional_instructions"], list)


class TestCodeSherlockConfigBestPractices:
    """Tests for best-practice coverage."""

    def test_covers_key_security_characteristics(
        self, codesherlock_config: Dict[str, Any]
    ) -> None:
        required = {
            "Input Validation",
            "Code Injection",
            "Exception Handling",
        }
        configured = set(codesherlock_config["preferred_characteristics"])
        assert required.issubset(configured)

    def test_covers_code_quality_characteristics(
        self, codesherlock_config: Dict[str, Any]
    ) -> None:
        required = {"Modularity", "Dependency Injection"}
        configured = set(codesherlock_config["preferred_characteristics"])
        assert required.issubset(configured)

    def test_covers_operational_characteristics(
        self, codesherlock_config: Dict[str, Any]
    ) -> None:
        required = {
            "Monitoring and Logging",
            "Resource Utilization",
        }
        configured = set(codesherlock_config["preferred_characteristics"])
        assert required.issubset(configured)

    def test_reasonable_number_of_characteristics(
        self, codesherlock_config: Dict[str, Any]
    ) -> None:
        count = len(codesherlock_config["preferred_characteristics"])
        assert 3 <= count <= 10


class TestCodeSherlockConfigEdgeCases:
    """Tests for formatting and edge cases."""

    def test_no_whitespace_in_values(self, codesherlock_config: Dict[str, Any]) -> None:
        for branch in codesherlock_config["target_branches"]:
            assert branch == branch.strip()
        for characteristic in codesherlock_config["preferred_characteristics"]:
            assert characteristic == characteristic.strip()

    def test_branch_names_no_invalid_characters(
        self, codesherlock_config: Dict[str, Any]
    ) -> None:
        invalid = {" ", "\t", "\n", "~", "^", ":", "?", "*", "[", "\\"}
        for branch in codesherlock_config["target_branches"]:
            for char in invalid:
                assert char not in branch

    def test_config_file_size_reasonable(self, codesherlock_config_path: Path) -> None:
        assert codesherlock_config_path.stat().st_size < 10_240

    def test_yaml_indentation_consistency(self, codesherlock_config_path: Path) -> None:
        lines = codesherlock_config_path.read_text().splitlines()
        for i, line in enumerate(lines, 1):
            if line.startswith(" "):
                spaces = len(line) - len(line.lstrip())
                assert spaces % 2 == 0, f"Line {i} has invalid indentation"


class TestCodeSherlockConfigIntegration:
    """Integration-level validation tests."""

    def test_branch_name_length_constraints(
        self, codesherlock_config: Dict[str, Any]
    ) -> None:
        for branch in codesherlock_config["target_branches"]:
            assert 1 <= len(branch) <= 255

    def test_financial_critical_characteristics_present(
        self, codesherlock_config: Dict[str, Any]
    ) -> None:
        required = {
            "Input Validation",
            "Exception Handling",
            "Monitoring and Logging",
        }
        configured = set(codesherlock_config["preferred_characteristics"])
        missing = required - configured
        assert not missing, f"Missing critical characteristics: {missing}"


class TestCodeSherlockConfigDocumentation:
    """Tests for inline documentation quality."""

    def test_config_has_comments(self, codesherlock_config_path: Path) -> None:
        lines = codesherlock_config_path.read_text().splitlines()
        assert sum(1 for line in lines if line.strip().startswith("#")) >= 3

    def test_sections_are_documented(self, codesherlock_config_path: Path) -> None:
        lines = codesherlock_config_path.read_text().splitlines()

        for key in (
            "target_branches:",
            "preferred_characteristics:",
        ):
            idx = next(
                (i for i, line in enumerate(lines) if key in line),
                None,
            )
            assert idx is not None
            preceding = lines[max(0, idx - 5) : idx]
            assert any(line.strip().startswith("#") for line in preceding)
