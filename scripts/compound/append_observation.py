"""Append-only observation ledger writes for architecture compounding."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping
from uuid import uuid4

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX CI is not supported for compound writers
    fcntl = None  # type: ignore[assignment]

_SCRIPTS_ROOT = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from compound.schema import (  # noqa: E402
    LEDGER_PATH,
    Observation,
    ObservationSource,
    PathPolicyError,
    SchemaError,
    WriterMode,
    assert_writable,
    observation_from_mapping,
    parse_observation_line,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_YML_REL = "docs/compound/runtime.yml"
_RUNTIME_LOCK_NAME = "runtime.yml.lock"
_LEDGER_LOCK_NAME = "observations.jsonl.lock"


def _repo_path(relative: Path | str, repo_root: Path | None = None) -> Path:
    root = repo_root or REPO_ROOT
    return root / Path(relative)


@contextmanager
def _exclusive_lock(lock_path: Path) -> Iterator[None]:
    """Cross-process exclusive lock for compound writer critical sections."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    # Best-effort cleanup so lock artifacts don't accumulate or get committed.
    try:
        lock_path.unlink()
    except OSError:
        # Ignore cleanup failures (e.g., lock file already removed or transient FS issue).
        pass


def read_writer_mode(repo_root: Path | None = None) -> WriterMode:
    """Read dual-writer mode from runtime.yml."""
    runtime_path = _repo_path(RUNTIME_YML_REL, repo_root)
    if not runtime_path.exists():
        return WriterMode.DUAL
    text = runtime_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("writer_mode:"):
            # split(..., 1) preserves timestamp values that contain additional colons.
            value = stripped.split(":", 1)[1].strip()
            try:
                return WriterMode(value)
            except ValueError as exc:
                raise SchemaError(f"Invalid writer_mode: {value}") from exc
    return WriterMode.DUAL


def _parse_runtime_yaml(text: str) -> dict[str, str | int | None]:
    """Parse the small runtime.yml key set without requiring PyYAML.

    Values may contain colons (ISO-8601 timestamps); keys are split on the
    first ``:`` only via ``str.split(":", 1)``.
    """
    data: dict[str, str | int | None] = {
        "writer_mode": WriterMode.DUAL.value,
        "conflict_count": 0,
        "conflict_window_minutes": 30,
        "last_conflict_at": None,
    }
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key == "writer_mode":
            data[key] = value
        elif key in {"conflict_count", "conflict_window_minutes"}:
            try:
                data[key] = int(value)
            except ValueError as exc:
                raise SchemaError(f"Invalid integer for {key}: {value}") from exc
        elif key == "last_conflict_at":
            data[key] = None if value in {"null", "~", ""} else value
    return data


def _write_runtime_yaml(path: Path, data: Mapping[str, Any], *, repo_root: Path | None = None) -> None:
    """Write runtime.yml with the fixed key set."""
    root = (repo_root or REPO_ROOT).resolve()
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        rel = resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise PathPolicyError(f"Runtime path outside repo: {path}") from exc
    if rel != RUNTIME_YML_REL:
        raise PathPolicyError(f"Write denied (runtime path mismatch): {path}")
    assert_writable(rel)
    lines = [
        "# Architecture-expert dual-writer runtime mode.",
        "# writer_mode: dual | github_only",
        "# Auto-flip to github_only after >=3 synthesize push conflicts or divergent",
        "# ledger tips within conflict_window_minutes.",
        f"writer_mode: {data.get('writer_mode', WriterMode.DUAL.value)}",
        f"conflict_count: {int(data.get('conflict_count') or 0)}",
        f"conflict_window_minutes: {int(data.get('conflict_window_minutes') or 30)}",
        f"last_conflict_at: {data.get('last_conflict_at') if data.get('last_conflict_at') is not None else 'null'}",
        "",
    ]
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def _default_runtime_data() -> dict[str, str | int | None]:
    """Return the default runtime.yml payload."""
    return {
        "writer_mode": WriterMode.DUAL.value,
        "conflict_count": 0,
        "conflict_window_minutes": 30,
        "last_conflict_at": None,
    }


def _conflicts_in_window(
    *,
    count: int,
    last_raw: str | int | None,
    window_minutes: int,
    current: datetime,
) -> int:
    """Return conflict count still inside the hybrid-backup window."""
    if not isinstance(last_raw, str) or last_raw in {"null", ""}:
        return 0
    try:
        last_at = datetime.fromisoformat(last_raw.replace("Z", "+00:00"))
    except ValueError:
        return 0
    age_minutes = (current - last_at).total_seconds() / 60.0
    if age_minutes > window_minutes:
        return 0
    return count


def record_push_conflict(repo_root: Path | None = None, *, now: datetime | None = None) -> WriterMode:
    """Increment conflict_count and flip to github_only when threshold is met.

    Threshold: >=3 conflicts within conflict_window_minutes (plan A12).
    Updates are serialized with an exclusive lock on the runtime sidecar.
    """
    root = repo_root or REPO_ROOT
    runtime_path = _repo_path(RUNTIME_YML_REL, root)
    assert_writable(RUNTIME_YML_REL)
    current = datetime.now(timezone.utc) if now is None else now
    lock_path = runtime_path.parent / _RUNTIME_LOCK_NAME
    with _exclusive_lock(lock_path):
        if runtime_path.exists():
            data = _parse_runtime_yaml(runtime_path.read_text(encoding="utf-8"))
        else:
            data = _default_runtime_data()

        window_minutes = int(data.get("conflict_window_minutes") or 30)
        count = _conflicts_in_window(
            count=int(data.get("conflict_count") or 0),
            last_raw=data.get("last_conflict_at"),
            window_minutes=window_minutes,
            current=current,
        )
        count += 1
        data["conflict_count"] = count
        data["last_conflict_at"] = current.strftime("%Y-%m-%dT%H:%M:%SZ")
        if count >= 3:
            data["writer_mode"] = WriterMode.GITHUB_ONLY.value
        _write_runtime_yaml(runtime_path, data, repo_root=root)
        try:
            return WriterMode(str(data["writer_mode"]))
        except ValueError as exc:
            raise SchemaError(f"Invalid writer_mode after conflict record: {data['writer_mode']}") from exc


def _cursor_emit_blocked(observation: Observation, writer_mode: WriterMode, *, allow_cursor: bool) -> str | None:
    """Return a no-op message when Cursor emit is blocked by github_only mode."""
    if writer_mode is not WriterMode.GITHUB_ONLY:
        return None
    if observation.source is not ObservationSource.CURSOR or allow_cursor:
        return None
    return (
        "writer_mode=github_only: Cursor continuous emit no-ops; "
        "use workflow_dispatch or a PR that lands through GitHub"
    )


def load_existing_dedupe_keys(ledger_path: Path) -> set[tuple[str, str, str]]:
    """Load dedupe keys already present in the ledger."""
    keys: set[tuple[str, str, str]] = set()
    if not ledger_path.exists():
        return keys
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            obs = parse_observation_line(stripped)
        except SchemaError:
            continue
        keys.add(obs.dedupe_key())
    return keys


def append_observation(
    data: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
    source_override: ObservationSource | None = None,
    allow_cursor_when_github_only: bool = False,
) -> tuple[Observation | None, str]:
    """Append one observation if new; return (observation_or_None, message).

    Idempotent on (source, event_type, primary_ref). Never rewrites prior lines.
    Dedupe-check + append is serialized with an exclusive ledger lock.
    """
    root = repo_root or REPO_ROOT
    ledger_rel = LEDGER_PATH.as_posix()
    assert_writable(ledger_rel)
    ledger_path = _repo_path(LEDGER_PATH, root)

    payload = dict(data)
    if source_override is not None:
        payload["source"] = source_override.value
    if not payload.get("observation_id"):
        payload["observation_id"] = f"obs-{uuid4().hex[:12]}"
    if not payload.get("created_at"):
        payload["created_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    observation = observation_from_mapping(payload)
    blocked = _cursor_emit_blocked(
        observation,
        read_writer_mode(root),
        allow_cursor=allow_cursor_when_github_only,
    )
    if blocked is not None:
        return None, blocked

    lock_path = ledger_path.parent / _LEDGER_LOCK_NAME
    with _exclusive_lock(lock_path):
        existing = load_existing_dedupe_keys(ledger_path)
        if observation.dedupe_key() in existing:
            return None, f"idempotent-no-op for {observation.dedupe_key()}"

        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        if not ledger_path.exists():
            ledger_path.write_text(
                "# Architecture Expert observation ledger (JSONL, append-only).\n"
                "# schema_version=1 — see scripts/compound/schema.py\n",
                encoding="utf-8",
            )

        with ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(observation.to_json_line())
            handle.write("\n")

    return observation, f"appended {observation.observation_id}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", help="Observation JSON object string")
    parser.add_argument("--file", type=Path, help="Path to JSON observation file")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (defaults to detected root)",
    )
    parser.add_argument(
        "--record-push-conflict",
        action="store_true",
        help="Increment hybrid-backup conflict_count (plan A12)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate observation JSON without appending",
    )
    return parser


def _is_under(path: Path, root: Path) -> bool:
    """Return True when ``path`` is inside ``root`` after resolve."""
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _load_observation_payload(path: Path, *, repo_root: Path | None = None) -> Mapping[str, Any]:
    """Load observation JSON from a path under the repo or system temp dir."""
    root = (repo_root or REPO_ROOT).resolve()
    resolved = path.expanduser().resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if not (_is_under(resolved, root) or _is_under(resolved, temp_root)):
        raise PathPolicyError(f"Observation path must be under the repo or temp dir: {path}")
    if not resolved.is_file():
        raise SchemaError(f"Observation file not found: {path}")
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise SchemaError("Observation payload must be a JSON object")
    return payload


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for appending a single observation."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.record_push_conflict:
            mode = record_push_conflict(args.repo_root)
            print(f"recorded push conflict; writer_mode={mode.value}")
            return 0
        if bool(args.json) == bool(args.file):
            parser.error("Provide exactly one of --json or --file")
        if args.json:
            payload = json.loads(args.json)
            if not isinstance(payload, Mapping):
                raise SchemaError("Observation payload must be a JSON object")
        else:
            payload = _load_observation_payload(Path(args.file), repo_root=args.repo_root)
        if args.validate_only:
            observation_from_mapping(payload)
            print("validated")
            return 0
        _, message = append_observation(payload, repo_root=args.repo_root)
        print(message)
        return 0
    except (SchemaError, PathPolicyError, json.JSONDecodeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
