# Graph Scale, Topology Bounds & Operating Envelope

**Date:** 2026-11-28
**Baseline:** `main@0628082eb` + PR `#2023` (`max_sector_peers` bounded sector-hub mode)
**Classification:** Measured operating bounds and topology complexity reference (local SQLite + FastAPI TestClient + PostgreSQL 18.6 reference)

## 1. Graph Minimums, Maximums & Topology Formulas

Let $N$ be total assets, $S$ be meaningful sectors (`sector != "Unknown"`), $n_s$ be assets in sector $s$, $B$ be bonds with a valid `issuer_id`, and $K$ be `max_sector_peers`.

| Dimension                           | Minimum                                                      | Unbounded Default (`max_sector_peers=None`)                  | Bounded Sector-Hub (`max_sector_peers=K`)                                                        | Notes                                                                                                            |
| ----------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| **Nodes ($N$)**                     | `0` (empty graph returns 1 placeholder node in 3D layout)    | Practically bounded to **$\le 500$ assets** per dense sector | Tested up to **$5,578$ live equities** (and **$10,000$–$50,000$** synthetic nodes)               | `AssetRelationshipGraph` accepts any finite non-negative count                                                   |
| **`same_sector` directed edges**    | `0` (when $n_s \le 1$ or `sector == "Unknown"`)              | $\sum_{s} n_s(n_s - 1)$ — **$O(N^2)$ clique**                | $\sum_{s} \big(n_s \cdot \min(K, n_s - 1) - \text{self}\big) \le N \cdot K$ — **$O(N \cdot K)$** | On 5,578 live US equities across 11 sectors: **4,076,540** unbounded vs **55,670** at $K=10$ (**73× reduction**) |
| **`corporate_link` directed edges** | `0`                                                          | $\le B$ (1 per bond with valid `issuer_id`)                  | $\le B$ ($O(N)$ pass)                                                                            | Unidirectional `bond -> issuer`                                                                                  |
| **Relationship strength**           | `-1.0`                                                       | `[-1.0, 1.0]` enforced at init & append                      | `[-1.0, 1.0]` enforced at init & append                                                          | `same_sector_strength` default `0.7`; `corporate_bond_strength` default `0.9`                                    |
| **`max_sector_peers` ($K$)**        | `1` (when set; `0`, negative, or `bool` raises `ValueError`) | `None` (all-pairs)                                           | Integer $\ge 1$ (`MAX_SECTOR_PEERS` env var)                                                     | Recommended $K \in [5, 25]$ for $N > 500$                                                                        |
| **API `/api/assets` page size**     | `limit=1`                                                    | Paginated (`limit`, `offset`)                                | Paginated (`limit`, `offset`)                                                                    | Sub-4 ms p50 at $N = 5,578$                                                                                      |
| **Frontend rendering caps**         | `1`                                                          | `NEXT_PUBLIC_MAX_NODES` / `NEXT_PUBLIC_MAX_EDGES`            | `NEXT_PUBLIC_MAX_NODES` / `NEXT_PUBLIC_MAX_EDGES`                                                | Client-side Plotly cap; `/api/visualization` returns full graph unless capped server-side                        |

## 2. Measured Scaling Curves (Live Market Dataset — 5,578 US Equities)

Measured on Linux x86_64, Python 3.14.4, SQLite (`AssetGraphRepository.save_graph()` / `load_graph()`), 11 live sectors (`Financial: 1,098`, `Healthcare: 1,054`, `Technology: 800`, `Industrials: 715`, `Consumer Cyclical: 520`, `Basic Materials: 298`, `Communication Services: 252`, `Energy: 252`, `Real Estate: 244`, `Consumer Defensive: 240`, `Utilities: 105`):

| Tier                         | Topology                    | Assets ($N$) | Directed Edges ($E$) | Build Edges | SQLite Save | SQLite Load |  Metrics | Peak `tracemalloc` | Exact Round-Trip |
| ---------------------------- | --------------------------- | -----------: | -------------------: | ----------: | ----------: | ----------: | -------: | -----------------: | :--------------: |
| `LIVE-250-CANONICAL`         | All-pairs ($K=\text{None}$) |        `250` |              `7,896` |    `0.035s` |    `0.305s` |    `0.231s` | `0.012s` |         `15.6 MiB` |       Yes        |
| `LIVE-500-CANONICAL`         | All-pairs ($K=\text{None}$) |        `500` |             `29,386` |    `0.159s` |    `0.723s` |    `0.821s` | `0.038s` |         `50.9 MiB` |       Yes        |
| `LIVE-1000-BOUNDED-K10`      | Sector-hub ($K=10$)         |      `1,000` |              `9,890` |    `0.031s` |    `0.400s` |    `0.253s` | `0.017s` |         `17.8 MiB` |       Yes        |
| `LIVE-FULL-5578-BOUNDED-K10` | Sector-hub ($K=10$)         |      `5,578` |             `55,670` |    `0.182s` |    `2.259s` |    `1.790s` | `0.093s` |        `100.4 MiB` |       Yes        |

### Empirical Scaling as a Function of $N$ and $E$

- **Unbounded all-pairs ($K=\text{None}$):** Edge count scales quadratically with sector size ($E \approx \frac{N^2}{S}$). Doubling $N$ from `250 -> 500` increased $E$ by **3.72×** (`7,896 -> 29,386`) and peak memory by **3.26×** (`15.6 -> 50.9 MiB`). At $N = 5,578$, $E = 4,076,540$, which exceeds practical interactive memory/payload budgets.
- **Bounded sector-hub ($K=10$):** Edge count, persistence latency, and memory scale linearly with $E \approx N \cdot K$:
  - `save_s` $\approx 40\ \mu\text{s/edge}$ (`2.26s` for `55,670` edges)
  - `load_s` $\approx 32\ \mu\text{s/edge}$ (`1.79s` for `55,670` edges)
  - `peak_tracemalloc` $\approx 1.8\ \text{KiB/edge}$ (`100.4 MiB` for `55,670` edges)

## 3. Measured FastAPI Endpoint Envelope at $N = 5,578, E = 55,670$

Measured over 10 sequential requests per route against the in-memory runtime graph (`create_app()` + `synchronize_runtime_graph()`):

| Endpoint                                               | HTTP  |     Payload |         p50 |         p95 |         max | Operating Guidance                                                                                                        |
| ------------------------------------------------------ | :---: | ----------: | ----------: | ----------: | ----------: | ------------------------------------------------------------------------------------------------------------------------- |
| `GET /api/assets?limit=50&offset=0`                    | `200` |  `14.7 KiB` |   `3.83 ms` |  `41.95 ms` |  `41.95 ms` | Safe at $N \ge 5,578$                                                                                                     |
| `GET /api/assets?sector=Technology&limit=100&offset=0` | `200` |  `14.5 KiB` |   `3.55 ms` |   `3.86 ms` |   `3.86 ms` | Safe at $N \ge 5,578$                                                                                                     |
| `GET /api/assets/AAPL`                                 | `200` |  `0.35 KiB` |   `2.70 ms` |   `2.96 ms` |   `2.96 ms` | $O(1)$ lookup                                                                                                             |
| `GET /api/metrics`                                     | `200` |  `16.4 KiB` |   `4.12 ms` |   `5.14 ms` |   `5.14 ms` | Safe at $E = 55,670$                                                                                                      |
| `GET /api/relationships?limit=100&offset=0`            | `200` | `4,771 KiB` | `161.19 ms` | `171.80 ms` | `171.80 ms` | **Caution:** currently returns full edge list (~4.8 MB at 55.7k edges); enforce pagination before $E > 100\text{k}$       |
| `GET /api/visualization`                               | `200` | `9,833 KiB` | `517.11 ms` | `556.39 ms` | `556.39 ms` | **Caution:** ~9.8 MB JSON at 5.6k nodes / 55.7k edges; use sector filtering or server-side node/edge caps for browser UIs |

## 4. Recommended Operating Guardrails

1. **Always set `MAX_SECTOR_PEERS` (e.g., `10`–`20`) when $N > 500$** so `build_relationships()` stays $O(N \cdot K)$ instead of $O(N^2)$.
2. **Keep single-snapshot edge counts $E \le 100,000$** for interactive FastAPI + SQLite/single-node PostgreSQL responsiveness until `/api/relationships` and `/api/visualization` enforce server-side pagination/truncation caps.
3. **Reference baselines:**
   - Local dense-hub & lock contention: [capacity-envelope-baseline-2026-11-27.md](capacity-envelope-baseline-2026-11-27.md)
   - PostgreSQL 18.6 `10k`/`50k` baseline: [production-scale-pg18-baseline-2026-11-27.md](production-scale-pg18-baseline-2026-11-27.md)
