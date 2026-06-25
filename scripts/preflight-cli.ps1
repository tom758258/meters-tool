param(
    [ValidateSet("all", "keysight-34461a")]
    [string]$Target = "all",
    [switch]$ListTargets,
    [string]$OutputRoot = ".tmp_tests\cli_preflight"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$TmpRoot = Join-Path $RepoRoot ".tmp_tests"
. (Join-Path $PSScriptRoot "_validation_helpers.ps1")

if ($ListTargets) {
    Write-Output "keysight-34461a"
    return
}

function Assert-UnderTmpRoot {
    param([Parameter(Mandatory = $true)][string]$Path)
    Assert-PathUnderRoot `
        -RootPath $TmpRoot `
        -Path $Path `
        -Message "Only paths under .tmp_tests are allowed for -OutputRoot and preflight output: {0}"
}

function Resolve-OutputRoot {
    param([Parameter(Mandatory = $true)][string]$Path)
    if ([System.IO.Path]::IsPathRooted($Path)) {
        $resolved = Get-FullPath $Path
    } else {
        $resolved = Get-FullPath (Join-Path $RepoRoot $Path)
    }
    Assert-UnderTmpRoot -Path $resolved
    return $resolved
}

$PreflightRoot = Resolve-OutputRoot -Path $OutputRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python executable not found: $Python"
}

Add-RepoSrcToPythonPath -RepoRoot $RepoRoot

function Clear-OutputDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)
    New-Item -ItemType Directory -Force -Path $TmpRoot | Out-Null
    Assert-UnderTmpRoot -Path $Path
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
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
            Start-Sleep -Milliseconds 150
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
                -Arguments @("-m", "keysight_logger_cli", "stop", "--format", "json", "--port", [string]$SoftTriggerPort) `
                -StdOutPath $stopOut `
                -StdErrPath $stopErr
            $clientResults.Add([pscustomobject]$stopResult) | Out-Null
            $exited = $process.WaitForExit(5000)
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
    for ($attempt = 1; $attempt -le 40; $attempt++) {
        $stdoutPath = Join-Path $OutDir "$Name`_attempt_$attempt.json"
        $stderrPath = Join-Path $OutDir "$Name`_attempt_$attempt.stderr.txt"
        $lastResult = Invoke-CapturedCommand `
            -Name "$Name`_attempt_$attempt" `
            -FilePath $Python `
            -Arguments @(
                "-m", "keysight_logger_cli",
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
                # Retry until the trigger server is ready and emits valid JSON.
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
        -Arguments @("-m", "keysight_logger_cli", "wait-ready", "--format", "json", "--port", [string]$Port) `
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
        -Arguments @("-m", "keysight_logger_cli", "status", "--format", "json", "--port", [string]$Port) `
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

function New-StartBaseArgs {
    param(
        [Parameter(Mandatory = $true)][string]$Resource,
        [Parameter(Mandatory = $true)][string]$CsvPath,
        [Parameter(Mandatory = $true)][string]$Port
    )
    return @(
        "-m", "keysight_logger_cli",
        "start-trigger-record",
        "--resource", $Resource,
        "--csv", $CsvPath,
        "--sw-trigger-port", $Port,
        "--auto-range", "on",
        "--auto-zero", "off",
        "--nplc", "1.0",
        "--status-format", "jsonl"
    )
}

function Invoke-DryRunCase {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string[]]$ModeArgs,
        [Parameter(Mandatory = $true)][string]$ExpectedMeasurement,
        [Parameter(Mandatory = $true)][string]$ExpectedReadPath,
        [string]$ExpectedUnit,
        [string[]]$ExpectedScpiCommands = @(),
        [Parameter(Mandatory = $true)][string]$OutDir,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][System.Collections.Generic.List[object]]$Commands,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][System.Collections.Generic.List[object]]$Checks
    )

    $safeName = New-SafeCaseName -Name $Name
    $jsonl = Join-Path $OutDir "$safeName.jsonl"
    $stderr = Join-Path $OutDir "$safeName.stderr.txt"
    $csv = Join-Path $OutDir "$safeName.csv"
    $port = [string](Get-AvailableTcpPort)
    $args = @((New-StartBaseArgs -Resource "SIM::34461A" -CsvPath $csv -Port $port) + $ModeArgs + @("--dry-run"))

    $result = Invoke-CapturedCommand `
        -Name $Name `
        -FilePath $Python `
        -Arguments $args `
        -StdOutPath $jsonl `
        -StdErrPath $stderr
    $Commands.Add([pscustomobject]$result) | Out-Null
    Assert-Condition ($result.success) "$Name failed"
    $events = @(Read-JsonLines -Path $jsonl)
    Assert-Condition ($events.Count -eq 1) "$Name should emit one JSONL event"
    Assert-Condition ($events[0].event -eq "dry_run") "$Name event type mismatch"
    Assert-Condition ($events[0].measurement_cli_name -eq $ExpectedMeasurement) "$Name measurement mismatch"
    Assert-Condition ($events[0].read_path -eq $ExpectedReadPath) "$Name read path mismatch"
    if (-not [string]::IsNullOrWhiteSpace($ExpectedUnit)) {
        Assert-Condition ($events[0].measurement_unit -eq $ExpectedUnit) "$Name measurement unit mismatch"
    }
    if ($ExpectedScpiCommands.Count -gt 0) {
        $actualScpi = @($events[0].scpi_commands)
        Assert-Condition `
            (($actualScpi -join "`n") -eq ($ExpectedScpiCommands -join "`n")) `
            "$Name SCPI sequence mismatch"
    }
    $Checks.Add([pscustomobject]@{
        name = $Name
        success = $true
        jsonl = $jsonl
        csv = $csv
        stderr = $stderr
        read_path = $ExpectedReadPath
        measurement_unit = $events[0].measurement_unit
        scpi_commands = @($events[0].scpi_commands)
    }) | Out-Null
}

function Invoke-SimulateCase {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string[]]$ModeArgs,
        [Parameter(Mandatory = $true)][int]$ExpectedCaptured,
        [string]$ExpectedMeasurementType,
        [string]$ExpectedUnit,
        [int]$SoftTriggerCount = 0,
        [Parameter(Mandatory = $true)][string]$OutDir,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][System.Collections.Generic.List[object]]$Commands,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][System.Collections.Generic.List[object]]$Checks
    )

    $safeName = New-SafeCaseName -Name $Name
    $jsonl = Join-Path $OutDir "$safeName.jsonl"
    $stderr = Join-Path $OutDir "$safeName.stderr.txt"
    $csv = Join-Path $OutDir "$safeName.csv"
    $port = Get-AvailableTcpPort
    $args = @(
        (New-StartBaseArgs -Resource "SIM::34461A" -CsvPath $csv -Port ([string]$port)) +
        $ModeArgs +
        @("--simulate")
    )

    $result = Invoke-CapturedStartProcess `
        -Name $Name `
        -Arguments $args `
        -StdOutPath $jsonl `
        -StdErrPath $stderr `
        -TimeoutSeconds 45 `
        -SoftTriggerCount $SoftTriggerCount `
        -SoftTriggerPort $port `
        -OutDir $OutDir
    $Commands.Add([pscustomobject]$result) | Out-Null
    Assert-Condition ($result.success) "$Name failed"
    $events = @(Read-JsonLines -Path $jsonl)
    $ready = @(Select-LastJsonEvent -Events $events -EventName "ready")
    $summary = @(Select-LastJsonEvent -Events $events -EventName "summary")
    if ($SoftTriggerCount -gt 0) {
        Assert-Condition ($ready.Count -eq 1) "$Name ready event missing"
        $statusCommand = @($result.client_commands | Where-Object { $_.name -eq "$Name`_soft_status" } | Select-Object -Last 1)
        Assert-Condition ($statusCommand.Count -eq 1) "$Name status client command missing"
        $statusPayload = Get-Content -LiteralPath $statusCommand[0].stdout -Raw | ConvertFrom-Json -ErrorAction Stop
        Assert-Condition ($statusPayload.run_id -eq $ready[0].run_id) "$Name status run_id mismatch"
    }
    Assert-Condition ($summary.Count -eq 1) "$Name summary event missing"
    Assert-Condition ([int]$summary[0].captured -eq $ExpectedCaptured) "$Name captured count mismatch"
    Assert-Condition ([int]$summary[0].errors -eq 0) "$Name errors should be 0"
    $rowCount = Test-CsvRowCount -Path $csv
    Assert-Condition ($rowCount -ge $ExpectedCaptured) "$Name CSV row count mismatch"
    $rows = @(Import-Csv -LiteralPath $csv)
    if (-not [string]::IsNullOrWhiteSpace($ExpectedMeasurementType)) {
        Assert-Condition ($rows[0].measurement_type -eq $ExpectedMeasurementType) "$Name CSV measurement type mismatch"
    }
    if (-not [string]::IsNullOrWhiteSpace($ExpectedUnit)) {
        Assert-Condition ($rows[0].unit -eq $ExpectedUnit) "$Name CSV unit mismatch"
    }
    $Checks.Add([pscustomobject]@{
        name = $Name
        success = $true
        captured = [int]$summary[0].captured
        errors = [int]$summary[0].errors
        ready_events = $ready.Count
        jsonl = $jsonl
        csv = $csv
        stderr = $stderr
    }) | Out-Null
}

function Invoke-TargetPreflight {
    param([Parameter(Mandatory = $true)][string]$ResolvedTarget)

    $outDir = Join-Path $PreflightRoot $ResolvedTarget
    Clear-OutputDirectory -Path $outDir

    $checks = [System.Collections.Generic.List[object]]::new()
    $commands = [System.Collections.Generic.List[object]]::new()

    $measurementCases = @(
        [pscustomobject]@{ name = "current-dc"; mode_args = @(); unit = $null; scpi_commands = @() },
        [pscustomobject]@{ name = "voltage-dc"; mode_args = @(); unit = $null; scpi_commands = @() },
        [pscustomobject]@{ name = "current-ac"; mode_args = @(); unit = $null; scpi_commands = @() },
        [pscustomobject]@{ name = "voltage-ac"; mode_args = @(); unit = $null; scpi_commands = @() },
        [pscustomobject]@{
            name = "frequency"
            mode_args = @("--ac-bandwidth-hz", "20", "--gate-time-s", "0.1", "--freq-period-timeout", "auto")
            unit = "Hz"
            scpi_commands = @(
                "CONF:FREQ",
                "FREQ:VOLT:RANG:AUTO ON",
                "FREQ:RANG:LOW 20",
                "FREQ:APER 0.1",
                "FREQ:TIM:AUTO ON"
            )
        },
        [pscustomobject]@{
            name = "period"
            mode_args = @("--ac-bandwidth-hz", "20", "--gate-time-s", "0.1")
            unit = "s"
            scpi_commands = @(
                "CONF:PER",
                "PER:VOLT:RANG:AUTO ON",
                "PER:RANG:LOW 20",
                "PER:APER 0.1"
            )
        },
        [pscustomobject]@{ name = "resistance-2w"; mode_args = @(); unit = $null; scpi_commands = @() },
        [pscustomobject]@{ name = "resistance-4w"; mode_args = @(); unit = $null; scpi_commands = @() }
    )
    $measurements = @($measurementCases | ForEach-Object { $_.name })

    foreach ($measurementCase in $measurementCases) {
        Invoke-DryRunCase `
            -Name "dry_run_immediate_$($measurementCase.name)" `
            -ModeArgs @(
                @("--trigger-mode", "immediate", "--measurement", $measurementCase.name, "--max-samples", "1") +
                $measurementCase.mode_args
            ) `
            -ExpectedMeasurement $measurementCase.name `
            -ExpectedReadPath "READ?" `
            -ExpectedUnit $measurementCase.unit `
            -ExpectedScpiCommands $measurementCase.scpi_commands `
            -OutDir $outDir `
            -Commands $commands `
            -Checks $checks
    }

    Invoke-DryRunCase `
        -Name "dry_run_external_read_path" `
        -ModeArgs @("--trigger-mode", "external", "--measurement", "current-dc", "--max-samples", "1") `
        -ExpectedMeasurement "current-dc" `
        -ExpectedReadPath "FETC?" `
        -OutDir $outDir `
        -Commands $commands `
        -Checks $checks

    Invoke-DryRunCase `
        -Name "dry_run_buffered_read_path" `
        -ModeArgs @("--trigger-mode", "software-custom", "--measurement", "current-dc", "--trigger-count", "1", "--sample-count", "2") `
        -ExpectedMeasurement "current-dc" `
        -ExpectedReadPath "DATA:POINts? / DATA:REMove?" `
        -OutDir $outDir `
        -Commands $commands `
        -Checks $checks

    foreach ($measurementCase in $measurementCases) {
        Invoke-SimulateCase `
            -Name "simulate_immediate_$($measurementCase.name)" `
            -ModeArgs @(
                @("--trigger-mode", "immediate", "--measurement", $measurementCase.name, "--max-samples", "1") +
                $measurementCase.mode_args
            ) `
            -ExpectedCaptured 1 `
            -ExpectedMeasurementType $measurementCase.name.Replace("-", "_") `
            -ExpectedUnit $measurementCase.unit `
            -OutDir $outDir `
            -Commands $commands `
            -Checks $checks
    }

    Invoke-SimulateCase `
        -Name "simulate_software_trigger" `
        -ModeArgs @("--trigger-mode", "software", "--measurement", "current-dc", "--max-samples", "2") `
        -ExpectedCaptured 2 `
        -SoftTriggerCount 2 `
        -OutDir $outDir `
        -Commands $commands `
        -Checks $checks

    Invoke-SimulateCase `
        -Name "simulate_software_timer" `
        -ModeArgs @("--trigger-mode", "software", "--timer-interval-s", "0.5", "--measurement", "current-dc", "--max-samples", "1") `
        -ExpectedCaptured 1 `
        -OutDir $outDir `
        -Commands $commands `
        -Checks $checks

    Invoke-SimulateCase `
        -Name "simulate_immediate_custom" `
        -ModeArgs @("--trigger-mode", "immediate-custom", "--measurement", "current-dc", "--trigger-count", "1", "--sample-count", "2") `
        -ExpectedCaptured 2 `
        -OutDir $outDir `
        -Commands $commands `
        -Checks $checks

    Invoke-SimulateCase `
        -Name "simulate_software_custom" `
        -ModeArgs @("--trigger-mode", "software-custom", "--measurement", "current-dc", "--trigger-count", "2", "--sample-count", "1") `
        -ExpectedCaptured 2 `
        -SoftTriggerCount 2 `
        -OutDir $outDir `
        -Commands $commands `
        -Checks $checks

    Invoke-SimulateCase `
        -Name "simulate_external" `
        -ModeArgs @("--trigger-mode", "external", "--measurement", "current-dc", "--max-samples", "1") `
        -ExpectedCaptured 1 `
        -OutDir $outDir `
        -Commands $commands `
        -Checks $checks

    Invoke-SimulateCase `
        -Name "simulate_external_custom" `
        -ModeArgs @("--trigger-mode", "external-custom", "--measurement", "current-dc", "--trigger-count", "1", "--sample-count", "2") `
        -ExpectedCaptured 2 `
        -OutDir $outDir `
        -Commands $commands `
        -Checks $checks

    $softTriggerJson = Join-Path $outDir "soft_trigger_dry_run.json"
    $softTriggerResult = Invoke-CapturedCommand `
        -Name "soft_trigger_dry_run" `
        -FilePath $Python `
        -Arguments @("-m", "keysight_logger_cli", "send-command", "--dry-run", "--format", "json", "--port", "8765", "--arguments-json", '{"source":"preflight"}') `
        -StdOutPath $softTriggerJson `
        -StdErrPath (Join-Path $outDir "soft_trigger_dry_run.stderr.txt")
    $commands.Add([pscustomobject]$softTriggerResult) | Out-Null
    Assert-Condition ($softTriggerResult.success) "send-command dry-run command failed"
    $softTrigger = Get-Content -LiteralPath $softTriggerJson -Raw | ConvertFrom-Json -ErrorAction Stop
    Assert-Condition ($softTrigger.event -eq "dry_run") "send-command dry-run event mismatch"
    Assert-Condition ($softTrigger.send_request -eq $false) "send-command dry-run should not send HTTP"
    $checks.Add([pscustomobject]@{ name = "soft_trigger_dry_run_json"; success = $true; path = $softTriggerJson }) | Out-Null

    $softStopJson = Join-Path $outDir "soft_stop_dry_run.json"
    $softStopResult = Invoke-CapturedCommand `
        -Name "soft_stop_dry_run" `
        -FilePath $Python `
        -Arguments @("-m", "keysight_logger_cli", "stop", "--dry-run", "--format", "json", "--port", "8765") `
        -StdOutPath $softStopJson `
        -StdErrPath (Join-Path $outDir "soft_stop_dry_run.stderr.txt")
    $commands.Add([pscustomobject]$softStopResult) | Out-Null
    Assert-Condition ($softStopResult.success) "stop dry-run command failed"
    $softStop = Get-Content -LiteralPath $softStopJson -Raw | ConvertFrom-Json -ErrorAction Stop
    Assert-Condition ($softStop.event -eq "dry_run") "stop dry-run event mismatch"
    Assert-Condition ($softStop.send_request -eq $false) "stop dry-run should not send HTTP"
    $checks.Add([pscustomobject]@{ name = "soft_stop_dry_run_json"; success = $true; path = $softStopJson }) | Out-Null

    $softStatusJson = Join-Path $outDir "soft_status_dry_run.json"
    $softStatusResult = Invoke-CapturedCommand `
        -Name "soft_status_dry_run" `
        -FilePath $Python `
        -Arguments @("-m", "keysight_logger_cli", "status", "--dry-run", "--format", "json", "--port", "8765") `
        -StdOutPath $softStatusJson `
        -StdErrPath (Join-Path $outDir "soft_status_dry_run.stderr.txt")
    $commands.Add([pscustomobject]$softStatusResult) | Out-Null
    Assert-Condition ($softStatusResult.success) "status dry-run command failed"
    $softStatus = Get-Content -LiteralPath $softStatusJson -Raw | ConvertFrom-Json -ErrorAction Stop
    Assert-Condition ($softStatus.event -eq "dry_run") "status dry-run event mismatch"
    Assert-Condition ($softStatus.send_request -eq $false) "status dry-run should not send HTTP"
    Assert-Condition ($softStatus.method -eq "GET") "status dry-run method mismatch"
    $checks.Add([pscustomobject]@{ name = "soft_status_dry_run_json"; success = $true; path = $softStatusJson }) | Out-Null

    $listResourcesJson = Join-Path $outDir "list_resources_dry_run.json"
    $listResourcesErr = Join-Path $outDir "list_resources_dry_run.stderr.txt"
    $listResourcesResult = Invoke-CapturedCommand `
        -Name "list_resources_dry_run_json" `
        -FilePath $Python `
        -Arguments @("-m", "keysight_logger_cli", "list-resources", "--dry-run", "--live-only", "--json") `
        -StdOutPath $listResourcesJson `
        -StdErrPath $listResourcesErr
    $commands.Add([pscustomobject]$listResourcesResult) | Out-Null
    Assert-Condition ($listResourcesResult.success) "list-resources dry-run command failed"
    $listResources = Get-Content -LiteralPath $listResourcesJson -Raw | ConvertFrom-Json -ErrorAction Stop
    Assert-Condition ($listResources.event -eq "dry_run") "list-resources dry-run event mismatch"
    Assert-Condition ($listResources.command -eq "list-resources") "list-resources dry-run command mismatch"
    Assert-Condition ($listResources.status -eq "dry_run") "list-resources dry-run status mismatch"
    Assert-Condition ($listResources.dry_run_performs_visa_io -eq $false) "list-resources dry-run should not perform VISA I/O"
    Assert-Condition ($listResources.live_only -eq $true) "list-resources dry-run live_only mismatch"
    Assert-Condition ($listResources.effective_verify -eq $true) "list-resources dry-run effective_verify mismatch"
    Assert-Condition ($listResources.planned_real_run.filter_live_only -eq $true) "list-resources dry-run filter_live_only mismatch"
    Assert-Condition ($listResources.planned_real_run.query_idn -eq $true) "list-resources dry-run query_idn mismatch"
    $checks.Add([pscustomobject]@{ name = "list_resources_dry_run_json"; success = $true; path = $listResourcesJson; stderr = $listResourcesErr }) | Out-Null

    $pytestOut = Join-Path $outDir "pytest_list_resources.stdout.txt"
    $pytestErr = Join-Path $outDir "pytest_list_resources.stderr.txt"
    $pytestResult = Invoke-CapturedCommand `
        -Name "pytest_list_resources_mocked" `
        -FilePath $Python `
        -Arguments @(
            "-m", "pytest",
            "tests/cli/test_cli_list_resources_command.py",
            "-q", "-p", "no:cacheprovider",
            "--basetemp", ".tmp_tests\pytest_tmp",
            "-k", "list_resources"
        ) `
        -StdOutPath $pytestOut `
        -StdErrPath $pytestErr
    $commands.Add([pscustomobject]$pytestResult) | Out-Null
    Assert-Condition ($pytestResult.success) "mocked list-resources pytest coverage failed"
    $checks.Add([pscustomobject]@{ name = "list_resources_mocked_pytest"; success = $true; stdout = $pytestOut; stderr = $pytestErr }) | Out-Null

    $checkItems = @($checks.ToArray())
    $commandItems = @($commands.ToArray())
    $summaryCounts = [ordered]@{
        commands_total = $commandItems.Count
        checks_total = $checkItems.Count
        dry_run_cases = @($checkItems | Where-Object { $_.name -like "dry_run_*" }).Count
        simulate_cases = @($checkItems | Where-Object { $_.name -like "simulate_*" }).Count
        soft_client_dry_runs = @($checkItems | Where-Object { $_.name -in @("soft_trigger_dry_run_json", "soft_stop_dry_run_json", "soft_status_dry_run_json") }).Count
        list_resources_contract_checks = @($checkItems | Where-Object { $_.name -eq "list_resources_dry_run_json" }).Count
        mocked_pytest_checks = @($checkItems | Where-Object { $_.name -eq "list_resources_mocked_pytest" }).Count
    }

    $reportPath = Join-Path $outDir "report.json"
    $summaryPath = Join-Path $outDir "summary.md"
    $report = [ordered]@{
        schema_version = 1
        target = $ResolvedTarget
        generated_at = (Get-Date).ToUniversalTime().ToString("o")
        package_version = Get-PackageVersion
        git_head = Get-GitHead
        validation_mode = "preflight"
        output_dir = $outDir
        artifact_paths = [ordered]@{
            output_dir = $outDir
            report = $reportPath
            summary = $summaryPath
        }
        status = "passed"
        summary_counts = $summaryCounts
        commands = $commandItems
        checks = $checkItems
    }
    Write-JsonReport -LiteralPath $reportPath -Report $report -Depth 10

    $summaryLines = @(
        "# CLI Preflight Summary",
        "",
        "- Target: $ResolvedTarget",
        "- Status: passed",
        "- Package version: $($report.package_version)",
        "- Git HEAD: $($report.git_head)",
        "- Validation mode: preflight",
        "- Output directory: $outDir",
        "- Commands total: $($summaryCounts.commands_total)",
        "- Checks total: $($summaryCounts.checks_total)",
        "- Dry-run cases: $($summaryCounts.dry_run_cases)",
        "- Simulate cases: $($summaryCounts.simulate_cases)",
        "- Soft client dry-runs: $($summaryCounts.soft_client_dry_runs)",
        "- list-resources contract checks: $($summaryCounts.list_resources_contract_checks)",
        "- Mocked pytest checks: $($summaryCounts.mocked_pytest_checks)",
        "- Measurements covered by dry-run and simulator immediate: $($measurements -join ', ')",
        "- Read paths covered: READ?, FETC?, DATA:POINts? / DATA:REMove?",
        "- Simulator trigger modes covered: immediate, software, software timer, immediate-custom, software-custom, external, external-custom",
        "- Soft client dry-runs: passed",
        "- list-resources dry-run JSON contract: passed",
        "- Mocked list-resources coverage: passed",
        "- Report: $reportPath"
    )
    Write-Utf8NoBomLines -LiteralPath $summaryPath -Lines $summaryLines

    Write-Host "preflight passed: $ResolvedTarget"
    Write-Host "summary: $summaryPath"
    return [pscustomobject]@{
        target = $ResolvedTarget
        status = "passed"
        output_dir = $outDir
        report = $reportPath
        summary = $summaryPath
    }
}

$targets = if ($Target -eq "all") {
    @("keysight-34461a")
} else {
    @($Target)
}

$results = foreach ($item in $targets) {
    Invoke-TargetPreflight -ResolvedTarget $item
}

if (@($results).Count -gt 1) {
    Write-Host "all CLI preflight targets passed"
}
