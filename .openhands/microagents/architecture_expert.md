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
| architecture | [domains/architecture.md](domains/architecture.md) | 0 | 19 |
| api | [domains/api.md](domains/api.md) | 0 | 11 |
| persistence | [domains/persistence.md](domains/persistence.md) | 0 | 17 |
| ci-guardrails | [domains/ci-guardrails.md](domains/ci-guardrails.md) | 0 | 19 |
| rebuild-reconciliation | [domains/rebuild-reconciliation.md](domains/rebuild-reconciliation.md) | 0 | 9 |
| deployment | [domains/deployment.md](domains/deployment.md) | 0 | 0 |

## Operator notes

See [README.md](README.md). Watched series: [watched-series.yml](watched-series.yml).
Runtime writer mode: [runtime.yml](runtime.yml).

