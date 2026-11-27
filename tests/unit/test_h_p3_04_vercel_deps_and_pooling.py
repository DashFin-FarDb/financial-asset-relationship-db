"""Unit tests for H-P3-04: slim Vercel API dependencies and PostgreSQL connection pooling."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from api import database as api_db
from src.data.database import create_engine_from_url


def _requirement_names(path: Path) -> set[str]:
    """Return normalized lowercase package names declared in a requirements file."""
    names: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.match(r"([A-Za-z0-9_.-]+)", line)
        if match:
            names.add(match.group(1).lower().replace("_", "-"))
    return names


def test_vercel_api_requirements_excludes_non_production_heavy_packages() -> None:
    """api/requirements.txt keeps production FastAPI deps and drops Gradio/MCP/scraper bloat."""
    req_path = Path(__file__).resolve().parents[2] / "api" / "requirements.txt"
    assert req_path.is_file()
    packages = _requirement_names(req_path)

    required = {
        "fastapi",
        "uvicorn",
        "pydantic",
        "python-multipart",
        "numpy",
        "mangum",
        "psycopg2-binary",
        "sqlalchemy",
        "pyjwt",
        "passlib",
        "slowapi",
        "prometheus-client",
        "structlog",
        "sentry-sdk",
    }
    excluded = {
        "gradio",
        "mcp",
        "fastmcp",
        "yfinance",
        "pandas",
        "plotly",
        "curl-cffi",
        "markdown",
        "bleach",
    }
    assert required <= packages
    assert packages.isdisjoint(excluded)


def test_sqlalchemy_postgres_engine_enables_connection_pooling(monkeypatch: pytest.MonkeyPatch) -> None:
    """PostgreSQL SQLAlchemy engines configure pre-ping and bounded pool settings."""
    monkeypatch.setenv("DB_POOL_SIZE", "4")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "6")
    monkeypatch.setenv("DB_POOL_RECYCLE_SECONDS", "240")
    monkeypatch.setenv("DB_POOL_TIMEOUT_SECONDS", "15")

    engine = create_engine_from_url("postgresql://user:pass@127.0.0.1:5432/fardb")
    try:
        assert engine.pool._pre_ping is True
        assert engine.pool.size() == 4
        assert engine.pool._max_overflow == 6
        assert engine.pool._recycle == 240
        assert engine.pool._timeout == 15
    finally:
        engine.dispose()


def test_api_database_postgres_pool_checkout_return_and_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    """api.database.get_connection uses ThreadedConnectionPool and discards broken connections."""
    api_db.close_postgres_pool()

    fake_conn = MagicMock()
    fake_conn.closed = 0
    fake_pool = MagicMock()
    fake_pool.closed = False
    fake_pool.getconn.return_value = fake_conn

    pool_factory = MagicMock(return_value=fake_pool)
    monkeypatch.setattr("psycopg2.pool.ThreadedConnectionPool", pool_factory)
    monkeypatch.setattr(api_db, "DATABASE_TYPE", "postgresql")
    monkeypatch.setattr(api_db, "DATABASE_URL", "postgresql://user:pass@127.0.0.1:5432/authdb")
    monkeypatch.setenv("API_DB_POOL_ENABLED", "true")
    monkeypatch.setenv("API_DB_POOL_MAX_CONN", "3")

    with api_db.get_connection() as conn:
        assert conn is fake_conn
    fake_pool.putconn.assert_called_once_with(fake_conn, close=False)

    fake_pool.putconn.reset_mock()
    with pytest.raises(RuntimeError, match="boom"):
        with api_db.get_connection():
            raise RuntimeError("boom")
    fake_conn.rollback.assert_called_once()
    fake_pool.putconn.assert_called_once_with(fake_conn, close=True)

    api_db.close_postgres_pool()
    fake_pool.closeall.assert_called_once()
    assert pool_factory.call_count == 1
    assert pool_factory.call_args.args[1] == 3
