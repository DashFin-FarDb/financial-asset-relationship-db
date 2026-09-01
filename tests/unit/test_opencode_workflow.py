"""Security contract tests for the comment-triggered OpenCode workflow."""

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

WORKFLOW_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "opencode.yml"
TRUSTED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
UNTRUSTED_ASSOCIATIONS = {
    "CONTRIBUTOR",
    "FIRST_TIMER",
    "FIRST_TIME_CONTRIBUTOR",
    "MANNEQUIN",
    "NONE",
}


def _load_workflow() -> dict[str, Any]:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _opencode_job() -> dict[str, Any]:
    return _load_workflow()["jobs"]["opencode"]


def test_opencode_triggers_only_on_new_comments() -> None:
    workflow = _load_workflow()

    assert set(workflow["on"]) == {"issue_comment", "pull_request_review_comment"}
    assert workflow["on"]["issue_comment"]["types"] == ["created"]
    assert workflow["on"]["pull_request_review_comment"]["types"] == ["created"]


def test_opencode_job_requires_the_exact_trusted_association_set() -> None:
    condition = str(_opencode_job()["if"])
    match = re.search(
        r"contains\(fromJSON\('([^']+)'\),\s*github\.event\.comment\.author_association\)",
        condition,
    )

    assert match is not None, "OpenCode commands must be gated by commenter association at job level"
    configured_associations = set(json.loads(match.group(1)))
    assert configured_associations == TRUSTED_ASSOCIATIONS
    assert configured_associations.isdisjoint(UNTRUSTED_ASSOCIATIONS)


def test_opencode_command_gate_remains_bounded() -> None:
    condition = str(_opencode_job()["if"])
    commands = {
        "contains(github.event.comment.body, ' /oc')",
        "startsWith(github.event.comment.body, '/oc')",
        "contains(github.event.comment.body, ' /opencode')",
        "startsWith(github.event.comment.body, '/opencode')",
    }

    assert all(command in condition for command in commands)
    assert condition.count("github.event.comment.body") == len(commands)
    assert "author_association" in condition.split("github.event.comment.body", maxsplit=1)[0]


def test_opencode_job_retains_only_required_token_permissions() -> None:
    assert _opencode_job()["permissions"] == {
        "id-token": "write",
        "contents": "read",
    }


def test_opencode_secret_step_stays_behind_the_job_gate() -> None:
    steps = _opencode_job()["steps"]
    assert len(steps) == 2

    checkout, opencode = steps
    assert checkout["uses"] == "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
    assert checkout["with"]["persist-credentials"] is False

    assert opencode["uses"] == "anomalyco/opencode/github@47b6b6f5f4f9b42d2bce7af1c4e5bf6efaf22ba7"
    assert opencode["env"] == {"OPENCODE_API_KEY": "${{ secrets.OPENCODE_API_KEY }}"}
    assert opencode["with"] == {"model": "opencode/big-pickle"}
