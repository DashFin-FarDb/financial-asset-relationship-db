# AI System Specification

**Status:** current baseline for release-evidence docs readiness
**Applies to:** Financial Asset Relationship Database (FarDB) production path
**Audience:** operators, reviewers, and release-evidence runs
**Related:** [Claims and truth policy](strategy/claims-and-truth-policy.md),
[ADR 0001](adr/0001-production-architecture.md),
[Release Evidence Pack](release-evidence-pack.md)

This document supports transparency and human-oversight expectations analogous to
EU AI Act Article 13 (transparency) and Article 14 (human oversight) for FarDB’s
production operating model. It describes what the system does, what it does not
claim, and where humans remain in control.

## 1. System identity

| Item             | Description                                                                                           |
| ---------------- | ----------------------------------------------------------------------------------------------------- |
| Product          | Financial Asset Relationship Database (FarDB)                                                         |
| Production stack | FastAPI backend (`api/`) + Next.js frontend (`frontend/`)                                             |
| Non-production   | Gradio UI (`app.py`) for demos and internal testing only                                              |
| Primary function | Persist and expose an asset relationship graph, metrics, and rebuild/recovery control-plane behaviour |

FarDB is an enterprise data and operations system. It is **not** marketed as a
general-purpose generative AI assistant or automated investment advisor.

## 2. Intended use

**Intended:**

- Operators and authorized users inspect asset relationships, metrics, and API
  health for staging/production targets that have passed release-evidence gates.
- Rebuild, recovery, and promotion workflows run under GitHub Environments with
  documented secrets and manual gates where required.
- Release evidence is captured from workflow outputs and attached redacted
  artefacts (see [Release Evidence Pack](release-evidence-pack.md)).

**Not intended:**

- Autonomous trading, credit decisions, or unsupervised portfolio allocation.
- Unattended production promotion without the required Environment approvals and
  evidence markers.
- Treating coding-agent assistance during development as a runtime user-facing
  AI feature of the deployed product.

## 3. Transparency (Article 13 analogue)

Operators and reviewers can determine system behaviour from:

1. **Architecture declaration** — FastAPI + Next.js is production; Gradio is not
   ([ADR 0001](adr/0001-production-architecture.md)).
2. **Public API surface** — OpenAPI from the FastAPI app; dashboard routes load
   graph/metrics data from documented endpoints.
3. **Authorization boundary** — Hosted database deny-by-default for provider
   untrusted roles (`anon` / `authenticated`) per
   [ADR 0007](adr/0007-database-authorization-boundary.md); FastAPI remains the
   product ingress.
4. **Claims discipline** — Statements about capability must follow
   [claims and truth policy](strategy/claims-and-truth-policy.md) (CURRENT / NEXT /
   RESEARCH / AMBITION).
5. **Promotion logging** — Staging and production promotion workflows record
   promotion decisions for auditability.

When AI-assisted tooling is used in development or review, that assistance is
outside the runtime product boundary unless a FUTURE ADR explicitly brings a
model-serving path into production.

## 4. Human oversight (Article 14 analogue)

Humans retain effective control through:

| Control                | Where                                                                                                                       |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Environment approvals  | GitHub Environments (`staging`, `staging-manual-gate`, `release-evidence`, production twins)                                |
| Manual workflow inputs | `workflow_dispatch` for release-evidence, hosted readiness, promotion                                                       |
| Strict RC gate         | `hardening_tier=P0` on release-evidence fails closed on skipped hosted readiness, docs readiness, or database authorization |
| Authorization closure  | Operator runbook and `[DB AUTHZ]` tracker before marking H-P0-04 Satisfied                                                  |
| Sign-off               | Named operator evidence required for enterprise release items in the evidence pack                                          |

Automated checks (pytest gates, hosted readiness, database authorization checker)
inform humans; they do not replace Environment protection rules or required
manual sign-off artefacts.

## 5. Data and risk posture (summary)

- Durable graph and auth data use configured PostgreSQL boundaries
  (`DATABASE_URL` / `POSTGRES_URL`, `ASSET_GRAPH_DATABASE_URL`,
  `COORDINATION_DATABASE_URL`) on GitHub Environments.
- Provider Data API untrusted roles are denied by design on exposed schemas
  (ADR 0007).
- Secrets, connection strings, and restricted topology must not appear in public
  issues, PR bodies, or redacted pass templates.

## 6. Limitations

- Presence of this file satisfies the release-evidence **docs readiness** file
  check; it does not by itself certify EU AI Act conformity assessment or
  third-party audit.
- Hosted readiness and database authorization remain separate gates with their
  own pass markers.
- Soft rehearsal (`hardening_tier=none`) is not valid RC / H-P0-04 closure
  evidence.

## 7. Change control

Update this specification when:

- A production model-serving or automated decision feature is introduced
- Oversight gates or Environment approval requirements change
- The production architecture ADR is superseded

Link material changes from the relevant ADR or release-evidence pack update.
