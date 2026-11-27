"""Immutable ResearchRun provenance contract (research_run.v1).

Provides canonical, deterministic SHA-256 digesting for research runs that
produce proposed relationship assertions. No floating-point values participate
in canonical hash inputs.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

RESEARCH_RUN_CONTRACT_VERSION = "research_run.v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:@/-]{0,127}$")
_UTC = timezone.utc


def _reject_floats(value: Any, path: str = "parameters") -> None:
    """Recursively reject floating-point values so canonical digests stay exact."""
    if isinstance(value, bool):
        return
    if isinstance(value, float):
        raise ValueError(f"{path} must not contain floating-point values; encode decimals as strings")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} keys must be strings")
            _reject_floats(item, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            _reject_floats(item, f"{path}[{idx}]")
    elif value is not None and not isinstance(value, (str, int)):
        raise ValueError(f"{path} contains unsupported type {type(value).__name__}")


def compute_research_run_digest(
    *,
    run_id: str,
    contract_version: str,
    domain_id: str,
    method_id: str,
    input_digest_sha256: str,
    parameters: dict[str, Any],
    actor_id: str,
    tenant_id: str,
    created_at_iso: str,
) -> str:
    """Compute a deterministic lowercase SHA-256 digest over canonical JSON fields."""
    _reject_floats(parameters)
    canonical_payload = {
        "actor_id": actor_id,
        "contract_version": contract_version,
        "created_at": created_at_iso,
        "domain_id": domain_id,
        "input_digest_sha256": input_digest_sha256,
        "method_id": method_id,
        "parameters": parameters,
        "run_id": run_id,
        "tenant_id": tenant_id,
    }
    encoded = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ResearchRunCreate(BaseModel):
    """Input payload for recording an immutable ResearchRun."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(default_factory=lambda: f"run-{uuid4().hex}")
    domain_id: str = Field(min_length=1, max_length=128)
    method_id: str = Field(min_length=1, max_length=128)
    input_digest_sha256: str = Field(min_length=64, max_length=64)
    parameters: dict[str, Any] = Field(default_factory=dict)
    actor_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(default="default", min_length=1, max_length=128)
    created_at: datetime = Field(default_factory=lambda: datetime.now(_UTC))

    @field_validator("run_id", "domain_id", "method_id", "actor_id", "tenant_id")
    @classmethod
    def validate_safe_identifier(cls, value: str) -> str:
        """Ensure identifiers are bounded, printable, and non-empty."""
        if not _SAFE_ID_RE.fullmatch(value):
            raise ValueError("identifier contains invalid characters or length")
        return value

    @field_validator("input_digest_sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        """Ensure input_digest_sha256 is 64 lowercase hex characters."""
        if not _SHA256_RE.fullmatch(value):
            raise ValueError("input_digest_sha256 must be 64 lowercase hex characters")
        return value

    @field_validator("parameters")
    @classmethod
    def validate_parameters_no_floats(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Reject floating-point values inside parameters."""
        _reject_floats(value)
        return value


class ResearchRunRecord(BaseModel):
    """Immutable persisted ResearchRun provenance record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    contract_version: str = RESEARCH_RUN_CONTRACT_VERSION
    domain_id: str
    method_id: str
    input_digest_sha256: str
    parameters: dict[str, Any]
    actor_id: str
    tenant_id: str
    created_at: str
    canonical_digest: str

    @classmethod
    def from_create(cls, payload: ResearchRunCreate) -> ResearchRunRecord:
        """Build an immutable ResearchRunRecord with canonical digest from a create payload."""
        ts = payload.created_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=_UTC)
        created_at_iso = ts.astimezone(_UTC).isoformat()
        digest = compute_research_run_digest(
            run_id=payload.run_id,
            contract_version=RESEARCH_RUN_CONTRACT_VERSION,
            domain_id=payload.domain_id,
            method_id=payload.method_id,
            input_digest_sha256=payload.input_digest_sha256,
            parameters=payload.parameters,
            actor_id=payload.actor_id,
            tenant_id=payload.tenant_id,
            created_at_iso=created_at_iso,
        )
        return cls(
            run_id=payload.run_id,
            contract_version=RESEARCH_RUN_CONTRACT_VERSION,
            domain_id=payload.domain_id,
            method_id=payload.method_id,
            input_digest_sha256=payload.input_digest_sha256,
            parameters=payload.parameters,
            actor_id=payload.actor_id,
            tenant_id=payload.tenant_id,
            created_at=created_at_iso,
            canonical_digest=digest,
        )
