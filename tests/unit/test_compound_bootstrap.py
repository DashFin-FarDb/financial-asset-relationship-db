"""Unit tests for bounded architecture-expert bootstrap seeding."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from compound.bootstrap import SEED_DOCS, scrape_recent_prs, seed_from_docs  # noqa: E402
from compound.schema import DOMAINS, parse_observation_line  # noqa: E402


@pytest.fixture
def seed_repo(tmp_path: Path) -> Path:
    """Fixture repo with seed docs derived from SEED_DOCS and empty ledger."""
    (tmp_path / "docs" / "compound" / "ledger").mkdir(parents=True)
    (tmp_path / "docs" / "compound" / "ledger" / "observations.jsonl").write_text(
        "# schema_version=1\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "compound" / "runtime.yml").write_text(
        "writer_mode: dual\nconflict_count: 0\nconflict_window_minutes: 30\nlast_conflict_at: null\n",
        encoding="utf-8",
    )
    for rel, _domains in SEED_DOCS:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {path.name}\n", encoding="utf-8")
    return tmp_path


@pytest.mark.unit
class TestCompoundBootstrap:
    """Bootstrap seed coverage and gh-unavailable behavior."""

    def test_seed_docs_cover_all_domains(self, seed_repo: Path) -> None:
        """Bootstrap from fixture seed docs covers all six domains."""
        messages = seed_from_docs(seed_repo)
        assert any("appended" in message or "idempotent" in message for message in messages)
        ledger = seed_repo / "docs/compound/ledger/observations.jsonl"
        domains_seen: set[str] = set()
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            obs = parse_observation_line(line)
            domains_seen.update(obs.domains)
            assert not str(obs.primary_ref).startswith("docs/adr/") or obs.source.value == "bootstrap"
        assert domains_seen == set(DOMAINS)

    def test_seed_does_not_write_denylisted_paths(self, seed_repo: Path) -> None:
        """Bootstrap only appends ledger; ADR bytes remain unchanged."""
        adr = seed_repo / "docs/adr/0001-production-architecture.md"
        before = adr.read_text(encoding="utf-8")
        seed_from_docs(seed_repo)
        assert adr.read_text(encoding="utf-8") == before

    def test_gh_unavailable_is_nonfatal(self, seed_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When gh is unavailable, PR scrape reports skipped and does not raise."""
        from compound import bootstrap as mod

        monkeypatch.setattr(mod, "_gh_json", lambda _args: None)
        messages = scrape_recent_prs(seed_repo)
        assert messages == ["PR scrape skipped: gh unavailable or failed"]

    def test_scrape_maps_domains_from_pr_files(self, seed_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Bootstrap PR scrape classifies domains from changed file paths."""
        from compound import bootstrap as mod

        monkeypatch.setattr(
            mod,
            "_gh_json",
            lambda _args: [
                {
                    "number": 99,
                    "title": "API change",
                    "state": "OPEN",
                    "mergedAt": None,
                    "files": [{"path": "api/main.py"}, {"path": "docs/adr/0001.md"}],
                }
            ],
        )
        messages = scrape_recent_prs(seed_repo)
        assert any("pr:99" in message for message in messages)
        ledger = seed_repo / "docs/compound/ledger/observations.jsonl"
        domains: set[str] = set()
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            obs = parse_observation_line(line)
            if obs.primary_ref == "pr:99":
                domains.update(obs.domains)
        assert "api" in domains
        assert "architecture" in domains
