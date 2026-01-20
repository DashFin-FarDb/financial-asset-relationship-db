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
        Return the filesystem path to the PR agent GitHub Actions workflow file.
        
        Returns:
            Path: Path to '.github/workflows/pr-agent.yml'.
        """
        return Path('.github/workflows/pr-agent.yml')
    
    @pytest.fixture
    def workflow_content(self, workflow_file: Path) -> Dict[str, Any]:
        """
        Load and parse the GitHub Actions workflow YAML into a Python mapping.
        
        Parameters:
            workflow_file (Path): Path to the workflow YAML file to read and parse.
        
        Returns:
            Dict[str, Any]: Parsed YAML content as a dictionary.
        
        Notes:
            If the file is missing, the test is skipped. If the YAML is invalid, the test is failed with the parse error.
        """
        try:
            with open(workflow_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            pytest.skip('Workflow file not found')
        except yaml.YAMLError as e:
            pytest.fail(f'Invalid YAML: {e}')
    
    @pytest.fixture
    def workflow_raw(self, workflow_file: Path) -> str:
        """
        Return the raw text of the workflow file for text-based validations.
        
        If the file is not found, the test will be skipped.
        
        Returns:
            str: Full file contents decoded as UTF-8.
        """
        try:
            with open(workflow_file, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            pytest.skip('Workflow file not found')
    
    def test_no_duplicate_step_name_setup_python(self, workflow_content: Dict[str, Any]):
        """
        Ensure each job contains at most one step named 'Setup Python'.
        
        Parameters:
            workflow_content (dict): Parsed GitHub Actions workflow YAML as a mapping; used to inspect the top-level 'jobs' and their 'steps' to count occurrences of the step name "Setup Python".
        """
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
        # Module-level fixtures (add at the top of the file after imports)
        """
        Provide a module-scoped pytest fixture that loads and parses the GitHub Actions workflow at .github/workflows/pr-agent.yml.
        
        If the workflow file is missing, the fixture will skip the requesting tests; if the YAML is invalid, the fixture will fail the requesting tests with the YAML error.
        
        Returns:
            dict: Parsed YAML content of the workflow file as a mapping.
        """
        @pytest.fixture(scope='module')
        def workflow_content() -> Dict[str, Any]:
            """
            Load and parse the PR agent GitHub Actions workflow YAML into a dictionary.
            
            Skips the test if the workflow file is missing and fails the test if the YAML is invalid.
            
            Returns:
                Parsed workflow content as a dictionary (mapping YAML keys to Python values).
            """
            try:
                with open('.github/workflows/pr-agent.yml', 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
            except FileNotFoundError:
                pytest.skip('Workflow file not found')
            except yaml.YAMLError as e:
                pytest.fail(f'Invalid YAML: {e}')

        @pytest.fixture(scope='module')
        def pr_agent_job(workflow_content: Dict[str, Any]) -> Dict[str, Any]:
            """
            Get the "pr-agent-trigger" job mapping from parsed workflow content.
            
            Parameters:
                workflow_content (Dict[str, Any]): Parsed YAML of the workflow file (top-level mapping).
            
            Returns:
                Dict[str, Any]: Mapping representing the `pr-agent-trigger` job.
            
            Raises:
                KeyError: If the top-level `jobs` key or the `pr-agent-trigger` job is not present.
            """
            return workflow_content['jobs']['pr-agent-trigger']

        # Remove all duplicate fixture definitions from individual test classes
    
    def test_has_pr_agent_trigger_job(self, workflow_content: Dict[str, Any]):
        """
        Assert the workflow defines a top-level job named "pr-agent-trigger".
        
        Checks that `workflow_content` contains a top-level `jobs` mapping and that the `pr-agent-trigger` job key is present.
        
        Parameters:
            workflow_content (Dict[str, Any]): Parsed YAML mapping of the workflow file.
        """
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
        Return the configuration mapping for the 'pr-agent-trigger' job from the repository's workflow file.
        
        Reads .github/workflows/pr-agent.yml and returns the mapping found at ['jobs']['pr-agent-trigger']. If the workflow file is missing the test is skipped; if the YAML is invalid the test fails.
        
        Returns:
            Dict[str, Any]: The `pr-agent-trigger` job configuration mapping.
        """
        try:
            with open('.github/workflows/pr-agent.yml', 'r', encoding='utf-8') as f:
                workflow = yaml.safe_load(f)
            return workflow['jobs']['pr-agent-trigger']
        except FileNotFoundError:
            pytest.skip('Workflow file not found')
        except yaml.YAMLError as e:
            pytest.fail(f'Invalid YAML: {e}')
    
    def test_checkout_step_exists(self, pr_agent_job: Dict[str, Any]):
        """
        Verify the job contains at least one checkout step that uses `actions/checkout`.
        
        Parameters:
            pr_agent_job (Dict[str, Any]): Job dictionary from the parsed workflow YAML; its `steps` list is inspected for a step with a `uses` value starting with `actions/checkout`.
        """
        steps = pr_agent_job.get('steps', [])
        checkout_steps = [
            step for step in steps
            if step.get('uses', '').startswith('actions/checkout')
        ]
        assert len(checkout_steps) >= 1, "Job should have checkout step"
    
    def test_setup_python_exists(self, pr_agent_job: Dict[str, Any]):
        """
        Assert the job defines exactly one step named "Setup Python".
        
        Parameters:
            pr_agent_job (dict): The job dictionary (typically the 'pr-agent-trigger' job from the parsed workflow) to inspect.
        """
        steps = pr_agent_job.get('steps', [])
        python_steps = [
            step for step in steps
            if step.get('name') == 'Setup Python'
        ]
        assert len(python_steps) == 1, "Job should have exactly one Setup Python step"
    
    def test_setup_nodejs_exists(self, pr_agent_job: Dict[str, Any]):
        """
        Verify the job contains at least one step named "Setup Node.js".
        
        Raises:
            AssertionError: If no step named "Setup Node.js" is present.
        """
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
        """
        Asserts the pr-agent-trigger job specifies Node.js version 18 for its "Setup Node.js" step.
        
        Checks the job's steps for one named "Setup Node.js" and verifies its `with.node-version` is exactly "18".
        
        Parameters:
            pr_agent_job (dict): Mapping representing the `pr-agent-trigger` job configuration from the workflow YAML.
        """
        steps = pr_agent_job.get('steps', [])
        for step in steps:
            if step.get('name') == 'Setup Node.js':
                version = step.get('with', {}).get('node-version')
                assert version == '18', \
                    f"Expected Node.js version '18', got '{version}'"
    
    def test_setup_order_correct(self, pr_agent_job: Dict[str, Any]):
        """
        Verify the setup steps in the pr-agent-trigger job are ordered as: checkout, Setup Python, then Setup Node.js.
        
        Asserts that when the relevant steps are present, actions/checkout appears before the "Setup Python" step, and "Setup Python" appears before the "Setup Node.js" step. If one or more of these steps are absent, the corresponding ordering assertion is skipped.
        
        Parameters:
            pr_agent_job (dict): Parsed job dictionary from the workflow file; expected to include a 'steps' list.
        """
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
        Return the configuration mapping for the 'pr-agent-trigger' job from the repository's workflow file.
        
        Reads .github/workflows/pr-agent.yml and returns the mapping found at ['jobs']['pr-agent-trigger']. If the workflow file is missing the test is skipped; if the YAML is invalid the test fails.
        
        Returns:
            Dict[str, Any]: The `pr-agent-trigger` job configuration mapping.
        """
        try:
            with open('.github/workflows/pr-agent.yml', 'r', encoding='utf-8') as f:
                workflow = yaml.safe_load(f)
            return workflow['jobs']['pr-agent-trigger']
        except FileNotFoundError:
            pytest.skip('Workflow file not found')
        except yaml.YAMLError as e:
            pytest.fail(f'Invalid YAML: {e}')
    
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
        """Test that Python install step includes requirements-dev.txt."""
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
        Return the `pr-agent-trigger` job dictionary from the parsed workflow content and verify it includes a Python testing step.
        
        This fixture retrieves the job mapping for `pr-agent-trigger` and asserts that the job's steps contain at least one step whose name contains both "Python" and "Test".
        
        Returns:
            Dict[str, Any]: The `pr-agent-trigger` job dictionary.
        
        """
        steps = pr_agent_job.get('steps', [])
        test_steps = [
            step for step in steps
            if re.match(r'^Python Test(s)?$', step.get('name', ''))
        ]
            if 'Python' in step.get('name', '') and 'Test' in step.get('name', '')
        ]
        assert len(test_steps) >= 1, "Job should include Python testing step"
    
    def test_frontend_tests_step_exists(self, pr_agent_job: Dict[str, Any]):
        """Test that frontend tests step exists."""
        steps = pr_agent_job.get('steps', [])
        test_steps = [
            step for step in steps
            if 'Frontend' in step.get('name', '') and 'Test' in step.get('name', '')
        ]
        assert len(test_steps) >= 1, "Job should include frontend testing step"
    
    def test_python_linting_step_exists(self, pr_agent_job: Dict[str, Any]):
        """Test that Python linting step exists."""
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
        Load and parse the GitHub Actions workflow at .github/workflows/pr-agent.yml into a dictionary.
        
        Skips the running test if the file is missing and fails the test if the YAML is invalid.
        
        Returns:
            dict: Parsed workflow content as a dictionary.
        """
        try:
            with open('.github/workflows/pr-agent.yml', 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            pytest.skip('Workflow file not found')
        except yaml.YAMLError as e:
            pytest.fail(f'Invalid YAML: {e}')
    
    def test_workflow_level_permissions_defined(self, workflow_content: Dict[str, Any]):
        """
        Assert that the parsed workflow content includes a top-level 'permissions' key.
        """
        assert 'permissions' in workflow_content, \
            "Workflow should define permissions"
    
    def test_workflow_permissions_contents_read(self, workflow_content: Dict[str, Any]):
        """
        Verify workflow-level and pr-agent-trigger job permissions: the workflow's `contents` permission is set to 'read' and the `pr-agent-trigger` job's `issues` permission is set to 'write'.
        """
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
        """
        Assert that the auto-merge-check job grants the `pull-requests` permission.
        
        Fails the test if the `auto-merge-check` job's `permissions` mapping does not contain the `pull-requests` key.
        """
        job = workflow_content['jobs']['auto-merge-check']
        permissions = job.get('permissions', {})
        assert 'pull-requests' in permissions, \
            "auto-merge-check job should have pull-requests permission"


class TestPRAgentWorkflowConditionals:
    """Test conditional execution logic."""
    
    @pytest.fixture
    def workflow_content(self) -> Dict[str, Any]:
        """
        Load and parse the GitHub Actions workflow at .github/workflows/pr-agent.yml into a dictionary.
        
        Skips the running test if the file is missing and fails the test if the YAML is invalid.
        
        Returns:
            dict: Parsed workflow content as a dictionary.
        """
        try:
            with open('.github/workflows/pr-agent.yml', 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            pytest.skip('Workflow file not found')
        except yaml.YAMLError as e:
            pytest.fail(f'Invalid YAML: {e}')
    
    def test_pr_agent_trigger_has_conditional(self, workflow_content: Dict[str, Any]):
        """
        Assert that the `pr-agent-trigger` job defines an `if` conditional.
        
        Raises:
            AssertionError: If the `pr-agent-trigger` job does not contain an `if` key.
        """
        job = workflow_content['jobs']['pr-agent-trigger']
        assert 'if' in job, \
            "pr-agent-trigger job should have conditional execution"
    
    def test_pr_agent_checks_for_changes_requested(self, workflow_content: Dict[str, Any]):
        """
        Assert the pr-agent-trigger job's `if` condition references the 'changes_requested' review state.
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
        Read and return the raw text of the .github/workflows/pr-agent.yml workflow file.
        
        If the workflow file is not found, the calling test is skipped via pytest.skip.
        
        Returns:
            Raw YAML text of the PR Agent workflow file.
        """
        try:
            with open('.github/workflows/pr-agent.yml', 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            pytest.skip('Workflow file not found')
    
    def test_uses_secrets_context_for_github_token(self, workflow_raw: str):
        """Test that GITHUB_TOKEN is accessed via secrets context."""
        if 'GITHUB_TOKEN' in workflow_raw:
            # Should use ${{ secrets.GITHUB_TOKEN }}
            assert 'secrets.GITHUB_TOKEN' in workflow_raw, \
                "GITHUB_TOKEN should be accessed via secrets context"
    
    def test_no_hardcoded_tokens(self, workflow_raw: str):
        """
        Scan the workflow text for common hardcoded token patterns and fail if any are found.
        
        Searches the provided raw workflow YAML for known token formats (for example: GitHub PATs, OpenAI keys, Slack tokens, and npm tokens) and asserts that none are present.
        
        Parameters:
            workflow_raw (str): Raw text of the workflow file to scan.
        """
        # Check for common token patterns
        token_patterns = [
            r'ghp_[a-zA-Z0-9]{36}',  # GitHub PAT (classic)
            r'gho_[a-zA-Z0-9]{36}',  # GitHub OAuth
            r'github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}',  # GitHub PAT (fine-grained)
            r'ghu_[a-zA-Z0-9]{36}',  # GitHub user-to-server token
            r'ghs_[a-zA-Z0-9]{36}',  # GitHub server-to-server token
            r'ghr_[a-zA-Z0-9]{36}',  # GitHub refresh token
            r'sk-[a-zA-Z0-9]{20,}',  # OpenAI API key (flexible length)
            r'xox[baprs]-[0-9]+-[0-9]+-[a-zA-Z0-9]+',  # Slack tokens (structured format)
            r'npm_[a-zA-Z0-9]{36}',  # npm access token
        ]
        
        for pattern in token_patterns:
            matches = re.findall(pattern, workflow_raw)
            assert len(matches) == 0, \
                f"Found hardcoded token pattern: {pattern}"
    
    def test_uses_pinned_action_versions(self, workflow_raw: str):
        """
        Verify that all non-local GitHub Actions referenced in the workflow are pinned to immutable versions.
        
        Checks each `uses:` entry in the raw workflow text (excluding local or docker-style references) and asserts each action is pinned either to a 40-character commit SHA or to a semantic version tag such as `v1`, `v1.2`, or `v1.2.3`. Also asserts that at least one `uses:` statement is present.
        
        Parameters:
            workflow_raw (str): Raw text content of the GitHub Actions workflow file being validated.
        """
        # Capture the action reference after 'uses:' regardless of trailing content
        uses_pattern = r'^\s*uses:\s*([^\s@]+)@([^\s#]+)'
        uses_statements = re.findall(uses_pattern, workflow_raw, re.MULTILINE)

        assert uses_statements, "No 'uses:' statements found to validate"

        for owner_repo, ref in uses_statements:
            # Exclude local or docker actions
            if not owner_repo or '/' not in owner_repo:
                def test_checkout_has_fetch_depth(self, workflow_raw: str):
                    """Test that each actions/checkout step specifies fetch-depth."""
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
        """Test that checkout action specifies fetch-depth."""
        if 'actions/checkout' in workflow_raw:
            assert 'fetch-depth' in workflow_raw, \
                "Checkout action should specify fetch-depth"


class TestPRAgentWorkflowGitHubScriptUsage:
    """Test GitHub Script action usage."""
    
    @pytest.fixture
    def workflow_content(self) -> Dict[str, Any]:
        """
        Load and parse the GitHub Actions workflow at .github/workflows/pr-agent.yml into a dictionary.
        
        Skips the running test if the file is missing and fails the test if the YAML is invalid.
        
        Returns:
            dict: Parsed workflow content as a dictionary.
        """
        try:
            with open('.github/workflows/pr-agent.yml', 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            pytest.skip('Workflow file not found')
        except yaml.YAMLError as e:
            pytest.fail(f'Invalid YAML: {e}')
    
    def test_uses_github_script_action(self, workflow_content: Dict[str, Any]):
        """
        Check whether the workflow includes the actions/github-script action.
        
        Asserts that the parsed workflow content contains the substring 'github-script' when converted to a string.
        
        Parameters:
            workflow_content (dict): Parsed YAML content of .github/workflows/pr-agent.yml.
        """
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
