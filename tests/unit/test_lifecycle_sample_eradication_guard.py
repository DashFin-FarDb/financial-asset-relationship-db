"""Architectural guard tests ensuring complete eradication of sample data fallbacks from runtime lifecycle."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import get_args

import api.api_models
import api.graph_lifecycle
import api.graph_lifecycle_providers

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_RUNTIME_FILES: list[Path] = [
    _PROJECT_ROOT / "api" / "graph_lifecycle.py",
    _PROJECT_ROOT / "api" / "graph_lifecycle_providers.py",
    _PROJECT_ROOT / "api" / "app_factory.py",
    _PROJECT_ROOT / "src" / "api" / "dependencies.py",
    _PROJECT_ROOT / "api" / "routers" / "graph_admin.py",
]


def test_runtime_lifecycle_modules_do_not_import_sample_data() -> None:
    """Runtime lifecycle modules must not import from src.data.sample_data or reference sample constructors."""
    for file_path in _RUNTIME_FILES:
        assert file_path.exists(), f"Runtime file {file_path} not found"
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "sample_data" not in alias.name, f"{file_path} imports forbidden module '{alias.name}'"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert "sample_data" not in module, f"{file_path} imports forbidden module from '{module}'"
                for alias in node.names:
                    assert "sample_data" not in alias.name, f"{file_path} imports forbidden module '{alias.name}'"
                    assert (
                        alias.name != "create_sample_database"
                    ), f"{file_path} imports forbidden symbol '{alias.name}'"
                    assert alias.name != "create_sample_graph", f"{file_path} imports forbidden symbol '{alias.name}'"


def test_lifecycle_providers_exposes_no_sample_graph_constructor() -> None:
    """api.graph_lifecycle_providers must not expose any sample graph constructor or callable."""
    assert not hasattr(
        api.graph_lifecycle_providers, "create_sample_graph"
    ), "api.graph_lifecycle_providers must not expose create_sample_graph"
    for attr in dir(api.graph_lifecycle_providers):
        assert (
            "sample_graph" not in attr.lower()
        ), f"api.graph_lifecycle_providers exposes forbidden sample seam '{attr}'"


def test_graph_rebuild_source_type_contract_excludes_sample() -> None:
    """GraphRebuildSource literal must strictly allow only 'cache' and 'real_data', never 'sample'."""
    provider_source_type = api.graph_lifecycle_providers.GraphRebuildSource
    api_source_type = api.api_models.GraphRebuildSource

    for source_type, name in [
        (provider_source_type, "api.graph_lifecycle_providers.GraphRebuildSource"),
        (api_source_type, "api.api_models.GraphRebuildSource"),
    ]:
        allowed_sources = set(get_args(source_type))
        assert allowed_sources == {
            "cache",
            "real_data",
        }, f"{name} allowed sources must be exactly {{'cache', 'real_data'}}, got {allowed_sources}"
        assert "sample" not in allowed_sources, f"{name} must not include 'sample'"


def test_graph_lifecycle_provider_source_mapping_excludes_sample() -> None:
    """_PROVIDER_SOURCE_TO_STARTUP_SOURCE in graph_lifecycle must not map 'sample'."""
    mapping = api.graph_lifecycle._PROVIDER_SOURCE_TO_STARTUP_SOURCE  # pylint: disable=protected-access
    assert set(mapping.keys()) == {
        "cache",
        "real_data",
    }, f"Provider source mapping keys must be strictly {{'cache', 'real_data'}}, got {set(mapping.keys())}"
    assert "sample" not in mapping, "Provider source mapping must not include 'sample'"
