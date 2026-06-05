param(
    [Alias("Model", "Profile")]
    [string]$Target,

    [Alias("Transport")]
    [string]$Connection,

    [string]$Resource
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

function Test-CsvHasRows {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    $rows = @(Import-Csv -LiteralPath $Path)
    return ($rows.Count -ge 1)
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

if ([string]::IsNullOrWhiteSpace($Resource)) {
    Fail-Usage "Missing -Resource. Live checks never scan or guess a VISA resource."
}

$resolvedTarget = Resolve-Target -Value $Target
$resolvedConnection = Resolve-Connection -Value $Connection

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = Join-Path (Join-Path (Join-Path $LiveRoot $resolvedTarget) $resolvedConnection) $timestamp
Assert-UnderTmpRoot -Path $runDir
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$preflightOut = Join-Path $runDir "preflight.stdout.txt"
$preflightErr = Join-Path $runDir "preflight.stderr.txt"
$preflightResult = Invoke-CapturedCommand `
    -Name "preflight" `
    -FilePath "powershell.exe" `
    -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $PreflightScript, "-Target", $resolvedTarget) `
    -StdOutPath $preflightOut `
    -StdErrPath $preflightErr

if (-not $preflightResult.success) {
    $report = [ordered]@{
        schema_version = 1
        target = $resolvedTarget
        connection = $resolvedConnection
        resource = $Resource
        generated_at = (Get-Date).ToUniversalTime().ToString("o")
        output_dir = $runDir
        status = "preflight_failed"
        commands = @([pscustomobject]$preflightResult)
    }
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $runDir "report.json") -Encoding UTF8
    throw "Preflight failed. See $preflightOut and $preflightErr"
}

$liveCsv = Join-Path $runDir "live.csv"
$dryRunJsonl = Join-Path $runDir "dry_run.jsonl"
$dryRunErr = Join-Path $runDir "dry_run.stderr.txt"
$liveJsonl = Join-Path $runDir "live.jsonl"
$liveErr = Join-Path $runDir "live.stderr.txt"
$reportPath = Join-Path $runDir "report.json"
$summaryPath = Join-Path $runDir "summary.md"

$liveBaseArgs = @(
    "-m", "keysight_logger.cli",
    "start-trigger-record",
    "--resource", $Resource,
    "--csv", $liveCsv,
    "--trigger-mode", "immediate",
    "--measurement", "current-dc",
    "--auto-range", "on",
    "--auto-zero", "off",
    "--nplc", "1.0",
    "--max-samples", "1",
    "--status-format", "jsonl"
)

$dryRunResult = Invoke-CapturedCommand `
    -Name "live_args_dry_run" `
    -FilePath $Python `
    -Arguments @($liveBaseArgs + @("--dry-run")) `
    -StdOutPath $dryRunJsonl `
    -StdErrPath $dryRunErr
Assert-Condition ($dryRunResult.success) "Safe dry-run plan failed; live smoke was not started."

$dryRunEvents = @(Read-JsonLines -Path $dryRunJsonl)
Assert-Condition ($dryRunEvents.Count -eq 1) "Safe dry-run should emit one plan event."
$plan = $dryRunEvents[0]

Write-Host ""
Write-Host "Live CLI smoke plan"
Write-Host "Target: $resolvedTarget"
Write-Host "Connection: $resolvedConnection"
Write-Host "Resource: $Resource"
Write-Host "Output directory: $runDir"
Write-Host "Measurement: $($plan.measurement_cli_name)"
Write-Host "Trigger mode: $($plan.trigger_mode)"
Write-Host "Read path: $($plan.read_path)"
Write-Host "Cleanup: $($plan.cleanup_steps -join ', ')"
Write-Host "Planned SCPI/configuration:"
foreach ($command in $plan.scpi_commands) {
    Write-Host "  $command"
}
Write-Host "Possible state changes:"
Write-Host "  Connects to the explicit VISA resource and validates 34461A identity."
Write-Host "  Sends the existing CLI clear/reset and measurement setup sequence."
Write-Host "  Captures one current-dc immediate sample with READ?."
Write-Host "  Uses best-effort release/local cleanup; no initial state snapshot/restore is available."
Write-Host ""

if ([Console]::IsInputRedirected) {
    throw "Live smoke requires interactive Enter confirmation; stdin is redirected."
}
[void](Read-Host "Press Enter to run the live smoke, or Ctrl+C to cancel")

$liveResult = Invoke-CapturedCommand `
    -Name "live_smoke" `
    -FilePath $Python `
    -Arguments $liveBaseArgs `
    -StdOutPath $liveJsonl `
    -StdErrPath $liveErr

$status = "failed"
$captured = $null
$errors = $null
if ($liveResult.success) {
    $liveEvents = @(Read-JsonLines -Path $liveJsonl)
    $summary = @($liveEvents | Where-Object { $_.event -eq "summary" } | Select-Object -Last 1)
    Assert-Condition ($summary.Count -eq 1) "Live summary event missing."
    $captured = [int]$summary[0].captured
    $errors = [int]$summary[0].errors
    Assert-Condition ($captured -eq 1) "Live smoke should capture exactly one sample."
    Assert-Condition ($errors -eq 0) "Live smoke should finish with errors=0."
    Assert-Condition (Test-CsvHasRows -Path $liveCsv) "Live CSV should contain at least one data row."
    Assert-Condition (Test-Path -LiteralPath $liveJsonl) "Live JSONL log missing."
    $status = "passed"
}

$report = [ordered]@{
    schema_version = 1
    target = $resolvedTarget
    connection = $resolvedConnection
    resource = $Resource
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    output_dir = $runDir
    status = $status
    captured = $captured
    errors = $errors
    csv = $liveCsv
    jsonl = $liveJsonl
    commands = @(
        [pscustomobject]$preflightResult,
        [pscustomobject]$dryRunResult,
        [pscustomobject]$liveResult
    )
}
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportPath -Encoding UTF8

$summaryLines = @(
    "# Live CLI Check Summary",
    "",
    "- Target: $resolvedTarget",
    "- Connection: $resolvedConnection",
    "- Resource: $Resource",
    "- Status: $status",
    "- Captured: $captured",
    "- Errors: $errors",
    "- CSV: $liveCsv",
    "- JSONL log: $liveJsonl",
    "- Report: $reportPath"
)
Set-Content -LiteralPath $summaryPath -Value $summaryLines -Encoding UTF8

if (-not $liveResult.success) {
    throw "Live smoke command failed. See $liveJsonl and $liveErr"
}

Write-Host "live CLI smoke passed"
Write-Host "summary: $summaryPath"
