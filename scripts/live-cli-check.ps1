param(
    [Alias("Model", "Profile")]
    [string]$Target,

    [Alias("Transport")]
    [string]$Connection,

    [string]$Resource,

    [Alias("Backend", "visa-library")]
    [string]$VisaLibrary,

    [ValidateSet("minimal", "basic", "frequency-period", "external", "finite-custom", "infinite-custom", "overflow", "worker-streaming", "full")]
    [string]$Suite = "minimal",

    [switch]$PlanOnly,
    [switch]$DebugArtifacts,

    [switch]$SkipPreflight
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
. (Join-Path $PSScriptRoot "_artifact_privacy.ps1")

if (-not (Test-Path -LiteralPath $Python)) {
        throw "Repository virtual-environment Python executable not found."
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
        [int]$TimeoutSeconds = 45,
        [int]$PlannedStopAfterSeconds = 0,
        [int]$ExpectedExitCode = 0,
        [string]$ExpectedStopReason = "",
        [int]$MinCaptured = 0,
        [bool]$ExpectOverflow = $false,
        [bool]$RequireContinuedDrain = $false,
        [bool]$Streaming = $false
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
        planned_stop_after_seconds = $PlannedStopAfterSeconds
        expected_exit_code = $ExpectedExitCode
        expected_stop_reason = $ExpectedStopReason
        min_captured = $MinCaptured
        expect_overflow = $ExpectOverflow
        require_continued_drain = $RequireContinuedDrain
        streaming = $Streaming
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

    $finiteCustom = @()
    $infiniteCustom = @()
    $overflow = @()
    $customModes = @("immediate", "software")
    if ($ResolvedTarget -eq "keysight-34461a") { $customModes += "external" }
    foreach ($mode in $customModes) {
        $softTriggers = if ($mode -eq "software") { 1 } else { 0 }
        $externalEdges = if ($mode -eq "external") { 1 } else { 0 }
        foreach ($handling in @("monitor", "stop_on_overflow")) {
            $monitorArg = if ($handling -eq "monitor") { "--monitor-overflow" } else { "--stop-on-overflow" }
            $modeArgs = @("--trigger-mode", "$mode-custom", "--measurement", "current-dc", $monitorArg)
            $finiteCustom += New-LiveCase -Name "finite_${mode}_${handling}" `
                -ModeArgs @($modeArgs + @("--trigger-count", "1", "--sample-count", "2")) `
                -ExpectedCaptured 2 -SoftTriggerCount $softTriggers -ExternalEdges $externalEdges `
                -ExpectedStopReason "completed"
            $streamName = if ($handling -eq "monitor") { "infinite_custom_$mode" } else { "infinite_custom_${mode}_stop_on_overflow" }
            $streamTriggers = if ($mode -eq "software") { 2 } else { 0 }
            $streamEdges = if ($mode -eq "external") { 2 } else { 0 }
            $streamMinimum = if ($mode -eq "immediate") { 1 } else { 2 }
            $streamStop = if ($mode -eq "external") { 10 } else { 3 }
            $infiniteCustom += New-LiveCase -Name $streamName `
                -ModeArgs @($modeArgs + @("--trigger-count-infinite", "--sample-count", "1", "--allow-buffer-overflow-risk")) `
                -ExpectedCaptured -1 -MinCaptured $streamMinimum -SoftTriggerCount $streamTriggers -ExternalEdges $streamEdges `
                -PlannedStopAfterSeconds $streamStop -ExpectedStopReason "stop_requested"
            foreach ($count in @("finite", "infinite")) {
                $countArgs = if ($count -eq "finite") { @("--trigger-count", "1") } else { @("--trigger-count-infinite") }
                $plannedStop = if ($handling -eq "monitor") { 30 } else { 0 }
                $stopReason = if ($handling -eq "monitor") { "stop_requested" } else { "overflow_detected" }
                $overflow += New-LiveCase -Name "overflow_${mode}_${count}_${handling}" `
                    -ModeArgs @($modeArgs + $countArgs + @("--sample-count", "1000000", "--nplc", "0.02", "--buffer-drain-size", "1", "--allow-buffer-overflow-risk")) `
                    -ExpectedCaptured -1 -MinCaptured 1 -SoftTriggerCount $softTriggers -ExternalEdges $externalEdges `
                    -TimeoutSeconds 60 -PlannedStopAfterSeconds $plannedStop -ExpectedExitCode 3 `
                    -ExpectedStopReason $stopReason -ExpectOverflow $true -RequireContinuedDrain ($handling -eq "monitor")
            }
        }
    }

    if ($ResolvedTarget -eq "keysight-34460a" -and $SelectedSuite -eq "external") {
        Fail-Usage "Suite '$SelectedSuite' is not supported for keysight-34460a because the base 34460A profile does not support external trigger modes."
    }

    switch ($SelectedSuite) {
        "minimal" { return $minimal }
        "basic" { return $basic }
        "frequency-period" { return $frequencyPeriod }
        "external" { return $external }
        "finite-custom" { return $finiteCustom }
        "infinite-custom" { return $infiniteCustom }
        "overflow" { return $overflow }
        "worker-streaming" {
            $selected = @($basic | Where-Object { $_.name -in @(
                "basic_immediate_current_dc", "basic_software_trigger", "basic_software_timer"
            ) }) + @($finiteCustom + $infiniteCustom | Where-Object { $_.name -notlike '*stop_on_overflow' })
            if ($ResolvedTarget -eq "keysight-34461a") { $selected += $external[0] }
            foreach ($case in $selected) {
                $case.name = "worker_streaming_" + $case.name
                $case.streaming = $true
            }
            return $selected
        }
        "full" {
            if ($ResolvedTarget -eq "keysight-34460a") {
                return @($basic + $frequencyPeriod + $finiteCustom)
            }
            return @($basic + $frequencyPeriod + $external + $finiteCustom)
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
        "--csv-format", "full",
        "--sw-trigger-port", [string]$Port,
        "--auto-range", "on",
        "--auto-zero", "off",
        "--nplc", "1.0",
        "--status-format", "jsonl"
    )
    if (-not [string]::IsNullOrWhiteSpace($resolvedVisaLibrary)) {
        $args += @("--visa-library", $resolvedVisaLibrary)
    }
    if ($Case.streaming) { $args += @("--streaming", "--json") }
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
        -StdErrPath $stderr `
        -CaptureInMemory:(-not $DebugArtifacts)
    Assert-Condition ($result.success) "$($Case.name) dry-run failed"
    $events = @(Read-JsonLines -Path $jsonl -Text $result.stdout_text -FromText:(-not $DebugArtifacts))
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
    Write-Host "  CSV: <private-local-path>"
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
        -StdErrPath $stderr `
        -CaptureInMemory:(-not $DebugArtifacts)

    try {
        $probeText = if ($DebugArtifacts) { Get-Content -LiteralPath $json -Raw } else { $commandResult.stdout_text }
        $diagnostic = $probeText | ConvertFrom-Json -ErrorAction Stop
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

function Add-StreamingObservation {
    param([Parameter(Mandatory = $true)][hashtable]$State, [Parameter(Mandatory = $true)]$Event)

    # Validate ordered stdout independently of non-atomic HTTP snapshots.
    if ($null -eq $Event.PSObject.Properties['schema_version'] -or
        $Event.schema_version -isnot [int] -or $Event.schema_version -ne 2 -or
        $null -eq $Event.PSObject.Properties['event']) { throw 'Invalid streaming event envelope.' }
    if ($Event.event -in @('ready', 'status', 'sample', 'summary')) {
        if ($null -eq $Event.PSObject.Properties['run_id'] -or
            $Event.run_id -isnot [string] -or [string]::IsNullOrWhiteSpace($Event.run_id)) {
            throw 'Missing streaming run_id.'
        }
        if ($null -eq $State.run_id) { $State.run_id = $Event.run_id }
        if ($Event.run_id -ne $State.run_id) { throw 'Streaming run_id mismatch.' }
    }
    if ($Event.event -in @('ready', 'status')) {
        if ($null -eq $Event.PSObject.Properties['stream'] -or
            $null -eq $Event.stream -or $Event.stream.lifecycle -ne 'run_bound') {
            throw 'Missing run_bound stream declaration.'
        }
    }
    switch ($Event.event) {
        'ready' {
            if ($State.ready -or $State.phase -ne 'waiting' -or
                $null -ne $Event.stream.PSObject.Properties['state']) { throw 'Invalid streaming ready order.' }
            $State.ready = $true
        }
        'status' {
            $phase = $Event.stream.state
            $ranks = @{ waiting = 0; active = 1; ended = 2 }
            if ($phase -notin @('waiting', 'active', 'ended') -or
                $ranks[$phase] -lt $ranks[$State.phase]) { throw 'Streaming state regressed or is invalid.' }
            if ($phase -ne 'waiting' -and -not $State.ready) { throw 'Streaming transition before ready.' }
            if ($phase -ne $State.phase) { $State.transitions.Add($phase) | Out-Null }
            $State.phase = $phase
            if ($phase -eq 'active') { $State.active = $true }
            if ($null -ne $Event.PSObject.Properties['stopping'] -and $Event.stopping) { $State.stopping = $true }
            if (($null -ne $Event.PSObject.Properties['fatal_error'] -and $Event.fatal_error) -or
                ($null -ne $Event.PSObject.Properties['errors'] -and $Event.errors -gt 0)) {
                throw 'Worker reported an acquisition failure.'
            }
        }
        'sample' {
            if ($State.phase -ne 'active') { throw 'Sample outside the Active interval.' }
            $State.samples++
            if ($Event.captured -ne $State.samples) { throw 'Streaming sample counter mismatch.' }
        }
        'summary' {
            if ($State.phase -ne 'ended' -or $State.summary) { throw 'Missing Ended or duplicate Summary.' }
            $State.summary = $true
            if ($Event.captured -ne $State.samples) { throw 'Summary and JSONL sample count mismatch.' }
        }
        'error' { throw 'Worker emitted an error event.' }
    }
}

function Invoke-StreamingClient {
    param([string]$Command, [string]$Name, [int]$Port, [string]$OutDir)

    # Client processes also have a deadline; an HTTP timeout alone is insufficient.
    return Invoke-CapturedCommand -Name $Name -FilePath $Python `
        -Arguments @('-m', 'meters_tool_cli', $Command, '--json', '--port', [string]$Port, '--timeout-ms', '1000') `
        -StdOutPath (Join-Path $OutDir "$Name.json") -StdErrPath (Join-Path $OutDir "$Name.stderr.txt") `
        -CaptureInMemory -ProcessTimeoutMs 5000
}

function Invoke-StreamingStartProcess {
    param(
        [Parameter(Mandatory = $true)]$Case,
        [string[]]$Arguments, [string]$StdOutPath, [string]$StdErrPath,
        [int]$Port, [string]$OutDir,
        [int]$ActiveTimeoutMs = 15000, [int]$StopGracePeriodMs = 10000
    )

    $state = @{
        run_id = $null; ready = $false; active = $false; stopping = $false; phase = 'waiting'
        summary = $false; samples = 0; transitions = [System.Collections.Generic.List[string]]::new()
    }
    $lines = [System.Collections.Generic.List[string]]::new()
    $failures = [System.Collections.Generic.List[string]]::new()
    $clients = [System.Collections.Generic.List[object]]::new()
    $statusChecked = $false
    $httpEnded = $false
    $triggerCount = 0
    $externalPrompted = $false
    $stopSent = $false
    $forced = $false
    $timedOut = $false
    $eof = $false
    $activeAt = $null
    $nextTriggerAt = 0
    $stopAt = $null
    $exitAt = $null
    $clock = [System.Diagnostics.Stopwatch]::StartNew()
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $Python
    $psi.WorkingDirectory = $RepoRoot
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.Arguments = Join-ProcessArguments -Arguments $Arguments
    $process = [System.Diagnostics.Process]::Start($psi)
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $lineTask = $process.StandardOutput.ReadLineAsync()
    try {
        while ($true) {
            # Drain complete lines before deciding whether a dependent trigger is safe.
            $batch = 0
            while (-not $eof -and $lineTask.IsCompleted -and $batch -lt 1000) {
                $line = $lineTask.GetAwaiter().GetResult()
                if ($null -eq $line) { $eof = $true; break }
                $lines.Add($line) | Out-Null
                try {
                    if ([string]::IsNullOrWhiteSpace($line)) { throw 'Empty JSONL line.' }
                    Add-StreamingObservation -State $state -Event ($line | ConvertFrom-Json -ErrorAction Stop)
                } catch {
                    if ($failures.Count -eq 0) { $failures.Add('Invalid or unsuccessful streaming JSONL event.') | Out-Null }
                }
                $lineTask = $process.StandardOutput.ReadLineAsync()
                $batch++
            }
            $now = $clock.ElapsedMilliseconds
            if ($state.active -and $null -eq $activeAt) { $activeAt = $now }
            if ($process.HasExited) {
                if ($eof) { break }
                if ($null -eq $exitAt) { $exitAt = $now }
                if ($now - $exitAt -ge 2000) { $failures.Add('Stdout EOF deadline exceeded.') | Out-Null; break }
                Start-Sleep -Milliseconds 10
                continue
            }
            if ($null -ne $stopAt -and $now - $stopAt -ge $StopGracePeriodMs) {
                $forced = $true
                $failures.Add('Stop grace period exceeded; cleanup unconfirmed.') | Out-Null
                $process.Kill()
                if (-not $process.WaitForExit(2000)) { break }
                continue
            }
            if (-not $stopSent -and $now -ge $Case.timeout_seconds * 1000) {
                $timedOut = $true
                $failures.Add('Run deadline exceeded.') | Out-Null
            } elseif (-not $stopSent -and -not $state.active -and $now -ge $ActiveTimeoutMs) {
                $timedOut = $true
                $failures.Add('Active deadline exceeded; dependent triggers were withheld.') | Out-Null
            }
            $plannedStop = $null -ne $activeAt -and $Case.planned_stop_after_seconds -gt 0 -and
                $now - $activeAt -ge $Case.planned_stop_after_seconds * 1000
            if (-not $stopSent -and ($failures.Count -gt 0 -or $plannedStop)) {
                $stopSent = $true
                try {
                    $stop = Invoke-StreamingClient -Command 'stop' -Name "$($Case.name)_stop" -Port $Port -OutDir $OutDir
                } finally {
                    # The bounded Stop client does not consume the worker's cleanup grace.
                    $stopAt = $clock.ElapsedMilliseconds
                }
                $clients.Add([pscustomobject]$stop) | Out-Null
                $response = $stop.stdout_text | ConvertFrom-Json -ErrorAction Stop
                if (-not $stop.success -or $response.event -ne 'stop' -or $response.status -ne 'accepted') {
                    $failures.Add('HTTP Stop was not accepted.') | Out-Null
                }
                continue
            }
            $needsControl = $Case.soft_trigger_count -gt 0 -or $Case.external_edges -gt 0 -or $Case.planned_stop_after_seconds -gt 0
            if (-not $stopSent -and $failures.Count -eq 0 -and $state.ready -and $state.active -and
                $state.phase -ne 'ended' -and -not $state.stopping -and -not $httpEnded -and $needsControl) {
                if (-not $statusChecked) {
                    $status = Invoke-StreamingClient -Command 'status' -Name "$($Case.name)_live_soft_status" -Port $Port -OutDir $OutDir
                    $clients.Add([pscustomobject]$status) | Out-Null
                    $snapshot = $status.stdout_text | ConvertFrom-Json -ErrorAction Stop
                    if (-not $status.success -or $snapshot.event -ne 'status' -or
                        $snapshot.run_id -ne $state.run_id -or $snapshot.stream.lifecycle -ne 'run_bound' -or
                        $snapshot.stream.state -notin @('active', 'ended') -or
                        -not $snapshot.ok -or $snapshot.fatal_error -or $snapshot.errors -gt 0 -or $snapshot.stopping) {
                        throw 'HTTP streaming status correlation failed.'
                    }
                    $httpEnded = $snapshot.stream.state -eq 'ended'
                    $statusChecked = $true
                    continue
                }
                if ($batch -eq 1000) { continue }
                if ($Case.external_edges -gt 0 -and -not $externalPrompted) {
                    Write-Host "Streaming Active confirmed: $($Case.name). Apply $($Case.external_edges) external trigger edge(s) now."
                    $externalPrompted = $true
                }
                if ($triggerCount -lt $Case.soft_trigger_count -and $now -ge $nextTriggerAt) {
                    $trigger = Invoke-StreamingClient -Command 'send-command' -Name "$($Case.name)_trigger_$($triggerCount + 1)" -Port $Port -OutDir $OutDir
                    $clients.Add([pscustomobject]$trigger) | Out-Null
                    $response = $trigger.stdout_text | ConvertFrom-Json -ErrorAction Stop
                    if (-not $trigger.success -or $response.event -ne 'send-command' -or $response.status -ne 'accepted') {
                        throw 'Software trigger was not accepted.'
                    }
                    $triggerCount++
                    $nextTriggerAt = $clock.ElapsedMilliseconds + 250
                }
            }
            Start-Sleep -Milliseconds 10
        }
    } catch {
        $failures.Add('Streaming control or output observation failed.') | Out-Null
    } finally {
        # Unexpected exceptions still use cooperative Stop before forced termination.
        if (-not $process.HasExited) {
            if (-not $stopSent) {
                $stopSent = $true
                try {
                    $clients.Add([pscustomobject](Invoke-StreamingClient -Command 'stop' -Name "$($Case.name)_cleanup_stop" -Port $Port -OutDir $OutDir)) | Out-Null
                } catch { $failures.Add('Cleanup Stop failed.') | Out-Null }
                finally { $stopAt = $clock.ElapsedMilliseconds }
            }
            $cleanupDeadline = $stopAt + $StopGracePeriodMs
            while (-not $process.HasExited -and $clock.ElapsedMilliseconds -lt $cleanupDeadline) {
                # Keep stdout flowing while Stop cleanup runs, including after client failures.
                if ($eof -or -not $lineTask.IsCompleted) { Start-Sleep -Milliseconds 10; continue }
                $line = $lineTask.GetAwaiter().GetResult()
                if ($null -eq $line) { $eof = $true; continue }
                $lines.Add($line) | Out-Null
                try { Add-StreamingObservation -State $state -Event ($line | ConvertFrom-Json -ErrorAction Stop) }
                catch { $failures.Add('Invalid or unsuccessful cleanup event.') | Out-Null }
                $lineTask = $process.StandardOutput.ReadLineAsync()
            }
            if (-not $process.HasExited) {
                $forced = $true
                try { $process.Kill() }
                catch { $failures.Add('Forced termination could not be confirmed.') | Out-Null }
                [void]$process.WaitForExit(2000)
            }
        }
        $tailDeadline = $clock.ElapsedMilliseconds + 2000
        while (-not $eof -and $clock.ElapsedMilliseconds -lt $tailDeadline) {
            if (-not $lineTask.IsCompleted) { Start-Sleep -Milliseconds 10; continue }
            $line = $lineTask.GetAwaiter().GetResult()
            if ($null -eq $line) { $eof = $true; break }
            $lines.Add($line) | Out-Null
            try { Add-StreamingObservation -State $state -Event ($line | ConvertFrom-Json -ErrorAction Stop) }
            catch { $failures.Add('Invalid or unsuccessful tail event.') | Out-Null }
            $lineTask = $process.StandardOutput.ReadLineAsync()
        }
        $stderrComplete = $stderrTask.Wait(2000)
        Write-Utf8NoBomLines -LiteralPath $StdOutPath -Lines @($lines.ToArray())
        Write-Utf8NoBomText -LiteralPath $StdErrPath -Text $(if ($stderrComplete) { $stderrTask.GetAwaiter().GetResult() } else { '' })
    }
    if (-not $state.ready -or -not $state.summary -or $state.phase -ne 'ended') { $failures.Add('Missing Ready, Ended or Summary.') | Out-Null }
    if (($Case.expected_captured -ne 0 -or $Case.min_captured -gt 0) -and -not $state.active) { $failures.Add('Active was not observed.') | Out-Null }
    if ($triggerCount -ne $Case.soft_trigger_count) { $failures.Add('Required software triggers were not sent.') | Out-Null }
    if ($Case.external_edges -gt 0 -and -not $externalPrompted) { $failures.Add('External trigger gate was not released.') | Out-Null }
    if ($Case.planned_stop_after_seconds -gt 0 -and -not $stopSent) { $failures.Add('Planned Stop was not sent.') | Out-Null }
    if (-not $eof -or -not $stderrComplete) { $failures.Add('Output drain incomplete.') | Out-Null }
    $exited = $process.HasExited
    $exitCode = if ($exited) { $process.ExitCode } else { $null }
    $process.Dispose()
    return [ordered]@{
        name = "$($Case.name)_live"; command = $Python; arguments = $Arguments
        exit_code = $exitCode; duration_seconds = [math]::Round($clock.Elapsed.TotalSeconds, 3)
        stdout = $StdOutPath; stderr = $StdErrPath; client_commands = @($clients.ToArray())
        success = $exited -and $exitCode -eq $Case.expected_exit_code -and $failures.Count -eq 0 -and -not $forced
        timed_out = $timedOut; forced_termination = $forced
        cleanup_unconfirmed = $forced -or -not $exited -or -not $eof -or -not $stderrComplete
        streaming_evidence = [ordered]@{
            run_id = $state.run_id; ready = $state.ready; active = $state.active
            transitions = @($state.transitions.ToArray()); sample_count = $state.samples
            ended = $state.phase -eq 'ended'; summary = $state.summary; stdout_eof = $eof
            http_status_checked = $statusChecked; software_triggers_sent = $triggerCount
            external_prompt_after_active = $externalPrompted; stop_requested = $stopSent
            failure_reasons = @($failures.ToArray())
        }
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
        if ($Case.streaming) {
            Write-Host "Do not apply triggers until the Streaming Active prompt appears."
        } else {
            Write-Host "After pressing Enter, the logger will arm the instrument. Apply the trigger edge after the run starts."
        }
        [void](Read-Host "Press Enter to start this external trigger case, or Ctrl+C to cancel")
    }

    $jsonl = Join-Path $CaseDir "live.jsonl"
    $stderr = Join-Path $CaseDir "live.stderr.txt"
    $args = New-StartArgs -Case $Case -CsvPath $CsvPath -Port $Port
    if ($Case.streaming) {
        $result = Invoke-StreamingStartProcess -Case $Case -Arguments $args `
            -StdOutPath $jsonl -StdErrPath $stderr -Port $Port -OutDir $CaseDir
    } else {
        $result = Invoke-CapturedStartProcess `
        -Name "$($Case.name)_live" `
        -Arguments $args `
        -StdOutPath $jsonl `
        -StdErrPath $stderr `
        -TimeoutSeconds $Case.timeout_seconds `
        -SoftTriggerCount $Case.soft_trigger_count `
        -SoftTriggerPort $Port `
        -OutDir $CaseDir `
        -SoftTriggerRetryCount 60 `
        -SoftTriggerRetryDelayMs 250 `
        -InterTriggerDelayMs 250 `
        -StopGracePeriodMs 10000 `
        -PlannedStopAfterSeconds $Case.planned_stop_after_seconds `
        -ExpectedExitCode $Case.expected_exit_code `
        -CaptureClientCommandsInMemory:(-not $DebugArtifacts)
    }

    $failureReasons = [System.Collections.Generic.List[string]]::new()
    $infinite = $Case.mode_args -contains "--trigger-count-infinite"
    $expectedReadings = $null
    if ($Case.expected_stop_reason -and -not $infinite) {
        $expectedReadings = [int]$Case.mode_args[[array]::IndexOf($Case.mode_args, "--trigger-count") + 1] *
            [int]$Case.mode_args[[array]::IndexOf($Case.mode_args, "--sample-count") + 1]
    }
    if (-not $result.success) {
        $failureReasons.Add("live command failed or timed out") | Out-Null
    }
    $captured = $null
    $errors = $null
    $events = @()
    if (Test-Path -LiteralPath $jsonl) {
        try { $events = @(Read-JsonLines -Path $jsonl) }
        catch {
            if (-not $Case.streaming) { throw }
            $failureReasons.Add("Streaming JSONL could not be parsed") | Out-Null
        }
    }
    $ready = @(Select-LastJsonEvent -Events $events -EventName "ready")
    $summary = @(Select-LastJsonEvent -Events $events -EventName "summary")
    $runId = $null
    if ($ready.Count -eq 1 -and $null -ne $ready[0].PSObject.Properties['run_id']) {
        $runId = $ready[0].run_id
    } elseif ($summary.Count -eq 1 -and $null -ne $summary[0].PSObject.Properties['run_id']) {
        $runId = $summary[0].run_id
    }
    if ($Case.soft_trigger_count -gt 0 -or $Case.planned_stop_after_seconds -gt 0 -or $Case.expected_exit_code -ne 0 -or ($Case.streaming -and $Case.external_edges -gt 0)) {
        if ($ready.Count -ne 1) {
            $failureReasons.Add("ready event missing") | Out-Null
        }
        $statusCommand = @($result.client_commands | Where-Object { $_.name -in @("$($Case.name)_live_soft_status", "$($Case.name)_live_planned_stop_status") } | Select-Object -Last 1)
        if ($statusCommand.Count -ne 1) {
            $failureReasons.Add("status client command missing") | Out-Null
        } elseif ($ready.Count -eq 1) {
            $statusText = if ($DebugArtifacts -and -not $Case.streaming) { Get-Content -LiteralPath $statusCommand[0].stdout -Raw } else { $statusCommand[0].stdout_text }
            try { $statusPayload = $statusText | ConvertFrom-Json -ErrorAction Stop }
            catch {
                if (-not $Case.streaming) { throw }
                $statusPayload = [pscustomobject]@{}
                $failureReasons.Add('Streaming HTTP status could not be parsed') | Out-Null
            }
            if ($null -eq $statusPayload -and $Case.streaming) { $statusPayload = [pscustomobject]@{} }
            if ($null -eq $statusPayload.PSObject.Properties['run_id'] -or $statusPayload.run_id -ne $runId) {
                $failureReasons.Add("status run_id mismatch") | Out-Null
            }
            $statusFieldsValid = $true
            foreach ($field in @("trigger_count_infinite", "expected_readings", "overflow_monitoring", "overflow_detected", "stop_reason", "final_drain_complete", "data_integrity")) {
                if ($null -eq $statusPayload.PSObject.Properties[$field]) {
                    $failureReasons.Add("status field missing: $field") | Out-Null
                    $statusFieldsValid = $false
                }
            }
            if ($statusFieldsValid -and $Case.expected_stop_reason -and
                ($statusPayload.trigger_count_infinite -ne $infinite -or $statusPayload.overflow_monitoring -ne "active")) {
                $failureReasons.Add("running Custom monitoring state mismatch") | Out-Null
            }
        }
    }
    if ($summary.Count -eq 1) {
        if ($null -eq $runId -or $null -eq $summary[0].PSObject.Properties['run_id'] -or $summary[0].run_id -ne $runId) {
            $failureReasons.Add("summary run_id mismatch") | Out-Null
        }
        $captured = [int]$summary[0].captured
        $errors = [int]$summary[0].errors
        if ($Case.expected_captured -ge 0 -and $captured -ne $Case.expected_captured) {
            $failureReasons.Add("captured count mismatch: expected=$($Case.expected_captured) actual=$captured") | Out-Null
        }
        if ($captured -lt $Case.min_captured) {
            $failureReasons.Add("captured count below minimum: expected=$($Case.min_captured) actual=$captured") | Out-Null
        }
        if ($errors -ne 0) {
            $failureReasons.Add("errors should be 0; actual=$errors") | Out-Null
        }
        if ($null -eq $summary[0].PSObject.Properties['ok'] -or [bool]$summary[0].ok -ne ($Case.expected_exit_code -eq 0)) {
            $failureReasons.Add("summary ok mismatch") | Out-Null
        }
        if ($Case.expected_stop_reason) {
            $summaryFieldsValid = $true
            foreach ($field in @("trigger_count_infinite", "expected_readings", "overflow_monitoring", "overflow_detected", "stop_reason", "final_drain_complete", "data_integrity")) {
                if ($null -eq $summary[0].PSObject.Properties[$field]) {
                    $failureReasons.Add("summary field missing: $field") | Out-Null
                    $summaryFieldsValid = $false
                }
            }
            if ($summaryFieldsValid) {
                if ($summary[0].stop_reason -ne $Case.expected_stop_reason) {
                    $failureReasons.Add("stop reason mismatch") | Out-Null
                }
                if ($summary[0].overflow_detected -ne $Case.expect_overflow) {
                    $failureReasons.Add("overflow state mismatch") | Out-Null
                }
                if ($summary[0].final_drain_complete -isnot [bool]) {
                    $failureReasons.Add("final drain result missing") | Out-Null
                } elseif (-not $Case.expect_overflow -and -not $summary[0].final_drain_complete) {
                    $failureReasons.Add("final drain incomplete") | Out-Null
                }
                if ($summary[0].trigger_count_infinite -ne $infinite -or
                    $summary[0].expected_readings -ne $expectedReadings -or
                    $summary[0].overflow_monitoring -ne "active") {
                    $failureReasons.Add("Custom monitoring state mismatch") | Out-Null
                }
                $expectedIntegrity = if ($Case.expect_overflow) { "incomplete" } elseif ($infinite) { "unknown" } else { "no_loss_detected" }
                if ($summary[0].data_integrity -ne $expectedIntegrity) {
                    $failureReasons.Add("data integrity mismatch") | Out-Null
                }
            }
            if ($null -ne $summary[0].PSObject.Properties['fatal_error'] -and $summary[0].fatal_error) {
                $failureReasons.Add("unexpected fatal error") | Out-Null
            }
        }
    } else {
        $failureReasons.Add("summary event missing") | Out-Null
    }
    $overflowObserved = $false
    $sampleAfterOverflow = $false
    $continuedDrain = $false
    if ($Case.require_continued_drain) {
        foreach ($event in $events) {
            if ($event.event -eq "status" -and
                $null -ne $event.PSObject.Properties['run_id'] -and $event.run_id -eq $runId -and
                $null -ne $event.PSObject.Properties['overflow_detected'] -and $event.overflow_detected -eq $true) {
                if ($sampleAfterOverflow -and $null -ne $event.PSObject.Properties['stop_reason'] -and $event.stop_reason -eq "unknown") {
                    $continuedDrain = $true
                }
                $overflowObserved = $true
            } elseif ($overflowObserved -and $event.event -eq "sample") {
                $sampleAfterOverflow = $true
            }
        }
        if (-not $continuedDrain) {
            $failureReasons.Add("continued drain after overflow not observed before Stop") | Out-Null
        }
    }
    # Keep only review evidence; status/sample events can contain measurement values.
    $runtimeErrors = @(
        foreach ($event in $events) {
            if ($event.event -eq "error") {
                [ordered]@{ message = $event.message; exit_code = $event.exit_code }
            }
        }
    )
    $diagnostics = @()
    $cleanupResults = @()
    foreach ($event in $events) {
        if ($event.event -eq "message" -and
            $event.message -match '^(release_to_local before close|release_to_local retry|release_to_local|cleanup_release_to_local): (.+)$') {
            $cleanupResults += [ordered]@{ step = $Matches[1]; result = $Matches[2] }
        } elseif ($event.event -eq "status" -and
            $event.message -match '^(?:(?:buffered )?capture error count=|hardware status poll timeout warning |hardware status polling degraded )') {
            $diagnostics += [ordered]@{ message = $event.message }
        }
    }
    $runtimeEvidence = [ordered]@{
        source = "cli_jsonl"
        continued_drain_after_overflow = if ($Case.require_continued_drain) { $continuedDrain } else { $null }
        summary = if ($summary.Count -eq 1) {
            [ordered]@{
                ok = $summary[0].ok
                fatal_error = if ($null -ne $summary[0].PSObject.Properties['fatal_error']) { $summary[0].fatal_error } else { $null }
                trigger_count_infinite = if ($null -ne $summary[0].PSObject.Properties['trigger_count_infinite']) { $summary[0].trigger_count_infinite } else { $null }
                expected_readings = if ($null -ne $summary[0].PSObject.Properties['expected_readings']) { $summary[0].expected_readings } else { $null }
                overflow_monitoring = if ($null -ne $summary[0].PSObject.Properties['overflow_monitoring']) { $summary[0].overflow_monitoring } else { $null }
                overflow_detected = if ($null -ne $summary[0].PSObject.Properties['overflow_detected']) { $summary[0].overflow_detected } else { $null }
                stop_reason = if ($null -ne $summary[0].PSObject.Properties['stop_reason']) { $summary[0].stop_reason } else { $null }
                final_drain_complete = if ($null -ne $summary[0].PSObject.Properties['final_drain_complete']) { $summary[0].final_drain_complete } else { $null }
                data_integrity = if ($null -ne $summary[0].PSObject.Properties['data_integrity']) { $summary[0].data_integrity } else { $null }
            }
        } else { $null }
        error_events = $runtimeErrors
        diagnostics = $diagnostics
        cleanup = [ordered]@{
            status = if ($cleanupResults.Count -gt 0) { "observed" } else { "not_observed" }
            results = $cleanupResults
            # Runtime messages report release results, but do not confirm close success.
            close_status = "not_reported"
        }
        identity = [ordered]@{
            status = "not_available"
            reason = "Runtime JSONL does not expose detected manufacturer, model or firmware."
        }
    }
    if ($Case.streaming) {
        $runtimeEvidence.streaming = $result.streaming_evidence
        $runtimeEvidence.cleanup.process_exit_observed = ($null -ne $result.exit_code)
        $runtimeEvidence.cleanup.forced_termination = $result.forced_termination
        if ($cleanupResults.Count -eq 0 -or @($cleanupResults | Where-Object { $_.result -match 'failed|error' }).Count -gt 0) {
            $result.cleanup_unconfirmed = $true
        }
        $runtimeEvidence.cleanup.unconfirmed = $result.cleanup_unconfirmed
        foreach ($reason in $result.streaming_evidence.failure_reasons) { $failureReasons.Add($reason) | Out-Null }
        if ($result.cleanup_unconfirmed) { $failureReasons.Add('Cleanup unconfirmed; operator must check the instrument before continuing.') | Out-Null }
    }
    $rowCount = Test-CsvRowCount -Path $CsvPath
    if ($null -ne $captured -and $rowCount -ne $captured) {
        $failureReasons.Add("CSV row count mismatch: summary=$captured actual=$rowCount") | Out-Null
    }
    $measurementType = $null
    $unit = $null
    $value = $null
    if ($rowCount -gt 0) {
        $csvRows = @(Import-Csv -LiteralPath $CsvPath)
        $firstRow = $csvRows[0]
        $samples = @($events | Where-Object { $_.event -eq "sample" })
        if ($samples.Count -ne $rowCount) {
            $failureReasons.Add("JSONL sample and CSV correlation mismatch") | Out-Null
        } else {
            for ($index = 0; $index -lt $rowCount; $index++) {
                if ($null -eq $samples[$index].PSObject.Properties['run_id'] -or
                    $null -eq $samples[$index].PSObject.Properties['trigger_id'] -or
                    $null -eq $csvRows[$index].PSObject.Properties['trigger_id']) {
                    $failureReasons.Add("JSONL sample and CSV correlation fields missing at row $index") | Out-Null
                    break
                }
                if ($samples[$index].run_id -ne $runId -or $samples[$index].trigger_id -ne $csvRows[$index].trigger_id) {
                    $failureReasons.Add("JSONL sample and CSV correlation mismatch at row $index") | Out-Null
                    break
                }
            }
        }
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
        expected_exit_code = $Case.expected_exit_code
        expected_stop_reason = $Case.expected_stop_reason
        planned_stop_after_seconds = $Case.planned_stop_after_seconds
        expect_overflow = $Case.expect_overflow
        require_continued_drain = $Case.require_continued_drain
        captured_count = $captured
        captured = $captured
        errors = $errors
        ready_events = $ready.Count
        runtime_evidence = $runtimeEvidence
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
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$CommandItems,
        [string]$FailureReason
    )

    $report = [ordered]@{
        schema_version = "1.1"
        kind = "meters_tool_live_validation"
        artifact_visibility = "private"
        candidate_evidence_only = $true
        promotes_live_support = $false
        private_raw_artifacts_retained = $true
        redaction_applied = $false
        redaction_version = 1
        target = $resolvedTarget
        model_id = $resolvedTarget
        expected_model = $resolvedCliModel
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
        output_dir = $privateRoot
        artifact_paths = [ordered]@{
            output_dir = $privateRoot
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
    if ($Suite -eq 'worker-streaming') {
        $report.not_run_cases = @($cases | Where-Object { $_.name -notin @($CaseItems | ForEach-Object { $_.name }) } | ForEach-Object { $_.name })
        $report.unverified_observations = @(
            [ordered]@{ name = 'raw_operation_condition'; status = 'not_verified'; evidence_needed = 'Non-interfering instrument I/O trace with raw replies.' },
            [ordered]@{ name = 'query_trigger_overlap_and_latency'; status = 'not_verified'; evidence_needed = 'Correlated trigger and instrument I/O timestamps.' },
            [ordered]@{ name = 'observation_query_timeout'; status = 'not_verified'; evidence_needed = 'Separately authorized, bounded hardware fault validation.' },
            [ordered]@{ name = 'stop_before_active_race'; status = 'not_run'; evidence_needed = 'Separately controlled live race evidence; excluded from the routine suite.' }
        )
    }
    if (-not [string]::IsNullOrWhiteSpace($FailureReason)) { $report.failure_reason = $FailureReason }
    if ($DebugArtifacts) { Write-JsonReport -LiteralPath $reportPath -Report $report -Depth 12 }

    $summaryLines = @(
        "# Live CLI Check Summary",
        "",
        "- Target: $resolvedTarget",
        "- Model ID: $resolvedTarget",
        "- Expected model: $resolvedCliModel",
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
        "- Output directory: $privateRoot",
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
    if ($DebugArtifacts) { Write-Utf8NoBomLines -LiteralPath $summaryPath -Lines $summaryLines }

    try {
        [void](New-ShareableArtifactSet `
            -PrivateReport $report `
            -RunRoot $runDir `
            -PrivateRoot $privateRoot `
            -ShareableRoot $shareableRoot `
            -RepoRoot $RepoRoot `
            -Resource $Resource `
            -Connection $resolvedConnection `
            -MinimalArtifacts:(-not $DebugArtifacts))
        foreach ($name in @("report.json", "summary.md")) {
            $file = Join-Path $shareableRoot $name
            if (-not (Test-Path -LiteralPath $file -PathType Leaf) -or
                [string]::IsNullOrWhiteSpace([System.IO.File]::ReadAllText($file))) {
                throw "Missing or empty shareable artifact: $name"
            }
        }
        $null = Get-Content -LiteralPath (Join-Path $shareableRoot "report.json") -Raw | ConvertFrom-Json -ErrorAction Stop
        if (-not $DebugArtifacts) {
            Remove-ValidationRunArtifacts -RunDirectory $runDir -RepoRoot $RepoRoot
        }
        $script:artifactsFinalized = $true
        return $true
    } catch {
        $script:artifactGenerationFailed = $true
        $location = ($_.ScriptStackTrace -split "`r?`n" | Select-Object -First 2) -join " | "
        $failureDetail = Protect-ArtifactText -Text "$($_.Exception.Message) [$location]" -Resource $Resource `
            -RepoRoot $RepoRoot -PrivateRoot $privateRoot
        Write-Host "Shareable artifact generation failed: $failureDetail"
        Remove-ValidationRunArtifacts -RunDirectory $runDir -RepoRoot $RepoRoot `
            -ShareableFailed -FailureDetail $failureDetail -Resource $Resource
        return $false
    }
}

if ([string]::IsNullOrWhiteSpace($Resource)) {
    Fail-Usage "Missing -Resource. Live checks never scan or guess a VISA resource."
}
if ($SkipPreflight -and (-not $PlanOnly)) {
    Fail-Usage "-SkipPreflight is allowed only with -PlanOnly."
}

try {
    $resolvedTarget = Resolve-ValidationTarget -Target $Target
} catch {
    Fail-Usage $_.Exception.Message
}
$resolvedCliModel = Get-TargetCliModel -ResolvedTarget $resolvedTarget
$resolvedConnection = Resolve-Connection -Value $Connection
$resolvedVisaLibrary = if ([string]::IsNullOrWhiteSpace($VisaLibrary)) { $null } else { $VisaLibrary.Trim() }
$cases = @(Get-LiveCases -SelectedSuite $Suite -ResolvedTarget $resolvedTarget)

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = Join-Path (Join-Path (Join-Path (Join-Path $LiveRoot $resolvedTarget) $resolvedConnection) $Suite) $timestamp
Assert-UnderTmpRoot -Path $runDir
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
$privateRoot = Join-Path $runDir "private"
$shareableRoot = Join-Path $runDir "shareable"
New-Item -ItemType Directory -Force -Path $privateRoot | Out-Null
New-Item -ItemType Directory -Force -Path $shareableRoot | Out-Null

$commands = [System.Collections.Generic.List[object]]::new()
$caseResults = [System.Collections.Generic.List[object]]::new()
$dryRunResults = [System.Collections.Generic.List[object]]::new()
$scpiDiagnostics = [System.Collections.Generic.List[object]]::new()
$reportPath = Join-Path $privateRoot "report.json"
$summaryPath = Join-Path $privateRoot "summary.md"
$canonicalSummaryPath = ((Get-PortableRelativePath -BasePath $RepoRoot -Path (Join-Path $shareableRoot "summary.md")).Replace('\', '/'))
$canonicalErrorPath = ((Get-PortableRelativePath -BasePath $RepoRoot -Path (Join-Path $privateRoot "error-summary.md")).Replace('\', '/'))
$stdinRedirected = [Console]::IsInputRedirected
$script:handlingArtifactFailure = $false
$artifactsFinalized = $false
$artifactGenerationFailed = $false
$liveExecuted = $false

trap {
    $safeFailure = Protect-ArtifactText `
        -Text $_.Exception.Message `
        -Resource $Resource `
        -RepoRoot $RepoRoot `
        -PrivateRoot $privateRoot `
        -SensitiveValues @(Get-DistinctiveSensitiveTokens -Resource $Resource)
    if (-not $script:handlingArtifactFailure -and -not $script:artifactsFinalized -and -not $script:artifactGenerationFailed) {
        $script:handlingArtifactFailure = $true
        $written = $false
        try {
            $written = Write-LiveArtifacts `
                -Status "wrapper_failed" `
                -FailureReason $safeFailure `
                -PlanOnlyRun ([bool]$PlanOnly) `
                -LiveExecuted ([bool]$liveExecuted) `
                -CaseItems @($caseResults.ToArray()) `
                -DryRunItems @($dryRunResults.ToArray()) `
                -ScpiDiagnosticItems @($scpiDiagnostics.ToArray()) `
                -CommandItems @($commands.ToArray())
        } catch {
            $script:artifactGenerationFailed = $true
            $artifactFailure = Protect-ArtifactText -Text $_.Exception.Message -Resource $Resource `
                -RepoRoot $RepoRoot -PrivateRoot $privateRoot `
                -SensitiveValues @(Get-DistinctiveSensitiveTokens -Resource $Resource)
            try {
                Remove-ValidationRunArtifacts -RunDirectory $runDir -RepoRoot $RepoRoot `
                    -ShareableFailed -FailureDetail $artifactFailure -Resource $Resource
            } catch {
                [Console]::Error.WriteLine("Artifact failure cleanup could not be completed.")
            }
        }
        if ($written) { Write-Host "summary: $canonicalSummaryPath" } else { Write-Host "artifact error: $canonicalErrorPath" }
    }
    [Console]::Error.WriteLine($safeFailure)
    exit 1
}

if ((-not $SkipPreflight) -and (-not ($stdinRedirected -and (-not $PlanOnly)))) {
    $preflightOut = Join-Path $privateRoot "preflight.stdout.txt"
    $preflightErr = Join-Path $privateRoot "preflight.stderr.txt"
    $preflightRoot = Join-Path $privateRoot "preflight"
    $preflightArgs = @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $PreflightScript,
        "-Target", $resolvedTarget, "-OutputRoot", $preflightRoot
    )
    if ($DebugArtifacts) { $preflightArgs += "-DebugArtifacts" }
    $preflightResult = Invoke-CapturedCommand `
        -Name "preflight" `
        -FilePath "powershell.exe" `
        -Arguments $preflightArgs `
        -StdOutPath $preflightOut `
        -StdErrPath $preflightErr `
        -CaptureInMemory:(-not $DebugArtifacts)
    $commands.Add([pscustomobject]$preflightResult) | Out-Null

    if (-not $preflightResult.success) {
        $artifactsWritten = Write-LiveArtifacts `
            -Status "preflight_failed" `
            -PlanOnlyRun ([bool]$PlanOnly) `
            -LiveExecuted $false `
            -CaseItems @() `
            -DryRunItems @() `
            -ScpiDiagnosticItems @() `
            -CommandItems @($commands.ToArray())
        if (-not $artifactsWritten) { Write-Host "artifact error: $canonicalErrorPath"; throw "Shareable artifact generation failed." }
        Write-Host "summary: $canonicalSummaryPath"
        throw "Preflight failed. Review the shareable summary."
    }
}

Write-Host ""
Write-Host "Live CLI check"
Write-Host "Target: $resolvedTarget"
Write-Host "Connection: $resolvedConnection"
Write-Host "VISA library/backend: $(if ([string]::IsNullOrWhiteSpace($resolvedVisaLibrary)) { 'system_visa' } else { $resolvedVisaLibrary })"
Write-Host "Suite: $Suite"
Write-Host "Resource: $(Get-RedactedResourceDisplay -Resource $Resource -Connection $resolvedConnection)"
Write-Host "Output directory: $((Get-PortableRelativePath -BasePath $RepoRoot -Path $runDir).Replace('\', '/'))"
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
    $caseDir = Join-Path $privateRoot $caseName
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
    $artifactsWritten = Write-LiveArtifacts `
        -Status "planned" `
        -PlanOnlyRun $true `
        -LiveExecuted $false `
        -CaseItems @() `
        -DryRunItems @($dryRunResults.ToArray()) `
        -ScpiDiagnosticItems @() `
        -CommandItems @($commands.ToArray())
    Write-Host "live CLI plan generated: $Suite"
    if (-not $artifactsWritten) { Write-Host "artifact error: $canonicalErrorPath"; throw "Shareable artifact generation failed." }
    Write-Host "summary: $canonicalSummaryPath"
    exit 0
}

if ($stdinRedirected) {
    $artifactsWritten = Write-LiveArtifacts `
        -Status "confirmation_required" `
        -PlanOnlyRun $false `
        -LiveExecuted $false `
        -CaseItems @() `
        -DryRunItems @($dryRunResults.ToArray()) `
        -ScpiDiagnosticItems @() `
        -CommandItems @($commands.ToArray())
    if (-not $artifactsWritten) { Write-Host "artifact error: $canonicalErrorPath"; throw "Shareable artifact generation failed." }
    Write-Host "summary: $canonicalSummaryPath"
    throw "Live suite requires interactive Enter confirmation; stdin is redirected."
}

Write-Host ""
Write-Host "WARNING: Single-client instrument access required."
Write-Host "Ensure no other Meters WebUI, CLI, logger, test process, or external VISA application"
Write-Host "is using the same physical instrument during this live test."
Write-Host "Concurrent control may interfere with SCPI command/response ordering or instrument state."
if ($Suite -eq "overflow") {
    Write-Host "WARNING: This suite intentionally causes Reading Memory Overflow and incomplete data."
}
[void](Read-Host "Press Enter to run suite '$Suite', or Ctrl+C to cancel")

$liveExecuted = $true
$suiteStatus = "passed"
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
            $safeFailureReasons = ConvertTo-SafeConsoleFailureReasons `
                -FailureReasons @($probeFailure.failure_reasons) `
                -Resource $Resource `
                -RepoRoot $RepoRoot `
                -PrivateRoot $privateRoot
            Write-Host "SCPI probe failed: $($case.name)"
            Write-Host "failure reasons: $($safeFailureReasons -join '; ')"
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
        $safeFailureReasons = ConvertTo-SafeConsoleFailureReasons `
            -FailureReasons @($liveResult.failure_reasons) `
            -Resource $Resource `
            -RepoRoot $RepoRoot `
            -PrivateRoot $privateRoot
        Write-Host "live case failed: $($case.name)"
        Write-Host "failure reasons: $($safeFailureReasons -join '; ')"
        break
    }
}

$artifactsWritten = Write-LiveArtifacts `
    -Status $suiteStatus `
    -PlanOnlyRun $false `
    -LiveExecuted $liveExecuted `
    -CaseItems @($caseResults.ToArray()) `
    -DryRunItems @($dryRunResults.ToArray()) `
    -ScpiDiagnosticItems @($scpiDiagnostics.ToArray()) `
    -CommandItems @($commands.ToArray())

if (-not $artifactsWritten) {
    Write-Host "artifact error: $canonicalErrorPath"
    throw "Shareable artifact generation failed. Only a redacted private/error-summary.md was retained."
}

if ($suiteStatus -ne "passed") {
    Write-Host "summary: $canonicalSummaryPath"
    throw "Live CLI suite failed: $Suite. Review the shareable summary."
}

Write-Host "live CLI suite passed: $Suite"
Write-Host "summary: $canonicalSummaryPath"
