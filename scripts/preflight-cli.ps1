param(
    [ValidateSet("all", "keysight-34461a")]
    [string]$Target = "all"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$TmpRoot = Join-Path $RepoRoot ".tmp_tests"
$PreflightRoot = Join-Path $TmpRoot "cli_preflight"
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python executable not found: $Python"
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
        throw "Refusing to clean path outside .tmp_tests: $pathFull"
    }
}

function Clear-OutputDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)
    New-Item -ItemType Directory -Force -Path $TmpRoot | Out-Null
    Assert-UnderTmpRoot -Path $Path
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
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

function Assert-Condition {
    param(
        [Parameter(Mandatory = $true)][bool]$Condition,
        [Parameter(Mandatory = $true)][string]$Message
    )
    if (-not $Condition) {
        throw $Message
    }
}

function Test-CsvHasRows {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    $rows = @(Import-Csv -LiteralPath $Path)
    return ($rows.Count -ge 1)
}

function Invoke-TargetPreflight {
    param([Parameter(Mandatory = $true)][string]$ResolvedTarget)

    $outDir = Join-Path $PreflightRoot $ResolvedTarget
    Clear-OutputDirectory -Path $outDir

    $dryRunJsonl = Join-Path $outDir "dry_run.jsonl"
    $dryRunCsv = Join-Path $outDir "dry_run.csv"
    $simulateJsonl = Join-Path $outDir "simulate.jsonl"
    $simulateCsv = Join-Path $outDir "simulate.csv"
    $softTriggerJson = Join-Path $outDir "soft_trigger.json"
    $softStopJson = Join-Path $outDir "soft_stop.json"
    $pytestOut = Join-Path $outDir "pytest_list_resources.stdout.txt"
    $pytestErr = Join-Path $outDir "pytest_list_resources.stderr.txt"

    $checks = [System.Collections.Generic.List[object]]::new()
    $commands = [System.Collections.Generic.List[object]]::new()

    $startBaseArgs = @(
        "-m", "keysight_logger.cli",
        "start-trigger-record",
        "--resource", "SIM::34461A",
        "--trigger-mode", "immediate",
        "--measurement", "current-dc",
        "--auto-range", "on",
        "--auto-zero", "off",
        "--nplc", "1.0",
        "--max-samples", "1",
        "--status-format", "jsonl"
    )

    $dryRunArgs = @($startBaseArgs + @("--csv", $dryRunCsv, "--dry-run"))
    $dryRunResult = Invoke-CapturedCommand `
        -Name "start_dry_run" `
        -FilePath $Python `
        -Arguments $dryRunArgs `
        -StdOutPath $dryRunJsonl `
        -StdErrPath (Join-Path $outDir "dry_run.stderr.txt")
    $commands.Add([pscustomobject]$dryRunResult) | Out-Null
    Assert-Condition ($dryRunResult.success) "dry-run command failed"
    $dryRunEvents = @(Read-JsonLines -Path $dryRunJsonl)
    Assert-Condition ($dryRunEvents.Count -eq 1) "dry-run should emit one JSONL event"
    Assert-Condition ($dryRunEvents[0].event -eq "dry_run") "dry-run event type mismatch"
    Assert-Condition ($dryRunEvents[0].trigger_mode -eq "immediate") "dry-run trigger mode mismatch"
    Assert-Condition ($dryRunEvents[0].measurement_cli_name -eq "current-dc") "dry-run measurement mismatch"
    Assert-Condition ($dryRunEvents[0].read_path -like "*READ?*") "dry-run read path should mention READ?"
    $checks.Add([pscustomobject]@{ name = "dry_run_jsonl_plan"; success = $true; path = $dryRunJsonl }) | Out-Null

    $simulateArgs = @($startBaseArgs + @("--csv", $simulateCsv, "--simulate"))
    $simulateResult = Invoke-CapturedCommand `
        -Name "start_simulate" `
        -FilePath $Python `
        -Arguments $simulateArgs `
        -StdOutPath $simulateJsonl `
        -StdErrPath (Join-Path $outDir "simulate.stderr.txt")
    $commands.Add([pscustomobject]$simulateResult) | Out-Null
    Assert-Condition ($simulateResult.success) "simulate command failed"
    $simulateEvents = @(Read-JsonLines -Path $simulateJsonl)
    $summary = @($simulateEvents | Where-Object { $_.event -eq "summary" } | Select-Object -Last 1)
    Assert-Condition ($summary.Count -eq 1) "simulate summary event missing"
    Assert-Condition ([int]$summary[0].captured -eq 1) "simulate summary captured should be 1"
    Assert-Condition ([int]$summary[0].errors -eq 0) "simulate summary errors should be 0"
    Assert-Condition (Test-CsvHasRows -Path $simulateCsv) "simulate CSV should contain at least one data row"
    $checks.Add([pscustomobject]@{
        name = "simulate_jsonl_summary"
        success = $true
        captured = [int]$summary[0].captured
        errors = [int]$summary[0].errors
        jsonl = $simulateJsonl
        csv = $simulateCsv
    }) | Out-Null

    $softTriggerResult = Invoke-CapturedCommand `
        -Name "soft_trigger_dry_run" `
        -FilePath $Python `
        -Arguments @("-m", "keysight_logger.cli", "soft-trigger", "--dry-run", "--format", "json", "--port", "8765", "--meta", '{"source":"preflight"}') `
        -StdOutPath $softTriggerJson `
        -StdErrPath (Join-Path $outDir "soft_trigger.stderr.txt")
    $commands.Add([pscustomobject]$softTriggerResult) | Out-Null
    Assert-Condition ($softTriggerResult.success) "soft-trigger dry-run command failed"
    $softTrigger = Get-Content -LiteralPath $softTriggerJson -Raw | ConvertFrom-Json -ErrorAction Stop
    Assert-Condition ($softTrigger.event -eq "dry_run") "soft-trigger dry-run event mismatch"
    Assert-Condition ($softTrigger.send_request -eq $false) "soft-trigger dry-run should not send HTTP"
    $checks.Add([pscustomobject]@{ name = "soft_trigger_dry_run_json"; success = $true; path = $softTriggerJson }) | Out-Null

    $softStopResult = Invoke-CapturedCommand `
        -Name "soft_stop_dry_run" `
        -FilePath $Python `
        -Arguments @("-m", "keysight_logger.cli", "soft-stop", "--dry-run", "--format", "json", "--port", "8765") `
        -StdOutPath $softStopJson `
        -StdErrPath (Join-Path $outDir "soft_stop.stderr.txt")
    $commands.Add([pscustomobject]$softStopResult) | Out-Null
    Assert-Condition ($softStopResult.success) "soft-stop dry-run command failed"
    $softStop = Get-Content -LiteralPath $softStopJson -Raw | ConvertFrom-Json -ErrorAction Stop
    Assert-Condition ($softStop.event -eq "dry_run") "soft-stop dry-run event mismatch"
    Assert-Condition ($softStop.send_request -eq $false) "soft-stop dry-run should not send HTTP"
    $checks.Add([pscustomobject]@{ name = "soft_stop_dry_run_json"; success = $true; path = $softStopJson }) | Out-Null

    $pytestResult = Invoke-CapturedCommand `
        -Name "pytest_list_resources_mocked" `
        -FilePath $Python `
        -Arguments @("-m", "pytest", "tests/test_cli_args.py", "-q", "-p", "no:cacheprovider", "-k", "list_resources") `
        -StdOutPath $pytestOut `
        -StdErrPath $pytestErr
    $commands.Add([pscustomobject]$pytestResult) | Out-Null
    Assert-Condition ($pytestResult.success) "mocked list-resources pytest coverage failed"
    $checks.Add([pscustomobject]@{ name = "list_resources_mocked_pytest"; success = $true; stdout = $pytestOut }) | Out-Null

    $report = [ordered]@{
        schema_version = 1
        target = $ResolvedTarget
        generated_at = (Get-Date).ToUniversalTime().ToString("o")
        output_dir = $outDir
        status = "passed"
        commands = @($commands.ToArray())
        checks = @($checks.ToArray())
    }
    $reportPath = Join-Path $outDir "report.json"
    $summaryPath = Join-Path $outDir "summary.md"
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportPath -Encoding UTF8

    $summaryLines = @(
        "# CLI Preflight Summary",
        "",
        "- Target: $ResolvedTarget",
        "- Status: passed",
        "- Output directory: $outDir",
        "- Dry-run JSONL: $dryRunJsonl",
        "- Simulate JSONL: $simulateJsonl",
        "- Simulate CSV: $simulateCsv",
        "- Simulate summary: captured=1 errors=0",
        "- Mocked list-resources coverage: passed"
    )
    Set-Content -LiteralPath $summaryPath -Value $summaryLines -Encoding UTF8

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
