#!/usr/bin/env bash
set -Eeuo pipefail

# Docker owns the fresh cluster and the container-local CLI endpoint for this run.
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
requested_major="${FARDB_POSTGRES_MAJOR:-16}"
case "$requested_major" in
  15|16) ;;
  *) echo 'Only PostgreSQL 15 and 16 are supported by this disposable harness' >&2; exit 2 ;;
esac
if [[ -n "${PG_CONFIG:-}" ]]; then
  echo 'Native execution is fail-closed until an equivalent CLI endpoint binding is approved' >&2
  exit 2
fi
cd "$repo_root"
configured_python="${FARDB_PYTHON:-python3}"
if ! harness_python="$(command -v "$configured_python")"; then
  echo 'A configured Python 3 interpreter is required (FARDB_PYTHON or python3)' >&2
  exit 2
fi
if ! "$harness_python" -c 'import sys; sys.exit(0 if sys.version_info[0] == 3 and sys.version_info[:2] >= (3, 10) else 1)'; then
  echo 'The configured interpreter must be Python 3.10 or newer within Python 3' >&2
  exit 2
fi
exec "$harness_python" -m tests.integration.postgresql_disposable_cluster harness --major "$requested_major" "$@"
