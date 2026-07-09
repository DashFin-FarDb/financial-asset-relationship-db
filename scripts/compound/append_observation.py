"""Append-only observation ledger writes for architecture compounding."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

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
RUNTIME_REL_PATH = "docs/compound/runtime.yml"
RUNTIME_DEFAULTS: dict[str, str | int | None] = {
    "writer_mode": WriterMode.DUAL.value,
    "conflict_count": 0,
    "conflict_window_minutes": 30,
    "last_conflict_at": None,
}


def _repo_path(relative: Path | str, repo_root: Path | None = None) -> Path:
    root = repo_root or REPO_ROOT
    return root / Path(relative)


def read_writer_mode(repo_root: Path | None = None) -> WriterMode:
    """Read dual-writer mode from docs/compound/runtime.yml."""
    runtime_path = _repo_path(RUNTIME_REL_PATH, repo_root)
    if not runtime_path.exists():
        return WriterMode.DUAL
    text = runtime_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("writer_mode:"):
            value = stripped.split(":", 1)[1].strip()
            try:
                return WriterMode(value)
            except ValueError as exc:
                raise SchemaError(f"Invalid writer_mode: {value}") from exc
    return WriterMode.DUAL


def _parse_runtime_yaml(text: str) -> dict[str, str | int | None]:
    """Parse the small runtime.yml key set without requiring PyYAML."""
    data = dict(RUNTIME_DEFAULTS)
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and ":" in stripped:
            _set_runtime_value(data, stripped)
    return data


def _set_runtime_value(data: dict[str, str | int | None], line: str) -> None:
    """Set one supported runtime key from a simple ``key: value`` line."""
    key, raw_value = line.split(":", 1)
    key = key.strip()
    value = raw_value.strip()
    if key == "writer_mode":
        data[key] = value
    elif key in {"conflict_count", "conflict_window_minutes"}:
        data[key] = int(value)
    elif key == "last_conflict_at":
        data[key] = None if value in {"null", "~", ""} else value


def _write_runtime_yaml(path: Path, data: Mapping[str, Any]) -> None:
    """Write runtime.yml with the fixed key set."""
    assert_writable(path.as_posix() if path.as_posix().startswith("docs/") else RUNTIME_REL_PATH)
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def record_push_conflict(repo_root: Path | None = None, *, now: datetime | None = None) -> WriterMode:
    """Increment conflict_count and flip to github_only when threshold is met.

    Threshold: >=3 conflicts within conflict_window_minutes (plan A12).
    """
    root = repo_root or REPO_ROOT
    runtime_path = _repo_path(RUNTIME_REL_PATH, root)
    assert_writable(RUNTIME_REL_PATH)
    current = datetime.now(timezone.utc) if now is None else now
    data = _read_runtime_data(runtime_path)
    count = _current_conflict_count(data, current) + 1
    data["conflict_count"] = count
    data["last_conflict_at"] = current.strftime("%Y-%m-%dT%H:%M:%SZ")
    if count >= 3:
        data["writer_mode"] = WriterMode.GITHUB_ONLY.value
    _write_runtime_yaml(runtime_path, data)
    return WriterMode(str(data["writer_mode"]))


def _read_runtime_data(runtime_path: Path) -> dict[str, str | int | None]:
    """Read runtime.yml or return defaults when it does not exist."""
    if runtime_path.exists():
        return _parse_runtime_yaml(runtime_path.read_text(encoding="utf-8"))
    return dict(RUNTIME_DEFAULTS)


def _current_conflict_count(data: Mapping[str, Any], current: datetime) -> int:
    """Return the active conflict count, resetting stale or malformed windows."""
    last_raw = data.get("last_conflict_at")
    if not isinstance(last_raw, str) or last_raw in {"null", ""}:
        return 0
    try:
        last_at = datetime.fromisoformat(last_raw.replace("Z", "+00:00"))
    except ValueError:
        return 0
    window_minutes = int(data.get("conflict_window_minutes") or 30)
    if (current - last_at).total_seconds() / 60.0 > window_minutes:
        return 0
    return int(data.get("conflict_count") or 0)


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

    writer_mode = read_writer_mode(root)
    if (
        writer_mode is WriterMode.GITHUB_ONLY
        and observation.source is ObservationSource.CURSOR
        and not allow_cursor_when_github_only
    ):
        return (
            None,
            "writer_mode=github_only: Cursor continuous emit no-ops; "
            "use workflow_dispatch or a PR that lands through GitHub",
        )

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


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for appending a single observation."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.record_push_conflict:
            mode = record_push_conflict(args.repo_root)
            print(f"recorded push conflict; writer_mode={mode.value}")
            return 0
        if not args.json:
            parser.error("Provide --json")
        payload = json.loads(args.json)
        if not isinstance(payload, Mapping):
            raise SchemaError("Observation payload must be a JSON object")
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
