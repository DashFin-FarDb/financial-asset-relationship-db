"""
Comprehensive tests for GitHub workflow changes in current branch.

Tests validate:
1. PR Agent workflow simplifications and fixes
2. APISec scan workflow credential handling
3. Label workflow configuration validation  
4. Greetings workflow message simplification
5. YAML syntax and structure validity
"""

import pytest
import yaml
from pathlib import Path
from typing import Dict, Any, List
import re


class TestPRAgentWorkflowChanges:
    """Test PR Agent workflow modifications."""
    
    @pytest.fixture
    def pr_agent_workflow(self) -> Dict[str, Any]:
        """Load PR Agent workflow file."""
        workflow_path = Path(".github/workflows/pr-agent.yml")
        with open(workflow_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_no_duplicate_keys(self, pr_agent_workflow):
        """Verify no duplicate YAML keys exist."""
        # Check the raw file for duplicate keys
        workflow_path = Path(".github/workflows/pr-agent.yml")
        with open(workflow_path, 'r') as f:
            content = f.read()
        
        # Check for duplicate "Setup Python" steps
        setup_python_count = content.count("name: Setup Python")
        assert setup_python_count == 1, \
            f"Found {setup_python_count} 'Setup Python' steps, expected 1"
    
    def test_python_dependencies_installation(self, pr_agent_workflow):
        """Verify Python dependencies are installed correctly."""
        steps = pr_agent_workflow['jobs']['pr-agent-trigger']['steps']
        
        # Find the dependency installation step
        install_step = None
        for step in steps:
            if step.get('name') == 'Install Python dependencies':
                install_step = step
                break
        
        assert install_step is not None, "Python dependencies installation step not found"
        assert 'run' in install_step, "Install step missing run command"
        
        # Verify it installs pip
        assert 'pip install --upgrade pip' in install_step['run']
    
    def test_context_chunking_removed(self, pr_agent_workflow):
        """Verify context chunking logic was properly removed."""
        workflow_str = str(pr_agent_workflow)
        
        # These should no longer be present
        assert 'context_chunker' not in workflow_str.lower()
        assert 'chunking' not in workflow_str.lower()
        assert 'fetch-context' not in workflow_str.lower()
    
    def test_simplified_comment_parsing(self, pr_agent_workflow):
        """Verify comment parsing step exists and is simplified."""
        steps = pr_agent_workflow['jobs']['pr-agent-trigger']['steps']
        
        parse_step = None
        for step in steps:
            if 'parse' in step.get('name', '').lower() and 'comment' in step.get('name', '').lower():
                parse_step = step
                break
        
        assert parse_step is not None, "Parse comments step not found"
        assert 'gh api' in parse_step['run'], "Should use GitHub API to fetch reviews"
    
    def test_required_secrets_documented(self, pr_agent_workflow):
        """Verify GITHUB_TOKEN is properly used."""
        workflow_str = yaml.dump(pr_agent_workflow)
        assert 'GITHUB_TOKEN' in workflow_str or 'github.token' in workflow_str
    
    def test_workflow_triggers_valid(self, pr_agent_workflow):
        """Verify workflow triggers are properly configured."""
        assert 'on' in pr_agent_workflow or 'true' in str(pr_agent_workflow.get('on', {}))
        
        # Should trigger on pull_request_target for security
        on_config = pr_agent_workflow.get('on', {})
        assert 'pull_request_target' in on_config or 'pull_request' in on_config


class TestAPISecWorkflowChanges:
    """Test APISec scan workflow modifications."""
    
    @pytest.fixture
    def apisec_workflow(self) -> Dict[str, Any]:
        """Load APISec workflow file."""
        workflow_path = Path(".github/workflows/apisec-scan.yml")
        with open(workflow_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_conditional_execution_removed(self, apisec_workflow):
        """Verify the conditional execution logic was removed."""
        job = apisec_workflow['jobs']['Trigger_APIsec_scan']
        
        # The 'if' condition should not be present
        assert 'if' not in job, \
            "Conditional execution should be removed - workflow should run unconditionally"
    
    def test_credential_check_step_removed(self, apisec_workflow):
        """Verify credential checking step was removed."""
        steps = apisec_workflow['jobs']['Trigger_APIsec_scan']['steps']
        
        # Should not have a "Check for APIsec credentials" step
        check_steps = [s for s in steps if 'Check for APIsec' in s.get('name', '')]
        assert len(check_steps) == 0, \
            "Credential check step should be removed"
    
    def test_apisec_scan_step_present(self, apisec_workflow):
        """Verify the actual APIsec scan step is present."""
        steps = apisec_workflow['jobs']['Trigger_APIsec_scan']['steps']
        
        scan_step = None
        for step in steps:
            if step.get('name') == 'APIsec scan':
                scan_step = step
                break
        
        assert scan_step is not None, "APIsec scan step must be present"
        assert 'uses' in scan_step, "Scan step should use an action"
        assert 'apisec' in scan_step['uses'].lower()
    
    def test_required_secrets_usage(self, apisec_workflow):
        """Verify secrets are properly referenced."""
        workflow_str = yaml.dump(apisec_workflow)
        
        # Should reference the secrets
        assert 'apisec_username' in workflow_str
        assert 'apisec_password' in workflow_str
    
    def test_concurrency_configuration(self, apisec_workflow):
        """Verify concurrency settings are appropriate."""
        job = apisec_workflow['jobs']['Trigger_APIsec_scan']
        
        if 'concurrency' in job:
            concurrency = job['concurrency']
            assert 'group' in concurrency
            assert 'cancel-in-progress' in concurrency


class TestLabelWorkflowChanges:
    """Test label workflow modifications."""
    
    @pytest.fixture
    def label_workflow(self) -> Dict[str, Any]:
        """Load label workflow file."""
        workflow_path = Path(".github/workflows/label.yml")
        with open(workflow_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_simplified_to_basic_labeler(self, label_workflow):
        """Verify workflow was simplified to basic labeler action."""
        steps = label_workflow['jobs']['label']['steps']
        
        # Should only have the labeler step now
        assert len(steps) == 1, \
            f"Should have 1 step (labeler), found {len(steps)}"
        
        labeler_step = steps[0]
        assert 'actions/labeler' in labeler_step['uses']
    
    def test_config_check_removed(self, label_workflow):
        """Verify configuration checking logic was removed."""
        steps = label_workflow['jobs']['label']['steps']
        
        # Should not have config checking steps
        for step in steps:
            assert 'check-config' not in step.get('id', '').lower()
            assert 'checkout' not in step.get('uses', '').lower()
    
    def test_required_permissions(self, label_workflow):
        """Verify appropriate permissions are set."""
        job = label_workflow['jobs']['label']
        
        if 'permissions' in job:
            perms = job['permissions']
            assert 'pull-requests' in perms
            assert perms['pull-requests'] in ['write', 'read']
    
    def test_repo_token_configured(self, label_workflow):
        """Verify repo token is properly configured."""
        steps = label_workflow['jobs']['label']['steps']
        labeler_step = steps[0]
        
        assert 'with' in labeler_step
        assert 'repo-token' in labeler_step['with']


class TestGreetingsWorkflowChanges:
    """Test greetings workflow modifications."""
    
    @pytest.fixture
    def greetings_workflow(self) -> Dict[str, Any]:
        """Load greetings workflow file."""
        workflow_path = Path(".github/workflows/greetings.yml")
        with open(workflow_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_simplified_messages(self, greetings_workflow):
        """Verify messages were simplified to placeholders."""
        steps = greetings_workflow['jobs']['greeting']['steps']
        
        first_interaction_step = None
        for step in steps:
            if 'first-interaction' in step.get('uses', ''):
                first_interaction_step = step
                break
        
        assert first_interaction_step is not None
        
        with_config = first_interaction_step.get('with', {})
        
        # Messages should be simple placeholders now
        issue_msg = with_config.get('issue-message', '')
        pr_msg = with_config.get('pr-message', '')
        
        assert len(issue_msg) < 200, "Issue message should be simplified"
        assert len(pr_msg) < 200, "PR message should be simplified"
        
        # Should not contain elaborate instructions
        assert 'Resources:' not in issue_msg
        assert 'Resources:' not in pr_msg
    
    def test_repo_token_present(self, greetings_workflow):
        """Verify repo token is configured."""
        steps = greetings_workflow['jobs']['greeting']['steps']
        
        first_interaction_step = None
        for step in steps:
            if 'first-interaction' in step.get('uses', ''):
                first_interaction_step = step
                break
        
        assert 'with' in first_interaction_step
        assert 'repo-token' in first_interaction_step['with']


class TestWorkflowYAMLValidity:
    """Test YAML validity of all modified workflows."""
    
    @pytest.mark.parametrize("workflow_file", [
        ".github/workflows/pr-agent.yml",
        ".github/workflows/apisec-scan.yml",
        ".github/workflows/label.yml",
        ".github/workflows/greetings.yml",
    ])
    def test_yaml_syntax_valid(self, workflow_file):
        """Verify YAML syntax is valid."""
        workflow_path = Path(workflow_file)
        
        with open(workflow_path, 'r') as f:
            try:
                workflow = yaml.safe_load(f)
                assert workflow is not None
                assert isinstance(workflow, dict)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {workflow_file}: {e}")
    
    @pytest.mark.parametrize("workflow_file", [
        ".github/workflows/pr-agent.yml",
        ".github/workflows/apisec-scan.yml",
        ".github/workflows/label.yml",
        ".github/workflows/greetings.yml",
    ])
    def test_required_workflow_keys(self, workflow_file):
        """Verify required workflow keys are present."""
        workflow_path = Path(workflow_file)
        
        with open(workflow_path, 'r') as f:
            workflow = yaml.safe_load(f)
        
        assert 'name' in workflow, f"{workflow_file} missing 'name' key"
        assert 'on' in workflow or 'true' in str(workflow.get('on', {})), \
            f"{workflow_file} missing 'on' trigger"
        assert 'jobs' in workflow, f"{workflow_file} missing 'jobs' key"
        assert len(workflow['jobs']) > 0, f"{workflow_file} has no jobs defined"
    
    @pytest.mark.parametrize("workflow_file", [
        ".github/workflows/pr-agent.yml",
        ".github/workflows/apisec-scan.yml",
        ".github/workflows/label.yml",
        ".github/workflows/greetings.yml",
    ])
    def test_no_tabs_in_yaml(self, workflow_file):
        """Verify YAML files don't contain tabs."""
        workflow_path = Path(workflow_file)
        
        with open(workflow_path, 'r') as f:
            content = f.read()
        
        assert '\t' not in content, \
            f"{workflow_file} contains tabs - YAML should use spaces only"
    
    @pytest.mark.parametrize("workflow_file", [
        ".github/workflows/pr-agent.yml",
        ".github/workflows/apisec-scan.yml",
        ".github/workflows/label.yml",
        ".github/workflows/greetings.yml",
    ])
    def test_consistent_indentation(self, workflow_file):
        """Verify consistent indentation (2 spaces)."""
        workflow_path = Path(workflow_file)
        
        with open(workflow_path, 'r') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines, 1):
            if line.strip() and line[0] == ' ':
                # Count leading spaces
                spaces = len(line) - len(line.lstrip(' '))
                assert spaces % 2 == 0, \
                    f"{workflow_file}:{i} has inconsistent indentation (not multiple of 2)"


class TestRequirementsDevChanges:
    """Test requirements-dev.txt modifications."""
    
    def test_pyyaml_added(self):
        """Verify PyYAML was added to dev requirements."""
        with open('requirements-dev.txt', 'r') as f:
            content = f.read()
        
        assert 'pyyaml' in content.lower() or 'PyYAML' in content
    
    def test_pyyaml_version_pinned(self):
        """Verify PyYAML has version constraint."""
        with open('requirements-dev.txt', 'r') as f:
            lines = f.readlines()
        
        pyyaml_line = None
        for line in lines:
            if 'pyyaml' in line.lower():
                pyyaml_line = line.strip()
                break
        
        assert pyyaml_line is not None, "PyYAML not found in requirements-dev.txt"
        
        # Should have version specifier
        assert any(op in pyyaml_line for op in ['==', '>=', '<=', '~=', '>']), \
            "PyYAML should have version constraint"
    
    def test_requirements_file_format(self):
        """Verify requirements file follows proper format."""
        with open('requirements-dev.txt', 'r') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Should not have spaces around operators
            assert ' == ' not in line and ' >= ' not in line, \
                f"Line {i}: Use operators without spaces (e.g., 'package==1.0.0')"
    
    def test_no_duplicate_dependencies(self):
        """Verify no duplicate package specifications."""
        with open('requirements-dev.txt', 'r') as f:
            lines = f.readlines()
        
        packages = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                # Extract package name (before any version specifier)
                pkg_name = re.split(r'[<>=~!]', line)[0].strip().lower()
                packages.append(pkg_name)
        
        duplicates = [pkg for pkg in packages if packages.count(pkg) > 1]
        assert len(duplicates) == 0, \
            f"Found duplicate packages: {set(duplicates)}"


class TestDeletedFiles:
    """Test that removed files are actually gone."""
    
    def test_labeler_config_removed(self):
        """Verify labeler.yml configuration was removed."""
        labeler_path = Path(".github/labeler.yml")
        assert not labeler_path.exists(), \
            "labeler.yml should be removed"
    
    def test_context_chunker_removed(self):
        """Verify context chunker script was removed."""
        chunker_path = Path(".github/scripts/context_chunker.py")
        assert not chunker_path.exists(), \
            "context_chunker.py should be removed"
    
    def test_scripts_readme_removed(self):
        """Verify scripts README was removed."""
        readme_path = Path(".github/scripts/README.md")
        assert not readme_path.exists(), \
            "scripts/README.md should be removed"


class TestWorkflowIntegration:
    """Integration tests for workflow interactions."""
    
    def test_all_workflows_use_ubuntu_latest(self):
        """Verify all workflows use ubuntu-latest for consistency."""
        workflow_files = [
            ".github/workflows/pr-agent.yml",
            ".github/workflows/apisec-scan.yml",
            ".github/workflows/label.yml",
            ".github/workflows/greetings.yml",
        ]
        
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
            
            for job_name, job_config in workflow['jobs'].items():
                if 'runs-on' in job_config:
                    runs_on = job_config['runs-on']
                    assert 'ubuntu' in runs_on.lower(), \
                        f"{workflow_file}:{job_name} should use ubuntu runner"
    
    def test_workflows_use_appropriate_actions_versions(self):
        """Verify workflows use pinned or major version tags for actions."""
        workflow_files = [
            ".github/workflows/pr-agent.yml",
            ".github/workflows/apisec-scan.yml",
            ".github/workflows/label.yml",
            ".github/workflows/greetings.yml",
        ]
        
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                content = f.read()
            
            # Find all 'uses:' lines
            uses_pattern = r'uses:\s*([^\s]+)'
            matches = re.findall(uses_pattern, content)
            
            for action in matches:
                # Should have version specified (v1, v2, @sha, etc.)
                assert '@' in action or action.startswith('./'), \
                    f"{workflow_file}: Action {action} should specify version"
    
    def test_no_hardcoded_secrets_in_workflows(self):
        """Verify no hardcoded secrets exist in workflow files."""
        workflow_files = [
            ".github/workflows/pr-agent.yml",
            ".github/workflows/apisec-scan.yml",
            ".github/workflows/label.yml",
            ".github/workflows/greetings.yml",
        ]
        
        sensitive_patterns = [
            r'password:\s*["\']?[^$\s][^"\s]+',
            r'token:\s*["\']?[^$\s][^"\s]{20,}',
            r'api[_-]?key:\s*["\']?[^$\s][^"\s]+',
        ]
        
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                content = f.read()
            
            for pattern in sensitive_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                # Filter out references to secrets context
                actual_secrets = [m for m in matches if 'secrets.' not in m]
                assert len(actual_secrets) == 0, \
                    f"{workflow_file} may contain hardcoded secrets: {actual_secrets}"


class TestWorkflowSecurity:
    """Security-focused tests for workflow changes."""
    
    def test_pr_agent_uses_pull_request_target_safely(self):
        """Verify PR agent workflow uses pull_request_target safely."""
        with open(".github/workflows/pr-agent.yml", 'r') as f:
            workflow = yaml.safe_load(f)
        
        # If using pull_request_target, should checkout with specific ref
        if 'pull_request_target' in str(workflow.get('on', {})):
            steps = workflow['jobs']['pr_agent_response']['steps']
            checkout_step = steps[0]  # Usually first step
            
            if 'actions/checkout' in checkout_step.get('uses', ''):
                # Should specify ref or fetch-depth for security
                assert 'with' in checkout_step, \
                    "Checkout in pull_request_target should specify 'with' parameters"
    
    def test_workflows_have_appropriate_permissions(self):
        """Verify workflows follow least privilege principle."""
        workflow_files = {
            ".github/workflows/pr-agent.yml": ['contents', 'issues', 'pull-requests'],
            ".github/workflows/label.yml": ['pull-requests'],
            ".github/workflows/greetings.yml": ['issues', 'pull-requests'],
        }
        
        for workflow_file, expected_perms in workflow_files.items():
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
            
            # Check if permissions are defined at workflow or job level
            has_permissions = (
                'permissions' in workflow or
                any('permissions' in job for job in workflow['jobs'].values())
            )
            
            # If permissions are defined, verify they're appropriate
            if has_permissions:
                perms = workflow.get('permissions', {})
                if not perms:
                    # Check job-level permissions
                    for job in workflow['jobs'].values():
                        perms.update(job.get('permissions', {}))
                
                # Verify no write-all permission
                assert perms.get('write-all') != True and perms != 'write-all', \
                    f"{workflow_file} should not use write-all permission"
    
    def test_no_script_injection_vulnerabilities(self):
        """Check for potential script injection in workflow files."""
        workflow_files = [
            ".github/workflows/pr-agent.yml",
            ".github/workflows/apisec-scan.yml",
            ".github/workflows/label.yml",
            ".github/workflows/greetings.yml",
        ]
        
        dangerous_patterns = [
            r'\$\{\{.*github\.event\..*\}\}.*\|',  # Piping user input
            r'\$\{\{.*github\.event\..*\}\}.*\$\(',  # Command substitution
        ]
        
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                content = f.read()
            
            for pattern in dangerous_patterns:
                matches = re.findall(pattern, content)
                assert len(matches) == 0, \
                    f"{workflow_file} may have script injection vulnerability: {matches}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])