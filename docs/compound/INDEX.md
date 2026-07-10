# Architecture Expert Compound Index

Docs-first memory for architecture, seams, API, persistence/SQL, CI/guardrails,
rebuild/reconciliation, and deployment/readiness.

- **Canon writer:** `scripts/compound/synthesize.py` only
- **Ledger:** `docs/compound/ledger/observations.jsonl` (append-only)
- **Knowledge branch:** `knowledge/architecture-expert` (intended human promotion to `main`; verify before treating as current)
- **Status:** Label every claim **landed** or **provisional** only after verifying branch/PR/ref state vs `main`

## Domains

| Domain | Doc |
|--------|-----|
| Architecture & seams | [domains/architecture.md](domains/architecture.md) |
| API contracts | [domains/api.md](domains/api.md) |
| Persistence / SQL | [domains/persistence.md](domains/persistence.md) |
| CI / guardrails | [domains/ci-guardrails.md](domains/ci-guardrails.md) |
| Rebuild / reconciliation | [domains/rebuild-reconciliation.md](domains/rebuild-reconciliation.md) |
| Deployment / readiness | [domains/deployment.md](domains/deployment.md) |

## Operator notes

See [README.md](README.md). Watched series: [watched-series.yml](watched-series.yml).
Runtime writer mode: [runtime.yml](runtime.yml).
