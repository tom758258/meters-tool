param(
    [ValidateSet("keysight-34461a")]
    [string]$Target = "keysight-34461a",

    [string]$Release = "1.4.0",

    [string]$Resource = "SIM::34461A",

    [string]$OutputRoot = ".tmp_tests\cli_release"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$TmpRoot = Join-Path $RepoRoot ".tmp_tests"
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
. (Join-Path $PSScriptRoot "_validation_helpers.ps1")

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python executable not found: $Python"
}

Add-RepoSrcToPythonPath -RepoRoot $RepoRoot

function Assert-UnderTmpRoot {
    param([Parameter(Mandatory = $true)][string]$Path)
    Assert-PathUnderRoot `
        -RootPath $TmpRoot `
        -Path $Path `
        -Message "Only paths under .tmp_tests are allowed for release output: {0}"
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

$releaseRoot = Resolve-OutputRoot -Path $OutputRoot
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = Join-Path (Join-Path $releaseRoot $Target) $timestamp
Assert-UnderTmpRoot -Path $runDir
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$reportPath = Join-Path $runDir "report.json"
$summaryPath = Join-Path $runDir "summary.md"
$commands = [System.Collections.Generic.List[object]]::new()

$commandSpecs = @(
    [pscustomobject]@{
        name = "pytest_metadata_docs"
        file = $Python
        args = @(
            "-m", "pytest",
            "tests/cli/test_cli_package_metadata.py",
            "tests/cli/test_docs_cli_examples.py",
            "tests/core/test_core_public_api.py",
            "tests/cli/test_cli_docs_ownership.py",
            "-q", "-p", "no:cacheprovider",
            "--basetemp", ".tmp_tests\pytest_tmp"
        )
    },
    [pscustomobject]@{
        name = "pytest_full"
        file = $Python
        args = @("-m", "pytest", "tests", "-q", "-p", "no:cacheprovider", "--basetemp", ".tmp_tests\pytest_tmp")
    },
    [pscustomobject]@{
        name = "preflight_cli"
        file = "powershell.exe"
        args = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ".\scripts\preflight-cli.ps1", "-Target", $Target)
    },
    [pscustomobject]@{
        name = "live_cli_plan_only"
        file = "powershell.exe"
        args = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ".\scripts\live-cli-check.ps1", "-Target", $Target, "-Connection", "usb", "-Resource", $Resource, "-PlanOnly")
    }
)

foreach ($spec in $commandSpecs) {
    $stdout = Join-Path $runDir "$($spec.name).stdout.txt"
    $stderr = Join-Path $runDir "$($spec.name).stderr.txt"
    $result = Invoke-CapturedCommand -Name $spec.name -FilePath $spec.file -Arguments $spec.args -StdOutPath $stdout -StdErrPath $stderr
    $commands.Add([pscustomobject]$result) | Out-Null
}

$commandItems = @($commands.ToArray())
$failedCommands = @($commandItems | Where-Object { -not $_.success })
$status = if ($failedCommands.Count -eq 0) { "passed" } else { "failed" }

$report = [ordered]@{
    schema_version = 1
    target_release = $Release
    package_version = Get-PackageVersion
    target = $Target
    resource = $Resource
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    git_head = Get-GitHead
    validation_mode = "release_no_hardware"
    output_dir = $runDir
    artifact_paths = [ordered]@{
        output_dir = $runDir
        report = $reportPath
        summary = $summaryPath
    }
    status = $status
    commands = $commandItems
}
Write-JsonReport -LiteralPath $reportPath -Report $report -Depth 12

$summaryLines = @(
    "# CLI Release Check Summary",
    "",
    "- Target release: $Release",
    "- Package version: $($report.package_version)",
    "- Target: $Target",
    "- Resource: $Resource",
    "- Status: $status",
    "- Validation mode: release_no_hardware",
    "- Git HEAD: $($report.git_head)",
    "- Output directory: $runDir",
    "- Report: $reportPath",
    "",
    "## Commands"
)
foreach ($command in $commandItems) {
    $summaryLines += "- $($command.name): exit_code=$($command.exit_code) success=$($command.success) stdout=$($command.stdout) stderr=$($command.stderr)"
}
Write-Utf8NoBomLines -LiteralPath $summaryPath -Lines $summaryLines

Write-Host "release check $status`: $Release"
Write-Host "summary: $summaryPath"
if ($status -ne "passed") {
    exit 1
}
