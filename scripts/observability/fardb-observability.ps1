[CmdletBinding()]
param(
    [ValidateSet('Start', 'Status', 'Stop')]
    [string]$Action = 'Start',

    [string]$Distribution = 'Ubuntu-26.04',

    [switch]$ShowLogs,

    [switch]$StopInfrastructure
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:BackendUnit = 'fardb-backend.service'
$script:FrontendUnit = 'fardb-frontend.service'
$script:PrometheusUnit = 'prometheus.service'
$script:PdcUnit = 'grafana-pdc-agent.service'
$script:BackendPort = 8000
$script:FrontendPort = 3000
$script:PrometheusPort = 9090
$script:PdcMetricsPort = 8090
$script:BackendHealthUrl = 'http://127.0.0.1:8000/api/health'
$script:FrontendHealthUrl = 'http://127.0.0.1:3000/'
$script:PrometheusHealthUrl = 'http://127.0.0.1:9090/-/ready'
$script:PdcHealthUrl = 'http://127.0.0.1:8090/metrics'
$script:FastApiTargetUrl = (
    'http://127.0.0.1:9090/api/v1/query?query=' +
    'up%7Bjob%3D%22fardb_fastapi%22%7D'
)
$script:SupabaseTargetUrl = (
    'http://127.0.0.1:9090/api/v1/query?query=' +
    'up%7Bjob%3D%22integrations%2Fsupabase%2F2758727-metrics-endpoint-Fardb%22%7D'
)

function Throw-SafeError {
    param([Parameter(Mandatory)][string]$Message)

    throw [System.InvalidOperationException]::new($Message)
}

function Assert-DistributionNameSafe {
    if ($Distribution -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$') {
        Throw-SafeError 'The WSL distribution name contains unsupported characters.'
    }
}

function Assert-DistributionInstalled {
    $local:ErrorActionPreference = 'Continue'
    try {
        $installed = @(& wsl.exe --list --quiet 2>$null) |
            ForEach-Object { ($_ -replace "`0", '').Trim() } |
            Where-Object { $_ }
    } catch {
        Throw-SafeError 'The installed WSL distributions could not be inspected.'
    }
    if ($Distribution -notin $installed) {
        Throw-SafeError "Required WSL distribution is unavailable: $Distribution"
    }
}

function Invoke-WslCapture {
    param([Parameter(Mandatory)][string[]]$Arguments)

    $local:ErrorActionPreference = 'Continue'
    try {
        $captured = @(& wsl.exe -d $Distribution -- @Arguments 2>$null)
        $exitCode = $LASTEXITCODE
    } catch {
        $captured = @()
        $exitCode = 1
    }
    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = $captured
    }
}

function Invoke-WslRootCapture {
    param([Parameter(Mandatory)][string[]]$Arguments)

    $local:ErrorActionPreference = 'Continue'
    try {
        $captured = @(& wsl.exe -d $Distribution -u root -- @Arguments 2>$null)
        $exitCode = $LASTEXITCODE
    } catch {
        $captured = @()
        $exitCode = 1
    }
    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = $captured
    }
}

function Invoke-WslDiscard {
    param([Parameter(Mandatory)][string[]]$Arguments)

    $local:ErrorActionPreference = 'Continue'
    try {
        & wsl.exe -d $Distribution -- @Arguments 1>$null 2>$null
        return $LASTEXITCODE
    } catch {
        return 1
    }
}

function Invoke-WslRootDiscard {
    param([Parameter(Mandatory)][string[]]$Arguments)

    $local:ErrorActionPreference = 'Continue'
    try {
        & wsl.exe -d $Distribution -u root -- @Arguments 1>$null 2>$null
        return $LASTEXITCODE
    } catch {
        return 1
    }
}

function Assert-WslProcessHealthy {
    if ((Invoke-WslDiscard -Arguments @('/bin/true')) -ne 0) {
        Throw-SafeError (
            'WSL cannot create a process in the selected distribution. ' +
            'Run wsl --shutdown, repair or restart WSL, and retry; no services were changed.'
        )
    }
}

function Get-SingleWslValue {
    param(
        [Parameter(Mandatory)][string[]]$Arguments,
        [Parameter(Mandatory)][string]$FailureMessage
    )

    $result = Invoke-WslCapture -Arguments $Arguments
    $values = @($result.Output | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($result.ExitCode -ne 0 -or $values.Count -ne 1) {
        Throw-SafeError $FailureMessage
    }
    return $values[0]
}

function Assert-WslAbsolutePath {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Label
    )

    if (-not $Path.StartsWith('/') -or $Path.IndexOfAny([char[]]"`0`r`n") -ge 0) {
        Throw-SafeError "$Label did not resolve to a safe absolute WSL path."
    }
}

function Initialize-LauncherPaths {
    $repoRootWindows = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
    if ($repoRootWindows -notmatch '^([A-Za-z]):\\(.+)$') {
        Throw-SafeError 'The repository is not on a supported local Windows drive.'
    }
    $homePathRequest = @{
        Arguments = @('/usr/bin/printenv', 'HOME')
        FailureMessage = 'The WSL user home directory could not be resolved.'
    }
    $drive = $Matches[1].ToLowerInvariant()
    $relativePath = $Matches[2].Replace('\', '/')
    $script:RepoRootWsl = "/mnt/$drive/$relativePath"
    $script:WslHome = Get-SingleWslValue @homePathRequest

    Assert-WslAbsolutePath -Path $script:RepoRootWsl -Label 'Repository root'
    Assert-WslAbsolutePath -Path $script:WslHome -Label 'WSL home'

    $script:FrontendRootWsl = "$($script:RepoRootWsl)/frontend"
    $script:RuntimeEnvPath = "$($script:WslHome)/.config/fardb-observability/runtime.env"
    $script:PythonPath = "$($script:WslHome)/.local/share/fardb-observability/venv/bin/python"
    $script:NpmPath = '/usr/local/bin/npm'
}

function Test-WslPath {
    param(
        [Parameter(Mandatory)][ValidateSet('file', 'directory', 'executable')][string]$Kind,
        [Parameter(Mandatory)][string]$Path
    )

    $testFlag = switch ($Kind) {
        'file' { '-f' }
        'directory' { '-d' }
        'executable' { '-x' }
    }
    return (Invoke-WslDiscard -Arguments @('/usr/bin/test', $testFlag, $Path)) -eq 0
}

function Get-UserUnitProperty {
    param(
        [Parameter(Mandatory)][string]$Unit,
        [Parameter(Mandatory)][string]$Property
    )

    $result = Invoke-WslCapture -Arguments @(
        '/usr/bin/systemctl', '--user', 'show', $Unit, "--property=$Property", '--value', '--no-pager'
    )
    if ($result.ExitCode -ne 0) { return '' }
    return (@($result.Output) | Select-Object -First 1).Trim()
}

function Get-SystemUnitProperty {
    param(
        [Parameter(Mandatory)][string]$Unit,
        [Parameter(Mandatory)][string]$Property
    )

    $result = Invoke-WslRootCapture -Arguments @(
        '/usr/bin/systemctl', 'show', $Unit, "--property=$Property", '--value', '--no-pager'
    )
    if ($result.ExitCode -ne 0) { return '' }
    return (@($result.Output) | Select-Object -First 1).Trim()
}

function Get-UserUnitState {
    param([Parameter(Mandatory)][string]$Unit)

    if ((Get-UserUnitProperty -Unit $Unit -Property 'LoadState') -ne 'loaded') { return 'inactive' }
    $state = Get-UserUnitProperty -Unit $Unit -Property 'ActiveState'
    if (-not $state) { return 'inactive' }
    return $state
}

function Get-SystemUnitState {
    param([Parameter(Mandatory)][string]$Unit)

    if ((Get-SystemUnitProperty -Unit $Unit -Property 'LoadState') -ne 'loaded') { return 'unavailable' }
    $state = Get-SystemUnitProperty -Unit $Unit -Property 'ActiveState'
    if (-not $state) { return 'inactive' }
    return $state
}

function Assert-TransientUnitCompatible {
    param([Parameter(Mandatory)][string]$Unit)

    $loadState = Get-UserUnitProperty -Unit $Unit -Property 'LoadState'
    if (-not $loadState -or $loadState -eq 'not-found') { return }
    if ($loadState -ne 'loaded') {
        Throw-SafeError "The application unit is not in a usable state: $Unit"
    }
    if ((Get-UserUnitProperty -Unit $Unit -Property 'Transient') -ne 'yes') {
        Throw-SafeError (
            "A persistent legacy unit conflicts with the required transient unit: $Unit. " +
            'Follow the documented reversible migration before retrying.'
        )
    }
}

function Assert-Prerequisites {
    $requiredExecutables = @(
        @{ Path = '/usr/bin/curl'; Label = 'curl' },
        @{ Path = '/usr/bin/ss'; Label = 'ss' },
        @{ Path = '/usr/bin/systemctl'; Label = 'systemctl' },
        @{ Path = '/usr/bin/systemd-run'; Label = 'systemd-run' },
        @{ Path = $script:PythonPath; Label = 'the existing FarDb Python environment' },
        @{ Path = $script:NpmPath; Label = 'the existing npm installation' }
    )
    foreach ($requirement in $requiredExecutables) {
        if (-not (Test-WslPath -Kind 'executable' -Path $requirement.Path)) {
            Throw-SafeError "Required prerequisite is unavailable: $($requirement.Label)."
        }
    }
    if (-not (Test-WslPath -Kind 'file' -Path $script:RuntimeEnvPath)) {
        Throw-SafeError 'The existing FarDb runtime.env file is unavailable.'
    }
    if (-not (Test-WslPath -Kind 'directory' -Path "$($script:FrontendRootWsl)/node_modules")) {
        Throw-SafeError 'The existing frontend dependencies are unavailable.'
    }
    foreach ($unit in @($script:PrometheusUnit, $script:PdcUnit)) {
        if ((Get-SystemUnitProperty -Unit $unit -Property 'LoadState') -ne 'loaded') {
            Throw-SafeError "Required infrastructure unit is unavailable: $unit"
        }
    }
}

function Get-HttpStatus {
    param([Parameter(Mandatory)][string]$Url)

    $result = Invoke-WslCapture -Arguments @(
        '/usr/bin/curl', '--silent', '--show-error', '--output', '/dev/null',
        '--max-time', '3', '--write-out', '%{http_code}', $Url
    )
    if ($result.ExitCode -ne 0) { return 0 }
    $rawStatus = (@($result.Output) -join '').Trim()
    $status = 0
    if (-not [int]::TryParse($rawStatus, [ref]$status)) { return 0 }
    return $status
}

function Test-WslPortListening {
    param([Parameter(Mandatory)][int]$Port)

    $result = Invoke-WslCapture -Arguments @('/usr/bin/ss', '-H', '-ltn', "sport = :$Port")
    return $result.ExitCode -eq 0 -and @($result.Output | Where-Object { $_.Trim() }).Count -gt 0
}

function Assert-PortOwnedByUnit {
    param(
        [Parameter(Mandatory)][int]$Port,
        [Parameter(Mandatory)][string]$Unit,
        [Parameter(Mandatory)][ValidateSet('user', 'system')][string]$Scope,
        [Parameter(Mandatory)][string]$RecoveryMessage
    )

    if (-not (Test-WslPortListening -Port $Port)) { return }
    $unitState = if ($Scope -eq 'user') {
        Get-UserUnitState -Unit $Unit
    } else {
        Get-SystemUnitState -Unit $Unit
    }
    if ($unitState -ne 'active') {
        Throw-SafeError $RecoveryMessage
    }
}

function Start-Infrastructure {
    $exitCode = Invoke-WslRootDiscard -Arguments @(
        '/usr/bin/systemctl', 'start', $script:PrometheusUnit, $script:PdcUnit
    )
    if ($exitCode -ne 0) {
        Throw-SafeError 'Prometheus or Grafana PDC failed to start; inspect the exact system units locally.'
    }
}

function Wait-TransientUnitUnloaded {
    param([Parameter(Mandatory)][string]$Unit)

    for ($attempt = 1; $attempt -le 20; $attempt++) {
        $loadState = Get-UserUnitProperty -Unit $Unit -Property 'LoadState'
        if (-not $loadState -or $loadState -eq 'not-found') { return }
        Start-Sleep -Milliseconds 100
    }
    Throw-SafeError "The prior transient unit did not unload cleanly: $Unit"
}

function Start-TransientUserUnit {
    param(
        [Parameter(Mandatory)][string]$Unit,
        [Parameter(Mandatory)][string]$WorkingDirectory,
        [Parameter(Mandatory)][string[]]$Command
    )

    if ((Get-UserUnitState -Unit $Unit) -eq 'active') { return }

    $loadState = Get-UserUnitProperty -Unit $Unit -Property 'LoadState'
    if ($loadState -eq 'loaded') {
        [void](Invoke-WslDiscard -Arguments @('/usr/bin/systemctl', '--user', 'reset-failed', $Unit))
        Wait-TransientUnitUnloaded -Unit $Unit
    }

    $arguments = @(
        '/usr/bin/systemd-run', '--user', "--unit=$Unit", '--collect', '--quiet',
        '--property=Type=simple', "--property=WorkingDirectory=$WorkingDirectory",
        "--property=EnvironmentFile=$($script:RuntimeEnvPath)", '--'
    ) + $Command
    if ((Invoke-WslDiscard -Arguments $arguments) -ne 0) {
        Throw-SafeError "The transient application unit failed to start: $Unit"
    }
}

function Start-Application {
    $backendWasActive = (Get-UserUnitState -Unit $script:BackendUnit) -eq 'active'
    $backendStart = @{
        Unit = $script:BackendUnit
        WorkingDirectory = $script:RepoRootWsl
        Command = @(
            $script:PythonPath, '-m', 'uvicorn', 'api.main:app',
            '--host', '127.0.0.1', '--port', "$($script:BackendPort)"
        )
    }
    Start-TransientUserUnit @backendStart
    try {
        $frontendStart = @{
            Unit = $script:FrontendUnit
            WorkingDirectory = $script:FrontendRootWsl
            Command = @(
                $script:NpmPath, 'run', 'dev', '--',
                '--hostname', '127.0.0.1', '--port', "$($script:FrontendPort)"
            )
        }
        Start-TransientUserUnit @frontendStart
    } catch {
        if (-not $backendWasActive) {
            [void](Invoke-WslDiscard -Arguments @('/usr/bin/systemctl', '--user', 'stop', $script:BackendUnit))
        }
        throw
    }
}

function Wait-HttpReady {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Url,
        [int]$Attempts = 30
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        if ((Get-HttpStatus -Url $Url) -eq 200) { return }
        Start-Sleep -Seconds 1
    }
    Throw-SafeError "$Name did not become ready within $Attempts seconds."
}

function Test-PrometheusTargetUp {
    param([Parameter(Mandatory)][string]$QueryUrl)

    $result = Invoke-WslCapture -Arguments @('/usr/bin/curl', '--silent', '--show-error', '--max-time', '3', $QueryUrl)
    if ($result.ExitCode -ne 0) { return $false }
    try {
        $document = ((@($result.Output) -join "`n") | ConvertFrom-Json -ErrorAction Stop)
        $series = @($document.data.result)
        return $document.status -eq 'success' -and $series.Count -gt 0 -and @(
            $series | Where-Object { @($_.value).Count -lt 2 -or "$($_.value[1])" -ne '1' }
        ).Count -eq 0
    } catch {
        return $false
    }
}

function Wait-PrometheusTargetUp {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$QueryUrl,
        [int]$Attempts = 30
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        if (Test-PrometheusTargetUp -QueryUrl $QueryUrl) { return }
        Start-Sleep -Seconds 1
    }
    Throw-SafeError "$Name did not report up within $Attempts seconds."
}

function Write-StatusRow {
    param(
        [Parameter(Mandatory)][string]$Component,
        [Parameter(Mandatory)][string]$State,
        [Parameter(Mandatory)]$HttpStatus
    )

    Write-Output ("{0}: state={1}; http={2}" -f $Component, $State, $HttpStatus)
}

function Show-Status {
    $backendStatus = @{
        Component = 'FarDb backend'
        State = Get-UserUnitState -Unit $script:BackendUnit
        HttpStatus = Get-HttpStatus -Url $script:BackendHealthUrl
    }
    $frontendStatus = @{
        Component = 'FarDb frontend'
        State = Get-UserUnitState -Unit $script:FrontendUnit
        HttpStatus = Get-HttpStatus -Url $script:FrontendHealthUrl
    }
    $prometheusStatus = @{
        Component = 'Prometheus'
        State = Get-SystemUnitState -Unit $script:PrometheusUnit
        HttpStatus = Get-HttpStatus -Url $script:PrometheusHealthUrl
    }
    $pdcStatus = @{
        Component = 'Grafana PDC'
        State = Get-SystemUnitState -Unit $script:PdcUnit
        HttpStatus = Get-HttpStatus -Url $script:PdcHealthUrl
    }
    Write-StatusRow @backendStatus
    Write-StatusRow @frontendStatus
    Write-StatusRow @prometheusStatus
    Write-StatusRow @pdcStatus

    $fastApiState = if (Test-PrometheusTargetUp -QueryUrl $script:FastApiTargetUrl) { 'up' } else { 'down' }
    $supabaseState = if (Test-PrometheusTargetUp -QueryUrl $script:SupabaseTargetUrl) { 'up' } else { 'down' }
    Write-StatusRow -Component 'Prometheus target fardb_fastapi' -State $fastApiState -HttpStatus 'n/a'
    Write-StatusRow -Component 'Prometheus target Supabase' -State $supabaseState -HttpStatus 'n/a'
}

function Open-LogWindows {
    if (-not (Get-Command wt.exe -ErrorAction SilentlyContinue)) {
        Write-Warning 'Windows Terminal is unavailable; services remain running without visible log windows.'
        return
    }

    $windows = @(
        @('-w', 'new', 'new-tab', '--title', 'FarDb-API', 'wsl.exe', '-d', $Distribution, '--',
            '/usr/bin/journalctl', '--user', '-fu', $script:BackendUnit),
        @('-w', 'new', 'new-tab', '--title', 'FarDb-Frontend', 'wsl.exe', '-d', $Distribution, '--',
            '/usr/bin/journalctl', '--user', '-fu', $script:FrontendUnit),
        @('-w', 'new', 'new-tab', '--title', 'FarDb-Prometheus', 'wsl.exe', '-d', $Distribution, '-u', 'root', '--',
            '/usr/bin/journalctl', '-fu', $script:PrometheusUnit),
        @('-w', 'new', 'new-tab', '--title', 'FarDb-PDC', 'wsl.exe', '-d', $Distribution, '-u', 'root', '--',
            '/usr/bin/journalctl', '-fu', $script:PdcUnit)
    )

    foreach ($windowArguments in $windows) {
        try {
            Start-Process -FilePath 'wt.exe' -ArgumentList $windowArguments | Out-Null
            Start-Sleep -Milliseconds 250
        } catch {
            Write-Warning 'A log window could not be opened; the corresponding service remains running.'
        }
    }
}

function Start-Observability {
    Assert-Prerequisites
    Assert-TransientUnitCompatible -Unit $script:BackendUnit
    Assert-TransientUnitCompatible -Unit $script:FrontendUnit

    $backendPortCheck = @{
        Port = $script:BackendPort
        Unit = $script:BackendUnit
        Scope = 'user'
        RecoveryMessage = 'Port 8000 is owned by an unrecognised process; stop it explicitly before retrying.'
    }
    $frontendPortCheck = @{
        Port = $script:FrontendPort
        Unit = $script:FrontendUnit
        Scope = 'user'
        RecoveryMessage = (
            'Port 3000 is owned by an unrecognised process. Stop the Homebrew/local Grafana service or other ' +
            'conflicting process explicitly before retrying; the launcher will not terminate it.'
        )
    }
    $prometheusPortCheck = @{
        Port = $script:PrometheusPort
        Unit = $script:PrometheusUnit
        Scope = 'system'
        RecoveryMessage = 'Port 9090 is owned by a process outside prometheus.service; stop it explicitly before retrying.'
    }
    $pdcPortCheck = @{
        Port = $script:PdcMetricsPort
        Unit = $script:PdcUnit
        Scope = 'system'
        RecoveryMessage = 'The Grafana PDC health port is owned by an unrecognised process; stop it explicitly before retrying.'
    }
    Assert-PortOwnedByUnit @backendPortCheck
    Assert-PortOwnedByUnit @frontendPortCheck
    Assert-PortOwnedByUnit @prometheusPortCheck
    Assert-PortOwnedByUnit @pdcPortCheck

    Start-Infrastructure
    Start-Application

    Wait-HttpReady -Name 'Prometheus' -Url $script:PrometheusHealthUrl
    Wait-HttpReady -Name 'FarDb backend' -Url $script:BackendHealthUrl
    Wait-HttpReady -Name 'FarDb frontend' -Url $script:FrontendHealthUrl
    Wait-HttpReady -Name 'Grafana PDC' -Url $script:PdcHealthUrl
    Wait-PrometheusTargetUp -Name 'The FastAPI Prometheus target' -QueryUrl $script:FastApiTargetUrl
    Wait-PrometheusTargetUp -Name 'The Supabase Prometheus target' -QueryUrl $script:SupabaseTargetUrl

    Show-Status
    if ($ShowLogs) { Open-LogWindows }
}

function Stop-TransientUserUnit {
    param([Parameter(Mandatory)][string]$Unit)

    $loadState = Get-UserUnitProperty -Unit $Unit -Property 'LoadState'
    if (-not $loadState -or $loadState -eq 'not-found') { return }
    Assert-TransientUnitCompatible -Unit $Unit
    if ((Invoke-WslDiscard -Arguments @('/usr/bin/systemctl', '--user', 'stop', $Unit)) -ne 0) {
        Throw-SafeError "The transient application unit did not stop cleanly: $Unit"
    }
}

function Stop-Observability {
    Stop-TransientUserUnit -Unit $script:FrontendUnit
    Stop-TransientUserUnit -Unit $script:BackendUnit

    if ($StopInfrastructure) {
        if ((Invoke-WslRootDiscard -Arguments @(
            '/usr/bin/systemctl', 'stop', $script:PdcUnit, $script:PrometheusUnit
        )) -ne 0) {
            Throw-SafeError 'Prometheus or Grafana PDC did not stop cleanly.'
        }
    }
    Show-Status
}

try {
    Assert-DistributionNameSafe
    Assert-DistributionInstalled
    Assert-WslProcessHealthy
    Initialize-LauncherPaths

    switch ($Action) {
        'Start' { Start-Observability }
        'Status' { Show-Status }
        'Stop' { Stop-Observability }
    }
} catch {
    Write-Error ("FarDb observability launcher: {0}" -f $_.Exception.Message)
    exit 1
}
