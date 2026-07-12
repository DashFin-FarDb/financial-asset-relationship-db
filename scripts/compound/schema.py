"""Observation ledger schema and path allowlist/denylist for compounding.

Directional contract from the architecture-expert plan: emitters append
observations; synthesize alone rewrites domain docs and agent packs.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = 1

KNOWLEDGE_BRANCH = "knowledge/architecture-expert"

COMPOUND_ROOT = Path("docs/compound")
LEDGER_PATH = COMPOUND_ROOT / "ledger" / "observations.jsonl"
INDEX_PATH = COMPOUND_ROOT / "INDEX.md"
WATCHED_SERIES_PATH = COMPOUND_ROOT / "watched-series.yml"
RUNTIME_PATH = COMPOUND_ROOT / "runtime.yml"
DOMAINS_DIR = COMPOUND_ROOT / "domains"
BRIEFS_DIR = COMPOUND_ROOT / "briefs"

DOMAINS: tuple[str, ...] = (
    "architecture",
    "api",
    "persistence",
    "ci-guardrails",
    "rebuild-reconciliation",
    "deployment",
)

WRITE_ALLOWLIST_PREFIXES: tuple[str, ...] = (
    "docs/compound/",
    ".cursor/rules/architecture-expert.mdc",
    ".cursor/rules/architecture-expert-query.mdc",
    ".openhands/microagents/architecture_expert.md",
)

# Closed write denylist — human-owned policy/ADR surfaces compound must never rewrite.
# Keep entries aligned with real repo paths (validated by test_denylist_paths_exist).
# Reasons:
# - docs/adr/: architecture decision records (human-owned canon)
# - AGENTS.md: Dosu-maintained agent instructions
# - .github/AUTOMATION_SCOPE_POLICY.md: automation scope policy
# - .github/AI_AGENT_GUARDRAILS.md: agent guardrail policy
# - .github/copilot-instructions.md: Copilot instruction policy
# - docs/PR_SCOPE_GUARDRAILS.md: PR scope policy
# - docs/GOVERNANCE.md: governance policy
# - docs/DEPENDENCY_POLICY.md: dependency policy
# - docs/lessons/: durable lessons (human-curated)
WRITE_DENYLIST_PREFIXES: tuple[str, ...] = (
    "docs/adr/",
    "AGENTS.md",
    ".github/AUTOMATION_SCOPE_POLICY.md",
    ".github/AI_AGENT_GUARDRAILS.md",
    ".github/copilot-instructions.md",
    "docs/PR_SCOPE_GUARDRAILS.md",
    "docs/GOVERNANCE.md",
    "docs/DEPENDENCY_POLICY.md",
    "docs/lessons/",
)


class ObservationStatus(str, Enum):
    """Landed vs provisional observation status."""

    PROVISIONAL = "provisional"
    LANDED = "landed"


class ObservationSource(str, Enum):
    """Emitter that produced the observation."""

    GITHUB = "github"
    CURSOR = "cursor"
    MANUAL = "manual"
    BOOTSTRAP = "bootstrap"


class WriterMode(str, Enum):
    """Dual-writer vs GitHub-only continuous writer mode."""

    DUAL = "dual"
    GITHUB_ONLY = "github_only"


REQUIRED_WATCHED_SERIES_KEYS: frozenset[str] = frozenset({"version", "prs", "labels", "path_globs"})

# Path-prefix → domain mapping for live PR / bootstrap classification.
_PATH_DOMAIN_RULES: tuple[tuple[str, str], ...] = (
    ("api/", "api"),
    ("frontend/", "api"),
    ("src/data/", "persistence"),
    ("src/logic/rebuild", "rebuild-reconciliation"),
    ("src/logic/reconciliation", "rebuild-reconciliation"),
    ("src/logic/recovery", "rebuild-reconciliation"),
    ("docs/graph-persistence", "persistence"),
    ("docs/reconciliation", "rebuild-reconciliation"),
    (".github/", "ci-guardrails"),
    ("docs/PR_SCOPE", "ci-guardrails"),
    ("docs/staging", "deployment"),
    ("docs/release", "deployment"),
    ("docs/enterprise-deployment", "deployment"),
    ("scripts/check_hosted_readiness", "deployment"),
    ("docs/adr/", "architecture"),
    ("docs/compound/", "architecture"),
    ("src/", "architecture"),
)


@dataclass(frozen=True)
class Observation:
    """One append-only ledger observation."""

    observation_id: str
    source: ObservationSource
    event_type: str
    status: ObservationStatus
    primary_ref: str
    summary: str
    domains: tuple[str, ...] = ()
    refs: tuple[str, ...] = ()
    evidence_pointers: tuple[str, ...] = ()
    created_at: str = ""
    schema_version: int = SCHEMA_VERSION

    def dedupe_key(self) -> tuple[str, str, str]:
        """Return the idempotency key for this observation."""
        return (self.source.value, self.event_type, self.primary_ref)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSONL storage."""
        payload = asdict(self)
        payload["source"] = self.source.value
        payload["status"] = self.status.value
        payload["domains"] = list(self.domains)
        payload["refs"] = list(self.refs)
        payload["evidence_pointers"] = list(self.evidence_pointers)
        return payload

    def to_json_line(self) -> str:
        """Serialize as a single JSONL line."""
        return json.dumps(self.to_dict(), sort_keys=True)


@dataclass
class WatchedSeries:
    """Watched PR series configuration."""

    version: int
    prs: list[int] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    path_globs: list[str] = field(default_factory=list)


class SchemaError(ValueError):
    """Raised when observation or config validation fails."""


class PathPolicyError(PermissionError):
    """Raised when a write target violates allowlist/denylist policy."""


def _as_str_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    """Normalize a string or sequence of strings into a homogeneous tuple."""
    items: list[str]
    if value is None:
        items = []
    elif isinstance(value, str):
        items = [value]
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        items = []
        for item in value:
            if not isinstance(item, str):
                raise SchemaError(f"{field_name} entries must be strings")
            items.append(item)
    else:
        raise SchemaError(f"{field_name} must be a string or list of strings")
    return tuple(items)


def validate_domains(domains: Iterable[str]) -> tuple[str, ...]:
    """Validate domain names against the fixed partition set."""
    normalized: list[str] = []
    for domain in domains:
        if domain not in DOMAINS:
            raise SchemaError(f"Unknown domain '{domain}'; allowed: {', '.join(DOMAINS)}")
        if domain not in normalized:
            normalized.append(domain)
    return tuple(normalized)


def observation_from_mapping(data: Mapping[str, Any]) -> Observation:
    """Parse and validate an observation mapping."""
    required = (
        "observation_id",
        "source",
        "event_type",
        "status",
        "primary_ref",
        "summary",
    )
    missing = [key for key in required if key not in data or data[key] in (None, "")]
    if missing:
        raise SchemaError(f"Missing required observation fields: {', '.join(missing)}")

    try:
        source = ObservationSource(str(data["source"]))
        status = ObservationStatus(str(data["status"]))
    except ValueError as exc:
        raise SchemaError(str(exc)) from exc

    domains = validate_domains(_as_str_tuple(data.get("domains"), "domains"))
    raw_schema_version = data.get("schema_version", SCHEMA_VERSION)
    if isinstance(raw_schema_version, bool):
        raise SchemaError("schema_version must be an integer")
    schema_version = int(raw_schema_version)
    if schema_version != SCHEMA_VERSION:
        raise SchemaError(f"Unsupported schema_version {schema_version}; expected {SCHEMA_VERSION}")

    created_at = str(data.get("created_at") or "")
    if created_at:
        from datetime import datetime

        try:
            datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise SchemaError(f"created_at must be ISO-8601 (e.g. 2026-07-09T00:00:00Z): {created_at!r}") from exc

    return Observation(
        observation_id=str(data["observation_id"]),
        source=source,
        event_type=str(data["event_type"]),
        status=status,
        primary_ref=str(data["primary_ref"]),
        summary=str(data["summary"]),
        domains=domains,
        refs=_as_str_tuple(data.get("refs"), "refs"),
        evidence_pointers=_as_str_tuple(data.get("evidence_pointers"), "evidence_pointers"),
        created_at=created_at,
        schema_version=schema_version,
    )


def parse_observation_line(line: str) -> Observation:
    """Parse one JSONL ledger line into an Observation."""
    text = line.strip()
    if not text or text.startswith("#"):
        raise SchemaError("Empty or comment ledger line is not an observation")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SchemaError(f"Invalid JSONL observation: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise SchemaError("Observation JSON must be an object")
    return observation_from_mapping(payload)


def _require_typed_list(raw: Any, *, field: str, item_type: type, type_label: str) -> list:
    """Validate a watched-series list field and return typed items."""
    if not isinstance(raw, list):
        raise SchemaError(f"watched-series {field} must be a list")
    items: list = []
    for item in raw:
        if isinstance(item, bool) or not isinstance(item, item_type):
            raise SchemaError(f"watched-series {field} must be {type_label}")
        items.append(item)
    return items


def watched_series_from_mapping(data: Mapping[str, Any]) -> WatchedSeries:
    """Validate watched-series YAML/JSON mapping."""
    missing = sorted(REQUIRED_WATCHED_SERIES_KEYS - set(data.keys()))
    if missing:
        raise SchemaError(f"watched-series missing required keys: {', '.join(missing)}")

    version = data["version"]
    if not isinstance(version, int) or isinstance(version, bool):
        raise SchemaError("watched-series version must be an integer")

    return WatchedSeries(
        version=version,
        prs=_require_typed_list(data["prs"], field="prs", item_type=int, type_label="integers"),
        labels=_require_typed_list(data["labels"], field="labels", item_type=str, type_label="strings"),
        path_globs=_require_typed_list(data["path_globs"], field="path_globs", item_type=str, type_label="strings"),
    )


def normalize_repo_relative(path: str | Path) -> str:
    """Normalize a path to forward-slash repo-relative form.

    Rejects ``..`` segments so allowlist/denylist checks cannot be bypassed via
    traversal (for example ``docs/compound/../../AGENTS.md``).
    """
    text = str(path).replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    text = text.lstrip("/")
    parts: list[str] = []
    for part in text.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            raise PathPolicyError(f"Path traversal rejected: {path}")
        parts.append(part)
    return "/".join(parts)


def detect_domains_from_paths(paths: Iterable[str]) -> tuple[str, ...]:
    """Map changed file paths to compound domains.

    Returns at least ``("architecture",)`` when no path matches a rule.
    """
    found: list[str] = []
    found_set: set[str] = set()
    for raw in paths:
        try:
            normalized = normalize_repo_relative(raw)
        except PathPolicyError:
            continue
        for prefix, domain in _PATH_DOMAIN_RULES:
            if normalized.startswith(prefix) or f"/{prefix}" in f"/{normalized}":
                if domain not in found_set:
                    found.append(domain)
                    found_set.add(domain)
                break
    return tuple(found) if found else ("architecture",)


def is_denylisted(path: str | Path) -> bool:
    """Return True if path matches the closed write denylist."""
    try:
        normalized = normalize_repo_relative(path)
    except PathPolicyError:
        return True
    for prefix in WRITE_DENYLIST_PREFIXES:
        if prefix.endswith("/"):
            if normalized.startswith(prefix) or normalized == prefix.rstrip("/"):
                return True
        elif normalized == prefix:
            return True
    return False


def is_allowlisted(path: str | Path) -> bool:
    """Return True if path is under the write allowlist."""
    try:
        normalized = normalize_repo_relative(path)
    except PathPolicyError:
        return False
    for prefix in WRITE_ALLOWLIST_PREFIXES:
        if prefix.endswith("/"):
            if normalized.startswith(prefix):
                return True
        elif normalized == prefix:
            return True
    return False


def assert_writable(path: str | Path) -> str:
    """Raise PathPolicyError unless path is allowlisted and not denylisted."""
    normalized = normalize_repo_relative(path)
    if is_denylisted(normalized):
        raise PathPolicyError(f"Write denied (denylist): {normalized}")
    if not is_allowlisted(normalized):
        raise PathPolicyError(f"Write denied (not allowlisted): {normalized}")
    return normalized
