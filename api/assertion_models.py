"""Pydantic request/response models for governed assertion APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self

from src.governance.relationship_assertion import (
    AuthorityRole,
    ConfidenceStatus,
    EvidencePolarity,
    LifecycleState,
    Visibility,
)


class AssertionProposalRequest(BaseModel):
    """Request body for authenticated assertion proposal creation."""

    model_config = ConfigDict(extra="forbid")

    assertion_id: str
    predicate_id: str
    subject_id: str
    object_id: str
    method_id: str
    proposition: str
    effective_from: datetime
    confidence_status: Literal["assessed", "not_assessed"] = "not_assessed"
    confidence_bp: int | None = None
    confidence_type: str | None = None
    confidence_method: str | None = None
    effective_to: datetime | None = None

    @model_validator(mode="after")
    def validate_effective_interval(self) -> Self:
        """Reject mixed-awareness and inverted effective intervals."""
        if self.effective_to is None:
            return self

        from_is_aware = self.effective_from.utcoffset() is not None
        to_is_aware = self.effective_to.utcoffset() is not None
        if from_is_aware != to_is_aware:
            raise ValueError("effective_from and effective_to must use matching timezone awareness")
        if self.effective_to < self.effective_from:
            raise ValueError("effective_to must not precede effective_from")
        return self


class AssertionDecisionRequest(BaseModel):
    """Request body for lifecycle decisions."""

    model_config = ConfigDict(extra="forbid")

    to_state: Literal["Accepted", "Rejected", "Withdrawn", "Disputed", "Retracted"]
    expected_sequence: int = Field(ge=1)
    rationale: str = Field(min_length=1, max_length=4096)


class AssertionSupersessionRequest(BaseModel):
    """Credential-free request body for atomic supersession."""

    model_config = ConfigDict(extra="forbid")

    expected_sequence: int = Field(ge=1)
    rationale: str = Field(min_length=1, max_length=4096)
    accept_rationale: str = Field(min_length=1, max_length=4096)
    successor_proposal: AssertionProposalRequest


class AssertionEventResponse(BaseModel):
    """Authenticated command lifecycle event view with audit fields."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    assertion_id: str
    sequence: int
    from_state: LifecycleState | None
    to_state: LifecycleState
    authority: AuthorityRole
    actor_id: str
    rationale: str
    policy_version: str
    recorded_at: datetime
    successor_assertion_id: str | None = None
    correlation_id: str | None = None


class AssertionEvidenceMetadataResponse(BaseModel):
    """Redacted evidence metadata exposed to public API consumers."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    polarity: EvidencePolarity
    visibility: Visibility
    redacted: bool
    source_ref: str | None = None
    media_type: str | None = None
    content_sha256: str | None = None
    observed_at: datetime | None = None
    issued_at: datetime | None = None
    licensing: str | None = None
    reuse_policy: str | None = None
    recorded_at: datetime | None = None


class AssertionReadResponse(BaseModel):
    """Public redacted assertion explanation payload."""

    model_config = ConfigDict(extra="forbid")

    assertion_id: str
    predicate_id: str
    subject_id: str
    object_id: str
    method_id: str
    proposition: str
    confidence_status: ConfidenceStatus
    confidence_bp: int | None
    confidence_type: str | None
    confidence_method: str | None
    effective_from: datetime
    effective_to: datetime | None
    recorded_at: datetime
    state: LifecycleState
    known_at: datetime | None
    effective_at: datetime | None
    sequence: int = Field(ge=1)
    evidence: list[AssertionEvidenceMetadataResponse]


class AssertionPublicEventResponse(BaseModel):
    """Identity-redacted lifecycle event safe for public history responses."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    assertion_id: str
    sequence: int
    from_state: LifecycleState | None
    to_state: LifecycleState
    authority: AuthorityRole
    recorded_at: datetime
    successor_assertion_id: str | None = None


class AssertionHistoryResponse(BaseModel):
    """Public immutable assertion history response."""

    model_config = ConfigDict(extra="forbid")

    assertion_id: str
    effective_from: datetime
    effective_to: datetime | None
    recorded_at: datetime
    state: LifecycleState
    known_at: datetime | None
    effective_at: datetime | None
    events: list[AssertionPublicEventResponse]


class GovernedScopeResponse(BaseModel):
    """Public governed scope identity pair."""

    model_config = ConfigDict(extra="forbid")

    purpose: str
    predicate_id: str


class PublishedProjectionContextResponse(BaseModel):
    """Publication and revision context for one governed read projection."""

    model_config = ConfigDict(extra="forbid")

    publication_id: str
    revision_id: str
    rebuild_job_id: str
    execution_id: str
    published_at: datetime
    purpose: str
    effective_at: datetime
    known_at: datetime
    contract_version: str
    projector_version: str
    edge_set_hash: str
    projection_hash: str
    governed_scopes: list[GovernedScopeResponse]


class PublishedProjectionEdgeResponse(BaseModel):
    """Canonical published projection edge identity and provenance."""

    model_config = ConfigDict(extra="forbid")

    projection_edge_id: str
    source: str
    target: str
    relationship_type: str
    strength: str
    direction: str
    assertion_id: str


class PublishedAssertionBundleResponse(BaseModel):
    """Publication-bound assertion explanation and history."""

    model_config = ConfigDict(extra="forbid")

    explanation: AssertionReadResponse
    history: AssertionHistoryResponse


class PublishedEdgeExplanationResponse(BaseModel):
    """Publication-owned edge explanation response contract."""

    model_config = ConfigDict(extra="forbid")

    publication: PublishedProjectionContextResponse
    edge: PublishedProjectionEdgeResponse
    assertion: PublishedAssertionBundleResponse


class AssertionCommandResponse(BaseModel):
    """Response for proposal, decision, and supersession commands."""

    model_config = ConfigDict(extra="forbid")

    assertion_id: str
    event: AssertionEventResponse
    state: LifecycleState
    idempotent_reuse: bool = False
