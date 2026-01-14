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
    """
    Load and parse the pr-agent.yml GitHub Actions workflow.
    
    Returns:
        workflow (dict): Parsed YAML content of pr-agent.yml as a dictionary.
    """
    workflow_path = WORKFLOWS_DIR / "pr-agent.yml"
    with open(workflow_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


@pytest.fixture
def pr_agent_config() -> Dict[str, Any]:
    """
    Load and parse the PR agent YAML configuration.
    
    Parses the YAML content of CONFIG_FILE and returns the resulting mapping.
    
    Returns:
        config (dict): Parsed configuration mapping from CONFIG_FILE.
    """
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


@pytest.fixture
def apisec_workflow() -> Dict[str, Any]:
    """
    Load and parse the apisec-scan.yml workflow file.
    
    Returns:
        workflow (Dict[str, Any]): Parsed YAML mapping representing the workflow file.
    """
    workflow_path = WORKFLOWS_DIR / "apisec-scan.yml"
    with open(workflow_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


@pytest.fixture
def greetings_workflow() -> Dict[str, Any]:
    """
    Load and parse the greetings GitHub Actions workflow.
    
    Returns:
        dict: Parsed contents of the .github/workflows/greetings.yml file as a dictionary reflecting the YAML structure.
    """
    workflow_path = WORKFLOWS_DIR / "greetings.yml"
    with open(workflow_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


@pytest.fixture
def label_workflow() -> Dict[str, Any]:
    """
    Load and parse the .github/workflows/label.yml workflow file.
    
    Returns:
        dict: The parsed YAML content of the label workflow as a dictionary.
    """
    workflow_path = WORKFLOWS_DIR / "label.yml"
    with open(workflow_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)
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
        """
        Ensure the "Install Python dependencies" step does not install PyYAML or tiktoken.
        
        Asserts the step exists in the `pr-agent-trigger` job and that its `run` script contains no case-insensitive references to "pyyaml" or "tiktoken".
        """
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
        """
        Validate that the PR agent configuration contains required top-level keys and that the agent identity and enabled flag are correct.
        
        Checks for the presence of `agent`, `monitoring`, `comment_parsing`, and `actions` keys, and verifies the agent's `name` is "Financial DB PR Agent" and `enabled` is True.
        """
        assert 'agent' in pr_agent_config
        assert 'monitoring' in pr_agent_config
        assert 'comment_parsing' in pr_agent_config
        assert 'actions' in pr_agent_config
        
        # Check agent basics
        agent = pr_agent_config['agent']
        assert agent['name'] == 'Financial DB PR Agent'
        assert agent['enabled'] is True
    
    def test_monitoring_settings_intact(self, pr_agent_config: Dict[str, Any]):
        """
        Assert that the `monitoring` section of the PR agent config contains the required keys.
        
        Parameters:
            pr_agent_config (dict): Parsed PR agent configuration containing a `monitoring` mapping.
        """
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
        """
        Assert that the APIsec workflow defines the required triggers: `push`, `pull_request`, and `schedule`.
        
        Parameters:
            apisec_workflow (dict): Parsed YAML of the APIsec workflow file to inspect for the `on` triggers.
        """
        assert 'on' in apisec_workflow
        triggers = apisec_workflow['on']
        
        assert 'push' in triggers
        assert 'pull_request' in triggers
        assert 'schedule' in triggers


class TestGreetingsWorkflowSimplification:
    """Test suite for the simplified Greetings workflow."""
    
    def test_simple_messages_only(self, greetings_workflow: Dict[str, Any]):
        """
        Ensure the greeting job's first-interaction messages are short and plain.
        
        Checks that the step using `first-interaction` in the `greeting` job provides `issue-message` and `pr-message` values shorter than 100 characters and that they do not contain markdown headings (`##`) or bold formatting (`**`).
        
        Parameters:
            greetings_workflow (Dict[str, Any]): Parsed YAML of the greetings workflow.
        """
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
        """
        Ensure the label job's labeler step is not conditionally executed.
        
        Asserts that no step using the labeler action in the `label` job contains an `if` key.
        
        Parameters:
            label_workflow (Dict[str, Any]): Parsed YAML of the label workflow (label.yml).
        """
        job = label_workflow['jobs']['label']
        
        for step in job['steps']:
            if 'labeler' in step.get('uses', ''):
                # Should not have 'if' condition
                assert 'if' not in step
    
    def test_no_checkout_step(self, label_workflow: Dict[str, Any]):
        """
        Checks that the label job does not include a "Checkout repository" step.
        
        Parameters:
            label_workflow (Dict[str, Any]): Parsed workflow dictionary for the label workflow (from workflows/label.yml).
        """
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
        workflow_files = list(WORKFLOWS_DIR.glob("*.yml")) + list(WORKFLOWS_DIR.glob("*.yaml"))
        
        for wf_file in workflow_files:
            with open(wf_file, 'r', encoding='utf-8') as f:
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
        """
        Ensure the PR agent workflow does not reference the removed `labeler.yml` file.
        """
        workflow_str = yaml.dump(pr_agent_workflow)
        assert 'labeler.yml' not in workflow_str
    
    def test_no_context_chunker_references(self, pr_agent_workflow: Dict[str, Any]):
        """Verify no references to removed context_chunker.py."""
        workflow_str = yaml.dump(pr_agent_workflow)
        assert 'context_chunker' not in workflow_str
    
    def test_no_scripts_readme_references(self):
        """
        Ensure no workflow file references '.github/scripts/README.md'.
        
        Checks all YAML workflow files in the workflows directory and fails if any contain the path '.github/scripts/README.md'.
        """
        # Check all workflow files
        for wf_file in list(WORKFLOWS_DIR.glob("*.yml")) + list(WORKFLOWS_DIR.glob("*.yaml")):
            with open(wf_file, 'r', encoding='utf-8') as f:
                content = f.read()
                assert '.github/scripts/README.md' not in content


class TestRequirementsDevUpdates:
    """Test suite for requirements-dev.txt updates."""
    
    def test_pyyaml_added(self):
        """
        Verify requirements-dev.txt contains the explicit PyYAML development dependencies.
        
        Asserts that the file includes 'PyYAML>=6.0' and 'types-PyYAML>=6.0.0'.
        """
        req_file = Path(__file__).parent.parent.parent / "requirements-dev.txt"
        
        with open(req_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'PyYAML>=6.0' in content
        assert 'types-PyYAML>=6.0.0' in content
    
    def test_pyyaml_not_in_main_requirements(self):
        """
        Ensure PyYAML is not listed in the main requirements.txt.
        
        If a requirements.txt file exists at the repository root, read its contents and assert that it does not reference PyYAML (case-insensitive).
        """
        req_file = Path(__file__).parent.parent.parent / "requirements.txt"
        
        if req_file.exists():
            with open(req_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Should not be in main requirements
            assert 'pyyaml' not in content.lower()
            assert 'PyYAML' not in content and 'pyyaml' not in content.lower()
    
    def test_all_dev_requirements_have_versions(self):
        """
        Ensure every dependency in requirements-dev.txt has a version specifier or is a complex dependency.
        
        Recognizes PEP 508-style version operators (>=, ==, ~=, !=, <, <=, >). Treats a requirement as "complex" if it uses extras (e.g., package[extra]), a URL (contains '://'), or a direct reference (contains '@'). Fails the test with the offending requirement line if neither condition is met.
        """
        req_file = Path(__file__).parent.parent.parent / "requirements-dev.txt"
            # Basic PEP 508 version specifier check
            has_version = any(op in line for op in ['>=', '==', '~=', '!=', '<', '<=', '>'])
            # Handle extras syntax and file/URL requirements
            is_complex_req = ('[' in line or '://' in line or '@' in line)

            assert has_version or is_complex_req, \
                f"Requirement '{line}' should have a version specifier or be a complex dependency"
                f"Requirement '{line}' should have a version specifier"
    
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
        """
        Assert that the Parse PR Review Comments step includes the GITHUB_TOKEN environment variable.
        
        Parameters:
            pr_agent_workflow (dict): Parsed GitHub Actions workflow for the PR agent (loaded YAML as a dict).
        """
        job = pr_agent_workflow['jobs']['pr-agent-trigger']
        
        for step in job['steps']:
            if 'Parse PR Review Comments' in step.get('name', ''):
                env = step.get('env', {})
                assert 'GITHUB_TOKEN' in env


class TestEdgeCases:
    """Test edge cases in simplified workflows."""
    
    def test_empty_action_items_handling(self, pr_agent_workflow: Dict[str, Any]):
        """
        Assert the Parse PR Review Comments step provides a fallback when action items are empty.
        
        Checks the 'Parse PR Review Comments' step script and verifies it contains a fallback token such as 'general_improvements' or an 'echo' command to handle empty action items.
        """
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