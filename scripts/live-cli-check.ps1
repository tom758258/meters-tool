param(
    [Alias("Model", "Profile")]
    [string]$Target,

    [Alias("Transport")]
    [string]$Connection,

    [string]$Resource,

    [ValidateSet("minimal", "basic", "external", "full")]
    [string]$Suite = "minimal",

    [switch]$PlanOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$TmpRoot = Join-Path $RepoRoot ".tmp_tests"
$LiveRoot = Join-Path $TmpRoot "cli_live"
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$PreflightScript = Join-Path $PSScriptRoot "preflight-cli.ps1"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python executable not found: $Python"
}

function Fail-Usage {
    param([Parameter(Mandatory = $true)][string]$Message)
    [Console]::Error.WriteLine($Message)
    exit 2
}

function Get-FullPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [System.IO.Path]::GetFullPath($Path)
}

function Assert-UnderTmpRoot {
    param([Parameter(Mandatory = $true)][string]$Path)
    $tmpFull = Get-FullPath $TmpRoot
    $pathFull = Get-FullPath $Path
    $comparison = [System.StringComparison]::OrdinalIgnoreCase
    if (-not $pathFull.StartsWith($tmpFull + [System.IO.Path]::DirectorySeparatorChar, $comparison)) {
        throw "Refusing to write outside .tmp_tests: $pathFull"
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

function Invoke-CapturedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$StdOutPath,
        [Parameter(Mandatory = $true)][string]$StdErrPath
    )

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $FilePath
    $psi.WorkingDirectory = $RepoRoot
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.Arguments = Join-ProcessArguments -Arguments $Arguments

    $startedAt = Get-Date
    $process = [System.Diagnostics.Process]::Start($psi)
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    $finishedAt = Get-Date

    Set-Content -LiteralPath $StdOutPath -Value $stdout -Encoding UTF8
    Set-Content -LiteralPath $StdErrPath -Value $stderr -Encoding UTF8

    return [ordered]@{
        name = $Name
        command = $FilePath
        arguments = $Arguments
        exit_code = $process.ExitCode
        duration_seconds = [math]::Round(($finishedAt - $startedAt).TotalSeconds, 3)
        stdout = $StdOutPath
        stderr = $StdErrPath
        success = ($process.ExitCode -eq 0)
    }
}

function Invoke-CapturedStartProcess {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$StdOutPath,
        [Parameter(Mandatory = $true)][string]$StdErrPath,
        [Parameter(Mandatory = $true)][int]$TimeoutSeconds,
        [int]$SoftTriggerCount = 0,
        [int]$SoftTriggerPort = 0,
        [Parameter(Mandatory = $true)][string]$OutDir
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

    if ($SoftTriggerCount -gt 0) {
        for ($index = 1; $index -le $SoftTriggerCount; $index++) {
            $triggerResult = Invoke-SoftTriggerWithRetry `
                -Name "$Name`_soft_trigger_$index" `
                -Port $SoftTriggerPort `
                -CaseName $Name `
                -Index $index `
                -OutDir $OutDir
            $clientResults.Add([pscustomobject]$triggerResult) | Out-Null
            if (-not $triggerResult.success) {
                $clientFailure = "soft-trigger $index failed"
                break
            }
            Start-Sleep -Milliseconds 250
        }
    }

    $exited = $process.WaitForExit($TimeoutSeconds * 1000)
    if (-not $exited) {
        $timedOut = $true
        if ($SoftTriggerPort -gt 0) {
            $stopOut = Join-Path $OutDir "$Name`_timeout_soft_stop.json"
            $stopErr = Join-Path $OutDir "$Name`_timeout_soft_stop.stderr.txt"
            $stopResult = Invoke-CapturedCommand `
                -Name "$Name`_timeout_soft_stop" `
                -FilePath $Python `
                -Arguments @("-m", "keysight_logger.cli", "soft-stop", "--format", "json", "--port", [string]$SoftTriggerPort) `
                -StdOutPath $stopOut `
                -StdErrPath $stopErr
            $clientResults.Add([pscustomobject]$stopResult) | Out-Null
            $exited = $process.WaitForExit(10000)
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
    Set-Content -LiteralPath $StdOutPath -Value $stdout -Encoding UTF8
    Set-Content -LiteralPath $StdErrPath -Value $stderr -Encoding UTF8

    return [ordered]@{
        name = $Name
        command = $Python
        arguments = $Arguments
        exit_code = $process.ExitCode
        duration_seconds = [math]::Round(($finishedAt - $startedAt).TotalSeconds, 3)
        stdout = $StdOutPath
        stderr = $StdErrPath
        success = (($process.ExitCode -eq 0) -and (-not $timedOut) -and ($null -eq $clientFailure))
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
        [Parameter(Mandatory = $true)][string]$OutDir
    )

    $meta = [ordered]@{ case = $CaseName; index = "$Index" } | ConvertTo-Json -Compress
    $lastResult = $null
    for ($attempt = 1; $attempt -le 60; $attempt++) {
        $stdoutPath = Join-Path $OutDir "$Name`_attempt_$attempt.json"
        $stderrPath = Join-Path $OutDir "$Name`_attempt_$attempt.stderr.txt"
        $lastResult = Invoke-CapturedCommand `
            -Name "$Name`_attempt_$attempt" `
            -FilePath $Python `
            -Arguments @(
                "-m", "keysight_logger.cli",
                "soft-trigger",
                "--format", "json",
                "--port", [string]$Port,
                "--meta", $meta
            ) `
            -StdOutPath $stdoutPath `
            -StdErrPath $stderrPath
        if ($lastResult.success) {
            try {
                $event = Get-Content -LiteralPath $stdoutPath -Raw | ConvertFrom-Json -ErrorAction Stop
                if ($event.event -eq "soft-trigger" -and $event.status -eq "accepted") {
                    return $lastResult
                }
            } catch {
                # Retry until the logger endpoint is ready and emits valid JSON.
            }
        }
        Start-Sleep -Milliseconds 250
    }
    return $lastResult
}

function Read-JsonLines {
    param([Parameter(Mandatory = $true)][string]$Path)
    $events = @()
    foreach ($line in Get-Content -LiteralPath $Path) {
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

function Test-CsvRowCount {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return 0
    }
    $rows = @(Import-Csv -LiteralPath $Path)
    return $rows.Count
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

function Resolve-Target {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) {
        Fail-Usage "Missing -Target. Supported target: keysight-34461a."
    }
    $normalized = $Value.Trim().ToLowerInvariant()
    if ($normalized -ne "keysight-34461a") {
        Fail-Usage "Unsupported target '$Value'. Supported target: keysight-34461a."
    }
    return $normalized
}

function Resolve-Connection {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) {
        Fail-Usage "Missing -Connection. Supported connections: usb, local, lan, network."
    }
    $normalized = $Value.Trim().ToLowerInvariant()
    switch ($normalized) {
        "usb" { return "usb" }
        "local" { return "usb" }
        "lan" { return "lan" }
        "network" { return "lan" }
        default {
            Fail-Usage "Unsupported connection '$Value'. Supported connections: usb/local and lan/network."
        }
    }
}

function New-SafeCaseName {
    param([Parameter(Mandatory = $true)][string]$Name)
    return ($Name -replace '[^A-Za-z0-9_.-]', '_')
}

function New-LiveCase {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string[]]$ModeArgs,
        [Parameter(Mandatory = $true)][int]$ExpectedCaptured,
        [int]$SoftTriggerCount = 0,
        [int]$ExternalEdges = 0,
        [int]$TimeoutSeconds = 45
    )

    return [pscustomobject]@{
        name = $Name
        mode_args = $ModeArgs
        expected_captured = $ExpectedCaptured
        soft_trigger_count = $SoftTriggerCount
        external_edges = $ExternalEdges
        timeout_seconds = $TimeoutSeconds
    }
}

function Get-LiveCases {
    param([Parameter(Mandatory = $true)][string]$SelectedSuite)

    $minimal = @()
    $minimal += New-LiveCase `
        -Name "minimal_current_dc_immediate" `
        -ModeArgs @("--trigger-mode", "immediate", "--measurement", "current-dc", "--max-samples", "1") `
        -ExpectedCaptured 1

    $basic = @()
    $basic += New-LiveCase -Name "basic_immediate_current_dc" -ModeArgs @("--trigger-mode", "immediate", "--measurement", "current-dc", "--max-samples", "1") -ExpectedCaptured 1
    $basic += New-LiveCase -Name "basic_immediate_voltage_dc" -ModeArgs @("--trigger-mode", "immediate", "--measurement", "voltage-dc", "--max-samples", "1") -ExpectedCaptured 1
    $basic += New-LiveCase -Name "basic_immediate_current_ac" -ModeArgs @("--trigger-mode", "immediate", "--measurement", "current-ac", "--max-samples", "1") -ExpectedCaptured 1
    $basic += New-LiveCase -Name "basic_immediate_voltage_ac" -ModeArgs @("--trigger-mode", "immediate", "--measurement", "voltage-ac", "--max-samples", "1") -ExpectedCaptured 1
    $basic += New-LiveCase -Name "basic_immediate_resistance_2w" -ModeArgs @("--trigger-mode", "immediate", "--measurement", "resistance-2w", "--max-samples", "1") -ExpectedCaptured 1
    $basic += New-LiveCase -Name "basic_immediate_resistance_4w" -ModeArgs @("--trigger-mode", "immediate", "--measurement", "resistance-4w", "--max-samples", "1") -ExpectedCaptured 1
    $basic += New-LiveCase -Name "basic_software_trigger" -ModeArgs @("--trigger-mode", "software", "--measurement", "current-dc", "--max-samples", "1") -ExpectedCaptured 1 -SoftTriggerCount 1
    $basic += New-LiveCase -Name "basic_software_timer" -ModeArgs @("--trigger-mode", "software", "--timer-interval-s", "0.5", "--measurement", "current-dc", "--max-samples", "1") -ExpectedCaptured 1
    $basic += New-LiveCase -Name "basic_immediate_custom" -ModeArgs @("--trigger-mode", "immediate-custom", "--measurement", "current-dc", "--trigger-count", "1", "--sample-count", "1") -ExpectedCaptured 1
    $basic += New-LiveCase -Name "basic_software_custom" -ModeArgs @("--trigger-mode", "software-custom", "--measurement", "current-dc", "--trigger-count", "1", "--sample-count", "1") -ExpectedCaptured 1 -SoftTriggerCount 1

    $external = @()
    $external += New-LiveCase -Name "external_simple" -ModeArgs @("--trigger-mode", "external", "--measurement", "current-dc", "--max-samples", "1", "--trigger-timeout-ms", "10000") -ExpectedCaptured 1 -ExternalEdges 1 -TimeoutSeconds 60
    $external += New-LiveCase -Name "external_custom" -ModeArgs @("--trigger-mode", "external-custom", "--measurement", "current-dc", "--trigger-count", "1", "--sample-count", "1", "--trigger-timeout-ms", "10000") -ExpectedCaptured 1 -ExternalEdges 1 -TimeoutSeconds 60

    switch ($SelectedSuite) {
        "minimal" { return $minimal }
        "basic" { return $basic }
        "external" { return $external }
        "full" { return @($basic + $external) }
    }
}

function New-StartArgs {
    param(
        [Parameter(Mandatory = $true)][object]$Case,
        [Parameter(Mandatory = $true)][string]$CsvPath,
        [Parameter(Mandatory = $true)][int]$Port
    )

    return @(
        "-m", "keysight_logger.cli",
        "start-trigger-record",
        "--resource", $Resource,
        "--csv", $CsvPath,
        "--sw-trigger-port", [string]$Port,
        "--auto-range", "on",
        "--auto-zero", "off",
        "--nplc", "1.0",
        "--status-format", "jsonl"
    ) + $Case.mode_args
}

function Invoke-LiveDryRun {
    param(
        [Parameter(Mandatory = $true)][object]$Case,
        [Parameter(Mandatory = $true)][string]$CaseDir,
        [Parameter(Mandatory = $true)][int]$Port
    )

    $csv = Join-Path $CaseDir "live.csv"
    $jsonl = Join-Path $CaseDir "dry_run.jsonl"
    $stderr = Join-Path $CaseDir "dry_run.stderr.txt"
    $args = @((New-StartArgs -Case $Case -CsvPath $csv -Port $Port) + @("--dry-run"))
    $result = Invoke-CapturedCommand `
        -Name "$($Case.name)_dry_run" `
        -FilePath $Python `
        -Arguments $args `
        -StdOutPath $jsonl `
        -StdErrPath $stderr
    Assert-Condition ($result.success) "$($Case.name) dry-run failed"
    $events = @(Read-JsonLines -Path $jsonl)
    Assert-Condition ($events.Count -eq 1) "$($Case.name) dry-run should emit one plan"
    Assert-Condition ($events[0].event -eq "dry_run") "$($Case.name) dry-run event mismatch"

    Write-Host ""
    Write-Host "Live CLI plan: $($Case.name)"
    Write-Host "  Measurement: $($events[0].measurement_cli_name)"
    Write-Host "  Trigger mode: $($events[0].trigger_mode)"
    Write-Host "  Read path: $($events[0].read_path)"
    Write-Host "  Cleanup: $($events[0].cleanup_steps -join ', ')"
    Write-Host "  CSV: $csv"
    Write-Host "  SCPI/configuration:"
    foreach ($command in $events[0].scpi_commands) {
        Write-Host "    $command"
    }

    return [pscustomobject]@{
        command = [pscustomobject]$result
        plan = $events[0]
        csv = $csv
        jsonl = $jsonl
        stderr = $stderr
    }
}

function Invoke-LiveCase {
    param(
        [Parameter(Mandatory = $true)][object]$Case,
        [Parameter(Mandatory = $true)][string]$CaseDir,
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][string]$CsvPath
    )

    if ($Case.external_edges -gt 0) {
        Write-Host ""
        Write-Host "External trigger case: $($Case.name)"
        Write-Host "Required external trigger edges: $($Case.external_edges)"
        Write-Host "After pressing Enter, the logger will arm the instrument. Apply the trigger edge after the run starts."
        [void](Read-Host "Press Enter to start this external trigger case, or Ctrl+C to cancel")
    }

    $jsonl = Join-Path $CaseDir "live.jsonl"
    $stderr = Join-Path $CaseDir "live.stderr.txt"
    $args = New-StartArgs -Case $Case -CsvPath $CsvPath -Port $Port
    $result = Invoke-CapturedStartProcess `
        -Name "$($Case.name)_live" `
        -Arguments $args `
        -StdOutPath $jsonl `
        -StdErrPath $stderr `
        -TimeoutSeconds $Case.timeout_seconds `
        -SoftTriggerCount $Case.soft_trigger_count `
        -SoftTriggerPort $Port `
        -OutDir $CaseDir

    $failureReasons = [System.Collections.Generic.List[string]]::new()
    if (-not $result.success) {
        $failureReasons.Add("live command failed or timed out") | Out-Null
    }
    $captured = $null
    $errors = $null
    $events = @()
    if (Test-Path -LiteralPath $jsonl) {
        $events = @(Read-JsonLines -Path $jsonl)
    }
    $ready = @(Select-LastJsonEvent -Events $events -EventName "ready")
    $summary = @(Select-LastJsonEvent -Events $events -EventName "summary")
    if ($summary.Count -eq 1) {
        $captured = [int]$summary[0].captured
        $errors = [int]$summary[0].errors
        if ($captured -ne $Case.expected_captured) {
            $failureReasons.Add("captured count mismatch: expected=$($Case.expected_captured) actual=$captured") | Out-Null
        }
        if ($errors -ne 0) {
            $failureReasons.Add("errors should be 0; actual=$errors") | Out-Null
        }
    } else {
        $failureReasons.Add("summary event missing") | Out-Null
    }
    $rowCount = Test-CsvRowCount -Path $CsvPath
    if ($rowCount -lt $Case.expected_captured) {
        $failureReasons.Add("CSV row count mismatch: expected_at_least=$($Case.expected_captured) actual=$rowCount") | Out-Null
    }
    $caseStatus = if ($failureReasons.Count -eq 0) { "passed" } else { "failed" }

    return [pscustomobject]@{
        command = [pscustomobject]$result
        name = $Case.name
        status = $caseStatus
        failure_reasons = @($failureReasons.ToArray())
        expected_captured = $Case.expected_captured
        captured = $captured
        errors = $errors
        ready_events = $ready.Count
        csv_rows = $rowCount
        csv = $CsvPath
        jsonl = $jsonl
        stderr = $stderr
    }
}

function Write-LiveArtifacts {
    param(
        [Parameter(Mandatory = $true)][string]$Status,
        [Parameter(Mandatory = $true)][bool]$PlanOnlyRun,
        [Parameter(Mandatory = $true)][bool]$LiveExecuted,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$CaseItems,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$DryRunItems,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$CommandItems
    )

    $report = [ordered]@{
        schema_version = 1
        target = $resolvedTarget
        connection = $resolvedConnection
        suite = $Suite
        resource = $Resource
        generated_at = (Get-Date).ToUniversalTime().ToString("o")
        output_dir = $runDir
        status = $Status
        plan_only = $PlanOnlyRun
        live_executed = $LiveExecuted
        cases = @($CaseItems)
        dry_runs = @($DryRunItems)
        commands = @($CommandItems)
    }
    $report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $reportPath -Encoding UTF8

    $summaryLines = @(
        "# Live CLI Check Summary",
        "",
        "- Target: $resolvedTarget",
        "- Connection: $resolvedConnection",
        "- Suite: $Suite",
        "- Resource: $Resource",
        "- Status: $Status",
        "- Plan only: $PlanOnlyRun",
        "- Live executed: $LiveExecuted",
        "- Output directory: $runDir",
        "- Report: $reportPath",
        "",
        "## Dry Runs"
    )
    if ($DryRunItems.Count -eq 0) {
        $summaryLines += "- No dry-run plans generated."
    } else {
        foreach ($dryRun in $DryRunItems) {
            $summaryLines += "- $($dryRun.name): measurement=$($dryRun.plan.measurement_cli_name) trigger=$($dryRun.plan.trigger_mode) read_path=$($dryRun.plan.read_path) csv=$($dryRun.csv)"
        }
    }

    $summaryLines += @(
        "",
        "## Cases"
    )
    if ($CaseItems.Count -eq 0) {
        $summaryLines += "- No live cases executed."
    } else {
        foreach ($result in $CaseItems) {
            $line = "- $($result.name): status=$($result.status) captured=$($result.captured) errors=$($result.errors) csv_rows=$($result.csv_rows) csv=$($result.csv)"
            if ($result.status -ne "passed") {
                $line += " failure_reasons=$($result.failure_reasons -join '; ')"
            }
            $summaryLines += $line
        }
    }
    Set-Content -LiteralPath $summaryPath -Value $summaryLines -Encoding UTF8
}

if ([string]::IsNullOrWhiteSpace($Resource)) {
    Fail-Usage "Missing -Resource. Live checks never scan or guess a VISA resource."
}

$resolvedTarget = Resolve-Target -Value $Target
$resolvedConnection = Resolve-Connection -Value $Connection
$cases = @(Get-LiveCases -SelectedSuite $Suite)

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = Join-Path (Join-Path (Join-Path (Join-Path $LiveRoot $resolvedTarget) $resolvedConnection) $Suite) $timestamp
Assert-UnderTmpRoot -Path $runDir
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$commands = [System.Collections.Generic.List[object]]::new()
$caseResults = [System.Collections.Generic.List[object]]::new()
$dryRunResults = [System.Collections.Generic.List[object]]::new()
$reportPath = Join-Path $runDir "report.json"
$summaryPath = Join-Path $runDir "summary.md"
$stdinRedirected = [Console]::IsInputRedirected

if (-not ($stdinRedirected -and (-not $PlanOnly))) {
    $preflightOut = Join-Path $runDir "preflight.stdout.txt"
    $preflightErr = Join-Path $runDir "preflight.stderr.txt"
    $preflightResult = Invoke-CapturedCommand `
        -Name "preflight" `
        -FilePath "powershell.exe" `
        -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $PreflightScript, "-Target", $resolvedTarget) `
        -StdOutPath $preflightOut `
        -StdErrPath $preflightErr
    $commands.Add([pscustomobject]$preflightResult) | Out-Null

    if (-not $preflightResult.success) {
        Write-LiveArtifacts `
            -Status "preflight_failed" `
            -PlanOnlyRun ([bool]$PlanOnly) `
            -LiveExecuted $false `
            -CaseItems @() `
            -DryRunItems @() `
            -CommandItems @($commands.ToArray())
        throw "Preflight failed. See $preflightOut and $preflightErr"
    }
}

Write-Host ""
Write-Host "Live CLI check"
Write-Host "Target: $resolvedTarget"
Write-Host "Connection: $resolvedConnection"
Write-Host "Suite: $Suite"
Write-Host "Resource: $Resource"
Write-Host "Output directory: $runDir"
Write-Host ""
if ($PlanOnly) {
    Write-Host "PlanOnly: generating dry-run plans only; no VISA resource will be opened."
} elseif ($stdinRedirected) {
    Write-Host "Stdin is redirected; generating dry-run plans only before refusing live acquisition."
} else {
    Write-Host "Possible state changes:"
    Write-Host "  Connects to the explicit VISA resource and validates 34461A identity."
    Write-Host "  Sends the existing CLI clear/reset and measurement setup sequence for each case."
    Write-Host "  Uses best-effort release/local cleanup; no initial state snapshot/restore is available."
}

foreach ($case in $cases) {
    $caseName = New-SafeCaseName -Name $case.name
    $caseDir = Join-Path $runDir $caseName
    Assert-UnderTmpRoot -Path $caseDir
    New-Item -ItemType Directory -Force -Path $caseDir | Out-Null
    $port = Get-Random -Minimum 20000 -Maximum 60000
    $dryRun = Invoke-LiveDryRun -Case $case -CaseDir $caseDir -Port $port
    $dryRunResults.Add([pscustomobject]@{
        name = $case.name
        port = $port
        case_dir = $caseDir
        csv = $dryRun.csv
        command = $dryRun.command
        plan = $dryRun.plan
    }) | Out-Null
    $commands.Add($dryRun.command) | Out-Null
}

if ($PlanOnly) {
    Write-LiveArtifacts `
        -Status "planned" `
        -PlanOnlyRun $true `
        -LiveExecuted $false `
        -CaseItems @() `
        -DryRunItems @($dryRunResults.ToArray()) `
        -CommandItems @($commands.ToArray())
    Write-Host "live CLI plan generated: $Suite"
    Write-Host "summary: $summaryPath"
    exit 0
}

if ($stdinRedirected) {
    Write-LiveArtifacts `
        -Status "confirmation_required" `
        -PlanOnlyRun $false `
        -LiveExecuted $false `
        -CaseItems @() `
        -DryRunItems @($dryRunResults.ToArray()) `
        -CommandItems @($commands.ToArray())
    Write-Host "summary: $summaryPath"
    throw "Live suite requires interactive Enter confirmation; stdin is redirected."
}

Write-Host ""
[void](Read-Host "Press Enter to run suite '$Suite', or Ctrl+C to cancel")

$suiteStatus = "passed"
$liveExecuted = $true
foreach ($caseInfo in @($dryRunResults.ToArray())) {
    $case = @($cases | Where-Object { $_.name -eq $caseInfo.name } | Select-Object -First 1)[0]
    $liveResult = Invoke-LiveCase `
        -Case $case `
        -CaseDir $caseInfo.case_dir `
        -Port $caseInfo.port `
        -CsvPath $caseInfo.csv
    $caseResults.Add($liveResult) | Out-Null
    $commands.Add($liveResult.command) | Out-Null
    if ($liveResult.status -eq "passed") {
        Write-Host "live case passed: $($case.name)"
    } else {
        $suiteStatus = "failed"
        Write-Host "live case failed: $($case.name)"
        Write-Host "failure reasons: $($liveResult.failure_reasons -join '; ')"
        break
    }
}

Write-LiveArtifacts `
    -Status $suiteStatus `
    -PlanOnlyRun $false `
    -LiveExecuted $liveExecuted `
    -CaseItems @($caseResults.ToArray()) `
    -DryRunItems @($dryRunResults.ToArray()) `
    -CommandItems @($commands.ToArray())

if ($suiteStatus -ne "passed") {
    throw "Live CLI suite failed: $Suite. See $summaryPath"
}

Write-Host "live CLI suite passed: $Suite"
Write-Host "summary: $summaryPath"
