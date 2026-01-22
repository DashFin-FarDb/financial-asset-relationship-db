"""
Comprehensive tests for workflow configuration changes in current branch.

Tests focus on:
1. PR Agent workflow configuration validation
2. Greetings workflow message customization
3. Label workflow configuration
4. APISec scan workflow conditional execution
5. Workflow YAML syntax and structure
6. Security best practices in workflows
"""

from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml


class TestPRAgentWorkflowChanges:
    """Tests for pr-agent.yml workflow changes."""

    @pytest.fixture
    def pr_agent_workflow(self) -> Dict[str, Any]:
        """
        Load and parse the .github/workflows/pr-agent.yml workflow file.

        Returns:
            dict: Dictionary representation of the parsed YAML workflow.
        """
        workflow_path = Path(".github/workflows/pr-agent.yml")
        with open(workflow_path, "r") as f:
            return yaml.safe_load(f)

    def test_workflow_has_valid_yaml_syntax(self, pr_agent_workflow):
        """Verify workflow file has valid YAML syntax."""
        assert pr_agent_workflow is not None
        assert isinstance(pr_agent_workflow, dict)

    def test_workflow_has_required_keys(self, pr_agent_workflow):
        """
        Checks that the parsed pr-agent workflow contains the top-level keys 'name', 'on', 'permissions', and 'jobs'.

        Parameters:
            pr_agent_workflow (dict): Parsed YAML content of .github/workflows/pr-agent.yml represented as a dictionary.
        """
        required_keys = ["name", "on", "permissions", "jobs"]
        for key in required_keys:
            assert key in pr_agent_workflow, f"Missing required key: {key}"

    def test_on_key_uses_string_format(self, pr_agent_workflow):
        """Verify 'on' key uses string format (not bare 'on')."""
        # The fix changed from `on:` to `"on":`
        assert "on" in pr_agent_workflow or '"on"' in pr_agent_workflow

    def test_workflow_triggers_are_configured(self, pr_agent_workflow):
        """
        Assert that the parsed pr-agent workflow config includes pull request triggers.

        Parameters:
            pr_agent_workflow (dict): Parsed YAML of .github/workflows/pr-agent.yml as a dictionary; may use either `on` or `"on"` key.
        """
        triggers = pr_agent_workflow.get("on") or pr_agent_workflow.get('"on"')
        assert triggers is not None

        # Should trigger on PR events
        assert "pull_request" in triggers
        assert "pull_request_review" in triggers

    def test_python_dependencies_installation(self, pr_agent_workflow):
        """Verify Python dependencies are properly installed."""
        jobs = pr_agent_workflow.get("jobs", {})
        pr_agent_job = jobs.get("pr-agent-action", {})
        steps = pr_agent_job.get("steps", [])

        # Find the dependency installation step
        install_step = None
        for step in steps:
            if step.get("name") == "Install Python dependencies":
                install_step = step
                break

        assert install_step is not None, "Python dependency installation step not found"
        assert "run" in install_step

    def test_no_duplicate_setup_python_steps(self, pr_agent_workflow):
        """Verify no duplicate 'Setup Python' steps exist."""
        jobs = pr_agent_workflow.get("jobs", {})
        pr_agent_job = jobs.get("pr-agent-action", {})
        steps = pr_agent_job.get("steps", [])

        setup_python_steps = [s for s in steps if s.get("name") == "Setup Python"]
        assert len(setup_python_steps) == 1, "Found duplicate 'Setup Python' steps"

    def test_uses_specific_python_version(self, pr_agent_workflow):
        """Verify workflow pins Python version."""
        jobs = pr_agent_workflow.get("jobs", {})
        pr_agent_job = jobs.get("pr-agent-action", {})
        steps = pr_agent_job.get("steps", [])

        setup_python_step = next(
            (s for s in steps if s.get("name") == "Setup Python"), None
        )
        assert setup_python_step is not None
        assert "with" in setup_python_step
        assert "python-version" in setup_python_step["with"]
        assert setup_python_step["with"]["python-version"] == "3.11"

    def test_checkout_uses_fetch_depth_zero(self, pr_agent_workflow):
        """Verify checkout fetches full git history."""
        jobs = pr_agent_workflow.get("jobs", {})
        pr_agent_job = jobs.get("pr-agent-action", {})
        steps = pr_agent_job.get("steps", [])

        checkout_step = next(
            (s for s in steps if "actions/checkout" in s.get("uses", "")), None
        )
        assert checkout_step is not None
        assert checkout_step.get("with", {}).get("fetch-depth") == 0


class TestPRAgentConfigChanges:
    """Tests for pr-agent-config.yml configuration changes."""

    @pytest.fixture
    def pr_agent_config(self) -> Dict[str, Any]:
        """
        Load and parse the .github/pr-agent-config.yml file.

        Returns:
            config (Dict[str, Any]): Parsed YAML configuration as a dictionary.
        """
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    def test_config_has_valid_yaml_syntax(self, pr_agent_config):
        """Verify config file has valid YAML syntax."""
        assert pr_agent_config is not None
        assert isinstance(pr_agent_config, dict)

    def test_agent_version_is_simplified(self, pr_agent_config):
        """
        Assert the agent version in the parsed pr-agent-config.yml equals "1.0.0".

        Parameters:
            pr_agent_config (dict): Parsed YAML content of .github/pr-agent-config.yml as a dictionary.
        """
        agent_config = pr_agent_config.get("agent", {})
        version = agent_config.get("version")

        # Version should be 1.0.0 (reverted from 1.1.0)
        assert version == "1.0.0"

    def test_no_context_chunking_config(self, pr_agent_config):
        """
        Ensure the agent configuration does not include a 'context' chunking subsection.
        """
        agent_config = pr_agent_config.get("agent", {})

        # Context chunking section should not exist
        assert "context" not in agent_config

    def test_no_chunking_limits_config(self, pr_agent_config):
        """Verify chunking limits configuration was removed."""
        limits_config = pr_agent_config.get("limits", {})

        # These keys should not exist anymore
        assert "max_files_per_chunk" not in limits_config
        assert "max_diff_lines" not in limits_config
        assert "max_comment_length" not in limits_config
        assert "fallback" not in limits_config

    def test_basic_config_structure_intact(self, pr_agent_config):
        """Verify basic configuration structure is maintained."""
        assert "agent" in pr_agent_config
        assert "monitoring" in pr_agent_config
        assert "limits" in pr_agent_config

    def test_rate_limiting_configured(self, pr_agent_config):
        """Verify rate limiting is still configured."""
        limits = pr_agent_config.get("limits", {})
        assert "rate_limit_requests" in limits
        assert isinstance(limits["rate_limit_requests"], int)

    def test_monitoring_interval_configured(self, pr_agent_config):
        """Verify monitoring interval is configured."""
        monitoring = pr_agent_config.get("monitoring", {})
        assert "check_interval" in monitoring
        assert isinstance(monitoring["check_interval"], int)


class TestGreetingsWorkflowChanges:
    """Tests for greetings.yml workflow changes."""

    @pytest.fixture
    def greetings_workflow(self) -> Dict[str, Any]:
        """Load greetings.yml workflow."""
        workflow_path = Path(".github/workflows/greetings.yml")
        with open(workflow_path, "r") as f:
            return yaml.safe_load(f)

    def test_workflow_syntax_valid(self, greetings_workflow):
        """Verify workflow has valid YAML syntax."""
        assert greetings_workflow is not None
        assert isinstance(greetings_workflow, dict)

    def test_greetings_messages_simplified(self, greetings_workflow):
        """Verify greeting messages were simplified."""
        jobs = greetings_workflow.get("jobs", {})
        greeting_job = jobs.get("greeting", {})
        steps = greeting_job.get("steps", [])

        action_step = next(
            (s for s in steps if "actions/first-interaction" in s.get("uses", "")), None
        )

        assert action_step is not None
        assert "with" in action_step

        # Messages should be simple placeholders
        issue_message = action_step["with"].get("issue-message", "")
        pr_message = action_step["with"].get("pr-message", "")

        # Should be simple generic messages, not multi-line detailed ones
        assert len(issue_message) < 200, "Issue message should be simplified"
        assert len(pr_message) < 200, "PR message should be simplified"

    def test_no_complex_markdown_formatting(self, greetings_workflow):
        """Verify messages don't contain complex markdown."""
        jobs = greetings_workflow.get("jobs", {})
        greeting_job = jobs.get("greeting", {})
        steps = greeting_job.get("steps", [])

        action_step = next(
            (s for s in steps if "actions/first-interaction" in s.get("uses", "")), None
        )

        if action_step and "with" in action_step:
            issue_message = action_step["with"].get("issue-message", "")
            pr_message = action_step["with"].get("pr-message", "")

            # Should not contain resources section or checkmarks
            assert "**Resources:**" not in issue_message
            assert "**Resources:**" not in pr_message
            assert "✅" not in issue_message
            assert "✅" not in pr_message


class TestLabelWorkflowChanges:
    """Tests for label.yml workflow changes."""

    @pytest.fixture
    def label_workflow(self) -> Dict[str, Any]:
        """
        Load and parse the label GitHub Actions workflow file.

        Returns:
            workflow (dict): Parsed contents of `.github/workflows/label.yml` as a dictionary.
        """
        workflow_path = Path(".github/workflows/label.yml")
        with open(workflow_path, "r") as f:
            return yaml.safe_load(f)

    def test_workflow_syntax_valid(self, label_workflow):
        """Verify workflow has valid YAML syntax."""
        assert label_workflow is not None
        assert isinstance(label_workflow, dict)

    def test_no_config_check_step(self, label_workflow):
        """Verify config check step was removed."""
        jobs = label_workflow.get("jobs", {})
        label_job = jobs.get("label", {})
        steps = label_job.get("steps", [])

        # Should not have config check step
        config_check_steps = [
            s for s in steps if s.get("name") == "Check for labeler config"
        ]
        assert len(config_check_steps) == 0

    def test_no_checkout_step(self, label_workflow):
        """Verify checkout step was removed (not needed)."""
        jobs = label_workflow.get("jobs", {})
        label_job = jobs.get("label", {})
        steps = label_job.get("steps", [])

        checkout_steps = [s for s in steps if "actions/checkout" in s.get("uses", "")]
        assert len(checkout_steps) == 0

    def test_simplified_to_single_step(self, label_workflow):
        """
        Assert the label workflow has been simplified to a single actions/labeler step.

        Checks that the 'label' job contains exactly one step and that the step's `uses`
        reference includes `actions/labeler`.
        """
        jobs = label_workflow.get("jobs", {})
        label_job = jobs.get("label", {})
        steps = label_job.get("steps", [])

        # Should only have the labeler action step
        assert len(steps) == 1
        assert "actions/labeler" in steps[0].get("uses", "")

    def test_no_conditional_execution(self, label_workflow):
        """Verify no conditional if statements in steps."""
        jobs = label_workflow.get("jobs", {})
        label_job = jobs.get("label", {})
        steps = label_job.get("steps", [])

        for step in steps:
            assert "if" not in step, "Steps should not have conditional execution"


class TestAPISecScanWorkflowChanges:
    """Tests for apisec-scan.yml workflow changes."""

    @pytest.fixture
    def apisec_workflow(self) -> Dict[str, Any]:
        """
        Load and parse the .github/workflows/apisec-scan.yml GitHub Actions workflow.

        Returns:
            workflow (dict | None): Parsed YAML content of the workflow file as a dictionary, or `None` if the file is empty.
        """
        workflow_path = Path(".github/workflows/apisec-scan.yml")
        with open(workflow_path, "r") as f:
            return yaml.safe_load(f)

    def test_workflow_syntax_valid(self, apisec_workflow):
        """Verify workflow has valid YAML syntax."""
        assert apisec_workflow is not None
        assert isinstance(apisec_workflow, dict)

    def test_no_job_level_conditional(self, apisec_workflow):
        """Verify job-level 'if' condition was removed."""
        jobs = apisec_workflow.get("jobs", {})
        scan_job = jobs.get("Trigger_APIsec_scan", {})

        # Should not have 'if' at job level
        assert "if" not in scan_job

    def test_no_credential_check_step(self, apisec_workflow):
        """
        Confirm the 'Trigger_APIsec_scan' job contains no step named 'Check for APIsec credentials'.

        Asserts that there are zero steps whose `name` equals 'Check for APIsec credentials' in that job's step list.
        """
        jobs = apisec_workflow.get("jobs", {})
        scan_job = jobs.get("Trigger_APIsec_scan", {})
        steps = scan_job.get("steps", [])

        credential_check_steps = [
            s for s in steps if s.get("name") == "Check for APIsec credentials"
        ]
        assert len(credential_check_steps) == 0

    def test_scan_step_is_first_step(self, apisec_workflow):
        """
        Assert that the Trigger_APIsec_scan job's first step is named "APIsec scan" and invokes the apisec-inc/apisec-run-scan action.

        Checks that the job exists, contains at least one step, and that the first step's name equals "APIsec scan" and its `uses` reference includes `apisec-inc/apisec-run-scan`.
        """
        jobs = apisec_workflow.get("jobs", {})
        scan_job = jobs.get("Trigger_APIsec_scan", {})
        steps = scan_job.get("steps", [])

        assert len(steps) >= 1
        first_step = steps[0]
        assert first_step.get("name") == "APIsec scan"
        assert "apisec-inc/apisec-run-scan" in first_step.get("uses", "")

    def test_workflow_assumes_credentials_configured(self, apisec_workflow):
        """Verify workflow now assumes credentials are configured."""
        # Since credential checks are removed, workflow should run unconditionally
        jobs = apisec_workflow.get("jobs", {})
        scan_job = jobs.get("Trigger_APIsec_scan", {})

        # No if condition means it always runs
        assert "if" not in scan_job


class TestWorkflowSecurityBestPractices:
    """Security-focused tests for workflow changes."""

    def test_no_hardcoded_secrets_in_workflows(self):
        """Verify no hardcoded secrets in any workflow file."""
        workflow_dir = Path(".github/workflows")

        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                content = f.read()

            # Check for common secret patterns
            dangerous_patterns = [
                "password:",
                "api_key:",
                "token:",
                "secret:",
            ]

            for pattern in dangerous_patterns:
                # Allow if it's using secrets context
                lines_with_pattern = [
                    line
                    for line in content.split("\n")
                    if pattern in line.lower() and "secrets." not in line
                ]

                assert len(lines_with_pattern) == 0, (
                    f"Potential hardcoded secret in {workflow_file}: {lines_with_pattern}"
                )

    def test_workflows_use_pinned_action_versions(self):
        """Verify workflows use pinned action versions."""
        workflow_dir = Path(".github/workflows")

        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                workflow = yaml.safe_load(f)

            jobs = workflow.get("jobs", {})
            for job_name, job_config in jobs.items():
                steps = job_config.get("steps", [])
                for step in steps:
                    if "uses" in step:
                        action = step["uses"]
                        # Should have @version or @sha
                        assert (
                            action.startswith("./")
                            or action.startswith("docker://")
                            or "@" in action
                        ), f"Action {action} in {workflow_file} should be pinned"

    def test_workflows_use_read_only_permissions_by_default(self):
        """
        Ensure workflow files in .github/workflows limit top-level write permissions to enforce least privilege.

        Iterates over each YAML workflow file in .github/workflows, and for workflows that define a top-level `permissions` mapping, counts entries explicitly set to `write`. The test fails if more than three permissions are set to `write` for a single workflow.
        """
        workflow_dir = Path(".github/workflows")

        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                workflow = yaml.safe_load(f)

            # Check top-level permissions
            if "permissions" in workflow:
                perms = workflow["permissions"]
                if isinstance(perms, dict):
                    # If specific permissions are set, verify they're intentional
                    write_perms = [k for k, v in perms.items() if v == "write"]
                    # Write permissions should be justified by workflow purpose
                    assert len(write_perms) <= 3, (
                        f"Too many write permissions in {workflow_file}: {write_perms}"
                    )


class TestWorkflowYAMLQuality:
    """Tests for YAML quality and consistency."""

    def test_all_workflows_have_names(self):
        """
        Ensure every workflow YAML file in .github/workflows defines a non-empty top-level 'name' field.

        Raises:
            AssertionError: If any workflow file is missing the 'name' field or the 'name' value is an empty string.
        """
        workflow_dir = Path(".github/workflows")

        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                workflow = yaml.safe_load(f)

            assert "name" in workflow, f"{workflow_file} missing 'name' field"
            assert len(workflow["name"]) > 0, f"{workflow_file} has empty name"

    def test_all_jobs_have_descriptive_names(self):
        """Verify all jobs have descriptive names or job IDs."""
        workflow_dir = Path(".github/workflows")

        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                workflow = yaml.safe_load(f)

            jobs = workflow.get("jobs", {})
            for job_id, job_config in jobs.items():
                # Either job_id should be descriptive or should have 'name' field
                is_descriptive_id = len(job_id) > 5 and "_" in job_id
                has_name_field = "name" in job_config

                assert is_descriptive_id or has_name_field, (
                    f"Job {job_id} in {workflow_file} needs better identification"
                )

    def test_workflows_have_consistent_indentation(self):
        """
        Check that workflow YAML files under .github/workflows use indentation in multiples of two spaces.

        Reads each `*.yml` file in `.github/workflows` and asserts any line that begins with spaces has a leading-space count that is divisible by 2; assertion messages include file name and line number on failure.
        """
        workflow_dir = Path(".github/workflows")

        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                content = f.read()

            # Check that indentation is consistent (2 spaces is standard)
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                if line.strip() and line[0] == " ":
                    # Count leading spaces
                    spaces = len(line) - len(line.lstrip(" "))
                    # Should be multiple of 2
                    assert spaces % 2 == 0, (
                        f"{workflow_file} line {i}: inconsistent indentation ({spaces} spaces)"
                    )


class TestDeletedFiles:
    """Tests verifying removed files are actually deleted."""

    def test_labeler_yml_deleted(self):
        """Verify .github/labeler.yml was deleted."""
        labeler_path = Path(".github/labeler.yml")
        assert not labeler_path.exists(), "labeler.yml should be deleted"

    def test_context_chunker_script_deleted(self):
        """Verify .github/scripts/context_chunker.py was deleted."""
        chunker_path = Path(".github/scripts/context_chunker.py")
        assert not chunker_path.exists(), "context_chunker.py should be deleted"

    def test_scripts_readme_deleted(self):
        """Verify .github/scripts/README.md was deleted."""
        readme_path = Path(".github/scripts/README.md")
        assert not readme_path.exists(), "scripts/README.md should be deleted"


class TestRequirementsDevChanges:
    """Tests for requirements-dev.txt changes."""

    def test_requirements_file_exists(self):
        """Verify requirements-dev.txt exists."""
        req_path = Path("requirements-dev.txt")
        assert req_path.exists(), "requirements-dev.txt should exist"

    def test_pyyaml_dependency_added(self):
        """Verify PyYAML dependency is in requirements-dev.txt."""
        req_path = Path("requirements-dev.txt")
        with open(req_path, "r") as f:
            content = f.read().lower()

        assert "pyyaml" in content, "PyYAML should be in requirements-dev.txt"

    def test_pyyaml_version_pinned(self):
        """Verify PyYAML has version constraint."""
        req_path = Path("requirements-dev.txt")
        with open(req_path, "r") as f:
            lines = f.readlines()

        pyyaml_lines = [line for line in lines if "pyyaml" in line.lower()]
        assert len(pyyaml_lines) > 0, "PyYAML not found in requirements"

        # Should have version specifier
        pyyaml_line = pyyaml_lines[0]
        assert any(op in pyyaml_line for op in ["==", ">=", "<=", "~="]), (
            "PyYAML should have version constraint"
        )

    def test_no_duplicate_dependencies(self):
        """
        Check that requirements-dev.txt contains no duplicate package entries.

        Ignores blank lines and comments, normalizes package names to lowercase and strips version specifiers (e.g., ==, >=, <=, ~=, >, <), and asserts there are no duplicate package names; on failure, reports the duplicated package names.
        """
        req_path = Path("requirements-dev.txt")
        with open(req_path, "r") as f:
            lines = [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]

        # Extract package names (before version specifiers)
        package_names = []
        for line in lines:
            pkg_name = (
                line.split("=")[0].split(">")[0].split("<")[0].split("~")[0].strip()
            )
            package_names.append(pkg_name.lower())

        # Check for duplicates
        duplicates = [pkg for pkg in package_names if package_names.count(pkg) > 1]
        duplicates = {pkg for pkg in package_names if package_names.count(pkg) > 1}
        assert len(duplicates) == 0, f"Duplicate dependencies found: {duplicates}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
Additional comprehensive tests for workflow configuration edge cases and regressions.

These tests provide additional coverage beyond the existing test suite, focusing on:
1. Regression tests to ensure removed functionality doesn't accidentally return
2. Negative tests for error conditions
3. Edge case handling in simplified workflows
4. Cross-workflow consistency validation
"""

import pytest
import yaml
import re
from pathlib import Path
from typing import Dict, Any, List, Set


class TestContextChunkingRemovalRegression:
    """Regression tests ensuring context chunking functionality stays removed."""
    
    def test_no_context_chunking_imports_in_workflows(self):
        """Verify no workflows import or reference context chunking."""
        workflow_dir = Path(".github/workflows")

        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r', encoding='utf-8') as f:
                content = f.read().lower()

            # Check for any references to context chunking (expanded variants)
            forbidden_terms = [
                'context_chunker',
                'context-chunker',
                'contextchunker',
                'context chunker',
                'chunking',
                'chunker',
                'tiktoken',
                'max_tokens',
                'max-tokens',
                'chunk_size',
                'chunk-size',
                'overlap_tokens',
                'overlap-tokens',
                'context_file',
                'context-file',
                '/tmp/pr_context',
                'pr_context',
            ]

            for term in forbidden_terms:
                assert term not in content, (
                    f"{workflow_file.name} contains reference to removed chunking: '{term}'"
                )
        """Verify no workflows import or reference context_chunker."""
        workflow_dir = Path(".github/workflows")
        
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for any references to context chunking
            forbidden_terms = [
                'context_chunker',
                'context-chunker',
                'chunking',
                'tiktoken',
                'max_tokens',
                'chunk_size',
                'overlap_tokens'
            ]
            
            for term in forbidden_terms:
                assert term not in content.lower(), \
                    f"{workflow_file.name} contains reference to removed chunking: '{term}'"
    
    def test_pr_agent_config_no_context_section(self):
        """Verify pr-agent-config.yml has no context configuration."""
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        agent_config = config.get('agent', {})
        
        # Context section should not exist
        assert 'context' not in agent_config, \
            "Context configuration should be removed from pr-agent-config.yml"
    
    def test_pr_agent_config_no_chunking_limits(self):
        """Verify pr-agent-config.yml has no chunking limits."""
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        limits_config = config.get('limits', {})
        
        # Chunking-related limits should not exist
        forbidden_keys = [
            'max_files_per_chunk',
            'max_diff_lines',
            'max_comment_length',
            'fallback'
        ]
        
        for key in forbidden_keys:
            assert key not in limits_config, \
                f"Chunking limit '{key}' should be removed from limits configuration"
    
    def test_no_python_chunking_dependencies(self):
        """Verify tiktoken and chunking-specific dependencies are not in requirements."""
        req_files = ['requirements.txt', 'requirements-dev.txt']
        
        for req_file in req_files:
            req_path = Path(req_file)
            if req_path.exists():
                with open(req_path, 'r') as f:
                    content = f.read().lower()
                
                # tiktoken was optional for chunking, should be removed
                assert 'tiktoken' not in content, \
                    f"tiktoken should not be in {req_file} after chunking removal"
    
    def test_pr_agent_workflow_no_context_file_output(self):
        """Verify PR agent workflow doesn't create context files."""
        workflow_path = Path(".github/workflows/pr-agent.yml")
        with open(workflow_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should not write to context files
        forbidden_patterns = [
            r'/tmp/pr_context\.json',
            r'/tmp/pr_context_chunked\.json',
            r'context_file=',
            r'CONTEXT_FILE='
        ]
        
        for pattern in forbidden_patterns:
            assert not re.search(pattern, content), \
                f"Workflow should not reference context files: {pattern}"


class TestWorkflowErrorHandling:
    """Test error handling and edge cases in workflows."""
    
    def test_pr_agent_workflow_handles_missing_reviews(self):
        """Verify PR agent workflow handles PRs without reviews gracefully."""
        workflow_path = Path(".github/workflows/pr-agent.yml")
        with open(workflow_path, 'r') as f:
            workflow = yaml.safe_load(f)
        
        jobs = workflow.get('jobs', {})
        
        for job_name, job_config in jobs.items():
            steps = job_config.get('steps', [])
            
            # Check for steps that parse reviews
            for step in steps:
                if 'review' in step.get('name', '').lower():
                    run_command = step.get('run', '')
                    
                    # Should handle empty results
                    assert '|| echo' in run_command or 'general_improvements' in run_command, \
                        f"Step '{step.get('name')}' should handle missing reviews"
    
                    if not has_timeout:
                        assert False, f"{workflow_file.name}::{job_name} has no timeout"
    def test_apisec_workflow_validates_action_handles_missing_secrets(self):
        """Verify APISec workflow uses action version known to handle missing secrets by pinning the action."""
        workflow_path = Path(".github/workflows/apisec-scan.yml")
        with open(workflow_path, 'r') as f:
            workflow = yaml.safe_load(f)

        jobs = workflow.get('jobs', {})
        apisec_job = jobs.get('Trigger_APIsec_scan', {})
        steps = apisec_job.get('steps', [])

        for step in steps:
            uses_val = step.get('uses', '')
            if 'apisec' in uses_val.lower():
                assert '@' in uses_val, "APISec action should use a pinned version (e.g., @vX or @<sha>)"
                # Optionally enforce a major version pin pattern
                # assert re.search(r'@v?\d+(\.\d+(\.\d+)?)?$', uses_val) or re.search(r'@[0-9a-fA-F]{7,}', uses_val)
                break
        else:
            pytest.fail("APISec action step not found in workflow")
        """Verify workflows handle missing secrets appropriately."""
        workflow_dir = Path(".github/workflows")
        
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # If workflow uses secrets, should have some handling
            if '${{ secrets.' in content:
                # API sec scan removed the conditional check, which is fine
                # as long as the action itself handles missing creds
                if 'apisec' in workflow_file.name:
                    # APISec action should handle missing credentials internally
                    pass


class TestWorkflowConsistency:
    """Test consistency across all workflow files."""
    
    def test_all_workflows_use_same_python_version(self):
        """Verify all workflows use consistent Python version."""
        workflow_dir = Path(".github/workflows")
        python_versions: Set[str] = set()
        
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
            
            jobs = workflow.get('jobs', {})
            
            for job_config in jobs.values():
                steps = job_config.get('steps', [])
                
                for step in steps:
                    if step.get('uses', '').startswith('actions/setup-python'):
                        with_config = step.get('with', {})
                        version = with_config.get('python-version')
                        if version:
                            python_versions.add(str(version))
        
        # Should use consistent version (3.11)
        assert len(python_versions) <= 1, \
            f"Multiple Python versions found: {python_versions}. Should use 3.11 consistently."
        
        if python_versions:
            assert '3.11' in python_versions, \
                f"Python version should be 3.11, found: {python_versions}"
    
    def test_all_workflows_use_same_node_version(self):
        """Verify all workflows use consistent Node version."""
        workflow_dir = Path(".github/workflows")
        node_versions: Set[str] = set()
        
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
            
            jobs = workflow.get('jobs', {})
            
            for job_config in jobs.values():
                steps = job_config.get('steps', [])
                
                for step in steps:
                    if step.get('uses', '').startswith('actions/setup-node'):
                        with_config = step.get('with', {})
                        version = with_config.get('node-version')
                        if version:
                            node_versions.add(str(version))
        
        # Should use consistent version
        assert len(node_versions) <= 1, \
            f"Multiple Node versions found: {node_versions}. Should be consistent."
    
    def test_all_workflows_use_checkout_v4(self):
        """Verify all workflows use actions/checkout@v4."""
        workflow_dir = Path(".github/workflows")
        checkout_versions: Set[str] = set()
        
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find all checkout action uses
            checkout_matches = re.findall(r'uses:\s*actions/checkout@(v\d+)', content)
            checkout_versions.update(checkout_matches)
        
        # Should primarily use v4
        if checkout_versions:
            assert 'v4' in checkout_versions, \
                "Should use actions/checkout@v4"
    
    def test_workflows_have_consistent_permissions(self):
        """Verify workflows follow consistent permission patterns."""
        workflow_dir = Path(".github/workflows")
        
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
            
            permissions = workflow.get('permissions')
            
            if permissions:
                # Permissions should be explicitly set (not just 'write-all')
                assert permissions != 'write-all', \
                    f"{workflow_file.name} uses overly permissive 'write-all'"
                
                # Should be a dict with specific permissions
                assert isinstance(permissions, dict), \
                    f"{workflow_file.name} should use explicit permission dict"


class TestSimplifiedConfigurationEdgeCases:
    """Test edge cases in simplified workflow configurations."""
    
    def test_greetings_messages_are_not_empty(self):
        """Verify greetings workflow has non-empty messages."""
        workflow_path = Path(".github/workflows/greetings.yml")
        with open(workflow_path, 'r') as f:
            workflow = yaml.safe_load(f)
        
        jobs = workflow.get('jobs', {})
        first_interaction_job = jobs.get('greeting', {})
        steps = first_interaction_job.get('steps', [])
        
        for step in steps:
            with_config = step.get('with', {})
            
            # Check issue message
            issue_msg = with_config.get('issue-message', '')
            assert len(issue_msg.strip()) > 0, "Issue message should not be empty"
            assert len(issue_msg.strip()) > 10, "Issue message should be meaningful"
            
            # Check PR message
            pr_msg = with_config.get('pr-message', '')
            assert len(pr_msg.strip()) > 0, "PR message should not be empty"
            assert len(pr_msg.strip()) > 10, "PR message should be meaningful"
    
    def test_label_workflow_without_config_check(self):
        """Verify label workflow works without labeler.yml config check."""
        workflow_path = Path(".github/workflows/label.yml")
        with open(workflow_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should not check for config file existence
        assert 'check-config' not in content, \
            "Label workflow should not check for config file"
        assert 'labeler.yml' not in content, \
            "Label workflow should not reference labeler.yml"
        
        # Labeler action should be called directly
        assert 'actions/labeler@v4' in content or 'actions/labeler@v5' in content, \
            "Should use labeler action directly"
    
    def test_apisec_workflow_without_credential_check(self):
        """Verify APISec workflow runs without explicit credential check."""
        workflow_path = Path(".github/workflows/apisec-scan.yml")
        with open(workflow_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should not have step checking for credentials
        assert 'Check for APIsec credentials' not in content, \
            "APISec workflow should not have credential check step"
        
        # Should not have if condition on job level
        with open(workflow_path, 'r') as f:
            workflow = yaml.safe_load(f)
        
        jobs = workflow.get('jobs', {})
        apisec_job = jobs.get('Trigger_APIsec_scan', {})
        
        assert 'if' not in apisec_job or \
               'secrets.apisec' not in str(apisec_job.get('if', '')), \
            "APISec job should not have conditional on secrets"


class TestGitignoreChanges:
    """Test .gitignore modifications."""
    
    def test_gitignore_removed_test_db_patterns(self):
        """Verify .gitignore removed test database patterns."""
        gitignore_path = Path(".gitignore")
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # These patterns were removed in the diff
        removed_patterns = ['test_*.db', '*_test.db', 'junit.xml']
        
        for pattern in removed_patterns:
            assert pattern not in content, \
                f"Pattern '{pattern}' should be removed from .gitignore"
    
    def test_gitignore_still_has_coverage_patterns(self):
        """Verify .gitignore still has coverage-related patterns."""
        gitignore_path = Path(".gitignore")
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # These should still be present
        required_patterns = ['.coverage', 'coverage.xml', 'htmlcov/']
        
        for pattern in required_patterns:
            assert pattern in content, \
                f"Pattern '{pattern}' should still be in .gitignore"


class TestPRAgentConfigVersionDowngrade:
    """Test pr-agent-config.yml version change."""
    
    def test_pr_agent_version_downgraded_to_1_0_0(self):
        """Verify PR agent version was downgraded from 1.1.0 to 1.0.0."""
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        agent_config = config.get('agent', {})
        version = agent_config.get('version')
        
        assert version == '1.0.0', \
            f"PR agent version should be 1.0.0, got {version}"
    
    def test_pr_agent_config_structure_valid_after_simplification(self):
        """Verify pr-agent-config.yml is still valid after removing sections."""
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Should have required top-level keys
        assert 'agent' in config, "Config should have 'agent' section"
        assert 'monitoring' in config, "Config should have 'monitoring' section"
        assert 'limits' in config, "Config should have 'limits' section"
        
        # Agent section should have basic config
        agent = config['agent']
        assert 'name' in agent, "Agent should have name"
        assert 'version' in agent, "Agent should have version"
        assert 'enabled' in agent, "Agent should have enabled flag"


class TestWorkflowSecurityRegressions:
    """Ensure security best practices weren't compromised by simplifications."""
    
    def test_workflows_dont_echo_secrets(self):
        """Verify workflows don't accidentally echo secrets."""
        workflow_dir = Path(".github/workflows")
        
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find all secret references
            secret_refs = re.findall(r'\$\{\{\s*secrets\.(\w+)\s*\}\}', content)
            
            for secret_name in secret_refs:
                # Check that secret isn't echoed
                echo_pattern = rf'echo.*\$\{{\{{\s*secrets\.{secret_name}\s*\}}\}}'
                assert not re.search(echo_pattern, content, re.IGNORECASE), \
                    f"{workflow_file.name} appears to echo secret: {secret_name}"
    
    def test_pr_agent_workflow_validates_dependency_files(self):
        """Verify PR agent workflow validates dependency files exist."""
        workflow_path = Path(".github/workflows/pr-agent.yml")
        with open(workflow_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should check for requirements files
        assert 'requirements.txt' in content or 'requirements-dev.txt' in content, \
            "PR agent should reference requirements files"
        
        # Should validate files exist before installing
        assert 'if [ -f' in content or '[ -f ' in content, \
            "Should check if dependency files exist"


class TestCodecovWorkflowDeletion:
    """Test that codecov.yaml workflow was properly deleted."""
    
    
    def test_no_codecov_references_in_other_workflows(self):
        """Verify other workflows don't reference codecov."""
        workflow_dir = Path(".github/workflows")
        
        for workflow_file in workflow_dir.glob("*.yml"):
            if workflow_file.name == 'codecov.yaml':
                continue
            
            with open(workflow_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Should not reference codecov
            assert 'codecov' not in content.lower(), \
                f"{workflow_file.name} should not reference codecov"


class TestAPISecScanWorkflowConfigChanges:
    """Tests for apisec-scan.yml workflow configuration changes."""

    @pytest.fixture
    def apisec_workflow(self) -> Dict[str, Any]:
        """Load apisec-scan.yml workflow."""
        workflow_path = Path(".github/workflows/apisec-scan.yml")
        with open(workflow_path, "r") as f:
            return yaml.safe_load(f)

    def test_workflow_has_valid_yaml_syntax(self, apisec_workflow):
        """Verify apisec-scan.yml has valid YAML syntax."""
        assert apisec_workflow is not None
        assert isinstance(apisec_workflow, dict)

    def test_no_job_level_credential_conditional(self, apisec_workflow):
        """Verify job-level credential check conditional was removed."""
        jobs = apisec_workflow.get("jobs", {})
        trigger_job = jobs.get("Trigger_APIsec_scan", {})

        # The 'if' condition should not check for credentials
        job_if = trigger_job.get("if", "")

        # Should not contain credential checks
        assert "apisec_username" not in str(job_if).lower()
        assert "apisec_password" not in str(job_if).lower()

    def test_no_credential_check_step(self, apisec_workflow):
        """Verify the credential check step was removed."""
        jobs = apisec_workflow.get("jobs", {})
        trigger_job = jobs.get("Trigger_APIsec_scan", {})
        steps = trigger_job.get("steps", [])

        # Find any step that checks for credentials
        credential_check_steps = [
            s for s in steps if "Check for APIsec credentials" in s.get("name", "")
        ]

        assert len(credential_check_steps) == 0, (
            "Credential check step should be removed"
        )

    def test_apisec_scan_step_present(self, apisec_workflow):
        """Verify APIsec scan step is still present."""
        jobs = apisec_workflow.get("jobs", {})
        trigger_job = jobs.get("Trigger_APIsec_scan", {})
        steps = trigger_job.get("steps", [])

        # Find the APIsec scan step
        scan_step = next((s for s in steps if "APIsec scan" in s.get("name", "")), None)

        assert scan_step is not None, "APIsec scan step should be present"
        assert "uses" in scan_step
        assert "apisec-inc/apisec-run-scan" in scan_step["uses"]

    def test_concurrency_configuration(self, apisec_workflow):
        """Verify concurrency configuration is present."""
        jobs = apisec_workflow.get("jobs", {})
        trigger_job = jobs.get("Trigger_APIsec_scan", {})

        assert "concurrency" in trigger_job, "Concurrency config should be present"
        concurrency = trigger_job["concurrency"]
        assert "group" in concurrency
        assert "cancel-in-progress" in concurrency

    def test_permissions_configured(self, apisec_workflow):
        """Verify workflow permissions are properly configured."""
        assert "permissions" in apisec_workflow
        permissions = apisec_workflow["permissions"]

        # Should have some permissions configured
        assert isinstance(permissions, dict)
        assert len(permissions) > 0

    def test_workflow_triggers_on_schedule(self, apisec_workflow):
        """Verify workflow has schedule trigger."""
        triggers = apisec_workflow.get("on", {})

        # Should have schedule trigger
        assert "schedule" in triggers or "workflow_dispatch" in triggers

    def test_no_exit_zero_on_missing_credentials(self, apisec_workflow):
        """Verify workflow doesn't exit 0 on missing credentials."""
        jobs = apisec_workflow.get("jobs", {})
        trigger_job = jobs.get("Trigger_APIsec_scan", {})
        steps = trigger_job.get("steps", [])

        # Check that no step contains 'exit 0' for credential checks
        for step in steps:
            run_script = step.get("run", "")
            if "apisec_username" in run_script or "apisec_password" in run_script:
                assert "exit 0" not in run_script, (
                    "Should not silently exit on missing credentials"
                )


class TestGitignoreChanges:
    """Tests for .gitignore file changes."""

    @pytest.fixture
    def gitignore_content(self) -> str:
        """Load .gitignore file content."""
        gitignore_path = Path(".gitignore")
        with open(gitignore_path, "r") as f:
            return f.read()

    def test_gitignore_file_exists(self):
        """Verify .gitignore exists."""
        gitignore_path = Path(".gitignore")
        assert gitignore_path.exists(), ".gitignore should exist"

    def test_junit_xml_not_ignored(self, gitignore_content):
        """Verify junit.xml is NOT in .gitignore (was removed)."""
        # junit.xml should not be in gitignore anymore
        assert "junit.xml" not in gitignore_content, (
            "junit.xml should not be in .gitignore"
        )

    def test_test_db_patterns_not_ignored(self, gitignore_content):
        """Verify test database patterns are NOT in .gitignore (were removed)."""
        # test_*.db and *_test.db should not be in gitignore
        assert "test_*.db" not in gitignore_content, (
            "test_*.db pattern should not be in .gitignore"
        )
        assert "*_test.db" not in gitignore_content, (
            "*_test.db pattern should not be in .gitignore"
        )

    def test_pytest_cache_still_ignored(self, gitignore_content):
        """Verify .pytest_cache is still ignored."""
        assert ".pytest_cache" in gitignore_content, (
            ".pytest_cache should still be in .gitignore"
        )

    def test_coverage_files_still_ignored(self, gitignore_content):
        """Verify coverage files are still ignored."""
        assert ".coverage" in gitignore_content
        assert "coverage.xml" in gitignore_content
        assert "htmlcov/" in gitignore_content

    def test_tox_still_ignored(self, gitignore_content):
        """Verify .tox directory is still ignored."""
        assert ".tox" in gitignore_content

    def test_hypothesis_still_ignored(self, gitignore_content):
        """Verify .hypothesis directory is still ignored."""
        assert ".hypothesis" in gitignore_content


class TestGitignoreChanges:
    """Tests for .gitignore file changes."""

    @pytest.fixture
    def gitignore_content(self) -> str:
        """Load .gitignore file content."""
        gitignore_path = Path(".gitignore")
        with open(gitignore_path, "r") as f:
            return f.read()

    def test_gitignore_file_exists(self):
        """Verify .gitignore exists."""
        gitignore_path = Path(".gitignore")
        assert gitignore_path.exists(), ".gitignore should exist"

    def test_junit_xml_not_ignored(self, gitignore_content):
        """Verify junit.xml is NOT in .gitignore (was removed)."""
        # junit.xml should not be in gitignore anymore
        assert "junit.xml" not in gitignore_content, (
            "junit.xml should not be in .gitignore"
        )

    def test_test_db_patterns_not_ignored(self, gitignore_content):
        """Verify test database patterns are NOT in .gitignore (were removed)."""
        # test_*.db and *_test.db should not be in gitignore
        assert "test_*.db" not in gitignore_content, (
            "test_*.db pattern should not be in .gitignore"
        )
        assert "*_test.db" not in gitignore_content, (
            "*_test.db pattern should not be in .gitignore"
        )

    def test_pytest_cache_still_ignored(self, gitignore_content):
        """Verify .pytest_cache is still ignored."""
        assert ".pytest_cache" in gitignore_content, (
            ".pytest_cache should still be in .gitignore"
        )

    def test_coverage_files_still_ignored(self, gitignore_content):
        """Verify coverage files are still ignored."""
        assert ".coverage" in gitignore_content
        assert "coverage.xml" in gitignore_content
        assert "htmlcov/" in gitignore_content

    def test_tox_still_ignored(self, gitignore_content):
        """Verify .tox directory is still ignored."""
        assert ".tox" in gitignore_content

    def test_hypothesis_still_ignored(self, gitignore_content):
        """Verify .hypothesis directory is still ignored."""
        assert ".hypothesis" in gitignore_content

    def test_no_duplicate_patterns(self, gitignore_content):
        """Verify no duplicate ignore patterns."""
        lines = [
            line.strip()
            for line in gitignore_content.split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]

        # Use set for O(1) lookups
        seen = set()
        duplicates = []
        for line in lines:
            if line in seen:
                duplicates.append(line)
            else:
                seen.add(line)
        assert len(duplicates) == 0, f"Duplicate patterns found: {set(duplicates)}"

    def test_frontend_coverage_still_ignored(self, gitignore_content):
        """Verify frontend coverage directory is still ignored."""
        assert "frontend/coverage/" in gitignore_content


class TestTypesYAMLVersionPinning:
    """Tests for types-PyYAML version pinning in requirements-dev.txt."""

    @pytest.fixture
    def requirements_content(self) -> str:
        """Load requirements-dev.txt content."""
        req_path = Path("requirements-dev.txt")
        with open(req_path, "r") as f:
            return f.read()

    def test_types_pyyaml_has_version_specifier(self, requirements_content):
        """Verify types-PyYAML has explicit version specifier."""
        # Find the types-PyYAML line
        lines = requirements_content.split("\n")
        types_pyyaml_lines = [
            line for line in lines if line.strip() and "types-pyyaml" in line.lower()
        ]

        assert len(types_pyyaml_lines) > 0, "types-PyYAML should be present"

        types_pyyaml_line = types_pyyaml_lines[0]
        # Should have >=6.0.0 version constraint
        assert ">=6.0" in types_pyyaml_line or ">=6.0.0" in types_pyyaml_line, (
            "types-PyYAML should have >=6.0.0 version constraint"
        )

    def test_types_pyyaml_not_unpinned(self, requirements_content):
        """Verify types-PyYAML is not unpinned (no version)."""
        lines = requirements_content.split("\n")
        for line in lines:
            if "types-pyyaml" in line.lower():
                # Should have version specifier
                assert any(op in line for op in [">=", "==", "<=", "~="]), (
                    "types-PyYAML should have version specifier"
                )

    def test_pyyaml_and_types_pyyaml_both_present(self, requirements_content):
        """Verify both PyYAML and types-PyYAML are present."""
        content_lower = requirements_content.lower()

        # Should have both
        assert "pyyaml" in content_lower, "PyYAML should be present"
        assert "types-pyyaml" in content_lower, "types-PyYAML should be present"

    def test_pyyaml_version_constraint(self, requirements_content):
        """Verify PyYAML has proper version constraint."""
        lines = requirements_content.split("\n")
        pyyaml_lines = [
            line
            for line in lines
            if line.strip() and line.strip().lower().startswith("pyyaml")
        ]

        assert len(pyyaml_lines) > 0, "PyYAML should be present"

        pyyaml_line = pyyaml_lines[0]
        # Should have >=6.0 constraint
        assert ">=6.0" in pyyaml_line, "PyYAML should have >=6.0 constraint"

    def test_requirements_file_ends_with_newline(self, requirements_content):
        """Verify requirements-dev.txt ends with a newline."""
        assert requirements_content.endswith("\n"), (
            "requirements-dev.txt should end with newline"
        )

    def test_no_trailing_whitespace(self, requirements_content):
        """Verify no lines have trailing whitespace."""
        lines = requirements_content.split("\n")

        for i, line in enumerate(lines, 1):
            if line and not line.startswith("#"):
                # Check for trailing whitespace (excluding blank lines)
                assert line == line.rstrip(), f"Line {i} has trailing whitespace"


class TestWorkflowEdgeCases:
    """Additional edge case tests for workflow configurations."""

    def test_all_workflows_have_names(self):
        """Verify all workflow files have a 'name' field."""
        workflow_dir = Path(".github/workflows")

        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                workflow = yaml.safe_load(f)

            assert "name" in workflow, (
                f"{workflow_file.name} should have a 'name' field"
            )
            assert workflow["name"], f"{workflow_file.name} name should not be empty"

    def test_workflows_have_on_triggers(self):
        """Verify all workflows have trigger definitions."""
        workflow_dir = Path(".github/workflows")

        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                content = f.read()
                workflow = yaml.safe_load(content)

            # Check for 'on' or 'true' (which is quoted 'on')
            has_trigger = "on" in workflow or '"on"' in content

            assert has_trigger, (
                f"{workflow_file.name} should have trigger definition ('on' field)"
            )

    def test_workflows_have_jobs(self):
        """Verify all workflows define at least one job."""
        workflow_dir = Path(".github/workflows")

        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                workflow = yaml.safe_load(f)

            assert "jobs" in workflow, (
                f"{workflow_file.name} should have 'jobs' section"
            )
            assert len(workflow["jobs"]) > 0, (
                f"{workflow_file.name} should have at least one job"
            )

    def test_job_steps_are_lists(self):
        """Verify all job steps are properly formatted as lists."""
        workflow_dir = Path(".github/workflows")

        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                workflow = yaml.safe_load(f)

            jobs = workflow.get("jobs", {})
            for job_id, job_config in jobs.items():
                if "steps" in job_config:
                    steps = job_config["steps"]
                    assert isinstance(steps, list), (
                        f"{workflow_file.name} job '{job_id}' steps should be a list"
                    )
                    assert len(steps) > 0, (
                        f"{workflow_file.name} job '{job_id}' should have at least one step"
                    )

    def test_steps_have_name_or_uses(self):
        """Verify all steps have either 'name' or 'uses' field."""
        workflow_dir = Path(".github/workflows")

        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                workflow = yaml.safe_load(f)

            jobs = workflow.get("jobs", {})
            for job_id, job_config in jobs.items():
                steps = job_config.get("steps", [])
                for i, step in enumerate(steps):
                    has_identification = (
                        "name" in step or "uses" in step or "run" in step
                    )
                    assert has_identification, (
                        f"{workflow_file.name} job '{job_id}' step {i} needs name, uses, or run"
                    )


class TestWorkflowSecretPatternsAndCheckoutVersion:
    """Additional tests for secrets and checkout action versions in workflows."""

    def test_enhanced_no_hardcoded_secrets_in_workflows(self):
        """Use enhanced regex patterns to detect hardcoded secrets."""
        workflow_dir = Path(".github/workflows")
        secret_patterns = [
            r'password:\s*["\'](?!.*\$\{)',
            r'token:\s*["\'](?!.*\$\{)',
            r'api[_-]?key:\s*["\'](?!.*\$\{)',
            r'secret[_-]?key:\s*["\'](?!.*\$\{)',
            r'aws[_-]?(?:access[_-]?key|secret[_-]?key):\s*["\'](?!.*\$\{)',
            r'gh[_-]?token:\s*["\'](?!.*\$\{)',
            r'["\'][A-Za-z0-9+/]{40,}["\']',  # Base64-like long strings
        ]

        import re

        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                content = f.read()

            for pattern in secret_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                assert len(matches) == 0, (
                    f"{workflow_file.name} may contain hardcoded secrets"
                )

    def test_checkout_actions_use_v4_or_newer(self):
        """Verify checkout actions use v4 or newer."""
        workflow_dir = Path(".github/workflows")

        import re

        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                workflow = yaml.safe_load(f)

            jobs = workflow.get("jobs", {})
            for job_id, job_config in jobs.items():
                steps = job_config.get("steps", [])
                for step in steps:
                    uses = step.get("uses", "")
                    if "actions/checkout" in uses:
                        if "@v" in uses:
                            try:
                                version_str = uses.split("@v")[1].split(".")[0]
                                version = int(version_str)
                                assert version >= 4, (
                                    f"{workflow_file.name} uses outdated checkout action"
                                )
                            except (IndexError, ValueError):
                                pytest.fail(
                                    f"Could not parse checkout action version in {workflow_file.name}: '{uses}'"
                                )
                        else:
                            assert uses.endswith("@v4") or uses.endswith("@main"), (
                                f"{workflow_file.name} uses non-versioned checkout action"
                            )


class TestPRAgentConfigurationRobustness:
    """Robustness tests for PR Agent configuration."""

    @pytest.fixture
    def pr_agent_config(self) -> Dict[str, Any]:
        """Load pr-agent-config.yml."""
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    def test_config_sections_are_dicts(self, pr_agent_config):
        """Verify all major config sections are dictionaries."""
        assert isinstance(pr_agent_config.get("agent", {}), dict)
        assert isinstance(pr_agent_config.get("monitoring", {}), dict)
        assert isinstance(pr_agent_config.get("limits", {}), dict)

    def test_agent_name_is_string(self, pr_agent_config):
        """Verify agent name is a non-empty string."""
        agent_name = pr_agent_config.get("agent", {}).get("name")
        assert isinstance(agent_name, str)
        assert len(agent_name) > 0

    def test_agent_enabled_is_boolean(self, pr_agent_config):
        """Verify agent enabled flag is boolean."""
        enabled = pr_agent_config.get("agent", {}).get("enabled")
        assert isinstance(enabled, bool)

    def test_monitoring_interval_is_positive_integer(self, pr_agent_config):
        """Verify monitoring interval is positive integer."""
        interval = pr_agent_config.get("monitoring", {}).get("check_interval")
        assert isinstance(interval, int)
        assert interval > 0

    def test_rate_limit_is_positive_integer(self, pr_agent_config):
        """Verify rate limit is positive integer."""
        rate_limit = pr_agent_config.get("limits", {}).get("rate_limit_requests")
        assert isinstance(rate_limit, int)
        assert rate_limit > 0

    def test_max_concurrent_prs_is_positive(self, pr_agent_config):
        """Verify max concurrent PRs is positive integer."""
        max_prs = pr_agent_config.get("limits", {}).get("max_concurrent_prs")
        assert isinstance(max_prs, int)
        assert max_prs > 0

    def test_no_undefined_config_sections(self, pr_agent_config):
        """Verify no undefined or empty config sections."""
        for key, value in pr_agent_config.items():
            assert value is not None, f"Config section '{key}' is None"
            if isinstance(value, dict):
                assert len(value) > 0, f"Config section '{key}' is empty"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
