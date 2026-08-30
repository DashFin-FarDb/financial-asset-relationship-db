"""Regression tests for bounded PR automation and the CircleCI pytest pilot."""

from pathlib import Path

import yaml


def _load_yaml(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def test_pr_agents_do_not_fan_out_on_check_suites_or_commits():
    pr_agent = _load_yaml(".github/workflows/pr-agent.yml")
    pr_copilot = _load_yaml(".github/workflows/pr-copilot.yml")

    assert set(pr_agent["on"]) == {"issue_comment"}
    assert set(pr_copilot["on"]) == {"issue_comment", "workflow_dispatch"}
    assert pr_copilot["on"]["workflow_dispatch"]["inputs"]["pr_number"]["required"] is True
    assert "github.event_name" in pr_copilot["concurrency"]["group"]


def test_dependency_auto_approval_is_disabled():
    workflow = _load_yaml(".github/workflows/pr-agent.yml")
    job = workflow["jobs"]["dependency-update"]
    serialized = yaml.safe_dump(job)

    assert str(job["if"]).strip().lower() in {"false", "${{ false }}"}
    assert job["permissions"] == {"contents": "read"}
    assert "createReview" not in serialized
    assert "APPROVE" not in serialized


def test_pr_agent_cannot_make_automatic_merge_claims():
    workflow = _load_yaml(".github/workflows/pr-agent.yml")
    job = workflow["jobs"]["auto-merge-check"]
    serialized = yaml.safe_dump(job)

    assert str(job["if"]).strip().lower() in {"false", "${{ false }}"}
    assert job["permissions"] == {"contents": "read"}
    assert "github-script" not in serialized
    assert "Ready for Merge" not in serialized


def test_pr_copilot_publishes_read_only_exact_head_status():
    workflow_text = Path(".github/workflows/pr-copilot.yml").read_text(encoding="utf-8")
    status_job = workflow_text.split("  status-update:", 1)[1].split("  review-handler:", 1)[0]

    assert "@pr-copilot status update" in workflow_text
    assert "GITHUB_STEP_SUMMARY" in status_job
    assert "actions/upload-artifact@" in status_job
    assert "--jq .head.sha" in status_job
    assert "createComment" not in status_job
    assert "updateComment" not in status_job


def test_circleci_python_pilot_is_two_way_and_timing_balanced():
    config = _load_yaml(".circleci/config.yml")
    job = config["jobs"]["python-test"]
    commands = "\n".join(
        step.get("run", {}).get("command", "")
        for step in job["steps"]
        if isinstance(step, dict) and isinstance(step.get("run"), dict)
    )

    assert job["parallelism"] == 2
    assert job["executor"] == "python-test-executor"
    assert "circleci tests run" in commands
    assert "--split-by=timings" in commands
    assert "--timings-type=file" in commands
    assert "--junitxml=" in commands


def test_circleci_pilot_does_not_claim_other_stub_jobs_are_real_checks():
    config = _load_yaml(".circleci/config.yml")
    for job_name in (
        "python-lint",
        "python-security",
        "frontend-lint",
        "frontend-build",
        "docker-build",
    ):
        assert config["jobs"][job_name]["steps"] == ["dummy-step"]
