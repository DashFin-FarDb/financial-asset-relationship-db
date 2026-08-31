"""Contract tests for the Super-Linter toolchain migration."""

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUPER_LINTER_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "super-linter.yml"
SUMMARY_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "summary.yml"
SUPER_LINTER_USE = "super-linter/super-linter@4ce20838b8ab83717e78138c5b3a1407148e0918"


def _load_workflow(path: Path) -> dict[str, object]:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(workflow, dict)
    return workflow


def _super_linter_step() -> dict[str, object]:
    workflow = _load_workflow(SUPER_LINTER_WORKFLOW)
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    run_lint = jobs["run-lint"]
    assert isinstance(run_lint, dict)
    steps = run_lint["steps"]
    assert isinstance(steps, list)
    return next(step for step in steps if step.get("name") == "Lint Code Base")


def test_super_linter_uses_reviewed_v8_release_by_exact_commit() -> None:
    assert _super_linter_step()["uses"] == SUPER_LINTER_USE


def test_v8_validator_ownership_replaces_retired_flags() -> None:
    env = _super_linter_step()["env"]
    assert isinstance(env, dict)

    retired = {
        "VALIDATE_JAVASCRIPT_JSX",
        "VALIDATE_JAVASCRIPT_STANDARD",
        "VALIDATE_JSHINT",
        "VALIDATE_PYTHON_PYINK",
        "VALIDATE_TYPESCRIPT_STANDARD",
        "VALIDATE_TYPESCRIPT_TSX",
    }
    assert retired.isdisjoint(env)
    assert env["VALIDATE_JSX"] is False
    assert env["VALIDATE_TSX"] is False
    assert env["VALIDATE_BIOME_FORMAT"] is False
    assert env["VALIDATE_BIOME_LINT"] is False
    assert env["VALIDATE_PYTHON_RUFF_FORMAT"] is False


def test_actions_and_checkov_validators_remain_enabled() -> None:
    env = _super_linter_step()["env"]
    assert isinstance(env, dict)

    assert "VALIDATE_GITHUB_ACTIONS" not in env
    assert "VALIDATE_CHECKOV" not in env
    assert env["GITHUB_ACTIONS_CONFIG_FILE"] == "actionlint.yaml"


def test_models_read_permission_remains_in_motivating_workflow() -> None:
    workflow = _load_workflow(SUMMARY_WORKFLOW)
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    summary = jobs["summary"]
    assert isinstance(summary, dict)
    permissions = summary["permissions"]
    assert isinstance(permissions, dict)

    assert permissions["models"] == "read"


def test_frontend_runtime_has_dependency_free_healthcheck() -> None:
    dockerfile = (PROJECT_ROOT / "Dockerfile.frontend").read_text(encoding="utf-8")

    assert "HEALTHCHECK --interval=30s --timeout=5s" in dockerfile
    assert "node -e" in dockerfile
    assert "require('http').get" in dockerfile
    assert "process.env.PORT||3000" in dockerfile
