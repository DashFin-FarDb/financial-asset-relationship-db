"""Append-only observation ledger writes for architecture compounding."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from compound.schema import (
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


def _repo_path(relative: Path | str, repo_root: Path | None = None) -> Path:
    root = repo_root or REPO_ROOT
    return root / Path(relative)


def read_writer_mode(repo_root: Path | None = None) -> WriterMode:
    """Read dual-writer mode from docs/compound/runtime.yml."""
    runtime_path = _repo_path("docs/compound/runtime.yml", repo_root)
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
    parser.add_argument("--file", type=Path, help="Path to JSON observation file")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (defaults to detected root)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for appending a single observation."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if bool(args.json) == bool(args.file):
        parser.error("Provide exactly one of --json or --file")

    try:
        if args.json:
            payload = json.loads(args.json)
        else:
            payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise SchemaError("Observation payload must be a JSON object")
        _, message = append_observation(payload, repo_root=args.repo_root)
        print(message)
        return 0
    except (SchemaError, PathPolicyError, json.JSONDecodeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
