# GRAC v1 exact-SHA staging evidence and sign-off

**Issue:** #1540
**Evidence date:** 2026-08-07
**Environment proved:** staging only
**Candidate source SHA:** `16d0a69c5d6f9bae94b9251991466bacbf15d3f0`
**Candidate SHA prefix:** `16d0a69c`
**Mechanical evidence status:** complete
**Named human sign-off:** PENDING
**Runtime claim:** remains `NEXT` until the named sign-off below is recorded and the final marker/status commit lands

> This record is evidence-only. It does not broaden the claim to production, capacity certification, multi-domain
> generality, or any environment other than the staging scope identified below.

## Final marker

The required machine-readable PASS marker is intentionally absent while named human sign-off is pending. The final
commit after sign-off must add exactly one marker in this form:

```text
relationship_assertion_v1: PASS|run-31207377781|16d0a69c
```

## Exact candidate and corrective lineage

| Evidence | Immutable identity |
| --- | --- |
| Final reviewed source SHA | `16d0a69c5d6f9bae94b9251991466bacbf15d3f0` |
| Corrective #1555 / PR #1563 merge commit | `16a3724703a8fbdd5ff20d82f879b62ec1ee1ba3` |
| Corrective #1556 / PR #1564 merge commit | `a1732133dbf619c4faf2d0225872870beb77ed3e` |
| Contract digest | `1280634438f92308f542b9075234e51902b175201e882c629943a446fb2ddeff` |
| Predicate/registry digest | `7ebf9342242e17cdce502bfdb3f5b7a170f27179856aa6405e616ef0098f3e54` |

Both corrective merge commits precede the final candidate SHA.

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

- Provider: Vercel production-target deployment used as the staging proof target
- Restarted deployment ID: `dpl_AQnVCtpffeaUt7N8PSszSKLuiyYA`
- Project ID: `prj_aFZQ2rTlfLgE3FOn62DqN5iCjdXs`
- Team ID: `team_Lt9gzxS4OvzXelGmNK71QKAF`
- GitHub SHA: `16d0a69c5d6f9bae94b9251991466bacbf15d3f0`
- Provider state: READY
- Runtime startup evidence: `persisted_graph_store` / `startup_source=persisted`
- Detailed health request: HTTP 200

### Verify after restart

- Workflow: `Governed Relationship Assertion Staging Proof`
- Mode: `verify_after_restart`
- Run: `31205820371` (run #20)
- Job: `92956484709`
- Head SHA: `16d0a69c5d6f9bae94b9251991466bacbf15d3f0`
- Conclusion: success
- Artifact ID: `9004673255`
- Artifact digest: `sha256:2d0d9d1f341ad28971b94cbedc7d613d1a00c1b6a67b3c706cbb7b1fa70f5ad8`
- Persisted startup: proved
- Governed scopes before/after restart: `1 / 1`
- Historical entries reconstructed: `1`
- Reconstructed assertions: `1`
- Database authorization: passed, exact SHA bound

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
- Hosted runtime evidence: persisted startup, 19 assets, 70 relationships

The earlier RC2 release-evidence run is historical context only and is not used to certify this candidate.

## Authority and lifecycle proof

| Role / item | Persisted value |
| --- | --- |
| Proposer of record | `grac_staging_proposer` |
| Determiner | `admin` |
| Owner/operator | `admin` |
| Predecessor assertion | `grac-v1-aapl-bond-issuer-20260805-01` |
| Successor assertion | `grac-v1-aapl-bond-issuer-20260807-02` |
| Predicate | `financial.bond.issuer_reference@1` |
| Subject | `AAPL_BOND_2030` |
| Object | `AAPL` |
| Method | `bond.issuer_id.resolution@1` |
| Supersession correlation | `grac-v1-staging-supersession-20260807` |

The proposer and determiner are distinct persisted principals.

Persisted supersession order under one correlation:

1. Successor `Proposed` at `2026-08-07 10:06:15.821198+00` by `grac_staging_proposer`.
2. Successor `Accepted` at `2026-08-07 10:06:15.885999+00` by `admin`.
3. Predecessor `Accepted -> Superseded` at `2026-08-07 10:06:15.917214+00` by `admin`, with successor ID
   `grac-v1-aapl-bond-issuer-20260807-02`.

This proves successor linkage and causal ordering without rewriting predecessor history.

## Publication, execution, revision, and hash evidence

### Predecessor historical publication

| Field | Value |
| --- | --- |
| Revision | `d1ee3300-5725-4006-a105-6bd44027f49a` |
| Publication | `b5d034e9-2fff-455e-b6ae-2b01291d86d0` |
| Rebuild job | `4dae133f-a66b-45df-8a4d-bd8df52146da` |
| Execution | `38dd15c0-4d61-4381-96f4-2a85024f67c6` |
| Projection hash | `aa2f8187499b0bb07bc5a40aec3328aefeec4cc329753ff1c052b77019cec7a4` |
| Edge-set hash | `c8c8e738ffe460a7716fcd89fa16baf494fe4015e2551a1f107e53b129a7d345` |
| Governed edge rows | `1` |

### Successor accepted publication

| Field | Value |
| --- | --- |
| Revision | `78babe14-266b-49f9-88d3-e70cdef34a90` |
| Publication | `8199d8e1-84e2-44e0-a42f-76e7c3c02dcd` |
| Rebuild job | `4b3aeb23-c332-4d7e-b1f4-4009895b2141` |
| Execution | `a59c21a4-2bda-4f94-b5d8-c344b3f869f4` |
| Projection hash | `6ad67ef6c94e3d8abe18cb2e66c08a88251e5e2236dcdd4eb4cdd5f9ecd9aa74` |
| Edge-set hash | `c8c8e738ffe460a7716fcd89fa16baf494fe4015e2551a1f107e53b129a7d345` |
| Governed edge rows | `1` |

### Empty-edge publication

| Field | Value |
| --- | --- |
| Revision | `87a7b5b0-811b-4f79-b91c-1d86fe9a05d9` |
| Publication | `559b72d9-47c8-45bf-8e2e-db43a6cf413a` |
| Rebuild job | `fc7ffbf3-c771-421b-b116-286c0734ea53` |
| Execution | `8c6de0cd-225f-4f98-a962-e235b11bab7f` |
| Projection hash | `ec149926bc6c4a7f3c12798e4dd251eba2a24fa1458d7b43f52d0d18970da30a` |
| Edge-set hash | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| Governed edge rows | `0` |

### Final restored/certified publication

| Field | Value |
| --- | --- |
| Revision | `24ba3cf9-e6ff-47f8-ae39-e9b007b114ae` |
| Publication | `442988aa-f9f5-467c-99eb-baf9550a1353` |
| Rebuild job | `37845906-7da4-4ad7-9ee0-10cf13667f35` |
| Execution | `d2adc175-365a-4a9b-8008-1055226189a8` |
| Projection hash | `26f326642a55e7f18b44752c476b8631da94a13a7f730d7f78029256688a1967` |
| Edge-set hash | `c8c8e738ffe460a7716fcd89fa16baf494fe4015e2551a1f107e53b129a7d345` |
| Governed edge rows | `1` |

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
`grac-v1-staging-restore-20260807`. The final strict restart proof reconstructed persisted lifecycle history at the
revision boundary and retained the predecessor/successor attribution.

## Redaction review

Mechanical artifact review found no credentials, passwords, JWTs, bearer tokens, GitHub tokens, Supabase keys, or
unmasked credential-bearing connection strings in the current seed, restart-verification, or release-evidence
artifacts.

The seed proof result contains the validator's intentionally sanitized database locator: scheme, hostname and port,
with the path replaced by `/*** (masked)`. It contains no username, password, database name, query string, token, or
other credential. Issue #1539 used the broader phrase "Never print or upload ... database URLs" while the merged
validator deliberately implements this masked-locator form. The final human sign-off must explicitly accept the
operational interpretation that the prohibition is against secret-bearing/unredacted database connection material;
otherwise #1539 must be reopened and the affected exact-SHA evidence rerun.

No database locator is reproduced in this evidence record.

## Mechanical merge-criterion disposition

| Criterion | Disposition |
| --- | --- |
| #1555, #1556, #1536-#1539 merged | SATISFIED |
| Exact-candidate database authorization rerun | SATISFIED — release-evidence run `31207377781` |
| Both #1539 live proof modes pass | SATISFIED — runs `31201674203` and `31205820371` |
| Exact SHA/source/deployment binding | SATISFIED |
| Distinct proposer/determiner | SATISFIED |
| Atomic supersession/history | SATISFIED |
| Publication cardinality/execution ownership | SATISFIED |
| Empty-edge governed-scope continuity | SATISFIED |
| Restart/historical reconstruction | SATISFIED |
| Release persistence/readiness/security/API gates | SATISFIED |
| Artifact redaction mechanical scan | SATISFIED; masked-locator policy interpretation requires human acceptance |
| Named human sign-off | PENDING |
| PASS marker / `NEXT -> CURRENT` promotion | BLOCKED until named sign-off |

## Named human sign-off

**Required signer:** repository owner/authorized human reviewer
**GitHub identity:** PENDING
**Decision:** PENDING
**Date:** PENDING

The signer must confirm all of the following:

- the evidence above is accepted as the exact-SHA staging proof for `16d0a69c5d6f9bae94b9251991466bacbf15d3f0`;
- the masked-locator redaction interpretation above is accepted;
- the claim is limited to the proved staging GRAC v1 financial vertical slice; and
- the final marker and `NEXT -> CURRENT` programme-status promotion may be committed.

Until that named sign-off is recorded, GRAC v1 remains `NEXT` and this document must not contain the PASS marker.
