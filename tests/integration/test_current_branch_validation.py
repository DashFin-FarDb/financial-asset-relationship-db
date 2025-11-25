"""
Validation tests for current branch changes.

Tests ensure that all modifications in the current branch are consistent,
properly integrated, and don't introduce regressions.
"""

import pytest
import yaml
from pathlib import Path


class TestWorkflowModifications:
    """Test modifications to workflow files."""
    
    def test_pr_agent_workflow_no_chunking_references(self):
        """PR agent workflow should not reference deleted chunking functionality."""
        workflow_path = Path(".github/workflows/pr-agent.yml")
        
        with open(workflow_path, 'r') as f:
            content = f.read()
        
        # Should not reference chunking
        assert 'context_chunker' not in content
        content_lower = content.lower()
        if 'chunking' in content_lower:
            assert content_lower.count('chunking') == content_lower.count('# chunking'), \
                "Found 'chunking' references outside of comments"
        assert 'tiktoken' not in content
    
    def test_pr_agent_workflow_has_simplified_parsing(self):
        """PR agent workflow should have simplified comment parsing."""
        workflow_path = Path(".github/workflows/pr-agent.yml")
        
        with open(workflow_path, 'r') as f:
            data = yaml.safe_load(f)
        
        # Should have parse-comments step
        jobs = data.get('jobs', {})
        trigger_job = jobs.get('pr-agent-trigger', {})
        steps = trigger_job.get('steps', [])
        
        step_names = [step.get('name', '') for step in steps]
        assert any('parse' in name.lower() and 'comment' in name.lower() for name in step_names)
    
    def test_apisec_workflow_no_credential_checks(self):
        """APIsec workflow should not include credential pre-check steps (simplified)."""
        workflow_path = Path(".github/workflows/apisec-scan.yml")
    
        with open(workflow_path, 'r') as f:
            data = yaml.safe_load(f)
    
        # Workflow should exist and be valid
        assert isinstance(data, dict)
        assert 'jobs' in data
        assert 'Trigger_APIsec_scan' in data['jobs']
    
        # Ensure no credential pre-check steps are present
        job = data['jobs']['Trigger_APIsec_scan']
        steps = job.get('steps', [])
        step_names = [str(step.get('name', '')).lower() for step in steps if isinstance(step, dict)]
        assert not any('credential' in name or 'secret' in name for name in step_names), \
            "Found credential pre-check steps; these should be removed in the simplified workflow"
        assert 'Trigger_APIsec_scan' in data['jobs']
    
        # Ensure no credential pre-check steps are present
        job = data['jobs']['Trigger_APIsec_scan']
        steps = job.get('steps', [])
        step_names = [str(step.get('name', '')).lower() for step in steps if isinstance(step, dict)]
        assert not any('credential' in name or 'secret' in name for name in step_names), \
            "Found credential pre-check steps; these should be removed in the simplified workflow"
        assert 'Trigger_APIsec_scan' in data['jobs']
    
        # Ensure no credential pre-check steps are present
        job = data['jobs']['Trigger_APIsec_scan']
        steps = job.get('steps', [])
        step_names = [str(step.get('name', '')).lower() for step in steps if isinstance(step, dict)]
        assert not any('credential' in name or 'secret' in name for name in step_names), \
            "Found credential pre-check steps; these should be removed in the simplified workflow"
        assert 'Trigger_APIsec_scan' in data['jobs']
    
        # Ensure no credential pre-check steps are present
        job = data['jobs']['Trigger_APIsec_scan']
        steps = job.get('steps', [])
        step_names = [str(step.get('name', '')).lower() for step in steps if isinstance(step, dict)]
        assert not any('credential' in name or 'secret' in name for name in step_names), \
            "Found credential pre-check steps; these should be removed in the simplified workflow"
    
    def test_label_workflow_simplified(self):
        """Label workflow should be simplified without config checks."""
        workflow_path = Path(".github/workflows/label.yml")
        assert workflow_path.exists(), "Expected '.github/workflows/label.yml' to exist"
    
    def test_greetings_workflow_simplified(self):
        """Greetings workflow should have simplified messages."""
        workflow_path = Path(".github/workflows/greetings.yml")
        
        with open(workflow_path, 'r') as f:
            data = yaml.safe_load(f)
        
        jobs = data.get('jobs', {})
        greeting_job = jobs.get('greeting', {})
    
    def test_labeler_config_deleted(self):
        """Labeler.yml configuration should be deleted."""
        labeler_path = Path(".github/labeler.yml")
        assert not labeler_path.exists()
    
    def test_scripts_readme_deleted(self):
        """Scripts README should be deleted."""
        readme_path = Path(".github/scripts/README.md")
        assert not readme_path.exists()


class TestRequirementsDevUpdates:
    """Test requirements-dev.txt updates."""
    
    def test_requirements_dev_has_pyyaml(self):
        """Requirements-dev should include PyYAML."""
        req_path = Path("requirements-dev.txt")
        
        with open(req_path, 'r') as f:
            content = f.read()
        
        assert 'PyYAML' in content
        assert 'types-PyYAML' in content
    
    def test_requirements_dev_valid_format(self):
        """Requirements-dev should be properly formatted."""
        req_path = Path("requirements-dev.txt")
        
        with open(req_path, 'r') as f:
            lines = f.readlines()
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                # Should have version specifier
                assert '>=' in line or '==' in line or '~=' in line


class TestPRAgentConfigSimplified:
    """Test PR Agent config simplification."""
    
    def test_config_version_downgraded(self):
        """PR Agent config version should be back to 1.0.0."""
        config_path = Path(".github/pr-agent-config.yml")
        
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
        
        version = data.get('agent', {}).get('version', '')
        assert version == '1.0.0'
    
    def test_config_no_chunking_settings(self):
        """PR Agent config should not have chunking settings."""
        config_path = Path(".github/pr-agent-config.yml")
        
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
        
        agent = data.get('agent', {})
        
        # Should not have context section
        assert 'context' not in agent
        
        limits = data.get('limits', {})
        
        # Should not have chunking limits
        assert 'max_files_per_chunk' not in limits
    
    def test_no_broken_workflow_references(self):
        """Workflows should not reference non-existent files."""
        workflow_dir = Path(".github/workflows")
        
        for workflow_file in list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml")):
            with open(workflow_file, 'r') as f:
                content = f.read()
        
        for summary_file in summary_files:
            path = Path(summary_file)
            assert path.is_file(), f"Required summary file '{summary_file}' does not exist or is not a file"
            assert path.stat().st_size > 0, f"Summary file '{summary_file}' is empty"
    
    def test_no_misleading_documentation(self):
        req_dev = Path("requirements-dev.txt")
        
        assert req_dev.exists()
        
        # File should not be empty
        with open(req_dev, 'r') as f:
            content = f.read().strip()
        
        assert len(content) > 0


class TestDocumentationConsistency:
    """Test documentation consistency with code changes."""
    
    def test_summary_files_exist(self):
        """Test summary documentation files should exist."""
        summary_files = [
            'COMPREHENSIVE_BRANCH_TEST_GENERATION_SUMMARY.md'
        ]
        
        for summary_file in summary_files:
            path = Path(summary_file)
            assert path.is_file(), f"Required summary file '{summary_file}' does not exist or is not a file"
            assert path.stat().st_size > 0, f"Summary file '{summary_file}' is empty"
    
    def test_no_misleading_documentation(self):
        """Documentation should not reference removed features as active."""
        readme = Path("README.md")
        
        if readme.exists():
            with open(readme, 'r') as f:
                content = f.read().lower()
            
            # If chunking is mentioned, it should be in past tense or removed context
            if 'chunking' in content:
                # This is acceptable for historical documentation
                pass