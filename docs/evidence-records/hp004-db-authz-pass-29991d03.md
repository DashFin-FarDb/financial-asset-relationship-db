# Database Authorization Public Redacted Pass — staging (H-P0-04)

**Evidence tier:** hosted target evidence (redacted)
**Authorities:** [ADR 0007](../adr/0007-database-authorization-boundary.md),
[Database authorization closure runbook](../runbooks/database-authorization-closure.md),
[Public redacted pass template](templates/db-authz-public-redacted-pass.md)
**Tracker:** [#1525](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1525),
[DAS-61](https://linear.app/dashfin/issue/DAS-61/db-authz-close-adr-0007-h-p0-04-for-staging)

Do **not** add connection strings, role inventories, object names, policy text, adviser dumps, or raw errors.
Keep detailed findings in the restricted worksheet (private handle only).

## Header

| Field                        | Value                                                                                     |
| ---------------------------- | ----------------------------------------------------------------------------------------- |
| Release commit SHA           | `29991d0328bd84ada289794b0e5191da56272ce9`                                                |
| Target environment           | staging                                                                                   |
| Evidence owner               | mohavro                                                                                   |
| Capture timestamp (UTC)      | 2026-07-23T11:08:31Z                                                                      |
| Workflow                     | release-evidence-verify                                                                   |
| `hardening_tier` (if Assert) | `P0`                                                                                      |
| Workflow run URL             | https://github.com/DashFin-FarDb/financial-asset-relationship-db/actions/runs/30002002715 |
| Workflow run commit SHA      | `29991d0328bd84ada289794b0e5191da56272ce9` (equals Release commit SHA)                    |
| Opaque ref for verifier      | `run-30002002715`                                                                         |

## Public marker (SHA-bound)

```text
hardening_ids: H-P0-01, H-P0-02, H-P0-03, H-P0-04, H-P0-06
topology: jobs=asset_graph; locks=coordination
db_authz: PASS|run-30002002715
```

## Automated gate

- [x] GitHub Environment secrets present for asset-graph, auth/app (or postgres fallback), and coordination URLs
- [x] Workflow run commit SHA equals Release commit SHA above
- [x] Workflow is `release-evidence-verify` with `hardening_tier=P0` (not `none`)
- [x] `scripts/check_database_authorization.py` exited successfully in the linked workflow
- [x] Workflow used applicable Environment secrets; schema inventory left at public-only / default untrusted roles (no override secrets set)
- [x] Redacted artifact `db-authz-output.json` shows `"status":"passed"` (no topology fields)
- [x] Shared-boundary decision recorded at label level only (`topology` marker above)
- [x] `FARDB_UNTRUSTED_DATABASE_ROLES` choice: default (secret left unset)

## Companion artifacts from the same run (redacted status only)

| Artifact                | Status |
| ----------------------- | ------ |
| `docs-readiness.json`   | passed |
| `readiness-output.json` | passed |
| `db-authz-output.json`  | passed |

## Exit criteria (pass/fail only)

- [x] Exposed-schema RLS control: passed (all inventoried exposed schemas)
- [x] Untrusted-role unintended authority: passed
- [x] Views automated access check: passed
- [x] Privileged functions automated execution check: passed
- [ ] Privileged functions manual fixed-search-path review: passed (details restricted)
- [ ] Application / recovery / restore checks after enforcement: passed
- [ ] High-severity access-control findings: none unresolved (or named time-bounded exception approved)
- [ ] Credential review and rollback evidence: complete (details restricted)
- [ ] Redacted operator sign-off: complete

## Operator sign-off (public)

| Role                          | Named owner | Sign-off | Date (UTC) |
| ----------------------------- | ----------- | -------- | ---------- |
| Closure owner                 | mohavro     | Pending  |            |
| Promotion / release authority |             | Pending  |            |

## Notes

- Deny-by-default migrations: PR #1526 on `main`.
- Docs readiness file for P0 assert path: PR #1527 on `main`.
- Restricted worksheet remains offline; do not paste topology into this record or #1525.
- Mark H-P0-04 / FPC-2026-07-21-01 Satisfied only after remaining exit criteria and named sign-off above.
