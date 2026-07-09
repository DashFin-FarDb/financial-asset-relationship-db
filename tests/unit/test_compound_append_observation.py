"""Unit tests for append-only observation ledger writes."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from compound.append_observation import append_observation, record_push_conflict  # noqa: E402
from compound.schema import ObservationSource, ObservationStatus, WriterMode  # noqa: E402


@pytest.fixture
def compound_repo(tmp_path: Path) -> Path:
    """Minimal compound tree for append tests."""
    ledger = tmp_path / "docs" / "compound" / "ledger"
    ledger.mkdir(parents=True)
    (ledger / "observations.jsonl").write_text(
        "# schema_version=1\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "compound" / "runtime.yml").write_text(
        "writer_mode: dual\nconflict_count: 0\nconflict_window_minutes: 30\nlast_conflict_at: null\n",
        encoding="utf-8",
    )
    return tmp_path


def _base_payload(**overrides: object) -> dict:
    payload = {
        "observation_id": "obs-1",
        "source": ObservationSource.GITHUB.value,
        "event_type": "pull_request.opened",
        "status": ObservationStatus.PROVISIONAL.value,
        "primary_ref": "pr:42",
        "summary": "Open PR",
        "domains": ["persistence"],
    }
    payload.update(overrides)
    return payload


@pytest.mark.unit
class TestAppendObservation:
    """Append idempotency and writer-mode gates."""

    def test_identical_observation_ids_are_idempotent(self, compound_repo: Path) -> None:
        """Appending two identical observation IDs results in one observation."""
        first, msg1 = append_observation(_base_payload(), repo_root=compound_repo)
        second, msg2 = append_observation(
            _base_payload(summary="dup"),
            repo_root=compound_repo,
        )
        assert first is not None
        assert "appended" in msg1
        assert second is None
        assert "idempotent" in msg2
        lines = [
            line
            for line in (compound_repo / "docs/compound/ledger/observations.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip() and not line.startswith("#")
        ]
        assert len(lines) == 1

    def test_repeat_pr_syncs_with_distinct_observation_ids_append(self, compound_repo: Path) -> None:
        """Later PR sync observations for the same PR update the ledger."""
        first, _ = append_observation(
            _base_payload(
                observation_id="gh-1-1",
                event_type="pull_request.synchronize",
                summary="Initial sync",
                domains=["api"],
            ),
            repo_root=compound_repo,
        )
        second, _ = append_observation(
            _base_payload(
                observation_id="gh-2-1",
                event_type="pull_request.synchronize",
                summary="Updated sync",
                domains=["persistence"],
            ),
            repo_root=compound_repo,
        )
        assert first is not None
        assert second is not None
        lines = [
            line
            for line in (compound_repo / "docs/compound/ledger/observations.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip() and not line.startswith("#")
        ]
        assert len(lines) == 2
        assert "Initial sync" in lines[0]
        assert "Updated sync" in lines[1]

    def test_open_pr_emits_provisional(self, compound_repo: Path) -> None:
        """Open PR fixture emits provisional status."""
        obs, _ = append_observation(_base_payload(), repo_root=compound_repo)
        assert obs is not None
        assert obs.status is ObservationStatus.PROVISIONAL

    def test_merged_pr_emits_landed(self, compound_repo: Path) -> None:
        """Merged PR fixture emits landed status."""
        obs, _ = append_observation(
            _base_payload(
                status=ObservationStatus.LANDED.value,
                event_type="pull_request.closed",
            ),
            repo_root=compound_repo,
        )
        assert obs is not None
        assert obs.status is ObservationStatus.LANDED

    def test_cursor_noop_when_github_only(self, compound_repo: Path) -> None:
        """Cursor continuous emit no-ops under github_only writer mode."""
        (compound_repo / "docs/compound/runtime.yml").write_text(
            "writer_mode: github_only\nconflict_count: 3\nconflict_window_minutes: 30\nlast_conflict_at: null\n",
            encoding="utf-8",
        )
        obs, message = append_observation(
            _base_payload(source=ObservationSource.CURSOR.value),
            repo_root=compound_repo,
        )
        assert obs is None
        assert "github_only" in message
        lines = [
            line
            for line in (compound_repo / "docs/compound/ledger/observations.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip() and not line.startswith("#")
        ]
        assert lines == []

    def test_cli_json_round_trip(self, compound_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI accepts --json and appends successfully."""
        from compound import append_observation as mod

        monkeypatch.setattr(mod, "REPO_ROOT", compound_repo)
        payload = json.dumps(_base_payload(observation_id="cli-1"))
        assert mod.main(["--json", payload, "--repo-root", str(compound_repo)]) == 0

    def test_cli_file_must_stay_inside_repo(self, compound_repo: Path) -> None:
        """CLI rejects --file inputs that resolve outside the selected repo root."""
        from compound import append_observation as mod

        outside_file = compound_repo.parent / "outside-observation.json"
        outside_file.write_text(json.dumps(_base_payload(observation_id="outside")), encoding="utf-8")

        assert mod.main(["--file", str(outside_file), "--repo-root", str(compound_repo)]) == 1

    def test_record_push_conflict_flips_at_threshold(self, compound_repo: Path) -> None:
        """Three conflicts inside the window flip writer_mode to github_only (A12)."""
        now = datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)
        assert record_push_conflict(compound_repo, now=now) is WriterMode.DUAL
        assert record_push_conflict(compound_repo, now=now + timedelta(minutes=1)) is WriterMode.DUAL
        assert record_push_conflict(compound_repo, now=now + timedelta(minutes=2)) is WriterMode.GITHUB_ONLY
        runtime = (compound_repo / "docs/compound/runtime.yml").read_text(encoding="utf-8")
        assert "writer_mode: github_only" in runtime
        assert "conflict_count: 3" in runtime

    def test_record_push_conflict_resets_outside_window(self, compound_repo: Path) -> None:
        """Conflicts outside the window reset the counter."""
        now = datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)
        record_push_conflict(compound_repo, now=now)
        record_push_conflict(compound_repo, now=now + timedelta(minutes=1))
        mode = record_push_conflict(compound_repo, now=now + timedelta(minutes=45))
        assert mode is WriterMode.DUAL
        runtime = (compound_repo / "docs/compound/runtime.yml").read_text(encoding="utf-8")
        assert "conflict_count: 1" in runtime
