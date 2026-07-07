# financial-asset-relationship-db

> Repo-specific guidance for Codex and other local agents.

## Purpose

Use this skill when working in the `financial-asset-relationship-db` repository and you need a compact summary of the repo's stable conventions.

## Repository shape

- Production stack: FastAPI backend in `api/` and Next.js frontend in `frontend/`.
- Non-production demo path: `app.py`.
- Shared domain logic lives under `src/`.
- Tests are under `tests/` and `frontend/__tests__/`.

## Core rules

- Treat `main` as the reference for stable behavior unless the user specifies another branch or PR.
- Confirm the current branch, the referenced branch or PR, and whether the target differs from `main` before summarizing or editing.
- Preserve unrelated user changes in the worktree.
- Keep changes narrow and aligned with existing patterns.

## Useful references

- [`AGENTS.md`](../../../AGENTS.md)
- [`.github/AUTOMATION_SCOPE_POLICY.md`](../../../.github/AUTOMATION_SCOPE_POLICY.md)
- [`docs/adr/0001-production-architecture.md`](../../../docs/adr/0001-production-architecture.md)

## Common commands

```bash
pytest
cd frontend && npm test
cd frontend && npm run lint
cd frontend && npm run build
```

For Python formatting and linting, follow the repo's existing tooling in `AGENTS.md` and `pyproject.toml`.
