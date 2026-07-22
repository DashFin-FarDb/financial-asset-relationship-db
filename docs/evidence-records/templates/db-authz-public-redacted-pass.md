# Public Redacted Database Authorization Pass (H-P0-04)

**Evidence tier:** hosted target evidence (redacted)
**Authorities:** [ADR 0007](../../adr/0007-database-authorization-boundary.md),
[Database authorization closure runbook](../../runbooks/database-authorization-closure.md)

Do **not** include connection strings, role inventories, object names, policy text, adviser dumps, or raw errors.
Keep detailed findings in the restricted worksheet.

## Header

| Field                        | Value                                                              |
| ---------------------------- | ------------------------------------------------------------------ |
| Release commit SHA           |                                                                    |
| Target environment           | staging / production                                               |
| Evidence owner               |                                                                    |
| Capture timestamp (UTC)      |                                                                    |
| Workflow                     | staging-promotion / production-promotion / release-evidence-verify |
| `hardening_tier` (if Assert) | `P0` required for RC-valid release-evidence; `none` is not closure |
| Workflow run URL             |                                                                    |
| Workflow run commit SHA      | must equal Release commit SHA                                      |
| Opaque ref for verifier      | `run-…` / `artifact-…` / numeric run id                            |

## Public marker (copy into SHA-bound promotion evidence file)

Copy the line below into the SHA-bound promotion evidence file. **Do not** replace the placeholder in this template
file or commit a filled copy of the template.

```text
db_authz: PASS|<opaque-workflow-run-or-artifact-id>
```

Soft rehearsal (`release-evidence-verify` with `hardening_tier=none`) is **not** valid closure evidence.

## Automated gate

- [ ] GitHub Environment secrets present for asset-graph, auth/app (or postgres fallback), and coordination URLs
- [ ] Workflow run commit SHA equals Release commit SHA above
- [ ] If workflow is `release-evidence-verify`: input `hardening_tier=P0` (not `none`)
- [ ] `scripts/check_database_authorization.py` exited successfully in the linked workflow (default exposed schema)
- [ ] Every inventoried exposed schema passed the checker (`--exposed-schema` per schema; names stay restricted)
- [ ] Redacted artifact `db-authz-output.json` shows `"status":"passed"` (no topology fields)
- [ ] Shared-boundary decision documented at label level only (if applicable)
- [ ] `FARDB_UNTRUSTED_DATABASE_ROLES` choice recorded as “default” or “custom (restricted record)” — no role list here

## Exit criteria (pass/fail only)

- [ ] Exposed-schema RLS control: passed (all inventoried exposed schemas)
- [ ] Untrusted-role unintended authority: passed
- [ ] Views automated access check: passed
- [ ] Privileged functions automated execution check: passed
- [ ] Privileged functions manual fixed-search-path review: passed (details restricted)
- [ ] Application / recovery / restore checks after enforcement: passed
- [ ] High-severity access-control findings: none unresolved (or named time-bounded exception approved)
- [ ] Credential review and rollback evidence: complete (details restricted)
- [ ] Redacted operator sign-off: complete

## Operator sign-off (public)

| Role                          | Named owner | Sign-off | Date (UTC) |
| ----------------------------- | ----------- | -------- | ---------- |
| Closure owner                 |             | Pending  |            |
| Promotion / release authority |             | Pending  |            |

## Notes

<!-- Redacted notes only. Link the restricted record by private handle, not by pasting contents. -->
