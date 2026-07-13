"""Unit tests for architecture-expert synthesize regeneration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from compound.schema import Observation, PathPolicyError, assert_writable, observation_from_mapping  # noqa: E402
from compound.synthesize import (  # noqa: E402
    load_ledger,
    should_hot_path_synthesize,
    synthesize,
)


def _write_obs(ledger: Path, rows: list[dict]) -> None:
    lines = ["# schema_version=1"]
    for row in rows:
        lines.append(json.dumps(row, sort_keys=True))
    ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _observation(**overrides: object) -> Observation:
    """Build a valid observation with focused overrides."""
    row: dict[str, object] = {
        "observation_id": "obs",
        "source": "github",
        "event_type": "pull_request.opened",
        "status": "provisional",
        "primary_ref": "pr:1",
        "summary": "Architecture seam change",
        "domains": ["architecture"],
        "created_at": "2026-07-01T00:00:00Z",
    }
    row.update(overrides)
    return observation_from_mapping(row)


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
        assert "Persistence seam merged" in persistence
        assert "## Landed" in persistence
        # Provisional section should not still list the superseded provisional-only claim
        provisional_block = persistence.split("## Provisional", 1)[1]
        assert "Propose persistence seam" not in provisional_block

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
        assert api_doc.count("**pr:7**") == 1

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
        obs_list = [observation_from_mapping(row) for row in rows]
        assert should_hot_path_synthesize(obs_list) is False
        assert should_hot_path_synthesize(obs_list, force=True) is True
        assert should_hot_path_synthesize(obs_list, event_hint="push") is True

        ledger = synth_repo / "docs/compound/ledger/observations.jsonl"
        _write_obs(ledger, rows)
        assert synthesize(synth_repo) == {}
        assert synthesize(synth_repo, force=True)

    def test_dependabot_batching_ignores_historical_non_bot(self) -> None:
        """Newest dependabot event still batches even if older non-bot rows exist."""
        mixed = [
            _observation(
                observation_id="old",
                created_at="2026-06-01T00:00:00Z",
            ),
            _observation(
                observation_id="new",
                event_type="pull_request.synchronize",
                primary_ref="pr:1366",
                summary="chore(deps): bump the python-dependencies group",
                domains=["ci-guardrails"],
                created_at="2026-07-09T00:00:00Z",
            ),
        ]
        assert should_hot_path_synthesize(mixed) is False

    def test_hot_path_uses_append_order_not_max_timestamp(self) -> None:
        """Trigger gate uses the last ledger row even if an older row has a newer timestamp."""
        rows = [
            _observation(
                observation_id="stale-ts",
                created_at="2026-12-01T00:00:00Z",
            ),
            _observation(
                observation_id="appended-last",
                event_type="pull_request.synchronize",
                primary_ref="pr:1366",
                summary="chore(deps): bump the python-dependencies group",
                domains=["ci-guardrails"],
                created_at="2026-01-01T00:00:00Z",
            ),
        ]
        assert should_hot_path_synthesize(rows) is False

    def test_refuse_denylisted_write(self) -> None:
        """Path policy rejects ADR writes."""
        with pytest.raises(PathPolicyError):
            assert_writable("docs/adr/0001-production-architecture.md")

    def test_load_ledger_skips_malformed_with_warning(
        self, synth_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Corrupt ledger lines are skipped and reported on stderr."""
        ledger = synth_repo / "docs/compound/ledger/observations.jsonl"
        ledger.write_text(
            "\n".join(
                [
                    "# schema_version=1",
                    "{not-json",
                    json.dumps(
                        {
                            "observation_id": "ok",
                            "source": "github",
                            "event_type": "pull_request.opened",
                            "status": "provisional",
                            "primary_ref": "pr:1",
                            "summary": "Valid row",
                            "domains": ["architecture"],
                            "created_at": "2026-07-01T00:00:00Z",
                        }
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        observations = load_ledger(ledger)
        assert len(observations) == 1
        assert observations[0].primary_ref == "pr:1"
        err = capsys.readouterr().err
        assert "skipping malformed ledger line" in err
