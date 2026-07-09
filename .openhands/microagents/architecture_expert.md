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
- **Knowledge branch:** `knowledge/architecture-expert` (human merge to `main`)
- **Status:** Every claim is either **landed** or **provisional**

## Domains

| Domain | Doc | Landed | Provisional |
|--------|-----|--------|-------------|
| architecture | [domains/architecture.md](domains/architecture.md) | 0 | 4 |
| api | [domains/api.md](domains/api.md) | 0 | 1 |
| persistence | [domains/persistence.md](domains/persistence.md) | 0 | 2 |
| ci-guardrails | [domains/ci-guardrails.md](domains/ci-guardrails.md) | 0 | 4 |
| rebuild-reconciliation | [domains/rebuild-reconciliation.md](domains/rebuild-reconciliation.md) | 0 | 0 |
| deployment | [domains/deployment.md](domains/deployment.md) | 0 | 0 |

## Operator notes

See [README.md](README.md). Watched series: [watched-series.yml](watched-series.yml).
Runtime writer mode: [runtime.yml](runtime.yml).

