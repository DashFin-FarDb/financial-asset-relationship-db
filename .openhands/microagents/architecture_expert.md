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
- **Status:** Every claim is either **landed** (merged to `main` / explicit promotion)
  or **provisional** (open PR / watched series)

## Domains

| Domain | Doc |
|--------|-----|
| Architecture & seams | [domains/architecture.md](docs/compound/domains/architecture.md) |
| API contracts | [domains/api.md](docs/compound/domains/api.md) |
| Persistence / SQL | [domains/persistence.md](docs/compound/domains/persistence.md) |
| CI / guardrails | [domains/ci-guardrails.md](docs/compound/domains/ci-guardrails.md) |
| Rebuild / reconciliation | [domains/rebuild-reconciliation.md](docs/compound/domains/rebuild-reconciliation.md) |
| Deployment / readiness | [domains/deployment.md](docs/compound/domains/deployment.md) |

## Operator notes

See [README.md](docs/compound/README.md). Watched series: [watched-series.yml](docs/compound/watched-series.yml).
Runtime writer mode: [runtime.yml](docs/compound/runtime.yml).
