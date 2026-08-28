# FarDb local observability launcher

## Purpose and boundary

`scripts/observability/fardb-observability.ps1` starts and checks the complete supported local monitoring path:

- FastAPI on `127.0.0.1:8000`;
- Next.js on `127.0.0.1:3000`;
- Prometheus on `127.0.0.1:9090`; and
- the Grafana private data source connection (PDC) agent.

The launcher is deliberately local and fail-closed. It does not install software, create or change credentials,
register a browser protocol, change a dashboard, start local Grafana, or alter a provider. Grafana Alloy is a
separate optional forwarding path and is not started or required by this direct-PDC route.

The primary Grafana Cloud dashboard is `mogdpxw`, **FarDB Control Plane — Observability, SLOs & Lifecycle**. The
retained database dashboard is `modsl8n`, **FarDb-Supabase — Production SQL Endpoint Monitoring**. Opening a Grafana
page cannot execute this local script; the optional browser handoff remains separately scoped.

## Prerequisites

The default WSL distribution is `Ubuntu-26.04`. Use `-Distribution` only to select another already-configured
distribution with the same prerequisites.

The selected distribution must already contain:

- working WSL process creation and systemd user sessions;
- `/usr/bin/systemctl`, `/usr/bin/systemd-run`, `/usr/bin/curl`, `/usr/bin/sha256sum`, and `/usr/bin/ss`;
- system units `prometheus.service` and `grafana-pdc-agent.service`;
- `$HOME/.config/fardb-observability/runtime.env`;
- `$HOME/.local/share/fardb-observability/venv/bin/python` with the FarDb backend dependencies;
- npm at `/usr/local/bin/npm` or `/usr/bin/npm`; and
- the checkout's existing `frontend/node_modules` directory.

Windows Git must be available on `PATH`. The launcher derives the backend and frontend working directories from its
own repository checkout. It never prints the contents of `runtime.env`; it combines a one-way file digest with the
current Git revision, tracked changes, and untracked-file digests into a second one-way runtime fingerprint. Only that
final fingerprint is placed in the local unit description. Credential values must not be placed in command arguments.

The Supabase scrape is selected by the generic Prometheus job prefix `integrations/supabase/`; no provider
instance identifier is embedded in the launcher. If a local Prometheus configuration uses another label, set the
non-secret Windows environment variable `FARDB_SUPABASE_PROMETHEUS_JOB_PREFIX` before running the script. The
value is limited to a bounded set of literal job-label characters, must end with `/`, and is not evaluated as a
regular expression.

## One-time migration from legacy user units

The launcher owns only transient user units named `fardb-backend.service` and `fardb-frontend.service`. It refuses to
start if persistent units with those names are installed. When the earlier local prototype units are present, stop
the application and preserve them reversibly before using the launcher:

```bash
systemctl --user stop fardb-frontend.service fardb-backend.service
mv ~/.config/systemd/user/fardb-backend.service ~/.config/systemd/user/fardb-backend.service.legacy-1729
mv ~/.config/systemd/user/fardb-frontend.service ~/.config/systemd/user/fardb-frontend.service.legacy-1729
systemctl --user daemon-reload
```

Do not remove `runtime.env`, the existing Python environment, frontend dependencies, Prometheus configuration, or
the PDC installation.

## Commands

Run these commands from the repository root in Windows PowerShell:

```powershell
# Inspect without starting or stopping anything.
& .\scripts\observability\fardb-observability.ps1 -Action Status

# Start the full supported path and wait for both scrape targets.
& .\scripts\observability\fardb-observability.ps1 -Action Start

# Optional: override the non-secret Supabase Prometheus job-label prefix.
$env:FARDB_SUPABASE_PROMETHEUS_JOB_PREFIX = 'integrations/supabase/'
& .\scripts\observability\fardb-observability.ps1 -Action Start

# Also open four visible Windows Terminal log views.
& .\scripts\observability\fardb-observability.ps1 -Action Start -ShowLogs

# Stop only FastAPI and Next.js.
& .\scripts\observability\fardb-observability.ps1 -Action Stop

# Explicitly stop Prometheus and PDC as well.
& .\scripts\observability\fardb-observability.ps1 -Action Stop -StopInfrastructure
```

`Start` is idempotent. When an owned transient application unit is already active, it is left running only when its
command, working directory, environment-file path, and runtime-input fingerprint still match. A code or `runtime.env`
change causes the launcher to replace that exact transient unit before checking readiness. `Stop`
targets only the two exact transient application units unless `-StopInfrastructure` is supplied. Launcher actions are
serialized per WSL distribution; a concurrent invocation fails without changing services. Listening-process cgroups
must also match the expected exact units.

## Readiness contract

`Start` succeeds only when all four components and both required Prometheus targets are healthy. The default
readiness deadline is 75 seconds because the database target has a one-minute scrape interval; use
`-ReadinessTimeoutSeconds` only to choose another bounded 5–300 second window.

| Component          | Unit                                                  | Readiness                                                   |
| ------------------ | ----------------------------------------------------- | ----------------------------------------------------------- |
| FastAPI            | transient `fardb-backend.service`                     | Detailed graph/database readiness on port 8000              |
| Next.js            | transient `fardb-frontend.service`                    | HTTP 200 on port 3000                                       |
| Prometheus         | `prometheus.service`                                  | HTTP 200 from `/-/ready` on port 9090                       |
| Grafana PDC        | `grafana-pdc-agent.service`                           | HTTP 200 from its loopback metrics endpoint                 |
| Application scrape | `job="fardb_fastapi"`                                 | Targets API reports a healthy scrape made during this Start |
| Database scrape    | `job` starts with `integrations/supabase/` by default | Targets API reports every match healthy and freshly scraped |

FastAPI readiness uses `/api/health/detailed` and requires a healthy status, an available graph, configured durable
graph persistence, persistence enabled for the running graph, and a configured, reachable database. It does not
require `startup_source="persisted"` or `persistence_loaded=true`; the current approved local staging state may use the
documented empty-persistence fallback while the separate target-bound database proof is pending. The one configured
readiness timeout is a deadline for the complete Start action, not a fresh allowance for each sequential check.

Status output is bounded to component names, unit/target states, and HTTP status codes. Command stderr and response
bodies are not relayed, so secrets and sensitive payloads are not printed.

If a Start fails after changing service state, it stops only the exact application or infrastructure units that were
inactive when that invocation began. Services that were already active are preserved.

## Port conflicts

The launcher checks ports 8000, 3000, 9090, and the PDC health port before it starts anything. A listener is accepted
only when the corresponding exact systemd unit is active.

The known port-3000 conflict is a Homebrew/local Grafana service. The launcher reports the conflict and stops. It
does not terminate or reconfigure that service. Stop the identified local Grafana service explicitly, confirm port
3000 is free, and rerun `Start`. Grafana Cloud and PDC do not require the local Grafana service.

## WSL recovery

If even `/bin/true` cannot start in the selected distribution, the launcher changes nothing and reports a WSL
process-health failure. Use the normal host recovery path, for example:

1. run `wsl --shutdown`;
2. restart or repair WSL/Windows if process creation still fails; and
3. rerun `-Action Status` before `Start`.

The launcher never installs a distribution or downloads a repair payload.

## PDC and Alloy separation

Prometheus plus `grafana-pdc-agent.service` is the proven direct Grafana Cloud path. A PDC signing credential is for
PDC only. Do not reuse it for Alloy remote configuration or Prometheus remote-write. Alloy remains optional until a
separately scoped write/Alloy credential is proven locally; an unavailable Alloy configuration must not fail this
launcher.

## Rollback

To return to the preserved persistent user units:

1. run `-Action Stop`;
2. confirm both transient application units have unloaded;
3. restore the two `.legacy-1729` files to their original `.service` names;
4. run `systemctl --user daemon-reload`; and
5. start the restored units explicitly.

Stopping with `-StopInfrastructure` is reversible: start the exact Prometheus and PDC units again through the
launcher or `systemctl`. No dashboard, token, access policy, sharing setting, alert route, or hosted database state is
part of this rollback.
