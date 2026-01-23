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
    """
    Return the path to the repository's codesherlock.yaml file.
    """
    repo_root = Path(__file__).parent.parent.parent
    return repo_root / "codesherlock.yaml"


@pytest.fixture
def codesherlock_config(codesherlock_config_path: Path) -> Dict[str, Any]:
    """
    Load and parse codesherlock.yaml into a dictionary.
    """
    with codesherlock_config_path.open("r") as f:
        return yaml.safe_load(f)


class TestCodeSherlockConfigFile:
    """Tests for existence and YAML validity."""

    def test_config_file_exists(self, codesherlock_config_path: Path) -> None:
        assert codesherlock_config_path.exists(), "codesherlock.yaml should exist"
        assert codesherlock_config_path.is_file(), "codesherlock.yaml should be a file"

    def test_config_is_valid_yaml(self, codesherlock_config_path: Path) -> None:
        try:
            with codesherlock_config_path.open("r") as f:
                config = yaml.safe_load(f)
            assert isinstance(config, dict), "Config should be a dictionary"
        except yaml.YAMLError as exc:
            pytest.fail(f"Invalid YAML syntax: {exc}")


class TestCodeSherlockConfigStructure:
    """Tests for required structure and types."""

    def test_config_has_required_fields(self, codesherlock_config: Dict[str, Any]) -> None:
        assert "target_branches" in codesherlock_config
        assert "preferred_characteristics" in codesherlock_config

    def test_target_branches_is_list(self, codesherlock_config: Dict[str, Any]) -> None:
        assert isinstance(codesherlock_config["target_branches"], list)

    def test_target_branches_not_empty(self, codesherlock_config: Dict[str, Any]) -> None:
        assert codesherlock_config["target_branches"]

    def test_target_branches_contains_main(self, codesherlock_config: Dict[str, Any]) -> None:
        assert "main" in codesherlock_config["target_branches"]

    def test_preferred_characteristics_is_list(self, codesherlock_config: Dict[str, Any]) -> None:
        assert isinstance(codesherlock_config["preferred_characteristics"], list)

    def test_preferred_characteristics_not_empty(self, codesherlock_config: Dict[str, Any]) -> None:
        assert codesherlock_config["preferred_characteristics"]


class TestCodeSherlockConfigContent:
    """Tests for value correctness and duplication."""

    def test_target_branches_are_strings(self, codesherlock_config: Dict[str, Any]) -> None:
        for branch in codesherlock_config["target_branches"]:
            assert isinstance(branch, str)
            assert branch

    def test_target_branches_no_duplicates(self, codesherlock_config: Dict[str, Any]) -> None:
        branches = codesherlock_config["target_branches"]
        assert len(branches) == len(set(branches))

    def test_preferred_characteristics_are_strings(self, codesherlock_config: Dict[str, Any]) -> None:
        for characteristic in codesherlock_config["preferred_characteristics"]:
            assert isinstance(characteristic, str)
            assert characteristic

    def test_preferred_characteristics_no_duplicates(self, codesherlock_config: Dict[str, Any]) -> None:
        chars = codesherlock_config["preferred_characteristics"]
        assert len(chars) == len(set(chars))

    def test_preferred_characteristics_valid_values(self, codesherlock_config: Dict[str, Any]) -> None:
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


class TestCodeSherlockConfigBestPractices:
    """Tests for best-practice coverage."""

    def test_includes_security_characteristics(self, codesherlock_config: Dict[str, Any]) -> None:
        required = {
            "Input Validation",
            "Code Injection",
            "Exception Handling",
        }
        configured = set(codesherlock_config["preferred_characteristics"])
        assert required.issubset(configured)

    def test_reasonable_number_of_characteristics(self, codesherlock_config: Dict[str, Any]) -> None:
        count = len(codesherlock_config["preferred_characteristics"])
        assert 3 <= count <= 10


class TestCodeSherlockConfigEdgeCases:
    """Tests for formatting and edge-case handling."""

    def test_no_whitespace_in_values(self, codesherlock_config: Dict[str, Any]) -> None:
        for branch in codesherlock_config["target_branches"]:
            assert branch == branch.strip()

        for characteristic in codesherlock_config["preferred_characteristics"]:
            assert characteristic == characteristic.strip()

    def test_branch_names_no_invalid_characters(self, codesherlock_config: Dict[str, Any]) -> None:
        invalid = {" ", "\t", "\n", "~", "^", ":", "?", "*", "[", "\\"}
        for branch in codesherlock_config["target_branches"]:
            for char in invalid:
                assert char not in branch

    def test_config_file_size_reasonable(self, codesherlock_config_path: Path) -> None:
        assert codesherlock_config_path.stat().st_size < 10_240


class TestCodeSherlockConfigDocumentation:
    """Tests for documentation quality."""

    def test_config_has_comments(self, codesherlock_config_path: Path) -> None:
        lines = codesherlock_config_path.read_text().splitlines()
        assert sum(1 for line in lines if line.strip().startswith("#")) >= 3

    def test_sections_are_documented(self, codesherlock_config_path: Path) -> None:
        lines = codesherlock_config_path.read_text().splitlines()

        for key in ("target_branches:", "preferred_characteristics:"):
            idx = next((i for i, l in enumerate(lines) if key in l), None)
            assert idx is not None

            preceding = lines[max(0, idx - 5) : idx]
            assert any(line.strip().startswith("#") for line in preceding)
