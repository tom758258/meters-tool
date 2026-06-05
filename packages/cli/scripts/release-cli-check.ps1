param(
    [ValidateSet("keysight-34461a")]
    [string]$Target = "keysight-34461a",

    [string]$Release = "cli-v1.3.1",

    [string]$Resource = "SIM::34461A",

    [string]$OutputRoot = ".tmp_tests\cli_release"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$PackageRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..\..")).Path
$TmpRoot = Join-Path $RepoRoot ".tmp_tests"
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python executable not found: $Python"
}

$PackageSrcRoots = @(
    (Join-Path $RepoRoot "packages\core\src"),
    (Join-Path $RepoRoot "packages\cli\src"),
    (Join-Path $RepoRoot "packages\webui\src")
)
$ExistingPythonPath = [Environment]::GetEnvironmentVariable("PYTHONPATH", "Process")
if ([string]::IsNullOrWhiteSpace($ExistingPythonPath)) {
    [Environment]::SetEnvironmentVariable("PYTHONPATH", ($PackageSrcRoots -join [System.IO.Path]::PathSeparator), "Process")
} else {
    [Environment]::SetEnvironmentVariable(
        "PYTHONPATH",
        (($PackageSrcRoots + $ExistingPythonPath) -join [System.IO.Path]::PathSeparator),
        "Process"
    )
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
        throw "Only paths under .tmp_tests are allowed for release output: $pathFull"
    }
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

function Get-PackageVersion {
    $pyproject = Join-Path $PackageRoot "pyproject.toml"
    $match = Select-String -LiteralPath $pyproject -Pattern '^version\s*=\s*"([^"]+)"' | Select-Object -First 1
    if ($null -eq $match) {
        return $null
    }
    return $match.Matches[0].Groups[1].Value
}

function Get-GitHead {
    try {
        $head = & git -C $RepoRoot rev-parse HEAD 2>$null
        if ($LASTEXITCODE -eq 0) {
            return $head.Trim()
        }
    } catch {
    }
    return $null
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
            "packages/cli/tests/test_cli_package_metadata.py",
            "packages/cli/tests/test_docs_cli_examples.py",
            "packages/core/tests/test_core_public_api.py",
            "packages/cli/tests/test_cli_docs_ownership.py",
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
        args = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ".\packages\cli\scripts\preflight-cli.ps1", "-Target", $Target)
    },
    [pscustomobject]@{
        name = "live_cli_plan_only"
        file = "powershell.exe"
        args = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ".\packages\cli\scripts\live-cli-check.ps1", "-Target", $Target, "-Connection", "usb", "-Resource", $Resource, "-PlanOnly")
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
$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $reportPath -Encoding UTF8

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
Set-Content -LiteralPath $summaryPath -Value $summaryLines -Encoding UTF8

Write-Host "release check $status`: $Release"
Write-Host "summary: $summaryPath"
if ($status -ne "passed") {
    exit 1
}
