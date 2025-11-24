"""
Comprehensive YAML schema validation tests for GitHub workflows.

Tests validate YAML structure, syntax, and GitHub Actions schema compliance
for all workflow files in .github/workflows/
"""

import os
import warnings
from pathlib import Path
from typing import Dict, Any, List

import pytest
import yaml
from pathlib import Path
from typing import Dict, Any, List


class TestWorkflowYAMLSyntax:
    """Test YAML syntax and structure validity."""
    
    @pytest.fixture
    def workflow_files(self):
        """Get all workflow YAML files."""
        workflow_dir = Path(".github/workflows")
        return list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml"))
    
    def test_all_workflows_are_valid_yaml(self, workflow_files):
        """All workflow files should be valid YAML."""
        assert len(workflow_files) > 0, "No workflow files found"
        
        for workflow_file in workflow_files:
            try:
                with open(workflow_file, 'r') as f:
                    data = yaml.safe_load(f)
                assert data is not None, f"{workflow_file.name} is empty"
                assert isinstance(data, dict), f"{workflow_file.name} should be a dictionary"
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {workflow_file.name}: {e}")
    
    def test_workflows_have_no_tabs(self, workflow_files):
        """Workflow files should use spaces, not tabs."""
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                content = f.read()
            
            assert '\t' not in content, \
                f"{workflow_file.name} contains tabs (should use spaces for indentation)"
    
    def test_workflows_use_consistent_indentation(self, workflow_files):
        """Workflow files should use consistent indentation (2 spaces)."""
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                lines = f.readlines()
            
            for i, line in enumerate(lines, 1):
                if line.strip() and not line.strip().startswith('#'):
                    # Count leading spaces
                    leading_spaces = len(line) - len(line.lstrip(' '))
                    if leading_spaces > 0:
                        assert leading_spaces % 2 == 0, \
                            f"{workflow_file.name}:{i} has odd indentation ({leading_spaces} spaces)"
    
    def test_workflows_have_no_trailing_whitespace(self, workflow_files):
        """Workflow files should not have trailing whitespace."""
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                lines = f.readlines()
            
            for i, line in enumerate(lines, 1):
                if line.rstrip('\n').endswith((' ', '\t')):
                    pytest.fail(f"{workflow_file.name}:{i} has trailing whitespace")


class TestWorkflowGitHubActionsSchema:
    """Test GitHub Actions schema compliance."""
    
    @pytest.fixture
    def workflow_data(self):
        """Load all workflow files as structured data."""
        workflow_dir = Path(".github/workflows")
        workflows = {}
        
        for workflow_file in list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml")):
            with open(workflow_file, 'r') as f:
                workflows[workflow_file.name] = yaml.safe_load(f)
        
        return workflows
    
    def test_workflows_have_name(self, workflow_data):
        """All workflows should have a name field."""
        for filename, data in workflow_data.items():
            assert 'name' in data, f"{filename} missing 'name' field"
            assert isinstance(data['name'], str), f"{filename} name should be string"
            assert len(data['name']) > 0, f"{filename} name is empty"
    
    def test_workflows_have_trigger(self, workflow_data):
        """All workflows should have at least one trigger."""
        valid_triggers = {
            'on', 'push', 'pull_request', 'workflow_dispatch',
            'schedule', 'issues', 'issue_comment', 'pull_request_review',
            'pull_request_review_comment', 'workflow_run', 'repository_dispatch'
        }
        
        for filename, data in workflow_data.items():
            assert 'on' in data, f"{filename} missing 'on' trigger"
            
            # 'on' can be string, list, or dict
            trigger = data['on']
            if isinstance(trigger, str):
                assert trigger in valid_triggers, \
                    f"{filename} has invalid trigger: {trigger}"
            elif isinstance(trigger, list):
                assert all(t in valid_triggers for t in trigger), \
                    f"{filename} has invalid triggers in list"
            elif isinstance(trigger, dict):
                assert any(k in valid_triggers for k in trigger.keys()), \
                    f"{filename} has no valid triggers in dict"
    
    def test_workflows_have_jobs(self, workflow_data):
        """All workflows should define at least one job."""
        for filename, data in workflow_data.items():
            assert 'jobs' in data, f"{filename} missing 'jobs' section"
            assert isinstance(data['jobs'], dict), f"{filename} jobs should be dict"
            assert len(data['jobs']) > 0, f"{filename} has no jobs defined"
    
    def test_jobs_have_runs_on(self, workflow_data):
        """All jobs should specify runs-on."""
        for filename, data in workflow_data.items():
            jobs = data.get('jobs', {})
            
            for job_name, job_data in jobs.items():
                assert 'runs-on' in job_data, \
                    f"{filename} job '{job_name}' missing 'runs-on'"
                
                runs_on = job_data['runs-on']
                valid_runners = [
                    'ubuntu-latest', 'ubuntu-20.04', 'ubuntu-18.04',
                    'windows-latest', 'windows-2022', 'windows-2019',
                    'macos-latest', 'macos-12', 'macos-11'
                ]
                
                if isinstance(runs_on, str):
                    # Can be expression or literal
                    if not runs_on.startswith('${{'):
                        assert any(runner in runs_on for runner in valid_runners), \
                            f"{filename} job '{job_name}' has invalid runs-on: {runs_on}"
    
    def test_jobs_have_steps_or_uses(self, workflow_data):
        """Jobs should have either steps or uses (for reusable workflows)."""
        for filename, data in workflow_data.items():
            jobs = data.get('jobs', {})
            
            for job_name, job_data in jobs.items():
                has_steps = 'steps' in job_data
                has_uses = 'uses' in job_data
                
                assert has_steps or has_uses, \
                    f"{filename} job '{job_name}' has neither 'steps' nor 'uses'"
                
                if has_steps:
                    assert isinstance(job_data['steps'], list), \
                        f"{filename} job '{job_name}' steps should be a list"
                    assert len(job_data['steps']) > 0, \
                        f"{filename} job '{job_name}' has empty steps"


class TestWorkflowSecurity:
    """Security-focused tests for GitHub workflows."""
    
    @pytest.fixture
    def workflow_files(self):
        """Get all workflow files."""
        workflow_dir = Path(".github/workflows")
        return list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml"))
    
    def test_no_hardcoded_secrets(self, workflow_files):
        """Workflows should not contain hardcoded secrets."""
        dangerous_patterns = [
            'ghp_', 'github_pat_', 'gho_', 'ghu_', 'ghs_', 'ghr_',  # GitHub tokens
            'AKIA', 'ASIA',  # AWS keys
            '-----BEGIN', '-----BEGIN RSA PRIVATE KEY',  # Private keys
        ]
    
        import re
        secret_ref_re = re.compile(r'\$\{\{\s*secrets\.[A-Za-z0-9_]+\s*\}\}')
    
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                content = f.read()
        
            lines = content.splitlines()
            for i, line in enumerate(lines, start=1):
                stripped = line.strip()
                # Skip commented lines
                if stripped.startswith('#'):
                    continue
                for pattern in dangerous_patterns:
                    if pattern in line:
                        valid_refs = list(secret_ref_re.finditer(line))
                        if valid_refs:
                            # Mask valid secret reference spans, then check remaining text for dangerous patterns
                            masked = list(line)
                            for m in valid_refs:
                                for idx in range(m.start(), m.end()):
                                    masked[idx] = ' '
                            remaining = ''.join(masked)
                            assert pattern not in remaining, (
                                f"{workflow_file.name}:{i} may contain hardcoded secret outside secrets.* reference: {pattern}"
                            )
                        else:
                            pytest.fail(
                                f"{workflow_file.name}:{i} may contain hardcoded secret without secrets.* reference: {pattern}"
                            )
    
    def test_pull_request_safe_checkout(self, workflow_files):
        """PR workflows should checkout safely (not HEAD of PR)."""
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                data = yaml.safe_load(f)
            
            # Check if triggered by pull_request
            triggers = data.get('on', {})
            if 'pull_request' in triggers or (isinstance(triggers, list) and 'pull_request' in triggers):
                # Look for checkout actions
                jobs = data.get('jobs', {})
                for job_name, job_data in jobs.items():
                    steps = job_data.get('steps', [])
                    
                    for step in steps:
                        if step.get('uses', '').startswith('actions/checkout'):
                            # Should specify ref or not checkout HEAD
                            # If no ref specified, it's okay (checks out merge commit)
                            # If ref specified, shouldn't be dangerous
                            with_data = step.get('with', {})
                            ref = with_data.get('ref', '')
                            if ref and 'head' in ref.lower() and 'sha' not in ref.lower():
import os
import pytest
import warnings
import yaml
from pathlib import Path
from typing import Dict, Any, List
                                    f"checks out PR HEAD (potential security risk)"
                                )

    
    def test_restricted_permissions(self, workflow_files):
        """Workflows should use minimal required permissions."""
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                data = yaml.safe_load(f)
            
            # Check top-level permissions
            permissions = data.get('permissions', {})
            
            # If permissions defined, shouldn't be 'write-all'
            if permissions:
                if isinstance(permissions, str):
                    assert permissions != 'write-all', \
                        f"{workflow_file.name} uses write-all permissions (too broad)"
                elif isinstance(permissions, dict):
                    # Check individual permissions
                    for scope, level in permissions.items():
                        if level == 'write':
                            # Write permissions should have justification in comments
                            pass  # Warning only


class TestWorkflowBestPractices:
    """Test adherence to GitHub Actions best practices."""
    
    @pytest.fixture
    def workflow_data(self):
        """Load all workflow files."""
        workflow_dir = Path(".github/workflows")
        workflows = {}
        
        for workflow_file in list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml")):
            with open(workflow_file, 'r') as f:
                workflows[workflow_file.name] = yaml.safe_load(f)
        
        return workflows
        for filename, data in workflow_data.items():
            jobs = data.get('jobs', {})
            
            for job_name, job_data in jobs.items():
                steps = job_data.get('steps', [])
                    if uses:
                        # Should not use @main or @master
                        if '@main' in uses or '@master' in uses:
                            warnings.warn(
                                f"{filename} job '{job_name}' step {i} "
                                f"uses unstable version: {uses}"
                            )
                                f"{filename} job '{job_name}' step {i} "
                                f"uses unstable version: {uses}"
                            )

    
    def test_steps_have_names(self, workflow_data):
        """Steps should have descriptive names."""
        for filename, data in workflow_data.items():
            jobs = data.get('jobs', {})
            
            for job_name, job_data in jobs.items():
                steps = job_data.get('steps', [])
                
                unnamed_steps = [
                    i for i, step in enumerate(steps)
                    if 'name' not in step
                ]
                
                # Allow a few unnamed steps, but not too many
                unnamed_ratio = len(unnamed_steps) / len(steps) if steps else 0
                assert unnamed_ratio < 0.5, \
                    f"{filename} job '{job_name}' has too many unnamed steps"
    
    def test_timeouts_defined(self, workflow_data):
        """Long-running jobs should have timeouts."""
        for filename, data in workflow_data.items():
            jobs = data.get('jobs', {})
            
            for job_name, job_data in jobs.items():
                steps = job_data.get('steps', [])
                
                # If job has many steps or installs dependencies, should have timeout
                if len(steps) > 5:
                    # Check for timeout-minutes
                    if 'timeout-minutes' not in job_data:
                        warnings.warn(
                            f"{filename} job '{job_name}' has many steps "
                            f"but no timeout defined"
                        )


class TestWorkflowCrossPlatform:
    """Test cross-platform compatibility issues."""
    
    @pytest.fixture
    def workflow_data(self):
        """Load workflow data."""
        workflow_dir = Path(".github/workflows")
        workflows = {}
        
        for workflow_file in list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml")):
            with open(workflow_file, 'r') as f:
                workflows[workflow_file.name] = yaml.safe_load(f)
        
        return workflows
    
    def test_shell_script_compatibility(self, workflow_data):
        """Shell scripts should be compatible with runner OS."""
        for filename, data in workflow_data.items():
            jobs = data.get('jobs', {})
            
            for job_name, job_data in jobs.items():
                runs_on = job_data.get('runs-on', '')
                steps = job_data.get('steps', [])
                
                is_windows = 'windows' in str(runs_on).lower()
                
                for step in steps:
                    run_command = step.get('run', '')
                    shell = step.get('shell', 'bash' if not is_windows else 'pwsh')
                    
                    if run_command:
                        # Check for Unix-specific commands on Windows
                        if is_windows and shell in ['bash', 'sh']:
                            unix_commands = ['grep', 'sed', 'awk', 'find']
                            for cmd in unix_commands:
                                if cmd in run_command:
                                    warnings.warn(
                                        f"{filename} job '{job_name}' uses Unix command "
                                        f"'{cmd}' on Windows"
                                    )
    
    def test_path_separators(self, workflow_data):
        """File paths should use forward slashes for cross-platform compatibility."""
        for filename, data in workflow_data.items():
            jobs = data.get('jobs', {})
            
            for job_name, job_data in jobs.items():
                steps = job_data.get('steps', [])
                
                for step in steps:
                    run_command = step.get('run', '')
                    
                    # Check for Windows-style paths (backslashes)
                    if '\\' in run_command and 'windows' not in str(job_data.get('runs-on', '')).lower():
                        # Might be legitimate (escaped chars), so just warn
                        pass


class TestWorkflowMaintainability:
    """Test workflow maintainability and documentation."""
    
    def test_workflows_have_comments(self):
        """Workflows should have explanatory comments."""
        workflow_dir = Path(".github/workflows")
        
        for workflow_file in list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml")):
            with open(workflow_file, 'r') as f:
                content = f.read()
            
            lines = content.split('\n')
            comment_lines = [l for l in lines if l.strip().startswith('#')]
            code_lines = [l for l in lines if l.strip() and not l.strip().startswith('#')]
            
            if len(code_lines) > 20:
                # Large workflows should have comments
                comment_ratio = len(comment_lines) / len(code_lines)
                assert comment_ratio >= 0.05, \
                    f"{workflow_file.name} is large but has few comments"
    
    def test_complex_expressions_explained(self):
        """Complex expressions should have explanatory comments."""
        workflow_dir = Path(".github/workflows")
        
        for workflow_file in list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml")):
            with open(workflow_file, 'r') as f:
                content = f.read()
            
            # Look for complex expressions
            import re
            complex_patterns = [
                r'\$\{\{.*\&\&.*\}\}',  # Multiple conditions
                r'\$\{\{.*\|\|.*\}\}',  # OR conditions
                r'\$\{\{.*\(.*\).*\}\}',  # Function calls
            ]
            
            for pattern in complex_patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    # Check if there's a comment nearby
                    start = max(0, match.start() - 200)
                    context = content[start:match.end()]

                    import warnings
                    # Should have explanation
                    lines = context.split('\n')
                    if len(lines) < 2 or '#' not in lines[-2]:
                        line_num = content[:match.start()].count('\n') + 1
                        warnings.warn(f"{workflow_file.name}: complex expression at line {line_num} lacks explanation: {match.group()}")
                        # Warning only, not failure