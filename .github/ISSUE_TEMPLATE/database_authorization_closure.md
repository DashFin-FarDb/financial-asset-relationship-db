---
name: Database authorization closure (ADR 0007)
about: Track staging/production ADR 0007 remediation and redacted H-P0-04 pass evidence
title: "[DB AUTHZ] Close ADR 0007 / H-P0-04 for "
labels: ["security", "evidence", "enterprise-readiness"]
assignees: ""
---

## Target

**Environment:** <!-- staging / production -->
**Release commit SHA:**
**Closure owner:**
**Linked RC evidence issue (if any):**
**Restricted worksheet location (private handle only):**

## Authorities

- [ADR 0007](https://github.com/DashFin-FarDb/financial-asset-relationship-db/blob/main/docs/adr/0007-database-authorization-boundary.md)
- [Closure runbook](https://github.com/DashFin-FarDb/financial-asset-relationship-db/blob/main/docs/runbooks/database-authorization-closure.md)
- [Public redacted pass template](https://github.com/DashFin-FarDb/financial-asset-relationship-db/blob/main/docs/evidence-records/templates/db-authz-public-redacted-pass.md)
- [Restricted worksheet template](https://github.com/DashFin-FarDb/financial-asset-relationship-db/blob/main/docs/evidence-records/templates/db-authz-restricted-closure.md)

## GitHub Environment readiness

- [ ] `staging` Environment exists (for `staging-promotion`)
- [ ] `staging-manual-gate` Environment exists (tagged dispatches)
- [ ] `release-evidence` Environment exists (for `release-evidence-verify`)
- [ ] `production` / `production-manual-gate` Environments exist when closing production

## Environment secret readiness (presence only)

- [ ] `ASSET_GRAPH_DATABASE_URL` present on every Environment the selected workflow can enter
- [ ] `DATABASE_URL` or `POSTGRES_URL` present on those Environments
- [ ] `COORDINATION_DATABASE_URL` present on those Environments
- [ ] Empty `FARDB_UNTRUSTED_DATABASE_ROLES` left unset (or intentional custom value retained in restricted record)
- [ ] If any boundary uses the global/default inventory: Environment **secret** `FARDB_EXPOSED_DATABASE_SCHEMAS` set to the full inventoried list (include `public` when exposed; or confirmed `public`-only). Skip when every boundary uses an override
- [ ] Per-boundary overrides set where needed (`FARDB_EXPOSED_DATABASE_SCHEMAS_DATABASE` / `_ASSET_GRAPH` / `_COORDINATION` / `_POSTGRES`)
- [ ] Schema secrets present on every Environment the selected workflow can enter (including `*-manual-gate`)

## Remediation sequence

- [ ] Step 1 — Restricted inventory captured
- [ ] Step 2 — Least-privilege design reviewed
- [ ] Step 3 — Negative access tests passed
- [ ] Step 4 — Rollback + app/persist/recovery/restore verified
- [ ] Step 5 — Credential / log review complete
- [ ] Step 6 — Changes applied via governed migration authority
- [ ] Step 7 — Provider advisers + bounded checker passed

## Automated gate run

Select exactly one workflow:

- [ ] `staging-promotion` dispatched
- [ ] `production-promotion` dispatched
- [ ] `release-evidence-verify` dispatched with `hardening_tier=P0` (not `none`)

- [ ] Workflow run URL:
- [ ] Workflow run commit SHA matches the Release commit SHA above
- [ ] `db-authz-output.json` artifact status is `passed`
- [ ] Public marker prepared: `db_authz: PASS|<opaque-ref>`

## Public attachment

- [ ] Public redacted pass template completed (no topology)
- [ ] Marker copied into SHA-bound promotion evidence file
- [ ] Linked from RC evidence issue / promotion record

## Decision

**Gate status:** <!-- Blocked / Passed with redacted evidence -->
**Decision owner:**
**Decision date:**

## Notes

<!-- Do not paste secrets, grants, object names, adviser dumps, or connection strings. -->
