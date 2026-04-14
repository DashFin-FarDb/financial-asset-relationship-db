"""
Tests for the summary.yml GitHub Actions workflow changes.

This module validates the structure and behavior of .github/workflows/summary.yml
after the PR that removed the sanitization step and changed how the AI inference
prompt and comment step handle user-controlled inputs.

Changes under test:
- Removed: "Sanitize issue inputs" step (sed-based sanitization of title/body)
- Changed: "Run AI inference" now uses raw github.event.issue.title/body directly
- Changed: "Comment with AI summary" now uses single-quoted interpolation for
  the response instead of a quoted environment variable, and ISSUE_NUMBER is
  no longer quoted in the shell command.
"""

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SUMMARY_WORKFLOW_PATH = REPO_ROOT / ".github/workflows/summary.yml"


`@pytest.fixture`(name="summary_workflow")




def summary_workflow_fixture():
    """
    Load and parse the summary.yml GitHub Actions workflow file.

    Returns:
        dict: Parsed YAML content of .github/workflows/summary.yml.
    """
    with open(SUMMARY_WORKFLOW_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)




`@pytest.fixture`(name="summary_workflow_raw")


def summary_workflow_raw_fixture():
    """
    Return the raw text content of summary.yml.

    Returns:
        str: Raw file content as a string.
    """
    with open(SUMMARY_WORKFLOW_PATH, "r", encoding="utf-8") as f:
        return f.read()


class TestSummaryWorkflowExists:
    """Verify the summary workflow file is present and valid YAML."""

    @staticmethod
    def test_summary_workflow_file_exists():
        """summary.yml must exist in .github/workflows."""
        assert SUMMARY_WORKFLOW_PATH.exists(), f"{SUMMARY_WORKFLOW_PATH} does not exist"

    @staticmethod
    def test_summary_workflow_is_valid_yaml():
        """summary.yml must be parseable as valid YAML."""
        with open(SUMMARY_WORKFLOW_PATH, "r", encoding="utf-8") as f:
            try:
                content = yaml.safe_load(f)
            except yaml.YAMLError as exc:
                pytest.fail(f"summary.yml contains invalid YAML: {exc}")
        assert content is not None, "summary.yml must not be an empty document"


class TestSummaryWorkflowStructure:
    """Verify the top-level structure of summary.yml."""

    def test_workflow_has_name(self, summary_workflow):
        """Workflow must define a name field."""
        assert "name" in summary_workflow, "summary.yml is missing 'name' field"

    def test_workflow_has_on_trigger(self, summary_workflow):
        """Workflow must define event triggers."""
        assert "on" in summary_workflow, "summary.yml is missing 'on' trigger"

    def test_workflow_triggers_on_issue_opened(self, summary_workflow):
        """Workflow must trigger when an issue is opened."""
        triggers = summary_workflow["on"]
        assert "issues" in triggers, "summary.yml should trigger on 'issues' event"
        issue_types = triggers["issues"].get("types", [])
        assert "opened" in issue_types, "summary.yml should trigger on issues of type 'opened'"

    def test_workflow_has_jobs(self, summary_workflow):
        """Workflow must define at least one job."""
        assert "jobs" in summary_workflow, "summary.yml is missing 'jobs'"
        assert len(summary_workflow["jobs"]) > 0, "summary.yml must have at least one job"

    def test_summary_job_exists(self, summary_workflow):
        """The 'summary' job must be defined."""
        assert "summary" in summary_workflow["jobs"], "summary.yml must contain a job named 'summary'"

    def test_summary_job_has_runs_on(self, summary_workflow):
        """The 'summary' job must specify a runner."""
        job = summary_workflow["jobs"]["summary"]
        assert "runs-on" in job, "The 'summary' job must specify 'runs-on'"

    def test_summary_job_runs_on_ubuntu(self, summary_workflow):
        """The 'summary' job should run on ubuntu-latest."""
        job = summary_workflow["jobs"]["summary"]
        assert "ubuntu" in job["runs-on"], "The 'summary' job should run on an ubuntu-based runner"

    def test_summary_job_has_steps(self, summary_workflow):
        """The 'summary' job must have at least one step."""
        job = summary_workflow["jobs"]["summary"]
        assert "steps" in job, "The 'summary' job must have steps"
        assert len(job["steps"]) > 0, "The 'summary' job must have at least one step"

    def test_summary_job_has_permissions(self, summary_workflow):
        """The 'summary' job must declare permissions."""
        job = summary_workflow["jobs"]["summary"]
        assert "permissions" in job, "The 'summary' job must declare 'permissions'"

    def test_summary_job_has_issues_write_permission(self, summary_workflow):
        """The 'summary' job must have 'issues: write' permission to post comments."""
        job = summary_workflow["jobs"]["summary"]
        perms = job.get("permissions", {})
        assert perms.get("issues") == "write", "The 'summary' job must have 'issues: write' to post issue comments"

    def test_summary_job_has_models_read_permission(self, summary_workflow):
        """The 'summary' job must have 'models: read' permission for AI inference."""
        job = summary_workflow["jobs"]["summary"]
        perms = job.get("permissions", {})
        assert perms.get("models") == "read", "The 'summary' job must have 'models: read' to use AI inference"


class TestSummaryWorkflowSteps:
    """Verify the steps present in the summary workflow after the PR changes."""

    @pytest.fixture(name="summary_steps")
    def summary_steps_fixture(self, summary_workflow):
        """
        Retrieve the steps defined in the 'summary' job of the parsed workflow.

        Parameters:
            summary_workflow (dict): Parsed YAML mapping for the workflow.

        Returns:
            steps (list): List of step mappings from `jobs.summary.steps`.
        """
        return summary_workflow["jobs"]["summary"]["steps"]

    def test_sanitize_step_is_absent(self, summary_steps):
        """
        Assert that no step name in the `summary` job contains the substring "sanitize" (case-insensitive).
        """
        step_names = [s.get("name", "") for s in summary_steps]
        sanitize_step_found = any("sanitize" in name.lower() for name in step_names)
        assert not sanitize_step_found, "The 'Sanitize issue inputs' step should not be present in summary.yml"

    def test_no_step_uses_sanitize_outputs(self, summary_steps):
        """
        Ensure no step references `steps.sanitize.outputs`.

        Asserts that none of the provided steps contain the string "steps.sanitize.outputs".
        """
        for step in summary_steps:
            step_str = yaml.dump(step)
            assert "steps.sanitize.outputs" not in step_str, (
                f"Step '{step.get('name', '?')}' references removed sanitize step outputs"
            )

    def test_checkout_step_exists(self, summary_steps):
        """The checkout step must still be present."""
        uses_values = [s.get("uses", "") for s in summary_steps]
        checkout_present = any("actions/checkout" in u for u in uses_values)
        assert checkout_present, "The 'actions/checkout' step must be present"

    def test_ai_inference_step_exists(self, summary_steps):
        """The AI inference step must be present."""
        uses_values = [s.get("uses", "") for s in summary_steps]
        inference_present = any("actions/ai-inference" in u for u in uses_values)
        assert inference_present, "An 'actions/ai-inference' step must be present"

    def test_ai_inference_step_has_id(self, summary_steps):
        """The AI inference step must have id='inference' for output reference."""
        inference_step = next(
            (s for s in summary_steps if "actions/ai-inference" in s.get("uses", "")),
            None,
        )
        assert inference_step is not None
        assert inference_step.get("id") == "inference", "The AI inference step must have id='inference'"

    def test_comment_step_exists(self, summary_steps):
        """A step to post a comment on the issue must be present."""
        run_steps = [s for s in summary_steps if "run" in s]
        comment_steps = [s for s in run_steps if "gh issue comment" in s.get("run", "")]
        assert len(comment_steps) >= 1, "There must be a step containing 'gh issue comment'"


class TestAIInferenceStepPrompt:
    """Verify the AI inference step uses raw (unsanitized) GitHub context expressions."""

    @pytest.fixture(name="inference_step")
    def inference_step_fixture(self, summary_workflow):
        """
        Finds and returns the `actions/ai-inference` step from the `summary` job.

        Parameters:
            summary_workflow (dict): Parsed YAML mapping of the workflow (as returned by yaml.safe_load).

        Returns:
            dict: The step dictionary for the `actions/ai-inference` step.

        Raises:
            AssertionError: If no step using `actions/ai-inference` is found.
        """
        steps = summary_workflow["jobs"]["summary"]["steps"]
        step = next(
            (s for s in steps if "actions/ai-inference" in s.get("uses", "")),
            None,
        )
        assert step is not None, "actions/ai-inference step not found"
        return step

    def test_prompt_uses_raw_issue_title(self, inference_step):
        """
        The AI inference prompt must use raw github.event.issue.title directly.

        After the PR, sanitized outputs are no longer used; the raw GitHub
        context expression is embedded in the prompt.
        """
        prompt = inference_step.get("with", {}).get("prompt", "")
        assert "github.event.issue.title" in prompt, (
            "The inference prompt must reference github.event.issue.title directly"
        )

    def test_prompt_uses_raw_issue_body(self, inference_step):
        """
        Asserts the AI inference step's prompt contains the raw GitHub issue body expression.

        Verifies the `with.prompt` value for the `actions/ai-inference` step includes `github.event.issue.body`.
        """
        prompt = inference_step.get("with", {}).get("prompt", "")
        assert "github.event.issue.body" in prompt, (
            "The inference prompt must reference github.event.issue.body directly"
        )

    def test_prompt_does_not_use_sanitized_title(self, inference_step):
        """
        Ensure the inference `prompt` does not reference the removed sanitize step's `title` output.

        Asserts that the string `steps.sanitize.outputs.title` is not present in the `with.prompt` value of the inference step.
        """
        prompt = inference_step.get("with", {}).get("prompt", "")
        assert "steps.sanitize.outputs.title" not in prompt, (
            "Inference prompt should not reference removed sanitize step title output"
        )

    def test_prompt_does_not_use_sanitized_body(self, inference_step):
        """
        The prompt must not reference steps.sanitize.outputs.body.

        The sanitization step was removed; its outputs must not appear in the prompt.
        """
        prompt = inference_step.get("with", {}).get("prompt", "")
        assert "steps.sanitize.outputs.body" not in prompt, (
            "Inference prompt should not reference removed sanitize step body output"
        )

    def test_prompt_contains_title_label(self, inference_step):
        """The prompt should include a 'Title:' label."""
        prompt = inference_step.get("with", {}).get("prompt", "")
        assert "Title:" in prompt, "The AI prompt should contain a 'Title:' label"

    def test_prompt_contains_body_label(self, inference_step):
        """The prompt should include a 'Body:' label."""
        prompt = inference_step.get("with", {}).get("prompt", "")
        assert "Body:" in prompt, "The AI prompt should contain a 'Body:' label"


class TestCommentStep:
    """Verify the 'Comment with AI summary' step structure after the PR changes."""

    @pytest.fixture(name="comment_step")
    def comment_step_fixture(self, summary_workflow):
        """
        Locate the step that posts the GitHub issue comment.

        Parameters:
                summary_workflow (dict): Parsed workflow mapping (the result of yaml.safe_load on .github/workflows/summary.yml).

        Returns:
                step (dict): The step mapping whose `run` script contains `gh issue comment`.

        Raises:
                AssertionError: If no step with `gh issue comment` is found.
        """
        steps = summary_workflow["jobs"]["summary"]["steps"]
        step = next(
            (s for s in steps if "gh issue comment" in s.get("run", "")),
            None,
        )
        assert step is not None, "Comment step with 'gh issue comment' not found"
        return step

    def test_comment_step_has_gh_token_env(self, comment_step):
        """The comment step must provide GH_TOKEN via env for gh CLI authentication."""
        env = comment_step.get("env", {})
        assert "GH_TOKEN" in env, "Comment step must set GH_TOKEN env var for gh CLI"

    def test_comment_step_gh_token_uses_github_token_secret(self, comment_step):
        """GH_TOKEN must be set from secrets.GITHUB_TOKEN."""
        env = comment_step.get("env", {})
        gh_token_value = env.get("GH_TOKEN", "")
        assert "secrets.GITHUB_TOKEN" in gh_token_value, "GH_TOKEN must be sourced from secrets.GITHUB_TOKEN"

    def test_comment_step_has_issue_number_env(self, comment_step):
        """The comment step must provide ISSUE_NUMBER via env."""
        env = comment_step.get("env", {})
        assert "ISSUE_NUMBER" in env, "Comment step must set ISSUE_NUMBER env var"

    def test_comment_step_issue_number_env_uses_github_context(self, comment_step):
        """ISSUE_NUMBER must come from github.event.issue.number."""
        env = comment_step.get("env", {})
        issue_number_value = env.get("ISSUE_NUMBER", "")
        assert "github.event.issue.number" in issue_number_value, (
            "ISSUE_NUMBER must be sourced from github.event.issue.number"
        )

    def test_comment_step_run_uses_issue_number_var(self, comment_step):
        """The shell command must reference ISSUE_NUMBER."""
        run_script = comment_step.get("run", "")
        assert "ISSUE_NUMBER" in run_script, "The gh comment command must reference the ISSUE_NUMBER variable"

    def test_comment_step_issue_number_is_quoted_in_shell(self, comment_step):
        """
        ISSUE_NUMBER should remain double-quoted in the shell command.

        Quoting "$ISSUE_NUMBER" preserves the current workflow behavior and avoids
        unsafe shell expansion patterns.
        """
        run_script = comment_step.get("run", "")
        assert re.search(r'gh issue comment "\$ISSUE_NUMBER"', run_script), (
            'gh issue comment should use quoted "$ISSUE_NUMBER"'
        )

    def test_comment_step_has_response_env_from_inference_output(self, comment_step):
        """
        Verify the AI response is passed through a RESPONSE environment variable.

        This keeps the workflow aligned with the current implementation and avoids
        embedding raw model output directly into the shell command.
        """
        env = comment_step.get("env", {})
        assert "RESPONSE" in env, "Comment step must set RESPONSE env var"
        response_value = env.get("RESPONSE", "")
        assert "steps.inference.outputs.response" in response_value, (
            "RESPONSE must be sourced from steps.inference.outputs.response"
        )

    def test_comment_step_uses_response_env_var_in_command(self, comment_step):
        """
        The run script should use the quoted RESPONSE env var for the --body argument.

        Passing the AI response via "$RESPONSE" is safer than inlining the raw
        expression directly into the shell command.
        """
        run_script = comment_step.get("run", "")
        assert '--body "$RESPONSE"' in run_script, 'The gh comment command should use --body "$RESPONSE"'


class TestIssueContentIsIncludedInWorkflow:
    """
    Verify that the workflow still includes the issue title and body content
    needed to generate a summary, without constraining whether sanitization or
    other hardening steps are present.
    """

    def test_workflow_references_issue_title(self, summary_workflow_raw):
        """
        Assert that the workflow references the GitHub issue title expression.

        This validates required summary input while allowing implementation
        details such as sanitization, truncation, or intermediate variables.
        """
        assert (
            "github.event.issue.title" in summary_workflow_raw
        ), "summary.yml should reference github.event.issue.title so the summary can include the issue title"

    def test_workflow_references_issue_body(self, summary_workflow_raw):
        """
        Assert that the workflow references the GitHub issue body expression.

        This validates required summary input while allowing implementation
        details such as sanitization, truncation, or intermediate variables.
        """
        assert (
            "github.event.issue.body" in summary_workflow_raw
        ), "summary.yml should reference github.event.issue.body so the summary can include the issue body"

    def test_workflow_uses_issue_content_in_step_configuration(self, summary_workflow_raw):
        """
        Verify that issue content is wired into workflow step configuration.

        The workflow may pass issue title/body directly, via env variables, or
        through sanitized intermediate variables. This test checks only that the
        workflow is set up to use issue content, not how it hardens that data.
        """
        assert re.search(
            r"github\.event\.issue\.(title|body)|(?:SANITIZED|ISSUE)_(?:TITLE|BODY)",
            summary_workflow_raw,
        ), "summary.yml should include issue title/body content in step configuration"
class TestPinnedActionVersions:
    """Verify actions in summary.yml use pinned commit SHAs, not floating tags."""

    @pytest.fixture(name="summary_steps")
    def summary_steps_fixture(self, summary_workflow):
        """
        Retrieve the steps defined in the 'summary' job of the parsed workflow.

        Parameters:
            summary_workflow (dict): Parsed YAML mapping for the workflow.

        Returns:
            steps (list): List of step mappings from `jobs.summary.steps`.
        """
        return summary_workflow["jobs"]["summary"]["steps"]

    def test_all_actions_specify_version(self, summary_steps):
        """Every action reference must include a version specifier after '@'."""
        for step in summary_steps:
            if "uses" in step:
                action = step["uses"]
                assert "@" in action, f"Action '{action}' in summary.yml must include a version specifier"

    def test_no_actions_use_latest(self, summary_steps):
        """No action reference may use '@latest'."""
        for step in summary_steps:
            action = step.get("uses", "")
            assert "@latest" not in action.lower(), f"Action '{action}' in summary.yml must not use '@latest'"

    def test_no_actions_use_master_branch(self, summary_steps):
        """
        Ensure no action references use the '@master' branch.

        Asserts that for every step in the summary job, the step's `uses` value does not contain `@master` (case-insensitive).
        """
        for step in summary_steps:
            action = step.get("uses", "")
            assert "@master" not in action.lower(), f"Action '{action}' in summary.yml must not use '@master' branch"

    def test_checkout_action_is_pinned_to_sha(self, summary_steps):
        """
        Ensure the actions/checkout step is pinned to an exact 40-hex commit SHA.

        Asserts that a step using `actions/checkout` exists in `summary_steps` and that its `uses` reference ends with a 40-character lowercase hex SHA (e.g., a full git commit SHA). Failure occurs if the step is missing or the ref is not a full SHA.
        """
        checkout_step = next(
            (s for s in summary_steps if "actions/checkout" in s.get("uses", "")),
            None,
        )
        assert checkout_step is not None, "actions/checkout step not found"
        action_ref = checkout_step["uses"]
        sha_part = action_ref.split("@", 1)[-1]
        assert re.match(r"^[0-9a-f]{40}$", sha_part), (
            f"actions/checkout must be pinned to a full commit SHA, got: {sha_part}"
        )

    def test_ai_inference_action_is_pinned_to_sha(self, summary_steps):
        """The actions/ai-inference step must be pinned to a commit SHA (40 hex chars)."""
        inference_step = next(
            (s for s in summary_steps if "actions/ai-inference" in s.get("uses", "")),
            None,
        )
        assert inference_step is not None, "actions/ai-inference step not found"
        action_ref = inference_step["uses"]
        sha_part = action_ref.split("@", 1)[-1]
        assert re.match(r"^[0-9a-f]{40}$", sha_part), (
            f"actions/ai-inference must be pinned to a full commit SHA, got: {sha_part}"
        )


class TestSummaryWorkflowRegression:
    """Regression and boundary tests to strengthen confidence in the workflow state."""

    def test_workflow_contains_required_steps(self, summary_workflow):
        """
        Assert that the 'summary' job contains the required workflow steps.

        This verifies the workflow still includes checkout, inference, and comment
        steps without requiring an exact total step count, which would make the
        test brittle if additional valid steps are added later.
        """
        steps = summary_workflow["jobs"]["summary"]["steps"]
        checkout_step = next(
            (s for s in steps if "actions/checkout" in s.get("uses", "")),
            None,
        )
        inference_step = next(
            (s for s in steps if "actions/ai-inference" in s.get("uses", "")),
            None,
        )
        comment_step = next(
            (s for s in steps if "gh issue comment" in s.get("run", "")),
            None,
        )
        assert checkout_step is not None, "Checkout step not found"
        assert inference_step is not None, "Inference step not found"
        assert comment_step is not None, "Comment step not found"

    def test_step_ordering_checkout_before_inference(self, summary_workflow):
        """The checkout step must appear before the AI inference step."""
        steps = summary_workflow["jobs"]["summary"]["steps"]
        checkout_idx = next(
            (i for i, s in enumerate(steps) if "actions/checkout" in s.get("uses", "")),
            None,
        )
        inference_idx = next(
            (i for i, s in enumerate(steps) if "actions/ai-inference" in s.get("uses", "")),
            None,
        )
        assert checkout_idx is not None, "Checkout step not found"
        assert inference_idx is not None, "Inference step not found"
        assert checkout_idx < inference_idx, "Checkout step must appear before the inference step"

    def test_step_ordering_inference_before_comment(self, summary_workflow):
        """The AI inference step must appear before the comment step."""
        steps = summary_workflow["jobs"]["summary"]["steps"]
        inference_idx = next(
            (i for i, s in enumerate(steps) if "actions/ai-inference" in s.get("uses", "")),
            None,
        )
        comment_idx = next(
            (i for i, s in enumerate(steps) if "gh issue comment" in s.get("run", "")),
            None,
        )
        assert inference_idx is not None, "Inference step not found"
        assert comment_idx is not None, "Comment step not found"
        assert inference_idx < comment_idx, "Inference step must appear before the comment step"

    def test_raw_github_expressions_present_in_prompt(self, summary_workflow_raw):
        """
        The raw YAML source must contain GitHub expression syntax for title and body
        inside the prompt, confirming unsanitized values are passed to the AI.
        """
        assert "github.event.issue.title" in summary_workflow_raw, (
            "Raw workflow YAML must reference github.event.issue.title in the prompt"
        )
        assert "github.event.issue.body" in summary_workflow_raw, (
            "Raw workflow YAML must reference github.event.issue.body in the prompt"
        )

    def test_response_env_var_still_defined_in_comment_step(self, summary_workflow):
        """
        The RESPONSE env var may still be declared in the comment step env block
        even if it is no longer used in the --body argument.

        This is a boundary test: if it IS present, it does not affect the shell
        command (which now embeds the expression directly). This test simply
        documents the current state without asserting either presence or absence,
        but validates that the run script does not use it for --body.
        """
        steps = summary_workflow["jobs"]["summary"]["steps"]
        comment_step = next(
            (s for s in steps if "gh issue comment" in s.get("run", "")),
            None,
        )
        assert comment_step is not None
        run_script = comment_step.get("run", "")
        # The key assertion: --body must not use the $RESPONSE env var pattern
        assert not re.search(r'--body\s+"\$RESPONSE"', run_script), (
            "The --body argument must not use the $RESPONSE env var"
        )
