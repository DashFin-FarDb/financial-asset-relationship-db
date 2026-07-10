# Architecture Expert Compound Index

Docs-first memory for architecture, seams, API, persistence/SQL, CI/guardrails,
rebuild/reconciliation, and deployment/readiness.

- **Canon writer:** `scripts/compound/synthesize.py` only
- **Ledger:** `docs/compound/ledger/observations.jsonl` (append-only)
- **Knowledge branch:** `knowledge/architecture-expert` (human merge to `main`)
- **Status:** Every claim is either **landed** or **provisional**

## Domains

| Domain | Doc | Landed | Provisional |
|--------|-----|--------|-------------|
| architecture | [domains/architecture.md](domains/architecture.md) | 0 | 18 |
| api | [domains/api.md](domains/api.md) | 0 | 11 |
| persistence | [domains/persistence.md](domains/persistence.md) | 0 | 16 |
| ci-guardrails | [domains/ci-guardrails.md](domains/ci-guardrails.md) | 0 | 18 |
| rebuild-reconciliation | [domains/rebuild-reconciliation.md](domains/rebuild-reconciliation.md) | 0 | 9 |
| deployment | [domains/deployment.md](domains/deployment.md) | 0 | 0 |

## Operator notes

See [README.md](README.md). Watched series: [watched-series.yml](watched-series.yml).
Runtime writer mode: [runtime.yml](runtime.yml).
