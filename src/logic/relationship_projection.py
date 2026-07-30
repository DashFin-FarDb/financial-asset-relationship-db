"""Deterministic GRAC v1 assertion projector (pure; no DB, clock, or env reads).

Projection is a pure function of explicit inputs. ``edge_set_hash`` is semantic
(sorted directed edges without provenance). ``projection_hash`` is provenance-
sensitive (includes assertion IDs, linked evidence digests, and revision
parameters). Floating-point values never participate in hash inputs.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from src.governance.relationship_assertion import (
    Assertion,
    AssertionEvent,
    EvidenceLink,
    EvidenceRecord,
    LifecycleState,
    ValidationError,
)
from src.governance.relationship_assertion_contract import (
    CONTRACT_VERSION,
    PredicatesDocument,
    PredicateSpec,
    canonical_json_bytes,
    sha256_hex,
)
from src.governance.relationship_assertion_lifecycle import resolve_state

UTC = timezone.utc
_UTC_OFFSET = timedelta(0)
PROJECTOR_VERSION = "projector.v1"
_ACCEPTED: LifecycleState = "Accepted"
_CONFLICT_ATTRS = frozenset({"predicate_id", "subject_id", "object_id", "method_id"})


class ProjectionError(Exception):
    """Raised when projection fails closed (conflicts or invalid inputs)."""


@dataclass(frozen=True, slots=True)
class ProjectionEdge:
    """Materialized governed edge candidate for a projection revision."""

    source_id: str
    target_id: str
    edge_type: str
    strength: str
    direction: str
    assertion_id: str


@dataclass(frozen=True, slots=True)
class GovernedScope:
    """Predicate scope governed for a projection purpose."""

    purpose: str
    predicate_id: str


@dataclass(frozen=True, slots=True)
class ProjectionRevision:
    """Immutable candidate graph snapshot with content hashes."""

    purpose: str
    effective_at: datetime
    known_at: datetime
    contract_version: str
    projector_version: str
    edge_set_hash: str
    projection_hash: str
    edges: tuple[ProjectionEdge, ...]
    governed_scopes: tuple[GovernedScope, ...]


@dataclass(frozen=True, slots=True)
class ProjectRequest:
    """Explicit pure-function inputs for deterministic projection."""

    assertions: Sequence[Assertion]
    events: Sequence[AssertionEvent]
    evidence: Sequence[EvidenceRecord]
    evidence_links: Sequence[EvidenceLink]
    predicate_registry: PredicatesDocument | Sequence[PredicateSpec]
    purpose: str
    effective_at: datetime
    known_at: datetime
    contract_version: str = CONTRACT_VERSION
    previously_published_scopes: Sequence[GovernedScope] = ()
    projector_version: str = PROJECTOR_VERSION


@dataclass(frozen=True, slots=True)
class _Candidate:
    """Internal accepted assertion expanded against a predicate."""

    assertion: Assertion
    predicate: PredicateSpec
    edge: ProjectionEdge


@dataclass(frozen=True, slots=True)
class _Window:
    """Purpose and bitemporal bounds for candidate selection."""

    purpose: str
    effective_at: datetime
    known_at: datetime


@dataclass(frozen=True, slots=True)
class _HashInputs:
    """Revision metadata included in content hashes."""

    purpose: str
    effective_at: datetime
    known_at: datetime
    contract_version: str
    projector_version: str
    evidence_rows: tuple[Mapping[str, str], ...]

    governed_scopes: tuple[GovernedScope, ...]


@dataclass(frozen=True, slots=True)
class _EvidenceBundle:
    """Evidence records and links considered for provenance hashing."""

    evidence: Sequence[EvidenceRecord]
    links: Sequence[EvidenceLink]
    known_at: datetime


def _require_utc(value: datetime, field_name: str) -> datetime:
    """Return ``value`` when timezone-aware with a zero UTC offset."""
    message = f"{field_name} must be timezone-aware UTC"
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError(message)
    if value.utcoffset() != _UTC_OFFSET:
        raise ValidationError(message)
    return value


def _canonical_instant(value: datetime) -> str:
    """Format a UTC datetime for hash inputs (microseconds, ``Z`` suffix)."""
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _predicate_index(registry: PredicatesDocument | Sequence[PredicateSpec]) -> dict[str, PredicateSpec]:
    """Index predicates by id from a document or sequence."""
    predicates = registry.predicates if isinstance(registry, PredicatesDocument) else list(registry)
    index: dict[str, PredicateSpec] = {}
    for predicate in predicates:
        if predicate.id in index:
            raise ProjectionError(f"duplicate predicate id in registry: {predicate.id}")
        index[predicate.id] = predicate
    return index


def _events_by_assertion(events: Sequence[AssertionEvent], known_at: datetime) -> dict[str, list[AssertionEvent]]:
    """Group events with ``recorded_at <= known_at`` by assertion id."""
    grouped: dict[str, list[AssertionEvent]] = defaultdict(list)
    for event in sorted(events, key=lambda item: (item.assertion_id, item.sequence)):
        recorded = _require_utc(event.recorded_at, "event.recorded_at")
        if recorded <= known_at:
            grouped[event.assertion_id].append(event)
    return grouped


def _effective_covers(assertion: Assertion, effective_at: datetime) -> bool:
    """Return True when ``effective_at`` is inside the assertion effective window."""
    start = _require_utc(assertion.effective_from, "effective_from")
    if start > effective_at:
        return False
    if assertion.effective_to is None:
        return True
    end = _require_utc(assertion.effective_to, "effective_to")
    return effective_at <= end


def _conflict_key(assertion: Assertion, predicate: PredicateSpec) -> tuple[str, ...]:
    """Build a conflict grouping key that always includes predicate identity."""
    parts: list[str] = [predicate.id]
    for field_name in predicate.conflict_key:
        if field_name not in _CONFLICT_ATTRS:
            raise ProjectionError(f"unsupported conflict_key field: {field_name}")
        parts.append(str(getattr(assertion, field_name)))
    return tuple(parts)


def _expand_edge(assertion: Assertion, predicate: PredicateSpec) -> ProjectionEdge:
    """Expand one assertion into a single materialized edge via the registry.

    ``bidirectional`` is stored as one canonical subject→object edge with
    ``direction="bidirectional"`` (matching the revision-edge CHECK constraint).
    Consumers must treat that flag as undirected for reverse traversal; the
    projector does not emit a second reverse row.
    """
    projection = predicate.projection
    if projection.direction == "subject_to_object":
        source_id, target_id = assertion.subject_id, assertion.object_id
    elif projection.direction == "object_to_subject":
        source_id, target_id = assertion.object_id, assertion.subject_id
    elif projection.direction == "bidirectional":
        source_id, target_id = assertion.subject_id, assertion.object_id
    else:
        raise ProjectionError(f"unsupported projection direction: {projection.direction}")
    return ProjectionEdge(
        source_id=source_id,
        target_id=target_id,
        edge_type=projection.edge_type,
        strength=projection.strength,
        direction=projection.direction,
        assertion_id=assertion.assertion_id,
    )


def _is_purpose_candidate(assertion: Assertion, predicate: PredicateSpec, window: _Window) -> bool:
    """Return True when assertion/predicate match purpose and effective window."""
    if predicate.projection.purpose != window.purpose:
        return False
    return _effective_covers(assertion, window.effective_at)


def _require_registered_method(assertion: Assertion, predicate: PredicateSpec) -> None:
    """Fail closed when assertion method_id is absent from the predicate registry."""
    if assertion.method_id not in predicate.method_ids:
        raise ProjectionError(
            f"assertion {assertion.assertion_id} method_id {assertion.method_id!r} "
            f"not registered for predicate {predicate.id}"
        )


def _select_accepted_candidates(
    assertions: Sequence[Assertion],
    events_by_id: Mapping[str, Sequence[AssertionEvent]],
    predicates: Mapping[str, PredicateSpec],
    window: _Window,
) -> list[_Candidate]:
    """Select Accepted assertions in purpose/effective scope and expand edges."""
    candidates: list[_Candidate] = []
    for assertion in sorted(assertions, key=lambda item: item.assertion_id):
        recorded = _require_utc(assertion.recorded_at, "recorded_at")
        if recorded > window.known_at:
            continue
        events = events_by_id.get(assertion.assertion_id, ())
        if not events or resolve_state(events) != _ACCEPTED:
            continue
        predicate = predicates.get(assertion.predicate_id)
        if predicate is None or not _is_purpose_candidate(assertion, predicate, window):
            continue
        _require_registered_method(assertion, predicate)
        candidates.append(
            _Candidate(
                assertion=assertion,
                predicate=predicate,
                edge=_expand_edge(assertion, predicate),
            )
        )
    return candidates


def _fail_closed_on_conflicts(candidates: Sequence[_Candidate]) -> None:
    """Raise when any conflict group contains more than one accepted assertion."""
    groups: dict[tuple[str, ...], list[_Candidate]] = defaultdict(list)
    for candidate in candidates:
        groups[_conflict_key(candidate.assertion, candidate.predicate)].append(candidate)
    for key, group in sorted(groups.items(), key=lambda item: item[0]):
        if len(group) <= 1:
            continue
        assertion_ids = sorted(item.assertion.assertion_id for item in group)
        objects = sorted({item.assertion.object_id for item in group})
        raise ProjectionError(
            f"projection conflict for key {key}: assertions={assertion_ids} objects={objects}; fail closed"
        )


def _semantic_edge_payload(edge: ProjectionEdge) -> dict[str, str]:
    """Return semantic edge fields used by ``edge_set_hash``."""
    return {
        "direction": edge.direction,
        "edge_type": edge.edge_type,
        "source_id": edge.source_id,
        "strength": edge.strength,
        "target_id": edge.target_id,
    }


def _provenance_edge_payload(edge: ProjectionEdge) -> dict[str, str]:
    """Return provenance-sensitive edge fields used by ``projection_hash``."""
    payload = _semantic_edge_payload(edge)
    payload["assertion_id"] = edge.assertion_id
    return payload


def _edge_sort_key(edge: ProjectionEdge) -> tuple[str, ...]:
    """Stable sort key for materialized edges."""
    return (
        edge.source_id,
        edge.target_id,
        edge.edge_type,
        edge.strength,
        edge.direction,
        edge.assertion_id,
    )


def _evidence_index(evidence: Sequence[EvidenceRecord]) -> dict[str, EvidenceRecord]:
    """Index evidence by id, failing closed on duplicate evidence_id values."""
    index: dict[str, EvidenceRecord] = {}
    for record in evidence:
        if record.evidence_id in index:
            raise ProjectionError(f"duplicate evidence id in projection inputs: {record.evidence_id}")
        index[record.evidence_id] = record
    return index


def _resolve_as_of_evidence_row(
    link: EvidenceLink,
    evidence_by_id: Mapping[str, EvidenceRecord],
    known_at: datetime,
) -> dict[str, str]:
    """Return one provenance evidence row visible at ``known_at``."""
    record = evidence_by_id.get(link.evidence_id)
    if record is None:
        raise ProjectionError(f"missing evidence record for link {link.link_id}")
    evidence_recorded = _require_utc(record.recorded_at, "evidence.recorded_at")
    if evidence_recorded > known_at:
        raise ProjectionError(f"evidence {record.evidence_id} recorded after known_at for link {link.link_id}")
    return {
        "assertion_id": link.assertion_id,
        "content_sha256": record.content_sha256,
        "evidence_id": link.evidence_id,
        "polarity": link.polarity,
    }


def _evidence_payload_for_edges(
    edges: Sequence[ProjectionEdge],
    bundle: _EvidenceBundle,
) -> list[dict[str, str]]:
    """Build sorted provenance evidence rows for projected assertion IDs."""
    evidence_by_id = _evidence_index(bundle.evidence)
    projected_ids = {edge.assertion_id for edge in edges}
    rows: list[dict[str, str]] = []
    for link in bundle.links:
        if link.assertion_id not in projected_ids:
            continue
        recorded = _require_utc(link.recorded_at, "evidence_link.recorded_at")
        if recorded > bundle.known_at:
            continue
        rows.append(_resolve_as_of_evidence_row(link, evidence_by_id, bundle.known_at))
    rows.sort(key=lambda item: (item["assertion_id"], item["evidence_id"], item["polarity"]))
    return rows


def _compute_hashes(edges: Sequence[ProjectionEdge], inputs: _HashInputs) -> tuple[str, str]:
    """Return ``(edge_set_hash, projection_hash)`` for ordered edges."""
    ordered = sorted(edges, key=_edge_sort_key)
    edge_set_hash = sha256_hex(canonical_json_bytes([_semantic_edge_payload(edge) for edge in ordered]))
    projection_payload: dict[str, Any] = {
        "contract_version": inputs.contract_version,
        "edges": [_provenance_edge_payload(edge) for edge in ordered],
        "effective_at": _canonical_instant(inputs.effective_at),
        "governed_scopes": [
            {"predicate_id": scope.predicate_id, "purpose": scope.purpose} for scope in inputs.governed_scopes
        ],
        "evidence": list(inputs.evidence_rows),
        "known_at": _canonical_instant(inputs.known_at),
        "projector_version": inputs.projector_version,
        "purpose": inputs.purpose,
    }
    projection_hash = sha256_hex(canonical_json_bytes(projection_payload))
    return edge_set_hash, projection_hash


def canonicalize_governed_scopes(
    scopes: Sequence[GovernedScope],
    purpose: str,
) -> tuple[GovernedScope, ...]:
    """Validate, deduplicate, and sort governed scopes for one purpose."""
    pairs = {(scope.purpose, scope.predicate_id) for scope in scopes}
    if any(scope_purpose != purpose or not predicate_id for scope_purpose, predicate_id in pairs):
        raise ValidationError("governed scopes must be non-empty predicates for the projection purpose")
    return tuple(
        GovernedScope(purpose=item_purpose, predicate_id=predicate_id) for item_purpose, predicate_id in sorted(pairs)
    )


def _governed_scopes(
    candidates: Sequence[_Candidate],
    purpose: str,
    previously_published_scopes: Sequence[GovernedScope],
) -> tuple[GovernedScope, ...]:
    """Carry published scopes forward and add scopes from successful candidates."""
    scopes = [*previously_published_scopes]
    scopes.extend(GovernedScope(purpose, candidate.predicate.id) for candidate in candidates)
    try:
        return canonicalize_governed_scopes(scopes, purpose)
    except ValidationError as exc:
        raise ProjectionError(str(exc)) from exc


def project(request: ProjectRequest) -> ProjectionRevision:
    """Project accepted assertions into a deterministic candidate revision.

    ``request.events`` should be the caller-supplied as-of stream; events with
    ``recorded_at`` after ``known_at`` are ignored. Callers must not pre-filter
    assertions to Accepted-only — eligibility is derived here.
    """
    if not request.purpose.strip():
        raise ProjectionError("purpose must be non-empty")
    effective = _require_utc(request.effective_at, "effective_at")
    known = _require_utc(request.known_at, "known_at")
    window = _Window(purpose=request.purpose, effective_at=effective, known_at=known)
    predicates = _predicate_index(request.predicate_registry)
    events_by_id = _events_by_assertion(request.events, known)
    candidates = _select_accepted_candidates(request.assertions, events_by_id, predicates, window)
    _fail_closed_on_conflicts(candidates)
    edges = tuple(sorted((candidate.edge for candidate in candidates), key=_edge_sort_key))
    governed_scopes = _governed_scopes(candidates, request.purpose, request.previously_published_scopes)
    evidence_rows = _evidence_payload_for_edges(
        edges,
        _EvidenceBundle(evidence=request.evidence, links=request.evidence_links, known_at=known),
    )
    edge_set_hash, projection_hash = _compute_hashes(
        edges,
        _HashInputs(
            purpose=request.purpose,
            effective_at=effective,
            known_at=known,
            contract_version=request.contract_version,
            projector_version=request.projector_version,
            evidence_rows=tuple(evidence_rows),
            governed_scopes=governed_scopes,
        ),
    )
    return ProjectionRevision(
        purpose=request.purpose,
        effective_at=effective,
        known_at=known,
        contract_version=request.contract_version,
        projector_version=request.projector_version,
        edge_set_hash=edge_set_hash,
        projection_hash=projection_hash,
        edges=edges,
        governed_scopes=governed_scopes,
    )
