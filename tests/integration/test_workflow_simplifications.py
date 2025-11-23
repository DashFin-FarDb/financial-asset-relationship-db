"""
Validation tests for GitHub workflow simplifications.

This test suite validates that workflow simplifications (removal of conditional
checks, simplified greetings, removed labeler prerequisites) were properly
implemented and don't break workflow functionality.
"""

import pytest
import yaml
from pathlib import Path
from typing import Any, Dict


WORKFLOWS_DIR = Path(__file__).parent.parent.parent / ".github" / "workflows"


def load_workflow(name: str) -> Dict[str, Any]:
    """Load a workflow file by name."""
    workflow_file = WORKFLOWS_DIR / name
    if not workflow_file.exists():
        pytest.skip(f"{name} not found")
    with open(workflow_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


class TestGreetingsWorkflowSimplification:
    """Test suite for greetings.yml simplification."""
    
    def test_greetings_workflow_exists(self):
        """Test that greetings workflow still exists."""
        assert (WORKFLOWS_DIR / "greetings.yml").exists()
    
    def test_greetings_has_placeholder_messages(self):
        """Test that greetings uses placeholder messages (not custom ones)."""
        workflow = load_workflow("greetings.yml")
        
        steps = workflow.get('jobs', {}).get('greeting', {}).get('steps', [])
        first_interaction_step = None
        
        for step in steps:
            if 'first-interaction' in step.get('uses', ''):
                first_interaction_step = step
                break
        
        assert first_interaction_step is not None, "Should have first-interaction step"
        
        with_section = first_interaction_step.get('with', {})
        issue_message = with_section.get('issue-message', '')
        pr_message = with_section.get('pr-message', '')
        
        # Should be simple placeholder messages, not long custom ones
        assert len(issue_message) < 200, "Issue message should be simple placeholder"
        assert len(pr_message) < 200, "PR message should be simple placeholder"
        assert 'displayed on users' in issue_message.lower(), (
            "Should contain generic placeholder text"
        )
    
    def test_greetings_no_complex_formatting(self):
        """Test that greetings don't contain complex markdown formatting."""
        workflow = load_workflow("greetings.yml")
        
        steps = workflow.get('jobs', {}).get('greeting', {}).get('steps', [])
        for step in steps:
            if 'first-interaction' in step.get('uses', ''):
                with_section = step.get('with', {})
                messages = [
                    with_section.get('issue-message', ''),
                    with_section.get('pr-message', '')
                ]
                
                for msg in messages:
                    # Should not contain multiple paragraphs or lists
                    assert msg.count('\n') < 3, "Messages should be simple, not multi-paragraph"
                    assert '- ' not in msg, "Messages should not contain lists"
                    assert '**' not in msg, "Messages should not contain bold formatting"


class TestLabelWorkflowSimplification:
    """Test suite for label.yml simplification."""
    
    def test_label_workflow_exists(self):
        """Test that label workflow still exists."""
        assert (WORKFLOWS_DIR / "label.yml").exists()
    
    def test_label_no_config_check_step(self):
        """Test that label workflow no longer checks for labeler config."""
        workflow = load_workflow("label.yml")
        
        steps = workflow.get('jobs', {}).get('label', {}).get('steps', [])
        step_names = [step.get('name', '') for step in steps]
        
        # Should not have checkout or config check steps
        assert 'Checkout repository' not in step_names, (
            "Label workflow should not checkout repository"
        )
        assert 'Check for labeler config' not in step_names, (
            "Label workflow should not check for config file"
        )
    
    def test_label_directly_uses_labeler(self):
        """Test that label workflow directly uses labeler action."""
        workflow = load_workflow("label.yml")
        
        steps = workflow.get('jobs', {}).get('label', {}).get('steps', [])
        
        # Should have exactly one step that uses labeler
        labeler_steps = [s for s in steps if 'labeler' in s.get('uses', '').lower()]
        assert len(labeler_steps) == 1, "Should have exactly one labeler step"
        
        # Should be a simple workflow with minimal steps
        assert len(steps) <= 2, "Should be a simple workflow with minimal steps"
    
    def test_label_no_conditional_execution(self):
        """Test that label workflow doesn't have conditional step execution."""
        workflow = load_workflow("label.yml")
        
        steps = workflow.get('jobs', {}).get('label', {}).get('steps', [])
        
        for step in steps:
            assert 'if' not in step, (
                f"Step '{step.get('name')}' should not have conditional execution"
            )


class TestAPISecWorkflowSimplification:
    """Test suite for apisec-scan.yml simplification."""
    
    def test_apisec_workflow_exists(self):
        """Test that APIsec workflow still exists."""
        assert (WORKFLOWS_DIR / "apisec-scan.yml").exists()
    
    def test_apisec_no_job_level_credential_check(self):
        """Test that APIsec workflow jobs don't check for credentials at job level."""
        workflow = load_workflow("apisec-scan.yml")
        
        for job_name, job in workflow.get('jobs', {}).items():
            # Job should not have conditional on secrets
            job_if = job.get('if', '')
            assert 'apisec_username' not in job_if, (
                f"Job '{job_name}' should not check for APIsec username credential"
            )
            assert 'apisec_password' not in job_if, (
                f"Job '{job_name}' should not check for APIsec password credential"
            )
    
    def test_apisec_no_credential_check_steps(self):
        """Test that APIsec workflow doesn't have steps that check credentials."""
        workflow = load_workflow("apisec-scan.yml")
        
        for job_name, job in workflow.get('jobs', {}).items():
            steps = job.get('steps', [])
            for step in steps:
                step_name = step.get('name', '')
                assert 'credential' not in step_name.lower(), (
                    f"Step '{step_name}' should not check credentials"
                )
                assert 'Check for APIsec' not in step_name, (
                    f"Step '{step_name}' should not check for APIsec setup"
                )
    
    def test_apisec_scan_step_exists(self):
        """Test that APIsec scan step still exists."""
        workflow = load_workflow("apisec-scan.yml")
        
        found_scan_step = False
        for job_name, job in workflow.get('jobs', {}).items():
            steps = job.get('steps', [])
            for step in steps:
                if 'apisec-run-scan' in step.get('uses', ''):
                    found_scan_step = True
                    break
        
        assert found_scan_step, "APIsec scan step should exist"


class TestPRAgentWorkflowSimplification:
    """Test suite for pr-agent.yml simplification (removal of context chunking)."""
    
    def test_pr_agent_no_chunking_step(self):
        """Test that PR Agent workflow no longer has context chunking step."""
        workflow = load_workflow("pr-agent.yml")
        
        for job_name, job in workflow.get('jobs', {}).items():
            steps = job.get('steps', [])
            step_names = [s.get('name', '') for s in steps]
            
            assert 'Fetch PR Context with Chunking' not in step_names, (
                "PR Agent should not have context chunking step"
            )
            assert 'context_chunker' not in str(steps).lower(), (
                "PR Agent should not reference context_chunker script"
            )
    
    def test_pr_agent_no_tiktoken_installation(self):
        """Test that PR Agent no longer installs tiktoken."""
        workflow = load_workflow("pr-agent.yml")
        
        workflow_str = yaml.dump(workflow).lower()
        assert 'tiktoken' not in workflow_str, (
            "PR Agent should not install or reference tiktoken"
        )
    
    def test_pr_agent_simplified_comment_parsing(self):
        """Test that PR Agent uses simplified comment parsing."""
        workflow = load_workflow("pr-agent.yml")
        
        for job_name, job in workflow.get('jobs', {}).items():
            steps = job.get('steps', [])
            
            # Should have "Parse PR Review Comments" step
            parse_steps = [s for s in steps if 'Parse' in s.get('name', '')]
            if parse_steps:
                parse_step = parse_steps[0]
                run_script = parse_step.get('run', '')
                
                # Should not reference context files or chunking
                assert 'context_chunked' not in run_script, (
                    "Should not use chunked context files"
                )
                assert 'CONTEXT_FILE' not in run_script, (
                    "Should not use context file variable"
                )
    
    def test_pr_agent_no_context_size_output(self):
        """Test that PR Agent no longer outputs context size metrics."""
        workflow = load_workflow("pr-agent.yml")
        
        for job_name, job in workflow.get('jobs', {}).items():
            steps = job.get('steps', [])
            for step in steps:
                run_script = step.get('run', '')
                
                # Should not output context_size or chunked status
                assert 'context_size=' not in run_script, (
                    "Should not output context_size"
                )
                assert 'chunked=' not in run_script, (
                    "Should not output chunked status"
                )
    
    def test_pr_agent_comment_simplified(self):
        """Test that PR Agent bot comment is simplified (no context stats)."""
        workflow = load_workflow("pr-agent.yml")
        
        for job_name, job in workflow.get('jobs', {}).items():
            steps = job.get('steps', [])
            for step in steps:
                if 'Comment' in step.get('name', ''):
                    script = step.get('with', {}).get('script', '')
                    if script:
                        # Should not mention context size or chunking
                        assert 'context size' not in script.lower(), (
                            "Comment should not mention context size"
                        )
                        assert 'chunking' not in script.lower(), (
                            "Comment should not mention chunking"
                        )
                        assert 'Context Management' not in script, (
                            "Comment should not mention Context Management"
                        )


class TestWorkflowSimplificationsConsistency:
    """Test suite for consistency across workflow simplifications."""
    
    def test_all_modified_workflows_exist(self):
        """Test that all modified workflows still exist."""
        modified_workflows = [
            'pr-agent.yml',
            'greetings.yml',
            'label.yml',
            'apisec-scan.yml'
        ]
        
        for workflow in modified_workflows:
            assert (WORKFLOWS_DIR / workflow).exists(), (
                f"Modified workflow {workflow} should still exist"
            )
    
    def test_workflows_still_have_proper_triggers(self):
        """Test that simplified workflows still have proper triggers."""
        workflows = {
            'greetings.yml': ['pull_request_target', 'issues'],
            'label.yml': ['pull_request_target'],
            'apisec-scan.yml': ['push', 'pull_request'],
            'pr-agent.yml': ['pull_request', 'pull_request_review', 'issue_comment']
        }
        
        for workflow_name, expected_triggers in workflows.items():
            workflow = load_workflow(workflow_name)
            actual_triggers = workflow.get('on', {})
            
            if isinstance(actual_triggers, list):
                actual_trigger_keys = actual_triggers
            elif isinstance(actual_triggers, dict):
                actual_trigger_keys = list(actual_triggers.keys())
            else:
                actual_trigger_keys = [actual_triggers]
            
            for expected in expected_triggers:
                assert any(expected in str(t) for t in actual_trigger_keys), (
                    f"{workflow_name} should trigger on {expected}"
                )
    
    def test_no_workflows_reference_deleted_files(self):
        """Test that no workflow references deleted files (labeler.yml, context_chunker.py)."""
        deleted_files = [
            'labeler.yml',
            'context_chunker.py',
            '.github/scripts/context_chunker.py'
        ]
        
        for workflow_file in list(WORKFLOWS_DIR.glob("*.yml")) + list(WORKFLOWS_DIR.glob("*.yaml")):
            with open(workflow_file, 'r') as f:
                content = f.read()
            
            for deleted_file in deleted_files:
                assert deleted_file not in content, (
                    f"{workflow_file.name} should not reference deleted file {deleted_file}"
                )


class TestWorkflowSimplificationsBenefits:
    """Test suite validating benefits of simplifications."""
    
    def test_simplified_workflows_are_shorter(self):
        """Test that simplified workflows are shorter (fewer lines)."""
        # These workflows should be relatively short after simplification
        simple_workflows = {
            'greetings.yml': 30,  # Max lines
            'label.yml': 30,
        }
        
        for workflow_name, max_lines in simple_workflows.items():
            workflow_file = WORKFLOWS_DIR / workflow_name
            if workflow_file.exists():
                with open(workflow_file, 'r') as f:
                    line_count = len(f.readlines())
                
                assert line_count <= max_lines, (
                    f"{workflow_name} should be under {max_lines} lines after simplification "
                    f"(current: {line_count} lines)"
                )
    
    def test_workflows_have_fewer_conditional_steps(self):
        """Test that workflows have minimal conditional logic."""
        simplified_workflows = ['greetings.yml', 'label.yml']
        
        for workflow_name in simplified_workflows:
            workflow = load_workflow(workflow_name)
            
            conditional_count = 0
            for job_name, job in workflow.get('jobs', {}).items():
                if 'if' in job:
                    conditional_count += 1
                
                steps = job.get('steps', [])
                for step in steps:
                    if 'if' in step:
                        conditional_count += 1
            
            assert conditional_count <= 1, (
                f"{workflow_name} should have minimal conditionals (found {conditional_count})"
            )
    
    def test_workflows_use_versioned_actions(self):
        """Test that workflows use versioned actions (not floating tags)."""
        
        for workflow_file in list(WORKFLOWS_DIR.glob("*.yml")) + list(WORKFLOWS_DIR.glob("*.yaml")):
            workflow = yaml.safe_load(workflow_file.read_text())
            
            for job_name, job in workflow.get('jobs', {}).items():
                steps = job.get('steps', [])
                for step in steps:
                    uses = step.get('uses', '')
                    if uses and '/' in uses:
                        # If it's a third-party action, it should be versioned
                        assert '@' in uses, (
                            f"Action '{uses}' in {workflow_file.name} should specify version"
                        )