# ADR 0012: Multi-Region and Advanced Hosting Strategy

For the broader enterprise-readiness audit and rollout plan, see
[docs/enterprise-readiness-index.md](../enterprise-readiness-index.md).

## Status

Accepted (Strategy & Architecture — No Multi-Region Infrastructure Deployed Yet)

## Date

2026-11-27

## Tracking Issue

- GitHub Issue #1920 (Enterprise Readiness Completion Checklist item 14)

## Context

FarDb's production architecture (ADR 0001, ADR 0002, ADR 0004, ADR 0005) currently operates in a
**single-region durable topology**:

- **Frontend & API Compute:** Vercel (Next.js frontend + slimmed `@vercel/python` FastAPI backend, H-P3-04).
- **Durable Persistence:** Hosted Supabase PostgreSQL (`combined` profile with three restricted runtime
  roles: `fardb_login_auth`, `fardb_login_graph`, `fardb_login_coordination`), protected by ADR 0007
  deny-by-default authorization, H-P2-01..05 rebuild/fencing/skew controls, and H-P3-01..05 runtime
  security controls.
- **Measured Single-Region Baselines:**
  - Scratch PostgreSQL 18 DR restore rehearsal (`2026-11-27`, #1913): total measured RTO **`2.34 s`**
    (`0.69 s` restore + `1.65 s` FastAPI restart to `READY`), RPO = point-in-time snapshot (`0` data loss).
  - Deterministic PostgreSQL 18 scale baseline (`2026-11-27`, #1918): `10,000` assets / `50,000` directed
    relationships persisted in `21.881 s`, reloaded in `1.614 s`, `25/25` distributed lock refreshes
    (median `3.986 ms`).

Before any future expansion to multi-region hosting, FarDb requires an explicit decision record defining
the target multi-region topology, provider/cost trade-offs, RPO/RTO implications, and how the
**single-writer rebuild invariant** (ADR 0004) holds across regions.

## Decision

When multi-region resilience is funded and scheduled as a future infrastructure initiative, FarDb will adopt
an **Active-Passive Single-Writer Primary Region + Multi-Region Read Serving** topology.

**Active-Active multi-writer across regions is explicitly rejected.**

### 1. Preservation of Single-Writer Rebuild Semantics

- Every graph persistence boundary (`ASSET_GRAPH_DATABASE_URL`) has **at most one authoritative primary
  region** at any point in time.
- The coordination boundary (`COORDINATION_DATABASE_URL`, `distributed_locks`) **must remain co-located
  with the authoritative primary region** (or on a strongly consistent single-primary store) so that
  distributed lock acquisition, monotonic fencing tokens (H-P2-02), and the partial unique index
  `uq_rebuild_jobs_single_running` (H-P2-03) remain linearizable.
- Secondary-region compute instances may serve read-only traffic from local runtime snapshots or regional
  PostgreSQL read replicas, but **must never execute graph rebuild writes** against a read replica
  (`_validate_coordination_database_primary` already fails closed against read replicas).

### 2. Multi-Region Topology Tiers, RPO/RTO & Provider Cost Model

| Tier | Topology | Provider Components (Vercel + Supabase / GCP) | Target RPO | Target RTO | Estimated Monthly Cost (USD) | Status |
| --- | --- | --- | --- | --- | --- | --- |
| **Tier 0 (Current)** | Single-region primary + scheduled logical backups | Vercel Pro ($20/seat) + Supabase Pro ($25 base + compute) + GCP Secret Manager (<$1) | `<= 24 h` (or `<= 5 min` with PITR add-on) | `<= 30 min` (cold restore; scratch measured `2.34 s`) | ~$45–$100 / mo | Active |
| **Tier 1 (Recommended Next)** | Single-region primary + Supabase PITR + cross-region encrypted backup replication | Tier 0 + Supabase PITR add-on ($100/mo) + cross-region GCS/S3 encrypted backup bucket (<$5/mo) | `<= 5 min` | `<= 15–30 min` (regional rebuild/restore) | ~$150–$220 / mo | Planned |
| **Tier 2 (Warm Standby + Multi-Region Reads)** | Active-Passive: Primary PostgreSQL + Cross-Region Read Replica + Vercel multi-region read functions | Tier 1 + Supabase Cross-Region Read Replica ($100–$200/mo) + Upstash/Redis global rate-limit store (H-P3-02, ~$10–$30/mo) | `<= 1 min` (async replication lag) | `<= 5–10 min` (replica promotion + secret/DNS cutover) | ~$270–$450 / mo | Future / On-Demand |
| **Tier 3 (Rejected)** | Active-Active multi-writer | Distributed SQL (CockroachDB/Spanner) + global consensus | `~0` | `< 1 min` | $1,000+ / mo | **Rejected** (violates single-writer simplicity & cost envelope) |

### 3. Regional Failover Protocol (Tier 1 / Tier 2)

1. **Freeze writers:** Confirm primary region is unreachable or revoke primary rebuild operator traffic.
2. **Promote / Restore target region:** Promote the cross-region read replica (Tier 2) or restore the
   latest cross-region PITR/logical backup into a new primary region (Tier 1).
3. **Mandatory post-recovery gates (H-P0-02, H-P2-05):**
   - Execute table-scoped cleanup (`distributed_locks` cleared, in-flight `rebuild_jobs` marked failed,
     confirming `running = 0`).
   - Run `python scripts/check_restore_boundary_skew.py` to confirm zero Graph vs. Coordination skew.
   - Run `python scripts/check_database_authorization.py` to confirm ADR 0007 deny-by-default parity.
4. **Cutover & Smoke (H-P1-03):**
   - Update `DATABASE_URL`, `ASSET_GRAPH_DATABASE_URL`, and `COORDINATION_DATABASE_URL` in Vercel and
     GCP Secret Manager to the promoted primary region.
   - Redeploy / restart FastAPI instances and execute
     `python scripts/check_hosted_readiness.py <base_url> --require-persistence --assets-smoke`.
   - Record failover evidence via `post-recovery-readiness.yml` (`recovery_context=post-restore`).

## Non-Negotiable Boundaries

- **No premature multi-region claim:** Accepting this ADR documents the approved architecture and cost
  model only. FarDb remains a **single-region** service until Tier 1/Tier 2 infrastructure is provisioned
  and a live regional failover rehearsal is recorded.
- **No infrastructure changes in this ADR:** Provisioning read replicas, cross-region buckets, or shared
  Redis stores is deferred to dedicated implementation issues.
- **Single-writer invariant preserved:** One rebuild writer per graph persistence boundary remains
  mandatory across all tiers.
