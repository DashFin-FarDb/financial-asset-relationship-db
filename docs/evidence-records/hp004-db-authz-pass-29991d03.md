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

| Field                        | Value                                                                                                        |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Release commit SHA           | `29991d0328bd84ada289794b0e5191da56272ce9`                                                                   |
| Target environment           | staging                                                                                                      |
| Evidence owner               | mohavro                                                                                                      |
| Capture timestamp (UTC)      | 2026-07-23T11:08:31Z                                                                                         |
| Workflow                     | release-evidence-verify                                                                                      |
| `hardening_tier` (if Assert) | `P0`                                                                                                         |
| Workflow run URL             | [run 30002002715](https://github.com/DashFin-FarDb/financial-asset-relationship-db/actions/runs/30002002715) |
| Workflow run commit SHA      | `29991d0328bd84ada289794b0e5191da56272ce9` (equals Release commit SHA)                                       |
| Opaque ref for verifier      | `run-30002002715`                                                                                            |
| Closure completed (UTC)      | 2026-07-24T14:30:00Z                                                                                         |

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

Same-run suite outcomes (redacted counts only): persistence, recovery, restart, API, and security JUnit
artifacts reported zero failures / zero errors under the release-evidence verify job.

## Exit criteria (pass/fail only)

- [x] Exposed-schema RLS control: passed (all inventoried exposed schemas; public-only inventory)
- [x] Untrusted-role unintended authority: passed (bounded checker + live grant count review)
- [x] Views automated access check: passed
- [x] Privileged functions automated execution check: passed
- [x] Privileged functions manual fixed-search-path review: passed (fixed nonempty `search_path` without `$user`; not executable by untrusted roles)
- [x] Application / recovery / restore checks after enforcement: passed (same-run readiness + persistence/recovery/restart suites; restore path covered by #1505 runbook + readiness persistence smoke)
- [x] High-severity access-control findings: passed (none unresolved; provider adviser INFO-only deny-by-default RLS notices are expected, not high severity)
- [x] Credential review and rollback evidence: passed (no unbounded credential exposure requiring rotation; migration rollback retained in restricted store; app path verified post-enforcement)
- [x] Redacted operator sign-off: passed

## Remediation sequence (public status only)

- [x] Step 1 — Restricted inventory captured (public-only exposed schema; details offline)
- [x] Step 2 — Least-privilege design reviewed (#1526 deny-by-default)
- [x] Step 3 — Negative access tests passed ([run 30002002715](https://github.com/DashFin-FarDb/financial-asset-relationship-db/actions/runs/30002002715))
- [x] Step 4 — Rollback + app/persist/recovery/restore verified (same-run suites + readiness)
- [x] Step 5 — Credential / log review complete (no unexpected untrusted-role authority; details offline)
- [x] Step 6 — Changes applied via governed migration authority (#1526)
- [x] Step 7 — Provider advisers + bounded checker passed ([run 30002002715](https://github.com/DashFin-FarDb/financial-asset-relationship-db/actions/runs/30002002715))

## Operator sign-off (public)

| Role                          | Named owner | Sign-off | Date (UTC) |
| ----------------------------- | ----------- | -------- | ---------- |
| Closure owner                 | mohavro     | Approved | 2026-07-24 |
| Promotion / release authority | mohavro     | Approved | 2026-07-24 |

## Notes

- Deny-by-default migrations: PR #1526 on `main`.
- Docs readiness file for P0 assert path: PR #1527 on `main`.
- Public PASS attachment: PR #1528 on `main`.
- Restricted worksheet remains offline; do not paste topology into this record or #1525.
- H-P0-04 / FPC-2026-07-21-01 marked Satisfied after the exit criteria and named sign-off above.
