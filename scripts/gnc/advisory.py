"""Deterministic, read-only GNC Phase 2 pull-request advisory.

The pure evaluator consumes bounded JSON-compatible metadata.  The GitHub
adapter fetches only metadata from the base repository and never downloads,
checks out, imports, or executes pull-request-head content.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import sys
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from .schema import canonical_hash, canonical_json_bytes, validate_contract

ADVISORY_VERSION = "gnc-phase2.v1"
CONTRACT_START = "<!-- gnc-contract:start -->"
CONTRACT_END = "<!-- gnc-contract:end -->"
APPROVAL_MARKER = "<!-- gnc-approval:v1 -->"
AUTHORIZED_APPROVERS = frozenset(("mohavro",))
ALLOWED_EVIDENCE_SOURCES = frozenset(("actions_run", "check_run", "commit_status", "review"))

MAX_PR_BODY_BYTES = 128 * 1024
MAX_CONTRACT_BYTES = 64 * 1024
MAX_CHANGED_PATHS = 500
MAX_PATH_BYTES = 512
MAX_AGGREGATE_PATH_BYTES = 256 * 1024
MAX_REVIEW_RECORDS = 1_000
MAX_EVIDENCE_RECORDS = 1_000
MAX_APPROVAL_COMMENTS = 1_000
MAX_SUMMARY_BYTES = 64 * 1024
MAX_ARTIFACT_BYTES = 1024 * 1024

_API_PATH_INVALID = "api.path-invalid"
_API_PR_SHAPE_INVALID = "api.pr-shape-invalid"
_API_SHAPE_INVALID = "api.shape-invalid"
_API_THREAD_COMMENTS_INVALID = "api.thread-comments-invalid"
_API_URL_INVALID = "api.url-invalid"
_EVENT_REPOSITORY_INVALID = "event.repository-invalid"
_REVIEWS_TOO_MANY = "reviews.too-many"
_UNKNOWN_REPOSITORY = "unknown/unknown"
_GIT_OBJECT_ID = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}/[A-Za-z0-9_.-]{1,100}$")
_SECRET_TEXT = re.compile(
    r"-----BEGIN [A-Z ]+PRIVATE KEY-----|(?<![A-Z0-9])(?:github_pat_|gh[opusr]_|sk_live_|xox[a-z0-9]*-)[A-Z0-9_-]+",
    re.IGNORECASE,
)
_CONTROL_TEXT = re.compile(r"[\x00-\x1f\x7f]")
_FORBIDDEN_OUTPUT_KEYS = frozenset(
    (
        "credential",
        "credentials",
        "diff",
        "evidence_body",
        "patch",
        "password",
        "private_key",
        "raw_evidence",
        "review_transcript",
        "script",
        "secret",
        "token",
    )
)


class AdvisoryInputError(ValueError):
    """A bounded, sanitized advisory-input failure."""

    def __init__(self, code: str) -> None:
        """Initialize the exception with one stable public error code."""
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Finding:
    """One deterministic advisory observation."""

    code: str
    kind: str
    subject: str = "repository"

    def normalized(self) -> dict[str, str]:
        """Return a stable, sanitized JSON representation."""
        return {
            "code": _identifier(self.code, "finding.code"),
            "kind": self.kind,
            "subject": _sanitize_text(self.subject, maximum=512),
        }


@dataclass
class AdvisoryBuilder:
    """Collect findings and produce a deterministic report."""

    repository: str
    pr_number: int
    findings: list[Finding] = field(default_factory=list)
    bindings: dict[str, Any] = field(default_factory=dict)
    changed_paths: list[dict[str, str]] = field(default_factory=list)
    evidence: list[dict[str, str]] = field(default_factory=list)

    def add(self, code: str, kind: str, subject: str = "repository") -> None:
        """Add one finding without exposing raw untrusted content."""
        self.findings.append(Finding(code=code, kind=kind, subject=subject))

    def build(self) -> dict[str, Any]:
        """Build a stable report whose state follows fail-safe precedence."""
        normalized_findings = sorted(
            {tuple(item.normalized().values()): item.normalized() for item in self.findings}.values(),
            key=lambda item: (item["kind"], item["code"], item["subject"]),
        )
        normalized_evidence = [_sanitize_json(item) for item in self.evidence]
        kinds = {item["kind"] for item in normalized_findings}
        state = "pass"
        if "needs-human" in kinds:
            state = "needs-human"
        elif "block" in kinds:
            state = "block"
        return {
            "advisory_version": ADVISORY_VERSION,
            "bindings": _sanitize_json(self.bindings),
            "changed_paths": sorted(self.changed_paths, key=lambda item: (item["path"], item["status"])),
            "evidence": sorted(
                normalized_evidence,
                key=lambda item: (item["requirement_id"], item["source"], item["state"]),
            ),
            "findings": normalized_findings,
            "pr_number": self.pr_number,
            "repository": _sanitize_text(self.repository, maximum=256),
            "schema_version": 1,
            "state": state,
        }


@dataclass(frozen=True)
class GitHubEvidenceSnapshot:
    """Bounded GitHub evidence collections for one exact head and target."""

    checks: Sequence[Any]
    statuses: Sequence[Any]
    runs: Sequence[Any]
    reviews: Sequence[Any]
    target: str


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _mapping(value: Any, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AdvisoryInputError(code)
    return value


def _sequence(value: Any, code: str) -> Sequence[Any]:
    if not _is_sequence(value):
        raise AdvisoryInputError(code)
    return value


def _string(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value:
        raise AdvisoryInputError(code)
    return value


def _identifier(value: Any, code: str) -> str:
    text = _string(value, code)
    if _IDENTIFIER.fullmatch(text) is None:
        raise AdvisoryInputError(code)
    return text


def _oid(value: Any, code: str) -> str:
    text = _string(value, code)
    if _GIT_OBJECT_ID.fullmatch(text) is None:
        raise AdvisoryInputError(code)
    return text


def _integer(value: Any, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AdvisoryInputError(code)
    if value < 1:
        raise AdvisoryInputError(code)
    return value


def _repository(value: Any, code: str) -> str:
    name = _string(value, code)
    if _REPOSITORY.fullmatch(name) is None:
        raise AdvisoryInputError(code)
    return name


def _sanitize_text(value: Any, *, maximum: int) -> str:
    text = value if isinstance(value, str) else "invalid"
    text = _SECRET_TEXT.sub("[redacted-secret]", text)
    text = _CONTROL_TEXT.sub(" ", text).replace("::", ": :").replace("`", "'")
    encoded = text.encode("utf-8")
    if len(encoded) <= maximum:
        return text
    return encoded[:maximum].decode("utf-8", errors="ignore") + "..."


def _sanitize_json(value: Any, *, key: str = "record") -> Any:
    normalized_key = key.strip().casefold()
    if normalized_key in _FORBIDDEN_OUTPUT_KEYS:
        return "[redacted-field]"
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, str):
        return _sanitize_text(value, maximum=4_096)
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for raw_key, item in sorted(value.items(), key=lambda pair: str(pair[0])):
            output_key = _sanitize_text(raw_key, maximum=128) if isinstance(raw_key, str) else "invalid-key"
            result[output_key] = _sanitize_json(item, key=output_key)
        return result
    if _is_sequence(value):
        return [_sanitize_json(item, key=key) for item in value]
    return "[unsupported-value]"


def _extract_contract_text(body: Any) -> str:
    if not isinstance(body, str):
        raise AdvisoryInputError("contract.body-invalid")
    if len(body.encode("utf-8")) > MAX_PR_BODY_BYTES:
        raise AdvisoryInputError("contract.body-oversized")
    markers_are_unique = body.count(CONTRACT_START) == 1 and body.count(CONTRACT_END) == 1
    if not markers_are_unique:
        raise AdvisoryInputError("contract.markers-invalid")
    start = body.index(CONTRACT_START) + len(CONTRACT_START)
    end = body.index(CONTRACT_END)
    if end <= start:
        raise AdvisoryInputError("contract.markers-invalid")
    raw_contract = body[start:end].strip()
    if len(raw_contract.encode("utf-8")) > MAX_CONTRACT_BYTES:
        raise AdvisoryInputError("contract.oversized")
    return raw_contract


def _contract_from_body(body: Any) -> tuple[dict[str, Any], str]:
    raw_contract = _extract_contract_text(body)
    try:
        parsed = json.loads(raw_contract)
        normalized = validate_contract(parsed)
    except (TypeError, ValueError) as exc:
        raise AdvisoryInputError("contract.malformed") from exc
    return normalized, canonical_hash(normalized)


def _canonical_repo_path(value: Any) -> str:
    path = _string(value, "paths.invalid").replace("\\", "/")
    if len(path.encode("utf-8")) > MAX_PATH_BYTES:
        raise AdvisoryInputError("paths.item-oversized")
    if path.startswith("//") or re.match(r"^[A-Za-z]:", path) is not None:
        raise AdvisoryInputError("paths.unsafe")
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise AdvisoryInputError("paths.unsafe")
    return pure.as_posix()


def _path_in_scope(path: str, scope: str) -> bool:
    path_parts = PurePosixPath(path).parts
    scope_parts = PurePosixPath(scope).parts
    if len(path_parts) < len(scope_parts):
        return False
    return path_parts[: len(scope_parts)] == scope_parts


def _changed_record_paths(raw_record: Any) -> tuple[str, list[str]]:
    record = _mapping(raw_record, "paths.record-invalid")
    status = _string(record.get("status"), "paths.status-invalid").casefold()
    allowed_statuses = frozenset(("added", "changed", "copied", "modified", "removed", "renamed"))
    if status not in allowed_statuses:
        raise AdvisoryInputError("paths.status-invalid")
    paths = [_canonical_repo_path(record.get("filename"))]
    if status == "renamed":
        paths.append(_canonical_repo_path(record.get("previous_filename")))
    return status, paths


def _append_changed_path(
    inventory: list[dict[str, str]],
    scoped_paths: list[str],
    seen: set[str],
    *,
    aggregate: int,
    path: str,
    role: str,
    status: str,
) -> int:
    aggregate += len(path.encode("utf-8"))
    if aggregate > MAX_AGGREGATE_PATH_BYTES:
        raise AdvisoryInputError("paths.aggregate-oversized")
    if path in seen:
        raise AdvisoryInputError("paths.duplicate")
    seen.add(path)
    scoped_paths.append(path)
    inventory.append({"path": _sanitize_text(path, maximum=MAX_PATH_BYTES), "role": role, "status": status})
    return aggregate


def _changed_path_inventory(records: Any) -> tuple[list[dict[str, str]], list[str]]:
    values = _sequence(records, "paths.invalid")
    if len(values) > MAX_CHANGED_PATHS:
        raise AdvisoryInputError("paths.too-many")
    inventory: list[dict[str, str]] = []
    scoped_paths: list[str] = []
    aggregate = 0
    seen: set[str] = set()
    for raw_record in values:
        status, paths = _changed_record_paths(raw_record)
        for index, path in enumerate(paths):
            aggregate = _append_changed_path(
                inventory,
                scoped_paths,
                seen,
                aggregate=aggregate,
                path=path,
                role="previous" if index else "current",
                status=status,
            )
    return inventory, scoped_paths


def _approval_payload(body: Any) -> Mapping[str, Any] | None:
    if not isinstance(body, str) or not body.startswith(f"{APPROVAL_MARKER}\n"):
        return None
    raw = body[len(APPROVAL_MARKER) + 1 :]
    if len(raw.encode("utf-8")) > 4_096:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, Mapping):
        return None
    required = {"actor", "contract_hash", "contract_version", "head_sha", "policy_sha"}
    return parsed if set(parsed) == required else None


def _comment_matches_approval(raw_comment: Any, expected: Mapping[str, Any]) -> bool:
    try:
        comment = _mapping(raw_comment, "approval.comment-invalid")
        approval = _approval_payload(comment.get("body"))
        if approval is None:
            return False
        user = _mapping(comment.get("user"), "approval.user-invalid")
        login = _string(user.get("login"), "approval.user-invalid")
        actor = _string(approval.get("actor"), "approval.actor-invalid")
        created_at = _string(comment.get("created_at"), "approval.created-at-invalid")
        updated_at = _string(comment.get("updated_at"), "approval.updated-at-invalid")
        actor_is_authorized = actor in AUTHORIZED_APPROVERS and login == actor
        comment_is_unedited = created_at == updated_at
        return actor_is_authorized and comment_is_unedited and approval == expected
    except AdvisoryInputError:
        return False


def _approval_is_valid(comments: Any, expected: Mapping[str, Any]) -> bool:
    values = _sequence(comments, "approval.comments-invalid")
    if len(values) > MAX_APPROVAL_COMMENTS:
        raise AdvisoryInputError("approval.comments-oversized")
    return sum(_comment_matches_approval(comment, expected) for comment in values) == 1


def _evaluate_bindings(
    builder: AdvisoryBuilder,
    contract: Mapping[str, Any],
    contract_hash: str,
    event_pr: Mapping[str, Any],
    current_pr: Mapping[str, Any],
    final_pr: Mapping[str, Any],
) -> dict[str, str]:
    event = {
        "head_sha": _oid(event_pr.get("head_sha"), "refs.event-head-invalid"),
        "target_sha": _oid(event_pr.get("target_sha"), "refs.event-target-invalid"),
        "target": _string(event_pr.get("target"), "refs.event-target-name-invalid"),
    }
    current = {
        "head_sha": _oid(current_pr.get("head_sha"), "refs.current-head-invalid"),
        "target_sha": _oid(current_pr.get("target_sha"), "refs.current-target-invalid"),
        "merge_base_sha": _oid(current_pr.get("merge_base_sha"), "refs.merge-base-invalid"),
        "target": _string(current_pr.get("target"), "refs.current-target-name-invalid"),
    }
    final = {
        "head_sha": _oid(final_pr.get("head_sha"), "refs.final-head-invalid"),
        "target_sha": _oid(final_pr.get("target_sha"), "refs.final-target-invalid"),
        "target": _string(final_pr.get("target"), "refs.final-target-name-invalid"),
    }
    if event["target"] != "main" or current["target"] != "main" or final["target"] != "main":
        builder.add("refs.wrong-target", "needs-human")
    if event["head_sha"] != current["head_sha"]:
        builder.add("refs.superseded-head", "needs-human")
    if event["target_sha"] != current["target_sha"]:
        builder.add("refs.base-moved", "needs-human")
    if final != {"head_sha": current["head_sha"], "target_sha": current["target_sha"], "target": current["target"]}:
        builder.add("refs.stale-completion", "needs-human")
    if contract["base_sha"] != current["merge_base_sha"]:
        builder.add("refs.contract-base-mismatch", "needs-human")
    if contract["policy_sha"] != current["target_sha"]:
        builder.add("refs.policy-mismatch", "needs-human")
    if current_pr.get("policy_file_present") is not True:
        builder.add("refs.policy-unavailable", "needs-human")
    bindings = {
        "base_sha": current["merge_base_sha"],
        "contract_hash": contract_hash,
        "contract_id": contract["contract_id"],
        "contract_version": contract["version"],
        "head_sha": current["head_sha"],
        "policy_sha": contract["policy_sha"],
        "target": current["target"],
        "target_sha": current["target_sha"],
    }
    builder.bindings = bindings
    return current


def _evaluate_paths(builder: AdvisoryBuilder, contract: Mapping[str, Any], changed_files: Any) -> None:
    inventory, paths = _changed_path_inventory(changed_files)
    builder.changed_paths = inventory
    allowed = contract["allowed_paths"]
    forbidden = contract["forbidden_paths"]
    for path in paths:
        if not any(_path_in_scope(path, scope) for scope in allowed):
            builder.add("paths.outside-allowlist", "block", path)
        if any(_path_in_scope(path, scope) for scope in forbidden):
            builder.add("paths.forbidden", "block", path)
    for scope in allowed:
        if not any(_path_in_scope(path, scope) for path in paths):
            builder.add("paths.expected-missing", "block", scope)


def _normalize_evidence_record(raw: Any) -> tuple[dict[str, str], dict[str, str]]:
    record = _mapping(raw, "evidence.record-invalid")
    output = {
        "requirement_id": _identifier(record.get("requirement_id"), "evidence.requirement-invalid"),
        "source": _string(record.get("source"), "evidence.source-invalid"),
        "state": _string(record.get("state"), "evidence.state-invalid"),
    }
    bound = {
        **output,
        "head_sha": _oid(record.get("head_sha"), "evidence.head-invalid"),
        "target": _string(record.get("target"), "evidence.target-invalid"),
    }
    return bound, output


def _missing_current_evidence_code(matching: Sequence[Mapping[str, str]], refs: Mapping[str, str]) -> str:
    if all(record["head_sha"] != refs["head_sha"] for record in matching):
        return "evidence.stale-sha"
    return "evidence.wrong-target"


def _requirement_finding(
    requirement_id: str, matching: Sequence[Mapping[str, str]], refs: Mapping[str, str]
) -> Finding | None:
    if not matching:
        return Finding("evidence.missing", "needs-human", requirement_id)
    if any(record["source"] not in ALLOWED_EVIDENCE_SOURCES for record in matching):
        return Finding("evidence.source-unapproved", "needs-human", requirement_id)
    current = [
        record for record in matching if record["head_sha"] == refs["head_sha"] and record["target"] == refs["target"]
    ]
    if not current:
        return Finding(_missing_current_evidence_code(matching, refs), "needs-human", requirement_id)
    valid_states = frozenset(("passed", "failed", "pending", "skipped", "canceled", "unavailable"))
    if any(record["state"] not in valid_states for record in current):
        return Finding("evidence.state-invalid", "needs-human", requirement_id)
    if any(record["state"] == "failed" for record in current):
        return Finding("evidence.failed", "block", requirement_id)
    if any(record["state"] == "passed" for record in current):
        return None
    return Finding("evidence.unavailable", "needs-human", requirement_id)


def _evaluate_evidence(
    builder: AdvisoryBuilder, contract: Mapping[str, Any], raw_evidence: Any, refs: Mapping[str, str]
) -> None:
    values = _sequence(raw_evidence, "evidence.invalid")
    if len(values) > MAX_EVIDENCE_RECORDS:
        raise AdvisoryInputError("evidence.too-many")
    normalized = [_normalize_evidence_record(raw) for raw in values]
    evidence = [record for record, _ in normalized]
    builder.evidence.extend(output for _, output in normalized)
    by_requirement: dict[str, list[dict[str, str]]] = {}
    for record in evidence:
        by_requirement.setdefault(record["requirement_id"], []).append(record)
    for requirement_id in contract["required_evidence"]:
        finding = _requirement_finding(requirement_id, by_requirement.get(requirement_id, []), refs)
        if finding is not None:
            builder.findings.append(finding)


def _evaluate_review_thread(builder: AdvisoryBuilder, raw: Any) -> None:
    thread = _mapping(raw, "reviews.thread-invalid")
    if thread.get("is_resolved") is True or thread.get("is_outdated") is True:
        return
    path = _sanitize_text(thread.get("path", "review-thread"), maximum=MAX_PATH_BYTES)
    raw_states = thread.get("review_states", [thread.get("review_state")])
    review_states = _sequence(raw_states, "reviews.thread-states-invalid")
    if "CHANGES_REQUESTED" in review_states:
        builder.add("reviews.unresolved-blocker", "block", path)
        return
    builder.add("reviews.unresolved-advisory", "advisory", path)


def _evaluate_reviews(builder: AdvisoryBuilder, reviews: Any, threads: Any) -> None:
    review_values = _sequence(reviews, "reviews.invalid")
    thread_values = _sequence(threads, "reviews.threads-invalid")
    if len(review_values) + len(thread_values) > MAX_REVIEW_RECORDS:
        raise AdvisoryInputError(_REVIEWS_TOO_MANY)
    for raw in review_values:
        _mapping(raw, "reviews.record-invalid")
    for raw in thread_values:
        _evaluate_review_thread(builder, raw)


def evaluate_advisory(snapshot: Any) -> dict[str, Any]:
    """Evaluate one bounded metadata snapshot without raising on untrusted input."""
    repository = _UNKNOWN_REPOSITORY
    pr_number = 1
    try:
        data = _mapping(snapshot, "snapshot.invalid")
        repository = _string(data.get("repository"), "snapshot.repository-invalid")
        pr_number = _integer(data.get("pr_number"), "snapshot.pr-number-invalid")
        builder = AdvisoryBuilder(repository=repository, pr_number=pr_number)
        api_errors = _sequence(data.get("api_errors", []), "snapshot.api-errors-invalid")
        if api_errors or data.get("pagination_complete") is not True:
            builder.add("metadata.incomplete", "needs-human")
        current_pr = _mapping(data.get("current_pr"), "snapshot.current-pr-invalid")
        try:
            contract, contract_hash = _contract_from_body(current_pr.get("body"))
        except AdvisoryInputError as exc:
            builder.add(exc.code, "needs-human")
            return builder.build()
        event_pr = _mapping(data.get("event_pr"), "snapshot.event-pr-invalid")
        final_pr = _mapping(data.get("final_pr"), "snapshot.final-pr-invalid")
        refs = _evaluate_bindings(builder, contract, contract_hash, event_pr, current_pr, final_pr)
        expected_approval = {
            "actor": "mohavro",
            "contract_hash": contract_hash,
            "contract_version": contract["version"],
            "head_sha": refs["head_sha"],
            "policy_sha": contract["policy_sha"],
        }
        if not _approval_is_valid(data.get("approval_comments"), expected_approval):
            builder.add("approval.missing-or-invalid", "needs-human")
        _evaluate_paths(builder, contract, data.get("changed_files"))
        _evaluate_evidence(builder, contract, data.get("evidence"), refs)
        _evaluate_reviews(builder, data.get("reviews"), data.get("review_threads"))
        return builder.build()
    except AdvisoryInputError as exc:
        builder = AdvisoryBuilder(repository=repository, pr_number=pr_number)
        builder.add(exc.code, "needs-human")
        return builder.build()
    except (KeyError, TypeError, ValueError) as exc:
        builder = AdvisoryBuilder(repository=repository, pr_number=pr_number)
        builder.add("metadata.invalid", "needs-human", type(exc).__name__)
        return builder.build()


def _slug(value: Any) -> str:
    text = value if isinstance(value, str) else "unavailable"
    slug = re.sub(r"[^a-z0-9._:-]+", "-", text.casefold()).strip("-")[:128]
    return slug if _IDENTIFIER.fullmatch(slug) else "unavailable"


def _evidence_state(status: Any, conclusion: Any) -> str:
    if status not in ("completed", "success", "failure", "error"):
        return "pending"
    if conclusion in ("success", "neutral") or status == "success":
        return "passed"
    if conclusion in ("failure", "timed_out", "action_required", "startup_failure") or status in (
        "failure",
        "error",
    ):
        return "failed"
    if conclusion == "skipped":
        return "skipped"
    if conclusion in ("cancelled", "canceled"):
        return "canceled"
    return "unavailable"


def _trusted_https_url(value: Any, code: str, *, allow_query: bool) -> str:
    url = _string(value, code)
    parsed = urllib.parse.urlsplit(url)
    decoded_path = urllib.parse.unquote(parsed.path)
    safe_origin = (
        parsed.scheme == "https" and bool(parsed.hostname) and parsed.username is None and parsed.password is None
    )
    safe_path = "\\" not in decoded_path and ".." not in PurePosixPath(decoded_path).parts
    safe_suffix = not parsed.fragment and (allow_query or not parsed.query)
    if not safe_origin or not safe_path or not safe_suffix:
        raise AdvisoryInputError(code)
    return url


def _trusted_api_path(value: Any) -> str:
    path = _string(value, _API_PATH_INVALID)
    parsed = urllib.parse.urlsplit(path)
    decoded_path = urllib.parse.unquote(parsed.path)
    if parsed.scheme or parsed.netloc or not decoded_path.startswith("/"):
        raise AdvisoryInputError(_API_PATH_INVALID)
    if "\\" in decoded_path or ".." in PurePosixPath(decoded_path).parts or parsed.fragment:
        raise AdvisoryInputError(_API_PATH_INVALID)
    return path


def _review_threads_connection(data: Any) -> tuple[Sequence[Any], Mapping[str, Any]]:
    if not isinstance(data, Mapping) or data.get("errors"):
        raise AdvisoryInputError("api.graphql-failed")
    try:
        connection = data["data"]["repository"]["pullRequest"]["reviewThreads"]
        nodes = _sequence(connection["nodes"], _API_SHAPE_INVALID)
        page_info = _mapping(connection["pageInfo"], _API_SHAPE_INVALID)
    except (KeyError, TypeError) as exc:
        raise AdvisoryInputError(_API_SHAPE_INVALID) from exc
    return nodes, page_info


def _review_states(node: Mapping[str, Any]) -> list[str]:
    try:
        comments = _mapping(node["comments"], _API_THREAD_COMMENTS_INVALID)
        nodes = _sequence(comments["nodes"], _API_THREAD_COMMENTS_INVALID)
        total_count = comments["totalCount"]
    except (KeyError, TypeError) as exc:
        raise AdvisoryInputError(_API_THREAD_COMMENTS_INVALID) from exc
    if isinstance(total_count, bool) or not isinstance(total_count, int) or total_count != len(nodes):
        raise AdvisoryInputError("api.thread-comments-truncated")
    states: list[str] = []
    for value in nodes:
        comment = _mapping(value, "api.thread-comment-invalid")
        review = comment.get("pullRequestReview")
        if isinstance(review, Mapping) and isinstance(review.get("state"), str):
            states.append(review["state"])
    return sorted(set(states))


def _review_thread_record(value: Any) -> dict[str, Any]:
    node = _mapping(value, "api.thread-invalid")
    return {
        "is_outdated": node.get("isOutdated"),
        "is_resolved": node.get("isResolved"),
        "path": node.get("path", "review-thread"),
        "review_states": _review_states(node),
    }


class GitHubMetadataClient:
    """Minimal read-only GitHub JSON client with proven pagination."""

    def __init__(self, *, token: str, api_url: str, graphql_url: str) -> None:
        """Initialize a client with the automatic read-only workflow token."""
        self._token = token
        self._api_url = _trusted_https_url(api_url, _API_URL_INVALID, allow_query=False).rstrip("/")
        self._graphql_url = _trusted_https_url(graphql_url, "api.graphql-url-invalid", allow_query=False)

    def _request(self, url: str, *, payload: Mapping[str, Any] | None = None) -> tuple[Any, Mapping[str, str]]:
        url = _trusted_https_url(url, _API_URL_INVALID, allow_query=True)
        parsed = urllib.parse.urlsplit(url)
        hostname = parsed.hostname
        if hostname is None:
            raise AdvisoryInputError(_API_URL_INVALID)
        body = canonical_json_bytes(payload) if payload is not None else None
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "User-Agent": "fardb-gnc-advisory",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        target = urllib.parse.urlunsplit(("", "", parsed.path, parsed.query, ""))
        connection = http.client.HTTPSConnection(hostname, port=parsed.port, timeout=30)
        try:
            connection.request("POST" if payload is not None else "GET", target, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read(MAX_ARTIFACT_BYTES + 1)
            if response.status >= 400:
                code = "api.rate-limited" if response.status in (403, 429) else "api.request-failed"
                raise AdvisoryInputError(code)
            if response.status >= 300:
                raise AdvisoryInputError("api.redirect-rejected")
            if len(raw) > MAX_ARTIFACT_BYTES:
                raise AdvisoryInputError("api.response-oversized")
            return json.loads(raw), dict(response.getheaders())
        except (OSError, http.client.HTTPException, json.JSONDecodeError) as exc:
            raise AdvisoryInputError("api.unavailable") from exc
        finally:
            connection.close()

    def get(self, path: str) -> Any:
        """Fetch one REST JSON resource."""
        data, _ = self._request(f"{self._api_url}{_trusted_api_path(path)}")
        return data

    def pages(self, path: str, *, key: str | None, limit: int) -> list[Any]:
        """Fetch every REST page or fail closed when completeness is unprovable."""
        records: list[Any] = []
        path = _trusted_api_path(path)
        separator = "&" if "?" in path else "?"
        page = 1
        while True:
            data, headers = self._request(f"{self._api_url}{path}{separator}per_page=100&page={page}")
            values = data.get(key) if key is not None and isinstance(data, Mapping) else data
            records.extend(_sequence(values, _API_SHAPE_INVALID))
            link = headers.get("Link", "")
            has_next = 'rel="next"' in link
            if len(records) > limit or (len(records) == limit and has_next):
                raise AdvisoryInputError("api.record-bound-exceeded")
            if not has_next:
                return records
            page += 1

    def review_threads(self, owner: str, name: str, number: int) -> list[dict[str, Any]]:
        """Fetch bounded unresolved-thread metadata without comment bodies."""
        query = """
        query($owner:String!,$name:String!,$number:Int!,$cursor:String) {
            repository(owner:$owner,name:$name) {
                pullRequest(number:$number) {
                    reviewThreads(first:100,after:$cursor) {
                        pageInfo { hasNextPage endCursor }
                        nodes {
                            isResolved isOutdated path
                            comments(first:100) { totalCount nodes { pullRequestReview { state } } }
                        }
                    }
                }
            }
        }
        """
        cursor: str | None = None
        result: list[dict[str, Any]] = []
        while True:
            payload = {
                "query": query,
                "variables": {"cursor": cursor, "name": name, "number": number, "owner": owner},
            }
            data, _ = self._request(self._graphql_url, payload=payload)
            nodes, page_info = _review_threads_connection(data)
            result.extend(_review_thread_record(node) for node in nodes)
            if len(result) > MAX_REVIEW_RECORDS:
                raise AdvisoryInputError(_REVIEWS_TOO_MANY)
            if not page_info.get("hasNextPage"):
                return result
            cursor = page_info.get("endCursor")
            if not isinstance(cursor, str) or not cursor:
                raise AdvisoryInputError("api.pagination-incomplete")


def _pr_metadata(pr: Mapping[str, Any], *, merge_base_sha: str | None = None) -> dict[str, Any]:
    try:
        result = {
            "body": pr.get("body") or "",
            "head_sha": pr["head"]["sha"],
            "target": pr["base"]["ref"],
            "target_sha": pr["base"]["sha"],
        }
    except (KeyError, TypeError) as exc:
        raise AdvisoryInputError(_API_PR_SHAPE_INVALID) from exc
    if merge_base_sha is not None:
        result["merge_base_sha"] = merge_base_sha
    return result


def _normalize_check_evidence(sources: GitHubEvidenceSnapshot) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw in sources.checks:
        item = _mapping(raw, "api.check-invalid")
        records.append(
            {
                "head_sha": item.get("head_sha"),
                "requirement_id": _slug(item.get("name")),
                "source": "check_run",
                "state": _evidence_state(item.get("status"), item.get("conclusion")),
                "target": sources.target,
            }
        )
    return records


def _normalize_status_evidence(sources: GitHubEvidenceSnapshot) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw in sources.statuses:
        item = _mapping(raw, "api.status-invalid")
        records.append(
            {
                "head_sha": item.get("sha"),
                "requirement_id": _slug(item.get("context")),
                "source": "commit_status",
                "state": _evidence_state(item.get("state"), item.get("state")),
                "target": sources.target,
            }
        )
    return records


def _normalize_run_evidence(sources: GitHubEvidenceSnapshot) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw in sources.runs:
        item = _mapping(raw, "api.run-invalid")
        records.append(
            {
                "head_sha": item.get("head_sha"),
                "requirement_id": _slug(item.get("name")),
                "source": "actions_run",
                "state": _evidence_state(item.get("status"), item.get("conclusion")),
                "target": sources.target,
            }
        )
    return records


def _review_order(item: Mapping[str, Any]) -> tuple[str, int]:
    review_id = item.get("id")
    numeric_id = review_id if isinstance(review_id, int) and not isinstance(review_id, bool) else -1
    submitted_at = item.get("submitted_at")
    return submitted_at if isinstance(submitted_at, str) else "", numeric_id


def _latest_authorized_reviews(reviews: Sequence[Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    latest_reviews: dict[tuple[str, str], Mapping[str, Any]] = {}
    latest_review_order: dict[tuple[str, str], tuple[str, int]] = {}
    for raw in reviews:
        item = _mapping(raw, "api.review-invalid")
        user = item.get("user")
        login = user.get("login") if isinstance(user, Mapping) else None
        commit_id = item.get("commit_id")
        if login not in AUTHORIZED_APPROVERS or not isinstance(commit_id, str):
            continue
        order = _review_order(item)
        key = (login, commit_id)
        if key not in latest_review_order or order > latest_review_order[key]:
            latest_reviews[key] = item
            latest_review_order[key] = order
    return latest_reviews


def _review_evidence_record(item: Mapping[str, Any], target: str) -> dict[str, Any]:
    states = {"APPROVED": "passed", "CHANGES_REQUESTED": "failed"}
    raw_state = item.get("state")
    state = states.get(raw_state, "unavailable") if isinstance(raw_state, str) else "unavailable"
    return {
        "head_sha": item.get("commit_id"),
        "requirement_id": "named-human-review",
        "source": "review",
        "state": state,
        "target": target,
    }


def _normalize_review_evidence(sources: GitHubEvidenceSnapshot) -> list[dict[str, Any]]:
    latest_reviews = _latest_authorized_reviews(sources.reviews)
    return [_review_evidence_record(latest_reviews[key], sources.target) for key in sorted(latest_reviews)]


def _normalize_evidence(sources: GitHubEvidenceSnapshot) -> list[dict[str, Any]]:
    records = [
        *_normalize_check_evidence(sources),
        *_normalize_status_evidence(sources),
        *_normalize_run_evidence(sources),
        *_normalize_review_evidence(sources),
    ]
    if len(records) > MAX_EVIDENCE_RECORDS:
        raise AdvisoryInputError("evidence.too-many")
    return records


def _collect_pr_and_paths(
    client: GitHubMetadataClient, repository_name: str, pr_number: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    current_raw = _mapping(client.get(f"/repos/{repository_name}/pulls/{pr_number}"), _API_PR_SHAPE_INVALID)
    current = _pr_metadata(current_raw)
    comparison = _mapping(
        client.get(
            f"/repos/{repository_name}/compare/"
            f"{urllib.parse.quote(current['target_sha'], safe='')}...{urllib.parse.quote(current['head_sha'], safe='')}"
        ),
        "api.compare-invalid",
    )
    merge_base = _mapping(comparison.get("merge_base_commit"), "api.merge-base-unavailable").get("sha")
    current["merge_base_sha"] = _oid(merge_base, "api.merge-base-unavailable")
    changed = client.pages(f"/repos/{repository_name}/pulls/{pr_number}/files?", key=None, limit=MAX_CHANGED_PATHS)
    changed_files = [
        {
            "filename": item.get("filename"),
            "previous_filename": item.get("previous_filename"),
            "status": item.get("status"),
        }
        for item in changed
        if isinstance(item, Mapping)
    ]
    return current, changed_files


def _collect_contract_metadata(
    client: GitHubMetadataClient, repository_name: str, current: dict[str, Any]
) -> list[Any]:
    comments: list[Any] = []
    try:
        contract, _ = _contract_from_body(current["body"])
    except AdvisoryInputError:
        contract = None
    if contract is None:
        current["policy_file_present"] = False
        return comments
    comments = client.pages(
        f"/repos/{repository_name}/issues/{contract['parent_issue']}/comments?",
        key=None,
        limit=MAX_APPROVAL_COMMENTS,
    )
    try:
        client.get(
            f"/repos/{repository_name}/contents/scripts/gnc/schema.py?ref="
            f"{urllib.parse.quote(contract['policy_sha'], safe='')}"
        )
        current["policy_file_present"] = True
    except AdvisoryInputError:
        current["policy_file_present"] = False
    return comments


def _collect_reviews(
    client: GitHubMetadataClient, repository_name: str, owner: str, name: str, pr_number: int
) -> tuple[list[Any], list[dict[str, Any]]]:
    reviews = client.pages(f"/repos/{repository_name}/pulls/{pr_number}/reviews?", key=None, limit=MAX_REVIEW_RECORDS)
    threads = client.review_threads(owner, name, pr_number)
    if len(reviews) + len(threads) > MAX_REVIEW_RECORDS:
        raise AdvisoryInputError(_REVIEWS_TOO_MANY)
    return reviews, threads


def _collect_evidence(
    client: GitHubMetadataClient,
    repository_name: str,
    current: Mapping[str, Any],
    reviews: Sequence[Any],
) -> list[dict[str, Any]]:
    head_sha = current["head_sha"]
    checks = client.pages(
        f"/repos/{repository_name}/commits/{head_sha}/check-runs?",
        key="check_runs",
        limit=MAX_EVIDENCE_RECORDS,
    )
    statuses = client.pages(
        f"/repos/{repository_name}/commits/{head_sha}/statuses?",
        key=None,
        limit=MAX_EVIDENCE_RECORDS,
    )
    runs = client.pages(
        f"/repos/{repository_name}/actions/runs?event=pull_request&head_sha={head_sha}",
        key="workflow_runs",
        limit=MAX_EVIDENCE_RECORDS,
    )
    return _normalize_evidence(
        GitHubEvidenceSnapshot(
            checks=checks,
            statuses=statuses,
            runs=runs,
            reviews=reviews,
            target=current["target"],
        )
    )


def collect_github_snapshot(event: Mapping[str, Any], client: GitHubMetadataClient) -> dict[str, Any]:
    """Collect the bounded, read-only metadata snapshot for one PR event."""
    repository = _mapping(event.get("repository"), _EVENT_REPOSITORY_INVALID)
    repository_name = _repository(repository.get("full_name"), _EVENT_REPOSITORY_INVALID)
    owner, name = repository_name.split("/", 1)
    event_raw_pr = _mapping(event.get("pull_request"), "event.pr-invalid")
    pr_number = _integer(event_raw_pr.get("number"), "event.pr-number-invalid")
    event_pr = _pr_metadata(event_raw_pr)
    current, changed_files = _collect_pr_and_paths(client, repository_name, pr_number)
    comments = _collect_contract_metadata(client, repository_name, current)
    reviews, threads = _collect_reviews(client, repository_name, owner, name, pr_number)
    evidence = _collect_evidence(client, repository_name, current, reviews)
    final_raw = _mapping(client.get(f"/repos/{repository_name}/pulls/{pr_number}"), _API_PR_SHAPE_INVALID)
    final_pr = _pr_metadata(final_raw)
    return {
        "api_errors": [],
        "approval_comments": comments,
        "changed_files": changed_files,
        "current_pr": current,
        "event_pr": event_pr,
        "evidence": evidence,
        "final_pr": final_pr,
        "pagination_complete": True,
        "pr_number": pr_number,
        "repository": repository_name,
        "review_threads": threads,
        "reviews": [{"state": item.get("state")} for item in reviews if isinstance(item, Mapping)],
    }


def failure_report(*, repository: str, pr_number: int, code: str) -> dict[str, Any]:
    """Create a minimal fail-safe report for a trusted runtime/API failure."""
    builder = AdvisoryBuilder(repository=repository, pr_number=pr_number)
    builder.add(code, "needs-human")
    return builder.build()


def render_summary(report: Mapping[str, Any]) -> str:
    """Render a bounded deterministic GitHub job summary."""
    state = _sanitize_text(report.get("state"), maximum=32)
    raw_bindings = report.get("bindings")
    bindings: Mapping[str, Any] = raw_bindings if isinstance(raw_bindings, Mapping) else {}
    lines = [
        "# GNC Phase 2 advisory",
        "",
        f"**State:** `{state}`",
        "",
        f"- PR: `{report.get('repository')}#{report.get('pr_number')}`",
        f"- Head: `{bindings.get('head_sha', 'unavailable')}`",
        f"- Contract: `{bindings.get('contract_hash', 'unavailable')}`",
        "",
        "## Deterministic findings",
        "",
    ]
    raw_findings = report.get("findings")
    findings = _sequence(raw_findings, "summary.findings-invalid") if _is_sequence(raw_findings) else []
    if findings:
        for item in findings:
            if isinstance(item, Mapping):
                lines.append(
                    f"- `{_sanitize_text(item.get('kind'), maximum=32)}` "
                    f"`{_sanitize_text(item.get('code'), maximum=128)}` — "
                    f"{_sanitize_text(item.get('subject'), maximum=512)}"
                )
    else:
        lines.append("- No deterministic gaps were found in the bounded metadata snapshot.")
    lines.extend(
        (
            "",
            "This is a read-only, non-required advisory. It does not approve, waive, review, merge, or mutate the PR.",
            "",
        )
    )
    summary = "\n".join(lines)
    if len(summary.encode("utf-8")) > MAX_SUMMARY_BYTES:
        return "# GNC Phase 2 advisory\n\n**State:** `needs-human`\n\n- `summary.bound-exceeded`\n"
    return summary


def _bounded_runtime_path(path: Path, runtime_root: Path, code: str) -> Path:
    try:
        root = runtime_root.resolve(strict=True)
        resolved = path.resolve(strict=False)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise AdvisoryInputError(code) from exc
    if resolved == root or not resolved.parent.is_dir():
        raise AdvisoryInputError(code)
    return resolved


def write_outputs(report: Mapping[str, Any], *, artifact_path: Path, summary_path: Path, runtime_root: Path) -> None:
    """Write exactly one bounded artifact and one bounded job summary."""
    artifact_path = _bounded_runtime_path(artifact_path, runtime_root, "output.artifact-path-invalid")
    summary_path = _bounded_runtime_path(summary_path, runtime_root, "output.summary-path-invalid")
    if artifact_path == summary_path:
        raise AdvisoryInputError("output.paths-overlap")
    artifact = canonical_json_bytes(report) + b"\n"
    if len(artifact) > MAX_ARTIFACT_BYTES:
        minimal = failure_report(
            repository=str(report.get("repository", _UNKNOWN_REPOSITORY)),
            pr_number=report.get("pr_number", 1) if isinstance(report.get("pr_number"), int) else 1,
            code="artifact.bound-exceeded",
        )
        artifact = canonical_json_bytes(minimal) + b"\n"
        report = minimal
    artifact_path.write_bytes(artifact)
    summary = render_summary(report)
    summary_path.write_text(summary, encoding="utf-8", newline="\n")


def _read_event(path: Path, runtime_root: Path) -> Mapping[str, Any]:
    path = _bounded_runtime_path(path, runtime_root, "event.path-invalid")
    raw = path.read_bytes()
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise AdvisoryInputError("event.oversized")
    parsed = json.loads(raw)
    return _mapping(parsed, "event.invalid")


def _event_identity(event: Mapping[str, Any], fallback_repository: str) -> tuple[str, int]:
    repository = fallback_repository
    pr_number = 1
    event_repository = event.get("repository")
    event_pr = event.get("pull_request")
    if isinstance(event_repository, Mapping) and isinstance(event_repository.get("full_name"), str):
        repository = event_repository["full_name"]
    if isinstance(event_pr, Mapping):
        try:
            pr_number = _integer(event_pr.get("number"), "event.pr-number-invalid")
        except AdvisoryInputError:
            # Keep the bounded fallback identity so runtime failures still emit a safe report.
            pass
    return repository, pr_number


def _live_report(event: Mapping[str, Any], token_env: str, expected_repository: str) -> dict[str, Any]:
    event_repository = _mapping(event.get("repository"), _EVENT_REPOSITORY_INVALID)
    actual_repository = _repository(event_repository.get("full_name"), _EVENT_REPOSITORY_INVALID)
    if actual_repository != _repository(expected_repository, "event.expected-repository-invalid"):
        raise AdvisoryInputError("event.repository-mismatch")
    token = os.environ.get(token_env)
    if not token:
        raise AdvisoryInputError("api.token-unavailable")
    client = GitHubMetadataClient(
        token=token,
        api_url=os.environ.get("GITHUB_API_URL", "https://api.github.com"),
        graphql_url=os.environ.get("GITHUB_GRAPHQL_URL", "https://api.github.com/graphql"),
    )
    return evaluate_advisory(collect_github_snapshot(event, client))


def _evaluate_cli(args: argparse.Namespace) -> dict[str, Any]:
    repository = args.repository
    pr_number = 1
    try:
        if args.input is not None:
            return evaluate_advisory(_read_event(args.input, args.runtime_root))
        if args.event is None:
            raise AdvisoryInputError("event.missing")
        event = _read_event(args.event, args.runtime_root)
        repository, pr_number = _event_identity(event, repository)
        return _live_report(event, args.token_env, args.repository)
    except AdvisoryInputError as exc:
        return failure_report(repository=repository, pr_number=pr_number, code=exc.code)
    except (OSError, json.JSONDecodeError):
        return failure_report(repository=repository, pr_number=pr_number, code="runtime.unavailable")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the live read-only adapter or evaluate a supplied offline snapshot."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", _UNKNOWN_REPOSITORY))
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    args = parser.parse_args(argv)
    report = _evaluate_cli(args)
    write_outputs(
        report,
        artifact_path=args.output,
        summary_path=args.summary,
        runtime_root=args.runtime_root,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
