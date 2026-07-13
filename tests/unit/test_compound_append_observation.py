"""Unit tests for append-only observation ledger writes."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from compound import append_observation as append_observation_mod
from compound.append_observation import (
    _load_observation_payload,
    _parse_runtime_yaml,
    _repo_path,
    _write_runtime_yaml,
    append_observation,
    record_push_conflict,
)
from compound.schema import ObservationSource, ObservationStatus, PathPolicyError, SchemaError, WriterMode


def _observation_lines(repo: Path) -> list[str]:
    """Return non-comment ledger observation lines."""
    ledger = repo / "docs/compound/ledger/observations.jsonl"
    return [
        line for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")
    ]


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


def _capture_thread(fn) -> tuple[threading.Thread, list[Exception]]:
    """Run ``fn`` on a thread, capturing exceptions for the parent to assert."""
    errors: list[Exception] = []

    def _run() -> None:
        try:
            fn()
        except Exception as exc:  # pragma: no cover - re-raised via parent assertions
            errors.append(exc)

    return threading.Thread(target=_run), errors


def _join_thread(thread: threading.Thread, *, timeout: float = 1.0) -> None:
    """Join a thread and require it finished within ``timeout``."""
    if thread.ident is not None:
        thread.join(timeout=timeout)
    assert thread.ident is None or not thread.is_alive()


@pytest.mark.unit
class TestAppendObservation:
    """Append idempotency and writer-mode gates."""

    def test_identical_event_keys_are_idempotent(self, compound_repo: Path) -> None:
        """Appending two identical event keys results in one observation."""
        first, msg1 = append_observation(_base_payload(), repo_root=compound_repo)
        second, msg2 = append_observation(
            _base_payload(observation_id="obs-2", summary="dup"),
            repo_root=compound_repo,
        )
        assert first is not None
        assert "appended" in msg1
        assert second is None
        assert "idempotent" in msg2
        assert len(_observation_lines(compound_repo)) == 1

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
        assert _observation_lines(compound_repo) == []

    def test_append_serializes_writer_mode_check_with_conflict_recording(
        self, compound_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A conflict recorder cannot flip writer mode between the Cursor gate and append."""
        (compound_repo / "docs/compound/runtime.yml").write_text(
            "writer_mode: dual\n"
            "conflict_count: 2\n"
            "conflict_window_minutes: 30\n"
            "last_conflict_at: 2026-07-09T12:00:00Z\n",
            encoding="utf-8",
        )
        entered_ledger_load = threading.Event()
        release_ledger_load = threading.Event()
        conflict_recorded = threading.Event()
        append_result: dict[str, tuple[object, str]] = {}
        original_load = append_observation_mod.load_existing_dedupe_keys

        def blocking_load(ledger_path: Path) -> set[tuple[str, str, str]]:
            entered_ledger_load.set()
            assert release_ledger_load.wait(timeout=1.0)
            return original_load(ledger_path)

        def run_append() -> None:
            append_result["result"] = append_observation(
                _base_payload(source=ObservationSource.CURSOR.value),
                repo_root=compound_repo,
            )

        def run_conflict_record() -> None:
            record_push_conflict(compound_repo, now=datetime(2026, 7, 9, 12, 1, tzinfo=timezone.utc))
            conflict_recorded.set()

        monkeypatch.setattr(append_observation_mod, "load_existing_dedupe_keys", blocking_load)
        append_thread, append_errors = _capture_thread(run_append)
        conflict_thread, conflict_errors = _capture_thread(run_conflict_record)

        append_thread.start()
        try:
            assert entered_ledger_load.wait(timeout=1.0)
            conflict_thread.start()
            assert not conflict_recorded.wait(timeout=0.2)
        finally:
            release_ledger_load.set()
        _join_thread(append_thread)
        _join_thread(conflict_thread)

        assert not append_errors
        assert not conflict_errors
        assert conflict_recorded.is_set()
        obs, message = append_result["result"]
        assert obs is not None
        assert "appended" in message

    def test_cli_json_round_trip(self, compound_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI accepts --json and appends successfully."""
        monkeypatch.setattr(append_observation_mod, "REPO_ROOT", compound_repo)
        payload = json.dumps(_base_payload(observation_id="cli-1"))
        assert append_observation_mod.main(["--json", payload, "--repo-root", str(compound_repo)]) == 0

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

    def test_parse_runtime_preserves_timestamp_colons(self) -> None:
        """ISO-8601 last_conflict_at values keep colons after the first key split."""
        parsed = _parse_runtime_yaml(
            "writer_mode: dual\nconflict_count: 2\nconflict_window_minutes: 30\n"
            "last_conflict_at: 2026-07-09T07:18:22Z\n"
        )
        assert parsed["last_conflict_at"] == "2026-07-09T07:18:22Z"
        assert parsed["conflict_count"] == 2

    def test_parse_runtime_rejects_non_integer_counts(self) -> None:
        """Non-integer conflict fields raise SchemaError, not bare ValueError."""
        with pytest.raises(SchemaError, match="Invalid integer for conflict_count"):
            _parse_runtime_yaml("writer_mode: dual\nconflict_count: three\n")

    def test_load_observation_payload_rejects_outside_repo(self, compound_repo: Path) -> None:
        """Absolute paths outside the repo and temp dir are rejected."""
        forbidden = Path("/etc/hosts")
        if not forbidden.is_file():
            forbidden = Path("/var/empty/outside-payload.json")
        with pytest.raises(PathPolicyError):
            _load_observation_payload(forbidden, repo_root=compound_repo)

    def test_repo_path_rejects_traversal_outside_repo(self, compound_repo: Path) -> None:
        """Repo-relative path resolution rejects parent traversal."""
        with pytest.raises(PathPolicyError):
            _repo_path("../outside-runtime.yml", repo_root=compound_repo)

    def test_write_runtime_yaml_rejects_absolute_path_outside_repo(self, compound_repo: Path) -> None:
        """Runtime writes cannot target an absolute path outside the repo."""
        outside_path = compound_repo.parent / "outside-runtime.yml"
        with pytest.raises(PathPolicyError):
            _write_runtime_yaml(outside_path, {}, repo_root=compound_repo)
        assert not outside_path.exists()

    def test_load_observation_payload_allows_repo_relative(self, compound_repo: Path) -> None:
        """Repo-relative observation files are accepted."""
        payload_path = compound_repo / "docs" / "compound" / "payload.json"
        payload_path.write_text(json.dumps(_base_payload()), encoding="utf-8")
        loaded = _load_observation_payload(payload_path, repo_root=compound_repo)
        assert loaded["observation_id"] == "obs-1"
