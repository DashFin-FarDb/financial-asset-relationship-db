"""
Additional edge case tests for workflow simplification changes.

This module tests edge cases, boundary conditions, and potential regressions
that could occur from the workflow simplification changes.
"""

import pytest
import yaml
WORKFLOWS_DIR = Path(__file__).parent.parent.parent / ".github" / "workflows"

def load_workflow(workflow_name: str) -> Dict[str, Any]:
    """Load a workflow file."""
    workflow_path = WORKFLOWS_DIR / workflow_name
    if not workflow_path.exists():
        pytest.skip(f"{workflow_name} not found")
    
    with open(workflow_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)
from typing import Dict, Any, List


WORKFLOWS_DIR = Path(__file__).parent.parent.parent / ".github" / "workflows"
    with open(workflow_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

WORKFLOWS_DIR = Path(__file__).parent.parent.parent / ".github" / "workflows"
from pathlib import Path
from typing import Dict, Any, List
import re
import pytest
import yaml

WORKFLOWS_DIR = Path(__file__).parent.parent.parent / ".github" / "workflows"
CONFIG_FILE = Path(__file__).parent.parent.parent / "pr-agent-config.yml"

def load_workflow(workflow_name: str) -> Dict[str, Any]:
    """Load a workflow file."""
    workflow_path = WORKFLOWS_DIR / workflow_name
    if not workflow_path.exists():
        pytest.skip(f"{workflow_name} not found")
    with open(workflow_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)
        
    def test_agent_enabled(self, config: Dict[str, Any]):
        """Test that agent is enabled."""
        agent_config = config.get('agent', {})
        enabled = agent_config.get('enabled', True)
        assert enabled is True, "Agent should be enabled"
    
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
# Duplicate and malformed TestWorkflowConsistency block removed
import re

class TestWorkflowConsistency:
    """Test consistency across multiple workflows."""
    
    PY_VERSION_PATTERN = re.compile(r'python-version\s*:\s*["\']?([0-9.]+)["\']?')
        
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
class TestWorkflowConsistency:
    """Test consistency across multiple workflows."""

    def test_consistent_python_version(self):
        """Ensure Python versions are consistent across workflows."""
        python_versions = {}

        if not WORKFLOWS_DIR.exists():
            pytest.skip("Workflows directory not found")

        for workflow_file in WORKFLOWS_DIR.glob("*.yml"):
            with open(workflow_file, 'r', encoding='utf-8') as f:
                content = f.read()

            versions = PY_VERSION_PATTERN.findall(content)
            if versions:
                python_versions[workflow_file.name] = versions[0]

        if python_versions:
            versions_set = set(python_versions.values())
            assert len(versions_set) <= 2, \
                f"Should have at most 2 Python versions, found: {versions_set}"

    def test_consistent_action_versions(self):
        """Ensure common actions (e.g., checkout) use consistent versions."""
        checkout_versions = {}

        if not WORKFLOWS_DIR.exists():
            pytest.skip("Workflows directory not found")

        for workflow_file in WORKFLOWS_DIR.glob("*.yml"):
            try:
                with open(workflow_file, 'r', encoding='utf-8') as f:
                    workflow = yaml.safe_load(f)

                jobs = workflow.get('jobs', {}) if isinstance(workflow, dict) else {}
                for job_config in jobs.values():
                    steps = job_config.get('steps', [])
                    for step in steps:
                        if isinstance(step, dict) and 'uses' in step:
                            uses = step['uses']
                            if isinstance(uses, str) and 'checkout' in uses.lower():
                                checkout_versions[workflow_file.name] = uses
            except Exception:
                continue

        if checkout_versions:
            v4_count = sum(1 for v in checkout_versions.values() if '@v4' in v)
            total_count = len(checkout_versions)
            assert v4_count >= total_count * 0.7, "Most workflows should use checkout@v4"
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
        """Test that workflows don't have duplicate keys (robust, nested-safe)."""
        if not WORKFLOWS_DIR.exists():
            pytest.skip("Workflows directory not found")
        try:
            from ruamel.yaml import YAML
            from ruamel.yaml.constructor import DuplicateKeyError
        except Exception:
            pytest.skip("ruamel.yaml not available; skipping robust duplicate key check")
    
        yaml_parser = YAML(typ='safe')
        # ruamel.yaml raises DuplicateKeyError on duplicates by default for typ='safe'
        for workflow_file in WORKFLOWS_DIR.glob("*.yml"):
            with open(workflow_file, 'r', encoding='utf-8') as f:
                try:
                    yaml_parser.load(f)
                except DuplicateKeyError as e:
                    pytest.fail(f"{workflow_file.name} has duplicate YAML keys: {e}")
    

                if python_versions:
                    # All should use same version or compatible versions
                    versions_set = set(python_versions.values())
                    assert len(versions_set) <= 2, \
                        f"Should have at most 2 Python versions, found: {versions_set}"
