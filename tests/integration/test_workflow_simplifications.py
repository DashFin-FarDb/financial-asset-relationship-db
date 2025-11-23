"""
Comprehensive tests for workflow simplification changes.

This test module specifically validates the changes made in the current branch:
- Removal of complex context chunking from pr-agent.yml
- Simplification of greetings.yml messages
- Removal of config checks in label.yml
- Removal of credential checks in apisec-scan.yml
- Simplification of pr-agent-config.yml

These tests ensure the simplified workflows function correctly and that
removed complexity does not inadvertently reappear.
"""

import pytest
import yaml
from pathlib import Path
from typing import Any, Dict, List


class TestPRAgentWorkflowSimplification:
    """Test that pr-agent.yml has been properly simplified."""
    
    @pytest.fixture
    def pr_agent_workflow(self) -> Dict[str, Any]:
        """Load pr-agent.yml workflow."""
        workflow_path = Path(__file__).parent.parent.parent / '.github' / 'workflows' / 'pr-agent.yml'
        with open(workflow_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_no_context_chunking_dependencies(self, pr_agent_workflow: Dict[str, Any]):
        """
        Test that pr-agent workflow no longer installs context chunking dependencies.
        
        The simplified workflow should not install PyYAML or tiktoken for context management.
        """
        for job_name, job in pr_agent_workflow.get('jobs', {}).items():
            for step in job.get('steps', []):
                # Check step name
                step_name = step.get('name', '')
                run_command = step.get('run', '')
                
                # Should not have steps specifically for context chunking
                assert 'chunking' not in step_name.lower(), (
                    f"Job '{job_name}' should not have context chunking steps"
                )
                assert 'tiktoken' not in step_name.lower(), (
                    f"Job '{job_name}' should not reference tiktoken"
                )
                
                # Should not install tiktoken in run commands
                assert 'tiktoken' not in run_command.lower(), (
                    f"Job '{job_name}' should not install tiktoken dependency"
                )
    
    def test_no_context_fetching_step(self, pr_agent_workflow: Dict[str, Any]):
        """
        Test that the complex 'Fetch PR Context with Chunking' step has been removed.
        
        The workflow should use simple comment parsing instead.
        """
        for job_name, job in pr_agent_workflow.get('jobs', {}).items():
            step_names = [step.get('name', '') for step in job.get('steps', [])]
            
            # Should not have the old complex context fetching step
            assert not any('Fetch PR Context with Chunking' in name for name in step_names), (
                f"Job '{job_name}' should not have 'Fetch PR Context with Chunking' step"
            )
            
            # Should not have context file references
            for step in job.get('steps', []):
                run_command = step.get('run', '')
                assert 'pr_context.json' not in run_command, (
                    f"Job '{job_name}' should not reference pr_context.json files"
                )
                assert 'pr_context_chunked.json' not in run_command, (
                    f"Job '{job_name}' should not reference pr_context_chunked.json files"
                )
    
    def test_has_simplified_comment_parsing(self, pr_agent_workflow: Dict[str, Any]):
        """
        Test that workflow uses simplified comment parsing.
        
        Should have a 'Parse PR Review Comments' step that directly extracts action items.
        """
        for job_name, job in pr_agent_workflow.get('jobs', {}).items():
            steps = job.get('steps', [])
            step_names = [step.get('name', '') for step in steps]
            
            # Should have the simplified parsing step
            has_parse_comments = any('Parse PR Review Comments' in name for name in step_names)
            
            if 'pr-agent' in job_name.lower() or any('review' in name.lower() for name in step_names):
                assert has_parse_comments, (
                    f"Job '{job_name}' should have simplified 'Parse PR Review Comments' step"
                )
    
    def test_no_duplicate_setup_python_steps(self, pr_agent_workflow: Dict[str, Any]):
        """
        Regression test: Ensure no duplicate Setup Python steps exist.
        
        This validates the fix for the duplicate YAML key issue that was corrected.
        """
        for job_name, job in pr_agent_workflow.get('jobs', {}).items():
            steps = job.get('steps', [])
            
            # Count Setup Python steps
            setup_python_count = sum(
                1 for step in steps
                if step.get('name') == 'Setup Python'
            )
            
            assert setup_python_count <= 1, (
                f"Job '{job_name}' has {setup_python_count} 'Setup Python' steps. "
                "Should have at most one."
            )
            
            # Count setup-python action usage
            setup_python_action_count = sum(
                1 for step in steps
                if 'setup-python' in step.get('uses', '').lower()
            )
            
            assert setup_python_action_count <= 1, (
                f"Job '{job_name}' uses setup-python action {setup_python_action_count} times. "
                "Should use it at most once."
            )
    
    def test_no_context_size_checking(self, pr_agent_workflow: Dict[str, Any]):
        """
        Test that workflow no longer checks context size.
        
        The simplified workflow should not have logic to measure or compare context sizes.
        """
        for job_name, job in pr_agent_workflow.get('jobs', {}).items():
            for step in job.get('steps', []):
                run_command = step.get('run', '')
                
                # Should not have context size checking
                assert 'CONTEXT_SIZE' not in run_command, (
                    f"Job '{job_name}' should not check CONTEXT_SIZE"
                )
                assert 'wc -c' not in run_command or 'pr_context' not in run_command, (
                    f"Job '{job_name}' should not measure context file size"
                )
                assert 'context_size' not in run_command, (
                    f"Job '{job_name}' should not reference context_size variable"
                )
    
    def test_no_chunking_script_references(self, pr_agent_workflow: Dict[str, Any]):
        """
        Test that workflow does not reference the deleted context_chunker.py script.
        """
        workflow_str = yaml.dump(pr_agent_workflow)
        
        assert 'context_chunker.py' not in workflow_str, (
            "Workflow should not reference deleted context_chunker.py script"
        )
        assert '.github/scripts/context_chunker' not in workflow_str, (
            "Workflow should not reference context_chunker in any path"
        )
    
    def test_simplified_output_variables(self, pr_agent_workflow: Dict[str, Any]):
        """
        Test that step outputs have been simplified.
        
        Should not have outputs related to context chunking like 'chunked' or 'context_file'.
        """
        for job_name, job in pr_agent_workflow.get('jobs', {}).items():
            for step in job.get('steps', []):
                if 'id' in step:
                    run_command = step.get('run', '')
                    
                    # Should not set chunking-related outputs
                    assert 'chunked=true' not in run_command and 'chunked=false' not in run_command, (
                        f"Step '{step.get('name')}' in job '{job_name}' should not set 'chunked' output"
                    )
                    assert 'context_file=' not in run_command, (
                        f"Step '{step.get('name')}' in job '{job_name}' should not set 'context_file' output"
                    )


class TestGreetingsWorkflowSimplification:
    """Test that greetings.yml has been simplified."""
    
    @pytest.fixture
    def greetings_workflow(self) -> Dict[str, Any]:
        """Load greetings.yml workflow."""
        workflow_path = Path(__file__).parent.parent.parent / '.github' / 'workflows' / 'greetings.yml'
        with open(workflow_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_uses_generic_messages(self, greetings_workflow: Dict[str, Any]):
        """
        Test that greetings workflow uses generic placeholder messages.
        
        The custom detailed welcome messages should be replaced with simple placeholders.
        """
        for job in greetings_workflow.get('jobs', {}).values():
            for step in job.get('steps', []):
                if 'first-interaction' in step.get('uses', ''):
                    issue_message = step.get('with', {}).get('issue-message', '')
                    pr_message = step.get('with', {}).get('pr-message', '')
                    
                    # Messages should be simple placeholders
                    assert len(issue_message) < 200, (
                        "Issue message should be short placeholder, not detailed custom message"
                    )
                    assert len(pr_message) < 200, (
                        "PR message should be short placeholder, not detailed custom message"
                    )
                    
                    # Should not contain custom project-specific content
                    assert 'Financial Asset Relationship Database' not in issue_message, (
                        "Should not have project-specific content in issue message"
                    )
                    assert 'Financial Asset Relationship Database' not in pr_message, (
                        "Should not have project-specific content in PR message"
                    )
    
    def test_no_markdown_formatting_in_messages(self, greetings_workflow: Dict[str, Any]):
        """
        Test that greeting messages don't have complex markdown formatting.
        
        Simplified messages should not have bullets, headers, or complex structure.
        """
        for job in greetings_workflow.get('jobs', {}).values():
            for step in job.get('steps', []):
                if 'first-interaction' in step.get('uses', ''):
                    issue_message = step.get('with', {}).get('issue-message', '')
                    pr_message = step.get('with', {}).get('pr-message', '')
                    
                    # Should not have markdown headers
                    assert '**' not in issue_message or issue_message.count('**') < 4, (
                        "Issue message should not have extensive markdown formatting"
                    )
                    assert '**' not in pr_message or pr_message.count('**') < 4, (
                        "PR message should not have extensive markdown formatting"
                    )
                    
                    # Should not have bullet lists
                    assert issue_message.count('- ') < 3, (
                        "Issue message should not have extensive bullet lists"
                    )
                    assert pr_message.count('- ') < 3, (
                        "PR message should not have extensive bullet lists"
                    )


class TestLabelerWorkflowSimplification:
    """Test that label.yml has been simplified."""
    
    @pytest.fixture
    def labeler_workflow(self) -> Dict[str, Any]:
        """Load label.yml workflow."""
        workflow_path = Path(__file__).parent.parent.parent / '.github' / 'workflows' / 'label.yml'
        with open(workflow_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_no_config_existence_check(self, labeler_workflow: Dict[str, Any]):
        """
        Test that labeler workflow no longer checks for config file existence.
        
        The workflow should directly use the labeler action without conditional checks.
        """
        for job in labeler_workflow.get('jobs', {}).values():
            step_names = [step.get('name', '') for step in job.get('steps', [])]
            
            # Should not have config checking steps
            assert not any('Check for labeler config' in name for name in step_names), (
                "Should not have 'Check for labeler config' step"
            )
            assert not any('check-config' in step.get('id', '') for step in job.get('steps', [])), (
                "Should not have 'check-config' step id"
            )
    
    def test_no_conditional_labeler_execution(self, labeler_workflow: Dict[str, Any]):
        """
        Test that labeler action runs unconditionally.
        
        Should not have 'if' conditions on the labeler step based on config existence.
        """
        for job in labeler_workflow.get('jobs', {}).values():
            for step in job.get('steps', []):
                if 'labeler' in step.get('uses', ''):
                    step_if = step.get('if', '')
                    
                    # Should not have config existence condition
                    assert 'config_exists' not in step_if, (
                        "Labeler step should not be conditional on config_exists"
                    )
                    assert not step_if or step_if == 'always()', (
                        "Labeler step should run unconditionally or always"
                    )
    
    def test_no_skipped_message_step(self, labeler_workflow: Dict[str, Any]):
        """
        Test that there's no step to report labeler being skipped.
        """
        for job in labeler_workflow.get('jobs', {}).values():
            step_names = [step.get('name', '') for step in job.get('steps', [])]
            
            assert not any('Labeler skipped' in name for name in step_names), (
                "Should not have 'Labeler skipped' reporting step"
            )
            assert not any('skipped' in name.lower() for name in step_names), (
                "Should not have steps related to skipping labeler"
            )
    
    def test_no_checkout_step(self, labeler_workflow: Dict[str, Any]):
        """
        Test that labeler workflow doesn't checkout repository.
        
        The simplified workflow should directly use the labeler action without checkout.
        """
        for job in labeler_workflow.get('jobs', {}).values():
            step_names = [step.get('name', '') for step in job.get('steps', [])]
            uses_actions = [step.get('uses', '') for step in job.get('steps', [])]
            
            # Should not checkout since config check was removed
            assert not any('Checkout' in name for name in step_names), (
                "Should not have checkout step in simplified labeler workflow"
            )
            assert not any('checkout' in uses for uses in uses_actions), (
                "Should not use checkout action in simplified labeler workflow"
            )


class TestAPISecWorkflowSimplification:
    """Test that apisec-scan.yml has been simplified."""
    
    @pytest.fixture
    def apisec_workflow(self) -> Dict[str, Any]:
        """Load apisec-scan.yml workflow."""
        workflow_path = Path(__file__).parent.parent.parent / '.github' / 'workflows' / 'apisec-scan.yml'
        with open(workflow_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_no_credential_check_step(self, apisec_workflow: Dict[str, Any]):
        """
        Test that APIsec workflow no longer checks for credentials before running.
        
        The workflow should directly run the scan without checking secret availability.
        """
        for job_name, job in apisec_workflow.get('jobs', {}).items():
            step_names = [step.get('name', '') for step in job.get('steps', [])]
            
            # Should not have credential checking step
            assert not any('Check for APIsec credentials' in name for name in step_names), (
                f"Job '{job_name}' should not have 'Check for APIsec credentials' step"
            )
            assert not any('credential' in name.lower() for name in step_names), (
                f"Job '{job_name}' should not have credential checking steps"
            )
    
    def test_no_conditional_job_execution(self, apisec_workflow: Dict[str, Any]):
        """
        Test that APIsec scan job no longer has credential-based conditional execution.
        
        Job should not have 'if' condition checking for secret availability.
        """
        for job_name, job in apisec_workflow.get('jobs', {}).items():
            job_if = job.get('if', '')
            
            # Should not check for secrets in job condition
            assert 'apisec_username' not in job_if, (
                f"Job '{job_name}' should not have conditional execution based on apisec_username"
            )
            assert 'apisec_password' not in job_if, (
                f"Job '{job_name}' should not have conditional execution based on apisec_password"
            )
            assert 'secrets.' not in job_if or 'secrets.GITHUB_TOKEN' in job_if, (
                f"Job '{job_name}' should not check for APIsec secrets in job condition"
            )
    
    def test_no_skip_warning_messages(self, apisec_workflow: Dict[str, Any]):
        """
        Test that there are no steps warning about skipped scans.
        """
        for job in apisec_workflow.get('jobs', {}).values():
            for step in job.get('steps', []):
                run_command = step.get('run', '')
                
                # Should not have warning messages about skipping
                assert 'credentials not configured' not in run_command.lower(), (
                    "Should not have messages about credentials not configured"
                )
                assert 'Skipping scan' not in run_command, (
                    "Should not have messages about skipping scan"
                )
                assert 'Register at' not in run_command, (
                    "Should not have registration instructions"
                )


class TestPRAgentConfigSimplification:
    """Test that pr-agent-config.yml has been simplified."""
    
    @pytest.fixture
    def pr_agent_config(self) -> Dict[str, Any]:
        """Load pr-agent-config.yml."""
        config_path = Path(__file__).parent.parent.parent / '.github' / 'pr-agent-config.yml'
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_no_context_management_section(self, pr_agent_config: Dict[str, Any]):
        """
        Test that config no longer has complex context management section.
        
        The agent.context section with chunking and summarization should be removed.
        """
        agent = pr_agent_config.get('agent', {})
        context = agent.get('context', {})
        
        # Should not have complex context configuration
        if context:
            assert 'max_tokens' not in context, (
                "Config should not have max_tokens in context section"
            )
            assert 'chunk_size' not in context, (
                "Config should not have chunk_size in context section"
            )
            assert 'overlap_tokens' not in context, (
                "Config should not have overlap_tokens in context section"
            )
            assert 'summarization_threshold' not in context, (
                "Config should not have summarization_threshold in context section"
            )
            assert 'chunking' not in context, (
                "Config should not have chunking subsection"
            )
            assert 'summarization' not in context, (
                "Config should not have summarization subsection"
            )
    
    def test_no_fallback_strategies(self, pr_agent_config: Dict[str, Any]):
        """
        Test that limits section doesn't have complex fallback strategies.
        """
        limits = pr_agent_config.get('limits', {})
        
        if limits:
            assert 'fallback' not in limits, (
                "Config should not have fallback subsection in limits"
            )
            assert 'on_context_overflow' not in str(limits).lower(), (
                "Config should not reference context overflow handling"
            )
            assert 'priority_order' not in limits, (
                "Config should not have priority_order for chunking"
            )
    
    def test_no_chunking_limits(self, pr_agent_config: Dict[str, Any]):
        """
        Test that config doesn't have chunking-specific limits.
        """
        limits = pr_agent_config.get('limits', {})
        
        if limits:
            assert 'max_files_per_chunk' not in limits, (
                "Config should not have max_files_per_chunk"
            )
            assert 'max_diff_lines' not in limits, (
                "Config should not have max_diff_lines for chunking"
            )
            assert 'max_comment_length' not in limits, (
                "Config should not have max_comment_length for chunking"
            )
    
    def test_version_downgraded(self, pr_agent_config: Dict[str, Any]):
        """
        Test that agent version has been reset to 1.0.0.
        
        With simplification, version should be 1.0.0 not 1.1.0.
        """
        agent = pr_agent_config.get('agent', {})
        version = agent.get('version', '')
        
        assert version == '1.0.0', (
            f"Agent version should be '1.0.0' after simplification, got '{version}'"
        )
    
    def test_config_structure_remains_valid(self, pr_agent_config: Dict[str, Any]):
        """
        Test that despite simplification, core config structure remains valid.
        """
        # Should still have essential sections
        assert 'agent' in pr_agent_config, "Config should still have agent section"
        assert 'monitoring' in pr_agent_config, "Config should still have monitoring section"
        
        # Agent should have basic fields
        agent = pr_agent_config.get('agent', {})
        assert 'name' in agent, "Agent should have name"
        assert 'version' in agent, "Agent should have version"
        assert 'enabled' in agent, "Agent should have enabled flag"


class TestDeletedScriptFilesVerification:
    """Verify that script files meant to be deleted are actually gone."""
    
    def test_context_chunker_script_deleted(self):
        """Test that .github/scripts/context_chunker.py has been deleted."""
        chunker_script = Path(__file__).parent.parent.parent / '.github' / 'scripts' / 'context_chunker.py'
        
        assert not chunker_script.exists(), (
            ".github/scripts/context_chunker.py should be deleted"
        )
    
    def test_scripts_readme_deleted(self):
        """Test that .github/scripts/README.md has been deleted."""
        scripts_readme = Path(__file__).parent.parent.parent / '.github' / 'scripts' / 'README.md'
        
        assert not scripts_readme.exists(), (
            ".github/scripts/README.md should be deleted"
        )
    
    def test_scripts_directory_empty_or_gone(self):
        """Test that .github/scripts directory is empty or doesn't exist."""
        scripts_dir = Path(__file__).parent.parent.parent / '.github' / 'scripts'
        
        if scripts_dir.exists():
            # If it exists, should be empty or only contain __pycache__
            contents = list(scripts_dir.iterdir())
            non_cache = [f for f in contents if '__pycache__' not in str(f)]
            
            assert len(non_cache) == 0, (
                f".github/scripts directory should be empty, found: {non_cache}"
            )


class TestWorkflowRegressionPrevention:
    """Regression tests to prevent reintroduction of complexity."""
    
    def test_no_workflow_references_deleted_files(self):
        """
        Test that no workflow file references the deleted files.
        """
        workflows_dir = Path(__file__).parent.parent.parent / '.github' / 'workflows'
        
import os
import pytest
import warnings
import yaml
from pathlib import Path
from typing import Dict, Any, List
            
            # Should not reference deleted files
            assert 'context_chunker.py' not in content, (
                f"{workflow_file.name} should not reference deleted context_chunker.py"
            )
            assert '.github/scripts/context_chunker' not in content, (
                f"{workflow_file.name} should not reference context_chunker path"
            )
    
    def test_no_yaml_duplicate_keys_anywhere(self):
        """
        Test that no workflow file has duplicate YAML keys.
        
        This is a comprehensive regression test for the duplicate key issue.
        """
        workflows_dir = Path(__file__).parent.parent.parent / '.github' / 'workflows'
        
        workflow_files = list(workflows_dir.glob('*.yml')) + list(workflows_dir.glob('*.yaml'))
        for workflow_file in workflow_files:
            duplicates = self._check_duplicate_keys(workflow_file)
            
            assert len(duplicates) == 0, (
                f"{workflow_file.name} contains duplicate YAML keys: {duplicates}"
            )
    
    def _check_duplicate_keys(self, file_path: Path) -> List[str]:
        """Helper to detect duplicate keys in YAML file."""
        duplicates = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        class DuplicateKeySafeLoader(yaml.SafeLoader):
            pass
        
        def constructor_with_dup_check(loader, node):
            mapping = {}
            for key_node, value_node in node.value:
                key = loader.construct_object(key_node, deep=False)
                if key in mapping:
                    duplicates.append(key)
                mapping[key] = loader.construct_object(value_node, deep=False)
            return mapping
        
        DuplicateKeySafeLoader.add_constructor(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            constructor_with_dup_check
        )
        
        try:
            yaml.load(content, Loader=DuplicateKeySafeLoader)
        except yaml.YAMLError:
            pass
        
        return duplicates
    
    def test_workflow_files_remain_valid_yaml(self):
        """
        Test that all workflow files are still valid YAML after simplification.
        """
        workflows_dir = Path(__file__).parent.parent.parent / '.github' / 'workflows'
        
        workflow_files = list(workflows_dir.glob('*.yml')) + list(workflows_dir.glob('*.yaml'))
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                try:
                    yaml.safe_load(f)
                except yaml.YAMLError as e:
                    pytest.fail(f"{workflow_file.name} contains invalid YAML: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])