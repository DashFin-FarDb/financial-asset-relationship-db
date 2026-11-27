"""Deterministic capacity and dense-subgraph benchmark harness for FarDB.

Measures graph construction, durable repository persistence (save/load),
metrics computation, dense-subgraph / paginated query latency, and peak memory
across uniform and hub-dense topologies. Supports SQLite (default in-memory)
and PostgreSQL URLs via ``--database-url``.
"""

from __future__ import annotations

import argparse
import json
import resource
import statistics
import tempfile
import threading
import time
import tracemalloc
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from src.data.database import create_engine_from_url, create_session_factory, init_db
from src.data.repository import AssetGraphRepository, CoordinationLockRepository
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity

Topology = Literal["uniform", "dense_hub"]


@dataclass(frozen=True, slots=True)
class CapacityBenchmarkResult:
    """Structured output of a single deterministic capacity benchmark run."""

    topology: Topology
    asset_count: int
    relationship_count: int
    loaded_asset_count: int
    loaded_relationship_count: int
    hub_count: int
    max_out_degree: int
    build_seconds: float
    save_seconds: float
    load_seconds: float
    metrics_seconds: float
    query_p50_ms: float
    query_p95_ms: float
    query_max_ms: float
    peak_tracemalloc_bytes: int
    max_rss_kib: int


def _asset_id(prefix: str, index: int) -> str:
    """Return a deterministic asset identifier."""
    return f"{prefix}_ASSET_{index:06d}"


def _uniform_pairs(asset_count: int) -> Iterator[tuple[int, int]]:
    """Yield unique directed non-self pairs with uniform out-degree."""
    for offset in range(1, asset_count):
        for source in range(asset_count):
            yield source, (source + offset) % asset_count


def _dense_hub_pairs(asset_count: int, hub_count: int) -> Iterator[tuple[int, int]]:
    """Yield unique directed pairs concentrated heavily on high-centrality hubs."""
    emitted: set[tuple[int, int]] = set()
    # First saturate hub-to-spoke and spoke-to-hub edges to form dense subgraphs.
    for hub in range(hub_count):
        for target in range(asset_count):
            if hub == target:
                continue
            pair = (hub, target)
            if pair not in emitted:
                emitted.add(pair)
                yield pair
    for hub in range(hub_count):
        for source in range(hub_count, asset_count):
            pair = (source, hub)
            if pair not in emitted:
                emitted.add(pair)
                yield pair
    # Fill any remaining budget deterministically across non-hub nodes.
    for pair in _uniform_pairs(asset_count):
        if pair not in emitted:
            emitted.add(pair)
            yield pair


def build_benchmark_graph(
    *,
    asset_count: int,
    relationship_count: int,
    topology: Topology = "dense_hub",
    prefix: str = "BENCH",
) -> tuple[AssetRelationshipGraph, int]:
    """Build a deterministic graph for capacity and dense-subgraph benchmarking."""
    if asset_count < 2:
        raise ValueError("asset_count must be at least 2")
    max_edges = asset_count * (asset_count - 1)
    if relationship_count < 0 or relationship_count > max_edges:
        raise ValueError(f"relationship_count must be between 0 and {max_edges}")

    graph = AssetRelationshipGraph()
    sectors = ("Technology", "Finance", "Healthcare", "Energy", "Industrials")
    for idx in range(asset_count):
        graph.add_asset(
            Equity(
                id=_asset_id(prefix, idx),
                symbol=f"{prefix}{idx}",
                name=f"{prefix} Equity {idx}",
                asset_class=AssetClass.EQUITY,
                sector=sectors[idx % len(sectors)],
                price=100.0 + (idx % 500),
            )
        )

    hub_count = max(1, min(asset_count // 20, 25)) if topology == "dense_hub" else 0
    pair_iter = _dense_hub_pairs(asset_count, hub_count) if topology == "dense_hub" else _uniform_pairs(asset_count)
    rel_type = "dense_hub_link" if topology == "dense_hub" else "uniform_scale_link"

    for edge_idx, (src, dst) in enumerate(pair_iter):
        if edge_idx == relationship_count:
            break
        strength = round(((edge_idx % 99) + 1) / 100.0, 2)
        graph.add_relationship(
            _asset_id(prefix, src),
            _asset_id(prefix, dst),
            rel_type,
            strength,
            bidirectional=False,
        )

    return graph, hub_count


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Return the nearest-rank percentile from a non-empty sorted list."""
    if not sorted_values:
        return 0.0
    rank = max(0, min(len(sorted_values) - 1, int(round((pct / 100.0) * (len(sorted_values) - 1)))))
    return sorted_values[rank]


def _measure_subgraph_and_pagination_queries(
    graph: AssetRelationshipGraph,
    *,
    iterations: int = 20,
    page_size: int = 50,
) -> tuple[float, float, float]:
    """Measure dense-hub neighbor extraction and paginated asset slicing latencies in ms."""
    asset_ids = sorted(graph.assets.keys())
    hub_id = max(asset_ids, key=lambda aid: len(graph.relationships.get(aid, ())))
    samples_ms: list[float] = []

    for i in range(max(1, iterations)):
        start = time.perf_counter()
        # Simulate dense-hub neighborhood extraction + paginated page slice.
        hub_edges = list(graph.relationships.get(hub_id, ()))
        neighbor_ids = {target_id for target_id, _, _ in hub_edges}
        _ = [graph.assets[nid] for nid in neighbor_ids if nid in graph.assets]
        offset = (i * page_size) % max(1, len(asset_ids))
        _ = [graph.assets[aid] for aid in asset_ids[offset : offset + page_size]]
        samples_ms.append((time.perf_counter() - start) * 1000.0)

    samples_ms.sort()
    p50 = statistics.median(samples_ms)
    p95 = _percentile(samples_ms, 95.0)
    return round(p50, 4), round(p95, 4), round(samples_ms[-1], 4)


def run_capacity_benchmark(
    *,
    asset_count: int,
    relationship_count: int,
    topology: Topology = "dense_hub",
    database_url: str = "sqlite:///:memory:",
    query_iterations: int = 20,
) -> CapacityBenchmarkResult:
    """Execute one deterministic capacity & dense-subgraph benchmark run."""
    tracemalloc.start()
    try:
        t0 = time.perf_counter()
        graph, hub_count = build_benchmark_graph(
            asset_count=asset_count,
            relationship_count=relationship_count,
            topology=topology,
        )
        build_seconds = time.perf_counter() - t0

        engine = create_engine_from_url(database_url)
        try:
            if database_url.startswith("sqlite"):
                init_db(engine)
            session_factory = create_session_factory(engine)

            with session_factory() as session:
                repo = AssetGraphRepository(session)
                t_save = time.perf_counter()
                repo.save_graph(graph)
                session.commit()
                save_seconds = time.perf_counter() - t_save

            with session_factory() as session:
                repo = AssetGraphRepository(session)
                t_load = time.perf_counter()
                loaded_graph = repo.load_graph()
                load_seconds = time.perf_counter() - t_load
        finally:
            engine.dispose()

        t_metrics = time.perf_counter()
        loaded_graph.calculate_metrics()
        metrics_seconds = time.perf_counter() - t_metrics

        p50_ms, p95_ms, max_ms = _measure_subgraph_and_pagination_queries(
            loaded_graph,
            iterations=query_iterations,
        )
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    loaded_edges = sum(len(edges) for edges in loaded_graph.relationships.values())
    max_out_degree = max((len(edges) for edges in loaded_graph.relationships.values()), default=0)
    max_rss_kib = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)

    return CapacityBenchmarkResult(
        topology=topology,
        asset_count=asset_count,
        relationship_count=relationship_count,
        loaded_asset_count=len(loaded_graph.assets),
        loaded_relationship_count=loaded_edges,
        hub_count=hub_count,
        max_out_degree=max_out_degree,
        build_seconds=round(build_seconds, 4),
        save_seconds=round(save_seconds, 4),
        load_seconds=round(load_seconds, 4),
        metrics_seconds=round(metrics_seconds, 4),
        query_p50_ms=p50_ms,
        query_p95_ms=p95_ms,
        query_max_ms=max_ms,
        peak_tracemalloc_bytes=int(peak_bytes),
        max_rss_kib=max_rss_kib,
    )


@dataclass(frozen=True, slots=True)
class LockContentionResult:
    """Structured output of a multi-worker distributed lock contention benchmark."""

    workers: int
    iterations_per_worker: int
    total_attempts: int
    acquisitions: int
    contention_rejections: int
    fencing_token_violations: int
    acquire_p50_ms: float
    acquire_p95_ms: float
    acquire_max_ms: float
    elapsed_seconds: float


def run_lock_contention_benchmark(
    *,
    workers: int = 4,
    iterations_per_worker: int = 10,
    database_url: str = "sqlite:///:memory:",
    ttl_seconds: int = 30,
) -> LockContentionResult:
    """Measure multi-worker distributed lock contention and fencing-token monotonicity."""
    if workers < 1:
        raise ValueError("workers must be at least 1")
    if iterations_per_worker < 1:
        raise ValueError("iterations_per_worker must be at least 1")

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    effective_url = database_url
    if database_url == "sqlite:///:memory:":
        # In-memory SQLite shares one StaticPool connection across threads; use a temp file
        # so each worker thread gets an independent DBAPI connection for realistic contention.
        temp_dir = tempfile.TemporaryDirectory(prefix="fardb-lock-bench-")
        effective_url = f"sqlite:///{Path(temp_dir.name) / 'contention.db'}"

    engine = create_engine_from_url(effective_url)
    try:
        if effective_url.startswith("sqlite"):
            init_db(engine)
        session_factory = create_session_factory(engine)
        guard = threading.Lock()
        latencies_ms: list[float] = []
        acquisitions = 0
        contention_rejections = 0
        fencing_violations = 0

        def _worker(worker_idx: int) -> None:
            nonlocal acquisitions, contention_rejections, fencing_violations
            holder_id = f"bench-worker-{worker_idx}"
            for _ in range(iterations_per_worker):
                start = time.perf_counter()
                try:
                    with session_factory() as session:
                        repo = CoordinationLockRepository(session)
                        res = repo.acquire_lock(
                            lock_name="graph_rebuild",
                            holder_id=holder_id,
                            ttl_seconds=ttl_seconds,
                        )
                        session.commit()
                        elapsed_ms = (time.perf_counter() - start) * 1000.0

                        if res.success:
                            refreshed = repo.refresh_lock(
                                lock_name="graph_rebuild",
                                holder_id=holder_id,
                                ttl_seconds=ttl_seconds,
                            )
                            session.commit()
                            valid = repo.verify_fencing_token(
                                lock_name="graph_rebuild",
                                holder_id=holder_id,
                                expected_fencing_token=refreshed.fencing_token,
                            )
                            repo.release_lock(lock_name="graph_rebuild", holder_id=holder_id)
                            session.commit()
                            with guard:
                                latencies_ms.append(elapsed_ms)
                                acquisitions += 1
                                if not valid or refreshed.fencing_token <= res.fencing_token:
                                    fencing_violations += 1
                        else:
                            with guard:
                                latencies_ms.append(elapsed_ms)
                                contention_rejections += 1
                except Exception:
                    # Under SQLite write-lock contention, transient OperationalError counts as contention.
                    elapsed_ms = (time.perf_counter() - start) * 1000.0
                    with guard:
                        latencies_ms.append(elapsed_ms)
                        contention_rejections += 1

        t_start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_worker, idx) for idx in range(workers)]
            for future in futures:
                future.result()
        elapsed_seconds = time.perf_counter() - t_start
    finally:
        engine.dispose()
        if temp_dir is not None:
            temp_dir.cleanup()

    latencies_ms.sort()
    p50 = statistics.median(latencies_ms) if latencies_ms else 0.0
    p95 = _percentile(latencies_ms, 95.0)
    max_ms = latencies_ms[-1] if latencies_ms else 0.0

    return LockContentionResult(
        workers=workers,
        iterations_per_worker=iterations_per_worker,
        total_attempts=workers * iterations_per_worker,
        acquisitions=acquisitions,
        contention_rejections=contention_rejections,
        fencing_token_violations=fencing_violations,
        acquire_p50_ms=round(p50, 4),
        acquire_p95_ms=round(p95, 4),
        acquire_max_ms=round(max_ms, 4),
        elapsed_seconds=round(elapsed_seconds, 4),
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for deterministic capacity and lock-contention benchmarks."""
    parser = argparse.ArgumentParser(description="Run FarDB deterministic capacity & lock-contention benchmarks.")
    parser.add_argument(
        "--mode",
        choices=("capacity", "contention"),
        default="capacity",
        help="Benchmark mode: graph capacity or multi-worker lock contention",
    )
    parser.add_argument("--assets", type=int, default=1000, help="Number of synthetic assets (>= 2)")
    parser.add_argument("--relationships", type=int, default=5000, help="Number of directed relationships")
    parser.add_argument(
        "--topology",
        choices=("uniform", "dense_hub"),
        default="dense_hub",
        help="Graph topology to benchmark",
    )
    parser.add_argument(
        "--database-url",
        default="sqlite:///:memory:",
        help="SQLAlchemy database URL (defaults to in-memory SQLite)",
    )
    parser.add_argument("--query-iterations", type=int, default=20, help="Subgraph/pagination query iterations")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent workers for contention mode")
    parser.add_argument("--iterations", type=int, default=10, help="Lock attempts per worker in contention mode")
    parser.add_argument("--json-out", type=Path, default=None, help="Optional path to write JSON report")
    args = parser.parse_args(argv)

    result: CapacityBenchmarkResult | LockContentionResult
    if args.mode == "contention":
        result = run_lock_contention_benchmark(
            workers=args.workers,
            iterations_per_worker=args.iterations,
            database_url=args.database_url,
        )
    else:
        result = run_capacity_benchmark(
            asset_count=args.assets,
            relationship_count=args.relationships,
            topology=args.topology,
            database_url=args.database_url,
            query_iterations=args.query_iterations,
        )
    payload = json.dumps(asdict(result), indent=2)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
