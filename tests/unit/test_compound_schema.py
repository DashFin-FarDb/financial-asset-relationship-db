"""Unit tests for architecture-expert compound schema and path policy."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from compound.schema import (  # noqa: E402
    ObservationSource,
    ObservationStatus,
    PathPolicyError,
    SchemaError,
    assert_writable,
    detect_domains_from_paths,
    is_allowlisted,
    is_denylisted,
    normalize_repo_relative,
    observation_from_mapping,
    watched_series_from_mapping,
)


@pytest.mark.unit
class TestCompoundSchema:
    """Observation and watched-series schema validation."""

    def test_provisional_and_landed_round_trip(self) -> None:
        """Valid provisional and landed observations serialize and re-parse."""
        for status in (ObservationStatus.PROVISIONAL, ObservationStatus.LANDED):
            raw = {
                "observation_id": f"obs-{status.value}",
                "source": "github",
                "event_type": "pull_request.synchronize",
                "status": status.value,
                "primary_ref": "pr:1390",
                "summary": "Docstring baseline PR",
                "domains": ["ci-guardrails"],
                "created_at": "2026-07-09T00:00:00Z",
            }
            obs = observation_from_mapping(raw)
            assert obs.status is status
            rebuilt = observation_from_mapping(obs.to_dict())
            assert rebuilt.dedupe_key() == obs.dedupe_key()
            assert rebuilt.observation_id == obs.observation_id

    def test_duplicate_dedupe_key_identity(self) -> None:
        """Same source/event/primary_ref share one dedupe key for idempotent append."""
        base = {
            "observation_id": "a",
            "source": ObservationSource.GITHUB.value,
            "event_type": "pull_request.opened",
            "status": "provisional",
            "primary_ref": "pr:1",
            "summary": "one",
        }
        other = dict(base)
        other["observation_id"] = "b"
        other["summary"] = "two"
        first = observation_from_mapping(base)
        second = observation_from_mapping(other)
        assert first.dedupe_key() == second.dedupe_key()

    def test_watched_series_missing_keys_fails(self) -> None:
        """Watched-series YAML missing required keys raises SchemaError."""
        with pytest.raises(SchemaError, match="missing required keys"):
            watched_series_from_mapping({"version": 1, "prs": []})

    def test_watched_series_valid_fixture(self) -> None:
        """Repo watched-series.yml validates against the schema."""
        path = REPO_ROOT / "docs" / "compound" / "watched-series.yml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        series = watched_series_from_mapping(data)
        assert series.version == 1

    def test_allowlist_accepts_compound_domain_doc(self) -> None:
        """Allowlist accepts docs/compound domain paths."""
        path = "docs/compound/domains/api.md"
        assert is_allowlisted(path)
        assert assert_writable(path) == path

    def test_denylist_rejects_adr_and_agents(self) -> None:
        """Denylist rejects ADR paths and AGENTS.md."""
        assert is_denylisted("docs/adr/0001-production-architecture.md")
        assert is_denylisted("AGENTS.md")
        with pytest.raises(PathPolicyError, match="denylist"):
            assert_writable("docs/adr/0001-production-architecture.md")
        with pytest.raises(PathPolicyError, match="denylist"):
            assert_writable("AGENTS.md")

    def test_unknown_path_not_allowlisted(self) -> None:
        """Paths outside allowlist are rejected even if not denylisted."""
        with pytest.raises(PathPolicyError, match="not allowlisted"):
            assert_writable("src/logic/asset_graph.py")

    def test_detect_domains_from_paths(self) -> None:
        """Changed paths map to compound domains; empty defaults to architecture."""
        assert detect_domains_from_paths([]) == ("architecture",)
        assert detect_domains_from_paths(["README.md"]) == ("architecture",)
        assert "api" in detect_domains_from_paths(["api/main.py", "frontend/app/page.tsx"])
        assert "persistence" in detect_domains_from_paths(["src/data/sample_data.py"])
        assert "rebuild-reconciliation" in detect_domains_from_paths(["src/logic/reconciliation_engine.py"])
        assert "ci-guardrails" in detect_domains_from_paths([".github/workflows/ci.yml"])
        assert "deployment" in detect_domains_from_paths(["docs/staging-deployment-operating-baseline.md"])
        multi = detect_domains_from_paths(["api/auth.py", "docs/adr/0001-production-architecture.md"])
        assert "api" in multi
        assert "architecture" in multi

    def test_path_traversal_rejected_by_policy(self) -> None:
        """``..`` segments cannot bypass allowlist/denylist checks."""
        with pytest.raises(PathPolicyError, match="traversal"):
            normalize_repo_relative("docs/compound/../../AGENTS.md")
        with pytest.raises(PathPolicyError, match="traversal"):
            assert_writable("docs/compound/../../AGENTS.md")
        assert is_denylisted("docs/compound/../../AGENTS.md")
        assert not is_allowlisted("docs/compound/../../AGENTS.md")
