# GRAC v1 exact-SHA staging evidence and sign-off

**Issue:** #1540
**Evidence date:** 2026-08-07
**Environment proved:** staging only
**Candidate source SHA:** `16d0a69c5d6f9bae94b9251991466bacbf15d3f0`
**Candidate SHA prefix:** `16d0a69c`
**Mechanical evidence status:** complete
**Named human sign-off:** APPROVED — `@mohavro`
**Runtime claim:** `CURRENT` only for the evidenced GRAC v1 financial vertical slice in the proved staging scope

> This record is evidence-only. It does not broaden the claim to production, capacity certification, multi-domain
> generality, or any environment other than the staged GRAC v1 financial vertical slice identified below.

## Final marker

Named human sign-off was recorded on PR #1598 after review of the exact-SHA evidence and redaction disposition.
The authorized machine-readable marker is:

```text
relationship_assertion_v1: PASS|run-31207377781|16d0a69c
```

`run-31207377781` is the final exact-SHA Release Evidence Verify reference. It is the terminal release-evidence
binding for this record, not a substitute for the two staging-proof runs recorded below.

## Exact candidate and corrective lineage

| Evidence                                 | Immutable identity                                                          |
| ---------------------------------------- | --------------------------------------------------------------------------- |
| Final reviewed source SHA                | `16d0a69c5d6f9bae94b9251991466bacbf15d3f0`                                  |
| Corrective #1555 / PR #1563 merge commit | `16a3724703a8fbdd5ff20d82f879b62ec1ee1ba3`                                  |
| Corrective #1556 / PR #1564 merge commit | `a1732133dbf619c4faf2d0225872870beb77ed3e`                                  |
| Contract digest                          | `sha256:1280634438f92308f542b9075234e51902b175201e882c629943a446fb2ddeff` |
| Predicate/registry digest                | `sha256:7ebf9342242e17cdce502bfdb3f5b7a170f27179856aa6405e616ef0098f3e54` |

Both corrective merge commits precede the final candidate SHA.

### Digest reproducibility

- **Contract digest source:** `src/governance/contracts/v1/contract.json` at the candidate SHA. The parsed JSON object
  is serialized with the repository's `canonical_json_bytes()` rules: UTF-8, sorted keys, compact separators,
  `ensure_ascii=False`, no NaN, and no floating-point hash inputs; SHA-256 is then applied to those canonical bytes.
- **Predicate/registry digest source:** `src/governance/contracts/v1/predicates.json` plus
  `src/governance/contracts/v1/transitions.json` at the candidate SHA. `compute_registry_digest()` constructs the
  object `{"predicates": <predicates document>, "transitions": <transitions document>}`, applies the same canonical
  JSON serialization, and hashes the result with SHA-256. The value is also pinned in `contract.json` in grouped form
  and normalized by retaining lowercase hexadecimal characters.

## Exact-SHA workflow evidence

### Seed and publish

- Workflow: `Governed Relationship Assertion Staging Proof`
- Mode: `seed_and_publish`
- Run: `31201674203` (run #19)
- Head/deployed SHA: `16d0a69c5d6f9bae94b9251991466bacbf15d3f0`
- Conclusion: success
- Artifact ID: `9003073849`
- Artifact digest: `sha256:4b39b0eac646dbe10ae4cf6b1c506d1479c89037d11b7e08be8c7c8305ca7e4a`
- Database authorization: passed, PostgreSQL checked, exact SHA bound

### Same-SHA restart/redeploy

The repository's staging operating baseline uses the existing Vercel-hosted topology; it does not require a separate
provider project for staging. The evidence classification here is nevertheless **staging only** and does not certify
production merely because the provider's deployment target has production semantics.

- Provider: Vercel
- Staging mapping label/project name: `financial-asset-relationship-db`
- Bounded hosted target used for exact-SHA readiness: `https://financial-asset-relationship-db-nine.vercel.app`
- Raw provider deployment/project/team identifiers: intentionally omitted under the operational-evidence redaction rule
- Provider audit: restarted deployment READY and bound to GitHub SHA
  `16d0a69c5d6f9bae94b9251991466bacbf15d3f0`
- Restarted detailed-health request: HTTP 200
- Runtime log corroboration: persisted graph store detected and graph initialized from persisted state

The exact-SHA release-readiness artifact subsequently returned the durable-health fields required by the repository's
operational-evidence framework:

| Returned field                                  | Observed value |
| ----------------------------------------------- | -------------- |
| `/api/health/detailed.status`                   | `healthy`      |
| `/api/health/detailed.graph_persistence_configured` | `true`     |
| `/api/health/detailed.graph.persistence_enabled`    | `true`     |
| `/api/health/detailed.graph.persistence_loaded`     | `true`     |
| `/api/health/detailed.graph.startup_source`          | `persisted`|
| `/api/health/detailed.database.configured`           | `true`     |
| `/api/health/detailed.database.reachable`            | `true`     |

### Verify after restart

- Workflow: `Governed Relationship Assertion Staging Proof`
- Mode: `verify_after_restart`
- Run: `31205820371` (run #20)
- Job: `92956484709`
- Head SHA: `16d0a69c5d6f9bae94b9251991466bacbf15d3f0`
- Conclusion: success
- Artifact ID: `9004673255`
- Artifact digest: `sha256:2d0d9d1f341ad28971b94cbedc7d613d1a00c1b6a67b3c706cbb7b1fa70f5ad8`
- Persisted startup: `persisted`
- Governed scopes before/after restart: `1 / 1`
- Historical entries reconstructed: `1`
- Reconstructed assertions: `1`
- Database authorization: passed, PostgreSQL checked, exact SHA bound

Identity-level restart parity recorded directly in the verify artifact:

| Identity / content                   | Restarted observed value                                                   |
| ------------------------------------ | -------------------------------------------------------------------------- |
| Revision ID                          | `24ba3cf9-e6ff-47f8-ae39-e9b007b114ae`                                     |
| Publication ID                       | `442988aa-f9f5-467c-99eb-baf9550a1353`                                     |
| Rebuild job ID                       | `37845906-7da4-4ad7-9ee0-10cf13667f35`                                     |
| Execution ID                         | `d2adc175-365a-4a9b-8008-1055226189a8`                                     |
| Projection/revision hash             | `26f326642a55e7f18b44752c476b8631da94a13a7f730d7f78029256688a1967`         |
| Canonical governed scope             | `financial.bond.issuer_reference@1::financial_graph_current_view`          |

The seed and restart-verification artifacts therefore bind the same revision/publication/rebuild/execution lineage,
not merely equal counts. The persisted predecessor/successor assertion identities and the full exercised publication
history are recorded below. Lifecycle event row IDs are not exposed as public evidence fields; no such IDs are
invented here.

### Final release evidence verification

- Workflow: `Release Evidence Verify`
- Run: `31207377781` (run #19)
- Job: `92961677802`
- Head/release SHA: `16d0a69c5d6f9bae94b9251991466bacbf15d3f0`
- Configuration: `require_persistence=true`, `strict_rc_gate=true`, `hardening_tier=P0`
- Hosted-readiness label: `release-evidence-verify`
- Conclusion: success
- Artifact ID: `9005342053`
- Artifact digest: `sha256:c8ef7523b55aead103964a27491316f580677571b9b0057bf60f5c454de751db`
- Durable persistence: PASS
- Restart/reload: PASS
- Recovery/rebuild: PASS
- API contract: PASS
- Security: PASS
- Hosted readiness/promotion: PASS
- AI-system documentation readiness: PASS
- Database authorization H-P0-04: PASS
- Strict aggregate assertion: PASS
- Hosted runtime: healthy, persisted startup, 19 assets, 70 relationships

The earlier RC2 release-evidence run is historical context only and is not used to certify this candidate.

## Authority and lifecycle proof

| Role / item              | Persisted value                         |
| ------------------------ | --------------------------------------- |
| Proposer of record       | `grac_staging_proposer`                 |
| Determiner               | `admin`                                 |
| Owner/operator           | `admin`                                 |
| Predecessor assertion    | `grac-v1-aapl-bond-issuer-20260805-01`  |
| Successor assertion      | `grac-v1-aapl-bond-issuer-20260807-02`  |
| Predicate                | `financial.bond.issuer_reference@1`     |
| Subject                  | `AAPL_BOND_2030`                        |
| Object                   | `AAPL`                                  |
| Method                   | `bond.issuer_id.resolution@1`           |
| Supersession correlation | `grac-v1-staging-supersession-20260807` |

The proposer and determiner are distinct persisted principals.

Persisted timestamp order under the single supersession correlation:

1. Successor `Proposed` at `2026-08-07 10:06:15.821198+00` by `grac_staging_proposer`.
2. Successor `Accepted` at `2026-08-07 10:06:15.885999+00` by `admin`.
3. Predecessor `Accepted -> Superseded` at `2026-08-07 10:06:15.917214+00` by `admin`, with successor ID
   `grac-v1-aapl-bond-issuer-20260807-02`.

This evidence proves the authoritative successor linkage and records the observed persisted timestamp order without
rewriting predecessor history. It does not claim a separate global monotonic sequence across different assertion
event streams beyond what the authoritative transaction and successor linkage establish.

## Publication, execution, revision, and hash evidence

### Predecessor historical publication

| Field              | Value                                                              |
| ------------------ | ------------------------------------------------------------------ |
| Revision           | `d1ee3300-5725-4006-a105-6bd44027f49a`                             |
| Publication        | `b5d034e9-2fff-455e-b6ae-2b01291d86d0`                             |
| Rebuild job        | `4dae133f-a66b-45df-8a4d-bd8df52146da`                             |
| Execution          | `38dd15c0-4d61-4381-96f4-2a85024f67c6`                             |
| Projection hash    | `aa2f8187499b0bb07bc5a40aec3328aefeec4cc329753ff1c052b77019cec7a4` |
| Edge-set hash      | `c8c8e738ffe460a7716fcd89fa16baf494fe4015e2551a1f107e53b129a7d345` |
| Governed edge rows | `1`                                                                |

### Successor accepted publication

| Field              | Value                                                              |
| ------------------ | ------------------------------------------------------------------ |
| Revision           | `78babe14-266b-49f9-88d3-e70cdef34a90`                             |
| Publication        | `8199d8e1-84e2-44e0-a42f-76e7c3c02dcd`                             |
| Rebuild job        | `4b3aeb23-c332-4d7e-b1f4-4009895b2141`                             |
| Execution          | `a59c21a4-2bda-4f94-b5d8-c344b3f869f4`                             |
| Projection hash    | `6ad67ef6c94e3d8abe18cb2e66c08a88251e5e2236dcdd4eb4cdd5f9ecd9aa74` |
| Edge-set hash      | `c8c8e738ffe460a7716fcd89fa16baf494fe4015e2551a1f107e53b129a7d345` |
| Governed edge rows | `1`                                                                |

### Empty-edge publication

| Field              | Value                                                              |
| ------------------ | ------------------------------------------------------------------ |
| Revision           | `87a7b5b0-811b-4f79-b91c-1d86fe9a05d9`                             |
| Publication        | `559b72d9-47c8-45bf-8e2e-db43a6cf413a`                             |
| Rebuild job        | `fc7ffbf3-c771-421b-b116-286c0734ea53`                             |
| Execution          | `8c6de0cd-225f-4f98-a962-e235b11bab7f`                             |
| Projection hash    | `ec149926bc6c4a7f3c12798e4dd251eba2a24fa1458d7b43f52d0d18970da30a` |
| Edge-set hash      | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| Governed edge rows | `0`                                                                |

### Final restored/certified publication

| Field              | Value                                                              |
| ------------------ | ------------------------------------------------------------------ |
| Revision           | `24ba3cf9-e6ff-47f8-ae39-e9b007b114ae`                             |
| Publication        | `442988aa-f9f5-467c-99eb-baf9550a1353`                             |
| Rebuild job        | `37845906-7da4-4ad7-9ee0-10cf13667f35`                             |
| Execution          | `d2adc175-365a-4a9b-8008-1055226189a8`                             |
| Projection hash    | `26f326642a55e7f18b44752c476b8631da94a13a7f730d7f78029256688a1967` |
| Edge-set hash      | `c8c8e738ffe460a7716fcd89fa16baf494fe4015e2551a1f107e53b129a7d345` |
| Governed edge rows | `1`                                                                |

For the final publication, live persistence verification confirmed publication count `1` and
`publication.execution_id == rebuild_jobs.execution_id == d2adc175-365a-4a9b-8008-1055226189a8`.

## Governed-scope and empty-edge continuity

Canonical governed scope:

```text
financial.bond.issuer_reference@1::financial_graph_current_view
```

The exercised successful publication sequence is:

```text
1 governed edge -> 0 governed edges with scope retained -> 1 governed edge restored
```

The empty-edge revision retained the canonical governed scope in revision metadata. The restart proof retained one
scope before and after restart, and no legacy edge reappeared merely because the governed revision emitted zero
edges.

## Historical reconstruction

The successor later transitioned `Accepted -> Disputed` under correlation
`grac-v1-staging-empty-edge-20260807`, then `Disputed -> Accepted` under correlation
`grac-v1-staging-restore-20260807`. The strict restart proof reconstructed persisted lifecycle history at the
certified revision boundary while retaining the same revision/publication/rebuild/execution lineage and the
predecessor/successor attribution established by the persistence audit.

## Redaction review

- **Observed artifact content:** mechanical inspection found no credentials, passwords, JWTs, bearer tokens, GitHub
  tokens, Supabase keys, or unmasked credential-bearing connection strings in the current seed,
  restart-verification, or release-evidence artifacts. Provider account identifiers are not reproduced in this
  committed evidence record.
- **Masked database locator:** the seed proof artifact contains the validator's intentionally sanitized locator form:
  scheme, hostname and port with path/credentials replaced by a mask. It contains no username, password, database
  name, query string, token, or other credential. The locator itself is not reproduced here.
- **Policy interpretation accepted by human sign-off:** issue #1539 used the broader phrase prohibiting uploaded
  database URLs, while the merged validator deliberately emits the sanitized locator form. The named human signer
  explicitly accepted the interpretation that the prohibition targets secret-bearing or unredacted connection
  material. This does not authorize publication of raw database URLs or secrets.
- **Repository operational-evidence rule:** raw provider account identifiers are prohibited, so provider deployment,
  project and team identifiers used during the authoritative provider audit are deliberately omitted. The permitted
  environment label, project name, target URL, statuses and proof fields are retained.

## Merge-criterion disposition

| Criterion                                        | Disposition                                                    |
| ------------------------------------------------ | -------------------------------------------------------------- |
| #1555, #1556, #1536-#1539 merged                 | SATISFIED                                                      |
| Exact-candidate database authorization rerun     | SATISFIED — release-evidence run `31207377781`                 |
| Both #1539 live proof modes pass                 | SATISFIED — runs `31201674203` and `31205820371`               |
| Exact SHA/source/deployment binding              | SATISFIED                                                      |
| Distinct proposer/determiner                     | SATISFIED                                                      |
| Atomic supersession/successor linkage            | SATISFIED                                                      |
| Publication cardinality/execution ownership      | SATISFIED                                                      |
| Empty-edge governed-scope continuity             | SATISFIED                                                      |
| Restart identity/historical reconstruction       | SATISFIED                                                      |
| Release persistence/readiness/security/API gates | SATISFIED                                                      |
| Artifact/provider redaction review               | SATISFIED — human disposition recorded                         |
| Named human sign-off                             | SATISFIED — `@mohavro`, 2026-08-07, PR #1598                  |
| Machine-readable marker                          | SATISFIED — exactly one authorized marker in this record       |
| `NEXT -> CURRENT` promotion                      | SATISFIED — limited to the proved staging financial slice      |

## Named human sign-off

**Signer:** `@mohavro` — repository owner/authorized human reviewer
**Decision:** APPROVED
**Date:** 2026-08-07
**Recorded on:** PR #1598, issue comment `5220959438`

The signer confirmed that:

- the evidence is accepted as the exact-SHA staging proof for
  `16d0a69c5d6f9bae94b9251991466bacbf15d3f0`;
- the masked-locator redaction interpretation is accepted without authorizing raw secret/URL publication;
- the approved `CURRENT` claim is limited to the proved staging GRAC v1 financial vertical slice; and
- the final marker and corresponding programme-status promotion are authorized.

## Claim boundary after sign-off

GRAC v1 is `CURRENT` for the evidenced staging implementation of
`financial.bond.issuer_reference@1` under `financial_graph_current_view` at the exact candidate SHA above. This is a
bounded capability claim. It is **not** production certification, capacity certification, independent assurance,
proof of a second domain, or authorization to broaden the claim beyond the exact evidence recorded here.
