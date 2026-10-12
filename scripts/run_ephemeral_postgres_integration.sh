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
python -m tests.integration.postgresql_disposable_cluster harness --major "$requested_major" "$@"
