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
        """List of workflows modified in this branch."""
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
        """Validate required GitHub Actions workflow keys."""
        required_keys = ['name', 'on', 'jobs']
        
        for workflow_file in modified_workflows:
            path = self.WORKFLOW_DIR / workflow_file
            with open(path, 'r') as f:
                workflow = yaml.safe_load(f)
            
            for key in required_keys:
                assert key in workflow, \
                    f"Workflow {workflow_file} missing required key: {key}"
    
    def test_pr_agent_workflow_simplified_correctly(self):
        """Verify PR agent workflow no longer has chunking code."""
        path = self.WORKFLOW_DIR / "pr-agent.yml"
        with open(path, 'r') as f:
            content = f.read()
        
        # Should NOT contain chunking references
        assert 'context_chunker' not in content.lower(), \
            "PR agent workflow still references context chunker"
        assert 'chunking' not in content.lower(), \
            "PR agent workflow still has chunking logic"
        
        # SHOULD contain essential functionality
        assert 'parse-comments' in content.lower() or 'parse' in content, \
            "PR agent workflow missing comment parsing"
        assert 'python' in content.lower(), \
            "PR agent workflow missing Python setup"



class TestRequirementsDevChanges:
    """Validate requirements-dev.txt modifications."""
    
    def test_requirements_dev_file_exists(self):
        """Ensure requirements-dev.txt exists."""
        path = Path(__file__).parent.parent.parent / "requirements-dev.txt"
        assert path.exists(), "requirements-dev.txt not found"
    
    def test_pyyaml_present_in_requirements_dev(self):
        """Verify PyYAML is in requirements-dev.txt."""
        path = Path(__file__).parent.parent.parent / "requirements-dev.txt"
        with open(path, 'r') as f:
            content = f.read()
        
        lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith('#')]
        assert any(line.lower().startswith('pyyaml') for line in lines), \
            ln for ln in (
                line.strip() for line in content.splitlines()
            if ln and not ln.startswith('#') and ln.split()[0].split('==')[0].split('~=')[0].split('>=')[0].split('<=')[0].split('>')[0].split('<')[0].split(';')[0] == 'PyYAML'
            if ln and not ln.startswith('#') and ln.split()[0].split('==')[0].split('~=')[0].split('>=')[0].split('<=')[0].split('>')[0].split('<')[0].split(';')[0] == 'PyYAML'
        ), "PyYAML should be in requirements-dev.txt for workflow validation"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# This test file was generated to validate workflow YAML changes
# in branch: codex/fix-env-var-naming-test-in-pr-agent-workflow
# Generated: 2024-11-24
# Purpose: Validate YAML structure and workflow simplifications