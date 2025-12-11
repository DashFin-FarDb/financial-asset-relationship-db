"""
Additional edge case tests for workflow simplification changes.

This module tests edge cases, boundary conditions, and potential regressions
that could occur from the workflow simplification changes.
"""

import pytest
import yaml
from pathlib import Path
from typing import Dict, Any, List


WORKFLOWS_DIR = Path(__file__).parent.parent.parent / ".github" / "workflows"
CONFIG_FILE = Path(__file__).parent.parent.parent / ".github" / "pr-agent-config.yml"


def load_workflow(workflow_name: str) -> Dict[str, Any]:
    """Load a workflow file."""
    workflow_path = WORKFLOWS_DIR / workflow_name
    if not workflow_path.exists():
        pytest.skip(f"{workflow_name} not found")
    
    with open(workflow_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


class TestPRAgentWorkflowEdgeCases:
    """Edge case tests for PR agent workflow changes."""
    
    @pytest.fixture
    def workflow(self) -> Dict[str, Any]:
        """Load PR agent workflow."""
        return load_workflow("pr-agent.yml")
    
    def test_on_key_properly_quoted(self, workflow: Dict[str, Any]):
        """Test that 'on' key is properly quoted (bug fix from diff)."""
        # The workflow should have either 'on' or '"on"' as a key
        assert 'on' in workflow or '"on"' in workflow, \
            "Workflow should have 'on' trigger key"
        
        # Verify the workflow file has "on": (quoted) in the source
        workflow_path = WORKFLOWS_DIR / "pr-agent.yml"
        with open(workflow_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should have quoted "on": to avoid YAML parsing issues
        assert '"on":' in content or "'on':" in content, \
            "'on' key should be quoted in YAML"
    
    def test_python_dependency_installation_robust(self, workflow: Dict[str, Any]):
        """Test that Python dependency installation is robust."""
        jobs = workflow.get('jobs', {})
        
        for job_name, job_config in jobs.items():
            steps = job_config.get('steps', [])
            
            install_steps = [
                step for step in steps 
                if 'name' in step and 'python' in step['name'].lower() 
                and 'dependencies' in step['name'].lower()
            ]
            
            for step in install_steps:
                run_script = step.get('run', '')
                
                # Should have proper error handling
                assert 'pip install --upgrade pip' in run_script, \
                    "Should upgrade pip first"
                
                # Should check for file existence
                if 'requirements' in run_script:
                    assert 'if [ -f' in run_script or 'test -f' in run_script, \
                        "Should check if requirements file exists"
    
    def test_no_duplicate_setup_python_steps(self, workflow: Dict[str, Any]):
        """Test that there are no duplicate 'Setup Python' steps."""
        jobs = workflow.get('jobs', {})
        
        for job_name, job_config in jobs.items():
            steps = job_config.get('steps', [])
            
            setup_python_steps = [
                step for step in steps 
                if 'name' in step and 'python' in step['name'].lower() 
                and 'setup' in step['name'].lower()
            ]
            
            assert len(setup_python_steps) <= 1, \
                f"Job {job_name} should not have duplicate 'Setup Python' steps"
    
    def test_parse_comments_step_exists(self, workflow: Dict[str, Any]):
        """Test that parse comments step exists (replaced chunking)."""
        jobs = workflow.get('jobs', {})
        
        has_parse_step = False
        for job_name, job_config in jobs.items():
            steps = job_config.get('steps', [])
            
            parse_steps = [
                step for step in steps 
                if 'name' in step and 'parse' in step['name'].lower() 
                and 'comment' in step['name'].lower()
            ]
            
            if len(parse_steps) > 0:
                has_parse_step = True
                
                # Verify it outputs action_items
                for step in parse_steps:
                    assert 'id' in step, \
                        "Parse step should have an ID for output"
                    
                    run_script = step.get('run', '')
                    assert 'action_items' in run_script or 'ACTION_ITEMS' in run_script, \
                        "Parse step should extract action items"
        
        # At least one job should have parse step
        assert has_parse_step, \
            "At least one job should have comment parsing step"
    
    def test_github_cli_usage(self, workflow: Dict[str, Any]):
        """Test that GitHub CLI (gh) is used correctly."""
        jobs = workflow.get('jobs', {})
        
        for job_name, job_config in jobs.items():
            steps = job_config.get('steps', [])
            
            for step in steps:
                run_script = step.get('run', '')
                
                if 'gh api' in run_script:
                    # Should have GITHUB_TOKEN in env
                    env = step.get('env', {})
                    assert 'GITHUB_TOKEN' in env or 'GH_TOKEN' in env, \
                        f"Step using 'gh api' should have GITHUB_TOKEN in env"
    
    def test_no_hardcoded_pr_numbers(self, workflow: Dict[str, Any]):
        """Test that PR numbers are dynamically retrieved."""
        workflow_path = WORKFLOWS_DIR / "pr-agent.yml"
        with open(workflow_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should use github.event context, not hardcoded numbers
        if 'pulls/' in content:
            assert '{{ github.event' in content, \
                "Should use github.event context for PR numbers"
            assert 'pulls/123' not in content, \
                "Should not have hardcoded PR numbers"


class TestLabelWorkflowEdgeCases:
    """Edge case tests for label workflow simplification."""
    
    @pytest.fixture
    def workflow(self) -> Dict[str, Any]:
        """Load label workflow."""
        return load_workflow("label.yml")
    
    def test_labeler_action_version(self, workflow: Dict[str, Any]):
        """Test that labeler action version is specified."""
        jobs = workflow.get('jobs', {})
        label_job = jobs.get('label', {})
        steps = label_job.get('steps', [])
        
        labeler_steps = [
            step for step in steps 
            if 'uses' in step and 'labeler' in step['uses'].lower()
        ]
        
        assert len(labeler_steps) > 0, \
            "Should have labeler action step"
        
        for step in labeler_steps:
            uses = step['uses']
            # Should have version pinned
            assert '@' in uses, \
                "Labeler action should have version pinned"
    
    def test_minimal_permissions(self, workflow: Dict[str, Any]):
        """Test that workflow has minimal required permissions."""
        permissions = workflow.get('permissions', {})
        
        # Should have pull-requests: write
        assert 'pull-requests' in permissions, \
            "Should have pull-requests permission"
        assert permissions['pull-requests'] == 'write', \
            "Should have write permission for pull-requests"
        
        # Should not have excessive permissions
        assert 'contents' in permissions, \
            "Should explicitly set contents permission"
    
    def test_single_labeler_step(self, workflow: Dict[str, Any]):
        """Test that there's only one labeler step."""
        jobs = workflow.get('jobs', {})
        label_job = jobs.get('label', {})
        steps = label_job.get('steps', [])
        
        labeler_steps = [
            step for step in steps 
            if 'uses' in step and 'labeler' in step['uses'].lower()
        ]
        
        assert len(labeler_steps) == 1, \
            "Should have exactly one labeler step"
    
    def test_repo_token_configured(self, workflow: Dict[str, Any]):
        """Test that repo-token is properly configured."""
        jobs = workflow.get('jobs', {})
        label_job = jobs.get('label', {})
        steps = label_job.get('steps', [])
        
        labeler_steps = [
            step for step in steps 
            if 'uses' in step and 'labeler' in step['uses'].lower()
        ]
        
        for step in labeler_steps:
            with_config = step.get('with', {})
            assert 'repo-token' in with_config, \
                "Labeler should have repo-token configured"


class TestGreetingsWorkflowEdgeCases:
    """Edge case tests for greetings workflow simplification."""
    
    @pytest.fixture
    def workflow(self) -> Dict[str, Any]:
        """Load greetings workflow."""
        return load_workflow("greetings.yml")
    
    def test_trigger_on_correct_events(self, workflow: Dict[str, Any]):
        """Test that workflow triggers on correct events."""
        on_config = workflow.get('on', {})
        
        # Should trigger on issues and pull_request
        assert 'issues' in on_config or 'issues' in str(on_config), \
            "Should trigger on issues"
        assert 'pull_request' in on_config or 'pull_request' in str(on_config), \
            "Should trigger on pull_request"
    
    def test_first_interaction_action_version(self, workflow: Dict[str, Any]):
        """Test that first-interaction action has version."""
        jobs = workflow.get('jobs', {})
        greeting_job = jobs.get('greeting', {})
        steps = greeting_job.get('steps', [])
        
        interaction_steps = [
            step for step in steps 
            if 'uses' in step and 'first-interaction' in step['uses'].lower()
        ]
        
        assert len(interaction_steps) > 0, \
            "Should have first-interaction step"
        
        for step in interaction_steps:
            uses = step['uses']
            assert '@' in uses, \
                "First-interaction action should have version"
    
    def test_messages_are_strings(self, workflow: Dict[str, Any]):
        """Test that messages are simple strings, not complex blocks."""
        jobs = workflow.get('jobs', {})
        greeting_job = jobs.get('greeting', {})
        steps = greeting_job.get('steps', [])
        
        for step in steps:
            with_config = step.get('with', {})
            
            if 'issue-message' in with_config:
                msg = with_config['issue-message']
                assert isinstance(msg, str), \
                    "Issue message should be a string"
                assert '\n' not in msg or len(msg.split('\n')) < 5, \
                    "Issue message should be concise"
            
            if 'pr-message' in with_config:
                msg = with_config['pr-message']
                assert isinstance(msg, str), \
                    "PR message should be a string"
                assert '\n' not in msg or len(msg.split('\n')) < 5, \
                    "PR message should be concise"


class TestAPISecWorkflowEdgeCases:
    """Edge case tests for APISec workflow simplification."""
    
    @pytest.fixture
    def workflow(self) -> Dict[str, Any]:
        """Load APISec workflow."""
        return load_workflow("apisec-scan.yml")
    
    def test_concurrency_configuration(self, workflow: Dict[str, Any]):
        """Test that concurrency is properly configured."""
        jobs = workflow.get('jobs', {})
        
        for job_name, job_config in jobs.items():
            if 'concurrency' in job_config:
                concurrency = job_config['concurrency']
                
                assert 'group' in concurrency, \
                    f"Job {job_name} concurrency should have group"
                assert 'cancel-in-progress' in concurrency, \
                    f"Job {job_name} concurrency should have cancel-in-progress"
    
    def test_apisec_action_configuration(self, workflow: Dict[str, Any]):
        """Test that APISec action is properly configured."""
        jobs = workflow.get('jobs', {})
        
        for job_name, job_config in jobs.items():
            steps = job_config.get('steps', [])
            
            apisec_steps = [
                step for step in steps 
                if 'uses' in step and 'apisec' in step['uses'].lower()
            ]
            
            for step in apisec_steps:
                with_config = step.get('with', {})
                
                # Should have necessary configuration
                assert len(with_config) > 0, \
                    "APISec step should have configuration"
                
                # Should have SHA-pinned version for security
                uses = step['uses']
                if '@' in uses:
                    version = uses.split('@')[1]
                    # If using SHA, it should be full 40-char SHA
                    if len(version) == 40:
                        assert version.isalnum(), \
                            "SHA should be alphanumeric"
    
    def test_no_early_exit_on_missing_credentials(self, workflow: Dict[str, Any]):
        """Test that workflow doesn't exit early on missing credentials."""
        workflow_path = WORKFLOWS_DIR / "apisec-scan.yml"
        with open(workflow_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should not have exit 0 for missing credentials
        assert 'exit 0' not in content or 'credential' not in content.lower(), \
            "Should not exit early on missing credentials"


class TestPRAgentConfigEdgeCases:
    """Edge case tests for PR agent config changes."""
    
    @pytest.fixture
    def config(self) -> Dict[str, Any]:
        """Load PR agent config."""
        if not CONFIG_FILE.exists():
            pytest.skip("pr-agent-config.yml not found")
        
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def test_version_downgrade_intentional(self, config: Dict[str, Any]):
        """Test that version downgrade was intentional."""
        agent_config = config.get('agent', {})
        version = agent_config.get('version', '')
        
        # Version should be 1.0.0 (downgraded from 1.1.0)
        assert version == "1.0.0", \
            "Agent version should be 1.0.0"
    
    def test_no_context_section(self, config: Dict[str, Any]):
        """Test that context section was removed."""
        agent_config = config.get('agent', {})
        
        assert 'context' not in agent_config, \
            "Context section should be removed"
    
    def test_no_chunking_configuration(self, config: Dict[str, Any]):
        """Test that chunking configuration was removed."""
        config_str = yaml.dump(config)
        config_str_lower = config_str.lower()
    
        assert 'chunk' not in config_str_lower, \
            "Should not have chunking configuration"
    
        # Allow GITHUB_TOKEN but fail if any other token-related configuration exists
        config_without_github_token = config_str_lower.replace('github_token', '')
        assert 'token' not in config_without_github_token, \
            "Should not have token management (except GITHUB_TOKEN)"
    
    def test_no_fallback_strategies(self, config: Dict[str, Any]):
        """Test that fallback strategies were removed."""
        limits_config = config.get('limits', {})
        
        assert 'fallback' not in limits_config, \
            "Fallback strategies should be removed"
    
    def test_essential_config_preserved(self, config: Dict[str, Any]):
        """Test that essential configuration is preserved."""
        assert 'agent' in config, \
            "Should have agent section"
        assert 'monitoring' in config, \
            "Should have monitoring section"
        assert 'limits' in config, \
            "Should have limits section"
    
    def test_agent_enabled(self, config: Dict[str, Any]):
        """Test that agent is enabled."""
        agent_config = config.get('agent', {})
        enabled = agent_config.get('enabled', False)
        
        assert enabled is True, \
            "Agent should be enabled"


class TestWorkflowConsistency:
    """Test consistency across multiple workflows."""
    
    def test_consistent_python_version(self):
        """Test that Python version is consistent across workflows."""
        python_versions = {}
        
        if not WORKFLOWS_DIR.exists():
            pytest.skip("Workflows directory not found")
        
        for workflow_file in WORKFLOWS_DIR.glob("*.yml"):
            with open(workflow_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract python-version specifications
            if 'python-version' in content:
                # Simple regex to find version
                import re
                versions = re.findall(r"python-version:\s*['\"]?([0-9.]+)", content)
                if versions:
                    python_versions[workflow_file.name] = versions[0]
        
        if python_versions:
            # All should use same version or compatible versions
            versions_set = set(python_versions.values())
            assert len(versions_set) <= 2, \
                f"Should have at most 2 Python versions, found: {versions_set}"
    
    def test_consistent_action_versions(self):
        """Test that common actions use consistent versions."""
        checkout_versions = {}
        
        if not WORKFLOWS_DIR.exists():
            pytest.skip("Workflows directory not found")
        
        for workflow_file in WORKFLOWS_DIR.glob("*.yml"):
            try:
                with open(workflow_file, 'r', encoding='utf-8') as f:
                    workflow = yaml.safe_load(f)
                
                jobs = workflow.get('jobs', {})
                for job_name, job_config in jobs.items():
                    steps = job_config.get('steps', [])
                    
                    for step in steps:
                        if 'uses' in step:
                            uses = step['uses']
                            if 'checkout' in uses.lower():
                                checkout_versions[workflow_file.name] = uses
            except Exception:
                # Skip files that can't be parsed
                continue
        
        if checkout_versions:
            # Most checkouts should use v4
            v4_count = sum(1 for v in checkout_versions.values() if '@v4' in v)
            total_count = len(checkout_versions)
            
            assert v4_count >= total_count * 0.7, \
                "Most workflows should use checkout@v4"
    
    def test_consistent_permissions_model(self):
        """Test that workflows use consistent permissions model."""
        if not WORKFLOWS_DIR.exists():
            pytest.skip("Workflows directory not found")
        
        for workflow_file in WORKFLOWS_DIR.glob("*.yml"):
            try:
                with open(workflow_file, 'r', encoding='utf-8') as f:
                    workflow = yaml.safe_load(f)
                
                # Should have explicit permissions
                permissions = workflow.get('permissions')
                
                if permissions is not None:
                    # Should be a dict or string
                    assert isinstance(permissions, (dict, str)), \
                        f"{workflow_file.name} should have valid permissions format"
                    
                    if isinstance(permissions, dict):
                        # Should have reasonable permissions
                        assert len(permissions) > 0, \
                            f"{workflow_file.name} should have at least one permission"
            except Exception:
                # Skip files that can't be parsed
                continue


class TestRegressionPrevention:
    """Tests to prevent regression of common issues."""
    
    def test_no_yaml_syntax_errors(self):
        """Test that all workflow files have valid YAML syntax."""
        if not WORKFLOWS_DIR.exists():
            pytest.skip("Workflows directory not found")
        
        for workflow_file in WORKFLOWS_DIR.glob("*.yml"):
            try:
                with open(workflow_file, 'r', encoding='utf-8') as f:
                    yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"{workflow_file.name} has YAML syntax error: {e}")
    
    def test_no_duplicate_keys_in_workflows(self):
        """Test that workflows don't have duplicate keys."""
        if not WORKFLOWS_DIR.exists():
            pytest.skip("Workflows directory not found")
        
        for workflow_file in WORKFLOWS_DIR.glob("*.yml"):
            # This would fail in yaml.safe_load if there were duplicates
            # but we'll be explicit
            with open(workflow_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for obvious duplicate keys at top level
            lines = content.split('\n')
            top_level_keys = []
            
            for line in lines:
                if line and not line.startswith(' ') and not line.startswith('#'):
                    if ':' in line:
                        key = line.split(':')[0].strip().strip('"').strip("'")
                        if key:
                            top_level_keys.append(key)
            
            duplicates = [k for k in top_level_keys if top_level_keys.count(k) > 1]
            unique_dups = list(set(duplicates))
            
            assert len(unique_dups) == 0, \
                f"{workflow_file.name} has duplicate keys: {unique_dups}"
    
    def test_no_missing_required_fields(self):
        """Test that workflows have required fields."""
        if not WORKFLOWS_DIR.exists():
            pytest.skip("Workflows directory not found")
        
        required_fields = ['name', 'on', 'jobs']
        
        for workflow_file in WORKFLOWS_DIR.glob("*.yml"):
            try:
                with open(workflow_file, 'r', encoding='utf-8') as f:
                    workflow = yaml.safe_load(f)
                
                for field in required_fields:
                    assert field in workflow or f'"{field}"' in str(workflow.keys()), \
                        f"{workflow_file.name} missing required field: {field}"
            except Exception:
                # Skip files that can't be parsed
                continue