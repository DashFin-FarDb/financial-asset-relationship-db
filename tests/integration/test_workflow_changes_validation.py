"""
Validation tests for GitHub workflow changes in current branch.

Tests specific changes made to workflow files, including:
- PR agent workflow simplification
- Greetings workflow message changes
- Label workflow configuration
- APISec scan workflow modifications
"""

import os
import pytest
import yaml
from pathlib import Path


class TestPRAgentWorkflowChanges:
    """Test PR agent workflow simplification changes."""
    
    @pytest.fixture
    def pr_agent_workflow(self):
        """
        Load and parse the PR Agent GitHub Actions workflow.
        
        Returns:
            dict: Parsed YAML contents of .github/workflows/pr-agent.yml as Python objects.
        """
        workflow_path = Path(".github/workflows/pr-agent.yml")
        with open(workflow_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_pr_agent_workflow_structure(self, pr_agent_workflow):
        """Verify PR agent workflow has expected structure."""
        assert 'name' in pr_agent_workflow
        assert pr_agent_workflow['name'] == 'PR Agent Workflow'
        assert 'on' in pr_agent_workflow
        assert 'jobs' in pr_agent_workflow
    
    def test_pr_agent_has_required_triggers(self, pr_agent_workflow):
        """Verify PR agent responds to correct events."""
        triggers = pr_agent_workflow['on']
        assert 'pull_request' in triggers
        assert 'pull_request_review' in triggers
        assert 'issue_comment' in triggers
        assert 'check_suite' in triggers
    
    def test_pr_agent_python_setup_simplified(self, pr_agent_workflow):
        """
        Ensure the PR Agent workflow uses a single simplified Python dependency installation step and does not install PyYAML.
        
        Searches the `pr-agent-trigger` job for a step whose name contains "Install Python dependencies", asserts exactly one such step exists, and verifies the step's `run` script does not reference `pyyaml` or `PyYAML`.
        """
        pr_agent_job = pr_agent_workflow['jobs']['pr-agent-trigger']
        steps = pr_agent_job['steps']
        
        # Find Python dependency installation step
        install_steps = [s for s in steps if 'Install Python dependencies' in s.get('name', '')]
        assert len(install_steps) == 1, "Should have exactly one Python install step"
        
        install_step = install_steps[0]
        run_script = install_step['run']
        
        # Verify no duplicate pyyaml installations
        assert run_script.count('pyyaml') == 0, "Should not explicitly install pyyaml in workflow"
        assert run_script.count('PyYAML') == 0, "Should not explicitly install PyYAML in workflow"
    
    def test_pr_agent_no_context_chunking_references(self, pr_agent_workflow):
        """Verify context chunking logic removed from workflow."""
        workflow_str = yaml.dump(pr_agent_workflow)
        
        # These should NOT appear in the simplified workflow
        assert 'context_chunker' not in workflow_str.lower()
        assert 'chunking' not in workflow_str.lower()
        assert 'tiktoken' not in workflow_str.lower()
    
    def test_pr_agent_uses_gh_cli_for_parsing(self, pr_agent_workflow):
        """Verify workflow uses gh CLI for PR comment parsing."""
        pr_agent_job = pr_agent_workflow['jobs']['pr-agent-trigger']
        steps = pr_agent_job['steps']
        
        parse_step = next((s for s in steps if 'Parse PR' in s.get('name', '')), None)
        assert parse_step is not None
        assert 'gh api' in parse_step['run']
    
    def test_pr_agent_has_proper_permissions(self, pr_agent_workflow):
        """
        Verify the PR Agent workflow exposes minimal permissions.
        
        Asserts the workflow top-level 'permissions' sets 'contents' to 'read' and the 'pr-agent-trigger' job-level 'permissions' sets 'issues' to 'write'.
        """
        # Top-level permissions
        assert pr_agent_workflow.get('permissions', {}).get('contents') == 'read'
        
        # Job-level permissions
        pr_agent_job = pr_agent_workflow['jobs']['pr-agent-trigger']
        assert pr_agent_job.get('permissions', {}).get('issues') == 'write'


class TestGreetingsWorkflowChanges:
    """Test greetings workflow simplification."""
    
    @pytest.fixture
    def greetings_workflow(self):
        """
        Load and parse the greetings GitHub Actions workflow YAML.
        
        Returns:
            The parsed contents of `.github/workflows/greetings.yml` as native Python structures (usually a dict).
        """
        workflow_path = Path(".github/workflows/greetings.yml")
        with open(workflow_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_greetings_workflow_simplified(self, greetings_workflow):
        """Verify greetings workflow uses simple messages."""
        job = greetings_workflow['jobs']['greeting']
        step = job['steps'][0]
        
        # Should use simple placeholder messages, not complex templates
        assert 'issue-message' in step['with']
        assert 'pr-message' in step['with']
        
        issue_msg = step['with']['issue-message']
        pr_msg = step['with']['pr-message']
        
        # Simplified messages should be short
        assert len(issue_msg) < 200
        assert len(pr_msg) < 200


class TestLabelWorkflowChanges:
    """Test label workflow simplification."""
    
    @pytest.fixture
    def label_workflow(self):
        """
        Load and parse the label workflow YAML from .github/workflows/label.yml.
        
        Returns:
            dict: Parsed workflow content as returned by yaml.safe_load.
        """
        workflow_path = Path(".github/workflows/label.yml")
        with open(workflow_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_label_workflow_no_config_check(self, label_workflow):
        """
        Assert the label workflow's 'label' job does not include a step that checks for a configuration file.
        
        The test collects step names from the 'label' job and fails if any name contains both "check" and "config" (case-insensitive).
        """
        job = label_workflow['jobs']['label']
        steps = job['steps']
        
        # Should not have conditional config checking
        step_names = [s.get('name', '') for s in steps]
        assert not any('check' in name.lower() and 'config' in name.lower() 
                      for name in step_names)
    
    def test_label_workflow_uses_actions_labeler(self, label_workflow):
        """Verify workflow uses actions/labeler correctly."""
        job = label_workflow['jobs']['label']
        steps = job['steps']
        
        labeler_step = next((s for s in steps if 'actions/labeler' in s.get('uses', '')), None)
        assert labeler_step is not None
        assert 'with' in labeler_step
        assert 'repo-token' in labeler_step['with']


class TestAPISecWorkflowChanges:
    """Test APISec workflow changes."""
    
    @pytest.fixture
    def apisec_workflow(self):
        """
        Load and parse the APISec workflow YAML from .github/workflows/apisec-scan.yml.
        
        Returns:
            workflow (dict): Parsed YAML content of the APISec workflow file.
        """
        workflow_path = Path(".github/workflows/apisec-scan.yml")
        with open(workflow_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_apisec_no_credential_checks(self, apisec_workflow):
        """
        Ensure the APISec Trigger_APIsec_scan job contains no credential-checking steps.
        
        Asserts that no step name within the job contains both "check" and "credential" (case-insensitive).
        """
        job = apisec_workflow['jobs']['Trigger_APIsec_scan']
        steps = job['steps']
        
        # Should not have credential checking steps
        step_names = [s.get('name', '') for s in steps]
        assert not any('check' in name.lower() and 'credential' in name.lower() 
                      for name in step_names)
    
    def test_apisec_no_conditional_if(self, apisec_workflow):
        """Verify APISec job doesn't have conditional execution."""
        job = apisec_workflow['jobs']['Trigger_APIsec_scan']
        assert 'if' not in job, "APISec job should not have conditional execution"


class TestDeletedFilesImpact:
    """Test that deleted files don't break workflows."""
    
    def test_labeler_config_file_deleted(self):
        """
        Check that the repository no longer contains the labeler configuration file.
        
        Asserts that .github/labeler.yml does not exist.
        """
        labeler_path = Path(".github/labeler.yml")
        assert not labeler_path.exists(), "labeler.yml should be deleted"
    
    def test_context_chunker_script_deleted(self):
        """Verify context_chunker.py script was removed."""
        chunker_path = Path(".github/scripts/context_chunker.py")
        assert not chunker_path.exists(), "context_chunker.py should be deleted"
    
    def test_scripts_readme_deleted(self):
        """Verify scripts README was removed."""
        readme_path = Path(".github/scripts/README.md")
        assert not readme_path.exists(), "scripts/README.md should be deleted"
    
    def test_no_workflow_references_to_deleted_scripts(self):
        """Verify no workflows reference the deleted context_chunker script."""
        workflows_dir = Path(".github/workflows")
        
        for workflow_file in workflows_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                content = f.read()
                assert 'context_chunker' not in content.lower(), \
                    f"{workflow_file.name} should not reference deleted context_chunker script"


class TestWorkflowSecurityBestPractices:
    """Test security best practices in modified workflows."""
    
    def test_workflows_use_pinned_action_versions(self):
        """Verify workflows use specific action versions, not 'latest'."""
        workflows_dir = Path(".github/workflows")
        
        for workflow_file in workflows_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
            
            # Check all jobs and steps
            for job_name, job in workflow.get('jobs', {}).items():
                for step in job.get('steps', []):
                    if 'uses' in step:
                        action = step['uses']
                        # Should have version specifier
                        assert '@' in action, \
                            f"Action {action} in {workflow_file.name} should specify version"
                        # Should not use 'latest' or 'master'
                        assert '@latest' not in action.lower()
                        assert '@master' not in action.lower()
    
    def test_workflows_limit_github_token_permissions(self):
        """Verify workflows follow least-privilege principle."""
        workflows_dir = Path(".github/workflows")
        
        for workflow_file in workflows_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
            
            # If permissions are specified, they should be limited
            if 'permissions' in workflow:
                perms = workflow['permissions']
                # Should not have blanket 'write-all' permission
                assert perms.get('contents') != 'write' or \
                       len(perms) > 1, \
                    f"{workflow_file.name} should limit permissions"


class TestWorkflowYAMLValidity:
    """Test YAML validity and formatting of workflows."""
    
    def test_all_workflows_valid_yaml(self):
        """
        Check each YAML workflow in .github/workflows for valid syntax.
        
        Fails the test if any file under .github/workflows with a .yml extension contains invalid YAML.
        """
        workflows_dir = Path(".github/workflows")
        
        for workflow_file in workflows_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                try:
                    yaml.safe_load(f)
                except yaml.YAMLError as e:
                    pytest.fail(f"{workflow_file.name} has invalid YAML: {e}")
    
    def test_workflows_have_required_fields(self):
        """
        Check each workflow file under .github/workflows contains the top-level keys 'name', 'on', and 'jobs'.
        
        If a workflow is missing any of these keys the test fails with an assertion identifying the workflow filename and the missing key.
        """
        workflows_dir = Path(".github/workflows")
        
        for workflow_file in workflows_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
            
            assert 'name' in workflow, f"{workflow_file.name} missing 'name'"
            assert 'on' in workflow, f"{workflow_file.name} missing 'on' trigger"
            assert 'jobs' in workflow, f"{workflow_file.name} missing 'jobs'"
    
    def test_workflow_jobs_have_runs_on(self):
        """
        Ensure every job in each GitHub workflow declares the runner using the `runs-on` key.
        
        Raises an assertion with the job name and workflow filename if any job definition is missing `runs-on`.
        """
        workflows_dir = Path(".github/workflows")
        
        for workflow_file in workflows_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
            
            for job_name, job in workflow.get('jobs', {}).items():
                assert 'runs-on' in job, \
                    f"Job '{job_name}' in {workflow_file.name} missing 'runs-on'"


class TestWorkflowIntegration:
    """Test integration between workflows and repository structure."""
    
    def test_workflows_reference_existing_paths(self):
        """
        Check that file paths referenced in workflow YAML files exist in the repository.
        
        Scans each file in .github/workflows for referenced paths (for example `working-directory:` and `path:` fields),
        normalises leading `./`, and ignores variable or wildcard references. Fails the test if any referenced path
        that is not a variable or wildcard does not exist in the repository.
        """
        workflows_dir = Path(".github/workflows")
        repo_root = Path(".")
        
        for workflow_file in workflows_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                content = f.read()
            
            # Common path patterns to check
            import re
            path_patterns = [
                r'working-directory:\s+(.+)',
                r'path:\s+["\']([^"\']+)["\']',
            ]
            
            for pattern in path_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    path = match.strip()
                    if path.startswith('./'):
                        path = path[2:]
                    # Skip variables and wildcards
                    if '$' not in path and '*' not in path:
                        full_path = repo_root / path
                        assert full_path.exists(), \
                            f"Path {path} referenced in {workflow_file.name} doesn't exist"