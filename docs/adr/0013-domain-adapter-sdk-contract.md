# ADR 0013: Domain-Adapter SDK Contract and Non-Financial Domain Proof

**Status:** Accepted
**Date:** 2026-11-27
**Related:** `src/domain_sdk/`, `src/logic/asset_graph.py`, `docs/strategy/fardb-project-continuity.md` (`FPC-2026-07-21-05`)

## Context

FarDB's canonical graph engine (`AssetRelationshipGraph`) and durable persistence layer (`AssetGraphRepository`) were
originally built for financial assets (`Equity`, `Bond`, `Commodity`, `Currency`). Strategy commitment
`FPC-2026-07-21-05` requires demonstrating that a second, non-financial domain can plug into FarDB through a versioned
adapter contract **without modifying `src/logic/asset_graph.py` or introducing domain-specific convenience branches into
the canonical core**.

## Decision

1. **Canonical `DomainAdapter` Protocol (`src/domain_sdk/protocol.py`):**
   Every domain adapter implements a `@runtime_checkable` protocol exposing:
   - `domain_id` (lowercase stable identifier), `entity_types`, and `predicate_ids`
   - `validate_entity(entity)` (fail-closed `ValueError` on contract violations)
   - `build_edges(entities)` (deterministic edge derivation within declared `predicate_ids` and `[-1.0, 1.0]` strength)
   - `to_canonical_graph(entities)` (pure projection onto `AssetRelationshipGraph`)
   - `sample_entities()` (deterministic conformance fixture)
2. **Explicit Registry (`src/domain_sdk/registry.py`):**
   Adapters are registered explicitly in `DomainRegistry`; duplicate or unknown `domain_id` lookups fail closed.
3. **Reusable Conformance Suite (`src/domain_sdk/conformance.py`):**
   Every adapter must pass `DomainConformanceSuite` (protocol compliance, positive/negative validation, edge
   determinism, declared predicate/strength bounds, and canonical projection).
4. **Second Reference Domain (`src/domain_sdk/human_resources_adapter.py`):**
   `HumanResourcesDomainAdapter` (`domain_id="human_resources"`) models employees, departments, roles, and skills with
   reporting, assignment, role-holding, skill, succession, and peer-department predicates. It passes
   `DomainConformanceSuite` and round-trips through `AssetGraphRepository` on SQLite with zero changes to
   `src/logic/asset_graph.py`.

## Consequences

- **Positive:** Domain expansion is strictly bounded behind `src/domain_sdk/`; new domains are mechanically verified by
  `DomainConformanceSuite` and cannot leak domain-specific logic into `AssetRelationshipGraph`.
- **Negative / Scope Boundary:** Canonical persistence still projects non-financial entities onto the existing `Asset`
  table schema (`AssetClass` + `sector` + `price` slots). Dedicated domain-native storage tables remain out of scope
  until a product domain requires them.
