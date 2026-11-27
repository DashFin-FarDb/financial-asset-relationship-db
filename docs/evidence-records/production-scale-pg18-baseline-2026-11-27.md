# PostgreSQL 18 Deterministic Scale Validation Baseline — 2026-11-27

**Evidence ID:** `FARDB-SCALE-PG18-2026-11-27-01`
**Gate:** Enterprise readiness item 12 — production-scale validation (Issue #1918)
**Classification:** Advisory deterministic PostgreSQL 18 regression baseline (not an SLO; not added to normal CI)
**Exact Repository Commit SHA:** `4f59a28ed` (`main`)
**Captured (UTC):** `2026-11-27T04:25:00Z`
**Operator:** `mohavro`

## 1. Agreed Deterministic Dataset & Advisory Performance Budget

Per [Operational Drill and Scale-Validation Pack](../testing/operational-drill-and-scale-validation-pack.md#scale-validation-guidance),
this record establishes the deterministic PostgreSQL scale dataset and advisory regression budget outside normal CI:

- **Deterministic generator:** `tests.helpers.graph_scale_factory.build_scale_graph(asset_count=10_000, relationship_count=50_000, prefix="SCALE10K")`
- **Graph size:** `10,000` assets / `50,000` directed relationships (10x the repository's `1,000 / 5,000` upper-representative CI fixture)
- **Target database schema:** Full committed `combined` Supabase PostgreSQL ledger (`supabase/ledger-profiles.json`, including `20261127030000_enforce_single_running_rebuild_job.sql`)
- **Advisory Regression Budget (non-SLO, manual/scheduled runs only):**
  - Graph construction: `<= 5.0 s`
  - PostgreSQL snapshot persistence (`AssetGraphRepository.save_graph`): `<= 60.0 s`
  - PostgreSQL persistence load (`AssetGraphRepository.load_graph`): `<= 10.0 s`
  - Distributed lock refresh (`25` consecutive cycles): `25 / 25` succeeded, max latency `<= 250 ms`
  - Peak Python allocation (`tracemalloc`): `<= 512 MiB`
  - Process RSS (`ru_maxrss`): `<= 1,024 MiB`

## 2. Environment & Target

- **Environment:** Linux x86_64, Python 3.14.4, disposable isolated local `PostgreSQL 18.6 (Ubuntu 18.6-0ubuntu0.26.04.1)` loopback cluster (torn down immediately after capture; zero production mutation).
- **Result classification:** **Advisory — Passed** (all measurements well within the agreed advisory regression budget).

## 3. Observed Measurements

| Measurement | Observed Result | Advisory Budget | Status |
| --- | ---: | ---: | --- |
| Graph construction (`SCALE10K`, 10k / 50k) | `0.607 s` | `<= 5.0 s` | Within budget |
| PostgreSQL 18 snapshot persistence (`save_graph`) | `21.881 s` | `<= 60.0 s` | Within budget |
| PostgreSQL 18 persistence load (`load_graph`) | `1.614 s` | `<= 10.0 s` | Within budget |
| Loaded assets / directed relationships | `10,000 / 50,000` | Exact match | Exact match |
| Distributed lock refreshes (`graph_rebuild`) | `25 / 25` succeeded | `25 / 25` | Passed |
| Lock refresh median / max latency | `3.986 ms` / `6.924 ms` | `<= 250 ms` | Within budget |
| PostgreSQL database size (`pg_database_size`) | `22,288,063 bytes` (`21.3 MiB`) | — | Recorded |
| Peak traced Python allocation (`tracemalloc`) | `176,657,936 bytes` (`168.5 MiB`) | `<= 512 MiB` | Within budget |
| Process max RSS (`ru_maxrss`) | `439,964 KiB` (`429.7 MiB`) | `<= 1,024 MiB` | Within budget |

## 4. Non-Negotiable Boundary & Limits

- Not added to normal PR CI.
- Timing figures are advisory regression baselines on disposable local PostgreSQL 18, not production hardware SLOs.
- Supersedes the un-bound SHA limitation from [`production-scale-local-baseline-2026-11-19.md`](production-scale-local-baseline-2026-11-19.md) by providing an exact-SHA (`4f59a28ed`) PostgreSQL 18 asset-graph + distributed-lock persistence baseline.
