[Diagnostics.CodeAnalysis.SuppressMessageAttribute(
    'PSReviewUnusedParameter',
    '',
    Justification = 'Script parameters are consumed by nested orchestration functions.'
)]
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
$script:BackendHealthUrl = 'http://127.0.0.1:8000/api/health/detailed'
$script:FrontendHealthUrl = 'http://127.0.0.1:3000/'
$script:PrometheusHealthUrl = 'http://127.0.0.1:9090/-/ready'
$script:PdcHealthUrl = 'http://127.0.0.1:8090/metrics'
$script:PrometheusTargetsUrl = 'http://127.0.0.1:9090/api/v1/targets?state=active'
$script:FastApiTargetJob = 'fardb_fastapi'
$script:LauncherMutex = $null
$script:LauncherMutexOwned = $false
$script:RuntimeInputFingerprint = ''

function Write-SafeError {
    param([Parameter(Mandatory)][string]$Message)

    throw [System.InvalidOperationException]::new($Message)
}

function Assert-DistributionNameSafe {
    if ($Distribution -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$') {
        Write-SafeError 'The WSL distribution name contains unsupported characters.'
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
        Write-SafeError 'Another FarDb observability launcher invocation is already active.'
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
        Write-SafeError 'The installed WSL distributions could not be inspected.'
    }
    if ($Distribution -notin $installed) {
        Write-SafeError "Required WSL distribution is unavailable: $Distribution"
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
        Write-SafeError (
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
        Write-SafeError $FailureMessage
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
    Write-SafeError "Required prerequisite is unavailable: $Label."
}

function Assert-WslAbsolutePath {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Label
    )

    if (-not $Path.StartsWith('/') -or $Path.IndexOfAny([char[]]"`0`r`n") -ge 0) {
        Write-SafeError "$Label did not resolve to a safe absolute WSL path."
    }
}

function Initialize-LauncherPath {
    if ([string]::IsNullOrWhiteSpace($PSScriptRoot)) {
        Write-SafeError 'The launcher must be run from its script file.'
    }
    $repoRootWindows = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
    $pathMatch = [regex]::Match($repoRootWindows, '^([A-Za-z]):\\(.+)$')
    if (-not $pathMatch.Success) {
        Write-SafeError 'The repository is not on a supported local Windows drive.'
    }
    $homePathRequest = @{
        Arguments = @('/usr/bin/printenv', 'HOME')
        FailureMessage = 'The WSL user home directory could not be resolved.'
    }
    $drive = $pathMatch.Groups[1].Value.ToLowerInvariant()
    $relativePath = $pathMatch.Groups[2].Value.Replace('\', '/')
    $script:RepoRootWindows = $repoRootWindows
    $script:RepoRootWsl = "/mnt/$drive/$relativePath"
    $script:WslHome = Get-SingleWslValue @homePathRequest

    Assert-WslAbsolutePath -Path $script:RepoRootWsl -Label 'Repository root'
    Assert-WslAbsolutePath -Path $script:WslHome -Label 'WSL home'

    $script:FrontendRootWsl = "$($script:RepoRootWsl)/frontend"
    $script:RuntimeEnvPath = "$($script:WslHome)/.config/fardb-observability/runtime.env"
    $script:PythonPath = "$($script:WslHome)/.local/share/fardb-observability/venv/bin/python"
    $script:NpmPath = Resolve-WslExecutablePath -Candidates @('/usr/local/bin/npm', '/usr/bin/npm') -Label 'npm'
}

function Initialize-PrometheusTargetSetting {
    if ([string]::IsNullOrWhiteSpace($SupabasePrometheusJobPrefix)) {
        $SupabasePrometheusJobPrefix = 'integrations/supabase/'
    }
    if ($SupabasePrometheusJobPrefix.Length -gt 128) {
        Write-SafeError 'The Supabase Prometheus job prefix exceeds 128 characters.'
    }
    if ($SupabasePrometheusJobPrefix -notmatch '^[A-Za-z0-9_./:-]+$') {
        Write-SafeError 'The Supabase Prometheus job prefix contains unsupported characters.'
    }
    if (-not $SupabasePrometheusJobPrefix.EndsWith('/')) {
        Write-SafeError 'The Supabase Prometheus job prefix must end with a path separator.'
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

function Test-ActiveTransientUnitMatch {
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
        Write-SafeError "The active transient unit belongs to another launcher configuration: $Unit"
    }
    if ($actualEnvironment -ne $expectedEnvironment) {
        Write-SafeError "The active transient unit belongs to another launcher configuration: $Unit"
    }
    return $actualDescription -eq $expectedDescription
}

function Get-StringSha256 {
    param([Parameter(Mandatory)][string]$Value)

    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        $digest = $algorithm.ComputeHash([Text.Encoding]::UTF8.GetBytes($Value))
    } finally {
        $algorithm.Dispose()
    }
    return ([BitConverter]::ToString($digest)).Replace('-', '').ToLowerInvariant()
}

function Get-WslFileSha256 {
    param([Parameter(Mandatory)][string]$Path)

    $result = Invoke-WslCommand -Arguments @('/usr/bin/sha256sum', '--', $Path) -Capture
    $lines = @($result.Output | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($result.ExitCode -ne 0) {
        Write-SafeError 'A required runtime input could not be fingerprinted safely.'
    }
    if ($lines.Count -ne 1) {
        Write-SafeError 'A required runtime input could not be fingerprinted safely.'
    }
    if ($lines[0] -notmatch '^([0-9A-Fa-f]{64})\s') {
        Write-SafeError 'A required runtime input could not be fingerprinted safely.'
    }
    return $Matches[1].ToLowerInvariant()
}

function Get-LocalFileSha256 {
    param([Parameter(Mandatory)][string]$Path)

    $algorithm = [Security.Cryptography.SHA256]::Create()
    $stream = $null
    try {
        $stream = [IO.File]::OpenRead($Path)
        $digest = $algorithm.ComputeHash($stream)
    } catch {
        Write-SafeError 'An untracked runtime input could not be fingerprinted safely.'
    } finally {
        if ($null -ne $stream) { $stream.Dispose() }
        $algorithm.Dispose()
    }
    return ([BitConverter]::ToString($digest)).Replace('-', '').ToLowerInvariant()
}

function Invoke-LocalGit {
    param([Parameter(Mandatory)][string[]]$Arguments)

    $local:ErrorActionPreference = 'Continue'
    try {
        $captured = @(& git.exe -C $script:RepoRootWindows -c core.quotepath=false @Arguments 2>$null)
        return [pscustomobject]@{ ExitCode = $LASTEXITCODE; Output = $captured }
    } catch {
        return [pscustomobject]@{ ExitCode = 1; Output = @() }
    }
}

function Get-LocalGitOutput {
    param(
        [Parameter(Mandatory)][string[]]$Arguments,
        [Parameter(Mandatory)][string]$FailureMessage
    )

    $result = Invoke-LocalGit -Arguments $Arguments
    if ($result.ExitCode -ne 0) { Write-SafeError $FailureMessage }
    return @($result.Output)
}

function Get-RepositoryRevision {
    $values = @(Get-LocalGitOutput -Arguments @('rev-parse', '--verify', 'HEAD') `
        -FailureMessage 'The repository revision could not be fingerprinted safely.' |
        ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($values.Count -ne 1) {
        Write-SafeError 'The repository revision could not be fingerprinted safely.'
    }
    if ($values[0] -notmatch '^[0-9A-Fa-f]{40,64}$') {
        Write-SafeError 'The repository revision could not be fingerprinted safely.'
    }
    return $values[0].ToLowerInvariant()
}

function Assert-UntrackedRuntimePathSafe {
    param([Parameter(Mandatory)][string]$RelativePath)

    if ([IO.Path]::IsPathRooted($RelativePath)) {
        Write-SafeError 'An untracked runtime input path could not be fingerprinted safely.'
    }
    if ($RelativePath.IndexOfAny([char[]]"`0`r`n") -ge 0) {
        Write-SafeError 'An untracked runtime input path could not be fingerprinted safely.'
    }
    if (@($RelativePath.Split('/') | Where-Object { $_ -eq '..' }).Count -gt 0) {
        Write-SafeError 'An untracked runtime input path could not be fingerprinted safely.'
    }
}

function Get-UntrackedRuntimeMaterial {
    param([Parameter(Mandatory)][AllowEmptyCollection()][string[]]$RelativePaths)

    $repoRootPrefix = $script:RepoRootWindows.TrimEnd('\') + '\'
    $material = @()
    foreach ($relativePath in @($RelativePaths | Where-Object { $_ })) {
        Assert-UntrackedRuntimePathSafe -RelativePath $relativePath
        $filePath = [IO.Path]::GetFullPath((Join-Path $script:RepoRootWindows $relativePath))
        if (-not $filePath.StartsWith($repoRootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            Write-SafeError 'An untracked runtime input could not be fingerprinted safely.'
        }
        if (-not [IO.File]::Exists($filePath)) {
            Write-SafeError 'An untracked runtime input could not be fingerprinted safely.'
        }
        $material += "$relativePath`0$(Get-LocalFileSha256 -Path $filePath)"
    }
    return $material
}

function Get-RepositoryRuntimeFingerprint {
    $head = Get-RepositoryRevision
    $diff = @(Get-LocalGitOutput `
        -Arguments @('diff', '--no-ext-diff', '--no-textconv', '--binary', 'HEAD', '--') `
        -FailureMessage 'The repository changes could not be fingerprinted safely.')
    $untracked = @(Get-LocalGitOutput -Arguments @('ls-files', '--others', '--exclude-standard') `
        -FailureMessage 'The repository changes could not be fingerprinted safely.')
    $untrackedMaterial = @(Get-UntrackedRuntimeMaterial -RelativePaths $untracked)
    $material = @($head, ($diff -join "`n")) + $untrackedMaterial
    return Get-StringSha256 -Value ($material -join "`0")
}

function Initialize-RuntimeInputFingerprint {
    $environmentFingerprint = Get-WslFileSha256 -Path $script:RuntimeEnvPath
    $repositoryFingerprint = Get-RepositoryRuntimeFingerprint
    $script:RuntimeInputFingerprint = Get-StringSha256 -Value (
        "$environmentFingerprint`0$repositoryFingerprint"
    )
}

function Get-TransientUnitIdentity {
    param(
        [Parameter(Mandatory)][string]$WorkingDirectory,
        [Parameter(Mandatory)][string[]]$Command
    )

    if (-not $script:RuntimeInputFingerprint) {
        Write-SafeError 'The runtime inputs were not fingerprinted before service identity validation.'
    }
    $identityMaterial = (
        @($WorkingDirectory, $script:RuntimeEnvPath, $script:RuntimeInputFingerprint) + $Command
    ) -join "`0"
    $fingerprint = Get-StringSha256 -Value $identityMaterial
    return "FarDb observability launcher $fingerprint"
}

function Assert-TransientUnitCompatible {
    param([Parameter(Mandatory)][string]$Unit)

    $loadState = Get-UnitProperty -Unit $Unit -Property 'LoadState' -Scope 'user'
    if (-not $loadState -or $loadState -eq 'not-found') { return }
    if ($loadState -ne 'loaded') {
        Write-SafeError "The application unit is not in a usable state: $Unit"
    }
    if ((Get-UnitProperty -Unit $Unit -Property 'Transient' -Scope 'user') -ne 'yes') {
        Write-SafeError (
            "A persistent legacy unit conflicts with the required transient unit: $Unit. " +
            'Follow the documented reversible migration before retrying.'
        )
    }
}

function Assert-Prerequisite {
    $requiredExecutables = @(
        @{ Path = '/usr/bin/curl'; Label = 'curl' },
        @{ Path = '/usr/bin/sha256sum'; Label = 'sha256sum' },
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
        Write-SafeError "Required prerequisite is unavailable: $Label."
    }
}

function Assert-SystemUnitAvailable {
    param([Parameter(Mandatory)][string]$Unit)

    if ((Get-UnitProperty -Unit $Unit -Property 'LoadState' -Scope 'system') -ne 'loaded') {
        Write-SafeError "Required infrastructure unit is unavailable: $Unit"
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

function Test-FastApiReady {
    $result = Invoke-WslCommand -Arguments @(
        '/usr/bin/curl', '--silent', '--show-error', '--max-time', '1', '--max-filesize', '16384',
        $script:BackendHealthUrl
    ) -Capture
    if ($result.ExitCode -ne 0) { return $false }
    try {
        $document = ((@($result.Output) -join "`n") | ConvertFrom-Json -ErrorAction Stop)
        return (
            $document.status -eq 'healthy' -and
            $document.graph_persistence_configured -eq $true -and
            $document.graph.available -eq $true -and
            $document.graph.persistence_enabled -eq $true -and
            $document.database.configured -eq $true -and
            $document.database.reachable -eq $true
        )
    } catch {
        return $false
    }
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
    Write-SafeError $RecoveryMessage
}

function Invoke-InfrastructureStart {
    $exitCode = Invoke-WslCommand -Arguments @(
        '/usr/bin/systemctl', 'start', $script:PrometheusUnit, $script:PdcUnit
    ) -Identity 'root'
    if ($exitCode -ne 0) {
        Write-SafeError 'Prometheus or Grafana PDC failed to start; inspect the exact system units locally.'
    }
}

function Wait-TransientUnitUnloaded {
    param([Parameter(Mandatory)][string]$Unit)

    for ($attempt = 1; $attempt -le 20; $attempt++) {
        $loadState = Get-UnitProperty -Unit $Unit -Property 'LoadState' -Scope 'user'
        if (-not $loadState -or $loadState -eq 'not-found') { return }
        Start-Sleep -Milliseconds 100
    }
    Write-SafeError "The prior transient unit did not unload cleanly: $Unit"
}

function Test-ActiveTransientUnitReusable {
    param(
        [Parameter(Mandatory)][string]$Unit,
        [Parameter(Mandatory)][string]$WorkingDirectory,
        [Parameter(Mandatory)][string[]]$Command
    )

    if ((Get-UnitState -Unit $Unit -Scope 'user') -ne 'active') { return $false }
    if (Test-ActiveTransientUnitMatch -Unit $Unit -WorkingDirectory $WorkingDirectory -Command $Command) {
        return $true
    }
    Write-SafeError (
        "The active transient unit was started from different runtime inputs: $Unit. " +
        'Run -Action Stop, then run -Action Start; the active unit was not changed.'
    )
}

function Clear-InactiveTransientUnit {
    param([Parameter(Mandatory)][string]$Unit)

    if ((Invoke-WslCommand -Arguments @('/usr/bin/systemctl', '--user', 'stop', $Unit)) -ne 0) {
        Write-SafeError "The inactive transient application unit did not stop cleanly: $Unit"
    }
    [void](Invoke-WslCommand -Arguments @('/usr/bin/systemctl', '--user', 'reset-failed', $Unit))
    Wait-TransientUnitUnloaded -Unit $Unit
}

function Invoke-TransientUserUnitStart {
    param(
        [Parameter(Mandatory)][string]$Unit,
        [Parameter(Mandatory)][string]$WorkingDirectory,
        [Parameter(Mandatory)][string[]]$Command
    )

    if (Test-ActiveTransientUnitReusable -Unit $Unit -WorkingDirectory $WorkingDirectory -Command $Command) { return }

    $loadState = Get-UnitProperty -Unit $Unit -Property 'LoadState' -Scope 'user'
    if ($loadState -eq 'loaded') {
        Clear-InactiveTransientUnit -Unit $Unit
    }

    $arguments = @(
        '/usr/bin/systemd-run', '--user', "--unit=$Unit", '--collect', '--quiet',
        '--property=Type=simple', "--property=WorkingDirectory=$WorkingDirectory",
        "--property=EnvironmentFile=$($script:RuntimeEnvPath)",
        "--property=Description=$(Get-TransientUnitIdentity -WorkingDirectory $WorkingDirectory -Command $Command)", '--'
    ) + $Command
    if ((Invoke-WslCommand -Arguments $arguments) -ne 0) {
        Write-SafeError "The transient application unit failed to start: $Unit"
    }
}

function Get-BackendStartSpec {
    return @{
        Unit = $script:BackendUnit
        WorkingDirectory = $script:RepoRootWsl
        Command = @(
            $script:PythonPath, '-m', 'uvicorn', 'api.main:app',
            '--host', '127.0.0.1', '--port', "$($script:BackendPort)"
        )
    }
}

function Get-FrontendStartSpec {
    return @{
        Unit = $script:FrontendUnit
        WorkingDirectory = $script:FrontendRootWsl
        Command = @(
            $script:NpmPath, 'run', 'dev', '--',
            '--hostname', '127.0.0.1', '--port', "$($script:FrontendPort)"
        )
    }
}

function Invoke-ApplicationStart {
    $backendWasActive = (Get-UnitState -Unit $script:BackendUnit -Scope 'user') -eq 'active'
    $backendStart = Get-BackendStartSpec
    Invoke-TransientUserUnitStart @backendStart
    try {
        $frontendStart = Get-FrontendStartSpec
        Invoke-TransientUserUnitStart @frontendStart
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
    Write-SafeError "$Name did not become ready within $TimeoutSeconds seconds."
}

function Wait-FastApiReady {
    param([int]$TimeoutSeconds = 30)

    $timer = [Diagnostics.Stopwatch]::StartNew()
    while ($timer.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        if (Test-FastApiReady) { return }
        if ($timer.Elapsed.TotalSeconds -lt $TimeoutSeconds) { Start-Sleep -Milliseconds 500 }
    }
    Write-SafeError "FarDb backend did not satisfy detailed readiness within $TimeoutSeconds seconds."
}

function Get-ReadinessSecondsRemaining {
    param([Parameter(Mandatory)][datetimeoffset]$Deadline)

    $remaining = [int][Math]::Ceiling(($Deadline - [datetimeoffset]::UtcNow).TotalSeconds)
    if ($remaining -le 0) {
        Write-SafeError "The complete Start action exceeded its $ReadinessTimeoutSeconds-second readiness deadline."
    }
    return $remaining
}

function Get-PrometheusActiveTarget {
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
        $targets = @(Get-PrometheusActiveTarget)
        $pending = @($definitions | Where-Object {
            -not (Test-PrometheusTargetSetUp -Targets $targets -JobSelector $_.Selector `
                -MatchMode $_.MatchMode -NotBefore $NotBefore)
        })
        if ($pending.Count -eq 0) { return }
        if ($timer.Elapsed.TotalSeconds -lt $TimeoutSeconds) { Start-Sleep -Milliseconds 500 }
    }
    $pendingNames = @($pending | ForEach-Object { $_.Name }) -join ' and '
    $targetNoun = if ($pending.Count -eq 1) { 'target' } else { 'targets' }
    Write-SafeError "$pendingNames Prometheus $targetNoun did not report a fresh healthy scrape within $TimeoutSeconds seconds."
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

    $activeTargets = @(Get-PrometheusActiveTarget)
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

function Invoke-ObservabilityStart {
    Assert-Prerequisite
    Initialize-RuntimeInputFingerprint
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
    $readinessDeadline = $freshScrapeAfter.AddSeconds($ReadinessTimeoutSeconds)
    try {
        Invoke-InfrastructureStart
        Invoke-ApplicationStart

        Wait-HttpReady -Name 'Prometheus' -Url $script:PrometheusHealthUrl `
            -TimeoutSeconds (Get-ReadinessSecondsRemaining -Deadline $readinessDeadline)
        Wait-FastApiReady `
            -TimeoutSeconds (Get-ReadinessSecondsRemaining -Deadline $readinessDeadline)
        Wait-HttpReady -Name 'FarDb frontend' -Url $script:FrontendHealthUrl `
            -TimeoutSeconds (Get-ReadinessSecondsRemaining -Deadline $readinessDeadline)
        Wait-HttpReady -Name 'Grafana PDC' -Url $script:PdcHealthUrl `
            -TimeoutSeconds (Get-ReadinessSecondsRemaining -Deadline $readinessDeadline)
        Wait-PrometheusTargetsUp -NotBefore $freshScrapeAfter `
            -TimeoutSeconds (Get-ReadinessSecondsRemaining -Deadline $readinessDeadline)

        Show-Status
        if ($ShowLogs) { Open-LogWindows }
    } catch {
        Restore-InitialServiceState -InitialStates $initialStates
        throw
    }
}

function Restore-InitialInfrastructureState {
    param([Parameter(Mandatory)][hashtable]$InitialStates)

    $systemUnits = @()
    if ($InitialStates.Pdc -ne 'active') { $systemUnits += $script:PdcUnit }
    if ($InitialStates.Prometheus -ne 'active') { $systemUnits += $script:PrometheusUnit }
    if ($systemUnits.Count -gt 0) {
        [void](Invoke-WslCommand -Arguments (@('/usr/bin/systemctl', 'stop') + $systemUnits) -Identity 'root')
    }
}

function Restore-InitialServiceState {
    param([Parameter(Mandatory)][hashtable]$InitialStates)

    if ($InitialStates.Frontend -ne 'active') {
        [void](Invoke-WslCommand -Arguments @('/usr/bin/systemctl', '--user', 'stop', $script:FrontendUnit))
    }
    if ($InitialStates.Backend -ne 'active') {
        [void](Invoke-WslCommand -Arguments @('/usr/bin/systemctl', '--user', 'stop', $script:BackendUnit))
    }
    Restore-InitialInfrastructureState -InitialStates $InitialStates
}

function Invoke-TransientUserUnitStop {
    param([Parameter(Mandatory)][string]$Unit)

    $loadState = Get-UnitProperty -Unit $Unit -Property 'LoadState' -Scope 'user'
    if (-not $loadState -or $loadState -eq 'not-found') { return }
    Assert-TransientUnitCompatible -Unit $Unit
    if ((Invoke-WslCommand -Arguments @('/usr/bin/systemctl', '--user', 'stop', $Unit)) -ne 0) {
        Write-SafeError "The transient application unit did not stop cleanly: $Unit"
    }
}

function Invoke-ObservabilityStop {
    Invoke-TransientUserUnitStop -Unit $script:FrontendUnit
    Invoke-TransientUserUnitStop -Unit $script:BackendUnit

    if ($StopInfrastructure) {
        if ((Invoke-WslCommand -Arguments @(
            '/usr/bin/systemctl', 'stop', $script:PdcUnit, $script:PrometheusUnit
        ) -Identity 'root') -ne 0) {
            Write-SafeError 'Prometheus or Grafana PDC did not stop cleanly.'
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
    Initialize-LauncherPath
    Initialize-PrometheusTargetSetting

    switch ($Action) {
        'Start' { Invoke-ObservabilityStart }
        'Status' { Show-Status }
        'Stop' { Invoke-ObservabilityStop }
    }
} catch {
    Write-Error ("FarDb observability launcher: {0}" -f $_.Exception.Message) -ErrorAction Continue
    $launcherExitCode = 1
} finally {
    Exit-LauncherMutex
}
exit $launcherExitCode
