"""Unit tests for Super-Linter workflow actionlint ignore arguments."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUPER_LINTER_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "super-linter.yml"
MODELS_PERMISSION_DIAGNOSTIC = 'unknown permission scope "models"'
MODELSX_PERMISSION_DIAGNOSTIC = 'unknown permission scope "modelsx"'


def _github_actions_command_args(workflow: dict) -> str:
    """Return GITHUB_ACTIONS_COMMAND_ARGS from the Super-Linter run-lint job.

    Args:
        workflow: Parsed Super-Linter workflow mapping.

    Returns:
        The command-args string passed through to actionlint.

    Raises:
        AssertionError: If the env value is missing or not a string.
    """
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    run_lint = jobs["run-lint"]
    assert isinstance(run_lint, dict)
    steps = run_lint["steps"]
    assert isinstance(steps, list)

    for step in steps:
        if not isinstance(step, dict):
            continue
        env = step.get("env")
        if not isinstance(env, dict):
            continue
        command_args = env.get("GITHUB_ACTIONS_COMMAND_ARGS")
        if command_args is not None:
            assert isinstance(command_args, str)
            return command_args

    raise AssertionError("GITHUB_ACTIONS_COMMAND_ARGS is not set on any run-lint step")


def _actionlint_ignore_pattern(command_args: str) -> str:
    """Extract the space-free actionlint -ignore regex from command args.

    Super-Linter splits *_COMMAND_ARGS on spaces without quote handling, so the
    ignore pattern must be a single token after ``-ignore``.

    Args:
        command_args: Raw GITHUB_ACTIONS_COMMAND_ARGS value.

    Returns:
        The regular expression passed to actionlint ``-ignore``.
    """
    parts = command_args.split()
    assert parts == ["-ignore", parts[1]], command_args
    pattern = parts[1]
    assert " " not in pattern
    return pattern


def test_actionlint_ignore_matches_models_permission_only() -> None:
    """Ignore the models compatibility diagnostic without hiding modelsx."""
    with SUPER_LINTER_WORKFLOW.open(encoding="utf-8") as handle:
        workflow = yaml.safe_load(handle)

    assert isinstance(workflow, dict)
    pattern = _actionlint_ignore_pattern(_github_actions_command_args(workflow))
    ignore = re.compile(pattern)

    assert ignore.search(MODELS_PERMISSION_DIAGNOSTIC)
    assert ignore.search(f"{MODELS_PERMISSION_DIAGNOSTIC}. all available permission scopes are")
    assert ignore.search(MODELSX_PERMISSION_DIAGNOSTIC) is None
    assert ignore.search('unknown permission scope "contents"') is None
