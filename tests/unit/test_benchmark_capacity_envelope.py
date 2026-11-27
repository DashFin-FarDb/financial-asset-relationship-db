"""Unit tests for the deterministic capacity and dense-subgraph benchmark harness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.benchmark_capacity_envelope import (
    build_benchmark_graph,
    main,
    run_capacity_benchmark,
    run_lock_contention_benchmark,
)


def test_build_benchmark_graph_dense_hub_creates_high_centrality_hub() -> None:
    """Dense-hub topology concentrates out-degree on hub assets."""
    graph, hub_count = build_benchmark_graph(asset_count=40, relationship_count=120, topology="dense_hub")
    assert hub_count >= 1
    assert len(graph.assets) == 40
    total_edges = sum(len(edges) for edges in graph.relationships.values())
    assert total_edges == 120
    max_degree = max(len(edges) for edges in graph.relationships.values())
    assert max_degree >= 39


def test_build_benchmark_graph_rejects_invalid_dimensions() -> None:
    """Invalid node or edge counts fail fast with ValueError."""
    with pytest.raises(ValueError, match="at least 2"):
        build_benchmark_graph(asset_count=1, relationship_count=0)
    with pytest.raises(ValueError, match="between 0 and"):
        build_benchmark_graph(asset_count=4, relationship_count=99)


@pytest.mark.parametrize("topology", ["uniform", "dense_hub"])
def test_run_capacity_benchmark_round_trips_graph_and_metrics(topology: str) -> None:
    """Benchmark round-trips exact node/edge counts and returns ordered latency percentiles."""
    result = run_capacity_benchmark(
        asset_count=30,
        relationship_count=90,
        topology=topology,  # type: ignore[arg-type]
        query_iterations=10,
    )
    assert result.loaded_asset_count == 30
    assert result.loaded_relationship_count == 90
    assert result.build_seconds >= 0.0
    assert result.save_seconds >= 0.0
    assert result.load_seconds >= 0.0
    assert result.metrics_seconds >= 0.0
    assert 0.0 <= result.query_p50_ms <= result.query_p95_ms <= result.query_max_ms
    assert result.peak_tracemalloc_bytes > 0


def test_cli_writes_json_report(tmp_path: Path) -> None:
    """CLI exits 0 and persists valid JSON report to --json-out."""
    report_path = tmp_path / "capacity.json"
    exit_code = main(
        [
            "--assets",
            "20",
            "--relationships",
            "60",
            "--topology",
            "dense_hub",
            "--query-iterations",
            "5",
            "--json-out",
            str(report_path),
        ]
    )
    assert exit_code == 0
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["loaded_asset_count"] == 20
    assert payload["loaded_relationship_count"] == 60
    assert payload["topology"] == "dense_hub"


def test_run_lock_contention_benchmark_preserves_fencing_monotonicity() -> None:
    """Multi-worker lock contention maintains monotonic fencing tokens with zero violations."""
    result = run_lock_contention_benchmark(workers=4, iterations_per_worker=5)
    assert result.total_attempts == 20
    assert result.acquisitions >= 1
    assert result.acquisitions + result.contention_rejections == 20
    assert result.fencing_token_violations == 0
    assert 0.0 <= result.acquire_p50_ms <= result.acquire_p95_ms <= result.acquire_max_ms


def test_cli_contention_mode_writes_json_report(tmp_path: Path) -> None:
    """CLI --mode contention exits 0 and writes structured contention JSON."""
    report_path = tmp_path / "contention.json"
    exit_code = main(
        [
            "--mode",
            "contention",
            "--workers",
            "3",
            "--iterations",
            "4",
            "--json-out",
            str(report_path),
        ]
    )
    assert exit_code == 0
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["total_attempts"] == 12
    assert payload["fencing_token_violations"] == 0
