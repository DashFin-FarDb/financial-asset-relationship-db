"""
Validation tests for simplified GitHub Actions workflows.

This module specifically tests the workflow files that were simplified
in the current branch, ensuring the simplifications don't break functionality.
"""

import pytest
import yaml
from pathlib import Path
from typing import Any, Dict


WORKFLOWS_DIR = Path(__file__).parent.parent.parent / ".github" / "workflows"


def load_workflow(filename: str) -> Dict[str, Any]:
    """
    Load a specific workflow file.
    
    Parameters:
        filename: Name of the workflow file (e.g., 'greetings.yml')
    
    Returns:
        Dict containing the parsed workflow.
    """
    workflow_path = WORKFLOWS_DIR / filename
    if not workflow_path.exists():
        pytest.skip(f"Workflow {filename} not found")
    
    with open(workflow_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


class TestGreetingsWorkflowSimplification:
    """Test the simplified greetings.yml workflow."""
    
    def test_greetings_workflow_exists(self):
        """Verify greetings workflow file exists."""
        assert (WORKFLOWS_DIR / "greetings.yml").exists(), \
            "greetings.yml should exist"
    
    def test_greetings_has_basic_structure(self):
        """Verify greetings workflow has required fields."""
        workflow = load_workflow("greetings.yml")
        
        assert "name" in workflow, "Workflow should have a name"
        assert "on" in workflow, "Workflow should have triggers"
        assert "jobs" in workflow, "Workflow should have jobs"
    
    def test_greetings_triggers_correct_events(self):
        """Verify greetings workflow triggers on correct events."""
        workflow = load_workflow("greetings.yml")
        triggers = workflow.get("on", [])
        
        if isinstance(triggers, list):
            assert "pull_request_target" in triggers, \
                "Should trigger on pull_request_target"
            assert "issues" in triggers, \
                "Should trigger on issues"
    
    def test_greetings_has_first_interaction_action(self):
        """Verify greetings uses first-interaction action."""
        workflow = load_workflow("greetings.yml")
        jobs = workflow.get("jobs", {})
        
        assert len(jobs) > 0, "Workflow should have at least one job"
        
        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            action_found = any(
                "first-interaction" in str(step.get("uses", ""))
                for step in steps
            )
            if action_found:
                return
        
        pytest.fail("Workflow should use actions/first-interaction action")
    
    def test_greetings_has_required_permissions(self):
        """Verify greetings job has required permissions."""
        workflow = load_workflow("greetings.yml")
        jobs = workflow.get("jobs", {})
        
        for job_name, job_config in jobs.items():
            permissions = job_config.get("permissions", {})
            assert "issues" in permissions, \
                f"Job '{job_name}' should have issues permission"
            assert "pull-requests" in permissions, \
                f"Job '{job_name}' should have pull-requests permission"


class TestLabelWorkflowSimplification:
    """Test the simplified label.yml workflow."""
    
    def test_label_workflow_exists(self):
        """Verify label workflow file exists."""
        assert (WORKFLOWS_DIR / "label.yml").exists(), \
            "label.yml should exist"
    
    def test_label_has_basic_structure(self):
        """Verify label workflow has required fields."""
        workflow = load_workflow("label.yml")
        
        assert "name" in workflow, "Workflow should have a name"
        assert "on" in workflow, "Workflow should have triggers"
        assert "jobs" in workflow, "Workflow should have jobs"
    
    def test_label_uses_labeler_action(self):
        """Verify label workflow uses actions/labeler."""
        workflow = load_workflow("label.yml")
        jobs = workflow.get("jobs", {})
        
        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            action_found = any(
                "labeler" in str(step.get("uses", ""))
                for step in steps
            )
            if action_found:
                return
        
        pytest.fail("Workflow should use actions/labeler action")
    
    def test_label_simplified_no_config_checks(self):
        """Verify simplified label workflow doesn't have config existence checks."""
        workflow = load_workflow("label.yml")
        workflow_str = yaml.dump(workflow)
        
        removed_patterns = [
            "check-config",
            "config_exists",
            "labeler.yml not found",
        ]
        
        for pattern in removed_patterns:
            assert pattern not in workflow_str, \
                f"Simplified workflow should not contain '{pattern}'"


class TestPRAgentWorkflowSimplification:
    """Test the simplified pr-agent.yml workflow."""
    
    def test_pr_agent_workflow_exists(self):
        """Verify pr-agent workflow file exists."""
        assert (WORKFLOWS_DIR / "pr-agent.yml").exists(), \
            "pr-agent.yml should exist"
    
    def test_pr_agent_has_basic_structure(self):
        """Verify pr-agent workflow has required fields."""
        workflow = load_workflow("pr-agent.yml")
        
        assert "name" in workflow, "Workflow should have a name"
        assert "on" in workflow, "Workflow should have triggers"
        assert "jobs" in workflow, "Workflow should have jobs"
    
    def test_pr_agent_no_duplicate_setup_python(self):
        """Verify pr-agent workflow doesn't have duplicate Setup Python steps."""
        workflow = load_workflow("pr-agent.yml")
        jobs = workflow.get("jobs", {})
        
        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            python_setup_steps = [
                step for step in steps
                if "Setup Python" in step.get("name", "")
            ]
            
            assert len(python_setup_steps) <= 1, \
                f"Job '{job_name}' should have at most one 'Setup Python' step"
    
    def test_pr_agent_simplified_dependencies_install(self):
        """Verify pr-agent has simplified dependency installation."""
        workflow = load_workflow("pr-agent.yml")
        workflow_str = yaml.dump(workflow)
        
        removed_patterns = [
            "tiktoken",
            "context chunker",
            "smart chunking"
        ]
        
        for pattern in removed_patterns:
            assert pattern.lower() not in workflow_str.lower(), \
                f"Simplified workflow should not reference '{pattern}'"
    
    def test_pr_agent_no_chunking_steps(self):
        """Verify pr-agent workflow doesn't have context chunking steps."""
        workflow = load_workflow("pr-agent.yml")
        jobs = workflow.get("jobs", {})
        
        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            
            for step in steps:
                step_name = step.get("name", "").lower()
                assert "chunk" not in step_name, \
                    f"Step '{step.get('name')}' should not reference chunking"


class TestAPISecWorkflowSimplification:
    """Test the simplified apisec-scan.yml workflow."""
    
    def test_apisec_workflow_exists(self):
        """Verify apisec workflow file exists."""
        assert (WORKFLOWS_DIR / "apisec-scan.yml").exists(), \
            "apisec-scan.yml should exist"
    
    def test_apisec_has_basic_structure(self):
        """Verify apisec workflow has required fields."""
        workflow = load_workflow("apisec-scan.yml")
        
        assert "name" in workflow, "Workflow should have a name"
        assert "on" in workflow, "Workflow should have triggers"
        assert "jobs" in workflow, "Workflow should have jobs"
    
    def test_apisec_no_credentials_check(self):
        """Verify apisec workflow doesn't have credential existence checks."""
        workflow = load_workflow("apisec-scan.yml")
        workflow_str = yaml.dump(workflow)
        
        removed_patterns = [
            "Check for APIsec credentials",
            "credentials not configured",
        ]
        
        for pattern in removed_patterns:
            assert pattern not in workflow_str, \
                f"Simplified workflow should not contain '{pattern}'"
    
    def test_apisec_scan_step_exists(self):
        """Verify apisec workflow has the scan action step."""
        workflow = load_workflow("apisec-scan.yml")
        jobs = workflow.get("jobs", {})
        
        has_scan_step = False
        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            for step in steps:
                uses = step.get("uses", "")
                if "apisec" in uses.lower() and "scan" in uses.lower():
                    has_scan_step = True
                    break
        
        assert has_scan_step, \
            "Workflow should have apisec scan action step"


class TestWorkflowSimplificationConsistency:
    """Test consistency across simplified workflows."""
    
    def test_simplified_workflows_have_reasonable_size(self):
        """Verify simplified workflows are not overly large."""
        workflow_files = [
            ("greetings.yml", 50),
            ("label.yml", 50),
            ("pr-agent.yml", 500),
            ("apisec-scan.yml", 500)
        ]
        
        for filename, max_lines in workflow_files:
            workflow_path = WORKFLOWS_DIR / filename
            if not workflow_path.exists():
                continue
            
            with open(workflow_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            assert len(lines) < max_lines, \
                f"{filename} should be reasonable size (<{max_lines} lines)"
    
    def test_no_orphaned_script_references(self):
        """Verify workflows don't reference deleted scripts."""
        workflow_files = ["pr-agent.yml"]
        
        deleted_scripts = [
            "context_chunker.py",
            ".github/scripts/context_chunker.py"
        ]
        
        for filename in workflow_files:
            workflow_path = WORKFLOWS_DIR / filename
            if not workflow_path.exists():
                pytest.skip(f"Workflow {filename} not found")
            
            workflow = load_workflow(filename)
            
            workflow_str = yaml.dump(workflow)
            
            for script in deleted_scripts:
                assert script not in workflow_str, \
                    f"{filename} should not reference deleted script '{script}'"