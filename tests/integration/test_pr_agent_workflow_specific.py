"""
Comprehensive tests specifically for pr-agent.yml workflow.
Tests the duplicate key fix and PR Agent-specific functionality.
"""

import pytest
import yaml
import re
from pathlib import Path
from typing import Dict, Any


class TestPRAgentWorkflowDuplicateKeyRegression:
    """Regression tests for the duplicate Setup Python key fix."""
    
    @pytest.fixture
    def workflow_file(self) -> Path:
        """
        Resolve the path to the pr-agent.yml workflow file.
        
        Returns:
            Path: Path to the .github/workflows/pr-agent.yml workflow file.
        """
        return Path('.github/workflows/pr-agent.yml')
    
    @pytest.fixture
    def workflow_content(self, workflow_file: Path) -> Dict[str, Any]:
        """
        Load and parse a GitHub Actions workflow YAML file.
        
        Parameters:
            workflow_file (Path): Path to the workflow YAML file to load.
        
        Returns:
            dict: Parsed YAML content as a Python mapping.
        """
        with open(workflow_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    @pytest.fixture
    def workflow_raw(self, workflow_file: Path) -> str:
        """
        Return the raw text content of the workflow file for text-based validation.
        
        Returns:
            raw (str): The file contents as a UTF-8 decoded string.
        """
        with open(workflow_file, 'r', encoding='utf-8') as f:
            return f.read()
    
    def test_no_duplicate_step_name_setup_python(self, workflow_content: Dict[str, Any]):
        """Test that there's no duplicate 'Setup Python' step name."""
        for job_name, job_config in workflow_content.get('jobs', {}).items():
            steps = job_config.get('steps', [])
            setup_python_count = sum(
                1 for step in steps 
                if step.get('name') == 'Setup Python'
            )
            
            assert setup_python_count <= 1, \
                f"Job '{job_name}' has {setup_python_count} 'Setup Python' steps, expected at most 1"
    
    def test_no_duplicate_with_blocks_in_setup_python(self, workflow_raw: str):
        """Test that Setup Python step doesn't have duplicate 'with:' blocks."""
        # Split into lines and check for pattern of duplicate 'with:' after Setup Python
        lines = workflow_raw.split('\n')
        
        for i, line in enumerate(lines):
            if 'name: Setup Python' in line:
                # Check next 10 lines for duplicate 'with:' keywords
                with_count = 0
                for j in range(i + 1, min(i + 11, len(lines))):
                    if re.match(r'^\s+with:\s*$', lines[j]):
                        with_count += 1
                    # Stop at next step
                    if re.match(r'^\s+- name:', lines[j]) and j != i:
                        break
                
                assert with_count <= 1, \
                    f"Setup Python step at line {i+1} has {with_count} 'with:' blocks, expected 1"
    
    def test_setup_python_single_python_version_definition(self, workflow_raw: str):
        """Test that python-version is defined only once per Setup Python step."""
        lines = workflow_raw.split('\n')
        
        for i, line in enumerate(lines):
            if 'name: Setup Python' in line:
                # Count python-version definitions in next lines until next step
                version_count = 0
                for j in range(i + 1, min(i + 15, len(lines))):
                    if 'python-version' in lines[j]:
                        version_count += 1
                    # Stop at next step
                    if re.match(r'^\s+- name:', lines[j]):
                        break
                
                assert version_count == 1, \
                    f"Setup Python at line {i+1} has {version_count} python-version definitions, expected 1"


class TestPRAgentWorkflowStructureValidation:
    """Validate the overall structure of pr-agent.yml."""
    
    @pytest.fixture
    def workflow_content(self) -> Dict[str, Any]:
        """
        Load and parse the pr-agent GitHub Actions workflow file at .github/workflows/pr-agent.yml.
        
        Returns:
            workflow (Dict[str, Any]): Parsed YAML content of the workflow as a dictionary.
        """
        with open('.github/workflows/pr-agent.yml', 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def test_has_pr_agent_trigger_job(self, workflow_content: Dict[str, Any]):
        """Test that workflow has the pr-agent-trigger job."""
        assert 'jobs' in workflow_content
        assert 'pr-agent-trigger' in workflow_content['jobs'], \
            "Workflow should have 'pr-agent-trigger' job"
    
    def test_has_auto_merge_check_job(self, workflow_content: Dict[str, Any]):
        """Test that workflow has the auto-merge-check job."""
        assert 'auto-merge-check' in workflow_content.get('jobs', {}), \
            "Workflow should have 'auto-merge-check' job"
    
    def test_has_dependency_update_job(self, workflow_content: Dict[str, Any]):
        """Test that workflow has the dependency-update job."""
        assert 'dependency-update' in workflow_content.get('jobs', {}), \
            "Workflow should have 'dependency-update' job"
    
    def test_trigger_on_pr_events(self, workflow_content: Dict[str, Any]):
        """Test that workflow triggers on appropriate PR events."""
        triggers = workflow_content.get('on', {})
        
        assert 'pull_request' in triggers, \
            "Workflow should trigger on pull_request events"
        
        if isinstance(triggers.get('pull_request'), dict):
            pr_types = triggers['pull_request'].get('types', [])
            expected_types = ['opened', 'synchronize', 'reopened']
            for expected in expected_types:
                assert expected in pr_types, \
                    f"pull_request trigger should include '{expected}' type"
    
    def test_trigger_on_pr_review(self, workflow_content: Dict[str, Any]):
        """Test that workflow triggers on PR review events."""
        triggers = workflow_content.get('on', {})
        assert 'pull_request_review' in triggers, \
            "Workflow should trigger on pull_request_review events"
    
    def test_trigger_on_issue_comment(self, workflow_content: Dict[str, Any]):
        """Test that workflow triggers on issue comment events."""
        triggers = workflow_content.get('on', {})
        assert 'issue_comment' in triggers, \
            "Workflow should trigger on issue_comment events for @copilot mentions"


class TestPRAgentWorkflowSetupSteps:
    """Test the setup steps in pr-agent workflow."""
    
    @pytest.fixture
    def pr_agent_job(self) -> Dict[str, Any]:
        """
        Retrieve the configuration for the 'pr-agent-trigger' job from the repository workflow file.
        
        Returns:
            Dict[str, Any]: Mapping containing the 'pr-agent-trigger' job configuration as defined in .github/workflows/pr-agent.yml.
        """
        with open('.github/workflows/pr-agent.yml', 'r', encoding='utf-8') as f:
            workflow = yaml.safe_load(f)
        return workflow['jobs']['pr-agent-trigger']
    
    def test_checkout_step_exists(self, pr_agent_job: Dict[str, Any]):
        """Test that job includes checkout step."""
        steps = pr_agent_job.get('steps', [])
        checkout_steps = [
            step for step in steps
            if step.get('uses', '').startswith('actions/checkout')
        ]
        assert len(checkout_steps) >= 1, "Job should have checkout step"
    
    def test_setup_python_exists(self, pr_agent_job: Dict[str, Any]):
        """Test that job includes Setup Python step."""
        steps = pr_agent_job.get('steps', [])
        python_steps = [
            step for step in steps
            if step.get('name') == 'Setup Python'
        ]
        assert len(python_steps) == 1, "Job should have exactly one Setup Python step"
    
    def test_setup_nodejs_exists(self, pr_agent_job: Dict[str, Any]):
        """Test that job includes Setup Node.js step."""
        steps = pr_agent_job.get('steps', [])
        node_steps = [
            step for step in steps
            if step.get('name') == 'Setup Node.js'
        ]
        assert len(node_steps) >= 1, "Job should have Setup Node.js step"
    
    def test_python_version_is_311(self, pr_agent_job: Dict[str, Any]):
        """Test that Python 3.11 is specified."""
        steps = pr_agent_job.get('steps', [])
        for step in steps:
            if step.get('name') == 'Setup Python':
                version = step.get('with', {}).get('python-version')
                assert version == '3.11', \
                    f"Expected Python version '3.11', got '{version}'"
    
    def test_nodejs_version_is_18(self, pr_agent_job: Dict[str, Any]):
        """Test that Node.js 18 is specified."""
        steps = pr_agent_job.get('steps', [])
        for step in steps:
            if step.get('name') == 'Setup Node.js':
                version = step.get('with', {}).get('node-version')
                assert version == '18', \
                    f"Expected Node.js version '18', got '{version}'"
    
    def test_setup_order_correct(self, pr_agent_job: Dict[str, Any]):
        """Test that setup steps are in correct order: checkout, python, node."""
        steps = pr_agent_job.get('steps', [])
        
        checkout_idx = None
        python_idx = None
        node_idx = None
        
        for i, step in enumerate(steps):
            if step.get('uses', '').startswith('actions/checkout'):
                checkout_idx = i
            elif step.get('name') == 'Setup Python':
                python_idx = i
            elif step.get('name') == 'Setup Node.js':
                node_idx = i
        
        if checkout_idx is not None and python_idx is not None:
            assert checkout_idx < python_idx, \
                "Checkout should come before Setup Python"
        
        if python_idx is not None and node_idx is not None:
            assert python_idx < node_idx, \
                "Setup Python should come before Setup Node.js"


class TestPRAgentWorkflowDependencyInstallation:
    """Test dependency installation steps."""
    
    @pytest.fixture
    def pr_agent_job(self) -> Dict[str, Any]:
        """
        Retrieve the configuration for the 'pr-agent-trigger' job from the repository workflow file.
        
        Returns:
            Dict[str, Any]: Mapping containing the 'pr-agent-trigger' job configuration as defined in .github/workflows/pr-agent.yml.
        """
        with open('.github/workflows/pr-agent.yml', 'r', encoding='utf-8') as f:
            workflow = yaml.safe_load(f)
        return workflow['jobs']['pr-agent-trigger']
    
    def test_python_dependencies_installation_step(self, pr_agent_job: Dict[str, Any]):
        """Test that Python dependencies installation step exists."""
        steps = pr_agent_job.get('steps', [])
        install_steps = [
            step for step in steps
            if step.get('name') == 'Install Python dependencies'
        ]
        assert len(install_steps) >= 1, \
            "Job should have 'Install Python dependencies' step"
    
    def test_node_dependencies_installation_step(self, pr_agent_job: Dict[str, Any]):
        """Test that Node dependencies installation step exists."""
        steps = pr_agent_job.get('steps', [])
        install_steps = [
            step for step in steps
            if step.get('name') == 'Install Node dependencies'
        ]
        assert len(install_steps) >= 1, \
            "Job should have 'Install Node dependencies' step"
    
    def test_python_install_includes_requirements_dev(self, pr_agent_job: Dict[str, Any]):
        """
        Verify the Python dependency installation step references requirements-dev.txt.
        
        Asserts that within the provided pr-agent job configuration there exists a step named
        'Install Python dependencies' whose run script includes 'requirements-dev.txt'.
        
        Parameters:
            pr_agent_job (Dict[str, Any]): Parsed job dictionary for the pr-agent-trigger job from the workflow YAML.
        """
        steps = pr_agent_job.get('steps', [])
        for step in steps:
            if step.get('name') == 'Install Python dependencies':
                run_script = step.get('run', '')
                assert 'requirements-dev.txt' in run_script, \
                    "Python install should reference requirements-dev.txt"
    
    def test_node_install_uses_working_directory(self, pr_agent_job: Dict[str, Any]):
        """Test that Node install step runs in the frontend directory."""
        steps = pr_agent_job.get('steps', [])
        for step in steps:
            if step.get('name') == 'Install Node dependencies':
                run_script = step.get('run', '') or ''
                working_dir = step.get('working-directory', '') or ''
                assert (
                    'frontend' in working_dir
                    or re.search(r'\bcd\s+frontend\b', run_script)
                ), "Node install should execute in the frontend directory (via working-directory or 'cd frontend')"


class TestPRAgentWorkflowTestingSteps:
    """Test that workflow includes proper testing steps."""
    
    @pytest.fixture
    def pr_agent_job(self) -> Dict[str, Any]:
        """
        Retrieve the configuration for the 'pr-agent-trigger' job from the repository workflow file.
        
        Returns:
            Dict[str, Any]: Mapping containing the 'pr-agent-trigger' job configuration as defined in .github/workflows/pr-agent.yml.
        """
        with open('.github/workflows/pr-agent.yml', 'r', encoding='utf-8') as f:
            workflow = yaml.safe_load(f)
        return workflow['jobs']['pr-agent-trigger']
    
    def test_python_tests_step_exists(self, pr_agent_job: Dict[str, Any]):
        """Test that Python tests step exists."""
        steps = pr_agent_job.get('steps', [])
        test_steps = [
            step for step in steps
            if 'Python' in step.get('name', '') and 'Test' in step.get('name', '')
        ]
        assert len(test_steps) >= 1, "Job should include Python testing step"
    
    def test_frontend_tests_step_exists(self, pr_agent_job: Dict[str, Any]):
        """
        Check that the pr-agent-trigger job includes a frontend test step.
        
        Asserts that the job has at least one step whose name contains both "Frontend" and "Test".
        """
        steps = pr_agent_job.get('steps', [])
        test_steps = [
            step for step in steps
            if 'Frontend' in step.get('name', '') and 'Test' in step.get('name', '')
        ]
        assert len(test_steps) >= 1, "Job should include frontend testing step"
    
    def test_python_linting_step_exists(self, pr_agent_job: Dict[str, Any]):
        """
        Assert the job contains at least one step whose name includes both "Python" and "Lint".
        
        This verifies that the pr-agent-trigger job defines a Python linting step by checking step names for both substrings.
        """
        steps = pr_agent_job.get('steps', [])
        lint_steps = [
            step for step in steps
            if 'Python' in step.get('name', '') and 'Lint' in step.get('name', '')
        ]
        assert len(lint_steps) >= 1, "Job should include Python linting step"
    
    def test_frontend_linting_step_exists(self, pr_agent_job: Dict[str, Any]):
        """Test that frontend linting step exists."""
        steps = pr_agent_job.get('steps', [])
        lint_steps = [
            step for step in steps
            if 'Frontend' in step.get('name', '') and 'Lint' in step.get('name', '')
        ]
        assert len(lint_steps) >= 1, "Job should include frontend linting step"


class TestPRAgentWorkflowPermissions:
    """Test workflow permissions configuration."""
    
    @pytest.fixture
    def workflow_content(self) -> Dict[str, Any]:
        """
        Load and parse the pr-agent GitHub Actions workflow file at .github/workflows/pr-agent.yml.
        
        Returns:
            workflow (Dict[str, Any]): Parsed YAML content of the workflow as a dictionary.
        """
        with open('.github/workflows/pr-agent.yml', 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def test_workflow_level_permissions_defined(self, workflow_content: Dict[str, Any]):
        """Test that workflow-level permissions are defined."""
        assert 'permissions' in workflow_content, \
            "Workflow should define permissions"
    
    def test_workflow_permissions_contents_read(self, workflow_content: Dict[str, Any]):
        """Test that workflow has read access to contents."""
        permissions = workflow_content.get('permissions', {})
        assert permissions.get('contents') == 'read', \
            "Workflow should have 'contents: read' permission"
        job = workflow_content['jobs']['pr-agent-trigger']
        permissions = job.get('permissions', {})
        assert permissions.get('issues') == 'write', "pr-agent-trigger job should have 'issues: write' permission"
        job = workflow_content['jobs']['pr-agent-trigger']
        permissions = job.get('permissions', {})
        assert permissions.get('issues') == 'write', \
            "pr-agent-trigger job should have 'issues: write' permission"
    
    def test_auto_merge_job_has_pr_write(self, workflow_content: Dict[str, Any]):
        """Test that auto-merge-check job has write access to PRs."""
        job = workflow_content['jobs']['auto-merge-check']
        permissions = job.get('permissions', {})
        assert 'pull-requests' in permissions, \
            "auto-merge-check job should have pull-requests permission"


class TestPRAgentWorkflowConditionals:
    """Test conditional execution logic."""
    
    @pytest.fixture
    def workflow_content(self) -> Dict[str, Any]:
        """
        Load and parse the pr-agent GitHub Actions workflow file at .github/workflows/pr-agent.yml.
        
        Returns:
            workflow (Dict[str, Any]): Parsed YAML content of the workflow as a dictionary.
        """
        with open('.github/workflows/pr-agent.yml', 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def test_pr_agent_trigger_has_conditional(self, workflow_content: Dict[str, Any]):
        """Test that pr-agent-trigger job has conditional execution."""
        job = workflow_content['jobs']['pr-agent-trigger']
        assert 'if' in job, \
            "pr-agent-trigger job should have conditional execution"
    
    def test_pr_agent_checks_for_changes_requested(self, workflow_content: Dict[str, Any]):
        """
        Verify the pr-agent-trigger job's `if` condition references the `changes_requested` review state.
        
        Asserts that the pr-agent-trigger job in the provided workflow content contains an `if` expression that includes 'changes_requested', indicating the job conditionally runs when a review requests changes.
        """
        job = workflow_content['jobs']['pr-agent-trigger']
        condition = job.get('if', '')
        assert 'changes_requested' in condition, \
            "pr-agent-trigger should check for changes_requested review state"
    
    def test_pr_agent_checks_for_copilot_mention(self, workflow_content: Dict[str, Any]):
        """Test that pr-agent-trigger checks for @copilot mentions."""
        job = workflow_content['jobs']['pr-agent-trigger']
        condition = job.get('if', '')
        assert '@copilot' in condition or 'copilot' in condition, \
            "pr-agent-trigger should check for @copilot mentions"
    
    def test_auto_merge_has_conditional(self, workflow_content: Dict[str, Any]):
        """Test that auto-merge-check job has conditional execution."""
        job = workflow_content['jobs']['auto-merge-check']
        assert 'if' in job, \
            "auto-merge-check job should have conditional execution"
    
    def test_dependency_update_checks_title(self, workflow_content: Dict[str, Any]):
        """Test that dependency-update job checks PR title."""
        job = workflow_content['jobs']['dependency-update']
        condition = job.get('if', '')
        assert 'deps' in condition or 'title' in condition, \
            "dependency-update should check PR title for dependency updates"


class TestPRAgentWorkflowSecurityBestPractices:
    """Test security best practices in pr-agent workflow."""
    
    @pytest.fixture
    def workflow_raw(self) -> str:
        """
        Get the raw text of the pr-agent workflow file.
        
        Returns:
            workflow_raw (str): Raw contents of .github/workflows/pr-agent.yml
        """
        with open('.github/workflows/pr-agent.yml', 'r', encoding='utf-8') as f:
            return f.read()
    
    def test_uses_secrets_context_for_github_token(self, workflow_raw: str):
        """Test that GITHUB_TOKEN is accessed via secrets context."""
        if 'GITHUB_TOKEN' in workflow_raw:
            # Should use ${{ secrets.GITHUB_TOKEN }}
            assert 'secrets.GITHUB_TOKEN' in workflow_raw, \
                "GITHUB_TOKEN should be accessed via secrets context"
    
    def test_no_hardcoded_tokens(self, workflow_raw: str):
        """Test that workflow doesn't contain hardcoded tokens."""
        # Check for common token patterns
        token_patterns = [
            r'ghp_[a-zA-Z0-9]{36}',  # GitHub PAT
            r'gho_[a-zA-Z0-9]{36}',  # GitHub OAuth
        ]
        
        for pattern in token_patterns:
            matches = re.findall(pattern, workflow_raw)
            assert len(matches) == 0, \
                f"Found hardcoded token pattern: {pattern}"
    
    def test_uses_pinned_action_versions(self, workflow_raw: str):
        """
        Validate that every external GitHub Action referenced by `uses:` in the workflow is pinned to a specific commit SHA or a semantic version tag.
        
        Parameters:
            workflow_raw (str): Raw YAML text of the workflow file to scan for `uses:` statements.
        
        """
        # Capture the action reference after 'uses:' regardless of trailing content
        uses_pattern = r'^\s*uses:\s*([^\s@]+)@([^\s#]+)'
        uses_statements = re.findall(uses_pattern, workflow_raw, re.MULTILINE)

        assert uses_statements, "No 'uses:' statements found to validate"

        for owner_repo, ref in uses_statements:
            # Exclude local or docker actions
            if not owner_repo or '/' not in owner_repo:
                def test_checkout_has_fetch_depth(self, workflow_raw: str):
                    """
                    Validate that each actions/checkout step in the workflow specifies a `fetch-depth` value.
                    
                    Parameters:
                        workflow_raw (str): Raw text content of the workflow file to inspect.
                    
                    Raises:
                        AssertionError: If any `actions/checkout` step is missing a `with:` block containing a `fetch-depth: <number>`.
                    """
                    # Split into steps heuristically
                    lines = workflow_raw.splitlines()
                    checkout_indices = [i for i, l in enumerate(lines) if re.search(r'uses:\s*actions/checkout@', l)]
                    if not checkout_indices:
                        return  # no checkout used; nothing to validate

                    for idx in checkout_indices:
                        has_with = False
                        has_fetch_depth = False
                        # Scan limited lookahead within the same step block until next "- name:" or another "uses:"
                        for j in range(idx + 1, min(idx + 20, len(lines))):
                            if re.match(r'^\s*-\s+name:', lines[j]) or re.match(r'^\s*uses:\s*', lines[j]):
                                break
                            if re.match(r'^\s*with:\s*$', lines[j]):
                                has_with = True
                            if re.match(r'^\s*fetch-depth\s*:\s*\d+\s*$', lines[j]):
                                has_fetch_depth = True
                        assert has_with and has_fetch_depth, "Each actions/checkout step must specify fetch-depth under with:"

            # Accept either a full SHA or a semantic version tag (vX or vX.Y[.Z])
            is_sha = bool(re.fullmatch(r'[0-9a-fA-F]{40}', ref))
            is_semver_tag = bool(re.fullmatch(r'v?\d+(\.\d+){0,2}', ref))

            assert is_sha or is_semver_tag, (
                f"Action '{owner_repo}@{ref}' should be pinned to a commit SHA or a specific version tag"
            )
    
    def test_checkout_has_fetch_depth(self, workflow_raw: str):
        """
        Ensure the workflow's actions/checkout usage specifies a fetch-depth.
        
        If the workflow contains an `actions/checkout` step, assert that a `fetch-depth` setting is present in the workflow text.
        """
        if 'actions/checkout' in workflow_raw:
            assert 'fetch-depth' in workflow_raw, \
                "Checkout action should specify fetch-depth"


class TestPRAgentWorkflowGitHubScriptUsage:
    """Test GitHub Script action usage."""
    
    @pytest.fixture
    def workflow_content(self) -> Dict[str, Any]:
        """
        Load and parse the pr-agent GitHub Actions workflow file at .github/workflows/pr-agent.yml.
        
        Returns:
            workflow (Dict[str, Any]): Parsed YAML content of the workflow as a dictionary.
        """
        with open('.github/workflows/pr-agent.yml', 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def test_uses_github_script_action(self, workflow_content: Dict[str, Any]):
        """Test that workflow uses github-script action."""
        workflow_str = str(workflow_content)
        assert 'github-script' in workflow_str, \
            "Workflow should use actions/github-script"
    
    def test_github_script_has_script_content(self, workflow_content: Dict[str, Any]):
        """Test that github-script steps have script content."""
        for job_name, job_config in workflow_content.get('jobs', {}).items():
            steps = job_config.get('steps', [])
            for step in steps:
                if 'actions/github-script' in step.get('uses', ''):
                    with_config = step.get('with', {})
                    assert 'script' in with_config, \
                        f"github-script step in job '{job_name}' should have script content"
