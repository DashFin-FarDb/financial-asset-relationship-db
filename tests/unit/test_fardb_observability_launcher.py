"""Static and parser contract tests for the FarDb local observability launcher."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "observability" / "fardb-observability.ps1"
DOCUMENTATION_PATH = REPO_ROOT / "docs" / "operations" / "fardb-local-observability.md"


def _script() -> str:
    """Return the launcher as UTF-8 text."""

    return SCRIPT_PATH.read_text(encoding="utf-8")


def _documentation() -> str:
    """Return the launcher runbook as UTF-8 text."""

    return DOCUMENTATION_PATH.read_text(encoding="utf-8")


def test_powershell_parser_accepts_launcher() -> None:
    """PowerShell's parser must accept the checked-in launcher when available."""

    executable = shutil.which("pwsh") or shutil.which("powershell")
    if executable is None:
        pytest.skip("PowerShell is unavailable on this runner")
    assert executable is not None

    escaped_path = str(SCRIPT_PATH).replace("'", "''")
    parser_command = (
        "$tokens=$null; $errors=$null; "
        f"[System.Management.Automation.Language.Parser]::ParseFile('{escaped_path}', "
        "[ref]$tokens, [ref]$errors) > $null; "
        "if ($errors.Count -gt 0) { $errors | ForEach-Object { Write-Error $_.Message }; exit 1 }"
    )
    result = subprocess.run(
        [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", parser_command],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_fixed_distribution_actions_units_and_ports() -> None:
    """The launcher must retain the issue's fixed distribution, actions, units, and ports."""

    text = _script()
    for expected in (
        "[ValidateSet('Start', 'Status', 'Stop')]",
        "[string]$Distribution = 'Ubuntu-26.04'",
        "fardb-backend.service",
        "fardb-frontend.service",
        "prometheus.service",
        "grafana-pdc-agent.service",
        "$script:BackendPort = 8000",
        "$script:FrontendPort = 3000",
        "$script:PrometheusPort = 9090",
    ):
        assert expected in text


def test_both_production_application_sides_are_transient_and_required() -> None:
    """FastAPI and Next.js must be launched as exact transient user units."""

    text = _script()
    assert "'/usr/bin/systemd-run', '--user'" in text
    assert "\"--unit=$Unit\", '--collect'" in text
    assert '"--property=WorkingDirectory=$WorkingDirectory"' in text
    assert '"--property=EnvironmentFile=$($script:RuntimeEnvPath)"' in text
    assert "'uvicorn', 'api.main:app'" in text
    assert "'run', 'dev', '--'" in text
    assert "Invoke-TransientUserUnitStart" in text


def test_existing_local_prerequisites_are_fail_closed() -> None:
    """The launcher must require existing runtime assets without creating them."""

    text = _script()
    for expected in (
        ".config/fardb-observability/runtime.env",
        ".local/share/fardb-observability/venv/bin/python",
        "/usr/local/bin/npm",
        "/usr/bin/npm",
        '"$($script:FrontendRootWsl)/node_modules"',
        "Assert-WslProcessHealthy",
        "Assert-Prerequisite",
    ):
        assert expected in text


def test_no_install_download_provider_or_alloy_behavior() -> None:
    """The launcher must not install, download, mutate providers, or start Alloy."""

    lowered = _script().lower()
    forbidden = (
        "invoke-webrequest",
        "start-bitstransfer",
        "apt-get",
        "winget",
        "choco",
        "wget",
        "docker",
        "alloy",
        "remote-write",
        "grafana api",
        "supabase api",
    )
    for marker in forbidden:
        assert marker not in lowered


def test_stop_boundaries_never_use_broad_process_termination() -> None:
    """Stop must address exact systemd units and never kill by process name or port."""

    text = _script()
    lowered = text.lower()
    for marker in ("stop-process", "taskkill", "pkill", "killall", "get-process"):
        assert marker not in lowered
    assert "Invoke-TransientUserUnitStop -Unit $script:FrontendUnit" in text
    assert "Invoke-TransientUserUnitStop -Unit $script:BackendUnit" in text
    assert "if ($StopInfrastructure)" in text
    assert re.search(r"'stop',\s*\$script:PdcUnit,\s*\$script:PrometheusUnit", text)


def test_health_contract_covers_components_and_both_targets() -> None:
    """Readiness must cover all four components and both current Prometheus jobs."""

    text = _script()
    for expected in (
        "http://127.0.0.1:8000/api/health/detailed",
        "Test-FastApiReady",
        "$document.graph_persistence_configured -eq $true",
        "$document.graph.persistence_enabled -eq $true",
        "$document.database.reachable -eq $true",
        "http://127.0.0.1:3000/",
        "http://127.0.0.1:9090/-/ready",
        "http://127.0.0.1:8090/metrics",
        "fardb_fastapi",
        "FARDB_SUPABASE_PROMETHEUS_JOB_PREFIX",
        "integrations/supabase/",
        "SupabasePrometheusJobPrefix.EndsWith('/')",
        "Wait-PrometheusTargetsUp",
        "lastScrape",
        "PrometheusTargetsUrl",
    ):
        assert expected in text
    assert "2758727-metrics-endpoint-Fardb" not in text


def test_start_safety_covers_concurrency_identity_port_ownership_and_rollback() -> None:
    """Start must fail closed around concurrent, stale, conflicting, or partial state."""

    text = _script()
    for expected in (
        "Enter-LauncherMutex",
        "Test-ActiveTransientUnitMatch",
        "Get-TransientUnitIdentity",
        "Initialize-RuntimeInputFingerprint",
        "Get-RepositoryRuntimeFingerprint",
        "'/usr/bin/sha256sum'",
        "Invoke-LocalGit",
        "'--no-textconv', '--binary', 'HEAD'",
        "'ls-files', '--others', '--exclude-standard'",
        "--property=Description=",
        "Test-WslPortOwnedByUnit",
        "ControlGroup",
        '"/proc/$listenerPid/cgroup"',
        "Restore-InitialServiceState",
        "Get-BackendStartParameters",
        "Get-FrontendStartParameters",
        "Rollback could not restore the previously active backend unit.",
        "Rollback could not restore the previously active frontend unit.",
        "Get-ReadinessSecondsRemaining",
        "$readinessDeadline",
        "ReadinessTimeoutSeconds",
    ):
        assert expected in text


def test_log_views_are_explicit_and_visible_only_on_request() -> None:
    """The optional log action must open four named Windows Terminal views."""

    text = _script()
    assert "if ($ShowLogs) { Open-LogWindows }" in text
    for title in ("FarDb-API", "FarDb-Frontend", "FarDb-Prometheus", "FarDb-PDC"):
        assert title in text
    assert "Start-Process -FilePath 'wt.exe'" in text


def test_errors_and_status_output_are_bounded() -> None:
    """External stderr and HTTP bodies must not be relayed to launcher output."""

    text = _script()
    assert "2>$null" in text
    assert "$local:ErrorActionPreference = 'Continue'" in text
    assert "--output', '/dev/null'" in text
    assert "Component names, states" not in text
    assert "Write-StatusRow" in text
    assert 'Write-Error ("FarDb observability launcher: {0}"' in text


def test_runbook_documents_recovery_rollback_and_security_boundaries() -> None:
    """The runbook must cover the operational and credential boundaries from issue #1729."""

    text = _documentation()
    for expected in (
        "One-time migration from legacy user units",
        "-Action Start",
        "-Action Status",
        "-Action Stop",
        "-StopInfrastructure",
        "Homebrew/local Grafana",
        "PDC and Alloy separation",
        "Do not reuse it for Alloy",
        "Rollback",
        "wsl --shutdown",
        "mogdpxw",
        "modsl8n",
    ):
        assert expected in text
