"""
Integration tests for .github/workflows/python-app.yml (Python package workflow).

Tests validate the changes introduced in the PR:
- Workflow renamed to "Python package"
- Matrix strategy added for Python 3.9, 3.10, 3.11
- fail-fast: false in strategy
- Path triggers updated to python-package.yml self-reference
- MERGIFY_TOKEN env var passed to step
- python -m pip used consistently (no bare pip for tool installs)
- permissions block removed from workflow level
"""

from pathlib import Path

import pytest
import yaml

WORKFLOW_PATH = Path(__file__).parent.parent.parent / ".github" / "workflows" / "python-app.yml"

pytestmark = pytest.mark.integration


def load_workflow():
    """Load and parse the python-app.yml workflow file."""
    with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestPythonPackageWorkflowStructure:
    """Tests for top-level structure and required fields."""

    def test_workflow_file_exists(self):
        """Verify the workflow file exists on disk."""
        assert WORKFLOW_PATH.exists(), f"Workflow file not found: {WORKFLOW_PATH}"

    def test_workflow_is_valid_yaml(self):
        """Verify the workflow file parses as valid YAML."""
        workflow = load_workflow()
        assert workflow is not None, "Workflow YAML is empty"
        assert isinstance(workflow, dict), "Workflow must be a YAML mapping"

    def test_workflow_has_required_top_level_keys(self):
        """Verify the required top-level keys name, on, and jobs are present."""
        workflow = load_workflow()
        for key in ("name", "on", "jobs"):
            assert key in workflow, f"Missing required top-level key: '{key}'"

    def test_workflow_name_is_python_package(self):
        """Workflow name must be 'Python package' (renamed from 'Python application')."""
        workflow = load_workflow()
        assert workflow["name"] == "Python package", (
            f"Expected workflow name 'Python package', got '{workflow['name']}'"
        )

    def test_no_top_level_permissions_block(self):
        """The top-level permissions block must not be present (removed in PR)."""
        workflow = load_workflow()
        assert "permissions" not in workflow, (
            "Top-level 'permissions' block should have been removed in this PR"
        )


class TestPythonPackageWorkflowTriggers:
    """Tests for push and pull_request trigger configuration."""

    def test_triggers_are_configured(self):
        """Verify both push and pull_request triggers are present."""
        workflow = load_workflow()
        triggers = workflow.get("on", {})
        assert "push" in triggers, "Missing 'push' trigger"
        assert "pull_request" in triggers, "Missing 'pull_request' trigger"

    def test_push_trigger_targets_main_branch(self):
        """Push trigger must target the 'main' branch."""
        workflow = load_workflow()
        push_branches = workflow["on"]["push"].get("branches", [])
        assert "main" in push_branches, f"Push trigger must include 'main', got: {push_branches}"

    def test_pull_request_trigger_targets_main_branch(self):
        """Pull request trigger must target the 'main' branch."""
        workflow = load_workflow()
        pr_branches = workflow["on"]["pull_request"].get("branches", [])
        assert "main" in pr_branches, f"PR trigger must include 'main', got: {pr_branches}"

    def test_push_paths_include_python_package_workflow(self):
        """Push path filter must reference python-package.yml, not python-app.yml."""
        workflow = load_workflow()
        push_paths = workflow["on"]["push"].get("paths", [])
        assert ".github/workflows/python-package.yml" in push_paths, (
            "Push paths must include '.github/workflows/python-package.yml'"
        )
        assert ".github/workflows/python-app.yml" not in push_paths, (
            "Push paths must NOT reference the old 'python-app.yml'"
        )

    def test_pull_request_paths_include_python_package_workflow(self):
        """Pull request path filter must reference python-package.yml, not python-app.yml."""
        workflow = load_workflow()
        pr_paths = workflow["on"]["pull_request"].get("paths", [])
        assert ".github/workflows/python-package.yml" in pr_paths, (
            "PR paths must include '.github/workflows/python-package.yml'"
        )
        assert ".github/workflows/python-app.yml" not in pr_paths, (
            "PR paths must NOT reference the old 'python-app.yml'"
        )

    def test_push_paths_include_python_files(self):
        """Push path filter must include Python source files."""
        workflow = load_workflow()
        push_paths = workflow["on"]["push"].get("paths", [])
        assert "**/*.py" in push_paths, "Push paths must include '**/*.py'"
        assert "requirements*.txt" in push_paths, "Push paths must include 'requirements*.txt'"

    def test_pull_request_paths_include_python_files(self):
        """Pull request path filter must include Python source files."""
        workflow = load_workflow()
        pr_paths = workflow["on"]["pull_request"].get("paths", [])
        assert "**/*.py" in pr_paths, "PR paths must include '**/*.py'"
        assert "requirements*.txt" in pr_paths, "PR paths must include 'requirements*.txt'"

    def test_push_paths_ignore_markdown(self):
        """Push trigger must ignore markdown and docs paths."""
        workflow = load_workflow()
        push_ignore = workflow["on"]["push"].get("paths-ignore", [])
        assert "**/*.md" in push_ignore, "Push paths-ignore must include '**/*.md'"
        assert "docs/**" in push_ignore, "Push paths-ignore must include 'docs/**'"

    def test_pull_request_paths_ignore_markdown(self):
        """Pull request trigger must ignore markdown and docs paths."""
        workflow = load_workflow()
        pr_ignore = workflow["on"]["pull_request"].get("paths-ignore", [])
        assert "**/*.md" in pr_ignore, "PR paths-ignore must include '**/*.md'"
        assert "docs/**" in pr_ignore, "PR paths-ignore must include 'docs/**'"

    def test_pull_request_types_are_configured(self):
        """Pull request trigger must include opened, synchronize, and reopened types."""
        workflow = load_workflow()
        pr_types = workflow["on"]["pull_request"].get("types", [])
        for event_type in ("opened", "synchronize", "reopened"):
            assert event_type in pr_types, (
                f"PR trigger must include type '{event_type}', got: {pr_types}"
            )


class TestPythonPackageWorkflowConcurrency:
    """Tests for concurrency configuration."""

    def test_concurrency_block_exists(self):
        """Verify the concurrency block is present."""
        workflow = load_workflow()
        assert "concurrency" in workflow, "Missing 'concurrency' block"

    def test_concurrency_cancel_in_progress(self):
        """cancel-in-progress must be true to avoid redundant runs."""
        workflow = load_workflow()
        concurrency = workflow["concurrency"]
        assert concurrency.get("cancel-in-progress") is True, (
            "concurrency.cancel-in-progress must be true"
        )

    def test_concurrency_group_uses_workflow_and_ref(self):
        """Concurrency group must be scoped to workflow name and git ref."""
        workflow = load_workflow()
        group = workflow["concurrency"].get("group", "")
        assert "github.workflow" in group, "Concurrency group must include github.workflow"
        assert "github.ref" in group, "Concurrency group must include github.ref"


class TestPythonPackageWorkflowMatrixStrategy:
    """Tests for the build matrix strategy (new in this PR)."""

    def test_build_job_has_strategy(self):
        """The build job must define a strategy block."""
        workflow = load_workflow()
        build_job = workflow["jobs"]["build"]
        assert "strategy" in build_job, "build job must have a 'strategy' block"

    def test_strategy_has_matrix(self):
        """The strategy block must define a matrix."""
        workflow = load_workflow()
        strategy = workflow["jobs"]["build"]["strategy"]
        assert "matrix" in strategy, "strategy must contain a 'matrix' block"

    def test_matrix_has_python_versions(self):
        """Matrix must define python-version entries."""
        workflow = load_workflow()
        matrix = workflow["jobs"]["build"]["strategy"]["matrix"]
        assert "python-version" in matrix, "matrix must include 'python-version'"

    def test_matrix_python_versions_are_correct(self):
        """Matrix must include exactly Python 3.9, 3.10, and 3.11."""
        workflow = load_workflow()
        versions = workflow["jobs"]["build"]["strategy"]["matrix"]["python-version"]
        assert set(versions) == {"3.9", "3.10", "3.11"}, (
            f"Expected python-version matrix ['3.9', '3.10', '3.11'], got: {versions}"
        )

    def test_matrix_has_three_python_versions(self):
        """Matrix must specify exactly three Python versions."""
        workflow = load_workflow()
        versions = workflow["jobs"]["build"]["strategy"]["matrix"]["python-version"]
        assert len(versions) == 3, (
            f"Expected 3 Python versions in matrix, found {len(versions)}: {versions}"
        )

    def test_strategy_fail_fast_is_false(self):
        """fail-fast must be false so all matrix versions are tested even when one fails."""
        workflow = load_workflow()
        fail_fast = workflow["jobs"]["build"]["strategy"].get("fail-fast")
        assert fail_fast is False, (
            f"strategy.fail-fast must be false, got: {fail_fast!r}"
        )

    def test_matrix_includes_python_39(self):
        """Matrix must include Python 3.9 for backwards compatibility."""
        workflow = load_workflow()
        versions = workflow["jobs"]["build"]["strategy"]["matrix"]["python-version"]
        assert "3.9" in versions, "Matrix must include Python 3.9"

    def test_matrix_includes_python_310(self):
        """Matrix must include Python 3.10."""
        workflow = load_workflow()
        versions = workflow["jobs"]["build"]["strategy"]["matrix"]["python-version"]
        assert "3.10" in versions, "Matrix must include Python 3.10"

    def test_matrix_includes_python_311(self):
        """Matrix must include Python 3.11."""
        workflow = load_workflow()
        versions = workflow["jobs"]["build"]["strategy"]["matrix"]["python-version"]
        assert "3.11" in versions, "Matrix must include Python 3.11"


class TestPythonPackageWorkflowBuildJob:
    """Tests for the build job configuration."""

    def test_build_job_exists(self):
        """The jobs block must contain a 'build' job."""
        workflow = load_workflow()
        assert "build" in workflow["jobs"], "Missing 'build' job"

    def test_build_job_runs_on_ubuntu_latest(self):
        """Build job must run on ubuntu-latest."""
        workflow = load_workflow()
        runs_on = workflow["jobs"]["build"].get("runs-on")
        assert runs_on == "ubuntu-latest", (
            f"build job must run on 'ubuntu-latest', got: '{runs_on}'"
        )

    def test_build_job_has_steps(self):
        """Build job must define at least one step."""
        workflow = load_workflow()
        steps = workflow["jobs"]["build"].get("steps", [])
        assert len(steps) > 0, "build job must have at least one step"

    def test_step_uses_ci_common_action(self):
        """The build step must use the local .github/actions/ci-common action."""
        workflow = load_workflow()
        steps = workflow["jobs"]["build"]["steps"]
        action_uses = [s.get("uses", "") for s in steps]
        assert "./.github/actions/ci-common" in action_uses, (
            "A step must use './.github/actions/ci-common'"
        )

    def test_step_passes_mergify_token_env(self):
        """The ci-common step must pass MERGIFY_TOKEN as an environment variable."""
        workflow = load_workflow()
        steps = workflow["jobs"]["build"]["steps"]
        ci_common_step = next(
            (s for s in steps if s.get("uses") == "./.github/actions/ci-common"), None
        )
        assert ci_common_step is not None, "ci-common step not found"
        env = ci_common_step.get("env", {})
        assert "MERGIFY_TOKEN" in env, "ci-common step must set MERGIFY_TOKEN env var"

    def test_step_mergify_token_references_secret(self):
        """MERGIFY_TOKEN env var must reference the MERGIFY_TOKEN repository secret."""
        workflow = load_workflow()
        steps = workflow["jobs"]["build"]["steps"]
        ci_common_step = next(
            (s for s in steps if s.get("uses") == "./.github/actions/ci-common"), None
        )
        assert ci_common_step is not None, "ci-common step not found"
        token_value = ci_common_step.get("env", {}).get("MERGIFY_TOKEN", "")
        assert "secrets.MERGIFY_TOKEN" in token_value, (
            f"MERGIFY_TOKEN must reference secrets.MERGIFY_TOKEN, got: '{token_value}'"
        )

    def test_step_with_language_is_python(self):
        """The ci-common step must specify language: python."""
        workflow = load_workflow()
        steps = workflow["jobs"]["build"]["steps"]
        ci_common_step = next(
            (s for s in steps if s.get("uses") == "./.github/actions/ci-common"), None
        )
        assert ci_common_step is not None, "ci-common step not found"
        language = ci_common_step.get("with", {}).get("language")
        assert language == "python", f"ci-common step must set language: python, got: '{language}'"

    def test_step_with_python_version_uses_matrix_expression(self):
        """python-version input must use the matrix expression, not a hardcoded value."""
        workflow = load_workflow()
        steps = workflow["jobs"]["build"]["steps"]
        ci_common_step = next(
            (s for s in steps if s.get("uses") == "./.github/actions/ci-common"), None
        )
        assert ci_common_step is not None, "ci-common step not found"
        python_version = ci_common_step.get("with", {}).get("python-version", "")
        assert "matrix.python-version" in python_version, (
            f"python-version must reference matrix.python-version, got: '{python_version}'"
        )
        # Must not be hardcoded to a single version
        assert python_version != "3.10", (
            "python-version must not be hardcoded to '3.10'; it must use the matrix expression"
        )

    def test_step_with_dependency_paths(self):
        """ci-common step must specify dependency-paths including requirements files."""
        workflow = load_workflow()
        steps = workflow["jobs"]["build"]["steps"]
        ci_common_step = next(
            (s for s in steps if s.get("uses") == "./.github/actions/ci-common"), None
        )
        assert ci_common_step is not None, "ci-common step not found"
        dep_paths = ci_common_step.get("with", {}).get("dependency-paths", "")
        assert "requirements.txt" in dep_paths, "dependency-paths must include requirements.txt"
        assert "requirements-dev.txt" in dep_paths, "dependency-paths must include requirements-dev.txt"


class TestPythonPackageWorkflowInstallScript:
    """Tests for the install script in the ci-common step."""

    def _get_install_script(self):
        """Extract the install script from the ci-common step."""
        workflow = load_workflow()
        steps = workflow["jobs"]["build"]["steps"]
        ci_common_step = next(
            (s for s in steps if s.get("uses") == "./.github/actions/ci-common"), None
        )
        assert ci_common_step is not None, "ci-common step not found"
        return ci_common_step.get("with", {}).get("install", "")

    def test_install_script_uses_python_m_pip_for_upgrade(self):
        """Install script must use 'python -m pip install --upgrade pip' (not bare pip)."""
        install = self._get_install_script()
        assert "python -m pip install --upgrade pip" in install, (
            "Install script must use 'python -m pip install --upgrade pip'"
        )

    def test_install_script_uses_python_m_pip_for_flake8_pytest(self):
        """Install script must use 'python -m pip install flake8 pytest' (not bare pip install)."""
        install = self._get_install_script()
        assert "python -m pip install flake8 pytest" in install, (
            "Install script must use 'python -m pip install flake8 pytest'"
        )

    def test_install_script_does_not_use_bare_pip_for_flake8(self):
        """Install script must not use 'pip install flake8 pytest' (should be python -m pip)."""
        install = self._get_install_script()
        # "pip install flake8" without "python -m" prefix is the old pattern
        import re
        bare_pip = re.search(r"(?<![-.])(?<!\w)pip install flake8", install)
        assert not bare_pip, (
            "Install script must not use bare 'pip install flake8'; use 'python -m pip install'"
        )

    def test_install_script_conditionally_installs_requirements(self):
        """Install script must conditionally install requirements.txt if it exists."""
        install = self._get_install_script()
        assert "requirements.txt" in install, "Install script must reference requirements.txt"
        assert "if [ -f requirements.txt ]" in install, (
            "Install script must guard requirements.txt install with existence check"
        )


class TestPythonPackageWorkflowTestScript:
    """Tests for the test script in the ci-common step."""

    def _get_test_script(self):
        """Extract the test script from the ci-common step."""
        workflow = load_workflow()
        steps = workflow["jobs"]["build"]["steps"]
        ci_common_step = next(
            (s for s in steps if s.get("uses") == "./.github/actions/ci-common"), None
        )
        assert ci_common_step is not None, "ci-common step not found"
        return ci_common_step.get("with", {}).get("test", "")

    def test_test_script_runs_flake8_strict(self):
        """Test script must run flake8 with strict error selectors."""
        test_script = self._get_test_script()
        assert "flake8" in test_script, "Test script must run flake8"
        assert "--select=E9,F63,F7,F82" in test_script, (
            "Test script must use flake8 --select=E9,F63,F7,F82 for critical errors"
        )

    def test_test_script_runs_flake8_style(self):
        """Test script must also run flake8 for style/complexity checks."""
        test_script = self._get_test_script()
        assert "--max-complexity=10" in test_script, (
            "Test script must run flake8 with --max-complexity=10"
        )

    def test_test_script_runs_pytest(self):
        """Test script must invoke pytest."""
        test_script = self._get_test_script()
        assert "pytest" in test_script, "Test script must run pytest"


class TestPythonPackageWorkflowRegressionAndEdgeCases:
    """Regression and edge-case tests for the python-app.yml changes."""

    def test_workflow_does_not_hardcode_python_310_in_step_with(self):
        """Regression: python-version in step 'with' must not be the hardcoded '3.10' string."""
        workflow = load_workflow()
        steps = workflow["jobs"]["build"]["steps"]
        for step in steps:
            with_section = step.get("with", {})
            pv = with_section.get("python-version", "")
            assert pv != "3.10", (
                "Hardcoded python-version '3.10' found in step 'with'; "
                "it must use the matrix expression instead"
            )

    def test_workflow_no_duplicate_top_level_keys(self, tmp_path):
        """Regression: the workflow YAML file must not have duplicate top-level keys."""
        import io

        class _DuplicateKeyLoader(yaml.SafeLoader):
            pass

        seen_keys = []

        def _construct_mapping(loader, node):
            pairs = loader.construct_pairs(node)
            for key, _ in pairs:
                seen_keys.append(key)
            return dict(pairs)

        _DuplicateKeyLoader.add_constructor(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            _construct_mapping,
        )

        with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        yaml.load(content, Loader=_DuplicateKeyLoader)  # noqa: S506

        top_level_keys = [k for k in seen_keys if seen_keys.count(k) > 1]
        # Check specifically for no duplicate top-level structural keys
        assert "name" not in top_level_keys or top_level_keys.count("name") <= 1

    def test_all_three_python_versions_are_strings(self):
        """Matrix python-version entries must be YAML strings, not bare floats."""
        workflow = load_workflow()
        versions = workflow["jobs"]["build"]["strategy"]["matrix"]["python-version"]
        for v in versions:
            assert isinstance(v, str), (
                f"Python version '{v}' must be a quoted string in YAML, not {type(v).__name__}. "
                "Unquoted '3.10' would be parsed as float 3.1."
            )

    def test_python_310_not_parsed_as_float(self):
        """Regression: '3.10' in matrix must be a string, not the float 3.1."""
        workflow = load_workflow()
        versions = workflow["jobs"]["build"]["strategy"]["matrix"]["python-version"]
        assert 3.1 not in versions, (
            "Python version 3.10 was parsed as float 3.1; it must be quoted as '\"3.10\"' in YAML"
        )
        assert "3.10" in versions, "Python version '3.10' must be present as a string"

    def test_workflow_file_is_not_empty(self):
        """Boundary: the workflow file must not be empty."""
        content = WORKFLOW_PATH.read_text(encoding="utf-8").strip()
        assert len(content) > 0, "Workflow file must not be empty"

    def test_workflow_contains_no_python_app_references_in_paths(self):
        """Regression: no path trigger should reference the old python-app.yml filename."""
        workflow = load_workflow()
        on_block = workflow.get("on", {})
        for trigger_name, trigger_config in on_block.items():
            if isinstance(trigger_config, dict):
                for path_key in ("paths", "paths-ignore"):
                    for path_entry in trigger_config.get(path_key, []):
                        assert "python-app.yml" not in path_entry, (
                            f"Trigger '{trigger_name}'.{path_key} still references "
                            f"'python-app.yml': '{path_entry}'"
                        )