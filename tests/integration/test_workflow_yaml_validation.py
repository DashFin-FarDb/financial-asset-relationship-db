"""
Comprehensive validation tests for GitHub workflow YAML files.

This module tests the structure, syntax, and best practices of all
GitHub Actions workflow files, with special focus on recent changes:
- Simplified greetings workflow
- Simplified labeler workflow  
- Simplified APIsec scan workflow
- Simplified PR agent workflow

Tests cover:
- YAML syntax validation
- Required workflow structure
- Security best practices
- Performance considerations
- Error handling
"""

import os
import pytest
import yaml
from pathlib import Path
from typing import Dict, Any, List


class TestWorkflowYAMLSyntax:
    """Test YAML syntax and basic structure of workflow files."""
    
    @pytest.fixture
    def workflows_dir(self) -> Path:
        """Get the workflows directory path."""
        return Path(__file__).parent.parent.parent / '.github' / 'workflows'
    
    @pytest.fixture
    def workflow_files(self, workflows_dir: Path) -> List[Path]:
        """Get all workflow YAML files."""
        return list(workflows_dir.glob('*.yml')) + list(workflows_dir.glob('*.yaml'))
    
    def test_all_workflows_are_valid_yaml(self, workflow_files: List[Path]):
        """Test that all workflow files contain valid YAML."""
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                try:
                    yaml.safe_load(f)
                except yaml.YAMLError as e:
                    pytest.fail(f"Invalid YAML in {workflow_file.name}: {e}")
    
    def test_workflows_have_required_top_level_keys(self, workflow_files: List[Path]):
        """Test that workflows have required top-level keys."""
        required_keys = {'name', 'on', 'jobs'}
        
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                data = yaml.safe_load(f)
            
            missing_keys = required_keys - set(data.keys())
            assert not missing_keys, (
                f"{workflow_file.name} missing required keys: {missing_keys}"
            )
    
    def test_workflow_names_are_descriptive(self, workflow_files: List[Path]):
        """Test that workflow names are descriptive and not empty."""
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                data = yaml.safe_load(f)
            
            name = data.get('name', '')
            assert name and len(name) > 3, (
                f"{workflow_file.name} has empty or too short name: '{name}'"
            )
            assert not name.isupper(), (
                f"{workflow_file.name} name should not be all uppercase: '{name}'"
            )
    
    def test_no_duplicate_keys_in_yaml(self, workflow_files: List[Path]):
        """Test that YAML files don't have duplicate keys within the same object.
        
        Note: This is a simplified check that may not catch all duplicates due to
        the complexity of YAML syntax (multiline strings, flow syntax, etc.). 
        It primarily checks for obvious duplicates that would cause issues.
        """
        import re
        
        for workflow_file in workflow_files:
            # Use PyYAML's safer duplicate key detection via custom constructor
            def no_duplicates_constructor(loader, node, deep=False):
                """Check for duplicate keys during YAML loading."""
                mapping = {}
                for key_node, value_node in node.value:
                    key = loader.construct_object(key_node, deep=deep)
                    if key in mapping:
                        raise yaml.constructor.ConstructorError(
                            f"Duplicate key: {key!r}",
                            key_node.start_mark
                        )
                    mapping[key] = loader.construct_object(value_node, deep=deep)
                return mapping
            
            # Create a custom loader that checks for duplicates
            class UniqueKeyLoader(yaml.SafeLoader):
                pass
            
            UniqueKeyLoader.add_constructor(
                yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                no_duplicates_constructor
            )
            
            try:
                with open(workflow_file, 'r') as f:
                    yaml.load(f, Loader=UniqueKeyLoader)
            except yaml.constructor.ConstructorError as e:
                pytest.fail(
                    f"{workflow_file.name} has duplicate key: {e.problem}"
                )


class TestGreetingsWorkflow:
    """Test the greetings workflow specifically."""
    
    @pytest.fixture
    def greetings_workflow(self) -> Dict[str, Any]:
        """Load the greetings workflow."""
        workflow_path = Path(__file__).parent.parent.parent / '.github' / 'workflows' / 'greetings.yml'
        with open(workflow_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_greetings_workflow_structure(self, greetings_workflow: Dict[str, Any]):
        """Test that greetings workflow has correct structure."""
        assert greetings_workflow['name'] == 'Greetings'
        assert 'on' in greetings_workflow
        assert 'issues' in greetings_workflow['on'] or 'pull_request' in greetings_workflow['on']
        assert 'jobs' in greetings_workflow
        assert 'greeting' in greetings_workflow['jobs']
    
    def test_greetings_uses_first_interaction_action(self, greetings_workflow: Dict[str, Any]):
        """Test that greetings workflow uses the first-interaction action."""
        steps = greetings_workflow['jobs']['greeting']['steps']
        action_found = False
        
        for step in steps:
            if 'uses' in step and 'first-interaction' in step['uses']:
                action_found = True
                # Check required inputs
                assert 'with' in step
                assert 'repo-token' in step['with']
                assert 'issue-message' in step['with']
                assert 'pr-message' in step['with']
        
        assert action_found, "Greetings workflow should use first-interaction action"
    
    def test_greetings_has_appropriate_messages(self, greetings_workflow: Dict[str, Any]):
        """Test that greeting messages are present and not empty."""
        steps = greetings_workflow['jobs']['greeting']['steps']
        
        for step in steps:
            if 'uses' in step and 'first-interaction' in step['uses']:
                issue_msg = step['with']['issue-message']
                pr_msg = step['with']['pr-message']
                
                assert issue_msg and len(issue_msg) > 10, "Issue message should be meaningful"
                assert pr_msg and len(pr_msg) > 10, "PR message should be meaningful"


class TestLabelerWorkflow:
    """Test the label workflow specifically."""
    
    @pytest.fixture
    def labeler_workflow(self) -> Dict[str, Any]:
        """Load the labeler workflow."""
        workflow_path = Path(__file__).parent.parent.parent / '.github' / 'workflows' / 'label.yml'
        with open(workflow_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_labeler_workflow_structure(self, labeler_workflow: Dict[str, Any]):
        """Test that labeler workflow has correct structure."""
        assert labeler_workflow['name'] == 'Labeler'
        assert 'on' in labeler_workflow
        assert 'pull_request' in labeler_workflow['on']
        assert 'jobs' in labeler_workflow
    
    def test_labeler_has_appropriate_permissions(self, labeler_workflow: Dict[str, Any]):
        """Test that labeler has correct permissions."""
        jobs = labeler_workflow['jobs']
        
        for job_name, job_config in jobs.items():
            if 'permissions' in job_config:
                perms = job_config['permissions']
                assert 'contents' in perms or 'pull-requests' in perms, (
                    f"Labeler job '{job_name}' should have appropriate permissions"
                )
    
    def test_labeler_uses_labeler_action(self, labeler_workflow: Dict[str, Any]):
        """Test that labeler workflow uses the labeler action."""
        for job_name, job_config in labeler_workflow['jobs'].items():
            steps = job_config.get('steps', [])
            action_found = False
            
            for step in steps:
                if 'uses' in step and 'labeler' in step['uses']:
                    action_found = True
                    # Check required inputs
                    assert 'with' in step
                    assert 'repo-token' in step['with']
            
            if 'labeler' in job_name.lower():
                assert action_found, f"Labeler job '{job_name}' should use labeler action"


class TestAPISecWorkflow:
    """Test the APISec scan workflow."""
    
    @pytest.fixture
    def apisec_workflow(self) -> Dict[str, Any]:
        """Load the APISec workflow."""
        workflow_path = Path(__file__).parent.parent.parent / '.github' / 'workflows' / 'apisec-scan.yml'
        with open(workflow_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_apisec_workflow_structure(self, apisec_workflow: Dict[str, Any]):
        """Test that APISec workflow has correct structure."""
        assert 'name' in apisec_workflow
        assert 'on' in apisec_workflow
        assert 'jobs' in apisec_workflow
    
    def test_apisec_has_security_permissions(self, apisec_workflow: Dict[str, Any]):
        """Test that APISec workflow has appropriate security permissions."""
        # Check top-level permissions
        if 'permissions' in apisec_workflow:
            perms = apisec_workflow['permissions']
            # Security workflows typically need security-events write
            assert 'security-events' in perms or 'contents' in perms
    
    def test_apisec_uses_apisec_action(self, apisec_workflow: Dict[str, Any]):
        """Test that APISec workflow uses the APISec action."""
        for job_name, job_config in apisec_workflow['jobs'].items():
            steps = job_config.get('steps', [])
            
            for step in steps:
                if 'uses' in step and 'apisec' in step['uses'].lower():
                    # Check that required secrets are referenced
                    if 'with' in step:
                        step_str = str(step)
                        assert 'apisec_username' in step_str or 'username' in step_str.lower()
    
    def test_apisec_simplified_no_credential_check(self, apisec_workflow: Dict[str, Any]):
        """Test that APISec workflow no longer has redundant credential checking."""
        for job_name, job_config in apisec_workflow['jobs'].items():
            steps = job_config.get('steps', [])
            
            for step in steps:
                # Check that we removed the credential check step
                if 'name' in step:
                    assert 'Check for APISec credentials' not in step['name'], (
                        "Credential check step should have been removed for simplification"
                    )


class TestPRAgentWorkflow:
    """Test the PR Agent workflow."""
    
    @pytest.fixture
    def pr_agent_workflow(self) -> Dict[str, Any]:
        """Load the PR Agent workflow."""
        workflow_path = Path(__file__).parent.parent.parent / '.github' / 'workflows' / 'pr-agent.yml'
        with open(workflow_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_pr_agent_workflow_structure(self, pr_agent_workflow: Dict[str, Any]):
        """Test that PR Agent workflow has correct structure."""
        assert 'name' in pr_agent_workflow
        assert 'on' in pr_agent_workflow
        assert 'jobs' in pr_agent_workflow
    
    def test_pr_agent_no_duplicate_setup_python(self, pr_agent_workflow: Dict[str, Any]):
        """Test that PR Agent workflow doesn't have duplicate 'Setup Python' steps."""
        for job_name, job_config in pr_agent_workflow['jobs'].items():
            steps = job_config.get('steps', [])
            setup_python_count = 0
            
            for step in steps:
                if 'name' in step and 'Setup Python' in step['name']:
                    setup_python_count += 1
            
            assert setup_python_count <= 1, (
                f"Job '{job_name}' has {setup_python_count} 'Setup Python' steps, should have at most 1"
            )
    
    def test_pr_agent_has_python_and_node_setup(self, pr_agent_workflow: Dict[str, Any]):
        """Test that PR Agent workflow sets up both Python and Node.js."""
        for job_name, job_config in pr_agent_workflow['jobs'].items():
            steps = job_config.get('steps', [])
            has_python = False
            has_node = False
            
            for step in steps:
                if 'uses' in step:
                    if 'setup-python' in step['uses']:
                        has_python = True
                    if 'setup-node' in step['uses']:
                        has_node = True
            
            # PR agent needs both
            if 'agent' in job_name.lower():
                assert has_python, f"Job '{job_name}' should setup Python"
                assert has_node, f"Job '{job_name}' should setup Node.js"
    
    def test_pr_agent_simplified_context_handling(self, pr_agent_workflow: Dict[str, Any]):
        """Test that PR Agent workflow has simplified context handling."""
        for job_name, job_config in pr_agent_workflow['jobs'].items():
            steps = job_config.get('steps', [])
            
            # Check that context chunking steps have been removed/simplified
            for step in steps:
                if 'name' in step:
                    # Old complex step names that should be gone
                    assert 'Fetch PR Context with Chunking' not in step['name'], (
                        "Complex context chunking should be simplified"
                    )
                    assert 'Install tiktoken' not in step['name'], (
                        "tiktoken installation should be removed"
                    )


class TestWorkflowSecurityBestPractices:
    """Test security best practices across all workflows."""
    
    @pytest.fixture
    def all_workflows(self) -> Dict[str, Dict[str, Any]]:
        """Load all workflow files."""
        workflows_dir = Path(__file__).parent.parent.parent / '.github' / 'workflows'
        workflows = {}
        
        for workflow_file in workflows_dir.glob('*.yml'):
            with open(workflow_file, 'r') as f:
                workflows[workflow_file.name] = yaml.safe_load(f)
        
        return workflows
    
    def test_workflows_use_pinned_action_versions(self, all_workflows: Dict[str, Dict[str, Any]]):
        """Test that workflows use pinned versions for third-party actions."""
        for workflow_name, workflow_data in all_workflows.items():
            for job_name, job_config in workflow_data['jobs'].items():
                steps = job_config.get('steps', [])
                
                for step in steps:
                    if 'uses' in step:
                        action = step['uses']
                        # GitHub official actions can use @v4, @v5, etc.
                        if action.startswith(('actions/', './', '../')):
                            continue
                        
                        # Third-party actions should be pinned to SHA or @v1, @v2, etc.
                        assert '@' in action, (
                            f"{workflow_name} - {job_name}: Action '{action}' should have version pinned"
                        )
    
    def test_workflows_have_explicit_permissions(self, all_workflows: Dict[str, Dict[str, Any]]):
        """Test that workflows explicitly define permissions when needed."""
        for workflow_name, workflow_data in all_workflows.items():
            # Workflows that write to repo should have explicit permissions
            jobs = workflow_data['jobs']
            
            for job_name, job_config in jobs.items():
                # If job has actions that typically need permissions, check they're defined
                steps = job_config.get('steps', [])
                needs_permissions = False
                
                for step in steps:
                    if 'uses' in step:
                        action = step['uses']
                        # Actions that typically need permissions
                        if any(keyword in action.lower() for keyword in ['comment', 'label', 'issue', 'pr']):
                            needs_permissions = True
                
                if needs_permissions:
                    # Either job-level or workflow-level permissions should exist
                    has_perms = ('permissions' in job_config or 
                                'permissions' in workflow_data)
                    
                    # Note: This is a soft check - some actions use GITHUB_TOKEN automatically
                    if not has_perms:
                        print(f"Warning: {workflow_name} - {job_name} may need explicit permissions")
    
    def test_workflows_dont_expose_secrets_in_logs(self, all_workflows: Dict[str, Dict[str, Any]]):
        """Test that workflows don't echo or print secrets."""
        dangerous_patterns = ['echo.*secrets\\.', 'print.*secrets\\.', 'console\\.log.*secrets\\.']
        
        for workflow_name, workflow_data in all_workflows.items():
            workflow_str = str(workflow_data).lower()
            
            for pattern in dangerous_patterns:
                import re
                if re.search(pattern, workflow_str):
                    pytest.fail(
                        f"{workflow_name} may be exposing secrets in logs (pattern: {pattern})"
                    )


class TestWorkflowPerformance:
    """Test performance considerations in workflows."""
    
    @pytest.fixture
    def all_workflows(self) -> Dict[str, Dict[str, Any]]:
        """Load all workflow files."""
        workflows_dir = Path(__file__).parent.parent.parent / '.github' / 'workflows'
        workflows = {}
        
        for workflow_file in workflows_dir.glob('*.yml'):
            with open(workflow_file, 'r') as f:
                workflows[workflow_file.name] = yaml.safe_load(f)
        
        return workflows
    
    def test_workflows_have_reasonable_timeouts(self, all_workflows: Dict[str, Dict[str, Any]]):
        """Test that workflows have timeout-minutes set for long-running jobs."""
        for workflow_name, workflow_data in all_workflows.items():
            for job_name, job_config in workflow_data['jobs'].items():
                # Jobs with many steps should have timeouts
                steps = job_config.get('steps', [])
                
                if len(steps) > 5:
                    if 'timeout-minutes' not in job_config:
                        print(f"Info: {workflow_name} - {job_name} with {len(steps)} steps has no timeout")
    
    def test_workflows_use_concurrency_groups(self, all_workflows: Dict[str, Dict[str, Any]]):
        """Test that workflows that may run multiple times use concurrency groups."""
        for workflow_name, workflow_data in all_workflows.items():
            triggers = workflow_data.get('on', {})
            
            # If triggered on PR synchronize, should have concurrency
            if isinstance(triggers, dict):
                if 'pull_request' in triggers or 'pull_request_target' in triggers:
                    for job_name, job_config in workflow_data['jobs'].items():
                        # Check for concurrency at job or workflow level
                        has_concurrency = ('concurrency' in job_config or 
                                          'concurrency' in workflow_data)
                        
                        if not has_concurrency:
                            print(f"Info: {workflow_name} - {job_name} may benefit from concurrency group")


class TestRequirementsDevChanges:
    """Test changes to requirements-dev.txt for workflow support."""
    
    @pytest.fixture
    def requirements_dev(self) -> List[str]:
        """Load requirements-dev.txt."""
        req_path = Path(__file__).parent.parent.parent / 'requirements-dev.txt'
        with open(req_path, 'r') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    def test_pyyaml_is_present(self, requirements_dev: List[str]):
        """Test that PyYAML is in requirements-dev.txt for workflow testing."""
        pyyaml_found = any('pyyaml' in req.lower() or 'yaml' in req.lower() 
                           for req in requirements_dev)
        
        assert pyyaml_found, "PyYAML should be in requirements-dev.txt for workflow testing"
    
    def test_no_duplicate_requirements(self, requirements_dev: List[str]):
        """Test that there are no duplicate package specifications."""
        # Extract package names (before == or >=)
        packages = []
        for req in requirements_dev:
            pkg_name = req.split('==')[0].split('>=')[0].split('[')[0].strip().lower()
            packages.append(pkg_name)
        
        duplicates = [pkg for pkg in set(packages) if packages.count(pkg) > 1]
        assert not duplicates, f"Duplicate packages found in requirements-dev.txt: {duplicates}"
    
    def test_requirements_have_version_pins(self, requirements_dev: List[str]):
        """Test that requirements have version specifications for reproducibility."""
        for req in requirements_dev:
            # Skip -e editable installs
            if req.startswith('-e') or req.startswith('git+'):
                continue
            
            # Should have version specifier
            has_version = any(op in req for op in ['==', '>=', '<=', '~=', '!='])
            
            # This is a recommendation, not a hard requirement
            if not has_version:
                print(f"Info: {req} has no version pin")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])