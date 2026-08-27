"""GNC Phase 2 deterministic advisory tests."""

from __future__ import annotations

import ast
import copy
import json
import re
from pathlib import Path
from typing import Any, Mapping

import pytest

from scripts.gnc.advisory import (
    APPROVAL_MARKER,
    CONTRACT_END,
    CONTRACT_START,
    MAX_AGGREGATE_PATH_BYTES,
    MAX_APPROVAL_COMMENTS,
    MAX_ARTIFACT_BYTES,
    MAX_CHANGED_PATHS,
    MAX_CONTRACT_BYTES,
    MAX_EVIDENCE_RECORDS,
    MAX_PATH_BYTES,
    MAX_PR_BODY_BYTES,
    MAX_REVIEW_RECORDS,
    MAX_SUMMARY_BYTES,
    AdvisoryInputError,
    GitHubMetadataClient,
    canonical_json_bytes,
    collect_github_snapshot,
    evaluate_advisory,
    failure_report,
    main,
    render_summary,
    write_outputs,
)
from scripts.gnc.schema import canonical_hash, validate_contract

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "gnc-advisory.yml"
CASES = REPO_ROOT / "tests" / "fixtures" / "gnc" / "advisory" / "phase2-cases.json"
SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40


def _contract(**overrides: object) -> dict:
    contract: dict[str, object] = {
        "schema_version": 1,
        "contract_id": "gnc.test-phase2",
        "version": 1,
        "parent_issue": 1739,
        "objective": "Evaluate one exact pull-request head.",
        "base_sha": SHA_B,
        "policy_sha": SHA_B,
        "risk_class": "high",
        "allowed_paths": ["src/allowed.py"],
        "forbidden_paths": ["src/blocked.py"],
        "rules": [
            {
                "rule_id": "scope.allowlist",
                "type": "mandatory_invariant",
                "statement": "Only the approved path changes.",
            }
        ],
        "required_evidence": ["ci"],
        "merge_criteria": ["Exact-head evidence passes."],
        "stop_conditions": ["An unapproved path changes."],
        "approved_by": "mohavro",
        "approved_at": "2026-08-27T20:21:28Z",
    }
    contract.update(overrides)
    return contract


def _body(contract: dict) -> str:
    return f"PR description\n{CONTRACT_START}\n{json.dumps(contract, sort_keys=True)}\n{CONTRACT_END}\n"


def _approval(contract: dict, *, head_sha: str = SHA_A, actor: str = "mohavro") -> dict:
    normalized = validate_contract(contract)
    approval = {
        "actor": actor,
        "contract_hash": canonical_hash(normalized),
        "contract_version": normalized["version"],
        "head_sha": head_sha,
        "policy_sha": normalized["policy_sha"],
    }
    return {
        "body": f"{APPROVAL_MARKER}\n{json.dumps(approval, sort_keys=True, separators=(',', ':'))}",
        "created_at": "2026-08-27T21:00:00Z",
        "updated_at": "2026-08-27T21:00:00Z",
        "user": {"login": actor},
    }


def _snapshot(contract: dict | None = None) -> dict:
    selected = contract or _contract()
    current = {
        "body": _body(selected),
        "head_sha": SHA_A,
        "merge_base_sha": SHA_B,
        "policy_file_present": True,
        "target": "main",
        "target_sha": SHA_B,
    }
    return {
        "api_errors": [],
        "approval_comments": [_approval(selected)],
        "changed_files": [{"filename": "src/allowed.py", "status": "modified"}],
        "current_pr": current,
        "event_pr": {"head_sha": SHA_A, "target": "main", "target_sha": SHA_B},
        "evidence": [
            {
                "head_sha": SHA_A,
                "requirement_id": "ci",
                "source": "check_run",
                "state": "passed",
                "target": "main",
            }
        ],
        "final_pr": {"head_sha": SHA_A, "target": "main", "target_sha": SHA_B},
        "pagination_complete": True,
        "pr_number": 42,
        "repository": "DashFin-FarDb/financial-asset-relationship-db",
        "review_threads": [],
        "reviews": [],
    }


def _codes(report: dict) -> set[str]:
    return {item["code"] for item in report["findings"]}


def _reapprove(snapshot: dict, contract: dict, *, head_sha: str = SHA_A) -> None:
    snapshot["current_pr"]["body"] = _body(contract)
    snapshot["approval_comments"] = [_approval(contract, head_sha=head_sha)]


@pytest.mark.unit
class TestContractAndApproval:
    @pytest.mark.parametrize(
        "body,code",
        [
            ("no markers", "contract.markers-invalid"),
            (
                f"{CONTRACT_START}{{}}{CONTRACT_END}{CONTRACT_START}{{}}{CONTRACT_END}",
                "contract.markers-invalid",
            ),
            (f"{CONTRACT_START}\nnot-json\n{CONTRACT_END}", "contract.malformed"),
        ],
    )
    def test_missing_duplicated_and_malformed_contracts_need_human(self, body: str, code: str) -> None:
        snapshot = _snapshot()
        snapshot["current_pr"]["body"] = body
        report = evaluate_advisory(snapshot)
        assert report["state"] == "needs-human"
        assert code in _codes(report)

    def test_body_and_contract_size_bounds_need_human(self) -> None:
        body_bound = _snapshot()
        body_bound["current_pr"]["body"] = "x" * (MAX_PR_BODY_BYTES + 1)
        assert "contract.body-oversized" in _codes(evaluate_advisory(body_bound))

        contract_bound = _snapshot()
        contract_bound["current_pr"]["body"] = (
            f"{CONTRACT_START}\n" + "x" * (MAX_CONTRACT_BYTES + 1) + f"\n{CONTRACT_END}"
        )
        assert "contract.oversized" in _codes(evaluate_advisory(contract_bound))

    def test_unapproved_wrong_actor_edited_and_hash_mismatch_never_pass(self) -> None:
        missing = _snapshot()
        missing["approval_comments"] = []
        assert "approval.missing-or-invalid" in _codes(evaluate_advisory(missing))

        wrong_actor = _snapshot()
        wrong_actor["approval_comments"] = [_approval(_contract(), actor="someone-else")]
        assert "approval.missing-or-invalid" in _codes(evaluate_advisory(wrong_actor))

        edited = _snapshot()
        edited["approval_comments"][0]["updated_at"] = "2026-08-27T21:00:01Z"
        assert "approval.missing-or-invalid" in _codes(evaluate_advisory(edited))

        missing_timestamp = _snapshot()
        missing_timestamp["approval_comments"][0].pop("created_at")
        assert "approval.missing-or-invalid" in _codes(evaluate_advisory(missing_timestamp))

        changed = _snapshot()
        changed_contract = _contract(objective="Changed after approval.")
        changed["current_pr"]["body"] = _body(changed_contract)
        assert "approval.missing-or-invalid" in _codes(evaluate_advisory(changed))

    def test_amendment_requires_phase1_lineage_and_a_new_approval(self) -> None:
        invalid = _snapshot()
        invalid["current_pr"]["body"] = _body(_contract(version=2))
        report = evaluate_advisory(invalid)
        assert report["state"] == "needs-human"
        assert "contract.malformed" in _codes(report)

        original = validate_contract(_contract())
        amended = _contract(
            version=2,
            previous_contract_hash=canonical_hash(original),
            amendment_reason="Add an approved exact-head validation.",
        )
        valid = _snapshot(amended)
        assert evaluate_advisory(valid)["state"] == "pass"

    def test_self_declared_approval_is_not_the_approval_proof(self) -> None:
        contract = _contract(approved_by="mohavro")
        snapshot = _snapshot(contract)
        snapshot["approval_comments"] = []
        assert evaluate_advisory(snapshot)["state"] == "needs-human"

    def test_approval_comment_bound_needs_human(self) -> None:
        snapshot = _snapshot()
        snapshot["approval_comments"] = [{}] * (MAX_APPROVAL_COMMENTS + 1)
        assert "approval.comments-oversized" in _codes(evaluate_advisory(snapshot))


@pytest.mark.unit
class TestExactBindings:
    @pytest.mark.parametrize(
        "mutation,code",
        [
            ("head", "refs.superseded-head"),
            ("base", "refs.base-moved"),
            ("final", "refs.stale-completion"),
            ("target", "refs.wrong-target"),
            ("policy", "refs.policy-mismatch"),
            ("merge-base", "refs.contract-base-mismatch"),
            ("policy-file", "refs.policy-unavailable"),
        ],
    )
    def test_exact_ref_mismatches_need_human(self, mutation: str, code: str) -> None:
        snapshot = _snapshot()
        if mutation == "head":
            snapshot["event_pr"]["head_sha"] = SHA_C
        elif mutation == "base":
            snapshot["event_pr"]["target_sha"] = SHA_C
        elif mutation == "final":
            snapshot["final_pr"]["head_sha"] = SHA_C
        elif mutation == "target":
            snapshot["current_pr"]["target"] = "release"
        elif mutation == "policy":
            contract = _contract(policy_sha=SHA_C)
            _reapprove(snapshot, contract)
        elif mutation == "merge-base":
            snapshot["current_pr"]["merge_base_sha"] = SHA_C
        else:
            snapshot["current_pr"]["policy_file_present"] = False
        report = evaluate_advisory(snapshot)
        assert report["state"] == "needs-human"
        assert code in _codes(report)

    def test_deleted_or_ambiguous_head_fails_closed(self) -> None:
        snapshot = _snapshot()
        snapshot["final_pr"]["head_sha"] = None
        assert evaluate_advisory(snapshot)["state"] == "needs-human"

    def test_fork_metadata_is_read_only_but_not_intrinsically_invalid(self) -> None:
        snapshot = _snapshot()
        snapshot["event_pr"]["is_fork"] = True
        snapshot["current_pr"]["is_fork"] = True
        assert evaluate_advisory(snapshot)["state"] == "pass"


@pytest.mark.unit
class TestChangedPaths:
    def test_forbidden_outside_and_missing_expected_paths_block(self) -> None:
        forbidden = _snapshot()
        forbidden["changed_files"] = [{"filename": "src/blocked.py", "status": "modified"}]
        report = evaluate_advisory(forbidden)
        assert report["state"] == "block"
        assert {"paths.forbidden", "paths.outside-allowlist", "paths.expected-missing"} <= _codes(report)

        missing = _snapshot()
        missing["changed_files"] = []
        assert "paths.expected-missing" in _codes(evaluate_advisory(missing))

    def test_rename_and_delete_inventory_is_complete(self) -> None:
        contract = _contract(allowed_paths=["src/old.py", "src/new.py"], forbidden_paths=["src/blocked.py"])
        renamed = _snapshot(contract)
        renamed["changed_files"] = [{"filename": "src/new.py", "previous_filename": "src/old.py", "status": "renamed"}]
        report = evaluate_advisory(renamed)
        assert report["state"] == "pass"
        assert {item["role"] for item in report["changed_paths"]} == {"current", "previous"}

        deleted = _snapshot()
        deleted["changed_files"] = [{"filename": "src/allowed.py", "status": "removed"}]
        assert evaluate_advisory(deleted)["state"] == "pass"

        origin_unavailable = _snapshot()
        origin_unavailable["changed_files"] = [
            {"filename": "src/allowed.py", "previous_filename": None, "status": "renamed"}
        ]
        report = evaluate_advisory(origin_unavailable)
        assert "paths.rename-origin-unavailable" in _codes(report)
        assert report["bindings"]["head_sha"] == SHA_A

    def test_path_canonicalization_and_component_scopes_are_deterministic(self) -> None:
        contract = _contract(allowed_paths=["src"], forbidden_paths=["frontend"])
        snapshot = _snapshot(contract)
        snapshot["changed_files"] = [{"filename": "src\\module\\file.py", "status": "modified"}]
        report = evaluate_advisory(snapshot)
        assert report["state"] == "pass"
        assert report["changed_paths"][0]["path"] == "src/module/file.py"

        near_prefix = _snapshot(contract)
        near_prefix["changed_files"] = [{"filename": "src-other/file.py", "status": "modified"}]
        assert "paths.outside-allowlist" in _codes(evaluate_advisory(near_prefix))

    @pytest.mark.parametrize("path", ["../escape.py", "/absolute.py", "C:/drive.py", "//server/share.py"])
    def test_traversal_and_absolute_paths_need_human(self, path: str) -> None:
        snapshot = _snapshot()
        snapshot["changed_files"] = [{"filename": path, "status": "modified"}]
        assert "paths.unsafe" in _codes(evaluate_advisory(snapshot))

    def test_duplicate_and_explicit_path_bounds_need_human(self) -> None:
        duplicate = _snapshot()
        duplicate["changed_files"] = [
            {"filename": "src/allowed.py", "status": "modified"},
            {"filename": "src/./allowed.py", "status": "modified"},
        ]
        duplicate_report = evaluate_advisory(duplicate)
        assert "paths.duplicate" in _codes(duplicate_report)
        assert duplicate_report["bindings"]["contract_id"] == "gnc.test-phase2"

        too_many = _snapshot()
        too_many["changed_files"] = [
            {"filename": f"src/{index}.py", "status": "modified"} for index in range(MAX_CHANGED_PATHS + 1)
        ]
        assert "paths.too-many" in _codes(evaluate_advisory(too_many))

        item_bound = _snapshot()
        item_bound["changed_files"] = [{"filename": "x" * (MAX_PATH_BYTES + 1), "status": "modified"}]
        assert "paths.item-oversized" in _codes(evaluate_advisory(item_bound))

        aggregate = _snapshot(_contract(allowed_paths=["scope"], forbidden_paths=["blocked"]))
        aggregate["changed_files"] = [
            {
                "filename": f"scope/new-{index}-" + "x" * 480,
                "previous_filename": f"scope/old-{index}-" + "y" * 480,
                "status": "renamed",
            }
            for index in range(MAX_CHANGED_PATHS)
        ]
        assert MAX_CHANGED_PATHS * MAX_PATH_BYTES < MAX_AGGREGATE_PATH_BYTES * 2
        assert "paths.aggregate-oversized" in _codes(evaluate_advisory(aggregate))


@pytest.mark.unit
class TestEvidenceAndReviews:
    @pytest.mark.parametrize(
        "state,expected_state,code",
        [
            ("passed", "pass", None),
            ("failed", "block", "evidence.failed"),
            ("skipped", "needs-human", "evidence.unavailable"),
            ("canceled", "needs-human", "evidence.unavailable"),
            ("unavailable", "needs-human", "evidence.unavailable"),
            ("pending", "needs-human", "evidence.unavailable"),
        ],
    )
    def test_evidence_outcomes(self, state: str, expected_state: str, code: str | None) -> None:
        snapshot = _snapshot()
        snapshot["evidence"][0]["state"] = state
        report = evaluate_advisory(snapshot)
        assert report["state"] == expected_state
        if code is not None:
            assert code in _codes(report)

    def test_missing_stale_wrong_target_and_unapproved_sources_need_human(self) -> None:
        missing = _snapshot()
        missing["evidence"] = []
        assert "evidence.missing" in _codes(evaluate_advisory(missing))

        stale = _snapshot()
        stale["evidence"][0]["head_sha"] = SHA_C
        assert "evidence.stale-sha" in _codes(evaluate_advisory(stale))

        missing_head = _snapshot()
        missing_head["evidence"][0]["head_sha"] = None
        assert evaluate_advisory(missing_head)["state"] == "needs-human"

        wrong_target = _snapshot()
        wrong_target["evidence"][0]["target"] = "release"
        assert "evidence.wrong-target" in _codes(evaluate_advisory(wrong_target))

        unapproved = _snapshot()
        unapproved["evidence"][0]["source"] = "external-artifact"
        assert "evidence.source-unapproved" in _codes(evaluate_advisory(unapproved))

    def test_failed_exact_head_evidence_cannot_be_masked_by_a_pass(self) -> None:
        snapshot = _snapshot()
        snapshot["evidence"].append({**snapshot["evidence"][0], "state": "failed"})
        report = evaluate_advisory(snapshot)
        assert report["state"] == "block"
        assert "evidence.failed" in _codes(report)

    def test_unresolved_deterministic_blocker_and_advisory_only_thread_are_distinct(self) -> None:
        blocked = _snapshot()
        blocked["review_threads"] = [
            {
                "is_outdated": False,
                "is_resolved": False,
                "path": "src/allowed.py",
                "review_state": "CHANGES_REQUESTED",
            }
        ]
        report = evaluate_advisory(blocked)
        assert report["state"] == "block"
        assert "reviews.unresolved-blocker" in _codes(report)

        advisory = _snapshot()
        advisory["review_threads"] = [
            {
                "is_outdated": False,
                "is_resolved": False,
                "path": "src/allowed.py",
                "review_state": "COMMENTED",
            }
        ]
        report = evaluate_advisory(advisory)
        assert report["state"] == "pass"
        assert "reviews.unresolved-advisory" in _codes(report)

    def test_review_and_evidence_record_bounds_need_human(self) -> None:
        reviews = _snapshot()
        reviews["reviews"] = [{"state": "COMMENTED"}] * (MAX_REVIEW_RECORDS + 1)
        assert "reviews.too-many" in _codes(evaluate_advisory(reviews))

        evidence = _snapshot()
        evidence["evidence"] = evidence["evidence"] * (MAX_EVIDENCE_RECORDS + 1)
        assert "evidence.too-many" in _codes(evaluate_advisory(evidence))


@pytest.mark.unit
class TestFailuresBoundsAndDeterminism:
    @pytest.mark.parametrize("field", ["pagination_complete", "api_errors"])
    def test_incomplete_pagination_and_api_errors_never_pass(self, field: str) -> None:
        snapshot = _snapshot()
        if field == "pagination_complete":
            snapshot[field] = False
        else:
            snapshot[field] = ["rate-limited"]
        report = evaluate_advisory(snapshot)
        assert report["state"] == "needs-human"
        assert "metadata.incomplete" in _codes(report)

    @pytest.mark.parametrize("code", ["api.rate-limited", "api.unavailable", "api.pagination-incomplete"])
    def test_runtime_api_failures_have_sanitized_needs_human_reports(self, code: str) -> None:
        report = failure_report(repository="owner/repo", pr_number=1, code=code)
        assert report["state"] == "needs-human"
        assert code in _codes(report)

    def test_fixture_cases_are_golden_and_repeat_byte_identically(self) -> None:
        fixture = json.loads(CASES.read_text(encoding="utf-8"))
        assert fixture["schema_version"] == 1
        for case in fixture["cases"]:
            snapshot = _snapshot()
            mutation = case["mutation"]
            if mutation == "forbidden_path":
                snapshot["changed_files"] = [{"filename": "src/blocked.py", "status": "modified"}]
            elif mutation == "superseded_head":
                snapshot["event_pr"]["head_sha"] = SHA_C
            elif mutation == "missing_approval":
                snapshot["approval_comments"] = []
            elif mutation == "failed_evidence":
                snapshot["evidence"][0]["state"] = "failed"
            first = evaluate_advisory(snapshot)
            second = evaluate_advisory(copy.deepcopy(snapshot))
            assert canonical_json_bytes(first) == canonical_json_bytes(second)
            assert first["state"] == case["expected_state"]
            if case["expected_code"] is not None:
                assert case["expected_code"] in _codes(first)

    def test_output_sanitizes_secret_like_and_workflow_command_text(self) -> None:
        snapshot = _snapshot(_contract(allowed_paths=["src"], forbidden_paths=["blocked"]))
        secret_prefix = "_".join(("github", "pat"))
        snapshot["changed_files"] = [
            {"filename": f"src/{secret_prefix}_example-secret::warning.py", "status": "modified"}
        ]
        snapshot["evidence"].append(
            {
                "head_sha": SHA_A,
                "requirement_id": "other",
                "source": f"{secret_prefix}_hidden-source",
                "state": "passed",
                "target": "main",
            }
        )
        report = evaluate_advisory(snapshot)
        serialized = canonical_json_bytes(report).decode("utf-8")
        summary = render_summary(report)
        assert f"{secret_prefix}_example" not in serialized
        assert "::warning" not in serialized
        assert f"{secret_prefix}_example" not in summary
        assert "::warning" not in summary

    def test_summary_and_artifact_bounds_fail_safely(self, tmp_path: Path) -> None:
        large_report = {
            "bindings": {},
            "findings": [
                {"code": "x", "kind": "advisory", "subject": "y" * 1_000}
                for _ in range((MAX_SUMMARY_BYTES // 1_000) + 10)
            ],
            "pr_number": 1,
            "repository": "owner/repo",
            "state": "pass",
        }
        assert len(render_summary(large_report).encode("utf-8")) <= MAX_SUMMARY_BYTES

        oversized = dict(large_report, payload="z" * (MAX_ARTIFACT_BYTES + 1))
        artifact = tmp_path / "advisory.json"
        summary = tmp_path / "summary.md"
        write_outputs(oversized, artifact_path=artifact, summary_path=summary, runtime_root=tmp_path)
        written = json.loads(artifact.read_text(encoding="utf-8"))
        assert written["state"] == "needs-human"
        assert "artifact.bound-exceeded" in _codes(written)

    def test_output_paths_cannot_escape_the_runtime_root(self, tmp_path: Path) -> None:
        report = failure_report(repository="owner/repo", pr_number=1, code="synthetic.failure")
        with pytest.raises(AdvisoryInputError, match="output.artifact-path-invalid"):
            write_outputs(
                report,
                artifact_path=tmp_path.parent / "outside.json",
                summary_path=tmp_path / "summary.md",
                runtime_root=tmp_path,
            )

    def test_live_adapter_failure_preserves_event_identity(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        event = tmp_path / "event.json"
        event.write_text(
            json.dumps(
                {
                    "pull_request": {"number": 77},
                    "repository": {"full_name": "owner/repo"},
                }
            ),
            encoding="utf-8",
        )
        output = tmp_path / "advisory.json"
        summary = tmp_path / "summary.md"
        assert (
            main(
                [
                    "--event",
                    str(event),
                    "--output",
                    str(output),
                    "--summary",
                    str(summary),
                    "--runtime-root",
                    str(tmp_path),
                    "--repository",
                    "owner/repo",
                ]
            )
            == 0
        )
        report = json.loads(output.read_text(encoding="utf-8"))
        assert report["repository"] == "owner/repo"
        assert report["pr_number"] == 77
        assert "api.token-unavailable" in _codes(report)

        mismatch_output = tmp_path / "mismatch.json"
        assert (
            main(
                [
                    "--event",
                    str(event),
                    "--output",
                    str(mismatch_output),
                    "--summary",
                    str(summary),
                    "--runtime-root",
                    str(tmp_path),
                    "--repository",
                    "other/repo",
                ]
            )
            == 0
        )
        assert "event.repository-mismatch" in _codes(json.loads(mismatch_output.read_text(encoding="utf-8")))


class _PagedClient(GitHubMetadataClient):
    def __init__(self, responses: list[tuple[object, dict[str, str]]]) -> None:
        super().__init__(
            token=type(self).__name__,
            api_url="https://example.invalid",
            graphql_url="https://example.invalid/graphql",
        )
        self.responses = responses
        self.requests: list[tuple[str, Mapping[str, Any] | None]] = []

    def _request(self, url: str, *, payload: Mapping[str, Any] | None = None) -> tuple[Any, Mapping[str, str]]:
        self.requests.append((url, payload))
        return self.responses.pop(0)


class _SnapshotClient(GitHubMetadataClient):
    def __init__(self, contract: dict, *, policy_available: bool = True) -> None:
        super().__init__(
            token=type(self).__name__,
            api_url="https://example.invalid",
            graphql_url="https://example.invalid/graphql",
        )
        self.contract = contract
        self.policy_available = policy_available
        self.pr = {
            "body": _body(contract),
            "head": {"sha": SHA_A},
            "base": {"ref": "main", "sha": SHA_B},
        }

    def get(self, path: str) -> Any:
        if path.endswith("/pulls/42"):
            return self.pr
        if "/compare/" in path:
            return {"merge_base_commit": {"sha": SHA_B}}
        if "/contents/scripts/gnc/schema.py" in path:
            if not self.policy_available:
                raise AdvisoryInputError("api.request-failed")
            return {"sha": SHA_B}
        raise AssertionError(f"unexpected GET path: {path}")

    def pages(self, path: str, *, key: str | None, limit: int) -> list[Any]:
        del key, limit
        assert "&&" not in path
        if "/issues/1739/comments?" in path:
            return [_approval(self.contract)]
        if "/check-runs?" in path:
            return [{"conclusion": "success", "head_sha": SHA_A, "name": "ci", "status": "completed"}]
        if "/statuses?" in path or "/actions/runs?" in path:
            return []
        raise AssertionError(f"unexpected paged path: {path}")

    def changed_files(self, owner: str, name: str, number: int) -> list[dict[str, Any]]:
        assert (owner, name, number) == ("owner", "repo", 42)
        return [{"filename": "src/allowed.py", "previous_filename": None, "status": "modified"}]

    def reviews(self, owner: str, name: str, number: int) -> list[dict[str, Any]]:
        assert (owner, name, number) == ("owner", "repo", 42)
        return [
            {
                "commit_id": SHA_A,
                "id": 1,
                "state": "CHANGES_REQUESTED",
                "submitted_at": "2026-08-27T20:00:00Z",
                "user": {"login": "mohavro"},
            },
            {
                "commit_id": SHA_A,
                "id": 2,
                "state": "APPROVED",
                "submitted_at": "2026-08-27T21:00:00Z",
                "user": {"login": "mohavro"},
            },
        ]

    def review_threads(self, owner: str, name: str, number: int) -> list[dict[str, Any]]:
        assert (owner, name, number) == ("owner", "repo", 42)
        return []


@pytest.mark.unit
class TestPaginationProof:
    def test_all_pages_are_consumed(self) -> None:
        client = _PagedClient([([{"id": 1}], {"Link": '<next>; rel="next"'}), ([{"id": 2}], {})])
        assert client.pages("/records?", key=None, limit=2) == [{"id": 1}, {"id": 2}]

    def test_bound_with_an_unfetched_page_fails_closed(self) -> None:
        client = _PagedClient([([{"id": 1}], {"Link": '<next>; rel="next"'})])
        with pytest.raises(AdvisoryInputError, match="api.record-bound-exceeded"):
            client.pages("/records?", key=None, limit=1)

    @pytest.mark.parametrize(
        "url",
        ["file:///tmp/data", "".join(("http", "://api.github.com")), "https://user@example.com"],
    )
    def test_client_rejects_non_https_or_credentialed_origins(self, url: str) -> None:
        with pytest.raises(AdvisoryInputError, match="api.url-invalid"):
            GitHubMetadataClient(token=url, api_url=url, graphql_url="https://api.github.com/graphql")

    @pytest.mark.parametrize("path", ["/repos/owner/repo/../secret", "file:///tmp/data", "//example.com/data"])
    def test_client_rejects_traversing_or_absolute_api_paths(self, path: str) -> None:
        client = _PagedClient([])
        with pytest.raises(AdvisoryInputError, match="api.path-invalid"):
            client.get(path)

    def test_changed_files_graphql_selects_metadata_without_patches(self) -> None:
        response = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "files": {
                            "nodes": [{"changeType": "MODIFIED", "path": "src/allowed.py"}],
                            "pageInfo": {"endCursor": None, "hasNextPage": False},
                            "totalCount": 1,
                        }
                    }
                }
            }
        }
        client = _PagedClient([(response, {})])
        assert client.changed_files("owner", "repo", 42) == [
            {"filename": "src/allowed.py", "previous_filename": None, "status": "modified"}
        ]
        payload = client.requests[0][1]
        assert payload is not None
        query = str(payload["query"]).casefold()
        assert "patch" not in query
        assert "path changetype" in " ".join(query.split())

    def test_reviews_graphql_selects_state_without_bodies(self) -> None:
        response = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviews": {
                            "nodes": [
                                {
                                    "author": {"login": "mohavro"},
                                    "commit": {"oid": SHA_A},
                                    "databaseId": 9,
                                    "state": "APPROVED",
                                    "submittedAt": "2026-08-27T21:00:00Z",
                                }
                            ],
                            "pageInfo": {"endCursor": None, "hasNextPage": False},
                            "totalCount": 1,
                        }
                    }
                }
            }
        }
        client = _PagedClient([(response, {})])
        assert client.reviews("owner", "repo", 42) == [
            {
                "commit_id": SHA_A,
                "id": 9,
                "state": "APPROVED",
                "submitted_at": "2026-08-27T21:00:00Z",
                "user": {"login": "mohavro"},
            }
        ]
        payload = client.requests[0][1]
        assert payload is not None
        assert "body" not in str(payload["query"]).casefold()

    def test_graphql_total_count_mismatch_fails_closed(self) -> None:
        response = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "files": {
                            "nodes": [{"changeType": "MODIFIED", "path": "src/allowed.py"}],
                            "pageInfo": {"endCursor": None, "hasNextPage": False},
                            "totalCount": 2,
                        }
                    }
                }
            }
        }
        client = _PagedClient([(response, {})])
        with pytest.raises(AdvisoryInputError, match="api.pagination-incomplete"):
            client.changed_files("owner", "repo", 42)

    def test_all_thread_comment_review_states_are_collected(self) -> None:
        change_request = {
            "author": {"login": "reviewer"},
            "commit": {"oid": SHA_A},
            "databaseId": 7,
            "state": "CHANGES_REQUESTED",
            "submittedAt": "2026-08-27T20:00:00Z",
        }
        node = {
            "comments": {
                "nodes": [
                    {
                        "pullRequestReview": {
                            "author": {"login": "reviewer"},
                            "commit": {"oid": SHA_A},
                            "databaseId": 6,
                            "state": "COMMENTED",
                            "submittedAt": "2026-08-27T19:00:00Z",
                        }
                    },
                    {"pullRequestReview": change_request},
                ],
                "totalCount": 2,
            },
            "isOutdated": False,
            "isResolved": False,
            "path": "src/allowed.py",
        }
        response = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [node],
                            "pageInfo": {"endCursor": None, "hasNextPage": False},
                            "totalCount": 1,
                        }
                    }
                }
            }
        }
        client = _PagedClient([(response, {})])
        records = client.review_threads("owner", "repo", 42)
        assert [review["state"] for review in records[0]["reviews"]] == ["COMMENTED", "CHANGES_REQUESTED"]
        payload = client.requests[0][1]
        assert payload is not None
        assert "body" not in str(payload["query"]).casefold()
        snapshot = _snapshot()
        snapshot["review_threads"] = records
        assert "reviews.unresolved-blocker" in _codes(evaluate_advisory(snapshot))

    def test_later_decisive_review_supersedes_thread_change_request(self) -> None:
        change_request = {
            "commit_id": SHA_A,
            "id": 7,
            "state": "CHANGES_REQUESTED",
            "submitted_at": "2026-08-27T20:00:00Z",
            "user": {"login": "reviewer"},
        }
        snapshot = _snapshot()
        snapshot["reviews"] = [
            change_request,
            {
                **change_request,
                "id": 8,
                "state": "APPROVED",
                "submitted_at": "2026-08-27T21:00:00Z",
            },
        ]
        snapshot["review_threads"] = [
            {
                "is_outdated": False,
                "is_resolved": False,
                "path": "src/allowed.py",
                "reviews": [change_request],
            }
        ]
        report = evaluate_advisory(snapshot)
        assert report["state"] == "pass"
        assert "reviews.unresolved-blocker" not in _codes(report)
        assert "reviews.unresolved-advisory" in _codes(report)

    def test_truncated_thread_comment_connection_fails_closed(self) -> None:
        response = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [
                                {
                                    "comments": {"nodes": [{}], "totalCount": 2},
                                    "isOutdated": False,
                                    "isResolved": False,
                                    "path": "src/allowed.py",
                                }
                            ],
                            "pageInfo": {"endCursor": None, "hasNextPage": False},
                            "totalCount": 1,
                        }
                    }
                }
            }
        }
        client = _PagedClient([(response, {})])
        with pytest.raises(AdvisoryInputError, match="api.thread-comments-truncated"):
            client.review_threads("owner", "repo", 42)

    def test_live_snapshot_shapes_metadata_and_latest_review_wins(self) -> None:
        contract = _contract(required_evidence=["ci", "named-human-review"])
        snapshot = collect_github_snapshot(
            {
                "pull_request": {"number": 42, **_SnapshotClient(contract).pr},
                "repository": {"full_name": "owner/repo"},
            },
            _SnapshotClient(contract),
        )
        report = evaluate_advisory(snapshot)
        assert report["state"] == "pass"
        assert snapshot["changed_files"] == [
            {"filename": "src/allowed.py", "previous_filename": None, "status": "modified"}
        ]
        assert [record["state"] for record in snapshot["evidence"] if record["source"] == "review"] == ["passed"]

    def test_policy_lookup_failure_becomes_a_specific_advisory_finding(self) -> None:
        contract = _contract()
        client = _SnapshotClient(contract, policy_available=False)
        snapshot = collect_github_snapshot(
            {
                "pull_request": {"number": 42, **client.pr},
                "repository": {"full_name": "owner/repo"},
            },
            client,
        )
        assert snapshot["current_pr"]["policy_file_present"] is False
        assert "refs.policy-unavailable" in _codes(evaluate_advisory(snapshot))


@pytest.mark.unit
class TestWorkflowStaticContract:
    def test_workflow_is_trusted_read_only_pinned_and_non_enforcing(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        assert "pull_request_target:" in text
        for action in ("opened", "reopened", "edited", "synchronize", "ready_for_review"):
            assert action in text
        assert "ref: ${{ github.event.pull_request.base.sha }}" in text
        assert not re.search(r"ref:\s*\$\{\{[^\n]*head\.sha", text)
        assert "persist-credentials: false" in text
        assert "cancel-in-progress: true" in text
        assert "retention-days: 30" in text
        assert "continue-on-error" not in text
        assert "secrets." not in text
        assert "pull-requests: write" not in text
        assert "issues: write" not in text
        assert "contents: write" not in text
        assert "checks: write" not in text
        assert "id-token: write" not in text
        for permission in ("actions: read", "checks: read", "contents: read", "issues: read", "pull-requests: read"):
            assert permission in text
        uses = re.findall(r"uses:\s*[^@\s]+@([^\s]+)", text)
        assert uses
        assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in uses)
        for checkout in re.findall(r"git checkout[^\n]+", text):
            assert "scripts/gnc/advisory.py" not in checkout

    def test_workflow_has_one_summary_and_one_bounded_artifact(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        assert text.count("actions/upload-artifact@") == 1
        assert text.count("--summary") == 1
        assert text.count("--runtime-root") == 1
        assert "gnc-advisory.json" in text

    def test_runtime_module_imports_only_the_standard_library_and_landed_schema(self) -> None:
        tree = ast.parse((REPO_ROOT / "scripts" / "gnc" / "advisory.py").read_text(encoding="utf-8"))
        roots: set[str] = set()
        relative_imports: set[tuple[int, str | None]] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    roots.add(node.module.split(".")[0])
                else:
                    relative_imports.add((node.level, node.module))
        assert roots <= {
            "__future__",
            "argparse",
            "dataclasses",
            "http",
            "json",
            "os",
            "pathlib",
            "re",
            "sys",
            "typing",
            "urllib",
        }
        assert relative_imports == {(1, "schema")}
