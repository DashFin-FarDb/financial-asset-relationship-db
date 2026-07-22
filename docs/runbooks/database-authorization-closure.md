# Database Authorization Closure Runbook (ADR 0007 / H-P0-04)

**Status:** Operator setup path (repository). Live target-environment closure remains release-blocking.
**Authorities:** [ADR 0007](../adr/0007-database-authorization-boundary.md),
[Release Evidence Pack](../release-evidence-pack.md) (H-P0-04),
[FPC-2026-07-21-01](../strategy/fardb-project-continuity.md).

This runbook sets up and executes the ADR 0007 remediation sequence. It does **not** mutate databases by itself
and does **not** publish restricted topology. Fill the restricted worksheet offline; attach only redacted pass/fail
evidence publicly.

## What “set up” means

| Layer                                     | Done in repository?                                      | Operator still must                          |
| ----------------------------------------- | -------------------------------------------------------- | -------------------------------------------- |
| ADR + bounded checker                     | Yes (`scripts/check_database_authorization.py`)          | Run against live boundaries                  |
| Fail-closed workflow wiring               | Yes (staging / production / release-evidence)            | Configure GitHub Environment secrets         |
| Verifier marker grammar                   | Yes (`db_authz: PASS\|<opaque-ref>`)                     | Attach a real opaque ref after a passing run |
| Restricted / public worksheets            | Yes (templates under `docs/evidence-records/templates/`) | Complete them for the target env             |
| Live inventory, roles, policies, advisers | No (must stay restricted)                                | Capture and remediate off-repo               |

## Prerequisites (GitHub Environment secrets)

Promotion and Assert-path authz steps fail closed unless **all** required boundaries are present:

| Secret / variable                | Required for H-P0-04 authz gate | Notes                                                                                                            |
| -------------------------------- | ------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `ASSET_GRAPH_DATABASE_URL`       | Yes                             | Graph boundary                                                                                                   |
| `DATABASE_URL` or `POSTGRES_URL` | Yes (at least one)              | Auth/app boundary                                                                                                |
| `COORDINATION_DATABASE_URL`      | Yes for authz gate              | Point at the effective coordination boundary; required by workflows even if topology documents a shared fallback |
| `FARDB_UNTRUSTED_DATABASE_ROLES` | Optional                        | Defaults to provider roles `anon,authenticated` when unset; leave empty unset (workflows unset empty strings)    |
| `HOSTED_READINESS_BASE_URL`      | For hosted readiness steps      | Separate from authz checker                                                                                      |

Configure these on the GitHub Environments used by `staging-promotion.yml`, `production-promotion.yml`, and
`release-evidence-verify.yml`. Record **presence only** in public evidence—never paste values.

See also [Staging Deployment Operating Baseline](../staging-deployment-operating-baseline.md).

## Local dry-run (optional, non-CI)

With local env vars pointing at a **non-production** PostgreSQL boundary you control:

```bash
# Optional override when not using default anon,authenticated
# export FARDB_UNTRUSTED_DATABASE_ROLES=anon,authenticated
export DATABASE_URL='postgresql://…'
export ASSET_GRAPH_DATABASE_URL='postgresql://…'
export COORDINATION_DATABASE_URL='postgresql://…'
# Default schema is public. Repeat per inventoried exposed schema:
python scripts/check_database_authorization.py --exposed-schema public
```

Expect bounded pass/fail output only. Do not commit connection strings or catalog dumps. CI/promotion workflows
check the default schema only; closure still requires a pass for every inventoried exposed schema (record in the
restricted worksheet).

## Remediation sequence (ADR 0007)

Track progress with the
[Database authorization closure](../../.github/ISSUE_TEMPLATE/database_authorization_closure.md) issue template.
Use the worksheets:

- Restricted: [db-authz-restricted-closure.md](../evidence-records/templates/db-authz-restricted-closure.md)
  (do **not** commit filled copies with live topology)
- Public: [db-authz-public-redacted-pass.md](../evidence-records/templates/db-authz-public-redacted-pass.md)

| Step | Action                                                                              | Evidence home                               |
| ---- | ----------------------------------------------------------------------------------- | ------------------------------------------- |
| 1    | Capture live object, route, role, policy, view, and function inventory              | Restricted worksheet                        |
| 2    | Design least-privilege roles and policies on staging / non-prod                     | Restricted worksheet                        |
| 3    | Run negative access tests before enabling enforcement                               | Restricted worksheet + optional drill issue |
| 4    | Rehearse rollback; confirm app, persisted startup, recovery, and restore still work | Restricted + public readiness/restore links |
| 5    | Review access logs; rotate credentials whose exposure cannot be bounded             | Restricted worksheet                        |
| 6    | Apply reviewed changes through governed migration authority                         | Restricted change record                    |
| 7    | Re-run provider advisers and the bounded checker; attach redacted closure           | Public redacted pass + opaque workflow ref  |

Privileged / security-definer functions require the **manual** fixed-search-path review called out in ADR 0007
(the checker cannot infer business privilege solely from catalog shape).

## Dispatch the automated gate

After Environment secrets are present and remediation is applied:

1. Prefer **staging-promotion** (or **production-promotion** when that is the target) with a SHA-bound evidence file
   that already includes hardening markers (see pack). The workflow runs
   `scripts/check_database_authorization.py` and uploads redacted `db-authz-output.json`.
2. Alternatively dispatch **release-evidence-verify** with `hardening_tier=P0` (default). Soft rehearsal
   (`hardening_tier=none`) must not be treated as RC proof.
3. On success, form the public marker from the run or artifact id, for example:
   - `db_authz: PASS|run-<digits>`
   - `db_authz: PASS|artifact-<digits>`
   - `db_authz: PASS|<prefix>-run-<digits>`
   - `db_authz: PASS|<numeric-run-id>` (≥6 digits)

Bare `PASS`, `TBD`, `TODO`, and angle-bracket templates are rejected by `scripts/verify_staging_promotion.py`.

## Public evidence attachment

1. Copy the public redacted pass template into the RC evidence issue or a companion evidence record.
2. Paste the `db_authz: PASS|<opaque-ref>` line into the SHA-bound evidence file used by promotion.
3. Confirm exit-criteria checkboxes without object names, grants, or adviser dumps.
4. Keep the restricted worksheet offline (or in an approved private store). Never paste it into PRs or CI logs.

## Exit criteria (gate closes only when all are true)

From ADR 0007:

- Every exposed-schema table passes the RLS control.
- Untrusted provider roles have no unintended database authority.
- Views pass the automated access check; privileged functions pass automated execution checks **and** manual
  fixed-search-path review.
- Application, recovery, and restore integration checks pass after enforcement.
- No unresolved high-severity access-control finding remains without a named, time-bounded exception approved by the release authority.
- Credential review, rollback evidence, and redacted operator sign-off are complete.
- Public marker `db_authz: PASS|<opaque-ref>` is attached for the exact artefact under promotion.

Until then H-P0-04 / FPC-2026-07-21-01 remain **Partially satisfied / Blocked**.

## Related documents

- [ADR 0007](../adr/0007-database-authorization-boundary.md)
- [Release Evidence Pack — hardening markers](../release-evidence-pack.md#hardening-evidence-markers)
- [Operational Evidence Capture Framework](../operations/operational-evidence-capture-framework.md)
- [Hosted Readiness Evidence Guide](../operations/hosted-readiness-evidence-guide.md)
- [Staging Deployment Operating Baseline](../staging-deployment-operating-baseline.md)
