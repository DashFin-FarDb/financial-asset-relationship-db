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
    RUNTIME_PATH,
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
RUNTIME_REL = RUNTIME_PATH.as_posix()


def _default_runtime_data() -> dict[str, str | int | None]:
    """Return default runtime.yml values."""
    return {
        "writer_mode": WriterMode.DUAL.value,
        "conflict_count": 0,
        "conflict_window_minutes": 30,
        "last_conflict_at": None,
    }


def _repo_path(relative: Path | str, repo_root: Path | None = None) -> Path:
    root = repo_root or REPO_ROOT
    return root / Path(relative)


def _resolve_repo_file(file_path: Path, repo_root: Path | None = None) -> Path:
    """Resolve a caller-supplied file path and require it to stay inside the repo."""
    root = (repo_root or REPO_ROOT).resolve()
    candidate = file_path if file_path.is_absolute() else root / file_path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PathPolicyError("--file must point inside the repository root") from exc
    if not resolved.is_file():
        raise PathPolicyError(f"--file does not exist or is not a file: {file_path}")
    return resolved


def read_writer_mode(repo_root: Path | None = None) -> WriterMode:
    """Read dual-writer mode from runtime.yml."""
    runtime_path = _repo_path(RUNTIME_PATH, repo_root)
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
    data = _default_runtime_data()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        _apply_runtime_yaml_value(data, key.strip(), value.strip())
    return data


def _apply_runtime_yaml_value(data: dict[str, str | int | None], key: str, value: str) -> None:
    """Apply one supported runtime.yml scalar to the runtime data mapping."""
    if key == "writer_mode":
        data[key] = value
    elif key in {"conflict_count", "conflict_window_minutes"}:
        data[key] = int(value)
    elif key == "last_conflict_at":
        data[key] = None if value in {"null", "~", ""} else value


def _write_runtime_yaml(path: Path, data: Mapping[str, Any]) -> None:
    """Write runtime.yml with the fixed key set."""
    assert_writable(path.as_posix() if path.as_posix().startswith("docs/") else RUNTIME_REL)
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


def _load_runtime_data(runtime_path: Path) -> dict[str, str | int | None]:
    """Load runtime.yml data or return defaults when it does not exist."""
    if runtime_path.exists():
        return _parse_runtime_yaml(runtime_path.read_text(encoding="utf-8"))
    return _default_runtime_data()


def _conflict_count_inside_window(data: Mapping[str, Any], current: datetime) -> int:
    """Return the existing conflict count if the previous conflict is still inside the window."""
    last_raw = data.get("last_conflict_at")
    if not isinstance(last_raw, str) or last_raw in {"null", ""}:
        return 0
    try:
        last_at = datetime.fromisoformat(last_raw.replace("Z", "+00:00"))
    except ValueError:
        return 0
    window_minutes = int(data.get("conflict_window_minutes") or 30)
    age_minutes = (current - last_at).total_seconds() / 60.0
    return 0 if age_minutes > window_minutes else int(data.get("conflict_count") or 0)


def record_push_conflict(repo_root: Path | None = None, *, now: datetime | None = None) -> WriterMode:
    """Increment conflict_count and flip to github_only when threshold is met.

    Threshold: >=3 conflicts within conflict_window_minutes (plan A12).
    """
    root = repo_root or REPO_ROOT
    runtime_path = _repo_path(RUNTIME_PATH, root)
    assert_writable(RUNTIME_REL)
    current = datetime.now(timezone.utc) if now is None else now
    data = _load_runtime_data(runtime_path)
    count = _conflict_count_inside_window(data, current) + 1
    data["conflict_count"] = count
    data["last_conflict_at"] = current.strftime("%Y-%m-%dT%H:%M:%SZ")
    if count >= 3:
        data["writer_mode"] = WriterMode.GITHUB_ONLY.value
    _write_runtime_yaml(runtime_path, data)
    return WriterMode(str(data["writer_mode"]))


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


def _prepare_payload(
    data: Mapping[str, Any],
    *,
    source_override: ObservationSource | None = None,
) -> dict[str, Any]:
    """Return an observation payload with generated defaults filled in."""
    payload = dict(data)
    if source_override is not None:
        payload["source"] = source_override.value
    if not payload.get("observation_id"):
        payload["observation_id"] = f"obs-{uuid4().hex[:12]}"
    if not payload.get("created_at"):
        payload["created_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return payload


def _cursor_emit_blocked(
    observation: Observation,
    writer_mode: WriterMode,
    *,
    allow_cursor_when_github_only: bool,
) -> bool:
    """Return True when github_only mode should no-op a Cursor observation."""
    return (
        writer_mode is WriterMode.GITHUB_ONLY
        and observation.source is ObservationSource.CURSOR
        and not allow_cursor_when_github_only
    )


def _github_only_noop_message() -> str:
    """Return the user-facing no-op message for github_only Cursor emits."""
    return (
        "writer_mode=github_only: Cursor continuous emit no-ops; "
        "use workflow_dispatch or a PR that lands through GitHub"
    )


def _ensure_ledger_file(ledger_path: Path) -> None:
    """Create the ledger file with its header if it does not exist."""
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    if ledger_path.exists():
        return
    ledger_path.write_text(
        "# Architecture Expert observation ledger (JSONL, append-only).\n"
        "# schema_version=1 — see scripts/compound/schema.py\n",
        encoding="utf-8",
    )


def _append_json_line(ledger_path: Path, observation: Observation) -> None:
    """Append one serialized observation to the ledger."""
    with ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(observation.to_json_line())
        handle.write("\n")


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

    payload = _prepare_payload(data, source_override=source_override)
    observation = observation_from_mapping(payload)

    writer_mode = read_writer_mode(root)
    if _cursor_emit_blocked(
        observation,
        writer_mode,
        allow_cursor_when_github_only=allow_cursor_when_github_only,
    ):
        return None, _github_only_noop_message()

    existing = load_existing_dedupe_keys(ledger_path)
    if observation.dedupe_key() in existing:
        return None, f"idempotent-no-op for {observation.dedupe_key()}"

    _ensure_ledger_file(ledger_path)
    _append_json_line(ledger_path, observation)
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


def _record_push_conflict_cli(repo_root: Path | None) -> int:
    """Handle the push-conflict CLI mode."""
    mode = record_push_conflict(repo_root)
    print(f"recorded push conflict; writer_mode={mode.value}")
    return 0


def _require_payload_source(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Require exactly one observation payload source."""
    if bool(args.json) == bool(args.file):
        parser.error("Provide exactly one of --json or --file")


def _load_cli_payload(args: argparse.Namespace) -> Any:
    """Load an observation payload from CLI arguments."""
    if args.json:
        return json.loads(args.json)
    input_file = _resolve_repo_file(args.file, args.repo_root)
    return json.loads(input_file.read_text(encoding="utf-8"))


def _handle_cli_payload(args: argparse.Namespace, payload: Any) -> int:
    """Validate or append a loaded CLI observation payload."""
    if not isinstance(payload, Mapping):
        raise SchemaError("Observation payload must be a JSON object")
    if args.validate_only:
        observation_from_mapping(payload)
        print("validated")
        return 0
    _, message = append_observation(payload, repo_root=args.repo_root)
    print(message)
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for appending a single observation."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.record_push_conflict:
            return _record_push_conflict_cli(args.repo_root)
        _require_payload_source(parser, args)
        return _handle_cli_payload(args, _load_cli_payload(args))
    except (SchemaError, PathPolicyError, json.JSONDecodeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
