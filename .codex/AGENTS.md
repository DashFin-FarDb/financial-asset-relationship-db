# Codex Repo Notes

This file supplements the root `AGENTS.md` with a short repo-local baseline for Codex users.

## Keep in mind

- Production path is FastAPI in `api/` plus Next.js in `frontend/`.
- `app.py` is non-production and kept only for demos/internal testing.
- Always verify branch/ref identity before reviewing or summarizing PRs.
- Do not revert unrelated local changes.
- Prefer `rg` / `rg --files` for repo search.

## High-value references

- Root guidance: [`AGENTS.md`](../AGENTS.md)
- Production architecture policy: [`.github/AUTOMATION_SCOPE_POLICY.md`](../.github/AUTOMATION_SCOPE_POLICY.md)
- Architecture decision record: [`docs/adr/0001-production-architecture.md`](../docs/adr/0001-production-architecture.md)

## When editing

- Prefer the existing repo patterns over inventing new abstractions.
- Keep changes scoped to the production architecture unless the request explicitly targets demos or internal tooling.
- For auth, database, deployment, CI, security, or persistence work, move carefully and validate the full flow.
