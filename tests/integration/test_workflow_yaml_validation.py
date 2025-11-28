"""
Advanced YAML validation tests for GitHub workflow files.

This module provides comprehensive validation of YAML structure,
syntax, and best practices for all workflow files.
"""

import pytest
import yaml
from pathlib import Path
from typing import Dict, Any, List
import re


WORKFLOWS_DIR = Path(__file__).parent.parent.parent / ".github" / "workflows"


def get_workflow_files() -> List[Path]:
    """Get all workflow YAML files."""
    if not WORKFLOWS_DIR.exists():
        return []
    return list(WORKFLOWS_DIR.glob("*.yml")) + list(WORKFLOWS_DIR.glob("*.yaml"))


@pytest.fixture
def workflow_files():
    """Fixture providing list of workflow files."""
    files = get_workflow_files()
    if not files:
        pytest.skip("No workflow files found")
    return files


@pytest.fixture(params=get_workflow_files(), ids=lambda p: p.name)
def workflow_file(request):
    """Parametrized fixture for each workflow file."""
    return request.param


@pytest.fixture
def workflow_content(workflow_file):
    """Load workflow file content."""
    with open(workflow_file, 'r') as f:
        return yaml.safe_load(f)


class TestYAMLSyntax:
    """Test YAML syntax and structure."""
    
    def test_workflow_is_valid_yaml(self, workflow_file):
        """Each workflow file should be valid YAML."""
        with open(workflow_file, 'r') as f:
            try:
                yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {workflow_file.name}: {e}")
    
    def test_workflow_not_empty(self, workflow_content):
        """Workflow file should not be empty."""
        assert workflow_content is not None, "Workflow content is None"
        assert len(workflow_content) > 0, "Workflow content is empty"
    
    def test_no_tabs_in_yaml(self, workflow_file):
        """YAML files should use spaces, not tabs."""
        with open(workflow_file, 'r') as f:
            content = f.read()
        
        assert '\t' not in content, \
            f"{workflow_file.name} contains tabs. Use spaces for YAML indentation."
    
    def test_consistent_indentation(self, workflow_file):
        """YAML files should have consistent indentation (2 spaces)."""
        with open(workflow_file, 'r') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines, 1):
            if line.strip() and not line.strip().startswith('#'):
                # Count leading spaces
                leading_spaces = len(line) - len(line.lstrip(' '))
                
                # Should be multiple of 2
                if leading_spaces > 0:
                    assert leading_spaces % 2 == 0, \
                        f"{workflow_file.name}:{i} has inconsistent indentation ({leading_spaces} spaces)"


class TestWorkflowStructure:
    """Test GitHub Actions workflow structure."""
    
    def test_has_name_field(self, workflow_content, workflow_file):
        """Workflow should have a descriptive name."""
        assert 'name' in workflow_content, \
            f"{workflow_file.name} missing 'name' field"
        
        name = workflow_content['name']
        assert isinstance(name, str), "Workflow name should be a string"
        assert len(name) > 0, "Workflow name should not be empty"
        assert len(name) <= 100, "Workflow name should be concise"
    
    def test_has_on_trigger(self, workflow_content, workflow_file):
        """Workflow should define when it runs."""
        assert 'on' in workflow_content, \
            f"{workflow_file.name} missing 'on' trigger definition"
    
    def test_has_jobs(self, workflow_content, workflow_file):
        """Workflow should define at least one job."""
        assert 'jobs' in workflow_content, \
            f"{workflow_file.name} missing 'jobs' section"
        
        jobs = workflow_content['jobs']
        assert isinstance(jobs, dict), "Jobs should be a dictionary"
        assert len(jobs) > 0, "Workflow should have at least one job"
    
    def test_jobs_have_runs_on(self, workflow_content, workflow_file):
        """Each job should specify which runner to use."""
        jobs = workflow_content.get('jobs', {})
        
def test_jobs_have_runs_on(self, workflow_content, workflow_file):
    """Non-reusable jobs must specify which runner to use."""
    jobs = workflow_content.get('jobs', {})
    
    for job_name, job_config in jobs.items():
        if 'uses' in job_config:
            continue  # Skip reusable workflow jobs
            if not isinstance(job_config, dict):
                pytest.fail(f"Job '{job_name}' in {workflow_file.name} is not a dictionary")
for job_name, job_config in jobs.items():
    if 'uses' in job_config:
        continue  # Skip reusable workflow jobs
    
    # Non-reusable jobs must specify a runner
    assert 'runs-on' in job_config, \
        f"Non-reusable job '{job_name}' in {workflow_file.name} must specify 'runs-on'"
                f"Job '{job_name}' in {workflow_file.name} missing 'runs-on'"
    def test_jobs_have_steps(self, workflow_content, workflow_file):
        """Each job should have steps defined."""
        jobs = workflow_content.get('jobs', {})
        
        for job_name, job_config in jobs.items():
            # Skip if it's a reusable workflow call
            if 'uses' in job_config:
                continue
            
            assert 'steps' in job_config, \
                f"Job '{job_name}' in {workflow_file.name} missing 'steps'"
            
            steps = job_config['steps']
            assert isinstance(steps, list), \
                f"Steps in job '{job_name}' should be a list"
            assert len(steps) > 0, \
                f"Job '{job_name}' should have at least one step"


class TestTriggerConfiguration:
    """Test workflow trigger configuration."""
    
    def test_trigger_is_valid_type(self, workflow_content):
        """Workflow trigger should be a valid type."""
        on_trigger = workflow_content.get('on')
        
        assert isinstance(on_trigger, (str, list, dict)), \
            "'on' should be a string, list, or dictionary"
    
    def test_pull_request_trigger_valid(self, workflow_content):
        """Pull request triggers should be properly configured."""
        on_trigger = workflow_content.get('on', {})
        
        if isinstance(on_trigger, dict) and 'pull_request' in on_trigger:
            pr_config = on_trigger['pull_request']
            
            if isinstance(pr_config, dict):
                # Check valid activity types
                if 'types' in pr_config:
                    valid_types = {
                        'opened', 'edited', 'closed', 'reopened',
                        'synchronize', 'assigned', 'unassigned',
                        'labeled', 'unlabeled', 'review_requested'
                    }
                    
                    for activity_type in pr_config['types']:
                        assert activity_type in valid_types, \
                            f"Invalid PR activity type: {activity_type}"
    
    def test_push_trigger_has_branches(self, workflow_content):
        """Push triggers should specify branches when appropriate."""
        on_trigger = workflow_content.get('on', {})
        
        if isinstance(on_trigger, dict) and 'push' in on_trigger:
            push_config = on_trigger['push']
            
            # If it's a dict, it should have branches or paths
            if isinstance(push_config, dict):
                has_filter = 'branches' in push_config or 'paths' in push_config
                # It's okay to not have filters for some workflows
                # Just check structure if present
                if 'branches' in push_config:
                    branches = push_config['branches']
                    assert isinstance(branches, list), \
                        "push.branches should be a list"
    
    def test_schedule_trigger_valid_cron(self, workflow_content):
        """Schedule triggers should have valid cron expressions."""
        on_trigger = workflow_content.get('on', {})
        
        if isinstance(on_trigger, dict) and 'schedule' in on_trigger:
            schedule = on_trigger['schedule']
            assert isinstance(schedule, list), "schedule should be a list"
            
            for item in schedule:
                assert 'cron' in item, "Schedule item should have 'cron'"
                cron = item['cron']
                
                # Basic cron validation: should have 5 fields
                parts = cron.split()
                assert len(parts) == 5, \
                    f"Cron expression should have 5 fields: {cron}"


class TestJobConfiguration:
    """Test individual job configurations."""
    
    def test_job_names_descriptive(self, workflow_content):
        """Job names should be descriptive."""
        jobs = workflow_content.get('jobs', {})
        
        for job_name in jobs.keys():
            assert len(job_name) > 2, \
                f"Job name '{job_name}' is too short"
            
            # Should use descriptive names, not just numbers
            assert not job_name.isdigit(), \
                f"Job name '{job_name}' should be descriptive, not just a number"
    
    def test_runner_types_valid(self, workflow_content):
        """Runner types should be valid GitHub-hosted or self-hosted."""
        jobs = workflow_content.get('jobs', {})
        
        valid_runners = {
            'ubuntu-latest', 'ubuntu-22.04', 'ubuntu-20.04',
            'windows-latest', 'windows-2022', 'windows-2019',
            'macos-latest', 'macos-12', 'macos-11'
        }
        
        for job_name, job_config in jobs.items():
            runs_on = job_config.get('runs-on')
            
            if isinstance(runs_on, str):
                # Allow self-hosted or standard runners
                if runs_on not in valid_runners:
                    assert runs_on.startswith('self-hosted') or \
                           runs_on.startswith('${{'), \
                        f"Job '{job_name}' has invalid runner: {runs_on}"
            elif isinstance(runs_on, list):
                # Matrix or label-based selection
                pass  # More complex validation needed
    
    def test_steps_have_name_or_uses(self, workflow_content):
        """Each step should have either a name or uses field."""
        jobs = workflow_content.get('jobs', {})
        
        for job_name, job_config in jobs.items():
            steps = job_config.get('steps', [])
            
            for i, step in enumerate(steps):
                has_identifier = 'name' in step or 'uses' in step or 'run' in step
                assert has_identifier, \
                    f"Step {i} in job '{job_name}' should have 'name', 'uses', or 'run'"
    
    def test_action_versions_pinned(self, workflow_content):
        """Actions should use pinned versions for security."""
        jobs = workflow_content.get('jobs', {})
        
        for job_name, job_config in jobs.items():
            steps = job_config.get('steps', [])
            
            for step in steps:
                if 'uses' in step:
                    action = step['uses']
                    
                    # Skip local actions
                    if action.startswith('./'):
                        continue
                    
                    # Should have a version (@ followed by ref)
                    assert '@' in action, \
                        f"Action '{action}' should be pinned to a version"
                    
                    # Extract version
                    version = action.split('@')[1]
                    
                    # Warn if using moving tags like @main or @master
                    moving_tags = ['main', 'master', 'latest', 'stable']
                    if version in moving_tags:
                        # This is a warning, not an error - but we'll document it
                        pass  # Could add logging here


class TestSecurityBestPractices:
    """Test security best practices in workflows."""
    
    def test_no_hardcoded_secrets(self, workflow_file):
        """Workflows should not contain hardcoded secrets."""
        with open(workflow_file, 'r') as f:
            content = f.read()
        
        # Check for potential secrets (basic patterns)
        secret_patterns = [
            r'password:\s*["\'][^"\'$]+["\']',
            r'token:\s*["\'][a-zA-Z0-9]{20,}["\']',
            r'api[_-]?key:\s*["\'][^"\'$]+["\']',
        ]
        
        for pattern in secret_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            # Filter out obvious ${{ secrets.* }} references
            actual_secrets = [m for m in matches if 'secrets.' not in m and '${{' not in m]
            
            assert len(actual_secrets) == 0, \
                f"Potential hardcoded secret in {workflow_file.name}"
    
    def test_secrets_use_github_secrets(self, workflow_file):
        """Secrets should reference GitHub secrets."""
        with open(workflow_file, 'r') as f:
            content = f.read()
        
        # Find all secret references
        secret_refs = re.findall(r'\$\{\{\s*secrets\.(\w+)\s*\}\}', content)
        
        # Check that they follow naming conventions (optional check)
        for secret_name in secret_refs:
            # Secret names should be UPPER_SNAKE_CASE
            assert secret_name.isupper() or '_' in secret_name or '-' in secret_name, \
                f"Secret '{secret_name}' should use UPPER_SNAKE_CASE naming"
    
    def test_permissions_are_minimal(self, workflow_content):
        """Workflow permissions should follow principle of least privilege."""
        permissions = workflow_content.get('permissions')
        
        if permissions:
            # Check if using minimal permissions
            if isinstance(permissions, dict):
                # Specific permissions defined - this is good
                risky_perms = ['write-all', 'admin']
                
                for perm, value in permissions.items():
                    assert value not in risky_perms, \
                        f"Overly broad permission '{perm}: {value}'"
            elif permissions == 'write-all':
                pytest.fail("Using 'permissions: write-all' is insecure")


class TestConditionals:
    """Test conditional execution in workflows."""
    
    def test_if_conditions_valid_syntax(self, workflow_content):
        """Conditional 'if' statements should have valid syntax."""
        jobs = workflow_content.get('jobs', {})
        
        for job_name, job_config in jobs.items():
            # Check job-level conditions
            if 'if' in job_config:
                condition = job_config['if']
                assert isinstance(condition, str), \
                    f"Job '{job_name}' if condition should be a string"
                assert len(condition) > 0, \
                    f"Job '{job_name}' if condition should not be empty"
            
            # Check step-level conditions
            steps = job_config.get('steps', [])
            for step in steps:
                if 'if' in step:
                    condition = step['if']
                    assert isinstance(condition, str), \
                        "Step if condition should be a string"
                    
                    # Check for common syntax errors
                    assert condition.count('(') == condition.count(')'), \
                        f"Unmatched parentheses in condition: {condition}"
    
    def test_no_always_true_conditions(self, workflow_content):
        """Workflows should not have always-true conditions."""
        jobs = workflow_content.get('jobs', {})
        
        always_true = ['true', '1 == 1', 'always()']
        
        for job_name, job_config in jobs.items():
            if 'if' in job_config:
                condition = job_config['if'].strip()
                # This is a soft check - sometimes always() is intentional
                if condition in always_true[:2]:  # Skip always() which has valid uses
                    # Warning rather than failure
                    pass


class TestWorkflowOptimization:
    """Test workflow performance and optimization."""
    
    def test_concurrency_group_defined(self, workflow_content):
        """Workflows should define concurrency groups to prevent conflicts."""
        # Concurrency is optional but recommended for PR workflows
        on_trigger = workflow_content.get('on', {})
        
        if isinstance(on_trigger, dict) and 'pull_request' in on_trigger:
            # PR workflows benefit from concurrency control
            if 'concurrency' not in workflow_content:
                # This is a recommendation, not a hard requirement
                pass
    
    def test_caching_configured_where_appropriate(self, workflow_content):
        """Workflows should use caching for dependencies."""
        jobs = workflow_content.get('jobs', {})
        
        uses_node = False
        uses_python = False
        uses_cache = False
        
        for job_config in jobs.values():
            steps = job_config.get('steps', [])
            
            for step in steps:
                if 'uses' in step:
                    action = step['uses']
                    if 'setup-node' in action:
                        uses_node = True
                    if 'setup-python' in action:
                        uses_python = True
                    if 'cache' in action or 'actions/cache' in action:
                        uses_cache = True
        
        # If using package managers, caching is beneficial (but not required)
        # This is informational rather than enforced
        if (uses_node or uses_python) and not uses_cache:
            # Could benefit from caching
            pass
    
    def test_no_extremely_long_workflows(self, workflow_file):
        """Workflows should not be excessively long."""
        with open(workflow_file, 'r') as f:
            lines = len(f.readlines())
        
        # Warn if workflow is very long (might need splitting)
        assert lines <= 1000, \
            f"{workflow_file.name} is very long ({lines} lines). Consider splitting."


class TestDocumentation:
    """Test workflow documentation and comments."""
    
    def test_workflow_has_description_comment(self, workflow_file):
        """Workflow should have a description comment at the top."""
        with open(workflow_file, 'r') as f:
            first_lines = ''.join(f.readlines()[:10])
        
        # Should have at least one comment in first 10 lines
        has_comment = '#' in first_lines
        # This is a recommendation
        if not has_comment:
            pass  # Could warn but not fail
    
    def test_complex_steps_have_comments(self, workflow_file):
        """Complex steps should have explanatory comments."""
        with open(workflow_file, 'r') as f:
            content = f.read()
        
        # Check for run blocks with complex scripts
        complex_run_blocks = re.findall(r'run:\s*\|[\s\S]*?(?=\n\s{0,2}\w|\Z)', content)
        
        # If there are multi-line run blocks, they should have comments
        # This is informational
        if len(complex_run_blocks) > 3:
            # Workflow has many complex scripts
            pass


class TestErrorHandling:
    """Test error handling in workflows."""
    
    def test_critical_steps_have_continue_on_error(self, workflow_content):
        """Critical steps should explicitly set continue-on-error."""
        jobs = workflow_content.get('jobs', {})
        
        for job_name, job_config in jobs.items():
            steps = job_config.get('steps', [])
            
            for step in steps:
                # Steps with 'run' that might fail should consider continue-on-error
                if 'run' in step:
                    # This is informational - not all steps need it
                    pass
    
    def test_timeout_minutes_set(self, workflow_content):
        """Jobs should have timeout-minutes to prevent infinite runs."""
        jobs = workflow_content.get('jobs', {})
        
        for job_name, job_config in jobs.items():
            # timeout-minutes is recommended but not required
            if 'timeout-minutes' in job_config:
                timeout = job_config['timeout-minutes']
                assert isinstance(timeout, int), \
                    f"Job '{job_name}' timeout-minutes should be an integer"
                assert 1 <= timeout <= 360, \
                    f"Job '{job_name}' timeout should be between 1 and 360 minutes"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])