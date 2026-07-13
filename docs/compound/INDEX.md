# Architecture Expert Compound Index

Docs-first memory for architecture, seams, API, persistence/SQL, CI/guardrails,
rebuild/reconciliation, and deployment/readiness.

- **Canon writer:** `scripts/compound/synthesize.py` only
- **Ledger:** `docs/compound/ledger/observations.jsonl` (append-only)
- **Knowledge branch:** `knowledge/architecture-expert` (intended human promotion to `main`; verify before treating as current)
- **Status:** Label every claim **landed** or **provisional** only after verifying branch/PR/ref state vs `main`

## Domains

| Domain | Doc | Landed | Provisional |
|--------|-----|--------|-------------|
| architecture | [domains/architecture.md](domains/architecture.md) | 11 | 23 |
| api | [domains/api.md](domains/api.md) | 2 | 13 |
| persistence | [domains/persistence.md](domains/persistence.md) | 1 | 17 |
| ci-guardrails | [domains/ci-guardrails.md](domains/ci-guardrails.md) | 2 | 26 |
| rebuild-reconciliation | [domains/rebuild-reconciliation.md](domains/rebuild-reconciliation.md) | 1 | 10 |
| deployment | [domains/deployment.md](domains/deployment.md) | 0 | 0 |

## Operator notes

See [README.md](README.md). Watched series: [watched-series.yml](watched-series.yml).
Runtime writer mode: [runtime.yml](runtime.yml).
