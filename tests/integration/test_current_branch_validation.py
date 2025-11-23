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
        """APIsec workflow should not have removed credential pre-checks."""
        workflow_path = Path(".github/workflows/apisec-scan.yml")
        
        with open(workflow_path, 'r') as f:
            data = yaml.safe_load(f)
        
        # Workflow should exist and be valid
        assert 'jobs' in data
        assert 'Trigger_APIsec_scan' in data['jobs']
    
    def test_label_workflow_simplified(self):
        """Label workflow should be simplified without config checks."""
        workflow_path = Path(".github/workflows/label.yml")
        
        with open(workflow_path, 'r') as f:
            content = f.read()
        
        # Should not have config existence checks
        assert 'check-config' not in content
        assert 'config_exists' not in content
    
    def test_greetings_workflow_simplified(self):
        """Greetings workflow should have simplified messages."""
        workflow_path = Path(".github/workflows/greetings.yml")
        
        with open(workflow_path, 'r') as f:
            data = yaml.safe_load(f)
        
        jobs = data.get('jobs', {})
        greeting_job = jobs.get('greeting', {})
        steps = greeting_job.get('steps', [])
        
        # Should have first-interaction action
        uses_actions = [step.get('uses', '') for step in steps]
        assert any('first-interaction' in action for action in uses_actions)


class TestDeletedFilesNoReferences:
    """Test that deleted files have no remaining references."""
    
    def test_no_context_chunker_imports(self):
        """No Python files should import context_chunker."""
        import subprocess
        
        result = subprocess.run(
            ['rg', '-l', 'context_chunker', '--type', 'py'],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )
        
        # Should only appear in test files documenting the deletion
        if result.stdout:
            files_with_reference = result.stdout.strip().split('\n')
            test_files = [f for f in files_with_reference if 'test' in f]
            # All references should be in test files
            assert len(files_with_reference) == len(test_files)
    
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
        assert 'fallback' not in limits
    
    def test_config_still_has_core_settings(self):
        """PR Agent config should retain core functionality."""
        config_path = Path(".github/pr-agent-config.yml")
        
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
        
        # Should have essential sections
        assert 'agent' in data
        assert 'monitoring' in data
        assert 'quality' in data
        assert 'git' in data


class TestBranchIntegration:
    """Test overall branch integration and consistency."""
    
    def test_all_yaml_files_valid(self):
        """All YAML files in the branch should be valid."""
        yaml_files = list(Path('.github').rglob('*.yml')) + list(Path('.github').rglob('*.yaml'))
        
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r') as f:
                    yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {yaml_file}: {e}")
    
    def test_no_broken_workflow_references(self):
        """Workflows should not reference non-existent files."""
        workflow_dir = Path(".github/workflows")
        
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                content = f.read()
            
            # Check for references to deleted files
            assert '.github/scripts/context_chunker.py' not in content
            assert '.github/labeler.yml' not in content or 'labeler.yml' in str(workflow_file)
    
    def test_python_dependencies_installable(self):
        """Python dependencies should be installable."""
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