"""
Comprehensive tests validating the simplified GitHub Actions workflows.

This module tests the changes made to simplify workflows by removing
context chunking, conditional checks, and other complexity while ensuring
core functionality remains intact.
"""

import pytest
import yaml
from pathlib import Path
from typing import Any, Dict


WORKFLOWS_DIR = Path(__file__).parent.parent.parent / ".github" / "workflows"
CONFIG_FILE = Path(__file__).parent.parent.parent / ".github" / "pr-agent-config.yml"


@pytest.fixture
def pr_agent_workflow() -> Dict[str, Any]:
    """Load the pr-agent.yml workflow file."""
    workflow_path = WORKFLOWS_DIR / "pr-agent.yml"
    with open(workflow_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


@pytest.fixture
def pr_agent_config() -> Dict[str, Any]:
    """Load the pr-agent-config.yml configuration file."""
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


@pytest.fixture
def apisec_workflow() -> Dict[str, Any]:
    """Load the apisec-scan.yml workflow file."""
    workflow_path = WORKFLOWS_DIR / "apisec-scan.yml"
    with open(workflow_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


@pytest.fixture
def greetings_workflow() -> Dict[str, Any]:
    """Load the greetings.yml workflow file."""
    workflow_path = WORKFLOWS_DIR / "greetings.yml"
    with open(workflow_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


@pytest.fixture
def label_workflow() -> Dict[str, Any]:
    """Load the label.yml workflow file."""
    workflow_path = WORKFLOWS_DIR / "label.yml"
    with open(workflow_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


class TestPRAgentWorkflowSimplification:
    """Test suite for the simplified PR Agent workflow."""
    
    def test_no_duplicate_setup_python_key(self, pr_agent_workflow: Dict[str, Any]):
        """Verify that the duplicate 'Setup Python' step has been removed."""
        job = pr_agent_workflow['jobs']['pr-agent-trigger']
        setup_python_steps = [
            step for step in job['steps']
            if 'setup' in step.get('name', '').lower() and 'python' in step.get('name', '').lower()
        ]
        assert len(setup_python_steps) == 1, "Should have exactly one 'Setup Python' step"
    
    def test_no_context_chunking_logic(self, pr_agent_workflow: Dict[str, Any]):
        """Verify that context chunking logic has been removed."""
        job = pr_agent_workflow['jobs']['pr-agent-trigger']
        step_names = [step.get('name', '') for step in job['steps']]
        
        # Should not have "Fetch PR Context with Chunking" step
        assert 'Fetch PR Context with Chunking' not in step_names
        
        # Should have simplified "Parse PR Review Comments" step instead
        assert 'Parse PR Review Comments' in step_names
    
    def test_parse_comments_step_simplified(self, pr_agent_workflow: Dict[str, Any]):
        """Verify Parse PR Review Comments step is simplified."""
        job = pr_agent_workflow['jobs']['pr-agent-trigger']
        parse_step = None
        
        for step in job['steps']:
            if step.get('name') == 'Parse PR Review Comments':
                parse_step = step
                break
        
        assert parse_step is not None, "Parse PR Review Comments step should exist"
        
        # Check that the script doesn't reference chunking
        script = parse_step.get('run', '')
        assert 'context_chunker.py' not in script
        assert 'chunked' not in script.lower() and 'chunk' not in script.lower()
        assert 'CONTEXT_SIZE' not in script
    
    def test_no_pyyaml_installation_in_dependencies(self, pr_agent_workflow: Dict[str, Any]):
        """Verify PyYAML installation has been removed from workflow."""
        job = pr_agent_workflow['jobs']['pr-agent-trigger']
        install_step = None
        
        for step in job['steps']:
            if step.get('name') == 'Install Python dependencies':
                install_step = step
                break
        
        assert install_step is not None
        script = install_step.get('run', '')
        
        # Should not install PyYAML or tiktoken in workflow
        assert 'pyyaml' not in script.lower()
        assert 'tiktoken' not in script.lower()
    
    def test_comment_output_simplified(self, pr_agent_workflow: Dict[str, Any]):
        """Verify PR comment output no longer references chunking."""
        job = pr_agent_workflow['jobs']['pr-agent-trigger']
        comment_step = None
        
        for step in job['steps']:
            if step.get('name') == 'Post PR Comment':
                comment_step = step
                break
        
        assert comment_step is not None
        script = comment_step.get('run', '')
        
        # Should not reference context size or chunking in output
        assert 'context_size' not in script.lower()
        assert 'chunked' not in script.lower()
        assert 'Context chunking applied' not in script
    
    def test_workflow_still_has_required_steps(self, pr_agent_workflow: Dict[str, Any]):
        """Verify essential workflow steps remain after simplification."""
        job = pr_agent_workflow['jobs']['pr-agent-trigger']
        step_names = [step.get('name', '') for step in job['steps']]
        
        required_steps = [
            'Checkout',
            'Setup Python',
            'Setup Node.js',
            'Install Python dependencies',
            'Parse PR Review Comments',
            'Run Python Linting',
            'Run Frontend Tests',
            'Post PR Comment'
        ]
        
        for required in required_steps:
            assert required in step_names, f"Required step '{required}' is missing"
    
    def test_action_items_output_preserved(self, pr_agent_workflow: Dict[str, Any]):
        """Verify action items extraction still works."""
        job = pr_agent_workflow['jobs']['pr-agent-trigger']
        parse_step = None
        
        for step in job['steps']:
            if step.get('name') == 'Parse PR Review Comments':
                parse_step = step
                break
        
        assert parse_step is not None
        script = parse_step.get('run', '')
        
        # Should still extract action items
        assert 'ACTION_ITEMS' in script
        assert 'action_items' in script
        assert 'GITHUB_OUTPUT' in script


class TestPRAgentConfigSimplification:
    """Test suite for the simplified PR Agent configuration."""
    
    def test_version_downgraded_to_1_0_0(self, pr_agent_config: Dict[str, Any]):
        """Verify version is back to 1.0.0 after removing context chunking."""
        assert pr_agent_config['agent']['version'] == '1.0.0'
    
    def test_no_context_configuration(self, pr_agent_config: Dict[str, Any]):
        """Verify context chunking configuration has been removed."""
        assert 'context' not in pr_agent_config.get('agent', {})
    
    def test_no_chunking_limits(self, pr_agent_config: Dict[str, Any]):
        """Verify chunking-related limits have been removed."""
        limits = pr_agent_config.get('limits', {})
        
        assert 'max_files_per_chunk' not in limits
        assert 'max_diff_lines' not in limits
        assert 'max_comment_length' not in limits
        assert 'fallback' not in limits
    
    def test_core_config_preserved(self, pr_agent_config: Dict[str, Any]):
        """Verify essential configuration remains."""
        assert 'agent' in pr_agent_config
        assert 'monitoring' in pr_agent_config
        assert 'comment_parsing' in pr_agent_config
        assert 'actions' in pr_agent_config
        
        # Check agent basics
        agent = pr_agent_config['agent']
        assert agent['name'] == 'Financial DB PR Agent'
        assert agent['enabled'] is True
    
    def test_monitoring_settings_intact(self, pr_agent_config: Dict[str, Any]):
        """Verify monitoring configuration is unchanged."""
        monitoring = pr_agent_config['monitoring']
        assert 'check_interval' in monitoring
        assert 'max_retries' in monitoring
        assert 'timeout' in monitoring
    
    def test_comment_parsing_intact(self, pr_agent_config: Dict[str, Any]):
        """Verify comment parsing configuration is unchanged."""
        parsing = pr_agent_config['comment_parsing']
        assert 'triggers' in parsing
        assert 'ignore_patterns' in parsing
        assert 'priority_keywords' in parsing


class TestAPISecWorkflowSimplification:
    """Test suite for the simplified APIsec workflow."""
    
    def test_no_conditional_skip(self, apisec_workflow: Dict[str, Any]):
        """Verify conditional credential check has been removed."""
        job = apisec_workflow['jobs']['Trigger_APIsec_scan']
        
        # Should not have 'if' condition checking for secrets
        assert 'if' not in job or 'apisec_username' not in str(job.get('if', ''))
    
    def test_no_credential_check_step(self, apisec_workflow: Dict[str, Any]):
        """Verify credential validation step has been removed."""
        job = apisec_workflow['jobs']['Trigger_APIsec_scan']
        step_names = [step.get('name', '') for step in job['steps']]
        
        assert 'Check for APIsec credentials' not in step_names
    
    def test_apisec_scan_step_preserved(self, apisec_workflow: Dict[str, Any]):
        """Verify main APIsec scan step is still present."""
        job = apisec_workflow['jobs']['Trigger_APIsec_scan']
        step_names = [step.get('name', '') for step in job['steps']]
        
        assert 'APIsec scan' in step_names
    
    def test_workflow_triggers_unchanged(self, apisec_workflow: Dict[str, Any]):
        """Verify workflow triggers remain the same."""
        assert 'on' in apisec_workflow
        triggers = apisec_workflow['on']
        
        assert 'push' in triggers
        assert 'pull_request' in triggers
        assert 'schedule' in triggers


class TestGreetingsWorkflowSimplification:
    """Test suite for the simplified Greetings workflow."""
    
    def test_simple_messages_only(self, greetings_workflow: Dict[str, Any]):
        """Verify custom welcome messages have been replaced with simple ones."""
        job = greetings_workflow['jobs']['greeting']
        
        for step in job['steps']:
            if 'first-interaction' in step.get('uses', ''):
                issue_msg = step['with'].get('issue-message', '')
                pr_msg = step['with'].get('pr-message', '')
                
                # Should have simple generic messages
                assert len(issue_msg) < 100, "Issue message should be simple"
                assert len(pr_msg) < 100, "PR message should be simple"
                
                # Should not have elaborate formatting
                assert '##' not in issue_msg
                assert '##' not in pr_msg
                assert '**' not in issue_msg
                assert '**' not in pr_msg


class TestLabelWorkflowSimplification:
    """Test suite for the simplified Label workflow."""
    
    def test_no_config_check(self, label_workflow: Dict[str, Any]):
        """Verify labeler config existence check has been removed."""
        job = label_workflow['jobs']['label']
        step_names = [step.get('name', '') for step in job['steps']]
        
        assert 'Check for labeler config' not in step_names
        assert 'Labeler skipped' not in step_names
    
    def test_no_conditional_labeler(self, label_workflow: Dict[str, Any]):
        """Verify labeler step no longer has conditional execution."""
        job = label_workflow['jobs']['label']
        
        for step in job['steps']:
            if 'labeler' in step.get('uses', ''):
                # Should not have 'if' condition
                assert 'if' not in step
    
    def test_no_checkout_step(self, label_workflow: Dict[str, Any]):
        """Verify unnecessary checkout step has been removed."""
        job = label_workflow['jobs']['label']
        step_names = [step.get('name', '') for step in job['steps']]
        
        assert 'Checkout repository' not in step_names
    
    def test_direct_labeler_execution(self, label_workflow: Dict[str, Any]):
        """Verify labeler action is called directly."""
        job = label_workflow['jobs']['label']
        
        # Should only have the labeler step
        assert len(job['steps']) == 1
        assert 'labeler' in job['steps'][0].get('uses', '')


class TestWorkflowConsistency:
    """Test suite for overall workflow consistency after simplification."""
    
    def test_all_workflows_valid_yaml(self):
        """Verify all workflow files are still valid YAML."""
        workflow_files = list(WORKFLOWS_DIR.glob("*.yml"))
        
        for wf_file in workflow_files:
            with open(wf_file, 'r', encoding='utf-8') as f:
                try:
                    try:
                        content = f.read()
                        yaml.safe_load(content)
                    except yaml.YAMLError as e:
                        lines_preview = "\n".join(content.splitlines()[:10])
                        pytest.fail(f"Invalid YAML in {wf_file.name}: {e}\nFirst 10 lines:\n{lines_preview}")
    
    def test_no_broken_references(self, pr_agent_workflow: Dict[str, Any]):
        """Verify no steps reference removed features."""
        job = pr_agent_workflow['jobs']['pr-agent-trigger']
        
        for step in job['steps']:
            script = step.get('run', '')
            
            # Should not reference removed scripts
            assert '.github/scripts/context_chunker.py' not in script
            
            # Should not reference removed outputs
            assert 'steps.fetch-context.outputs' not in script
    
    def test_output_references_updated(self, pr_agent_workflow: Dict[str, Any]):
        """Verify step output references have been updated."""
        job = pr_agent_workflow['jobs']['pr-agent-trigger']
        comment_step = None
        
        for step in job['steps']:
            if step.get('name') == 'Post PR Comment':
                comment_step = step
                break
        
        assert comment_step is not None
        script = comment_step.get('run', '')
        
        # Should reference parse-comments step, not fetch-context
        assert 'steps.parse-comments.outputs.action_items' in script
        assert 'steps.fetch-context' not in script


class TestRemovedFilesNotReferenced:
    """Test suite ensuring removed files are not referenced anywhere."""
    
    def test_no_labeler_yml_references(self, pr_agent_workflow: Dict[str, Any]):
        """Verify no references to removed labeler.yml."""
        workflow_str = yaml.dump(pr_agent_workflow)
        assert 'labeler.yml' not in workflow_str
    
    def test_no_context_chunker_references(self, pr_agent_workflow: Dict[str, Any]):
        """Verify no references to removed context_chunker.py."""
        workflow_str = yaml.dump(pr_agent_workflow)
        assert 'context_chunker' not in workflow_str
    
    def test_no_scripts_readme_references(self):
        """Verify no references to removed scripts README."""
        # Check all workflow files
        for wf_file in WORKFLOWS_DIR.glob("*.yml"):
            with open(wf_file, 'r', encoding='utf-8') as f:
                content = f.read()
                assert '.github/scripts/README.md' not in content


class TestRequirementsDevUpdates:
    """Test suite for requirements-dev.txt updates."""
    
    def test_pyyaml_added(self):
        """Verify PyYAML has been added to requirements-dev.txt."""
        req_file = Path(__file__).parent.parent.parent / "requirements-dev.txt"
        
        with open(req_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'PyYAML>=6.0' in content
        assert 'types-PyYAML>=6.0.0' in content
    
    def test_pyyaml_not_in_main_requirements(self):
        """Verify PyYAML is only in dev requirements, not main."""
        req_file = Path(__file__).parent.parent.parent / "requirements.txt"
        
        if req_file.exists():
            with open(req_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Should not be in main requirements
            assert 'pyyaml' not in content.lower()
            assert 'PyYAML' not in content and 'pyyaml' not in content.lower()
    def test_all_dev_requirements_have_versions(self):
        """Verify all dev requirements have version specifiers."""
        req_file = Path(__file__).parent.parent.parent / "requirements-dev.txt"
        
        with open(req_file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        for line in lines:
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Should have version specifier
            assert '>=' in line or '==' in line or '~=' in line, \
                f"Requirement '{line}' should have a version specifier"


class TestBackwardCompatibility:
    """Test suite ensuring changes don't break existing functionality."""
    
    def test_pr_agent_still_triggered_on_events(self, pr_agent_workflow: Dict[str, Any]):
        """Verify PR agent workflow still triggers on correct events."""
        triggers = pr_agent_workflow['on']
        
        assert 'pull_request' in triggers
        assert 'pull_request_review' in triggers
        assert 'issue_comment' in triggers
        assert 'workflow_run' in triggers
    
    def test_permissions_preserved(self, pr_agent_workflow: Dict[str, Any]):
        """Verify workflow permissions are maintained."""
        job = pr_agent_workflow['jobs']['pr-agent-trigger']
        permissions = job.get('permissions', {})
        
        assert 'contents' in permissions
        assert 'pull-requests' in permissions
        assert 'issues' in permissions
    
    def test_essential_environment_preserved(self, pr_agent_workflow: Dict[str, Any]):
        """Verify essential environment variables are still set."""
        job = pr_agent_workflow['jobs']['pr-agent-trigger']
        
        for step in job['steps']:
            if 'Parse PR Review Comments' in step.get('name', ''):
                env = step.get('env', {})
                assert 'GITHUB_TOKEN' in env


class TestEdgeCases:
    """Test edge cases in simplified workflows."""
    
    def test_empty_action_items_handling(self, pr_agent_workflow: Dict[str, Any]):
        """Verify workflow handles empty action items gracefully."""
        job = pr_agent_workflow['jobs']['pr-agent-trigger']
        parse_step = None
        
        for step in job['steps']:
            if step.get('name') == 'Parse PR Review Comments':
                parse_step = step
                break
        
        script = parse_step.get('run', '')
        
        # Should have fallback for empty action items
        assert 'general_improvements' in script or 'echo' in script
    
    def test_workflow_handles_missing_reviews(self, pr_agent_workflow: Dict[str, Any]):
        """Verify workflow doesn't fail when no reviews exist."""
        job = pr_agent_workflow['jobs']['pr-agent-trigger']
        parse_step = None
        
        for step in job['steps']:
            if step.get('name') == 'Parse PR Review Comments':
                parse_step = step
                break
        
        script = parse_step.get('run', '')
        
        # Should handle empty results gracefully
        assert '|| echo' in script or 'general_improvements' in script