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

## Interface contracts (verified from code)

### Observation payload contract (`append_observation.py` + `schema.py`)

Required fields:

- `observation_id`
- `source` (`github`, `cursor`, `manual`, `bootstrap`)
- `event_type`
- `status` (`provisional` or `landed`)
- `primary_ref`
- `summary`

Optional fields:

- `domains` (must be one of: `architecture`, `api`, `persistence`, `ci-guardrails`, `rebuild-reconciliation`, `deployment`)
- `refs`
- `evidence_pointers`
- `created_at` (ISO-8601 when provided)
- `schema_version` (must match current schema version)

Idempotency is enforced by the tuple `(source, event_type, primary_ref)`.

### Watched-series contract (`watched-series.yml`)

The file must include all required keys:

- `version` (integer)
- `prs` (list of integers)
- `labels` (list of strings)
- `path_globs` (list of strings)

### Write-safety policy

- Appenders only write to the observation ledger.
- `synthesize.py` is the canonical writer for `docs/compound/domains/*.md` and `docs/compound/INDEX.md`.
- Policy/ADR surfaces are denylisted (for example `docs/adr/`, `AGENTS.md`, and selected `.github` policy files).
- Path traversal (`..`) is rejected by path normalization before write checks.

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
python scripts/compound/append_observation.py --file observation.json
python scripts/compound/synthesize.py --force
python scripts/compound/sync_agent_packs.py
```

If `runtime.yml` has `writer_mode: github_only`, Cursor continuous emit no-ops;
use `workflow_dispatch` or a PR that lands through GitHub.

## Operator workflow (recommended order)

1. Bootstrap baseline observations:

   ```pwsh
   python scripts/compound/bootstrap.py --no-prs
   ```

2. Regenerate the docs projection:

   ```pwsh
   python scripts/compound/synthesize.py --force
   ```

3. Query memory to confirm expected landed/provisional sections:

   ```pwsh
   python scripts/compound/query_memory.py --question "what changed in ci guardrails?"
   ```

4. Sync agent packs only after synthesize output looks correct:

   ```pwsh
   python scripts/compound/sync_agent_packs.py
   ```

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

## Troubleshooting and common pitfalls

- `error: watched-series missing required keys`:
  - Fix `docs/compound/watched-series.yml` so it includes `version`, `prs`, `labels`, and `path_globs` with the expected types.
- `error: Rejected unsafe gh argument ...`:
  - `bootstrap.py` only accepts bounded `gh pr ...` arguments/tokens; remove shell metacharacters and unsupported subcommands.
- `writer_mode=github_only: Cursor continuous emit no-ops ...`:
  - Continuous Cursor writes are intentionally blocked. Use `workflow_dispatch` or let GitHub-driven events write observations.
- `warning: skipping malformed ledger line ...` during synthesize:
  - Fix the malformed JSON line in `docs/compound/ledger/observations.jsonl`; malformed entries are skipped to keep synthesis running.
- Query responses show "No compounded observations matched yet":
  - Seed the ledger first (`bootstrap.py --no-prs`) and rerun `synthesize.py --force`.
