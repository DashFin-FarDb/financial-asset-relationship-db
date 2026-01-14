"""
Additional comprehensive tests for workflow environment variables and step dependencies.

This test file supplements existing workflow tests with focus on:
- Environment variable naming consistency after removing chunking
- Step execution order and dependencies
- Error handling and fallback scenarios
- Regression prevention for simplification changes
"""

import re
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

WORKFLOWS_DIR = Path(".github/workflows")
CONFIG_FILE = Path(".github/pr-agent-config.yml")


# --- Shared Fixtures ---


@pytest.fixture(scope="module")
def pr_agent_workflow_data() -> Dict[str, Any]:
    """Load pr-agent.yml workflow once for the module."""
    path = WORKFLOWS_DIR / "pr-agent.yml"
    if not path.exists():
        pytest.fail("pr-agent.yml not found")
    with open(path, "r") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def apisec_workflow_data() -> Dict[str, Any]:
    """Load apisec-scan.yml workflow once for the module."""
    path = WORKFLOWS_DIR / "apisec-scan.yml"
    if not path.exists():
        pytest.fail("apisec-scan.yml not found")
    with open(path, "r") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def pr_agent_config_data() -> Dict[str, Any]:
    """Load pr-agent-config.yml once for the module."""
    if not CONFIG_FILE.exists():
        pytest.fail("pr-agent-config.yml not found")
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f)


# --- Test Classes ---


class TestWorkflowEnvironmentVariables:
    """Test environment variable usage and naming in workflows."""

    def test_no_chunking_env_vars_in_pr_agent(self, pr_agent_workflow_data: Dict[str, Any]):
        """Verify chunking-related environment variables are removed."""
        workflow_str = yaml.dump(pr_agent_workflow_data)

        # These environment variables should not exist after simplification
        forbidden_env_vars = [
            "CONTEXT_SIZE",
            "CHUNKED",
            "CONTEXT_FILE",
            "MAX_FILES_PER_CHUNK",
            "CHUNK_SIZE",
            "OVERLAP_TOKENS",
        ]

        for env_var in forbidden_env_vars:
            assert env_var not in workflow_str, f"Found removed env var '{env_var}' in simplified workflow"

    def test_action_items_env_var_exists(self, pr_agent_workflow_data: Dict[str, Any]):
        """Verify ACTION_ITEMS environment variable is properly used."""
        job = pr_agent_workflow_data["jobs"].get("pr-agent-trigger")
        assert job, "Job 'pr-agent-trigger' not found"

        # Find the parse comments step
        parse_step = None
        for step in job["steps"]:
            name = step.get("name", "").lower()
            if "parse" in name and "comment" in name:
                parse_step = step
                break

        assert parse_step is not None, "Parse comments step should exist"

        # Should output action_items
        assert "action_items=" in parse_step.get("run", ""), "Parse step should set action_items output"

    def test_github_token_env_properly_scoped(self, pr_agent_workflow_data: Dict[str, Any]):
        """Verify GITHUB_TOKEN is only used in steps that need it."""
        job = pr_agent_workflow_data["jobs"].get("pr-agent-trigger")
        assert job, "Job 'pr-agent-trigger' not found"

        for step in job["steps"]:
            step_name = step.get("name", "")
            has_github_api_call = "gh api" in step.get("run", "")
            has_env_token = "GITHUB_TOKEN" in str(step.get("env", {}))

            if has_github_api_call:
                assert has_env_token, f"Step '{step_name}' uses gh api but doesn't set GITHUB_TOKEN"

    def test_step_outputs_referenced_correctly(self, pr_agent_workflow_data: Dict[str, Any]):
        """Verify step outputs are referenced with correct syntax."""
        workflow_str = yaml.dump(pr_agent_workflow_data)

        # Find all step output references
        output_refs = re.findall(r"\$\{\{\s*steps\.([^.]+)\.outputs\.([^}\s]+)\s*\}\}", workflow_str)

        # Verify they follow naming convention
        for step_id, output_name in output_refs:
            # Step IDs should use kebab-case
            assert re.match(r"^[a-z][a-z0-9-]*$", step_id), f"Step ID '{step_id}' should use kebab-case"

            # Output names should use snake_case
            assert re.match(r"^[a-z][a-z0-9_]*$", output_name), f"Output name '{output_name}' should use snake_case"


class TestWorkflowStepDependencies:
    """Test step execution order and dependencies."""

    def test_checkout_before_any_code_operations(self, pr_agent_workflow_data: Dict[str, Any]):
        """Verify checkout happens before any code operations."""
        job = pr_agent_workflow_data["jobs"].get("pr-agent-trigger")
        steps = job["steps"]

        checkout_index = None
        code_op_index = None

        for i, step in enumerate(steps):
            name = step.get("name", "").lower()
            uses = step.get("uses", "").lower()

            if "checkout" in name or "checkout" in uses:
                checkout_index = i

            if any(keyword in step.get("run", "") for keyword in ["pip install", "npm install", "pytest", "flake8"]):
                if code_op_index is None:
                    code_op_index = i

        assert checkout_index is not None, "Checkout step should exist"
        if code_op_index is not None:
            assert checkout_index < code_op_index, "Checkout must happen before code operations"

    def test_python_setup_before_python_commands(self, pr_agent_workflow_data: Dict[str, Any]):
        """Verify Python setup happens before Python commands."""
        job = pr_agent_workflow_data["jobs"].get("pr-agent-trigger")
        steps = job["steps"]

        setup_python_index = None
        python_command_index = None

        for i, step in enumerate(steps):
            name = step.get("name", "").lower()
            uses = step.get("uses", "")
            run = step.get("run", "")

            if "setup" in name and "python" in name:
                setup_python_index = i

            if "python" in run or "pip" in run or "pytest" in run:
                if python_command_index is None:
                    python_command_index = i

        if python_command_index is not None:
            assert setup_python_index is not None, "Python setup step should exist"
            assert setup_python_index < python_command_index, "Python setup must happen before Python commands"

    def test_dependencies_installed_before_tests(self, pr_agent_workflow_data: Dict[str, Any]):
        """Verify dependencies are installed before running tests."""
        job = pr_agent_workflow_data["jobs"].get("pr-agent-trigger")
        steps = job["steps"]

        install_index = None
        test_index = None

        for i, step in enumerate(steps):
            name = step.get("name", "").lower()
            run = step.get("run", "")

            if "install" in name and "dependencies" in name:
                install_index = i

            if "test" in name or "pytest" in run:
                if test_index is None:
                    test_index = i

        if test_index is not None and install_index is not None:
            assert install_index < test_index, "Dependencies must be installed before running tests"

    def test_parse_comments_before_using_action_items(self, pr_agent_workflow_data: Dict[str, Any]):
        """Verify parse comments step runs before steps that use action items."""
        job = pr_agent_workflow_data["jobs"].get("pr-agent-trigger")
        steps = job["steps"]

        parse_index = None
        usage_index = None

        for i, step in enumerate(steps):
            if "id" in step and step["id"] == "parse-comments":
                parse_index = i

            run_script = step.get("run", "") + step.get("with", {}).get("script", "")
            if "steps.parse-comments.outputs.action_items" in run_script:
                if usage_index is None:
                    usage_index = i

        if usage_index is not None:
            assert parse_index is not None, "Parse comments step should exist"
            assert parse_index < usage_index, "Parse comments must run before using action_items output"


class TestWorkflowErrorHandling:
    """Test error handling and fallback scenarios in workflows."""

    def test_dependency_install_has_fallback(self, pr_agent_workflow_data: Dict[str, Any]):
        """Verify dependency installation has fallback for missing files."""
        job = pr_agent_workflow_data["jobs"].get("pr-agent-trigger")

        install_step = None
        for step in job["steps"]:
            if "Install Python dependencies" in step.get("name", ""):
                install_step = step
                break

        assert install_step is not None, "Install step should exist"
        script = install_step["run"]

        # Should check if files exist before installing
        assert (
            "if [ -f requirements.txt ]" in script or "if [ -f requirements-dev.txt ]" in script
        ), "Should check file existence before installing"

        # Should have else clause for fallback
        assert "else" in script, "Should have fallback when files don't exist"

    def test_parse_comments_handles_no_reviews(self, pr_agent_workflow_data: Dict[str, Any]):
        """Verify parse comments step handles case with no reviews."""
        job = pr_agent_workflow_data["jobs"].get("pr-agent-trigger")

        parse_step = None
        for step in job["steps"]:
            if "id" in step and step["id"] == "parse-comments":
                parse_step = step
                break

        assert parse_step is not None, "Parse step should exist"
        script = parse_step["run"]

        # Should have fallback value if no action items found
        assert (
            "general_improvements" in script or "|| echo" in script
        ), "Should have fallback value when no action items found"


class TestWorkflowSimplificationRegression:
    """Regression tests to ensure simplifications didn't break functionality."""

    def test_pr_agent_still_runs_on_review(self, pr_agent_workflow_data: Dict[str, Any]):
        """Verify PR agent still triggers on review submission."""
        triggers = pr_agent_workflow_data.get("on", {})

        assert "pull_request_review" in triggers, "Should still trigger on pull_request_review"
        assert "submitted" in triggers["pull_request_review"]["types"], "Should trigger on review submission"

    def test_pr_agent_still_parses_reviews(self, pr_agent_workflow_data: Dict[str, Any]):
        """Verify PR agent still extracts action items from reviews."""
        job = pr_agent_workflow_data["jobs"].get("pr-agent-trigger")

        parse_step = None
        for step in job["steps"]:
            if "parse" in step.get("name", "").lower():
                parse_step = step
                break

        assert parse_step is not None, "Parse step should exist"
        script = parse_step["run"]

        # Should still use gh api to fetch reviews
        assert "gh api" in script, "Should use GitHub API"
        assert "reviews" in script, "Should fetch reviews"
        assert "changes_requested" in script, "Should filter for changes requested"

    def test_apisec_removed_conditional_execution(self, apisec_workflow_data: Dict[str, Any]):
        """Verify APIsec workflow no longer has conditional credential checks."""
        job = apisec_workflow_data["jobs"].get("Trigger_APIsec_scan")
        assert job, "Job 'Trigger_APIsec_scan' not found"

        # Should not have 'if' condition checking for credentials
        job_if = job.get("if", "")
        assert "apisec_username" not in job_if, "Should not conditionally skip based on credentials"
        assert "apisec_password" not in job_if, "Should not conditionally skip based on credentials"

        # Should not have credential check step
        step_names = [step.get("name", "") for step in job["steps"]]
        assert not any("credential" in name.lower() for name in step_names), "Should not have credential check step"

    def test_apisec_still_uses_secrets(self, apisec_workflow_data: Dict[str, Any]):
        """Verify APIsec workflow still properly references secrets."""
        workflow_str = yaml.dump(apisec_workflow_data)

        # Should still use secrets for credentials
        assert "secrets.apisec_username" in workflow_str, "Should reference apisec_username secret"
        assert "secrets.apisec_password" in workflow_str, "Should reference apisec_password secret"


class TestWorkflowConfigIntegration:
    """Test integration between workflows and pr-agent-config.yml."""

    def test_config_version_matches_simplified_approach(self, pr_agent_config_data: Dict[str, Any]):
        """Verify config version reflects simplified approach."""
        agent = pr_agent_config_data.get("agent", {})
        version = agent.get("version", "")

        # Version should be 1.0.0 after simplification (removed chunking)
        assert version == "1.0.0", f"Config version should be 1.0.0 after simplification, got {version}"

    def test_config_no_longer_has_chunking_settings(self, pr_agent_config_data: Dict[str, Any]):
        """Verify config no longer has context chunking settings."""
        # Agent section should not have 'context' configuration
        agent_section = pr_agent_config_data.get("agent", {})
        assert "context" not in agent_section, "Agent section should not have 'context' configuration"

    def test_config_quality_standards_still_defined(self, pr_agent_config_data: Dict[str, Any]):
        """Verify quality standards remain after simplification."""
        assert "quality" in pr_agent_config_data, "Quality standards should still be defined"

        quality = pr_agent_config_data["quality"]
        assert "python" in quality, "Python quality standards should exist"
        assert "typescript" in quality, "TypeScript quality standards should exist"

    def test_workflow_uses_config_quality_standards(
        self, pr_agent_workflow_data: Dict[str, Any], pr_agent_config_data: Dict[str, Any]
    ):
        """Verify workflow respects quality standards from config."""
        quality = pr_agent_config_data.get("quality", {})
        python_quality = quality.get("python", {})

        job = pr_agent_workflow_data["jobs"].get("pr-agent-trigger")
        workflow_str = yaml.dump(job)

        # Check if configured linter is used
        if "linter" in python_quality:
            linter = python_quality["linter"]
            assert linter in workflow_str, f"Workflow should use configured linter '{linter}'"

        # Check if configured formatter is used
        if "formatter" in python_quality:
            formatter = python_quality["formatter"]
            assert formatter in workflow_str, f"Workflow should use configured formatter '{formatter}'"


class TestWorkflowPermissions:
    """Test workflow permission configurations remain secure."""

    def test_pr_agent_has_minimal_top_level_permissions(self, pr_agent_workflow_data: Dict[str, Any]):
        """Verify PR agent has minimal top-level permissions."""
        top_level_perms = pr_agent_workflow_data.get("permissions", {})

        # Top level should be read-only
        assert "contents" in top_level_perms, "Should define contents permission"
        assert top_level_perms["contents"] == "read", "Top-level contents should be read-only"

    def test_pr_agent_job_has_write_permissions_scoped(self, pr_agent_workflow_data: Dict[str, Any]):
        """Verify job-level write permissions are properly scoped."""
        job = pr_agent_workflow_data["jobs"].get("pr-agent-trigger")
        job_perms = job.get("permissions", {})

        # Job should have write access to issues (for comments)
        assert "issues" in job_perms, "Job should define issues permission"
        assert job_perms["issues"] == "write", "Job needs write access to post comments"


class TestWorkflowConcurrency:
    """Test workflow concurrency controls."""

    def test_apisec_has_concurrency_control(self, apisec_workflow_data: Dict[str, Any]):
        """Verify APIsec workflow has concurrency control."""
        job = apisec_workflow_data["jobs"].get("Trigger_APIsec_scan")
        assert job, "Job 'Trigger_APIsec_scan' not found"

        assert "concurrency" in job, "APIsec job should have concurrency control"

        concurrency = job["concurrency"]

        # Concurrency can be a string (group name) or a dict
        if isinstance(concurrency, dict):
            assert "group" in concurrency, "Should define concurrency group"
            assert "cancel-in-progress" in concurrency, "Should define cancel-in-progress behavior"
            assert concurrency["cancel-in-progress"] is True, "Should cancel in-progress runs to avoid duplicate scans"
        else:
            # If string, we assume basic grouping is active, but prefer explicit dict
            pass


class TestGreetingsWorkflowSimplification:
    """Test greetings workflow simplification."""

    @pytest.fixture
    def greetings_workflow(self) -> Dict[str, Any]:
        """Load greetings.yml workflow."""
        path = WORKFLOWS_DIR / "greetings.yml"
        if not path.exists():
            pytest.skip("greetings.yml not found")
        with open(path, "r") as f:
            return yaml.safe_load(f)

    def test_greetings_uses_simple_messages(self, greetings_workflow: Dict[str, Any]):
        """Verify greetings workflow uses simple placeholder messages."""
        job = greetings_workflow["jobs"]["greeting"]
        step = job["steps"][0]

        issue_message = step["with"]["issue-message"]
        pr_message = step["with"]["pr-message"]

        # Should be simple placeholder messages
        assert len(issue_message) < 100, "Issue message should be simple placeholder"
        assert len(pr_message) < 100, "PR message should be simple placeholder"

        # Should not contain markdown formatting
        assert "**" not in issue_message, "Issue message should be plain text"
        assert "**" not in pr_message, "PR message should be plain text"


class TestLabelWorkflowSimplification:
    """Test label workflow simplification."""

    @pytest.fixture
    def label_workflow(self) -> Dict[str, Any]:
        """Load label.yml workflow."""
        path = WORKFLOWS_DIR / "label.yml"
        if not path.exists():
            pytest.skip("label.yml not found")
        with open(path, "r") as f:
            return yaml.safe_load(f)

    def test_label_workflow_no_config_check(self, label_workflow: Dict[str, Any]):
        """Verify label workflow no longer checks for config file."""
        job = label_workflow["jobs"]["label"]
        step_names = [step.get("name", "") for step in job["steps"]]

        # Should not have checkout step just for checking config
        checkout_steps = [name for name in step_names if "checkout" in name.lower()]
        assert len(checkout_steps) == 0, "Should not checkout repo just to check for config"

        # Should not have config check step
        assert not any(
            "check" in name.lower() and "config" in name.lower() for name in step_names
        ), "Should not have config check step"

    def test_label_workflow_directly_runs_labeler(self, label_workflow: Dict[str, Any]):
        """Verify label workflow directly runs labeler action."""
        job = label_workflow["jobs"]["label"]
        steps = job["steps"]

        # Should have exactly one step - the labeler action
        assert len(steps) == 1, "Should have only one step after simplification"

        # That step should use the labeler action
        assert "actions/labeler" in steps[0]["uses"], "Should directly use labeler action"
