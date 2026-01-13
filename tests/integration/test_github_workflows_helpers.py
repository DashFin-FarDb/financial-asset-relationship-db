"""
Unit tests for helper functions in test_github_workflows.py module.
"""
This test suite validates the utility functions used for GitHub Actions workflow
testing, ensuring they correctly identify workflow files, parse YAML, and detect
duplicate keys.
"""

from pathlib import Path
from typing import List
from unittest.mock import patch

import pytest
import yaml

# Import functions from the module we're testing
from tests.integration.test_github_workflows import (
    WORKFLOWS_DIR,
    check_duplicate_keys,
    get_workflow_files,
    load_yaml_safe,
)


class TestGetWorkflowFiles:
    """Test suite for get_workflow_files() function."""

    @staticmethod
    def test_returns_list():
        """Test that get_workflow_files returns a list."""
        result = get_workflow_files()
        assert isinstance(result, list)

    def test_returns_path_objects(self):
        """Test that all returned items are Path objects."""
        result = get_workflow_files()
        for item in result:
            assert isinstance(item, Path)

    def test_only_returns_yaml_files(self):
        """Test that only .yml and .yaml files are returned."""
        result = get_workflow_files()
        for workflow_file in result:
            assert workflow_file.suffix in [
                ".yml",
                ".yaml",
            ], f"File {workflow_file} has invalid extension {workflow_file.suffix}"

    def test_returns_empty_list_when_directory_missing(self, tmp_path):
        """Test that empty list is returned when workflows directory doesn't exist."""
        nonexistent_dir = tmp_path / "nonexistent" / "workflows"

        with patch("tests.integration.test_github_workflows.WORKFLOWS_DIR", nonexistent_dir):
            result = get_workflow_files()
            assert result == []

    def test_finds_yml_files(self, tmp_path):
        """Test that .yml files are found."""
        workflows_dir = tmp_path / "workflows"
        workflows_dir.mkdir()

        yml_file = workflows_dir / "test.yml"
        yml_file.write_text("name: Test")

        with patch("tests.integration.test_github_workflows.WORKFLOWS_DIR", workflows_dir):
            result = get_workflow_files()
            assert len(result) == 1
            assert result[0].name == "test.yml"

    def test_finds_yaml_files(self, tmp_path):
        """Test that .yaml files are found."""
        workflows_dir = tmp_path / "workflows"
        workflows_dir.mkdir()

        yaml_file = workflows_dir / "test.yaml"
        yaml_file.write_text("name: Test")

        with patch("tests.integration.test_github_workflows.WORKFLOWS_DIR", workflows_dir):
            result = get_workflow_files()
            assert len(result) == 1
            assert result[0].name == "test.yaml"

    def test_finds_both_yml_and_yaml(self, tmp_path):
        """Test that both .yml and .yaml files are found together."""
        workflows_dir = tmp_path / "workflows"
        workflows_dir.mkdir()

        yml_file = workflows_dir / "test1.yml"
        yml_file.write_text("name: Test1")

        yaml_file = workflows_dir / "test2.yaml"
        yaml_file.write_text("name: Test2")

        with patch("tests.integration.test_github_workflows.WORKFLOWS_DIR", workflows_dir):
            result = get_workflow_files()
            assert len(result) == 2
            names = {f.name for f in result}
            assert names == {"test1.yml", "test2.yaml"}

    def test_ignores_non_yaml_files(self, tmp_path):
        """Test that non - YAML files are ignored."""
        workflows_dir = tmp_path / "workflows"
        workflows_dir.mkdir()

        (workflows_dir / "test.yml").write_text("name: Test")
        (workflows_dir / "readme.md").write_text("# README")
        (workflows_dir / "script.sh").write_text("#!/bin/bash")
        (workflows_dir / "data.json").write_text("{}")

        with patch("tests.integration.test_github_workflows.WORKFLOWS_DIR", workflows_dir):
            result = get_workflow_files()
            assert len(result) == 1
            assert result[0].name == "test.yml"

    def test_only_returns_files_not_directories(self, tmp_path):
        """Test that directories with .yml / .yaml names are not returned."""
        workflows_dir = tmp_path / "workflows"
        workflows_dir.mkdir()

        # Create a directory with .yml extension
        dir_with_yml_name = workflows_dir / "notafile.yml"
        dir_with_yml_name.mkdir()

        # Create an actual file
        (workflows_dir / "realfile.yml").write_text("name: Real")

        with patch("tests.integration.test_github_workflows.WORKFLOWS_DIR", workflows_dir):
            result = get_workflow_files()
            assert len(result) == 1
            assert result[0].name == "realfile.yml"
            assert result[0].is_file()


class TestLoadYamlSafe:
    """Test suite for load_yaml_safe() function."""

    def test_loads_valid_yaml(self, tmp_path):
        """Test that valid YAML is loaded correctly."""
        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text("name: Test\nvalue: 123")

        result = load_yaml_safe(yaml_file)
        assert result == {"name": "Test", "value": 123}

    def test_loads_empty_yaml(self, tmp_path):
        """Test that empty YAML file returns None."""
        yaml_file = tmp_path / "empty.yml"
        yaml_file.write_text("")

        result = load_yaml_safe(yaml_file)
        assert result is None

    def test_loads_yaml_with_lists(self, tmp_path):
        """Test that YAML with lists is loaded correctly."""
        yaml_content = """
items:
  - name: first
    value: 1
  - name: second
    value: 2
"""
        yaml_file = tmp_path / "list.yml"
        yaml_file.write_text(yaml_content)

        result = load_yaml_safe(yaml_file)
        assert "items" in result
        assert len(result["items"]) == 2
        assert result["items"][0]["name"] == "first"
        assert result["items"][1]["value"] == 2

    def test_loads_yaml_with_nested_structures(self, tmp_path):
        """Test that nested YAML structures are loaded correctly."""
        yaml_content = """
level1:
  level2:
    level3:
      value: deep
"""
        yaml_file = tmp_path / "nested.yml"
        yaml_file.write_text(yaml_content)

        result = load_yaml_safe(yaml_file)
        assert result["level1"]["level2"]["level3"]["value"] == "deep"

    def test_raises_on_invalid_yaml(self, tmp_path):
        """Test that invalid YAML raises YAMLError."""
        yaml_file = tmp_path / "invalid.yml"
        yaml_file.write_text("invalid: yaml: content: [unclosed")

        with pytest.raises(yaml.YAMLError):
            load_yaml_safe(yaml_file)

    def test_handles_special_yaml_types(self, tmp_path):
        """Test that YAML special types(null, boolean) are handled."""
        yaml_content = """
null_value: null
true_value: true
false_value: false
number: 42
float_val: 3.14
"""
        yaml_file = tmp_path / "types.yml"
        yaml_file.write_text(yaml_content)

        result = load_yaml_safe(yaml_file)
        assert result["null_value"] is None
        assert result["true_value"] is True
        assert result["false_value"] is False
        assert result["number"] == 42
        assert result["float_val"] == 3.14

    def test_handles_multiline_strings(self, tmp_path):
        """Test that multiline strings are loaded correctly."""
        yaml_content = """
script: |
  echo "line 1"
  echo "line 2"
  echo "line 3"
"""
        yaml_file = tmp_path / "multiline.yml"
        yaml_file.write_text(yaml_content)

        result = load_yaml_safe(yaml_file)
        assert "line 1" in result["script"]
        assert "line 2" in result["script"]
        assert "line 3" in result["script"]

    def test_handles_utf8_content(self, tmp_path):
        """Test that UTF - 8 encoded content is loaded correctly."""
        yaml_content = """
name: Test UTF - 8
emoji: 🚀
chinese: 中文
arabic: العربية
"""
        yaml_file = tmp_path / "utf8.yml"
        yaml_file.write_text(yaml_content, encoding="utf-8")

        result = load_yaml_safe(yaml_file)
        assert result["emoji"] == "🚀"
        assert result["chinese"] == "中文"
        assert result["arabic"] == "العربية"


class TestCheckDuplicateKeys:
    """Test suite for check_duplicate_keys() function."""

    def test_no_duplicates_returns_empty_list(self, tmp_path):
        """Test that YAML with no duplicate keys returns empty list."""
        yaml_content = """
name: Test
version: 1.0
author: Someone
"""
        yaml_file = tmp_path / "no_dup.yml"
        yaml_file.write_text(yaml_content)

        result = check_duplicate_keys(yaml_file)
        assert result == []

    def test_detects_top_level_duplicate(self, tmp_path):
        """Test that top - level duplicate keys are detected."""
        yaml_content = """
name: First
version: 1.0
name: Second
"""
        yaml_file = tmp_path / "dup.yml"
        yaml_file.write_text(yaml_content)

        result = check_duplicate_keys(yaml_file)
        assert "name" in result

    def test_detects_nested_duplicate(self, tmp_path):
        """Test that nested duplicate keys are detected."""
        yaml_content = """
config:
  setting: first
  value: 123
  setting: second
"""
        yaml_file = tmp_path / "nested_dup.yml"
        yaml_file.write_text(yaml_content)

        result = check_duplicate_keys(yaml_file)
        assert "setting" in result

    def test_detects_multiple_duplicates(self, tmp_path):
        """Test that multiple duplicate keys are all detected."""
        yaml_content = """
name: First
name: Second
version: 1.0
version: 2.0
version: 3.0
"""
        yaml_file = tmp_path / "multi_dup.yml"
        yaml_file.write_text(yaml_content)

        result = check_duplicate_keys(yaml_file)
        assert "name" in result
        assert "version" in result
        assert result.count("version") == 2

    def test_ignores_same_keys_in_different_contexts(self, tmp_path):
        """Test that same keys in different objects don't count as duplicates."""
        yaml_content = """
job1:
  name: Job One
  steps:
    - name: Step 1
job2:
  name: Job Two
  steps:
    - name: Step 2
"""
        yaml_file = tmp_path / "different_context.yml"
        yaml_file.write_text(yaml_content)

        result = check_duplicate_keys(yaml_file)
        assert result == []

    def test_handles_empty_file(self, tmp_path):
        """Test that empty file returns empty list."""
        yaml_file = tmp_path / "empty.yml"
        yaml_file.write_text("")

        result = check_duplicate_keys(yaml_file)
        assert result == []

    def test_handles_invalid_yaml_gracefully(self, tmp_path):
        """Test that invalid YAML is handled gracefully."""
        yaml_file = tmp_path / "invalid.yml"
        yaml_file.write_text("invalid: yaml: [unclosed")

        result = check_duplicate_keys(yaml_file)
        assert isinstance(result, list)

    def test_github_actions_pr_agent_scenario(self, tmp_path):
        """Test the specific PR Agent workflow duplicate key scenario."""
        yaml_content = """
name: PR Agent
on:
  pull_request:
jobs:
  review:
    runs - on: ubuntu - latest
    steps:
      - name: Checkout
        uses: actions / checkout @ v4
      - name: Setup Python
        uses: actions / setup - python @ v5
        with:
          python - version: '3.11'
      - name: Setup Python
        uses: actions / setup - python @ v5
        with:
          python - version: '3.11'
"""
        yaml_file = tmp_path / "pr_agent.yml"
        yaml_file.write_text(yaml_content)

        result = check_duplicate_keys(yaml_file)
        assert isinstance(result, list)

    def test_detects_duplicate_in_list_of_mappings(self, tmp_path):
        """Test detection of duplicates within a mapping that's in a list."""
        yaml_content = """
items:
  - key: value1
    key: value2
"""
        yaml_file = tmp_path / "list_dup.yml"
        yaml_file.write_text(yaml_content)

        result = check_duplicate_keys(yaml_file)
        assert "key" in result


class TestWorkflowsDirectoryConstant:
    """Test suite for WORKFLOWS_DIR constant."""

    @staticmethod
    def test_workflows_dir_is_path_object():
        """Test that WORKFLOWS_DIR is a Path object."""
        assert isinstance(WORKFLOWS_DIR, Path)

    def test_workflows_dir_points_to_github_workflows(self):
        """Test that WORKFLOWS_DIR points to .github / workflows."""
        assert WORKFLOWS_DIR.name == "workflows"
        assert WORKFLOWS_DIR.parent.name == ".github"

    @staticmethod
    def test_workflows_dir_is_absolute_or_relative_to_repo():
        """Test that WORKFLOWS_DIR path makes sense."""
        path_str = str(WORKFLOWS_DIR)
        assert ".github" in path_str
        assert "workflows" in path_str


class TestIntegrationScenarios:
    """Integration tests combining multiple helper functions."""

    def test_full_workflow_discovery_and_validation(self, tmp_path):
        """Test complete flow: discover workflows, load them, check for duplicates."""
        workflows_dir = tmp_path / "workflows"
        workflows_dir.mkdir()

        valid_workflow = workflows_dir / "valid.yml"
        valid_workflow.write_text(
            """
name: Valid Workflow
on: push
jobs:
  test:
    runs - on: ubuntu - latest
    steps:
      - uses: actions / checkout @ v4
"""
        )

        dup_workflow = workflows_dir / "duplicate.yml"
        dup_workflow.write_text(
            """
name: Duplicate Workflow
name: Another Name
on: push
jobs:
  test:
    runs - on: ubuntu - latest
"""
        )

        with patch("tests.integration.test_github_workflows.WORKFLOWS_DIR", workflows_dir):
            workflows = get_workflow_files()
            assert len(workflows) == 2

            for workflow_file in workflows:
                config = load_yaml_safe(workflow_file)
                assert config is not None
                assert "name" in config or "on" in config

                duplicates = check_duplicate_keys(workflow_file)

                if workflow_file.name == "valid.yml":
                    assert len(duplicates) == 0
                elif workflow_file.name == "duplicate.yml":
                    assert len(duplicates) > 0
                    assert "name" in duplicates

    def test_edge_case_workflow_with_complex_structure(self, tmp_path):
        """Test handling of complex real - world workflow structure."""
        workflows_dir = tmp_path / "workflows"
        workflows_dir.mkdir()

        complex_workflow = workflows_dir / "complex.yml"
        complex_workflow.write_text(
            """
name: Complex CI / CD
on:
  push:
    branches: [main, develop]
  pull_request:
    types: [opened, synchronize]
env:
  NODE_VERSION: '18'
  PYTHON_VERSION: '3.11'
jobs:
  test:
    runs - on: ubuntu - latest
    strategy:
      matrix:
        python - version: ['3.9', '3.10', '3.11']
    steps:
      - uses: actions / checkout @ v4
        with:
"""
        )
            fetch - depth: 0
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: 'pip'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: Run tests
        run: pytest tests/ --cov
"""
        )

        with patch("tests.integration.test_github_workflows.WORKFLOWS_DIR", workflows_dir):
            workflows = get_workflow_files()
            assert len(workflows) == 1

            config = load_yaml_safe(workflows[0])
            assert config["name"] == "Complex CI/CD"
            assert "push" in config["on"]
            assert "pull_request" in config["on"]
            assert "strategy" in config["jobs"]["test"]
            assert "matrix" in config["jobs"]["test"]["strategy"]

            duplicates = check_duplicate_keys(workflows[0])
            assert len(duplicates) == 0
