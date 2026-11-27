# Dense-Subgraph & Multi-Worker Lock Contention Baseline — 2026-11-27

**Evidence ID:** `FARDB-CAPACITY-CONTENTION-2026-11-27-01`
**Track:** Track 1 (PR 1B) — Capacity & Operating Envelope
**Classification:** Advisory deterministic local SQLite regression baseline (not a production hardware SLO)
**Captured (UTC):** `2026-11-27T19:17:00Z`
**Generator:** `python -m scripts.benchmark_capacity_envelope`

## 1. Dense-Subgraph & Scaling Measurements (`topology=dense_hub`)

| Tier | Assets / Edges | Hubs / Max Out-Degree | Build | Save | Load | Metrics | Query p50 / p95 / max | Peak `tracemalloc` | Max RSS |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| `1K-HUB` | `1,000 / 5,000` | `25 / 999` | `0.2454 s` | `0.5676 s` | `0.5030 s` | `0.0167 s` | `0.232 / 0.405 / 0.411 ms` | `12.2 MiB` | `105.9 MiB` |
| `5K-HUB` | `5,000 / 25,000` | `25 / 4,999` | `4.1371 s` | `2.6672 s` | `5.3577 s` | `0.0525 s` | `3.377 / 6.495 / 8.182 ms` | `53.0 MiB` | `199.8 MiB` |

*Exact round-trip integrity verified (`loaded_asset_count == asset_count` and `loaded_relationship_count == relationship_count`) on every tier.*

## 2. Multi-Worker Distributed Lock Contention (`workers=8, iterations=15`)

| Metric | Observed Result |
| --- | ---: |
| Concurrent workers × attempts | `8 × 15 = 120` |
| Successful lock acquisitions | `33` |
| Fail-closed contention rejections | `87` |
| Fencing-token monotonicity / verification violations | **`0`** |
| Acquire latency p50 / p95 / max | `7.765 ms` / `117.102 ms` / `555.600 ms` |
| Total elapsed time | `0.6892 s` |

## 3. Scope & Non-Negotiable Boundary

- Captured on Linux x86_64, Python 3.14.4 using isolated local SQLite (file-backed per-thread connections for contention mode, in-memory for capacity mode).
- Complements the PostgreSQL 18.6 `SCALE10K` baseline in [production-scale-pg18-baseline-2026-11-27.md](production-scale-pg18-baseline-2026-11-27.md).
- Does **not** claim million-node production certification; provides a reproducible local harness (`scripts/benchmark_capacity_envelope.py`) that also accepts `--database-url <postgres_url>` for hosted/disposable PostgreSQL runs.
