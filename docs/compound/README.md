# Architecture Expert Compound — Operator Runbook

Docs-first compounded memory for architecture, seams, API, persistence/SQL,
CI/guardrails, rebuild/reconciliation, and deployment/readiness.

## Layout

- `docs/compound/ledger/observations.jsonl` — append-only observation ledger
- `docs/compound/domains/*.md` — domain docs (synthesize-only)
- `docs/compound/INDEX.md` — thin cross-seam index
- `docs/compound/briefs/` — durable standing briefs
- `docs/compound/watched-series.yml` — watched PR numbers / labels / path globs
- `docs/compound/runtime.yml` — `writer_mode: dual | github_only`

## Bootstrap

```pwsh
python scripts/compound/bootstrap.py --no-prs   # seed docs only
python scripts/compound/bootstrap.py            # seed docs + bounded gh PR scrape
python scripts/compound/synthesize.py --force
python scripts/compound/sync_agent_packs.py
```

## Continuous compound

GitHub workflow: `.github/workflows/architecture-compound.yml`

- PR open/sync → provisional observation
- Push to `main` → landed observation + force synthesize
- `workflow_dispatch` → manual compound

Synthesize commits land only on `knowledge/architecture-expert`. **Never auto-merged to `main`.**

## Watched series

Edit `docs/compound/watched-series.yml`:

```yaml
version: 1
prs: [1390]
labels: ["architecture-expert"]
path_globs: ["api/**", "src/logic/**"]
```

## Cursor emit

On a checkout of `knowledge/architecture-expert`:

```pwsh
python scripts/compound/append_observation.py --json '<observation-json-object>'
python scripts/compound/synthesize.py --force
python scripts/compound/sync_agent_packs.py
```

If `runtime.yml` has `writer_mode: github_only`, Cursor continuous emit no-ops;
use `workflow_dispatch` or a PR that lands through GitHub.

## Consumers

```pwsh
python scripts/compound/query_memory.py --question "where does graph rebuild persistence live?"
python scripts/compound/standing_brief.py --as-of 2026-07-09
```

Agent packs (generated, sidecar-only):

- `.cursor/rules/architecture-expert.mdc`
- `.cursor/rules/architecture-expert-query.mdc`
- `.openhands/microagents/architecture_expert.md`

Do **not** overwrite Dosu-maintained `AGENTS.md`.

## Promote knowledge → main

1. Open a human PR from `knowledge/architecture-expert` → `main`
2. Use architecture-docs PR template discipline
3. Review provisional vs landed labeling
4. Merge only when docs look trustworthy

## Hybrid backup

Auto-flip criteria (plan A12): ≥3 synthesize push conflicts or divergent ledger
tips within 30 minutes → set `writer_mode: github_only` in `runtime.yml`.
