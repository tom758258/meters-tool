param(
    [Alias("Model", "Profile")]
    [string]$Target,

    [Alias("Transport")]
    [string]$Connection,

    [string]$Resource,

    [Alias("Backend")]
    [string]$VisaLibrary,

    [ValidateSet("minimal", "basic", "frequency-period", "external", "full")]
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
$ScpiProbeScript = Join-Path $PSScriptRoot "_frequency_period_scpi_probe.py"
. (Join-Path $PSScriptRoot "_validation_helpers.ps1")

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python executable not found: $Python"
}

Add-RepoSrcToPythonPath -RepoRoot $RepoRoot

function Fail-Usage {
    param([Parameter(Mandatory = $true)][string]$Message)
    [Console]::Error.WriteLine($Message)
    exit 2
}

function Assert-UnderTmpRoot {
    param([Parameter(Mandatory = $true)][string]$Path)
    Assert-PathUnderRoot `
        -RootPath $TmpRoot `
        -Path $Path `
        -Message "Refusing to write outside .tmp_tests: {0}"
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
        $readinessResult = Invoke-ReadinessClientChecks `
            -Name $Name `
            -Port $SoftTriggerPort `
            -OutDir $OutDir
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
                -OutDir $OutDir
            $clientResults.Add([pscustomobject]$triggerResult) | Out-Null
            if (-not $triggerResult.success) {
                $clientFailure = "send-command $index failed"
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
                -Arguments @("-m", "meters_tool_cli", "stop", "--format", "json", "--port", [string]$SoftTriggerPort) `
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
    Write-Utf8NoBomText -LiteralPath $StdOutPath -Text $stdout
    Write-Utf8NoBomText -LiteralPath $StdErrPath -Text $stderr

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
                "-m", "meters_tool_cli",
                "send-command",
                "--format", "json",
                "--port", [string]$Port,
                "--arguments-json", $meta
            ) `
            -StdOutPath $stdoutPath `
            -StdErrPath $stderrPath
        if ($lastResult.success) {
            try {
                $event = Get-Content -LiteralPath $stdoutPath -Raw | ConvertFrom-Json -ErrorAction Stop
                if ($event.event -eq "send-command" -and $event.status -eq "accepted") {
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

function Invoke-ReadinessClientChecks {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][string]$OutDir
    )

    $waitOut = Join-Path $OutDir "$Name`_wait_ready.json"
    $waitErr = Join-Path $OutDir "$Name`_wait_ready.stderr.txt"
    $waitResult = Invoke-CapturedCommand `
        -Name "$Name`_wait_ready" `
        -FilePath $Python `
        -Arguments @("-m", "meters_tool_cli", "wait-ready", "--format", "json", "--port", [string]$Port) `
        -StdOutPath $waitOut `
        -StdErrPath $waitErr
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
        -StdErrPath $statusErr

    return [ordered]@{
        success = $statusResult.success
        commands = @([pscustomobject]$waitResult, [pscustomobject]$statusResult)
    }
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
        Fail-Usage "Missing -Target. Supported targets: keysight-34461a, keysight-34460a."
    }
    $normalized = $Value.Trim().ToLowerInvariant()
    if ($normalized -notin @("keysight-34461a", "keysight-34460a")) {
        Fail-Usage "Unsupported target '$Value'. Supported targets: keysight-34461a, keysight-34460a."
    }
    return $normalized
}

function Get-TargetCliModel {
    param([Parameter(Mandatory = $true)][string]$ResolvedTarget)
    switch ($ResolvedTarget) {
        "keysight-34461a" { return "34461A" }
        "keysight-34460a" { return "34460A" }
    }
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
        [string]$ExpectedMeasurementType,
        [string]$ExpectedUnit,
        [string[]]$ExpectedScpiCommands = @(),
        [int]$SoftTriggerCount = 0,
        [int]$ExternalEdges = 0,
        [int]$TimeoutSeconds = 45
    )

    return [pscustomobject]@{
        name = $Name
        mode_args = $ModeArgs
        expected_captured = $ExpectedCaptured
        expected_measurement_type = $ExpectedMeasurementType
        expected_unit = $ExpectedUnit
        expected_scpi_commands = $ExpectedScpiCommands
        soft_trigger_count = $SoftTriggerCount
        external_edges = $ExternalEdges
        timeout_seconds = $TimeoutSeconds
    }
}

function Get-LiveCases {
    param(
        [Parameter(Mandatory = $true)][string]$SelectedSuite,
        [Parameter(Mandatory = $true)][string]$ResolvedTarget
    )

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

    $frequencyPeriod = @()
    $frequencyPeriod += New-LiveCase `
        -Name "frequency_period_frequency_immediate" `
        -ModeArgs @(
            "--trigger-mode", "immediate",
            "--measurement", "frequency",
            "--ac-bandwidth-hz", "20",
            "--gate-time-s", "0.1",
            "--freq-period-timeout", "auto",
            "--max-samples", "1"
        ) `
        -ExpectedCaptured 1 `
        -ExpectedMeasurementType "frequency" `
        -ExpectedUnit "Hz" `
        -ExpectedScpiCommands @(
            "CONF:FREQ",
            "FREQ:VOLT:RANG:AUTO ON",
            "FREQ:RANG:LOW 20",
            "FREQ:APER 0.1",
            "FREQ:TIM:AUTO ON"
        )
    $frequencyPeriod += New-LiveCase `
        -Name "frequency_period_period_immediate" `
        -ModeArgs @(
            "--trigger-mode", "immediate",
            "--measurement", "period",
            "--ac-bandwidth-hz", "20",
            "--gate-time-s", "0.1",
            "--max-samples", "1"
        ) `
        -ExpectedCaptured 1 `
        -ExpectedMeasurementType "period" `
        -ExpectedUnit "s" `
        -ExpectedScpiCommands @(
            "CONF:PER",
            "PER:VOLT:RANG:AUTO ON",
            "PER:RANG:LOW 20",
            "PER:APER 0.1"
        )

    $external = @()
    $external += New-LiveCase -Name "external_simple" -ModeArgs @("--trigger-mode", "external", "--measurement", "current-dc", "--max-samples", "1", "--trigger-timeout-ms", "10000") -ExpectedCaptured 1 -ExternalEdges 1 -TimeoutSeconds 60
    $external += New-LiveCase -Name "external_custom" -ModeArgs @("--trigger-mode", "external-custom", "--measurement", "current-dc", "--trigger-count", "1", "--sample-count", "1", "--trigger-timeout-ms", "10000") -ExpectedCaptured 1 -ExternalEdges 1 -TimeoutSeconds 60

    if ($ResolvedTarget -eq "keysight-34460a" -and $SelectedSuite -eq "external") {
        Fail-Usage "Suite 'external' is not supported for keysight-34460a because the base 34460A profile does not support external trigger modes."
    }

    switch ($SelectedSuite) {
        "minimal" { return $minimal }
        "basic" { return $basic }
        "frequency-period" { return $frequencyPeriod }
        "external" { return $external }
        "full" {
            if ($ResolvedTarget -eq "keysight-34460a") {
                return @($basic + $frequencyPeriod)
            }
            return @($basic + $frequencyPeriod + $external)
        }
    }
}

function New-StartArgs {
    param(
        [Parameter(Mandatory = $true)][object]$Case,
        [Parameter(Mandatory = $true)][string]$CsvPath,
        [Parameter(Mandatory = $true)][int]$Port
    )

    $args = @(
        "-m", "meters_tool_cli",
        "start-trigger-record",
        "--validation-allow-pending-live-support",
        "--resource", $Resource,
        "--model", $resolvedCliModel,
        "--csv", $CsvPath,
        "--sw-trigger-port", [string]$Port,
        "--auto-range", "on",
        "--auto-zero", "off",
        "--nplc", "1.0",
        "--status-format", "jsonl"
    )
    if (-not [string]::IsNullOrWhiteSpace($resolvedVisaLibrary)) {
        $args += @("--visa-library", $resolvedVisaLibrary)
    }
    return $args + $Case.mode_args
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
    if (-not [string]::IsNullOrWhiteSpace($Case.expected_unit)) {
        Assert-Condition ($events[0].measurement_unit -eq $Case.expected_unit) "$($Case.name) dry-run unit mismatch"
    }
    if ($Case.expected_scpi_commands.Count -gt 0) {
        $actualScpi = @($events[0].scpi_commands)
        Assert-Condition `
            (($actualScpi -join "`n") -eq ($Case.expected_scpi_commands -join "`n")) `
            "$($Case.name) dry-run SCPI sequence mismatch"
    }

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

function Format-ScpiErrorResponses {
    param([AllowNull()][object[]]$Responses)
    if ($null -eq $Responses -or @($Responses).Count -eq 0) {
        return "none"
    }
    return (
        @(
            $Responses | ForEach-Object {
                "code=$($_.code) raw=$($_.raw)"
            }
        ) -join " | "
    )
}

function Invoke-FrequencyPeriodScpiProbe {
    param(
        [Parameter(Mandatory = $true)][object]$CaseInfo
    )

    $measurement = [string]$CaseInfo.plan.measurement_cli_name
    $json = Join-Path $CaseInfo.case_dir "scpi_probe.json"
    $stderr = Join-Path $CaseInfo.case_dir "scpi_probe.stderr.txt"
    $args = @(
        $ScpiProbeScript,
        "--resource", $Resource,
        "--model", $resolvedCliModel,
        "--measurement", $measurement,
        "--timeout-ms", "5000"
    )
    if (-not [string]::IsNullOrWhiteSpace($resolvedVisaLibrary)) {
        $args += @("--visa-library", $resolvedVisaLibrary)
    }
    foreach ($scpiCommand in @($CaseInfo.plan.scpi_commands)) {
        $args += @("--command", [string]$scpiCommand)
    }

    $commandResult = Invoke-CapturedCommand `
        -Name "$($CaseInfo.name)_scpi_probe" `
        -FilePath $Python `
        -Arguments $args `
        -StdOutPath $json `
        -StdErrPath $stderr

    try {
        $diagnostic = Get-Content -LiteralPath $json -Raw | ConvertFrom-Json -ErrorAction Stop
    } catch {
        $diagnostic = [pscustomobject]@{
            schema_version = 1
            resource = $Resource
            measurement = $measurement
            status = "failed"
            all_scpi_error_responses_zero = $false
            idn = $null
            firmware_revision = $null
            identity_system_errors = $null
            commands = @()
            read = $null
            failure_reasons = @("probe did not emit valid JSON: $($_.Exception.Message)")
            cleanup = $null
        }
    }
    $diagnostic | Add-Member -NotePropertyName artifact_path -NotePropertyValue $json -Force
    $diagnostic | Add-Member -NotePropertyName stderr_path -NotePropertyValue $stderr -Force

    return [pscustomobject]@{
        success = (
            $commandResult.success -and
            $diagnostic.status -eq "passed" -and
            [bool]$diagnostic.all_scpi_error_responses_zero
        )
        command = [pscustomobject]$commandResult
        diagnostic = $diagnostic
    }
}

function New-ScpiProbeFailureCaseResult {
    param(
        [Parameter(Mandatory = $true)][object]$Case,
        [Parameter(Mandatory = $true)][object]$CaseInfo,
        [Parameter(Mandatory = $true)][object]$Probe
    )

    $failureReasons = @("SCPI probe failed; formal live CLI run skipped")
    $failureReasons += @($Probe.diagnostic.failure_reasons)
    return [pscustomobject]@{
        command = $Probe.command
        name = $Case.name
        status = "failed"
        failure_reasons = $failureReasons
        run_id = $null
        expected_captured = $Case.expected_captured
        captured_count = $null
        captured = $null
        errors = $null
        ready_events = 0
        csv_row_count = 0
        csv_rows = 0
        measurement_type = $Case.expected_measurement_type
        unit = $Case.expected_unit
        value = $null
        csv = $CaseInfo.csv
        jsonl = $null
        stderr = $Probe.diagnostic.stderr_path
        live_command_skipped = $true
        scpi_probe_command = $Probe.command
        scpi_diagnostic_path = $Probe.diagnostic.artifact_path
        scpi_diagnostic = $Probe.diagnostic
    }
}

function Invoke-LiveCase {
    param(
        [Parameter(Mandatory = $true)][object]$Case,
        [Parameter(Mandatory = $true)][string]$CaseDir,
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][string]$CsvPath,
        [AllowNull()][object]$ScpiProbeCommand,
        [AllowNull()][object]$ScpiDiagnostic
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
    $runId = $null
    if ($ready.Count -eq 1) {
        $runId = $ready[0].run_id
    } elseif ($summary.Count -eq 1) {
        $runId = $summary[0].run_id
    }
    if ($Case.soft_trigger_count -gt 0) {
        if ($ready.Count -ne 1) {
            $failureReasons.Add("ready event missing") | Out-Null
        }
        $statusCommand = @($result.client_commands | Where-Object { $_.name -eq "$($Case.name)_live_soft_status" } | Select-Object -Last 1)
        if ($statusCommand.Count -ne 1) {
            $failureReasons.Add("status client command missing") | Out-Null
        } elseif ($ready.Count -eq 1) {
            $statusPayload = Get-Content -LiteralPath $statusCommand[0].stdout -Raw | ConvertFrom-Json -ErrorAction Stop
            if ($statusPayload.run_id -ne $ready[0].run_id) {
                $failureReasons.Add("status run_id mismatch") | Out-Null
            }
        }
    }
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
    $measurementType = $null
    $unit = $null
    $value = $null
    if ($rowCount -gt 0) {
        $firstRow = @(Import-Csv -LiteralPath $CsvPath)[0]
        $measurementType = $firstRow.measurement_type
        $unit = $firstRow.unit
        $value = $firstRow.value
        if (
            -not [string]::IsNullOrWhiteSpace($Case.expected_measurement_type) -and
            $measurementType -ne $Case.expected_measurement_type
        ) {
            $failureReasons.Add(
                "CSV measurement type mismatch: expected=$($Case.expected_measurement_type) actual=$measurementType"
            ) | Out-Null
        }
        if (-not [string]::IsNullOrWhiteSpace($Case.expected_unit) -and $unit -ne $Case.expected_unit) {
            $failureReasons.Add("CSV unit mismatch: expected=$($Case.expected_unit) actual=$unit") | Out-Null
        }
    }
    if (
        $null -ne $ScpiDiagnostic -and
        -not [bool]$ScpiDiagnostic.all_scpi_error_responses_zero
    ) {
        $failureReasons.Add("SCPI diagnostic contains a non-zero error response") | Out-Null
    }
    $caseStatus = if ($failureReasons.Count -eq 0) { "passed" } else { "failed" }

    return [pscustomobject]@{
        command = [pscustomobject]$result
        name = $Case.name
        status = $caseStatus
        failure_reasons = @($failureReasons.ToArray())
        run_id = $runId
        expected_captured = $Case.expected_captured
        captured_count = $captured
        captured = $captured
        errors = $errors
        ready_events = $ready.Count
        csv_row_count = $rowCount
        csv_rows = $rowCount
        measurement_type = $measurementType
        unit = $unit
        value = $value
        csv = $CsvPath
        jsonl = $jsonl
        stderr = $stderr
        live_command_skipped = $false
        scpi_probe_command = $ScpiProbeCommand
        scpi_diagnostic_path = if ($null -eq $ScpiDiagnostic) { $null } else { $ScpiDiagnostic.artifact_path }
        scpi_diagnostic = $ScpiDiagnostic
    }
}

function Write-LiveArtifacts {
    param(
        [Parameter(Mandatory = $true)][string]$Status,
        [Parameter(Mandatory = $true)][bool]$PlanOnlyRun,
        [Parameter(Mandatory = $true)][bool]$LiveExecuted,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$CaseItems,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$DryRunItems,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$ScpiDiagnosticItems,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$CommandItems
    )

    $report = [ordered]@{
        schema_version = 1
        target = $resolvedTarget
        connection = $resolvedConnection
        visa_library = if ([string]::IsNullOrWhiteSpace($resolvedVisaLibrary)) { "system_visa" } else { $resolvedVisaLibrary }
        backend = if ([string]::IsNullOrWhiteSpace($resolvedVisaLibrary)) { "system_visa" } else { $resolvedVisaLibrary }
        support_policy_mode = "validation"
        pending_live_support_allowed = $true
        suite = $Suite
        resource = $Resource
        generated_at = (Get-Date).ToUniversalTime().ToString("o")
        package_version = Get-PackageVersion
        git_head = Get-GitHead
        validation_mode = if ($PlanOnlyRun) { "live_plan_only" } elseif ($LiveExecuted) { "live" } else { "live_not_executed" }
        output_dir = $runDir
        artifact_paths = [ordered]@{
            output_dir = $runDir
            report = $reportPath
            summary = $summaryPath
        }
        status = $Status
        plan_only = $PlanOnlyRun
        live_executed = $LiveExecuted
        cases = @($CaseItems)
        dry_runs = @($DryRunItems)
        scpi_diagnostics = @($ScpiDiagnosticItems)
        commands = @($CommandItems)
    }
    Write-JsonReport -LiteralPath $reportPath -Report $report -Depth 12

    $summaryLines = @(
        "# Live CLI Check Summary",
        "",
        "- Target: $resolvedTarget",
        "- Connection: $resolvedConnection",
        "- VISA library/backend: $($report.visa_library)",
        "- Support policy mode: $($report.support_policy_mode)",
        "- Pending live support allowed: $($report.pending_live_support_allowed)",
        "- Suite: $Suite",
        "- Resource: $Resource",
        "- Status: $Status",
        "- Package version: $($report.package_version)",
        "- Git HEAD: $($report.git_head)",
        "- Validation mode: $($report.validation_mode)",
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
        "## SCPI Diagnostics"
    )
    if ($ScpiDiagnosticItems.Count -eq 0) {
        $summaryLines += "- No SCPI probes executed."
    } else {
        foreach ($diagnostic in $ScpiDiagnosticItems) {
            $summaryLines += "- measurement=$($diagnostic.measurement) status=$($diagnostic.status) idn=$($diagnostic.idn) firmware=$($diagnostic.firmware_revision) artifact=$($diagnostic.artifact_path)"
            if ($null -ne $diagnostic.identity_system_errors) {
                $summaryLines += "  - *IDN? SYST:ERR?: $(Format-ScpiErrorResponses -Responses @($diagnostic.identity_system_errors.responses))"
            }
            foreach ($record in @($diagnostic.commands)) {
                $detail = Format-ScpiErrorResponses -Responses @($record.system_error_responses)
                if (-not [string]::IsNullOrWhiteSpace($record.transport_error)) {
                    $detail += " transport_error=$($record.transport_error)"
                }
                if (-not [string]::IsNullOrWhiteSpace($record.system_error_query_error)) {
                    $detail += " SYST:ERR?_error=$($record.system_error_query_error)"
                }
                $summaryLines += "  - $($record.command): $detail"
            }
            if ($null -ne $diagnostic.read) {
                $readDetail = Format-ScpiErrorResponses -Responses @($diagnostic.read.system_error_responses)
                if (-not [string]::IsNullOrWhiteSpace($diagnostic.read.transport_error)) {
                    $readDetail += " transport_error=$($diagnostic.read.transport_error)"
                }
                if (-not [string]::IsNullOrWhiteSpace($diagnostic.read.system_error_query_error)) {
                    $readDetail += " SYST:ERR?_error=$($diagnostic.read.system_error_query_error)"
                }
                $summaryLines += "  - READ? response=$($diagnostic.read.response): $readDetail"
            }
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
            $line = "- $($result.name): status=$($result.status) run_id=$($result.run_id) expected_captured=$($result.expected_captured) captured=$($result.captured) errors=$($result.errors) csv_rows=$($result.csv_rows) measurement_type=$($result.measurement_type) value=$($result.value) unit=$($result.unit) csv=$($result.csv)"
            if ($result.status -ne "passed") {
                $line += " failure_reasons=$($result.failure_reasons -join '; ')"
            }
            $summaryLines += $line
        }
    }
    Write-Utf8NoBomLines -LiteralPath $summaryPath -Lines $summaryLines
}

if ([string]::IsNullOrWhiteSpace($Resource)) {
    Fail-Usage "Missing -Resource. Live checks never scan or guess a VISA resource."
}

$resolvedTarget = Resolve-Target -Value $Target
$resolvedCliModel = Get-TargetCliModel -ResolvedTarget $resolvedTarget
$resolvedConnection = Resolve-Connection -Value $Connection
$resolvedVisaLibrary = if ([string]::IsNullOrWhiteSpace($VisaLibrary)) { $null } else { $VisaLibrary.Trim() }
$cases = @(Get-LiveCases -SelectedSuite $Suite -ResolvedTarget $resolvedTarget)

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = Join-Path (Join-Path (Join-Path (Join-Path $LiveRoot $resolvedTarget) $resolvedConnection) $Suite) $timestamp
Assert-UnderTmpRoot -Path $runDir
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$commands = [System.Collections.Generic.List[object]]::new()
$caseResults = [System.Collections.Generic.List[object]]::new()
$dryRunResults = [System.Collections.Generic.List[object]]::new()
$scpiDiagnostics = [System.Collections.Generic.List[object]]::new()
$reportPath = Join-Path $runDir "report.json"
$summaryPath = Join-Path $runDir "summary.md"
$stdinRedirected = [Console]::IsInputRedirected

if (-not ($stdinRedirected -and (-not $PlanOnly))) {
    $preflightOut = Join-Path $runDir "preflight.stdout.txt"
    $preflightErr = Join-Path $runDir "preflight.stderr.txt"
    $preflightRoot = Join-Path $runDir "preflight"
    $preflightResult = Invoke-CapturedCommand `
        -Name "preflight" `
        -FilePath "powershell.exe" `
        -Arguments @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            $PreflightScript,
            "-Target",
            $resolvedTarget,
            "-OutputRoot",
            $preflightRoot
        ) `
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
            -ScpiDiagnosticItems @() `
            -CommandItems @($commands.ToArray())
        throw "Preflight failed. See $preflightOut and $preflightErr"
    }
}

Write-Host ""
Write-Host "Live CLI check"
Write-Host "Target: $resolvedTarget"
Write-Host "Connection: $resolvedConnection"
Write-Host "VISA library/backend: $(if ([string]::IsNullOrWhiteSpace($resolvedVisaLibrary)) { 'system_visa' } else { $resolvedVisaLibrary })"
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
    Write-Host "  Connects to the explicit VISA resource and validates $resolvedCliModel identity."
    Write-Host "  Frequency/Period cases run isolated SCPI diagnostic sessions before the formal CLI run."
    Write-Host "  Sends the existing CLI clear/reset and measurement setup sequence for each case."
    Write-Host "  Uses best-effort release/local cleanup; no initial state snapshot/restore is available."
}

foreach ($case in $cases) {
    $caseName = New-SafeCaseName -Name $case.name
    $caseDir = Join-Path $runDir $caseName
    Assert-UnderTmpRoot -Path $caseDir
    New-Item -ItemType Directory -Force -Path $caseDir | Out-Null
    $port = Get-AvailableTcpPort
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
        -ScpiDiagnosticItems @() `
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
        -ScpiDiagnosticItems @() `
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
    $scpiProbeCommand = $null
    $scpiDiagnostic = $null
    if ($caseInfo.plan.measurement_cli_name -in @("frequency", "period")) {
        $probe = Invoke-FrequencyPeriodScpiProbe -CaseInfo $caseInfo
        $commands.Add($probe.command) | Out-Null
        $scpiDiagnostics.Add($probe.diagnostic) | Out-Null
        $scpiProbeCommand = $probe.command
        $scpiDiagnostic = $probe.diagnostic
        if (-not $probe.success) {
            $probeFailure = New-ScpiProbeFailureCaseResult `
                -Case $case `
                -CaseInfo $caseInfo `
                -Probe $probe
            $caseResults.Add($probeFailure) | Out-Null
            $suiteStatus = "failed"
            Write-Host "SCPI probe failed: $($case.name)"
            Write-Host "failure reasons: $($probeFailure.failure_reasons -join '; ')"
            continue
        }
    }
    $liveResult = Invoke-LiveCase `
        -Case $case `
        -CaseDir $caseInfo.case_dir `
        -Port $caseInfo.port `
        -CsvPath $caseInfo.csv `
        -ScpiProbeCommand $scpiProbeCommand `
        -ScpiDiagnostic $scpiDiagnostic
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
    -ScpiDiagnosticItems @($scpiDiagnostics.ToArray()) `
    -CommandItems @($commands.ToArray())

if ($suiteStatus -ne "passed") {
    throw "Live CLI suite failed: $Suite. See $summaryPath"
}

Write-Host "live CLI suite passed: $Suite"
Write-Host "summary: $summaryPath"
