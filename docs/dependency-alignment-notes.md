# Dependency alignment notes (startup install stability)

## What was checked

- Compared normalized runtime dependencies declared in:
  - `pyproject.toml` (`[project].dependencies`)
  - `requirements.txt` (runtime/deployment set)
- Re-validated frontend install/lint/build on branch `agent/database-authorization-boundary`.

## Result

- `pyproject.toml` and `requirements.txt` were out of sync before this update:
  - Present only in `requirements.txt`: `urllib3>=2.7.0`, `zipp>=4.1.0`
- This change adds those security-floor dependencies to `pyproject.toml` so both manifests describe the same runtime baseline.

## Additional dependency-risk review

- Current branch checks indicate the startup install issue was caused by incompatible frontend major bumps (`typescript@7` and `eslint@10`) against the active Next.js / typescript-eslint support window.
- No additional active dependency conflicts were identified on this branch after alignment.

## Remaining risk profile

- Residual risk is primarily from branches that are behind this commit and still carry the incompatible dependency set.
- Recommended mitigation after merge to `main`:
  1. Rebase or merge `main` into active feature branches.
  2. Re-run `npm install --prefix frontend`, `npm --prefix frontend run lint`, and `npm --prefix frontend run build`.
  3. Resolve lockfile conflicts by regenerating `frontend/package-lock.json` from the updated baseline if needed.
