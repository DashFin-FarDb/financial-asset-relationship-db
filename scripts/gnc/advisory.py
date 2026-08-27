"""Deterministic, read-only GNC Phase 2 pull-request advisory.

The pure evaluator consumes bounded JSON-compatible metadata.  The GitHub
adapter fetches only metadata from the base repository and never downloads,
checks out, imports, or executes pull-request-head content.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from .schema import GncSchemaError, canonical_hash, canonical_json_bytes, validate_contract

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

_GIT_OBJECT_ID = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
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
        state = "needs-human" if "needs-human" in kinds else "block" if "block" in kinds else "pass"
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
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise AdvisoryInputError(code)
    return value


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


def _contract_from_body(body: Any) -> tuple[dict[str, Any], str]:
    if not isinstance(body, str):
        raise AdvisoryInputError("contract.body-invalid")
    if len(body.encode("utf-8")) > MAX_PR_BODY_BYTES:
        raise AdvisoryInputError("contract.body-oversized")
    if body.count(CONTRACT_START) != 1 or body.count(CONTRACT_END) != 1:
        raise AdvisoryInputError("contract.markers-invalid")
    start = body.index(CONTRACT_START) + len(CONTRACT_START)
    end = body.index(CONTRACT_END)
    if end <= start:
        raise AdvisoryInputError("contract.markers-invalid")
    raw_contract = body[start:end].strip()
    if len(raw_contract.encode("utf-8")) > MAX_CONTRACT_BYTES:
        raise AdvisoryInputError("contract.oversized")
    try:
        parsed = json.loads(raw_contract)
        normalized = validate_contract(parsed)
    except (json.JSONDecodeError, GncSchemaError, TypeError, ValueError) as exc:
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
    return len(path_parts) >= len(scope_parts) and path_parts[: len(scope_parts)] == scope_parts


def _changed_path_inventory(records: Any) -> tuple[list[dict[str, str]], list[str]]:
    values = _sequence(records, "paths.invalid")
    if len(values) > MAX_CHANGED_PATHS:
        raise AdvisoryInputError("paths.too-many")
    inventory: list[dict[str, str]] = []
    scoped_paths: list[str] = []
    aggregate = 0
    seen: set[str] = set()
    allowed_statuses = frozenset(("added", "changed", "copied", "modified", "removed", "renamed"))
    for raw_record in values:
        record = _mapping(raw_record, "paths.record-invalid")
        status = _string(record.get("status"), "paths.status-invalid").casefold()
        if status not in allowed_statuses:
            raise AdvisoryInputError("paths.status-invalid")
        paths = [_canonical_repo_path(record.get("filename"))]
        if status == "renamed":
            paths.append(_canonical_repo_path(record.get("previous_filename")))
        for index, path in enumerate(paths):
            aggregate += len(path.encode("utf-8"))
            if aggregate > MAX_AGGREGATE_PATH_BYTES:
                raise AdvisoryInputError("paths.aggregate-oversized")
            if path in seen:
                raise AdvisoryInputError("paths.duplicate")
            seen.add(path)
            scoped_paths.append(path)
            inventory.append(
                {
                    "path": _sanitize_text(path, maximum=MAX_PATH_BYTES),
                    "role": "previous" if index else "current",
                    "status": status,
                }
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


def _approval_is_valid(comments: Any, expected: Mapping[str, Any]) -> bool:
    values = _sequence(comments, "approval.comments-invalid")
    if len(values) > MAX_APPROVAL_COMMENTS:
        raise AdvisoryInputError("approval.comments-oversized")
    matches = 0
    for raw_comment in values:
        comment = _mapping(raw_comment, "approval.comment-invalid")
        approval = _approval_payload(comment.get("body"))
        if approval is None:
            continue
        try:
            user = _mapping(comment.get("user"), "approval.user-invalid")
            login = _string(user.get("login"), "approval.user-invalid")
            actor = _string(approval.get("actor"), "approval.actor-invalid")
            valid = (
                actor in AUTHORIZED_APPROVERS
                and login == actor
                and comment.get("created_at") == comment.get("updated_at")
                and approval == expected
            )
        except AdvisoryInputError:
            valid = False
        if valid:
            matches += 1
    return matches == 1


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


def _evaluate_evidence(
    builder: AdvisoryBuilder, contract: Mapping[str, Any], raw_evidence: Any, refs: Mapping[str, str]
) -> None:
    values = _sequence(raw_evidence, "evidence.invalid")
    if len(values) > MAX_EVIDENCE_RECORDS:
        raise AdvisoryInputError("evidence.too-many")
    evidence: list[dict[str, str]] = []
    for raw in values:
        record = _mapping(raw, "evidence.record-invalid")
        requirement_id = _identifier(record.get("requirement_id"), "evidence.requirement-invalid")
        source = _string(record.get("source"), "evidence.source-invalid")
        state = _string(record.get("state"), "evidence.state-invalid")
        head_sha = _oid(record.get("head_sha"), "evidence.head-invalid")
        target = _string(record.get("target"), "evidence.target-invalid")
        normalized = {"requirement_id": requirement_id, "source": source, "state": state}
        evidence.append({**normalized, "head_sha": head_sha, "target": target})
        builder.evidence.append(normalized)
    valid_states = frozenset(("passed", "failed", "pending", "skipped", "canceled", "unavailable"))
    for requirement_id in contract["required_evidence"]:
        matching = [record for record in evidence if record["requirement_id"] == requirement_id]
        if not matching:
            builder.add("evidence.missing", "needs-human", requirement_id)
            continue
        if any(record["source"] not in ALLOWED_EVIDENCE_SOURCES for record in matching):
            builder.add("evidence.source-unapproved", "needs-human", requirement_id)
            continue
        current = [
            record
            for record in matching
            if record["head_sha"] == refs["head_sha"] and record["target"] == refs["target"]
        ]
        if not current:
            code = (
                "evidence.stale-sha"
                if all(record["head_sha"] != refs["head_sha"] for record in matching)
                else "evidence.wrong-target"
            )
            builder.add(code, "needs-human", requirement_id)
            continue
        if any(record["state"] not in valid_states for record in current):
            builder.add("evidence.state-invalid", "needs-human", requirement_id)
        elif any(record["state"] == "passed" for record in current):
            continue
        elif any(record["state"] == "failed" for record in current):
            builder.add("evidence.failed", "block", requirement_id)
        else:
            builder.add("evidence.unavailable", "needs-human", requirement_id)


def _evaluate_reviews(builder: AdvisoryBuilder, reviews: Any, threads: Any) -> None:
    review_values = _sequence(reviews, "reviews.invalid")
    thread_values = _sequence(threads, "reviews.threads-invalid")
    if len(review_values) + len(thread_values) > MAX_REVIEW_RECORDS:
        raise AdvisoryInputError("reviews.too-many")
    for raw in review_values:
        review = _mapping(raw, "reviews.record-invalid")
        if review.get("state") == "CHANGES_REQUESTED":
            builder.add("reviews.changes-requested", "block")
    for raw in thread_values:
        thread = _mapping(raw, "reviews.thread-invalid")
        if thread.get("is_resolved") is True or thread.get("is_outdated") is True:
            continue
        path = _sanitize_text(thread.get("path", "review-thread"), maximum=MAX_PATH_BYTES)
        if thread.get("review_state") == "CHANGES_REQUESTED":
            builder.add("reviews.unresolved-blocker", "block", path)
        else:
            builder.add("reviews.unresolved-advisory", "advisory", path)


def evaluate_advisory(snapshot: Any) -> dict[str, Any]:
    """Evaluate one bounded metadata snapshot without raising on untrusted input."""
    repository = "unknown/unknown"
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


class GitHubMetadataClient:
    """Minimal read-only GitHub JSON client with proven pagination."""

    def __init__(self, *, token: str, api_url: str, graphql_url: str) -> None:
        """Initialize a client with the automatic read-only workflow token."""
        self._token = token
        self._api_url = api_url.rstrip("/")
        self._graphql_url = graphql_url

    def _request(self, url: str, *, payload: Mapping[str, Any] | None = None) -> tuple[Any, Mapping[str, str]]:
        body = canonical_json_bytes(payload) if payload is not None else None
        request = urllib.request.Request(
            url,
            data=body,
            method="POST" if payload is not None else "GET",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "User-Agent": "fardb-gnc-advisory",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read(MAX_ARTIFACT_BYTES + 1)
                if len(raw) > MAX_ARTIFACT_BYTES:
                    raise AdvisoryInputError("api.response-oversized")
                return json.loads(raw), response.headers
        except urllib.error.HTTPError as exc:
            code = "api.rate-limited" if exc.code in (403, 429) else "api.request-failed"
            raise AdvisoryInputError(code) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AdvisoryInputError("api.unavailable") from exc

    def get(self, path: str) -> Any:
        """Fetch one REST JSON resource."""
        data, _ = self._request(f"{self._api_url}{path}")
        return data

    def pages(self, path: str, *, key: str | None, limit: int) -> list[Any]:
        """Fetch every REST page or fail closed when completeness is unprovable."""
        records: list[Any] = []
        separator = "&" if "?" in path else "?"
        page = 1
        while True:
            data, headers = self._request(f"{self._api_url}{path}{separator}per_page=100&page={page}")
            values = data.get(key) if key is not None and isinstance(data, Mapping) else data
            records.extend(_sequence(values, "api.shape-invalid"))
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
                  comments(first:1) { nodes { pullRequestReview { state } } }
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
            if not isinstance(data, Mapping) or data.get("errors"):
                raise AdvisoryInputError("api.graphql-failed")
            try:
                connection = data["data"]["repository"]["pullRequest"]["reviewThreads"]
                nodes = connection["nodes"]
                page_info = connection["pageInfo"]
            except (KeyError, TypeError) as exc:
                raise AdvisoryInputError("api.shape-invalid") from exc
            if not _is_sequence(nodes):
                raise AdvisoryInputError("api.shape-invalid")
            for node in nodes:
                review_state = None
                try:
                    review_state = node["comments"]["nodes"][0]["pullRequestReview"]["state"]
                except (KeyError, IndexError, TypeError):
                    pass
                result.append(
                    {
                        "is_outdated": node.get("isOutdated"),
                        "is_resolved": node.get("isResolved"),
                        "path": node.get("path", "review-thread"),
                        "review_state": review_state,
                    }
                )
            if len(result) > MAX_REVIEW_RECORDS:
                raise AdvisoryInputError("reviews.too-many")
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
        raise AdvisoryInputError("api.pr-shape-invalid") from exc
    if merge_base_sha is not None:
        result["merge_base_sha"] = merge_base_sha
    return result


def _normalize_evidence(
    *,
    checks: Sequence[Any],
    statuses: Sequence[Any],
    runs: Sequence[Any],
    reviews: Sequence[Any],
    head_sha: str,
    target: str,
) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for raw in checks:
        item = _mapping(raw, "api.check-invalid")
        records.append(
            {
                "head_sha": item.get("head_sha", head_sha),
                "requirement_id": _slug(item.get("name")),
                "source": "check_run",
                "state": _evidence_state(item.get("status"), item.get("conclusion")),
                "target": target,
            }
        )
    for raw in statuses:
        item = _mapping(raw, "api.status-invalid")
        records.append(
            {
                "head_sha": item.get("sha", head_sha),
                "requirement_id": _slug(item.get("context")),
                "source": "commit_status",
                "state": _evidence_state(item.get("state"), item.get("state")),
                "target": target,
            }
        )
    for raw in runs:
        item = _mapping(raw, "api.run-invalid")
        records.append(
            {
                "head_sha": item.get("head_sha", head_sha),
                "requirement_id": _slug(item.get("name")),
                "source": "actions_run",
                "state": _evidence_state(item.get("status"), item.get("conclusion")),
                "target": target,
            }
        )
    for raw in reviews:
        item = _mapping(raw, "api.review-invalid")
        user = item.get("user")
        login = user.get("login") if isinstance(user, Mapping) else None
        if login == "mohavro":
            records.append(
                {
                    "head_sha": item.get("commit_id") or head_sha,
                    "requirement_id": "named-human-review",
                    "source": "review",
                    "state": "passed" if item.get("state") == "APPROVED" else "failed",
                    "target": target,
                }
            )
    if len(records) > MAX_EVIDENCE_RECORDS:
        raise AdvisoryInputError("evidence.too-many")
    return records


def collect_github_snapshot(event: Mapping[str, Any], client: GitHubMetadataClient) -> dict[str, Any]:
    """Collect the bounded, read-only metadata snapshot for one PR event."""
    repository = _mapping(event.get("repository"), "event.repository-invalid")
    repository_name = _string(repository.get("full_name"), "event.repository-invalid")
    if "/" not in repository_name:
        raise AdvisoryInputError("event.repository-invalid")
    owner, name = repository_name.split("/", 1)
    event_raw_pr = _mapping(event.get("pull_request"), "event.pr-invalid")
    pr_number = _integer(event_raw_pr.get("number"), "event.pr-number-invalid")
    event_pr = _pr_metadata(event_raw_pr)

    current_raw = _mapping(client.get(f"/repos/{repository_name}/pulls/{pr_number}"), "api.pr-shape-invalid")
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

    comments: list[Any] = []
    policy_present = False
    try:
        contract, _ = _contract_from_body(current["body"])
    except AdvisoryInputError:
        contract = None
    if contract is not None:
        comments = client.pages(
            f"/repos/{repository_name}/issues/{contract['parent_issue']}/comments?",
            key=None,
            limit=MAX_APPROVAL_COMMENTS,
        )
        client.get(
            f"/repos/{repository_name}/contents/scripts/gnc/schema.py?ref="
            f"{urllib.parse.quote(contract['policy_sha'], safe='')}"
        )
        policy_present = True
    current["policy_file_present"] = policy_present

    reviews = client.pages(f"/repos/{repository_name}/pulls/{pr_number}/reviews?", key=None, limit=MAX_REVIEW_RECORDS)
    threads = client.review_threads(owner, name, pr_number)
    if len(reviews) + len(threads) > MAX_REVIEW_RECORDS:
        raise AdvisoryInputError("reviews.too-many")
    checks = client.pages(
        f"/repos/{repository_name}/commits/{current['head_sha']}/check-runs?",
        key="check_runs",
        limit=MAX_EVIDENCE_RECORDS,
    )
    statuses = client.pages(
        f"/repos/{repository_name}/commits/{current['head_sha']}/statuses?",
        key=None,
        limit=MAX_EVIDENCE_RECORDS,
    )
    runs = client.pages(
        f"/repos/{repository_name}/actions/runs?event=pull_request&head_sha={current['head_sha']}&",
        key="workflow_runs",
        limit=MAX_EVIDENCE_RECORDS,
    )
    evidence = _normalize_evidence(
        checks=checks,
        statuses=statuses,
        runs=runs,
        reviews=reviews,
        head_sha=current["head_sha"],
        target=current["target"],
    )

    final_raw = _mapping(client.get(f"/repos/{repository_name}/pulls/{pr_number}"), "api.pr-shape-invalid")
    final_pr = _pr_metadata(final_raw)
    return {
        "api_errors": [],
        "approval_comments": comments,
        "changed_files": [
            {
                "filename": item.get("filename"),
                "previous_filename": item.get("previous_filename"),
                "status": item.get("status"),
            }
            for item in changed
            if isinstance(item, Mapping)
        ],
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


def write_outputs(report: Mapping[str, Any], *, artifact_path: Path, summary_path: Path) -> None:
    """Write exactly one bounded artifact and one bounded job summary."""
    artifact = canonical_json_bytes(report) + b"\n"
    if len(artifact) > MAX_ARTIFACT_BYTES:
        minimal = failure_report(
            repository=str(report.get("repository", "unknown/unknown")),
            pr_number=report.get("pr_number", 1) if isinstance(report.get("pr_number"), int) else 1,
            code="artifact.bound-exceeded",
        )
        artifact = canonical_json_bytes(minimal) + b"\n"
        report = minimal
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(artifact)
    summary = render_summary(report)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summary, encoding="utf-8", newline="\n")


def _read_event(path: Path) -> Mapping[str, Any]:
    raw = path.read_bytes()
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise AdvisoryInputError("event.oversized")
    parsed = json.loads(raw)
    return _mapping(parsed, "event.invalid")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the live read-only adapter or evaluate a supplied offline snapshot."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", "unknown/unknown"))
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    args = parser.parse_args(argv)
    repository = args.repository
    pr_number = 1
    try:
        if args.input is not None:
            report = evaluate_advisory(_read_event(args.input))
        else:
            if args.event is None:
                raise AdvisoryInputError("event.missing")
            event = _read_event(args.event)
            event_repository = event.get("repository")
            event_pr = event.get("pull_request")
            if isinstance(event_repository, Mapping) and isinstance(event_repository.get("full_name"), str):
                repository = event_repository["full_name"]
            if (
                isinstance(event_pr, Mapping)
                and isinstance(event_pr.get("number"), int)
                and not isinstance(event_pr.get("number"), bool)
                and event_pr["number"] > 0
            ):
                pr_number = event_pr["number"]
            token = os.environ.get(args.token_env)
            if not token:
                raise AdvisoryInputError("api.token-unavailable")
            client = GitHubMetadataClient(
                token=token,
                api_url=os.environ.get("GITHUB_API_URL", "https://api.github.com"),
                graphql_url=os.environ.get("GITHUB_GRAPHQL_URL", "https://api.github.com/graphql"),
            )
            report = evaluate_advisory(collect_github_snapshot(event, client))
    except AdvisoryInputError as exc:
        report = failure_report(repository=repository, pr_number=pr_number, code=exc.code)
    except (OSError, json.JSONDecodeError):
        report = failure_report(repository=repository, pr_number=pr_number, code="runtime.unavailable")
    write_outputs(report, artifact_path=args.output, summary_path=args.summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
