# Governed Relationship Assertion Contract v1

**Status:** Frozen normative contract (Accepted via [ADR 0008](../adr/0008-governed-relationship-assertion-contract.md))
**Claim class for runtime capability:** `NEXT` until exact-SHA staging proof (programme PR 10 / issue #1540)
**Contract version:** `grac.v1`
**Baseline:** `main` at `5e45753705c10c2c4f50e0e9bc4d07b823d752ab`
**Runtime impact of this document:** Documentation only. An empty assertion store must produce zero behavioural change.

This file is the binding specification for Governed Relationship Assertion Contract (GRAC) v1. ADR 0008 records
the architecture decision. Semantic changes after acceptance require an explicit contract-amendment ADR/PR —
implementation PRs must not silently rewrite this document.

---

## 1. Purpose and boundaries

FarDB stores consequential financial relationships. GRAC v1 makes those relationships:

- **explainable** (provenance, method, evidence polarity, confidence characterization);
- **evidence-bound** (digests and references, not mutable narrative alone);
- **governed over time** (lifecycle, authority, supersession, bitemporal query);
- **operationally trustworthy** (deterministic projection; publish only through rebuild `SUCCEEDED`).

### In scope for v1

- Vocabulary and object boundaries for evidence, assertions, events, revisions, edges, and publications.
- Lifecycle states, transitions, and the authority matrix for those transitions.
- Evidence metadata and confidence semantics (including explicit `not_assessed`).
- Bitemporal rules and supersession invariants.
- Deterministic projection algorithm and fail-closed conflict rules.
- Additive seven-table persistence model.
- First financial vertical slice: `financial.bond.issuer_reference@1`.
- Threat model and control-plane disposition relative to `control-plane-platform`.

### Out of scope for v1

- Multi-domain assertion model or domain packs beyond the financial slice.
- Graph-database migration or replacement of `asset_relationships` as the current read model.
- Raw evidence body / blob custody.
- Generic AI inference writing accepted graph truth.
- Broad RBAC redesign beyond the authority matrix defined here.
- Archiving `control-plane-platform` (separate, explicitly approved action after GRAC v1 is verified).
- Claiming `CURRENT` capability before exact-SHA staging proof.

### Non-negotiable invariants

1. **Assertions are truth; graph edges are projections.**
2. **Append-only history; supersession via successors.** Corrections create successor assertions; they never rewrite history.
3. **Bitemporal time.** `effective_from` / `effective_to` (world time) and `recorded_at` / `known_at` (system knowledge).
4. **Confidence ≠ projection strength.** `not_assessed` must be explicit — no silent defaults.
5. **No evidence bodies in v1.**
6. **Pure deterministic projection.** No implicit clock, unordered DB results, random IDs, or environment-dependent logic.
7. **Conflicts fail closed.** Never last-write-wins.
8. **Publish only through the existing rebuild `SUCCEEDED` path.**
9. **Empty assertion store ⇒ zero behavioural change.**
10. **Main FarDB repo only.** `control-plane-platform` remains private reference-only during GRAC v1.

---

## 2. Vocabulary

| Term | Meaning |
| --- | --- |
| **Proposition** | A typed claim that a subject relates to an object under a versioned predicate. |
| **Evidence** | An immutable reference record (URI/path, SHA-256 digest, media type, visibility, licensing). No body bytes in v1. |
| **Assertion** | An immutable acceptance-candidate record binding proposition, method, confidence characterization, effective time, and optional supersession pointer. |
| **Determination** | The lifecycle outcome applied to an assertion (accept, reject, withdraw, dispute, retract, supersede, reaffirm). |
| **Event** | An append-only lifecycle/authority record for one assertion transition. |
| **Projection** | A pure deterministic function from accepted assertions (+ events needed for eligibility) to candidate graph edges. |
| **Revision** | An immutable candidate graph snapshot with content hashes. |
| **Publication** | Append-only proof that a rebuild job marked `SUCCEEDED` published a revision into the read model. |
| **Read model** | `asset_relationships` and the in-memory adjacency map. Not historical authority. |
| **Predicate** | Versioned registry entry (for example `financial.bond.issuer_reference@1`) defining subject/object types, method IDs, and projection strength. |
| **Confidence** | Optional integer basis points with declared type and method; never silently defaulted. |
| **Projection strength** | Predicate-registry compatibility value for the edge type; independent of confidence. |
| **Supersession** | Replacement of an assertion by a successor assertion without rewriting history. |
| **Authority** | Named role or policy identity permitted to perform a transition under a policy version. |
| **Purpose** | Declared use of a projected view (for example `financial_graph_current_view`). |

### Object boundaries

- Assertions are truth for provenance and history.
- Graph edges are projections of accepted assertions for a purpose and known-at instant.
- Evidence never embeds payload bytes in v1.
- Confidence must not be copied into projection strength fields.

---

## 3. Lifecycle and authority matrix

```mermaid
stateDiagram-v2
    [*] --> Proposed
    Proposed --> Accepted
    Proposed --> Rejected
    Proposed --> Withdrawn
    Accepted --> Disputed
    Accepted --> Retracted
    Accepted --> Superseded
    Disputed --> Accepted: Reaffirm
    Disputed --> Retracted
    Disputed --> Superseded
    Rejected --> [*]
    Withdrawn --> [*]
    Retracted --> [*]
    Superseded --> [*]
```

| State | Terminal | Meaning |
| --- | --- | --- |
| `Proposed` | No | Assertion exists; awaiting determination. |
| `Accepted` | No | Eligible for projection when effective/known-at windows match. |
| `Rejected` | Yes | Authority refused the proposition. |
| `Withdrawn` | Yes | Proposer cancelled before acceptance. |
| `Disputed` | No | Accepted assertion challenged; not eligible for new projection until reaffirmed, retracted, or superseded. |
| `Retracted` | Yes | Prior acceptance withdrawn without replacement successor (or successor recorded separately). |
| `Superseded` | Yes | Replaced by a successor assertion. |

`Rejected`, `Withdrawn`, `Retracted`, and `Superseded` are terminal. Resubmission always creates a **new** assertion.

### Transition event payload (required)

Every transition records, in order:

1. Monotonic event sequence for the assertion.
2. Previous state and resulting state.
3. Actor identity (bounded string).
4. Authority identity and policy version.
5. Bounded rationale (size-capped text; no evidence bodies).
6. Server-recorded UTC `recorded_at`.
7. Trace / correlation ID.
8. Successor assertion ID where the transition is supersession.

Illegal transitions must be rejected by the domain layer. Implementation PRs must encode this matrix, not invent shortcuts.

### Authority matrix

Authorities are logical roles. Mapping to JWT claims, operators, or service identities is an implementation concern
that must preserve this matrix. Missing authority fails closed.

| Transition | Required authority | Notes |
| --- | --- | --- |
| Propose (create → `Proposed`) | `proposer` | Creator becomes the assertion proposer of record. |
| Accept (`Proposed` → `Accepted`) | `acceptor` | May not be the same principal as proposer for the vertical-slice staging proof (reviewer dependency). |
| Reject (`Proposed` → `Rejected`) | `acceptor` | Rejection is an authority determination. |
| Withdraw (`Proposed` → `Withdrawn`) | `proposer` | Only the proposer (or delegated withdrawer policy) may withdraw. |
| Dispute (`Accepted` → `Disputed`) | `disputer` | Challenge does not rewrite history; it changes eligibility. |
| Reaffirm (`Disputed` → `Accepted`) | `acceptor` | Restores projection eligibility. |
| Retract (`Accepted`/`Disputed` → `Retracted`) | `retractor` | Terminal without mandatory successor. |
| Supersede (`Accepted`/`Disputed` → `Superseded`) | `acceptor` | Requires successor assertion ID. |
| Append evidence link on `Proposed`/`Accepted`/`Disputed` | `proposer` or `acceptor` | Evidence rows remain immutable; links are append-only. |
| Build projection revision | `projector` (system) | Pure function; no human authority shortcut. |
| Publish revision into read model | rebuild control plane on `SUCCEEDED` | No alternate publish path. |

Policy version strings are opaque bounded identifiers recorded on every event. Changing who may perform a
transition requires a new policy version and an amendment path if the matrix itself changes.

---

## 4. Evidence and confidence

### Evidence records

Each `relationship_evidence` row is immutable after insert and stores only:

- bounded source reference (URI or repository-relative path);
- SHA-256 digest of the referenced bytes (lowercase hex);
- media type;
- observed / issued timestamps when known;
- visibility classification;
- licensing / reuse metadata;
- custody / collector identity (bounded).

Evidence body bytes, scraped HTML, PDFs, and other blobs are **out of v1**. No evidence bodies are stored.

### Evidence polarity links

`relationship_assertion_evidence` links are append-only and carry polarity:

| Polarity | Meaning |
| --- | --- |
| `supporting` | Evidence tends to support the proposition. |
| `opposing` | Evidence tends to oppose the proposition. |
| `contextual` | Evidence situates the proposition without asserting support or opposition. |

### Confidence vs projection strength

| Field | Rule |
| --- | --- |
| `confidence_bp` | Optional integer basis points in `[0, 10000]`, or null when not assessed. |
| `confidence_type` | Required when `confidence_bp` is set; forbidden to invent silent defaults. |
| `confidence_method` | Required when `confidence_bp` is set; versioned method ID. |
| `confidence_status` | One of `assessed` or `not_assessed`. `not_assessed` requires `confidence_bp` null. |

Projection strength is **never** derived from confidence. Strength comes only from the predicate registry.
Confidence ≠ projection strength.

---

## 5. Bitemporal rules

| Axis | Fields | Meaning |
| --- | --- | --- |
| World / valid time | `effective_from`, `effective_to` | When the proposition applies in the financial world. `effective_to` null means open-ended. |
| System / recorded time | `recorded_at` on assertions and events | When FarDB learned or recorded the fact. Server clock at write; never client-supplied as authority. |
| Query known-at | `known_at` parameter | Reconstruct what FarDB knew as of that instant (events with `recorded_at <= known_at`). |

### Query contract

Historical and current queries that claim temporal correctness must accept:

- `effective_at` — select assertions whose effective window covers the instant;
- `known_at` — select only assertions/events recorded at or before that instant;
- resulting lifecycle state as of `known_at`.

Projection for purpose `financial_graph_current_view` uses the caller-supplied or rebuild-job-bounded
`(effective_at, known_at)` pair. The projector itself must not read wall-clock time.

---

## 6. Supersession

1. Supersession creates a successor assertion; the predecessor transitions to `Superseded`.
2. Predecessor rows are never updated except through append-only events that change lifecycle state.
3. A superseded assertion remains queryable for historical reconstruction.
4. Cycles are forbidden: an assertion must not appear in its own successor chain.
5. At most one non-terminal accepted assertion may occupy a given conflict key (see projection) at a
   `(effective_at, known_at)` pair; violations fail closed at projection time.
6. Retraction without successor is allowed; it removes projection eligibility without inventing replacement truth.

---

## 7. Deterministic projection algorithm

Projection is a **pure** function:

```text
project(accepted_assertions, events_as_of_known_at, predicate_registry, purpose, effective_at, known_at)
  -> ProjectionRevision | ProjectionError
```

### Determinism requirements

- No implicit clock, `uuid4`, random, environment variables, or unordered set iteration that affects output.
- Input assertion/event streams must be sorted by stable keys before folding (assertion ID, event sequence).
- Floating-point values must not participate in hash inputs; use decimal strings or integers from the registry.
- Identical inputs MUST produce identical revision content hashes on SQLite and PostgreSQL.

### Steps

1. **Select** assertions whose events as of `known_at` yield lifecycle state `Accepted`.
2. **Filter** by purpose and predicate scope registered for that purpose.
3. **Filter** by effective window covering `effective_at`.
4. **Expand** each assertion to candidate edges using the predicate registry (type, strength, direction).
5. **Group** candidates by conflict key. For `financial.bond.issuer_reference@1` the conflict key is
   `(predicate_id, subject_id)` — one accepted issuer reference per bond.
6. **Fail closed** if any conflict group contains more than one distinct object or incompatible edge — emit a
   projection error, never last-write-wins.
7. **Materialize** ordered `relationship_projection_edges` for the revision.
8. **Hash** canonical UTF-8 JSON of the ordered edge set (sorted keys, no insignificant whitespace variance)
   with SHA-256 into the revision content hash.
9. **Persist** revision + edges as a candidate. Publication is a separate step.

Disputed, rejected, withdrawn, retracted, and superseded assertions do not emit edges at that `known_at`.

### Publication

A candidate revision becomes current read-model truth only when:

1. A rebuild job owns execution under existing repository guards; and
2. The job is atomically marked `SUCCEEDED`; and
3. A `relationship_projection_publications` row records `(revision_id, rebuild_job_id, published_at)`.

No direct write from assertion APIs into `asset_relationships` bypassing this path is permitted in v1.

---

## 8. Additive persistence model (seven tables)

Seven additive tables; no existing table is removed or repurposed in v1:

| Table | Responsibility |
| --- | --- |
| `relationship_evidence` | Immutable evidence reference, digest, custody and visibility metadata |
| `relationship_assertions` | Immutable proposition, method, confidence, effective time and supersession pointer |
| `relationship_assertion_evidence` | Supporting, opposing or contextual evidence links |
| `relationship_assertion_events` | Ordered lifecycle and authority history |
| `relationship_projection_revisions` | Deterministic candidate graph revisions and hashes |
| `relationship_projection_edges` | Materialized governed edges for each revision |
| `relationship_projection_publications` | Append-only proof that a succeeded rebuild published a revision |

Schema DDL lands in programme PR 3 (#1533). Migrations must preserve SQLite/PostgreSQL parity, must not use
Alembic for this programme path unless a later ADR says otherwise, and must not mutate `asset_relationships`
row semantics as historical authority.

---

## 9. Financial vertical slice: `financial.bond.issuer_reference@1`

| Field | Value |
| --- | --- |
| Predicate | `financial.bond.issuer_reference@1` |
| Subject | `AAPL_BOND_2030` |
| Object | `AAPL` |
| Proposition | The bond’s `issuer_id` references the `AAPL` asset record |
| Method | `bond.issuer_id.resolution@1` |
| Evidence | Canonical digest of the committed sample record (reference only) |
| Projection edge | `AAPL_BOND_2030` → `AAPL` |
| Legacy-compatible type | `corporate_link` |
| Registry strength | `0.8` (explicitly not confidence) |
| Purpose | `financial_graph_current_view` |
| Claim scope | FarDB’s stored issuer reference — **not** an externally verified legal issuance claim |

### Slice proof obligations (programme completion)

The slice must eventually prove, after restart, for an exact deployed SHA:

1. Proposal and acceptance under the authority matrix.
2. Projection and publication through rebuild `SUCCEEDED`.
3. Evidence explanation with polarity.
4. Supersession by refreshed evidence / successor assertion.
5. Historical reconstruction via `effective_at` + `known_at`.
6. Invalid-transition rejection.
7. Answers to the programme completion questions in §12.

---

## 10. Threat model (v1)

| Threat | Mitigation |
| --- | --- |
| Silent rewrite of relationship history | Append-only tables; supersession via successors; no in-place proposition mutation. |
| Last-write-wins ambiguity | Fail-closed projection on conflict keys. |
| Confidence smuggled as edge strength | Separate fields; registry-owned strength; docs/tests forbid conflation. |
| Clock-skewed / nondeterministic projection | Pure projector; no wall clock; stable ordering; cross-DB hash identity tests. |
| Unauthorized acceptance | Authority matrix; acceptor ≠ proposer for staging proof; event audit. |
| Bypass publish path | Publication only via rebuild `SUCCEEDED` + publication row. |
| Evidence body exfiltration / custody creep | No evidence bodies in v1; digests and bounded references only. |
| Second control-plane service drift | Main FarDB repo only; `control-plane-platform` reference-only. |
| Premature CURRENT claims | Claim discipline: Accepted decision ≠ CURRENT capability until #1540. |
| Empty-store behaviour change | Invariant: no assertions ⇒ existing graph/API output unchanged. |

This threat model does not replace ADR 0007 database authorization, release evidence, or DR rehearsal gates.

---

## 11. Control-plane disposition

The earlier [`control-plane-platform`](https://github.com/DashFin-FarDb/control-plane-platform) repository:

- May contribute design ideas (policy-as-code, versioned policies, blocking decisions, append-only audit events,
  governance CI gates).
- Must **not** become a second service or a runtime dependency.
- Must **not** have its implementation or workflows copied wholesale.

During GRAC v1, keep all relationship truth and runtime governance in `financial-asset-relationship-db`.
Keep `control-plane-platform` private and **reference-only**. Archiving or marking it superseded is a separate,
explicitly approved action after GRAC v1 is verified.

---

## 12. Programme completion test

GRAC v1 is complete only when FarDB can answer, for one current governed graph edge:

1. Who proposed this relationship
2. What exact proposition was asserted
3. Which evidence supports or opposes it
4. Which method produced it
5. How confidence was characterized
6. When it was effective
7. When FarDB learned it
8. Who had authority to accept it
9. What it superseded
10. Which graph revision projected it
11. What the graph looked like before the correction

It must answer that after a restart, for an exact deployed SHA, without mutable history or nondeterministic
projection.

---

## 13. Amendment rule

If implementation exposes a semantic flaw in this contract:

1. Stop the implementation PR.
2. Open a contract-amendment PR that updates this file and, when the decision changes, ADR 0008 or a successor ADR.
3. Only then resume implementation against the amended contract.

Do not silently rewrite v1 inside schema, projector, API, UI, or staging PRs.

---

## References

- [ADR 0008: Governed Relationship Assertion Contract](../adr/0008-governed-relationship-assertion-contract.md)
- [ADR 0001: Production architecture](../adr/0001-production-architecture.md)
- [ADR 0007: Database authorization boundary](../adr/0007-database-authorization-boundary.md)
- [State machine and operating authority](./state-machine-and-operating-authority.md)
- [Claims and truth policy](../strategy/claims-and-truth-policy.md)
- [FarDB Project Continuity Ledger](../strategy/fardb-project-continuity.md)
- Tracker epic [#1530](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1530)
