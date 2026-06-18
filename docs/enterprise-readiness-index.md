# Enterprise Readiness Index

**Date:** 2026-06-18
**Purpose:** Single entry point for enterprise-readiness audit, roadmap, PR plan, and release criteria

## What To Read

| Document | Purpose |
| --- | --- |
| `docs/audits/enterprise-readiness-audit.md` | Full audit of what is done, planned, and still missing |
| `docs/roadmap/enterprise-readiness-roadmap.md` | High-level Now / Next / Later remediation roadmap |
| `docs/roadmap/enterprise-readiness-pr-plan.md` | PR-by-PR execution plan with validation commands |
| `docs/roadmap/enterprise-readiness-pr-board.md` | Operational PR board with status and exit criteria |
| `docs/release-checklist.md` | Release gates and enterprise exit criteria |

## Executive Summary

The repo is already strong in control-plane maturity:

- observability and SLOs are implemented;
- rebuild coordination and operator authorization are hardened;
- production architecture is clearly declared.

The remaining work is primarily around:

- durable graph persistence;
- restart/reload semantics;
- promotion gates;
- contract cleanup;
- distributed hosting semantics;
- security/governance automation;
- backup, restore, and DR.

## Recommended Reading Order

1. `docs/audits/enterprise-readiness-audit.md`
2. `docs/roadmap/enterprise-readiness-roadmap.md`
3. `docs/roadmap/enterprise-readiness-pr-plan.md`
4. `docs/roadmap/enterprise-readiness-pr-board.md`
5. `docs/release-checklist.md`

## Operational Rule

If a change touches production behavior, deployment, security, persistence, or recovery, it should be mapped back to one of the documents above before implementation begins.

## Related Entry Points

- [README.md](../README.md) — main repository entry point and production setup overview
- [docs/adr/0002-hosted-deployment-and-persistence.md](./adr/0002-hosted-deployment-and-persistence.md) — hosted persistence decision
- [docs/enterprise-deployment-operating-model.md](./enterprise-deployment-operating-model.md) — promotion and rollback operating model
