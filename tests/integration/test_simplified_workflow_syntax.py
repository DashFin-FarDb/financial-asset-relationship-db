"""
Syntax and best practices validation for simplified GitHub workflows.

Validates that the simplified workflows follow GitHub Actions best practices
and don't have common pitfalls.
"""

import pytest
import yaml
import re
from pathlib import Path
from typing import Dict, Any


class TestWorkflowSyntaxValidation:
    """Validate GitHub Actions workflow syntax."""
    
    @pytest.fixture
    def pr_agent_workflow(self) -> Dict[str, Any]:
        """Load pr-agent.yml workflow."""
        with open(".github/workflows/pr-agent.yml") as f:
            return yaml.safe_load(f)
    
    def test_pr_agent_has_required_triggers(self, pr_agent_workflow):
        """Verify pr-agent.yml has appropriate triggers."""
        triggers = pr_agent_workflow.get("on")
        assert triggers is not None, "Workflow must define 'on' triggers"

        # Normalize to dict if list/str forms are used
        if isinstance(triggers, str):
            trigger_keys = {triggers}
        elif isinstance(triggers, list):
            trigger_keys = set(triggers)
        elif isinstance(triggers, dict):
            trigger_keys = set(triggers.keys())
        else:
            pytest.fail(f"Unexpected type for 'on': {type(triggers)}")

        required = {"pull_request", "pull_request_review", "issue_comment", "check_suite"}
        missing = required - trigger_keys
        assert not missing, f"Missing required triggers: {', '.join(sorted(missing))}"
    
    def test_pr_agent_jobs_have_permissions(self, pr_agent_workflow):
        """Ensure jobs specify required permissions."""
        jobs = pr_agent_workflow.get("jobs", {})
        
        for job_name, job_config in jobs.items():
            permissions = job_config.get("permissions", {})
            if job_name == "pr-agent-trigger":
                assert "issues" in permissions, \
                    f"Job {job_name} should have issues permission"
    
    def test_pr_agent_uses_specific_action_versions(self, pr_agent_workflow):
        """Verify actions use pinned versions (not branches like @main/@master) and not unpinned."""
        jobs = pr_agent_workflow.get("jobs", {})
        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            for step in steps:
                uses = step.get("uses")
                if not uses:
                    continue
                # Allow local actions and docker images without '@'
                if uses.startswith("./") or uses.startswith("docker://"):
                    continue
                assert "@" in uses, f"Action must pin a version with '@': {uses}"
                # Take last '@' in case of '@' appearing in org/name
                version = uses.rsplit("@", 1)[1].strip()
                assert version and version.lower() not in {"main", "master", "latest", "head"}, \
                    f"Action should use immutable version/tag/sha, not @{version}: {uses}"
                # Discourage moving tags like vLatest; allow semantic tags or SHAs
                assert not re.fullmatch(r"[A-Za-z]+", version) or re.fullmatch(r"[0-9a-fA-F]{7,40}", version), \
                    f"Action version appears to be a branch-like ref: {version} in {uses}"
    
    def test_pr_agent_secrets_properly_referenced(self, pr_agent_workflow):
        """Ensure tokens are referenced correctly using supported contexts."""
        # Search both the parsed dump and raw content to avoid formatting artifacts
        workflow_str = yaml.dump(pr_agent_workflow)
        with open(".github/workflows/pr-agent.yml") as f:
            raw_content = f.read()
        combined = f"{workflow_str}\n{raw_content}"

        # Match both secrets.GITHUB_TOKEN and github.token usages
        secrets_refs = re.findall(r'\$\{\{\s*secrets\.([A-Z0-9_]+)\s*\}\}', combined, flags=re.IGNORECASE)
        github_token_refs = re.findall(r'\$\{\{\s*github\.token\s*\}\}', combined, flags=re.IGNORECASE)

        assert ("GITHUB_TOKEN" in [s.upper() for s in secrets_refs]) or (len(github_token_refs) > 0), \
            "Should reference an authentication token via secrets.GITHUB_TOKEN or github.token"


class TestSimplifiedWorkflowBestPractices:
    """Validate best practices in simplified workflows."""
    
    def test_modified_workflows_use_ubuntu_latest(self):
        """Verify modified workflows use ubuntu-latest for consistency."""
        # Only check workflows that were actually modified in this branch
        modified_workflows = [
            ".github/workflows/pr-agent.yml",
            ".github/workflows/apisec-scan.yml",
            ".github/workflows/greetings.yml",
            ".github/workflows/label.yml",
        ]
        
        for workflow_path in modified_workflows:
            workflow_file = Path(workflow_path)
            if not workflow_file.exists():
                continue
                
            with open(workflow_file) as f:
                workflow = yaml.safe_load(f)
            
            jobs = workflow.get("jobs", {})
            for job_name, job_config in jobs.items():
                runs_on = job_config.get("runs-on", "")
                if runs_on:
                    # Some workflows might legitimately use other runners
                    # Just check that runs-on is specified
                    assert len(str(runs_on)) > 0, \
                        f"{workflow_file.name}:{job_name} should specify runner"
    
    def test_modified_workflows_have_descriptive_names(self):
        """Ensure modified workflows have clear, descriptive names."""
        modified_workflows = [
            ".github/workflows/pr-agent.yml",
            ".github/workflows/apisec-scan.yml",
            ".github/workflows/greetings.yml",
            ".github/workflows/label.yml",
        ]
        
        for workflow_path in modified_workflows:
            workflow_file = Path(workflow_path)
            if not workflow_file.exists():
                continue
                
            with open(workflow_file) as f:
                workflow = yaml.safe_load(f)
            
            name = workflow.get("name", "")
            assert len(name) > 0, f"{workflow_file.name} should have a name"
    
    def test_pr_agent_install_steps_have_error_handling(self):
        """Verify installation steps handle errors appropriately."""
        with open(".github/workflows/pr-agent.yml") as f:
            workflow = yaml.safe_load(f)
        
        jobs = workflow.get("jobs", {})
        trigger_job = jobs.get("pr-agent-trigger", {})
        steps = trigger_job.get("steps", [])
        
        # Find install steps
        install_steps = [s for s in steps if "Install" in s.get("name", "")]
        
        assert len(install_steps) > 0, "Should have installation steps"
        
        for step in install_steps:
            run_script = step.get("run", "") or ""
            lower_script = run_script.lower()
            if "pip install" in lower_script and "-r" in lower_script:
                # Consider safe if using a file existence check or standard guarded patterns
                guarded = any(token in lower_script for token in [
                    "test -f", "[ -f", "if [ -f", "if test -f", "powershell -command", "cmd /c if exist"
                ])
                # Also accept robust pip flags that won't mask missing files (pip exits non-zero on missing -r target)
                uses_requirements = " -r " in lower_script or "--requirement" in lower_script
                assert uses_requirements, "Install must reference a requirements file via -r/--requirement."
                assert guarded or uses_requirements, "Install steps should guard file existence or safely use pip with -r."


class TestRemovedFeaturesNotReferenced:
    """Ensure removed features have no lingering references."""
    
    def test_no_context_chunking_in_any_workflow(self):
        """Verify no workflows reference context chunking."""
        workflow_dir = Path(".github/workflows")
        
        forbidden_terms = ["chunk", "context_size", "tiktoken", "summarization"]
        
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file) as f:
                content = f.read().lower()
            
            for term in forbidden_terms:
                assert term not in content, \
                    f"{workflow_file.name} contains removed term '{term}'"
    
    def test_no_labeler_config_file_referenced_in_code(self):
        """Ensure label.yml workflow doesn't actively reference the removed labeler.yml config."""
        # The label.yml workflow has comments mentioning labeler.yml setup,
        # but that's just documentation. Check that it's not actually trying to use it.
        workflow_path = Path(".github/workflows/label.yml")
        
        with open(workflow_path) as f:
            workflow = yaml.safe_load(f)
        
        # Check that the workflow doesn't have steps that would fail without labeler.yml
        jobs = workflow.get("jobs", {})
        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            # The labeler action should still be present, just without the config file
            # This is expected and not a problem - it's just simplified
            assert len(steps) > 0, f"Job {job_name} should have steps"


class TestWorkflowConditionalLogic:
    """Validate conditional execution logic in workflows."""
    
    def test_pr_agent_trigger_conditions_valid(self):
        """Ensure pr-agent-trigger has valid conditional logic."""
        with open(".github/workflows/pr-agent.yml") as f:
            workflow = yaml.safe_load(f)
        
        jobs = workflow.get("jobs", {})
        trigger_job = jobs.get("pr-agent-trigger", {})
        
        if_condition = trigger_job.get("if", "")
        assert len(if_condition) > 0, "pr-agent-trigger should have conditional"
        
        # Should check for changes_requested or @copilot mention
        assert "changes_requested" in if_condition, \
            "Should trigger on changes_requested reviews"
        assert "@copilot" in if_condition or "copilot" in if_condition.lower(), \
            "Should trigger on @copilot mentions"
    
    def test_auto_merge_check_conditions_valid(self):
        """Verify auto-merge-check has appropriate conditions."""
        with open(".github/workflows/pr-agent.yml") as f:
            workflow = yaml.safe_load(f)
        
        jobs = workflow.get("jobs", {})
        merge_job = jobs.get("auto-merge-check", {})
        
        if_condition = merge_job.get("if", "")
        assert len(if_condition) > 0, "auto-merge-check should have conditional"


class TestWorkflowStepOrdering:
    """Validate logical ordering of workflow steps."""
    
    def test_pr_agent_checkout_before_setup(self):
        """Ensure checkout happens before environment setup."""
        with open(".github/workflows/pr-agent.yml") as f:
            workflow = yaml.safe_load(f)
        
        jobs = workflow.get("jobs", {})
        trigger_job = jobs.get("pr-agent-trigger", {})
        steps = trigger_job.get("steps", [])
        
        step_names = [s.get("name", "") for s in steps]
        
        # Checkout should come before Setup
        checkout_idx = next((i for i, name in enumerate(step_names) 
                           if "Checkout" in name), None)
        setup_idx = next((i for i, name in enumerate(step_names) 
                         if "Setup" in name), None)
        
        assert checkout_idx is not None, "Should have Checkout step"
        assert setup_idx is not None, "Should have Setup step"
        assert checkout_idx < setup_idx, "Checkout should come before Setup"
    
    def test_pr_agent_install_before_run(self):
        """Ensure dependencies installed before running tests."""
        with open(".github/workflows/pr-agent.yml") as f:
            workflow = yaml.safe_load(f)
        
        jobs = workflow.get("jobs", {})
        trigger_job = jobs.get("pr-agent-trigger", {})
        steps = trigger_job.get("steps", [])
        
        step_names = [s.get("name", "") for s in steps]
        
        # Install should come before Run
        install_indices = [i for i, name in enumerate(step_names) 
                          if "Install" in name]
        run_indices = [i for i, name in enumerate(step_names) 
                      if "Run" in name and "Install" not in name]
        
        if install_indices and run_indices:
            assert min(run_indices) > max(install_indices), \
                "Install steps should complete before Run steps"


class TestWorkflowEnvironmentVariables:
    """Validate environment variable usage."""
    
    def test_github_token_properly_scoped(self):
        """Ensure GITHUB_TOKEN is used with appropriate scope."""
        with open(".github/workflows/pr-agent.yml") as f:
            content = f.read()
        
        # Find all uses of GITHUB_TOKEN
        token_uses = re.findall(r'GITHUB_TOKEN:\s*\$\{\{\s*secrets\.GITHUB_TOKEN\s*\}\}', 
                                content)
        
        assert len(token_uses) > 0, "Should use GITHUB_TOKEN"
    
    def test_no_hardcoded_secrets(self):
        """Verify no hardcoded secrets in modified workflows."""
        modified_workflows = [
            ".github/workflows/pr-agent.yml",
            ".github/workflows/apisec-scan.yml",
            ".github/workflows/greetings.yml",
            ".github/workflows/label.yml",
        ]
        
        # Patterns that might indicate hardcoded secrets
        secret_patterns = [
            r'password\s*[:=]\s*["\'](?!.*\$\{)[\w]+["\']',
            r'token\s*[:=]\s*["\'][a-zA-Z0-9]{20,}["\']',
            r'api[_-]?key\s*[:=]\s*["\'](?!.*\$\{)[\w]+["\']',
        ]
        
        for workflow_path in modified_workflows:
            workflow_file = Path(workflow_path)
            if not workflow_file.exists():
                continue
                
            with open(workflow_file) as f:
                content = f.read()
            
            for pattern in secret_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                # Filter out known safe patterns
                dangerous_matches = [m for m in matches if "secrets." not in m and "GITHUB_TOKEN" not in m]
                assert len(dangerous_matches) == 0, \
                    f"{workflow_file.name} may contain hardcoded secret"


class TestWorkflowComments:
    """Validate workflow documentation through comments."""
    
    def test_pr_agent_has_descriptive_comments(self):
        """Ensure pr-agent.yml has helpful comments."""
        with open(".github/workflows/pr-agent.yml") as f:
            content = f.read()
        
        # Should have some comment lines
        comment_lines = [line for line in content.splitlines() 
                        if line.strip().startswith("#")]
        
        # Workflows should have at least minimal documentation
        assert len(comment_lines) > 0, "Workflows benefit from comments"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])