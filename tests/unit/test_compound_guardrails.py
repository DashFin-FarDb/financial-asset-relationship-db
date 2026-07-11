"""Unit tests for hybrid-backup writer mode helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from compound.append_observation import append_observation, read_writer_mode  # noqa: E402
from compound.schema import ObservationSource, PathPolicyError, WriterMode, assert_writable  # noqa: E402


@pytest.mark.unit
class TestCompoundGuardrailHelpers:
    """Denylist and hybrid-backup mode behavior."""

    def test_denylist_write_helper(self) -> None:
        """Shared write helper rejects denylisted paths."""
        with pytest.raises(PathPolicyError):
            assert_writable("docs/adr/0001-production-architecture.md")

    def test_hybrid_backup_flag_blocks_cursor(self, tmp_path: Path) -> None:
        """github_only mode causes Cursor append to no-op with explicit message."""
        (tmp_path / "docs/compound/ledger").mkdir(parents=True)
        (tmp_path / "docs/compound/ledger/observations.jsonl").write_text("#\n", encoding="utf-8")
        (tmp_path / "docs/compound/runtime.yml").write_text(
            "writer_mode: github_only\nconflict_count: 3\nconflict_window_minutes: 30\nlast_conflict_at: null\n",
            encoding="utf-8",
        )
        assert read_writer_mode(tmp_path) is WriterMode.GITHUB_ONLY
        obs, message = append_observation(
            {
                "observation_id": "c1",
                "source": ObservationSource.CURSOR.value,
                "event_type": "manual",
                "status": "provisional",
                "primary_ref": "local:1",
                "summary": "cursor emit",
                "domains": ["architecture"],
            },
            repo_root=tmp_path,
        )
        assert obs is None
        assert "github_only" in message
