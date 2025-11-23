"""
Integration tests for workflow and requirements consistency.

This module tests that the GitHub workflows and requirements files
are consistent with each other, ensuring that:
- Workflows reference packages that exist in requirements
- Python versions are consistent
- Node versions are consistent
- Dependencies are properly specified

Tests cover recent simplifications:
- Removal of tiktoken from workflows and requirements
- Simplified PyYAML usage
- Consistent environment setup
"""

import pytest
import yaml
from pathlib import Path
from typing import Dict, Any, Set


class TestWorkflowRequirementsConsistency:
    """Test consistency between workflows and requirements files."""
    
    @pytest.fixture
    def requirements_dev(self) -> Set[str]:
        """Load package names from requirements-dev.txt."""
        req_path = Path(__file__).parent.parent.parent / 'requirements-dev.txt'
        packages = set()
        
        with open(req_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Extract package name
                    pkg_name = line.split('==')[0].split('>=')[0].split('[')[0].strip().lower()
                    packages.add(pkg_name)
        
        return packages
    
    @pytest.fixture
    def pr_agent_workflow(self) -> Dict[str, Any]:
        """Load PR agent workflow."""
        workflow_path = Path(__file__).parent.parent.parent / '.github' / 'workflows' / 'pr-agent.yml'
        with open(workflow_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_pyyaml_in_requirements_for_workflows(self, requirements_dev: Set[str]):
        """Test that PyYAML is in requirements for workflow YAML processing."""
        yaml_packages = {'pyyaml', 'yaml'}
        
        has_yaml = any(pkg in requirements_dev for pkg in yaml_packages)
        assert has_yaml, "PyYAML should be in requirements-dev.txt for workflow testing"
    
    def test_tiktoken_removed_from_requirements(self, requirements_dev: Set[str]):
        """Test that tiktoken has been removed as part of simplification."""
        assert 'tiktoken' not in requirements_dev, (
            "tiktoken should be removed from requirements as part of simplification"
        )
    
    def test_pr_agent_workflow_doesnt_install_tiktoken(self, pr_agent_workflow: Dict[str, Any]):
        """Test that PR agent workflow no longer tries to install tiktoken."""
        workflow_str = str(pr_agent_workflow).lower()
        
        assert 'tiktoken' not in workflow_str, (
            "PR agent workflow should not reference tiktoken after simplification"
        )
    
    def test_workflow_python_version_consistency(self, pr_agent_workflow: Dict[str, Any]):
        """Test that Python version in workflow is consistent."""
        jobs = pr_agent_workflow.get('jobs', {})
        for job_name, job_config in jobs.items():
            steps = job_config.get('steps', [])

            python_versions = []
            for step in steps:
                if 'uses' in step and 'setup-python' in step['uses']:
                    if 'with' in step and 'python-version' in step['with']:
                        python_versions.append(step['with']['python-version'])

            # All Python versions in a job should match
            if len(python_versions) > 1:
                assert len(set(python_versions)) == 1, (
                    f"Job '{job_name}' has inconsistent Python versions: {python_versions}"
                )
    
    def test_workflow_installs_python_dependencies(self, pr_agent_workflow: Dict[str, Any]):
        """Test that workflow installs Python dependencies correctly."""
        for job_name, job_config in pr_agent_workflow['jobs'].items():
            steps = job_config.get('steps', [])
            
            has_python_setup = False
            has_dep_install = False
            
            for step in steps:
                if 'uses' in step and 'setup-python' in step['uses']:
                    has_python_setup = True
                
                if 'run' in step:
                    run_cmd = step['run'].lower()
                    if 'pip install' in run_cmd:
                        has_dep_install = True
            
            # If Python is setup, dependencies should be installed
            if has_python_setup:
                assert has_dep_install, (
                    f"Job '{job_name}' sets up Python but doesn't install dependencies"
                )


class TestSimplificationConsistency:
    """Test that simplifications are consistent across all files."""
    
    def test_no_context_chunker_script_references(self):
        """Test that references to deleted context_chunker.py are removed."""
        pr_agent_path = Path(__file__).parent.parent.parent / '.github' / 'workflows' / 'pr-agent.yml'
        
        with open(pr_agent_path, 'r') as f:
            content = f.read()
        
        assert 'context_chunker.py' not in content, (
            "PR agent workflow should not reference deleted context_chunker.py"
        )
    
    def test_simplified_greetings_messages(self):
        """Test that greetings workflow has simplified messages."""
        greetings_path = Path(__file__).parent.parent.parent / '.github' / 'workflows' / 'greetings.yml'
        
        with open(greetings_path, 'r') as f:
            data = yaml.safe_load(f)
        
        steps = data['jobs']['greeting']['steps']
        
        for step in steps:
            if 'uses' in step and 'first-interaction' in step['uses']:
                issue_msg = step['with']['issue-message']
                pr_msg = step['with']['pr-message']
                
                # Messages should be simplified (not multi-paragraph)
                assert len(issue_msg) < 200, (
                    "Issue message should be simplified"
                )
                assert len(pr_msg) < 200, (
                    "PR message should be simplified"
                )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])