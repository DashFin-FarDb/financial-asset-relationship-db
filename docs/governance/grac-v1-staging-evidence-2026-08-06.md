# GRAC v1 exact-SHA staging evidence

relationship_assertion_v1: PASS|seed:31077645600;restart:31078079469|6bb1f2e473c

## Target

- Environment: Vercel staging
- Certified deployed SHA: 6bb1f2e473ce4190b6c7ee06f69734873e2abdce
- Seed workflow SHA: 51c25007c0c9d2c899f33d05286b8ac6a8139cf6
- Restart workflow SHA: 8cbbb8fe2d4eca7988d781bd7617a960f858feff

## Live proof runs

- seed_and_publish: 31077645600
- verify_after_restart: 31078079469
- Strict mode: true
- Persistence required: true
- Result: passed

## Publication lineage

- rebuild_job_id: b6178b62-3d56-42a5-ac17-99c785af5fa2
- execution_id: 45eafdab-8811-4583-9996-cd37211a504a
- publication_id: cc0edcaa-8dd4-4531-a3fb-6270a17be02e
- revision_id: 89b59302-e4a4-41cf-a82a-9605dbd5ebd3
- publication.execution_id matched owning execution: true
- publication count: 1

## Contract bindings

- contract digest: 1280634438f92308f542b9075234e51902b175201e882c629943a446fb2ddeff
- predicate registry digest: 7ebf9342242e17cdce502bfdb3f5b7a170f27179856aa6405e616ef0098f3e54
- projection hash: 1eef1124c6a82ab0a4b8a840d42e1e19abf627a760f0caad17be16ecca89cde7
- edge-set hash: c8c8e738ffe460a7716fcd89fa16baf494fe4015e2551a1f107e53b129a7d345
- governed scopes: `financial.bond.issuer_reference@1::financial_graph_current_view`

## Authority evidence

- proposer identity: grac_staging_proposer
- determiner identity: admin
- proposer and determiner distinct: true
- database authorization evidence: passed and embedded in proof runs
- authorization evidence SHA: 6bb1f2e473ce4190b6c7ee06f69734873e2abdce
- restart proof reference: 31078079469

## Restart verification

- publication survived restart: passed
- governed scopes survived restart: passed
- lifecycle reconstruction: passed
- historical reconstruction: passed

## Review

- Secret and credential redaction reviewed: yes
- Reviewed by: Mohamed Mohamed
- Review date: 2026-08-06
- Sign-off: approved for the evidenced staging scope only

## Durable persistence observation

- Observation run: captured locally, digest 4766421b0c93f12f6fbcb566ab69b9d99e3323ac3b8fd4a917f7fac134f68a71
- Observed deployment SHA: 6bb1f2e473ce4190b6c7ee06f69734873e2abdce
- Retained JSON: `docs/governance/evidence/grac-v1-restart-health-observation.json`
- Retained JSON SHA-256: 4766421b0c93f12f6fbcb566ab69b9d99e3323ac3b8fd4a917f7fac134f68a71

```json
{
  "persistence_configured": true,
  "graph": {
    "persistence_enabled": true,
    "persistence_loaded": true,
    "startup_source": "persisted"
  }
}
```
