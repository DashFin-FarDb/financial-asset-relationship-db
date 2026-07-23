"""
Tests for the hosted-readiness.yml GitHub Actions workflow.

This module validates the structure and security of .github/workflows/hosted-readiness.yml,
ensuring it is correctly configured as a manual-only workflow that safely invokes the
hosted readiness smoke-check script against operator-supplied deployment targets.

Security requirements enforced:
- Manual workflow_dispatch trigger only (no automatic triggers)
- Minimal permissions (contents: read only)
- No hardcoded hosted URLs, tokens, credentials, or secrets
- Base URL comes from manual input or repository secret
- Clean skip path when no hosted target is configured
- Script invocation uses environment variables, not hardcoded values
"""

import re
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[2]
HOSTED_READINESS_WORKFLOW_PATH = REPO_ROOT / ".github/workflows/hosted-readiness.yml"

TRUSTED_GITHUB_REFERENCES_PATTERN = re.compile(
    r"\b(?:inputs\.base_url|inputs\.timeout|inputs\.require_persistence|secrets\.HOSTED_READINESS_BASE_URL)\b"
)

PROVIDER_SECRET_NAMES = (
    "VERCEL_TOKEN",
    "NETLIFY_AUTH_TOKEN",
    "NETLIFY_SITE_ID",
    "HEROKU_API_KEY",
    "FLY_API_TOKEN",
    "RAILWAY_TOKEN",
    "RENDER_API_KEY",
    "DIGITALOCEAN_ACCESS_TOKEN",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AZURE_CLIENT_SECRET",
    "GCP_SA_KEY",
)


def _scannable_workflow_content(line: str) -> str:
    """Return workflow code content with comments removed and trusted references redacted."""
    content = line.split("#", 1)[0].strip()
    return TRUSTED_GITHUB_REFERENCES_PATTERN.sub("", content).strip()


@pytest.fixture(name="hosted_readiness_workflow")
def hosted_readiness_workflow_fixture():
    """
    Load and parse the hosted-readiness.yml GitHub Actions workflow file.

    PyYAML (YAML 1.1) may resolve an unquoted ``on`` key to boolean ``True``.
    This fixture normalises the result so callers can always use the string
    key ``'on'`` regardless of how the YAML was serialised.

    Returns:
        dict: Parsed YAML content of .github/workflows/hosted-readiness.yml
        with the trigger key normalised to the string ``'on'``.
    """
    with open(HOSTED_READINESS_WORKFLOW_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict), "hosted-readiness.yml must parse to a mapping"
    # Normalise: PyYAML 1.1 may load an unquoted `on:` key as boolean True.
    if True in data and "on" not in data:
        data["on"] = data.pop(True)
    return data


@pytest.fixture(name="hosted_readiness_workflow_raw")
def hosted_readiness_workflow_raw_fixture():
    """
    Return the raw text content of hosted-readiness.yml.

    Returns:
        str: Raw file content as a string.
    """
    with open(HOSTED_READINESS_WORKFLOW_PATH, encoding="utf-8") as f:
        return f.read()


@pytest.mark.integration
class TestHostedReadinessWorkflowExists:
    """Verify the hosted readiness workflow file is present and valid YAML."""

    @staticmethod
    def test_hosted_readiness_workflow_file_exists():
        """hosted-readiness.yml must exist in .github/workflows."""
        assert HOSTED_READINESS_WORKFLOW_PATH.exists(), f"{HOSTED_READINESS_WORKFLOW_PATH} does not exist"

    @staticmethod
    def test_hosted_readiness_workflow_is_valid_yaml():
        """hosted-readiness.yml must be parseable as valid YAML."""
        with open(HOSTED_READINESS_WORKFLOW_PATH, encoding="utf-8") as f:
            try:
                content = yaml.safe_load(f)
            except yaml.YAMLError as exc:
                pytest.fail(f"hosted-readiness.yml contains invalid YAML: {exc}")
        assert content is not None, "hosted-readiness.yml must not be an empty document"


@pytest.mark.integration
class TestHostedReadinessWorkflowStructure:
    """Verify the top-level structure of hosted-readiness.yml."""

    def test_workflow_has_name(self, hosted_readiness_workflow):
        """Workflow must define a name field."""
        assert "name" in hosted_readiness_workflow, "hosted-readiness.yml is missing 'name' field"

    def test_workflow_name_is_correct(self, hosted_readiness_workflow):
        """Workflow name must be 'Hosted readiness smoke check'."""
        assert (
            hosted_readiness_workflow["name"] == "Hosted readiness smoke check"
        ), "hosted-readiness.yml name must be 'Hosted readiness smoke check'"

    def test_workflow_has_on_trigger(self, hosted_readiness_workflow):
        """Workflow must define event triggers."""
        assert "on" in hosted_readiness_workflow, "hosted-readiness.yml is missing 'on' trigger"

    def test_workflow_triggers_on_workflow_dispatch_only(self, hosted_readiness_workflow):
        """Workflow must trigger on workflow_dispatch only."""
        triggers = hosted_readiness_workflow["on"]
        assert isinstance(triggers, dict), "Workflow triggers must be a mapping"
        assert set(triggers) == {
            "workflow_dispatch"
        }, "hosted-readiness.yml must define workflow_dispatch as its only trigger"

    def test_workflow_does_not_trigger_on_push(self, hosted_readiness_workflow):
        """Workflow must not trigger on push events."""
        triggers = hosted_readiness_workflow["on"]
        assert "push" not in triggers, "hosted-readiness.yml must not trigger on 'push' (manual-only workflow)"

    def test_workflow_does_not_trigger_on_pull_request(self, hosted_readiness_workflow):
        """Workflow must not trigger on pull_request events."""
        triggers = hosted_readiness_workflow["on"]
        assert (
            "pull_request" not in triggers
        ), "hosted-readiness.yml must not trigger on 'pull_request' (manual-only workflow)"

    def test_workflow_has_jobs(self, hosted_readiness_workflow):
        """Workflow must define at least one job."""
        assert "jobs" in hosted_readiness_workflow, "hosted-readiness.yml is missing 'jobs'"
        assert len(hosted_readiness_workflow["jobs"]) > 0, "hosted-readiness.yml must have at least one job"

    def test_hosted_readiness_job_exists(self, hosted_readiness_workflow):
        """The 'hosted-readiness' job must be defined."""
        assert (
            "hosted-readiness" in hosted_readiness_workflow["jobs"]
        ), "hosted-readiness.yml must contain a job named 'hosted-readiness'"

    def test_hosted_readiness_job_has_runs_on(self, hosted_readiness_workflow):
        """The 'hosted-readiness' job must specify a runner."""
        job = hosted_readiness_workflow["jobs"]["hosted-readiness"]
        assert "runs-on" in job, "The 'hosted-readiness' job must specify 'runs-on'"

    def test_hosted_readiness_job_runs_on_ubuntu(self, hosted_readiness_workflow):
        """The 'hosted-readiness' job should run on ubuntu-latest."""
        job = hosted_readiness_workflow["jobs"]["hosted-readiness"]
        assert "ubuntu" in str(job["runs-on"]), "The 'hosted-readiness' job should run on an ubuntu-based runner"

    def test_hosted_readiness_job_has_steps(self, hosted_readiness_workflow):
        """The 'hosted-readiness' job must have at least one step."""
        job = hosted_readiness_workflow["jobs"]["hosted-readiness"]
        assert "steps" in job, "The 'hosted-readiness' job must have steps"
        assert len(job["steps"]) > 0, "The 'hosted-readiness' job must have at least one step"


@pytest.mark.integration
class TestHostedReadinessWorkflowPermissions:
    """Verify the hosted-readiness workflow uses minimal permissions."""

    def test_hosted_readiness_job_permissions(self, hosted_readiness_workflow):
        """The 'hosted-readiness' job must have only 'contents: read' permission."""
        job = hosted_readiness_workflow["jobs"]["hosted-readiness"]
        assert "permissions" in job, "The 'hosted-readiness' job must declare 'permissions'"
        perms = job.get("permissions", {})
        assert perms == {"contents": "read"}, "The 'hosted-readiness' job must have only 'contents: read'"


@pytest.mark.integration
class TestHostedReadinessWorkflowInputs:
    """Verify the workflow_dispatch inputs are correctly defined."""

    def test_workflow_dispatch_has_inputs(self, hosted_readiness_workflow):
        """workflow_dispatch trigger must define inputs."""
        workflow_dispatch = hosted_readiness_workflow["on"]["workflow_dispatch"]
        assert "inputs" in workflow_dispatch, "workflow_dispatch must define 'inputs'"

    def test_base_url_input_configuration(self, hosted_readiness_workflow):
        """base_url input must be optional with description."""
        inputs = hosted_readiness_workflow["on"]["workflow_dispatch"]["inputs"]
        assert "base_url" in inputs, "workflow_dispatch inputs must include 'base_url'"
        base_url_input = inputs["base_url"]
        assert "description" in base_url_input, "base_url input must have a 'description'"
        required = base_url_input.get("required", False)
        assert required is False, "base_url input must not be required (allows using secret instead)"

    def test_timeout_input_configuration(self, hosted_readiness_workflow):
        """Timeout input must exist with a string default."""
        inputs = hosted_readiness_workflow["on"]["workflow_dispatch"]["inputs"]
        assert "timeout" in inputs, "workflow_dispatch inputs must include 'timeout'"
        timeout_input = inputs["timeout"]
        assert "default" in timeout_input, "timeout input must have a 'default' value"
        assert isinstance(timeout_input["default"], str), "timeout input default must be a string"
        assert timeout_input["default"] == "30", "timeout default must cover Vercel Python cold starts"

    def test_require_persistence_input_configuration(self, hosted_readiness_workflow):
        """require_persistence input must exist and be a boolean default false."""
        inputs = hosted_readiness_workflow["on"]["workflow_dispatch"]["inputs"]
        assert "require_persistence" in inputs, "workflow_dispatch inputs must include 'require_persistence'"
        input_cfg = inputs["require_persistence"]
        assert "description" in input_cfg, "require_persistence input must have a 'description'"
        assert input_cfg.get("default") is False, "require_persistence default must be false"
        assert input_cfg.get("type") == "boolean", "require_persistence type must be boolean"


@pytest.mark.integration
class TestHostedReadinessWorkflowEnvironment:
    """Verify the workflow environment configuration."""

    def test_environment_variables_configured(self, hosted_readiness_workflow):
        """
        Job must define HOSTED_READINESS_BASE_URL, HOSTED_READINESS_TIMEOUT,
        and HOSTED_READINESS_REQUIRE_PERSISTENCE env vars.
        """
        job = hosted_readiness_workflow["jobs"]["hosted-readiness"]
        assert "env" in job, "The 'hosted-readiness' job must define 'env' section"
        env = job.get("env", {})
        assert "HOSTED_READINESS_BASE_URL" in env, "Job must define HOSTED_READINESS_BASE_URL env var"
        assert "HOSTED_READINESS_TIMEOUT" in env, "Job must define HOSTED_READINESS_TIMEOUT env var"
        assert (
            "HOSTED_READINESS_REQUIRE_PERSISTENCE" in env
        ), "Job must define HOSTED_READINESS_REQUIRE_PERSISTENCE env var"

    def test_base_url_comes_from_input_or_secret(self, hosted_readiness_workflow):
        """Base URL must come from inputs.base_url or secrets.HOSTED_READINESS_BASE_URL."""
        job = hosted_readiness_workflow["jobs"]["hosted-readiness"]
        env = job.get("env", {})
        base_url_expr = env.get("HOSTED_READINESS_BASE_URL")
        assert (
            base_url_expr == "${{ inputs.base_url || secrets.HOSTED_READINESS_BASE_URL }}"
        ), "HOSTED_READINESS_BASE_URL must use only inputs.base_url with secrets.HOSTED_READINESS_BASE_URL fallback"

    def test_timeout_comes_from_input(self, hosted_readiness_workflow):
        """Timeout must come from inputs.timeout."""
        job = hosted_readiness_workflow["jobs"]["hosted-readiness"]
        env = job.get("env", {})
        assert (
            env.get("HOSTED_READINESS_TIMEOUT") == "${{ inputs.timeout }}"
        ), "HOSTED_READINESS_TIMEOUT must use inputs.timeout"

    def test_require_persistence_comes_from_input(self, hosted_readiness_workflow):
        """Require persistence must come from inputs.require_persistence."""
        job = hosted_readiness_workflow["jobs"]["hosted-readiness"]
        env = job.get("env", {})
        assert (
            env.get("HOSTED_READINESS_REQUIRE_PERSISTENCE") == "${{ inputs.require_persistence }}"
        ), "HOSTED_READINESS_REQUIRE_PERSISTENCE must use inputs.require_persistence"


@pytest.mark.integration
class TestHostedReadinessWorkflowSteps:
    """Verify the steps present in the hosted readiness workflow."""

    @pytest.fixture(name="hosted_readiness_steps")
    def hosted_readiness_steps_fixture(self, hosted_readiness_workflow):
        """
        Retrieve the steps defined in the 'hosted-readiness' job of the parsed workflow.

        Parameters:
            hosted_readiness_workflow (dict): Parsed YAML mapping for the workflow.

        Returns:
            steps (list): List of step mappings from `jobs.hosted-readiness.steps`.
        """
        return hosted_readiness_workflow["jobs"]["hosted-readiness"]["steps"]

    def test_checkout_step_exists(self, hosted_readiness_steps):
        """The checkout step must be present."""
        uses_values = [s.get("uses", "") for s in hosted_readiness_steps]
        checkout_present = any("actions/checkout" in u for u in uses_values)
        assert checkout_present, "The 'actions/checkout' step must be present"

    def test_checkout_action_is_pinned_to_sha(self, hosted_readiness_steps):
        """
        Ensure the actions/checkout step is pinned to an exact 40-hex commit SHA.

        Asserts that a step using `actions/checkout` exists and that its `uses`
        reference ends with a 40-character lowercase hex SHA.
        """
        checkout_step = next(
            (s for s in hosted_readiness_steps if "actions/checkout" in s.get("uses", "")),
            None,
        )
        assert checkout_step is not None, "actions/checkout step not found"
        action_ref = checkout_step["uses"]
        sha_part = action_ref.split("@", 1)[-1].split()[0]  # Handle inline comments
        assert re.match(
            r"^[0-9a-f]{40}$", sha_part
        ), f"actions/checkout must be pinned to a full commit SHA, got: {sha_part}"

    def test_skip_step_exists(self, hosted_readiness_steps):
        """A step to skip when no base URL is configured must be present."""
        skip_step_present = any(
            "Skip when hosted readiness target is not configured" in s.get("name", "") for s in hosted_readiness_steps
        )
        assert skip_step_present, "Workflow must have a skip step for when no base URL is configured"

    def test_skip_step_has_conditional(self, hosted_readiness_steps):
        """The skip step must have an 'if' conditional checking for empty base URL."""
        skip_step = next(
            (
                s
                for s in hosted_readiness_steps
                if "Skip when hosted readiness target is not configured" in s.get("name", "")
            ),
            None,
        )
        assert skip_step is not None
        assert "if" in skip_step, "Skip step must have an 'if' conditional"
        condition = skip_step["if"]
        assert "HOSTED_READINESS_BASE_URL" in condition, "Skip step condition must check HOSTED_READINESS_BASE_URL"
        assert "== ''" in condition or "==''" in condition, "Skip step must check for empty string"

    def test_run_check_step_exists(self, hosted_readiness_steps):
        """A step to run the hosted readiness smoke check must be present."""
        run_check_step_present = any(
            "Run hosted readiness smoke check" in s.get("name", "") for s in hosted_readiness_steps
        )
        assert run_check_step_present, "Workflow must have a step to run the hosted readiness smoke check"

    def test_run_check_step_has_conditional(self, hosted_readiness_steps):
        """The run check step must have an 'if' conditional checking for non-empty base URL."""
        run_check_step = next(
            (s for s in hosted_readiness_steps if "Run hosted readiness smoke check" in s.get("name", "")),
            None,
        )
        assert run_check_step is not None
        assert "if" in run_check_step, "Run check step must have an 'if' conditional"
        condition = run_check_step["if"]
        assert "HOSTED_READINESS_BASE_URL" in condition, "Run check step condition must check HOSTED_READINESS_BASE_URL"
        assert "!= ''" in condition or "!=''" in condition, "Run check step must check for non-empty string"

    def test_run_check_step_invokes_script(self, hosted_readiness_steps):
        """The run check step must invoke scripts/check_hosted_readiness.py."""
        run_check_step = next(
            (s for s in hosted_readiness_steps if "Run hosted readiness smoke check" in s.get("name", "")),
            None,
        )
        assert run_check_step is not None
        run_script = run_check_step.get("run", "")
        assert (
            "scripts/check_hosted_readiness.py" in run_script
        ), "Run check step must invoke scripts/check_hosted_readiness.py"

    def test_script_invocation_uses_env_var_not_hardcoded_url(self, hosted_readiness_steps):
        """The script invocation must use $HOSTED_READINESS_BASE_URL, not a hardcoded URL."""
        run_check_step = next(
            (s for s in hosted_readiness_steps if "Run hosted readiness smoke check" in s.get("name", "")),
            None,
        )
        assert run_check_step is not None
        run_script = run_check_step.get("run", "")
        assert (
            "$HOSTED_READINESS_BASE_URL" in run_script or "${HOSTED_READINESS_BASE_URL}" in run_script
        ), "Script invocation must use $HOSTED_READINESS_BASE_URL env var"

    def test_script_invocation_uses_timeout_env_var(self, hosted_readiness_steps):
        """The script invocation must use $HOSTED_READINESS_TIMEOUT for --timeout argument."""
        run_check_step = next(
            (s for s in hosted_readiness_steps if "Run hosted readiness smoke check" in s.get("name", "")),
            None,
        )
        assert run_check_step is not None
        run_script = run_check_step.get("run", "")
        assert "--timeout" in run_script, "Script invocation must include --timeout argument"
        assert (
            "$HOSTED_READINESS_TIMEOUT" in run_script or "${HOSTED_READINESS_TIMEOUT}" in run_script
        ), "Script invocation must use $HOSTED_READINESS_TIMEOUT env var"

    def test_script_invocation_uses_require_persistence_env_var(self, hosted_readiness_steps):
        """
        The script invocation must conditionally append --require-persistence
        using $HOSTED_READINESS_REQUIRE_PERSISTENCE.
        """
        run_check_step = next(
            (s for s in hosted_readiness_steps if "Run hosted readiness smoke check" in s.get("name", "")),
            None,
        )
        assert run_check_step is not None
        run_script = run_check_step.get("run", "")
        assert "--require-persistence" in run_script, "Script invocation must check/reference --require-persistence"
        assert (
            "HOSTED_READINESS_REQUIRE_PERSISTENCE" in run_script
        ), "Script invocation must check HOSTED_READINESS_REQUIRE_PERSISTENCE"


@pytest.mark.integration
class TestHostedReadinessWorkflowSecurity:
    """Verify the workflow does not contain hardcoded secrets or sensitive data."""

    def test_no_hardcoded_hosted_url(self, hosted_readiness_workflow_raw):
        """Workflow must not contain hardcoded hosted URLs."""
        for line in hosted_readiness_workflow_raw.splitlines():
            content = _scannable_workflow_content(line)
            assert not re.search(
                r"https?://", content, re.IGNORECASE
            ), f"Workflow must not contain hardcoded URLs in code: {line}"

    def test_no_hardcoded_tokens(self, hosted_readiness_workflow_raw):
        """Workflow must not contain hardcoded tokens or API keys."""
        sensitive_assignment = re.compile(
            r"\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|bearer[_-]?token|token)\b"
            r"\s*[:=]\s*['\"]?[A-Za-z0-9._~+/=-]{20,}['\"]?",
            re.IGNORECASE,
        )
        bearer_literal = re.compile(
            r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}",
            re.IGNORECASE,
        )

        for line in hosted_readiness_workflow_raw.splitlines():
            content = _scannable_workflow_content(line)
            if not content:
                continue
            assert not sensitive_assignment.search(
                content
            ), f"Workflow may contain hardcoded token or API key in line: {line}"
            assert not bearer_literal.search(content), f"Workflow may contain hardcoded bearer token in line: {line}"

    def test_no_hardcoded_database_urls(self, hosted_readiness_workflow_raw):
        """Workflow must not contain hardcoded database URLs."""
        for line in hosted_readiness_workflow_raw.splitlines():
            content = _scannable_workflow_content(line)
            assert not re.search(
                r"postgres(ql)?://", content, re.IGNORECASE
            ), f"Workflow must not contain hardcoded PostgreSQL URLs: {line}"
            assert not re.search(
                r"mysql://", content, re.IGNORECASE
            ), f"Workflow must not contain hardcoded MySQL URLs: {line}"

    def test_no_hardcoded_credentials(self, hosted_readiness_workflow_raw):
        """Workflow must not contain hardcoded usernames or passwords."""
        credential_assignment = re.compile(
            r"\b(?:username|password)\b\s*[:=]\s*['\"]?[^'\"\s#]{3,}['\"]?",
            re.IGNORECASE,
        )

        for line in hosted_readiness_workflow_raw.splitlines():
            content = _scannable_workflow_content(line)
            if not content:
                continue
            assert not credential_assignment.search(
                content
            ), f"Workflow may contain hardcoded credential in line: {line}"

    def test_no_raw_endpoint_response_bodies(self, hosted_readiness_workflow_raw):
        """Workflow must not contain raw endpoint response bodies or example payloads."""
        # The workflow should not include example JSON payloads that could leak information
        assert (
            '{"status": "healthy"' not in hosted_readiness_workflow_raw
        ), "Workflow must not contain example response bodies"
        assert (
            '"graph_initialized": true' not in hosted_readiness_workflow_raw
        ), "Workflow must not contain example response bodies"

    def test_no_provider_specific_secrets(self, hosted_readiness_workflow_raw):
        """Workflow must not embed provider-specific credential names."""
        scannable_content = "\n".join(
            _scannable_workflow_content(line) for line in hosted_readiness_workflow_raw.splitlines()
        )
        for secret_name in PROVIDER_SECRET_NAMES:
            assert not re.search(
                rf"\b{secret_name}\b", scannable_content
            ), f"Workflow must not embed provider-specific secret '{secret_name}'"


@pytest.mark.integration
class TestHostedReadinessWorkflowConcurrency:
    """Verify the workflow concurrency configuration."""

    def test_workflow_has_concurrency_group(self, hosted_readiness_workflow):
        """Workflow must define the intended concurrency group."""
        assert "concurrency" in hosted_readiness_workflow, "Workflow must define 'concurrency'"
        concurrency = hosted_readiness_workflow["concurrency"]
        assert (
            concurrency.get("group") == "${{ github.workflow }}-${{ github.ref }}"
        ), "Concurrency group must be scoped to workflow and ref"

    def test_concurrency_cancel_in_progress_is_false(self, hosted_readiness_workflow):
        """Workflow concurrency must not cancel in-progress runs (manual workflow safety)."""
        concurrency = hosted_readiness_workflow["concurrency"]
        cancel_in_progress = concurrency.get("cancel-in-progress", False)
        assert cancel_in_progress is False, "Concurrency cancel-in-progress must be false for manual workflow safety"
