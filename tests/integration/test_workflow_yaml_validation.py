"""
Additional validation tests for modified workflow files.
Tests YAML structure, required fields, and GitHub Actions syntax.
"""

import os
import yaml
import pytest
from pathlib import Path


class TestWorkflowYAMLValidation:
    """Validate YAML structure of modified workflow files."""
    
    WORKFLOW_DIR = Path(__file__).parent.parent.parent / ".github" / "workflows"
    
    @pytest.fixture
    def modified_workflows(self):
        """
        Names of workflow files that were modified in this branch.
        
        Returns:
            workflows (list[str]): Filenames of the modified GitHub Actions workflow YAML files.
        """
        return [
            "apisec-scan.yml",
            "greetings.yml",
            "label.yml",
            "pr-agent.yml"
        ]
    
    def test_workflows_are_valid_yaml(self, modified_workflows):
        """Ensure all modified workflows parse as valid YAML."""
        for workflow_file in modified_workflows:
            path = self.WORKFLOW_DIR / workflow_file
            assert path.exists(), f"Workflow file not found: {workflow_file}"
            
            with open(path, 'r') as f:
                try:
                    data = yaml.safe_load(f)
                    assert data is not None, f"Empty YAML in {workflow_file}"
                except yaml.YAMLError as e:
                    pytest.fail(f"Invalid YAML in {workflow_file}: {e}")
    
    def test_workflows_have_required_top_level_keys(self, modified_workflows):
        """
        Check that each modified GitHub Actions workflow contains the required top-level keys.
        
        For every workflow filename provided by the `modified_workflows` fixture, the file is loaded as YAML and the presence of the top-level keys `name`, `on`, and `jobs` is asserted. If a key is missing the test fails with a message identifying the workflow file and the missing key.
        
        Parameters:
            modified_workflows (list[str]): Filenames of workflow files that were modified in the branch.
        """
        required_keys = ['name', 'on', 'jobs']
        
        for workflow_file in modified_workflows:
            path = self.WORKFLOW_DIR / workflow_file
            try:
                    workflow = yaml.safe_load(f)
                    assert workflow is not None, f"Empty YAML in {workflow_file}"
        
                for key in required_keys:
                    assert key in workflow, \
                        f"Workflow {workflow_file} missing required key: {key}"
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {workflow_file}: {e}")
            except FileNotFoundError:
                pytest.fail(f"Workflow file not found: {workflow_file}")
    
    def test_pr_agent_workflow_simplified_correctly(self):
        """
        Validate that the pr-agent GitHub Actions workflow has been simplified: it no longer references chunking and still includes essential parsing and Python setup.
        
        Asserts that:
        - the file does not contain case-insensitive references to "context_chunker" or "chunking";
        - the file contains either "parse-comments" (case-insensitive) or "parse";
        - the file includes a Python setup step (case-insensitive).
        """
        path = self.WORKFLOW_DIR / "pr-agent.yml"
        with open(path, 'r') as f:
            content = f.read()
        
        content_lower = content.lower()

        # Should NOT contain chunking references
        assert 'context_chunker' not in content_lower, \
            "PR agent workflow still references context chunker"
        assert 'chunking' not in content_lower, \
            "PR agent workflow still has chunking logic"

        # SHOULD contain essential functionality
        assert 'parse-comments' in content_lower or 'parse' in content_lower, \
            "PR agent workflow missing comment parsing"
        assert 'python' in content_lower, \
            "PR agent workflow missing Python setup"
class TestRequirementsDevChanges:
    """Validate requirements-dev.txt modifications."""

    def test_requirements_dev_file_exists(self):
        """Check that requirements-dev.txt exists at the repository root."""
        path = Path(__file__).parent.parent.parent / "requirements-dev.txt"
        assert path.exists(), "requirements-dev.txt not found"

    def test_pyyaml_present_in_requirements_dev(self):
        """
        Check that PyYAML is declared in requirements-dev.txt.

        Reads the repository's requirements-dev.txt, ignores blank lines and comments,
        and asserts that a dependency beginning with "PyYAML" (case-insensitive) is present.
        """
        path = Path(__file__).parent.parent.parent / "requirements-dev.txt"
        assert path.exists(), "requirements-dev.txt not found"
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert any(line.lower().startswith("pyyaml") for line in lines), (
            "PyYAML not found in requirements-dev.txt"
        )