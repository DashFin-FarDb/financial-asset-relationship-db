---
name: architecture-expert
type: knowledge
version: 1.0.0
agent: CodeActAgent
triggers:
  - "@architecture-expert"
  - "@arch-expert"
---

# Architecture Expert Microagent

Compounded architecture memory for this repository.

## Rules

- Read `docs/compound/` before answering seam/API/persistence questions.
- Distinguish provisional vs landed claims.
- Cite or propose annotation for ADRs/policy; never rewrite them.
- Do not overwrite `AGENTS.md`.
- Additive to PR Agent / existing reviewers - do not disable them.

## Index excerpt

## Architecture Expert Compound Index

Docs-first memory for architecture, seams, API, persistence/SQL, CI/guardrails,
rebuild/reconciliation, and deployment/readiness.

- **Canon writer:** `scripts/compound/synthesize.py` only
- **Ledger:** `docs/compound/ledger/observations.jsonl` (append-only)
- **Knowledge branch:** `knowledge/architecture-expert` (intended human promotion to `main`; verify before treating as current)
- **Status:** Label every claim **landed** or **provisional** only after verifying branch/PR/ref state vs `main`

## Domains

| Domain | Doc | Landed | Provisional |
|--------|-----|--------|-------------|
| architecture | [/docs/compound/domains/architecture.md](/docs/compound/domains/architecture.md) | 28 | 24 |
| api | [/docs/compound/domains/api.md](/docs/compound/domains/api.md) | 4 | 11 |
| persistence | [/docs/compound/domains/persistence.md](/docs/compound/domains/persistence.md) | 1 | 16 |
| ci-guardrails | [/docs/compound/domains/ci-guardrails.md](/docs/compound/domains/ci-guardrails.md) | 8 | 22 |
| rebuild-reconciliation | [/docs/compound/domains/rebuild-reconciliation.md](/docs/compound/domains/rebuild-reconciliation.md) | 1 | 9 |
| deployment | [/docs/compound/domains/deployment.md](/docs/compound/domains/deployment.md) | 0 | 0 |

## Operator notes

See [README.md](/docs/compound/README.md). Watched series: [watched-series.yml](/docs/compound/watched-series.yml).
Runtime writer mode: [runtime.yml](/docs/compound/runtime.yml).

