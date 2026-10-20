Set-StrictMode -Version Latest

$script:ValidationTargetProfiles = @(
    [pscustomobject]@{ model_id = "keysight-34461a"; model = "34461A" },
    [pscustomobject]@{ model_id = "keysight-34460a"; model = "34460A" }
)

function Get-ValidationTargetProfiles {
    $profiles = @($script:ValidationTargetProfiles)
    $owners = @{}
    foreach ($profile in $profiles) {
        $modelId = [string]$profile.model_id
        $model = [string]$profile.model
        if ([string]::IsNullOrWhiteSpace($modelId)) {
            throw "Validation target model_id must not be empty."
        }
        if ($modelId -cne $modelId.ToLowerInvariant()) {
            throw "Validation target model_id must be lowercase: '$modelId'."
        }
        if ([string]::IsNullOrWhiteSpace($model)) {
            throw "Validation target '$modelId' must declare a physical model."
        }
        if ($owners.ContainsKey($modelId)) {
            throw "Duplicate validation target model_id '$modelId'."
        }
        $owners[$modelId] = $profile
    }
    return $profiles
}

function Get-SupportedTargetModelIds {
    return @(Get-ValidationTargetProfiles | ForEach-Object { $_.model_id })
}

function Resolve-ValidationTarget {
    param([AllowNull()][AllowEmptyString()][string]$Target)

    $supported = @(Get-SupportedTargetModelIds)
    $supportedText = $supported -join ", "
    if ([string]::IsNullOrWhiteSpace($Target)) {
        throw "Missing target. Supported targets: $supportedText."
    }
    $normalized = $Target.Trim().ToLowerInvariant()
    if ($normalized -notin $supported) {
        throw "Unsupported target '$Target'. Supported targets: $supportedText."
    }
    return $normalized
}

function Get-PackageVersion {
    param(
        [string]$ProjectRoot,
        [switch]$Required
    )

    if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
        $ProjectRoot = $RepoRoot
    }
    $pyproject = Join-Path $ProjectRoot "pyproject.toml"
    $match = Select-String -LiteralPath $pyproject -Pattern '^version\s*=\s*"([^"]+)"' | Select-Object -First 1
    if ($null -eq $match) {
        if ($Required) {
            throw "Could not read project version from $pyproject"
        }
        return $null
    }
    return $match.Matches[0].Groups[1].Value
}

function Get-GitHead {
    param([string]$ProjectRoot)

    if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
        $ProjectRoot = $RepoRoot
    }
    try {
        $head = & git -C $ProjectRoot rev-parse HEAD 2>$null
        if ($LASTEXITCODE -eq 0) {
            return $head.Trim()
        }
    } catch {
    }
    return $null
}

function Add-RepoSrcToPythonPath {
    param([Parameter(Mandatory = $true)][string]$RepoRoot)

    $packageSrcRoots = @(
        (Join-Path $RepoRoot "src")
    )
    $existingPythonPath = [Environment]::GetEnvironmentVariable("PYTHONPATH", "Process")
    if ([string]::IsNullOrWhiteSpace($existingPythonPath)) {
        [Environment]::SetEnvironmentVariable("PYTHONPATH", ($packageSrcRoots -join [System.IO.Path]::PathSeparator), "Process")
    } else {
        [Environment]::SetEnvironmentVariable(
            "PYTHONPATH",
            (($packageSrcRoots + $existingPythonPath) -join [System.IO.Path]::PathSeparator),
            "Process"
        )
    }
}

function Get-FullPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [System.IO.Path]::GetFullPath($Path)
}

function Assert-PathUnderRoot {
    param(
        [Parameter(Mandatory = $true)][string]$RootPath,
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Message
    )

    $rootFull = (Get-FullPath $RootPath).TrimEnd([System.IO.Path]::DirectorySeparatorChar)
    $pathFull = Get-FullPath $Path
    $comparison = [System.StringComparison]::OrdinalIgnoreCase
    if (-not $pathFull.StartsWith($rootFull + [System.IO.Path]::DirectorySeparatorChar, $comparison)) {
        throw ($Message -f $pathFull)
    }
}

function Get-AvailableTcpPort {
    $listener = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Parse("127.0.0.1"),
        0
    )
    $listener.Start()
    try {
        return [int]$listener.LocalEndpoint.Port
    } finally {
        $listener.Stop()
    }
}

function ConvertTo-ProcessArgument {
    param([Parameter(Mandatory = $true)][AllowEmptyString()][string]$Argument)
    if ($Argument -notmatch '[\s"]' -and $Argument.Length -gt 0) {
        return $Argument
    }

    $builder = [System.Text.StringBuilder]::new()
    [void]$builder.Append('"')
    $backslashes = 0
    foreach ($char in $Argument.ToCharArray()) {
        if ($char -eq '\') {
            $backslashes += 1
            continue
        }
        if ($char -eq '"') {
            [void]$builder.Append(('\' * ($backslashes * 2 + 1)))
            [void]$builder.Append('"')
            $backslashes = 0
            continue
        }
        if ($backslashes -gt 0) {
            [void]$builder.Append(('\' * $backslashes))
            $backslashes = 0
        }
        [void]$builder.Append($char)
    }
    if ($backslashes -gt 0) {
        [void]$builder.Append(('\' * ($backslashes * 2)))
    }
    [void]$builder.Append('"')
    return $builder.ToString()
}

function Join-ProcessArguments {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    return (($Arguments | ForEach-Object { ConvertTo-ProcessArgument -Argument $_ }) -join " ")
}

function Write-Utf8NoBomText {
    param(
        [Parameter(Mandatory = $true)][string]$LiteralPath,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Text
    )

    [System.IO.File]::WriteAllText(
        $LiteralPath,
        $Text,
        [System.Text.UTF8Encoding]::new($false)
    )
}

function Write-Utf8NoBomLines {
    param(
        [Parameter(Mandatory = $true)][string]$LiteralPath,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][AllowEmptyString()][string[]]$Lines
    )

    [System.IO.File]::WriteAllLines(
        $LiteralPath,
        $Lines,
        [System.Text.UTF8Encoding]::new($false)
    )
}

function Write-JsonReport {
    param(
        [Parameter(Mandatory = $true)][string]$LiteralPath,
        [Parameter(Mandatory = $true)]$Report,
        [int]$Depth = 12
    )

    Write-Utf8NoBomText -LiteralPath $LiteralPath -Text ($Report | ConvertTo-Json -Depth $Depth)
}

function Invoke-CapturedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$StdOutPath,
        [Parameter(Mandatory = $true)][string]$StdErrPath,
        [string]$WorkingDirectory = $RepoRoot,
        [switch]$CaptureInMemory
    )

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $FilePath
    $psi.WorkingDirectory = $WorkingDirectory
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.Arguments = Join-ProcessArguments -Arguments $Arguments

    $startedAt = Get-Date
    $process = [System.Diagnostics.Process]::Start($psi)
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $stderr = $stderrTask.GetAwaiter().GetResult()
    $finishedAt = Get-Date

    if (-not $CaptureInMemory) {
        Write-Utf8NoBomText -LiteralPath $StdOutPath -Text $stdout
        Write-Utf8NoBomText -LiteralPath $StdErrPath -Text $stderr
    }

    return [ordered]@{
        name = $Name
        command = $FilePath
        arguments = $Arguments
        exit_code = $process.ExitCode
        duration_seconds = [math]::Round(($finishedAt - $startedAt).TotalSeconds, 3)
        stdout = if ($CaptureInMemory) { $null } else { $StdOutPath }
        stderr = if ($CaptureInMemory) { $null } else { $StdErrPath }
        stdout_text = if ($CaptureInMemory) { $stdout } else { $null }
        stderr_text = if ($CaptureInMemory) { $stderr } else { $null }
        success = ($process.ExitCode -eq 0)
    }
}

function Invoke-ReadinessClientChecks {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][string]$OutDir,
        [switch]$CaptureInMemory
    )

    $waitOut = Join-Path $OutDir "$Name`_wait_ready.json"
    $waitErr = Join-Path $OutDir "$Name`_wait_ready.stderr.txt"
    $waitResult = Invoke-CapturedCommand `
        -Name "$Name`_wait_ready" `
        -FilePath $Python `
        -Arguments @("-m", "meters_tool_cli", "wait-ready", "--format", "json", "--port", [string]$Port) `
        -StdOutPath $waitOut `
        -StdErrPath $waitErr `
        -CaptureInMemory:$CaptureInMemory
    if (-not $waitResult.success) {
        return [ordered]@{ success = $false; commands = @([pscustomobject]$waitResult) }
    }

    $statusOut = Join-Path $OutDir "$Name`_soft_status.json"
    $statusErr = Join-Path $OutDir "$Name`_soft_status.stderr.txt"
    $statusResult = Invoke-CapturedCommand `
        -Name "$Name`_soft_status" `
        -FilePath $Python `
        -Arguments @("-m", "meters_tool_cli", "status", "--format", "json", "--port", [string]$Port) `
        -StdOutPath $statusOut `
        -StdErrPath $statusErr `
        -CaptureInMemory:$CaptureInMemory

    return [ordered]@{
        success = $statusResult.success
        commands = @([pscustomobject]$waitResult, [pscustomobject]$statusResult)
    }
}

function Invoke-CapturedStartProcess {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$StdOutPath,
        [Parameter(Mandatory = $true)][string]$StdErrPath,
        [int]$TimeoutSeconds = 30,
        [int]$SoftTriggerCount = 0,
        [int]$SoftTriggerPort = 0,
        [Parameter(Mandatory = $true)][string]$OutDir,
        [Parameter(Mandatory = $true)][int]$SoftTriggerRetryCount,
        [Parameter(Mandatory = $true)][int]$SoftTriggerRetryDelayMs,
        [Parameter(Mandatory = $true)][int]$InterTriggerDelayMs,
        [Parameter(Mandatory = $true)][int]$StopGracePeriodMs,
        [int]$PlannedStopAfterSeconds = 0,
        [int]$ExpectedExitCode = 0,
        [switch]$CaptureInMemory,
        [switch]$CaptureClientCommandsInMemory
    )

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $Python
    $psi.WorkingDirectory = $RepoRoot
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.Arguments = Join-ProcessArguments -Arguments $Arguments

    $startedAt = Get-Date
    $process = [System.Diagnostics.Process]::Start($psi)
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $clientResults = [System.Collections.Generic.List[object]]::new()
    $clientFailure = $null
    $timedOut = $false

    if ($SoftTriggerCount -gt 0 -or $PlannedStopAfterSeconds -gt 0 -or $ExpectedExitCode -ne 0) {
        $readinessResult = Invoke-ReadinessClientChecks `
            -Name $Name `
            -Port $SoftTriggerPort `
            -OutDir $OutDir `
            -CaptureInMemory:$CaptureClientCommandsInMemory
        foreach ($clientCommand in $readinessResult.commands) {
            $clientResults.Add($clientCommand) | Out-Null
        }
        if (-not $readinessResult.success) {
            $clientFailure = "readiness/status check failed"
        }
        for ($index = 1; $index -le $SoftTriggerCount; $index++) {
            if ($null -ne $clientFailure) {
                break
            }
            $triggerResult = Invoke-SoftTriggerWithRetry `
                -Name "$Name`_soft_trigger_$index" `
                -Port $SoftTriggerPort `
                -CaseName $Name `
                -Index $index `
                -OutDir $OutDir `
                -RetryCount $SoftTriggerRetryCount `
                -RetryDelayMs $SoftTriggerRetryDelayMs `
                -CaptureInMemory:$CaptureClientCommandsInMemory
            $clientResults.Add([pscustomobject]$triggerResult) | Out-Null
            if (-not $triggerResult.success) {
                $clientFailure = "send-command $index failed"
                break
            }
            Start-Sleep -Milliseconds $InterTriggerDelayMs
        }
    }

    $exited = $false
    if ($PlannedStopAfterSeconds -gt 0 -and $null -eq $clientFailure) {
        $exited = $process.WaitForExit($PlannedStopAfterSeconds * 1000)
        if (-not $exited) {
            $statusOut = Join-Path $OutDir "$Name`_planned_stop_status.json"
            $statusErr = Join-Path $OutDir "$Name`_planned_stop_status.stderr.txt"
            $statusResult = Invoke-CapturedCommand `
                -Name "$Name`_planned_stop_status" `
                -FilePath $Python `
                -Arguments @("-m", "meters_tool_cli", "status", "--format", "json", "--port", [string]$SoftTriggerPort) `
                -StdOutPath $statusOut `
                -StdErrPath $statusErr `
                -CaptureInMemory:$CaptureClientCommandsInMemory
            $clientResults.Add([pscustomobject]$statusResult) | Out-Null
            if (-not $statusResult.success) {
                $clientFailure = "status before planned stop failed"
            }
            $stopOut = Join-Path $OutDir "$Name`_planned_stop.json"
            $stopErr = Join-Path $OutDir "$Name`_planned_stop.stderr.txt"
            $stopResult = Invoke-CapturedCommand `
                -Name "$Name`_planned_stop" `
                -FilePath $Python `
                -Arguments @("-m", "meters_tool_cli", "stop", "--format", "json", "--port", [string]$SoftTriggerPort) `
                -StdOutPath $stopOut `
                -StdErrPath $stopErr `
                -CaptureInMemory:$CaptureClientCommandsInMemory
            $clientResults.Add([pscustomobject]$stopResult) | Out-Null
            if (-not $stopResult.success) {
                $clientFailure = "planned stop failed"
            }
            $exited = $process.WaitForExit($StopGracePeriodMs)
        }
    }
    if (-not $exited) { $exited = $process.WaitForExit($TimeoutSeconds * 1000) }
    if (-not $exited) {
        $timedOut = $true
        if ($SoftTriggerPort -gt 0) {
            $stopOut = Join-Path $OutDir "$Name`_timeout_soft_stop.json"
            $stopErr = Join-Path $OutDir "$Name`_timeout_soft_stop.stderr.txt"
            $stopResult = Invoke-CapturedCommand `
                -Name "$Name`_timeout_soft_stop" `
                -FilePath $Python `
                -Arguments @("-m", "meters_tool_cli", "stop", "--format", "json", "--port", [string]$SoftTriggerPort) `
                -StdOutPath $stopOut `
                -StdErrPath $stopErr `
                -CaptureInMemory:$CaptureClientCommandsInMemory
            $clientResults.Add([pscustomobject]$stopResult) | Out-Null
            $exited = $process.WaitForExit($StopGracePeriodMs)
        }
    }
    if (-not $exited) {
        $process.Kill()
        $process.WaitForExit()
    }
    $process.WaitForExit()
    $finishedAt = Get-Date
    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $stderr = $stderrTask.GetAwaiter().GetResult()
    if (-not $CaptureInMemory) {
        Write-Utf8NoBomText -LiteralPath $StdOutPath -Text $stdout
        Write-Utf8NoBomText -LiteralPath $StdErrPath -Text $stderr
    }

    return [ordered]@{
        name = $Name
        command = $Python
        arguments = $Arguments
        exit_code = $process.ExitCode
        duration_seconds = [math]::Round(($finishedAt - $startedAt).TotalSeconds, 3)
        stdout = if ($CaptureInMemory) { $null } else { $StdOutPath }
        stderr = if ($CaptureInMemory) { $null } else { $StdErrPath }
        stdout_text = if ($CaptureInMemory) { $stdout } else { $null }
        stderr_text = if ($CaptureInMemory) { $stderr } else { $null }
        success = (($process.ExitCode -eq $ExpectedExitCode) -and (-not $timedOut) -and ($null -eq $clientFailure))
        timed_out = $timedOut
        client_failure = $clientFailure
        client_commands = @($clientResults.ToArray())
    }
}

function Invoke-SoftTriggerWithRetry {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][string]$CaseName,
        [Parameter(Mandatory = $true)][int]$Index,
        [Parameter(Mandatory = $true)][string]$OutDir,
        [Parameter(Mandatory = $true)][int]$RetryCount,
        [Parameter(Mandatory = $true)][int]$RetryDelayMs,
        [switch]$CaptureInMemory
    )

    $meta = [ordered]@{ case = $CaseName; index = "$Index" } | ConvertTo-Json -Compress
    $lastResult = $null
    for ($attempt = 1; $attempt -le $RetryCount; $attempt++) {
        $stdoutPath = Join-Path $OutDir "$Name`_attempt_$attempt.json"
        $stderrPath = Join-Path $OutDir "$Name`_attempt_$attempt.stderr.txt"
        $lastResult = Invoke-CapturedCommand `
            -Name "$Name`_attempt_$attempt" `
            -FilePath $Python `
            -Arguments @(
                "-m", "meters_tool_cli",
                "send-command",
                "--format", "json",
                "--port", [string]$Port,
                "--arguments-json", $meta
            ) `
            -StdOutPath $stdoutPath `
            -StdErrPath $stderrPath `
            -CaptureInMemory:$CaptureInMemory
        if ($lastResult.success) {
            try {
                $responseText = if ($CaptureInMemory) { $lastResult.stdout_text } else { Get-Content -LiteralPath $stdoutPath -Raw }
                $event = $responseText | ConvertFrom-Json -ErrorAction Stop
                if ($event.event -eq "send-command" -and $event.status -eq "accepted") {
                    return $lastResult
                }
            } catch {
                # Retry until the trigger endpoint is ready and emits valid JSON.
            }
        }
        Start-Sleep -Milliseconds $RetryDelayMs
    }
    return $lastResult
}

function Read-JsonLines {
    param(
        [string]$Path,
        [AllowEmptyString()][string]$Text = "",
        [switch]$FromText
    )
    $events = @()
    $lines = if ($FromText) { @($Text -split '\r?\n') } else { @(Get-Content -LiteralPath $Path) }
    foreach ($line in $lines) {
        if ($line.Trim().Length -eq 0) {
            continue
        }
        $events += ($line | ConvertFrom-Json -ErrorAction Stop)
    }
    return @($events)
}

function Select-LastJsonEvent {
    param(
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$Events,
        [Parameter(Mandatory = $true)][string]$EventName
    )
    return @($Events | Where-Object { $_.event -eq $EventName } | Select-Object -Last 1)
}

function Assert-Condition {
    param(
        [Parameter(Mandatory = $true)][bool]$Condition,
        [Parameter(Mandatory = $true)][string]$Message
    )
    if (-not $Condition) {
        throw $Message
    }
}

function Test-CsvRowCount {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return 0
    }
    $rows = @(Import-Csv -LiteralPath $Path)
    return $rows.Count
}

function New-SafeCaseName {
    param([Parameter(Mandatory = $true)][string]$Name)
    return ($Name -replace '[^A-Za-z0-9_.-]', '_')
}

function Get-TargetCliModel {
    param([Parameter(Mandatory = $true)][string]$ResolvedTarget)
    $canonicalTarget = Resolve-ValidationTarget -Target $ResolvedTarget
    $profile = @(Get-ValidationTargetProfiles | Where-Object { $_.model_id -eq $canonicalTarget })[0]
    return $profile.model
}
