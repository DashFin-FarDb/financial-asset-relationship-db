# Operator Sign-Off Record (`bf624469`) — 2026-11-27

**Evidence ID:** `FARDB-SIGNOFF-2026-11-27-bf624469`
**Gate:** Enterprise readiness item 8 — Operator Sign-Off (Issue #1914)
**Bound Release Commit SHA:** `bf6244691` (`main`)
**Capture Timestamp (UTC):** `2026-11-27T04:27:00Z`
**Evidence Expiry Date (UTC):** `2026-12-11` (14-day window per H-P3-05)
**Linked RC Evidence Tracker:** [#1909](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1909)
**Linked Promotion / Baseline Record:** [`staging-operating-baseline-2026-11-26.md`](staging-operating-baseline-2026-11-26.md)
`sod_waiver: single-maintainer-repository-mohavro`

## Named Operational Role Ownership

Per [Enterprise Deployment Operating Model — Operator Responsibilities](../enterprise-deployment-operating-model.md#operator-responsibilities)
and [Enterprise Release Checklist — Governance Gate](../release-checklist.md#8-governance-gate), each operational
responsibility is explicitly assigned and signed off for commit `bf6244691`:

| Operational Role | Named Owner | Sign-Off Status | Date (UTC) | Scope & Responsibility |
| --- | --- | --- | --- | --- |
| **Deploy operator** | `mohavro` | Approved | `2026-11-27` | Executes Vercel frontend/API deployments and post-deploy verification |
| **Promotion approver** | `mohavro` | Approved | `2026-11-27` | Reviews SHA-bound evidence and links RC evidence issue `#1909` to promotion records |
| **Rollback executor** | `mohavro` | Approved | `2026-11-27` | Executes deployment rollback to prior known-good Vercel release if post-deploy checks fail |
| **Backup Operator** | `mohavro` | Approved | `2026-11-27` | Maintains scheduled Supabase logical/PITR backups and verifies backup integrity |
| **Restore Operator** | `mohavro` | Approved | `2026-11-27` | Executes `docs/runbooks/backup-restore-dr.md`, H-P0-02 cleanup, and H-P2-05 skew checks |
| **Secret/config maintainer** | `mohavro` | Approved | `2026-11-27` | Manages GCP Secret Manager, Vercel env vars, and GitHub Environment secrets |
| **Persistence-verification operator** | `mohavro` | Approved | `2026-11-27` | Runs `scripts/check_hosted_readiness.py --require-persistence` and sentinel checks |
| **Incident Commander** | `mohavro` | Approved | `2026-11-27` | Coordinates incident response, DR failover decisions, and post-incident follow-ups |

## Non-Negotiable Boundary Attestation

- **SHA-bound:** This sign-off applies exclusively to repository commit `bf6244691` and is **not inherited**
  by any later release candidate.
- **No gate waivers:** This sign-off satisfies governance ownership (item 8 / #1914) only. It does **not**
  waive any manual-evidence or automated CI gate (`#1909`, `#1912`, `#1913`, `#1915`), which remain gated on
  their respective GitHub Actions workflow artifacts once billing is restored.
- **Single-maintainer SoD disclosure:** `mohavro` is the sole repository maintainer; each responsibility is
  explicitly enumerated above with `sod_waiver: single-maintainer-repository-mohavro` recorded per H-P3-05.
