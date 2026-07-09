"""Unit tests for architecture-expert synthesize regeneration."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from compound.schema import PathPolicyError, assert_writable  # noqa: E402
from compound.synthesize import (  # noqa: E402
    should_hot_path_synthesize,
    synthesize,
)


def _write_obs(ledger: Path, rows: list[dict]) -> None:
    lines = ["# schema_version=1"]
    for row in rows:
        lines.append(json.dumps(row, sort_keys=True))
    ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def synth_repo(tmp_path: Path) -> Path:
    """Repo with compound stubs and empty domains."""
    root = tmp_path
    (root / "docs/compound/ledger").mkdir(parents=True)
    (root / "docs/compound/domains").mkdir(parents=True)
    (root / "docs/compound/ledger/observations.jsonl").write_text("#\n", encoding="utf-8")
    (root / "docs/compound/INDEX.md").write_text("# Index\n", encoding="utf-8")
    for domain in (
        "architecture",
        "api",
        "persistence",
        "ci-guardrails",
        "rebuild-reconciliation",
        "deployment",
    ):
        (root / f"docs/compound/domains/{domain}.md").write_text(f"# {domain}\n", encoding="utf-8")
    return root


@pytest.mark.unit
class TestCompoundSynthesize:
    """Synthesize sole-writer and batching behavior."""

    def test_landed_supersedes_provisional(self, synth_repo: Path) -> None:
        """Provisional then landed for same seam keeps landed in Landed section."""
        ledger = synth_repo / "docs/compound/ledger/observations.jsonl"
        _write_obs(
            ledger,
            [
                {
                    "observation_id": "1",
                    "source": "github",
                    "event_type": "pull_request.opened",
                    "status": "provisional",
                    "primary_ref": "pr:99",
                    "summary": "Propose persistence seam",
                    "domains": ["persistence"],
                    "created_at": "2026-07-01T00:00:00Z",
                },
                {
                    "observation_id": "2",
                    "source": "github",
                    "event_type": "push.main",
                    "status": "landed",
                    "primary_ref": "pr:99",
                    "summary": "Persistence seam merged",
                    "domains": ["persistence"],
                    "created_at": "2026-07-02T00:00:00Z",
                },
            ],
        )
        outputs = synthesize(synth_repo, force=True)
        persistence = outputs["docs/compound/domains/persistence.md"]
        assert "Persistence seam merged" in persistence  # nosec B101
        assert "## Landed" in persistence  # nosec B101
        # Provisional section should not still list the superseded provisional-only claim
        provisional_block = persistence.split("## Provisional", 1)[1]
        assert "Propose persistence seam" not in provisional_block  # nosec B101

    def test_two_emitters_one_section(self, synth_repo: Path) -> None:
        """Two observations for one event collapse to one primary_ref section entry."""
        ledger = synth_repo / "docs/compound/ledger/observations.jsonl"
        _write_obs(
            ledger,
            [
                {
                    "observation_id": "a",
                    "source": "github",
                    "event_type": "pull_request.opened",
                    "status": "provisional",
                    "primary_ref": "pr:7",
                    "summary": "Same event from github",
                    "domains": ["api"],
                    "created_at": "2026-07-01T00:00:00Z",
                },
                {
                    "observation_id": "b",
                    "source": "cursor",
                    "event_type": "pull_request.opened",
                    "status": "provisional",
                    "primary_ref": "pr:7",
                    "summary": "Same event from cursor",
                    "domains": ["api"],
                    "created_at": "2026-07-01T01:00:00Z",
                },
            ],
        )
        outputs = synthesize(synth_repo, force=True)
        api_doc = outputs["docs/compound/domains/api.md"]
        assert api_doc.count("**pr:7**") == 1  # nosec B101

    def test_dependabot_batches_without_force(self, synth_repo: Path) -> None:
        """Dependabot-only observations skip hot-path synthesize unless forced."""
        rows = [
            {
                "observation_id": "d1",
                "source": "github",
                "event_type": "pull_request.synchronize",
                "status": "provisional",
                "primary_ref": "pr:1366",
                "summary": "chore(deps): bump the python-dependencies group",
                "domains": ["ci-guardrails"],
                "created_at": "2026-07-01T00:00:00Z",
            }
        ]
        obs_list = []
        from compound.schema import observation_from_mapping

        for row in rows:
            obs_list.append(observation_from_mapping(row))
        assert should_hot_path_synthesize(obs_list) is False  # nosec B101
        assert should_hot_path_synthesize(obs_list, force=True) is True  # nosec B101
        assert should_hot_path_synthesize(obs_list, event_hint="push") is True  # nosec B101

        ledger = synth_repo / "docs/compound/ledger/observations.jsonl"
        _write_obs(ledger, rows)
        assert synthesize(synth_repo) == {}  # nosec B101
        assert synthesize(synth_repo, force=True)  # nosec B101

    def test_refuse_denylisted_write(self) -> None:
        """Path policy rejects ADR writes."""
        with pytest.raises(PathPolicyError):
            assert_writable("docs/adr/0001-production-architecture.md")
