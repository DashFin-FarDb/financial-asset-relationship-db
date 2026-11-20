# Hosted UI, API, and Supabase Data Path

**Status:** Active operator reference
**Scope:** Identify which hosted URL and database setting controls each part of graph display and persistence.

## Request and persistence path

The current frontend uses an Axios client to call the FastAPI API. It does not create a Supabase browser client or call
the Supabase Data API directly. The path for graph reads and writes is therefore:

```text
Browser -> hosted Next.js UI -> FastAPI API -> PostgreSQL graph store (Supabase)
```

The Netlify static export is a UI host. It fetches data from the separate API; publishing the UI does not start FastAPI
or configure the graph database. The repository's staging target architecture uses Vercel for the Next.js UI and
FastAPI API. When a different UI host is used, configure that host's build with the API origin for the matching
environment.

## Settings by responsibility

| Setting                                                   | Configured on                                              | Controls                                                           | Does not control                                                                                         |
| --------------------------------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| `NEXT_PUBLIC_API_URL`                                     | Netlify static UI build; optional elsewhere                | Browser requests to FastAPI endpoints such as `/api/visualization` | Database credentials, graph persistence, or Supabase Data API access                                     |
| `DATABASE_URL` (or documented `POSTGRES_URL` fallback)    | FastAPI runtime environment                                | Auth/application database connection                               | Frontend routing; it is not a substitute for `ASSET_GRAPH_DATABASE_URL` in durable staging configuration |
| `ASSET_GRAPH_DATABASE_URL`                                | FastAPI runtime environment                                | Authoritative durable graph database connection                    | Browser API routing                                                                                      |
| `COORDINATION_DATABASE_URL`                               | FastAPI runtime environment, when separately configured    | Rebuild job and lock coordination database                         | Graph storage unless an explicitly documented shared boundary applies                                    |
| `NEXT_PUBLIC_SUPABASE_URL` and a Supabase publishable key | A frontend only if it intentionally uses a Supabase client | Supabase project API URL and public client authentication          | The FastAPI origin or backend SQL persistence connection                                                 |

`NEXT_PUBLIC_API_URL` is embedded into the built frontend. On Vercel, this repository serves FastAPI at the same host
under `/api`, so the frontend uses same-origin API requests and the Vercel build deliberately ignores this variable.
On Netlify, the static UI has no FastAPI process; set `NEXT_PUBLIC_API_URL` to the matching API host origin (scheme and
host only, no `/api` suffix) and rebuild after changes. The Next.js config fails the Netlify build if this value is
missing, preventing a published UI that silently calls Netlify for API data. A Vercel-to-Supabase integration can sync
Supabase variables to connected Vercel project environments; it does not configure Netlify.

## Choose and configure a host

### Vercel: UI and FastAPI in one deployment

1. Link the Vercel project to this repository and keep the project root at the repository root. `vercel.json` builds
   `api/main.py` and the Next.js frontend, then routes `/api/*` to FastAPI. The frontend uses normal Next.js output
   on Vercel; static export is reserved for Netlify. Vercel Toolbar Preview Comments cannot patch an immutable
   static-export build, which caused the observed `IMMUTABLE_STATIC_PATCH_PREVIEW_COMMENTS` deployment error.
2. For each Vercel environment that should serve this app, configure the backend's private database variables for
   that same environment: app/auth (`DATABASE_URL`), graph (`ASSET_GRAPH_DATABASE_URL`), and coordination
   (`COORDINATION_DATABASE_URL`) when using a separate boundary. Give each one the approved environment-specific,
   role-scoped connection string. Do not copy production connection strings into Preview.
   The root certificate `prod-ca-2021.crt` is present in the repository and is not excluded by `vercel.json`; use it
   only with the documented `sslmode=verify-full` trust-root path for the matching Supabase endpoint.
3. Do not set `NEXT_PUBLIC_API_URL` on Vercel. The build forces same-origin calls so the browser requests
   `https://<this-deployment>/api/visualization` and the other API paths from `vercel.json`.
4. Build and deploy. Verify the deployment URL's `/api/health`, `/api/visualization`, and hosted readiness before
   sharing the UI. The database schema must already be migrated through the database migration authority process.

### Netlify: static UI calling a separate API

1. Link the Netlify site to this repository and retain the checked-in `netlify.toml`: base `frontend`, command
   `npm ci && npm run build`, publish directory `out`. The Next.js configuration selects static export outside
   Vercel, producing this `out` directory.
2. In Netlify site environment variables, set `NEXT_PUBLIC_API_URL` to the healthy FastAPI deployment origin for each
   deploy context. Use the staging API origin for Deploy Previews and the approved production API origin for Production.
   The URL is public and embedded in the frontend bundle; never put a database URL or private credential in this
   variable.
3. Confirm the API's CORS policy allows the exact Netlify site and preview origins. Do not broaden it to arbitrary
   origins to make a preview work.
4. Trigger a new build after changing the variable. Open the resulting site and confirm the browser's Network panel
   sends `/api/visualization` to the configured API host and receives a non-empty graph response.

### Shared verification

For either host, a successful UI build or page response does not prove the graph is loaded. Check the API endpoints,
then run `python scripts/check_hosted_readiness.py <API_BASE> --require-persistence --assets-smoke`. The result must
show graph persistence configured and loaded, startup source `persisted`, and a successful assets smoke check. Keep
staging checks pointed at an independently confirmed staging database and API; the Supabase Data API URL is not the
FastAPI URL.

Database connection strings and secret keys belong only in the backend's private runtime configuration. Never prefix
database credentials, service-role/secret keys, or other private credentials with `NEXT_PUBLIC_` or expose them to the
browser.

## Supabase Data API and role-based permissions

Supabase's Data API is an auto-generated REST interface over configured database schemas. It is useful when an
application intentionally uses the Supabase client or PostgREST directly. Enabling it, or setting
`NEXT_PUBLIC_SUPABASE_URL`, does not redirect this repository's Axios client to Supabase and does not make FastAPI
graph writes durable.

If the frontend is deliberately changed to use the Data API, treat that as an architecture change: specify the
exposed schema, role grants, row-level security policies, publishable key, and read/write behavior. Keep privileged
operations on the FastAPI server using restricted database roles. Do not use a service-role/secret key in browser
code. Supabase documents that Data API access is governed by Postgres permissions and that its Vercel integration
syncs environment variables to connected Vercel projects; neither behavior configures a separate Netlify site.

The Supabase-to-Vercel Preview/Development sync must only use credentials appropriate for those environments. When
preview-specific Supabase branches or credentials are not provisioned, do not assume Vercel preview deployments have
isolated persistence; review the connection's environment scopes and record the effective database boundary as release
evidence. See the [staging operating baseline](../staging-deployment-operating-baseline.md).

## Deployment verification

Use these checks in order, recording deployment/environment labels and results without copying secret values:

1. **Confirm the frontend API target.** Inspect the target UI deployment's build environment for the presence and
   intended origin of `NEXT_PUBLIC_API_URL`. In the browser Network panel, confirm graph requests go to that FastAPI
   origin and reach the expected `/api/...` endpoint. For Netlify, changing this value requires a new static build.
2. **Confirm the API is serving graph data.** Request `GET <API_BASE>/api/health` and
   `GET <API_BASE>/api/visualization`. A working UI or a successful health response alone does not prove durable
   graph persistence.
3. **Confirm backend persistence configuration.** In the backend's private environment, verify that
   `ASSET_GRAPH_DATABASE_URL` is present and points to the approved graph boundary. Verify app/auth and coordination
   boundaries against the [staging operating baseline](../staging-deployment-operating-baseline.md). Record only
   variable presence and redacted provider/database labels.
4. **Prove the graph was loaded from persistence.** Run the hosted readiness check against the API origin:

   ```bash
   python scripts/check_hosted_readiness.py <API_BASE> --require-persistence --assets-smoke
   ```

   Promotion evidence must show the persistence gate passed (`persistence_enabled` and `persistence_loaded` true,
   startup source `persisted`) and the bounded assets smoke check succeeded. A UI deployment, Data API toggle, database
   connection variable, or `/api/health` response alone is not persistence evidence.

### Netlify build-directory failure

Netlify applies the configured `base` directory before running the build command. With `base = "frontend"`, the command
must be relative to that directory (`npm ci && npm run build`), and the publish directory is `out`. Do not prefix the
command or publish path with `frontend/` again.

The reported deploy-preview log had all three of these resolved values:

```text
base:    /opt/build/repo/frontend
command: cd frontend && npm ci && npm run build
publish: /opt/build/repo/frontend/frontend/.next
```

That combination tries to enter `/opt/build/repo/frontend/frontend`, which does not exist. It also points Netlify at a
publish directory that differs from the static export configured in the current `netlify.toml`. The current
`origin/main` configuration is `base = "frontend"`, `command = "npm ci && npm run build"`, and `publish = "out"`.
The failed build occurs before the browser can call FastAPI; changing either Supabase public URL or the API URL will
not fix this directory error.

The maintainer reported the last successful preview deploy at 7:00 PM from
[PR #1936 commit `c535c78`](https://github.com/DashFin-FarDb/financial-asset-relationship-db/commit/c535c782683a8bd5984a3b18eb59f3148ef70dab).
That commit's `netlify.toml` has the current `frontend` base, `npm ci && npm run build` command, and `out` publish
directory; PR #1936 is closed and merged. The 7:17 PM failed log resolves different settings, so it is not evidence
that the same `c535c78` configuration failed. The failure excerpt does not identify its branch or commit, so its exact
preview cannot be assigned from that excerpt alone.

The Netlify deploy list later identified the 7:16 PM failure as
[Deploy Preview #1930](https://app.netlify.com/projects/fardb-grac/deploys/6aff4af15d7c6813103d3ecc), branch
`codex/phase14-b`, commit `5b7764a` (PR #1930). Its expanded build log confirms the old command and paths shown above.
The same dashboard showed production `main` at `53eadc2` skipped at 7:06 PM because account credit usage was exceeded,
and a notice that production deploys were paused. Thus PR #1936's successful preview did not publish production. The
production billing pause and PR #1930's stale branch config are separate blockers.

Local validation on 2026-11-19 parsed `netlify.toml` and ran `npm ci && npm run build` from `frontend/`. Both commands
completed successfully, and `frontend/out/index.html` was generated. `npm ci` also reported 24 moderate audit findings;
they were not remediated as part of this deployment-path check.

The open PR heads checked on 2026-11-19—#1926 through #1933—still contained the legacy command
`cd frontend && npm ci && npm run build` and publish path `frontend/.next`, while `origin/main` contains the corrected
static-export configuration. Any of those previews can therefore reproduce this failure until its head is updated to
the current base configuration. This audit is a dated snapshot; inspect the exact PR head before relying on it.

### Follow-up: PR #1930 after Netlify config update

At the maintainer's request, commit
[`3a0f6bf`](https://github.com/DashFin-FarDb/financial-asset-relationship-db/commit/3a0f6bfa3389cf7cd7e69fc685eaf18de60578c1)
copied `netlify.toml` from `main` to PR #1930. Netlify automatically rebuilt Deploy Preview #1930, and the corrected
command `npm ci && npm run build` completed its build stage. The deploy then failed because `frontend/out` did not
exist ([Netlify deploy log](https://app.netlify.com/projects/fardb-grac/deploys/6aff5e57516cadbb772b4e5f)).

The PR #1930 version of `frontend/next.config.js` does not set `output: 'export'`; `main` does. The branch therefore
does not produce the static `out/` directory expected by the updated Netlify publish setting. The Netlify command/path
failure is fixed, but the PR preview is not yet deployable. Resolve this by bringing the static-export setting into
the PR branch, then verify the preview publishes before treating this as closed.

For the affected deploy preview, inspect the `netlify.toml` at the exact commit Netlify built and compare it with
Netlify's resolved configuration. Update the preview branch or applicable configuration to match the current
configuration, then trigger a new deploy. In the next deploy log, confirm the base is `frontend`, the command has no
leading `cd frontend`, and the publish path is `out` relative to the base. Confirm the build completes and the preview
root serves the UI before checking `NEXT_PUBLIC_API_URL` and the separate API readiness path.

### Observed deployment checks (2026-11-19 and 2026-11-20)

The following read-only requests were made to the published sites on this date. This is a diagnostic snapshot, not a
release qualification; repeat it after deployment configuration or code changes.

| Target                                                                                    | Check                                                                   | Observed result                                                                    | Meaning                                                                                              |
| ----------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `https://fardb-grac.netlify.app`                                                          | Production UI root                                                      | HTTP 404 on 2026-11-20                                                             | The production Netlify root did not serve the UI at the time of the check.                           |
| `https://deploy-preview-1936--fardb-grac.netlify.app`                                     | PR preview UI root                                                      | HTTP 200                                                                           | Static UI is served. This does not establish API health or graph persistence.                        |
| `https://deploy-preview-1936--fardb-grac.netlify.app`                                     | Inspect built JavaScript for the API origin                             | Contains `https://financial-asset-relationship-db-nine.vercel.app/`                | The preview UI is configured to call this Vercel origin.                                             |
| `https://deploy-preview-1936--fardb-grac.netlify.app`                                     | UI root on 2026-11-20                                                   | HTTP 200                                                                           | Netlify can serve this preview's static UI.                                                          |
| `https://financial-asset-relationship-db-nine.vercel.app`                                 | `GET /api/health` and `GET /api/visualization`                          | HTTP 500 for both (earlier check)                                                  | The previously configured API origin was not serving these requests successfully.                    |
| Vercel main alias `financial-asset-relationship-db-git-main-mohavros-projects.vercel.app` | `GET /api/health` and `GET /api/visualization` on 2026-11-20            | HTTP 500 for both                                                                  | The current Vercel API alias is not returning API data.                                              |
| Latest Vercel production build (`main`, `53eadc2`)                                        | Deployment status on 2026-11-20                                         | Error `IMMUTABLE_STATIC_PATCH_PREVIEW_COMMENTS`                                    | Vercel reports deployment failed; no working production API origin is established.                   |
| Same Vercel API origin                                                                    | `check_hosted_readiness.py --require-persistence --assets-smoke --json` | Failed: `/api/health`, `/api/health/detailed`, and `/api/assets` returned HTTP 500 | Durable graph persistence was **not verified**. No persistence PASS should be claimed from this run. |

The test shows a live mismatch between UI availability and API availability. Follow-up inspection of Vercel runtime
logs on 2026-11-19 identifies that the compiled Netlify preview calls a stale Vercel alias. The alias resolves to
deployment `dpl_Fw4HjUUwtBsYtEa7as1VA7ph4jVn`, branch `mohavro-patch-4`, commit
`c0cd0721e2011ed9b8b4aa14b64098d517367522`, rather than the current PR #1930 Vercel deployment. Requests to
`/api/health`, `/api/health/detailed`, `/api/visualization`, and `/api/graph/metrics` on the stale alias fail during
Python module import: `api.auth` calls `initialize_schema()` at import time, which attempts its configured database
connection. Logs report a shared-pooler username of `postgres` and that SSL is required at
`aws-1-us-east-1.pooler.supabase.com:5432`. Supabase's shared session-pooler format requires the project-qualified
username `postgres.<project-ref>`; its connection guide also requires SSL, and recommends `verify-full` with the
project root certificate when hostname verification is required. Use the exact host and username from the project's
Connect dialog instead of composing them. [Supabase connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres)

The 2026-11-20 repository change makes `output: 'export'` conditional: Netlify builds retain static export, while
Vercel builds use standard Next.js output. This addresses the identified Vercel Toolbar Preview Comments failure
caused by trying to patch immutable files from a static-export build. Local builds verified Vercel's `.next` output
and Netlify's `out/index.html`; the hosted Vercel deployment has not yet been rebuilt and rechecked.

The current PR #1930 Vercel Preview deployment is
`dpl_CNXFyDym1R2apYj8Xsb1zrzPyHHd`, branch `codex/phase14-b`, commit
`18f9bea0888631edb076b00990531b4af397dd03`. Its runtime logs show a separate startup failure: the graph database's
`rebuild_jobs` table is missing required column `snapshot_sha256`; application startup then fails. The same requests
also produced Vercel's Python wrapper message `ImportError: cannot import name 'vc_handler' from
vercel_runtime.vc_init'`. Because that message follows the application startup exception, treat it as a possible
secondary symptom of the failed app import until a deployment with a compatible schema is tested. A read-only request to that
deployment's `/api/health` and `/api/visualization` returned HTTP 404. These findings mean changing Netlify's API URL
to the current PR deployment alone will not restore the graph. A follow-up request through the deployment's Git branch
alias `financial-asset-relationship-db-git-co-406214-mohavros-projects.vercel.app` returned HTTP 500 for both
`/api/health` and `/api/visualization`; Vercel runtime logs for the same request confirmed the schema startup failure
and subsequent wrapper import message. The unique deployment URL's 404 and the branch alias's 500 are separate
observations; use the branch alias result and runtime log to diagnose the live Preview function.

The Vercel project settings page showed provider variables `POSTGRES_URL`, `POSTGRES_PRISMA_URL`,
`POSTGRES_URL_NON_POOLING`, `POSTGRES_PASSWORD`, and Supabase API keys. The `POSTGRES_URL` and related secret
variables apply to both Production and Preview. No explicit `DATABASE_URL`, `ASSET_GRAPH_DATABASE_URL`, or
`COORDINATION_DATABASE_URL` appeared in the project variable list. In the repository settings code,
`DATABASE_URL` falls back to `POSTGRES_URL`, and a Preview graph database without `ASSET_GRAPH_DATABASE_URL` falls back
to that same database URL. This does not meet the staging baseline's explicit graph-boundary and role-scoped runtime
requirements. The Supabase project itself reports `ACTIVE_HEALTHY`, but the dashboard identifies it as `main
PRODUCTION` and shows no database branches.

A read-only query of the live `public.rebuild_jobs` columns confirmed `snapshot_sha256` is absent. The repository
migration that adds it is
[`supabase/ledgers/graph/migrations/20261016120000_add_snapshot_attestation.sql`](../../supabase/ledgers/graph/migrations/20261016120000_add_snapshot_attestation.sql).
The Vercel runtime error is therefore consistent with the Preview deployment using a graph schema older than the
current application expects. Do not run this migration against the dashboard's `main PRODUCTION` project as a way to
repair a Preview deployment. First identify or provision the approved staging database target and its distinct
role-scoped app/auth, graph, and coordination connection profiles. Apply the graph migration only through the
documented migration authority against that staging target, then verify the catalog and API. Recheck the `vc_handler`
wrapper message after a successful startup; investigate it as an independent Vercel runtime issue only if it persists
without the application startup exception.

The Vercel environment-variable API returned 403 and the local CLI reported no access to the Vercel account; no
secret values were read or changed. The browser's Vercel environment-variable list was visible, but dashboard
navigation to Supabase connection settings was blocked by another open extension panel. Once the staging DB and
connection profiles are established, set only Preview-scoped variables from those approved staging credentials.
Rebuild the API and confirm its actual deployment URL, then set Netlify's build-time `NEXT_PUBLIC_API_URL` to that
healthy API origin. Repeat health, visualization, and persisted-graph smoke checks before claiming persistence. Keep
these deployment IDs and observations as dated evidence; aliases and runtime logs may change or expire.

On 2026-11-20, the Supabase account inventory still showed the FarDb project `wjtqaevwapuzqivpyolc` with only its
`main` branch; no separate staging project or branch was listed. The maintainer reported that `DATABASE_URL`,
`ASSET_GRAPH_DATABASE_URL`, `COORDINATION_DATABASE_URL`, and `HOSTED_READINESS_BASE_URL` are configured on the GitHub
`staging` and `staging-manual-gate` Environments. This confirms reported secret presence only; it does not reveal or
verify their targets. Do not dispatch a staging qualification or point the UI at these values until the project ref
and API deployment are confirmed as staging. The previously shared project ref is production.

### Staging target provisioning attempt (2026-11-19)

The maintainer selected a new FarDb staging project or branch under the existing `mohavro.org` Supabase organization.
Supabase quoted a preview branch at `$0.01344/hour`; the maintainer explicitly approved that branch usage. Branch
creation was rejected because branching requires the Pro plan. A separate project was quoted at `$0/month`, but
creation was rejected because the organization already has its maximum two active Free projects. No existing project
was paused or deleted, and the organization plan was not upgraded. The Pro plan's published base price starts at
`$25/month`, with additional project and compute usage; that is a separate cost and requires explicit approval before
an upgrade. Consequently no FarDb staging target exists yet and no production database migration was applied.

## Change and release record

The architecture and deployment history support these boundaries:

- [PR #1340](https://github.com/DashFin-FarDb/financial-asset-relationship-db/pull/1340) addressed the frontend's
  FastAPI API base URL, not the Supabase Data API URL.
- [PR #1934](https://github.com/DashFin-FarDb/financial-asset-relationship-db/pull/1934) made Netlify a static UI
  deployment that fetches from a separate API.
- [PR #1870](https://github.com/DashFin-FarDb/financial-asset-relationship-db/pull/1870) and
  [PR #1871](https://github.com/DashFin-FarDb/financial-asset-relationship-db/pull/1871) define backend database
  authority and the authoritative graph lifecycle/persistence boundary.
- [PR #1936](https://github.com/DashFin-FarDb/financial-asset-relationship-db/pull/1936) addresses Netlify production
  build triggering; successful UI deployment remains separate from API and graph persistence verification.

For the broader target topology and database authority, see the
[enterprise deployment operating model](../enterprise-deployment-operating-model.md) and
[staging deployment operating baseline](../staging-deployment-operating-baseline.md).

## Official Supabase references

- [Data REST API](https://supabase.com/docs/guides/api)
- [Supabase and Vercel Marketplace integration](https://supabase.com/docs/guides/integrations/vercel-marketplace)
- [Supabase preview branches on Vercel](https://supabase.com/docs/guides/integrations/vercel-preview-branches)
