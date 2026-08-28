[CmdletBinding()]
param(
    [ValidateSet('Start', 'Status', 'Stop')]
    [string]$Action = 'Start',

    [string]$Distribution = 'Ubuntu-26.04',

    [string]$SupabasePrometheusJobPrefix = $env:FARDB_SUPABASE_PROMETHEUS_JOB_PREFIX,

    [ValidateRange(5, 300)][int]$ReadinessTimeoutSeconds = 75,

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
$script:PrometheusTargetsUrl = 'http://127.0.0.1:9090/api/v1/targets?state=active'
$script:FastApiTargetJob = 'fardb_fastapi'
$script:LauncherMutex = $null
$script:LauncherMutexOwned = $false

function Throw-SafeError {
    param([Parameter(Mandatory)][string]$Message)

    throw [System.InvalidOperationException]::new($Message)
}

function Assert-DistributionNameSafe {
    if ($Distribution -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$') {
        Throw-SafeError 'The WSL distribution name contains unsupported characters.'
    }
}

function Enter-LauncherMutex {
    $mutexName = "Local\FarDb-Observability-$Distribution"
    $script:LauncherMutex = [Threading.Mutex]::new($false, $mutexName)
    try {
        $script:LauncherMutexOwned = $script:LauncherMutex.WaitOne(0)
    } catch [Threading.AbandonedMutexException] {
        $script:LauncherMutexOwned = $true
    }
    if (-not $script:LauncherMutexOwned) {
        $script:LauncherMutex.Dispose()
        $script:LauncherMutex = $null
        Throw-SafeError 'Another FarDb observability launcher invocation is already active.'
    }
}

function Exit-LauncherMutex {
    if ($script:LauncherMutexOwned) {
        $script:LauncherMutex.ReleaseMutex()
        $script:LauncherMutexOwned = $false
    }
    if ($null -ne $script:LauncherMutex) {
        $script:LauncherMutex.Dispose()
        $script:LauncherMutex = $null
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

function Invoke-WslCommand {
    param(
        [Parameter(Mandatory)][string[]]$Arguments,
        [ValidateSet('user', 'root')][string]$Identity = 'user',
        [switch]$Capture
    )

    $local:ErrorActionPreference = 'Continue'
    $wslArguments = @('-d', $Distribution)
    if ($Identity -eq 'root') { $wslArguments += @('-u', 'root') }
    $wslArguments += @('--') + $Arguments

    try {
        if ($Capture) {
            $captured = @(& wsl.exe @wslArguments 2>$null)
            return [pscustomobject]@{
                ExitCode = $LASTEXITCODE
                Output = $captured
            }
        }
        & wsl.exe @wslArguments 1>$null 2>$null
        return $LASTEXITCODE
    } catch {
        if ($Capture) {
            return [pscustomobject]@{
                ExitCode = 1
                Output = @()
            }
        }
        return 1
    }
}

function Assert-WslProcessHealthy {
    if ((Invoke-WslCommand -Arguments @('/bin/true')) -ne 0) {
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

    $result = Invoke-WslCommand -Arguments $Arguments -Capture
    $values = @($result.Output | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($result.ExitCode -ne 0 -or $values.Count -ne 1) {
        Throw-SafeError $FailureMessage
    }
    return $values[0]
}

function Resolve-WslExecutablePath {
    param(
        [Parameter(Mandatory)][string[]]$Candidates,
        [Parameter(Mandatory)][string]$Label
    )

    foreach ($candidate in $Candidates) {
        if (Test-WslPath -Kind 'executable' -Path $candidate) { return $candidate }
    }
    Throw-SafeError "Required prerequisite is unavailable: $Label."
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
    if ([string]::IsNullOrWhiteSpace($PSScriptRoot)) {
        Throw-SafeError 'The launcher must be run from its script file.'
    }
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
    $script:NpmPath = Resolve-WslExecutablePath -Candidates @('/usr/local/bin/npm', '/usr/bin/npm') -Label 'npm'
}

function Initialize-PrometheusTargetSettings {
    if ([string]::IsNullOrWhiteSpace($SupabasePrometheusJobPrefix)) {
        $SupabasePrometheusJobPrefix = 'integrations/supabase/'
    }
    if (
        $SupabasePrometheusJobPrefix.Length -gt 128 -or
        $SupabasePrometheusJobPrefix -notmatch '^[A-Za-z0-9_./:-]+$'
    ) {
        Throw-SafeError 'The Supabase Prometheus job prefix contains unsupported characters.'
    }
    $script:SupabaseTargetJobPrefix = $SupabasePrometheusJobPrefix
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
    return (Invoke-WslCommand -Arguments @('/usr/bin/test', $testFlag, $Path)) -eq 0
}

function Get-UnitProperty {
    param(
        [Parameter(Mandatory)][string]$Unit,
        [Parameter(Mandatory)][string]$Property,
        [Parameter(Mandatory)][ValidateSet('user', 'system')][string]$Scope
    )

    $arguments = @('/usr/bin/systemctl')
    if ($Scope -eq 'user') { $arguments += @('--user') }
    $arguments += @('show', $Unit, "--property=$Property", '--value', '--no-pager')
    $identity = if ($Scope -eq 'system') { 'root' } else { 'user' }
    $result = Invoke-WslCommand -Arguments $arguments -Identity $identity -Capture
    if ($result.ExitCode -ne 0) { return '' }
    return (@($result.Output) | Select-Object -First 1).Trim()
}

function Get-UnitState {
    param(
        [Parameter(Mandatory)][string]$Unit,
        [Parameter(Mandatory)][ValidateSet('user', 'system')][string]$Scope
    )

    $loadState = Get-UnitProperty -Unit $Unit -Property 'LoadState' -Scope $Scope
    if ($loadState -ne 'loaded') {
        if ($Scope -eq 'system') { return 'unavailable' }
        return 'inactive'
    }
    $state = Get-UnitProperty -Unit $Unit -Property 'ActiveState' -Scope $Scope
    if (-not $state) { return 'inactive' }
    return $state
}

function Assert-ActiveTransientUnitMatches {
    param(
        [Parameter(Mandatory)][string]$Unit,
        [Parameter(Mandatory)][string]$WorkingDirectory,
        [Parameter(Mandatory)][string[]]$Command
    )

    $actualDirectory = Get-UnitProperty -Unit $Unit -Property 'WorkingDirectory' -Scope 'user'
    $actualEnvironment = Get-UnitProperty -Unit $Unit -Property 'EnvironmentFiles' -Scope 'user'
    $actualDescription = Get-UnitProperty -Unit $Unit -Property 'Description' -Scope 'user'
    $expectedEnvironment = "$($script:RuntimeEnvPath) (ignore_errors=no)"
    $expectedDescription = Get-TransientUnitIdentity -WorkingDirectory $WorkingDirectory -Command $Command
    if ($actualDirectory -ne $WorkingDirectory) {
        Throw-SafeError "The active transient unit belongs to another launcher configuration: $Unit"
    }
    if ($actualEnvironment -ne $expectedEnvironment) {
        Throw-SafeError "The active transient unit belongs to another launcher configuration: $Unit"
    }
    if ($actualDescription -ne $expectedDescription) {
        Throw-SafeError "The active transient unit belongs to another launcher configuration: $Unit"
    }
}

function Get-TransientUnitIdentity {
    param(
        [Parameter(Mandatory)][string]$WorkingDirectory,
        [Parameter(Mandatory)][string[]]$Command
    )

    $identityMaterial = (@($WorkingDirectory, $script:RuntimeEnvPath) + $Command) -join "`0"
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        $digest = $algorithm.ComputeHash([Text.Encoding]::UTF8.GetBytes($identityMaterial))
    } finally {
        $algorithm.Dispose()
    }
    $fingerprint = ([BitConverter]::ToString($digest)).Replace('-', '').ToLowerInvariant()
    return "FarDb observability launcher $fingerprint"
}

function Assert-TransientUnitCompatible {
    param([Parameter(Mandatory)][string]$Unit)

    $loadState = Get-UnitProperty -Unit $Unit -Property 'LoadState' -Scope 'user'
    if (-not $loadState -or $loadState -eq 'not-found') { return }
    if ($loadState -ne 'loaded') {
        Throw-SafeError "The application unit is not in a usable state: $Unit"
    }
    if ((Get-UnitProperty -Unit $Unit -Property 'Transient' -Scope 'user') -ne 'yes') {
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
        Assert-WslPathAvailable -Kind 'executable' -Path $requirement.Path -Label $requirement.Label
    }
    Assert-WslPathAvailable -Kind 'file' -Path $script:RuntimeEnvPath -Label 'the existing FarDb runtime.env file'
    Assert-WslPathAvailable -Kind 'directory' -Path "$($script:FrontendRootWsl)/node_modules" `
        -Label 'the existing frontend dependencies'
    foreach ($unit in @($script:PrometheusUnit, $script:PdcUnit)) {
        Assert-SystemUnitAvailable -Unit $unit
    }
}

function Assert-WslPathAvailable {
    param(
        [Parameter(Mandatory)][ValidateSet('file', 'directory', 'executable')][string]$Kind,
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Label
    )

    if (-not (Test-WslPath -Kind $Kind -Path $Path)) {
        Throw-SafeError "Required prerequisite is unavailable: $Label."
    }
}

function Assert-SystemUnitAvailable {
    param([Parameter(Mandatory)][string]$Unit)

    if ((Get-UnitProperty -Unit $Unit -Property 'LoadState' -Scope 'system') -ne 'loaded') {
        Throw-SafeError "Required infrastructure unit is unavailable: $Unit"
    }
}

function Get-HttpStatus {
    param([Parameter(Mandatory)][string]$Url)

    $result = Invoke-WslCommand -Arguments @(
        '/usr/bin/curl', '--silent', '--show-error', '--output', '/dev/null',
        '--max-time', '1', '--write-out', '%{http_code}', $Url
    ) -Capture
    if ($result.ExitCode -ne 0) { return 0 }
    $rawStatus = (@($result.Output) -join '').Trim()
    $status = 0
    if (-not [int]::TryParse($rawStatus, [ref]$status)) { return 0 }
    return $status
}

function Test-WslPortListening {
    param([Parameter(Mandatory)][int]$Port)

    $result = Invoke-WslCommand -Arguments @('/usr/bin/ss', '-H', '-ltn', "sport = :$Port") -Capture
    return $result.ExitCode -eq 0 -and @($result.Output | Where-Object { $_.Trim() }).Count -gt 0
}

function Test-WslPortOwnedByUnit {
    param(
        [Parameter(Mandatory)][int]$Port,
        [Parameter(Mandatory)][string]$Unit,
        [Parameter(Mandatory)][ValidateSet('user', 'system')][string]$Scope
    )

    $controlGroup = Get-UnitProperty -Unit $Unit -Property 'ControlGroup' -Scope $Scope
    if (-not $controlGroup) { return $false }
    $listeners = Invoke-WslCommand -Arguments @(
        '/usr/bin/ss', '-H', '-ltnp', "sport = :$Port"
    ) -Identity 'root' -Capture
    if ($listeners.ExitCode -ne 0) { return $false }
    $pidMatches = [regex]::Matches((@($listeners.Output) -join "`n"), 'pid=(\d+)')
    $listenerPids = @($pidMatches | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
    if ($listenerPids.Count -eq 0) { return $false }

    foreach ($listenerPid in $listenerPids) {
        $cgroup = Invoke-WslCommand -Arguments @('/usr/bin/cat', "/proc/$listenerPid/cgroup") `
            -Identity 'root' -Capture
        if ($cgroup.ExitCode -ne 0) { return $false }
        $owned = @($cgroup.Output | Where-Object { $_.Trim().EndsWith($controlGroup) }).Count -gt 0
        if (-not $owned) { return $false }
    }
    return $true
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
        Get-UnitState -Unit $Unit -Scope 'user'
    } else {
        Get-UnitState -Unit $Unit -Scope 'system'
    }
    if ($unitState -eq 'active' -and (Test-WslPortOwnedByUnit -Port $Port -Unit $Unit -Scope $Scope)) { return }
    Throw-SafeError $RecoveryMessage
}

function Start-Infrastructure {
    $exitCode = Invoke-WslCommand -Arguments @(
        '/usr/bin/systemctl', 'start', $script:PrometheusUnit, $script:PdcUnit
    ) -Identity 'root'
    if ($exitCode -ne 0) {
        Throw-SafeError 'Prometheus or Grafana PDC failed to start; inspect the exact system units locally.'
    }
}

function Wait-TransientUnitUnloaded {
    param([Parameter(Mandatory)][string]$Unit)

    for ($attempt = 1; $attempt -le 20; $attempt++) {
        $loadState = Get-UnitProperty -Unit $Unit -Property 'LoadState' -Scope 'user'
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

    if ((Get-UnitState -Unit $Unit -Scope 'user') -eq 'active') {
        Assert-ActiveTransientUnitMatches -Unit $Unit -WorkingDirectory $WorkingDirectory -Command $Command
        return
    }

    $loadState = Get-UnitProperty -Unit $Unit -Property 'LoadState' -Scope 'user'
    if ($loadState -eq 'loaded') {
        [void](Invoke-WslCommand -Arguments @('/usr/bin/systemctl', '--user', 'reset-failed', $Unit))
        Wait-TransientUnitUnloaded -Unit $Unit
    }

    $arguments = @(
        '/usr/bin/systemd-run', '--user', "--unit=$Unit", '--collect', '--quiet',
        '--property=Type=simple', "--property=WorkingDirectory=$WorkingDirectory",
        "--property=EnvironmentFile=$($script:RuntimeEnvPath)",
        "--property=Description=$(Get-TransientUnitIdentity -WorkingDirectory $WorkingDirectory -Command $Command)", '--'
    ) + $Command
    if ((Invoke-WslCommand -Arguments $arguments) -ne 0) {
        Throw-SafeError "The transient application unit failed to start: $Unit"
    }
}

function Start-Application {
    $backendWasActive = (Get-UnitState -Unit $script:BackendUnit -Scope 'user') -eq 'active'
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
            [void](Invoke-WslCommand -Arguments @('/usr/bin/systemctl', '--user', 'stop', $script:BackendUnit))
        }
        throw
    }
}

function Wait-HttpReady {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Url,
        [int]$TimeoutSeconds = 30
    )

    $timer = [Diagnostics.Stopwatch]::StartNew()
    while ($timer.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        if ((Get-HttpStatus -Url $Url) -eq 200) { return }
        if ($timer.Elapsed.TotalSeconds -lt $TimeoutSeconds) { Start-Sleep -Milliseconds 500 }
    }
    Throw-SafeError "$Name did not become ready within $TimeoutSeconds seconds."
}

function Get-PrometheusActiveTargets {
    $result = Invoke-WslCommand -Arguments @(
        '/usr/bin/curl', '--silent', '--show-error', '--max-time', '1', $script:PrometheusTargetsUrl
    ) -Capture
    if ($result.ExitCode -ne 0) { return @() }
    try {
        $document = ((@($result.Output) -join "`n") | ConvertFrom-Json -ErrorAction Stop)
        if ($document.status -ne 'success') { return @() }
        return @($document.data.activeTargets)
    } catch {
        return @()
    }
}

function Test-PrometheusTargetSetUp {
    param(
        [Parameter(Mandatory)][object[]]$Targets,
        [Parameter(Mandatory)][string]$JobSelector,
        [Parameter(Mandatory)][ValidateSet('exact', 'prefix')][string]$MatchMode,
        [datetimeoffset]$NotBefore = [datetimeoffset]::MinValue
    )

    $matchingTargets = @($Targets | Where-Object {
        Test-PrometheusJobMatch -Job "$($_.labels.job)" -Selector $JobSelector -MatchMode $MatchMode
    })
    if ($matchingTargets.Count -eq 0) { return $false }
    $unhealthyTargets = @($matchingTargets | Where-Object {
        -not (Test-PrometheusTargetFreshAndHealthy -Target $_ -NotBefore $NotBefore)
    })
    return $unhealthyTargets.Count -eq 0
}

function Test-PrometheusJobMatch {
    param(
        [Parameter(Mandatory)][string]$Job,
        [Parameter(Mandatory)][string]$Selector,
        [Parameter(Mandatory)][ValidateSet('exact', 'prefix')][string]$MatchMode
    )

    if ($MatchMode -eq 'exact') { return $Job -eq $Selector }
    return $Job.StartsWith($Selector, [StringComparison]::Ordinal)
}

function Test-PrometheusTargetFreshAndHealthy {
    param(
        [Parameter(Mandatory)]$Target,
        [Parameter(Mandatory)][datetimeoffset]$NotBefore
    )

    if ("$($Target.health)" -ne 'up') { return $false }
    if ($NotBefore -eq [datetimeoffset]::MinValue) { return $true }
    $lastScrape = [datetimeoffset]::MinValue
    if (-not [datetimeoffset]::TryParse("$($Target.lastScrape)", [ref]$lastScrape)) { return $false }
    return $lastScrape -ge $NotBefore
}

function Wait-PrometheusTargetsUp {
    param(
        [Parameter(Mandatory)][datetimeoffset]$NotBefore,
        [Parameter(Mandatory)][int]$TimeoutSeconds
    )

    $definitions = @(
        @{ Name = 'FastAPI'; Selector = $script:FastApiTargetJob; MatchMode = 'exact' },
        @{ Name = 'Supabase'; Selector = $script:SupabaseTargetJobPrefix; MatchMode = 'prefix' }
    )
    $timer = [Diagnostics.Stopwatch]::StartNew()
    while ($timer.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        $targets = @(Get-PrometheusActiveTargets)
        $pending = @($definitions | Where-Object {
            -not (Test-PrometheusTargetSetUp -Targets $targets -JobSelector $_.Selector `
                -MatchMode $_.MatchMode -NotBefore $NotBefore)
        })
        if ($pending.Count -eq 0) { return }
        if ($timer.Elapsed.TotalSeconds -lt $TimeoutSeconds) { Start-Sleep -Milliseconds 500 }
    }
    $pendingNames = @($pending | ForEach-Object { $_.Name }) -join ' and '
    Throw-SafeError "$pendingNames Prometheus target did not report a fresh healthy scrape within $TimeoutSeconds seconds."
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
    $components = @(
        @{ Component = 'FarDb backend'; Unit = $script:BackendUnit; Scope = 'user'; Url = $script:BackendHealthUrl },
        @{ Component = 'FarDb frontend'; Unit = $script:FrontendUnit; Scope = 'user'; Url = $script:FrontendHealthUrl },
        @{ Component = 'Prometheus'; Unit = $script:PrometheusUnit; Scope = 'system'; Url = $script:PrometheusHealthUrl },
        @{ Component = 'Grafana PDC'; Unit = $script:PdcUnit; Scope = 'system'; Url = $script:PdcHealthUrl }
    )
    foreach ($component in $components) {
        $state = Get-UnitState -Unit $component.Unit -Scope $component.Scope
        $httpStatus = Get-HttpStatus -Url $component.Url
        Write-StatusRow -Component $component.Component -State $state -HttpStatus $httpStatus
    }

    $activeTargets = @(Get-PrometheusActiveTargets)
    $targetDefinitions = @(
        @{ Component = 'Prometheus target fardb_fastapi'; Selector = $script:FastApiTargetJob; MatchMode = 'exact' },
        @{ Component = 'Prometheus target Supabase'; Selector = $script:SupabaseTargetJobPrefix; MatchMode = 'prefix' }
    )
    foreach ($target in $targetDefinitions) {
        $state = if (Test-PrometheusTargetSetUp -Targets $activeTargets -JobSelector $target.Selector `
                -MatchMode $target.MatchMode) {
            'up'
        } else {
            'down'
        }
        Write-StatusRow -Component $target.Component -State $state -HttpStatus 'n/a'
    }
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

    $initialStates = @{
        Backend = Get-UnitState -Unit $script:BackendUnit -Scope 'user'
        Frontend = Get-UnitState -Unit $script:FrontendUnit -Scope 'user'
        Prometheus = Get-UnitState -Unit $script:PrometheusUnit -Scope 'system'
        Pdc = Get-UnitState -Unit $script:PdcUnit -Scope 'system'
    }
    $freshScrapeAfter = [datetimeoffset]::UtcNow
    try {
        Start-Infrastructure
        Start-Application

        Wait-HttpReady -Name 'Prometheus' -Url $script:PrometheusHealthUrl `
            -TimeoutSeconds $ReadinessTimeoutSeconds
        Wait-HttpReady -Name 'FarDb backend' -Url $script:BackendHealthUrl `
            -TimeoutSeconds $ReadinessTimeoutSeconds
        Wait-HttpReady -Name 'FarDb frontend' -Url $script:FrontendHealthUrl `
            -TimeoutSeconds $ReadinessTimeoutSeconds
        Wait-HttpReady -Name 'Grafana PDC' -Url $script:PdcHealthUrl `
            -TimeoutSeconds $ReadinessTimeoutSeconds
        Wait-PrometheusTargetsUp -NotBefore $freshScrapeAfter -TimeoutSeconds $ReadinessTimeoutSeconds

        Show-Status
        if ($ShowLogs) { Open-LogWindows }
    } catch {
        Rollback-NewlyStartedServices -InitialStates $initialStates
        throw
    }
}

function Rollback-NewlyStartedServices {
    param([Parameter(Mandatory)][hashtable]$InitialStates)

    if ($InitialStates.Frontend -ne 'active') {
        [void](Invoke-WslCommand -Arguments @('/usr/bin/systemctl', '--user', 'stop', $script:FrontendUnit))
    }
    if ($InitialStates.Backend -ne 'active') {
        [void](Invoke-WslCommand -Arguments @('/usr/bin/systemctl', '--user', 'stop', $script:BackendUnit))
    }

    $systemUnits = @()
    if ($InitialStates.Pdc -ne 'active') { $systemUnits += $script:PdcUnit }
    if ($InitialStates.Prometheus -ne 'active') { $systemUnits += $script:PrometheusUnit }
    if ($systemUnits.Count -gt 0) {
        [void](Invoke-WslCommand -Arguments (@('/usr/bin/systemctl', 'stop') + $systemUnits) -Identity 'root')
    }
}

function Stop-TransientUserUnit {
    param([Parameter(Mandatory)][string]$Unit)

    $loadState = Get-UnitProperty -Unit $Unit -Property 'LoadState' -Scope 'user'
    if (-not $loadState -or $loadState -eq 'not-found') { return }
    Assert-TransientUnitCompatible -Unit $Unit
    if ((Invoke-WslCommand -Arguments @('/usr/bin/systemctl', '--user', 'stop', $Unit)) -ne 0) {
        Throw-SafeError "The transient application unit did not stop cleanly: $Unit"
    }
}

function Stop-Observability {
    Stop-TransientUserUnit -Unit $script:FrontendUnit
    Stop-TransientUserUnit -Unit $script:BackendUnit

    if ($StopInfrastructure) {
        if ((Invoke-WslCommand -Arguments @(
            '/usr/bin/systemctl', 'stop', $script:PdcUnit, $script:PrometheusUnit
        ) -Identity 'root') -ne 0) {
            Throw-SafeError 'Prometheus or Grafana PDC did not stop cleanly.'
        }
    }
    Show-Status
}

$launcherExitCode = 0
try {
    Assert-DistributionNameSafe
    Enter-LauncherMutex
    Assert-DistributionInstalled
    Assert-WslProcessHealthy
    Initialize-LauncherPaths
    Initialize-PrometheusTargetSettings

    switch ($Action) {
        'Start' { Start-Observability }
        'Status' { Show-Status }
        'Stop' { Stop-Observability }
    }
} catch {
    Write-Error ("FarDb observability launcher: {0}" -f $_.Exception.Message) -ErrorAction Continue
    $launcherExitCode = 1
} finally {
    Exit-LauncherMutex
}
exit $launcherExitCode
