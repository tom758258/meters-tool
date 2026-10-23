param(
    [string]$Target = "keysight-34461a",

    [string]$Release,

    [string]$Resource,

    [string]$OutputRoot = ".tmp_tests\release_acceptance"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$TmpRoot = Join-Path $RepoRoot ".tmp_tests"
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
. (Join-Path $PSScriptRoot "_validation_helpers.ps1")

function Get-PackageName {
    $pyproject = Join-Path $RepoRoot "pyproject.toml"
    $match = Select-String -LiteralPath $pyproject -Pattern '^name\s*=\s*"([^"]+)"' |
        Select-Object -First 1
    if ($null -eq $match) {
        throw "Could not read project name from $pyproject"
    }
    return $match.Matches[0].Groups[1].Value
}

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

function Get-RepoRelativePath {
    param([Parameter(Mandatory = $true)][string]$Path)
    $fullPath = Get-FullPath $Path
    $repoPrefix = $RepoRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) +
        [System.IO.Path]::DirectorySeparatorChar
    if (-not $fullPath.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside the repository: $fullPath"
    }
    return $fullPath.Substring($repoPrefix.Length).Replace("\", "/")
}

$resolvedTarget = Resolve-ValidationTarget -Target $Target
$targetModel = Get-TargetCliModel -ResolvedTarget $resolvedTarget
if ([string]::IsNullOrWhiteSpace($Resource)) {
    $Resource = "SIM::$targetModel"
}
$expectedSimulatorResource = "SIM::$targetModel"
if (-not $Resource.Equals($expectedSimulatorResource, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Release acceptance requires simulator resource $expectedSimulatorResource."
}

$packageName = Get-PackageName
if ($packageName -ne "meters-tool") {
    throw "Package name $packageName does not match expected project name meters-tool"
}
$packageVersion = Get-PackageVersion -Required
if ([string]::IsNullOrWhiteSpace($Release)) {
    $Release = $packageVersion
} elseif ($Release -ne $packageVersion) {
    throw "Release $Release does not match package version $packageVersion"
}

$releaseRoot = Resolve-OutputRoot -Path $OutputRoot
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss-fff"
$runDir = Join-Path (Join-Path $releaseRoot $resolvedTarget) $timestamp
Assert-UnderTmpRoot -Path $runDir
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$reportPath = Join-Path $runDir "report.json"
$summaryPath = Join-Path $runDir "summary.md"
$commands = [System.Collections.Generic.List[object]]::new()
$artifacts = [System.Collections.Generic.List[object]]::new()
$script:currentStep = "initialize"
$failedStep = $null
$failureMessage = $null
$gitHead = $null
$finalGitHead = $null
$finalReleaseDir = $null
$checksumsPath = $null
$windowsBundleZip = $null
$cliExe = $null
$launcherExe = $null
$wheel = $null
$sdist = $null
$checksumValidation = "not_run"
$standaloneCliSmoke = "not_run"
$launcherSelfTest = "not_run"

function Invoke-RecordedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    Write-Host "[start] $Name"
    $stdout = Join-Path $runDir "$Name.stdout.txt"
    $stderr = Join-Path $runDir "$Name.stderr.txt"
    try {
        $result = [pscustomobject](Invoke-CapturedCommand `
            -Name $Name `
            -FilePath $FilePath `
            -Arguments $Arguments `
            -StdOutPath $stdout `
            -StdErrPath $stderr)
    } catch {
        Write-Host "[failed] $Name"
        throw
    }
    $result | Add-Member -NotePropertyName error -NotePropertyValue $null
    $commands.Add($result) | Out-Null
    if (-not $result.success) {
        Write-Host "[failed] $Name duration=$($result.duration_seconds)s"
        throw "Step '$Name' failed with exit code $($result.exit_code)."
    }
    Write-Host "[passed] $Name duration=$($result.duration_seconds)s"
    return $result
}

function Set-RecordedCommandFailure {
    param(
        [Parameter(Mandatory = $true)]$Result,
        [Parameter(Mandatory = $true)][string]$Message
    )
    $Result.success = $false
    $Result.error = $Message
    Write-Host "[failed] $($Result.name) duration=$($Result.duration_seconds)s"
    throw $Message
}

function Invoke-ArtifactSmoke {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][System.IO.FileInfo]$Artifact,
        [Parameter(Mandatory = $true)][string]$UvPath
    )

    $venvDir = Join-Path $runDir "$Label-venv"
    $venvPython = Join-Path $venvDir "Scripts\python.exe"
    $cliCommand = Join-Path $venvDir "Scripts\meters-tool.exe"
    $webuiCommand = Join-Path $venvDir "Scripts\meters-tool-webui.exe"
    $launcherCommand = Join-Path $venvDir "Scripts\meters-tool-webui-launcher.exe"
    $artifactSpec = "$($Artifact.FullName)[all]"

    $script:currentStep = "${Label}_create_venv"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $Python `
        -Arguments @("-m", "venv", $venvDir))

    $script:currentStep = "${Label}_install"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $UvPath `
        -Arguments @("pip", "install", "--python", $venvPython, "--link-mode", "copy", $artifactSpec))

    $script:currentStep = "${Label}_imports_and_version"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $venvPython `
        -Arguments @(
            "-c",
            "import sys; from importlib.metadata import version; from importlib.resources import files; import meters_tool_core, meters_tool_cli, meters_tool_webui; assert version('meters-tool') == sys.argv[1]; static_root = files('meters_tool_webui').joinpath('static'); required_static = ('index.html', 'styles.css', 'app.js'); missing_static = [name for name in required_static if not static_root.joinpath(name).is_file()]; assert not missing_static, f'Missing packaged WebUI static files: {missing_static}'; cli_help_root = files('meters_tool_cli').joinpath('help'); required_cli_help = ('cli.html', 'cli.zh-TW.html', 'supported-models.html', 'supported-models.zh-TW.html', 'help.css'); missing_cli_help = [name for name in required_cli_help if not cli_help_root.joinpath(name).is_file()]; assert not missing_cli_help, f'Missing packaged CLI Help files: {missing_cli_help}'; webui_help_root = static_root.joinpath('help'); required_webui_help = ('webui.html', 'webui.zh-TW.html', 'supported-models.html', 'supported-models.zh-TW.html', 'help.css'); missing_webui_help = [name for name in required_webui_help if not webui_help_root.joinpath(name).is_file()]; assert not missing_webui_help, f'Missing packaged WebUI Help files: {missing_webui_help}'",
            $packageVersion
        ))

    $script:currentStep = "${Label}_launcher_entry_point"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $venvPython `
        -Arguments @(
            "-c",
            "import sys; from pathlib import Path; assert Path(sys.argv[1]).is_file(), f'Missing installed launcher entry point: {sys.argv[1]}'",
            $launcherCommand
        ))

    $script:currentStep = "${Label}_cli_version"
    $versionResult = Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $cliCommand `
        -Arguments @("--version")
    $versionOutput = (Get-Content -Raw -LiteralPath $versionResult.stdout).Trim()
    if ($versionOutput -ne "meters-tool $packageVersion") {
        Set-RecordedCommandFailure `
            -Result $versionResult `
            -Message "Installed CLI version was '$versionOutput'; expected 'meters-tool $packageVersion'."
    }

    $script:currentStep = "${Label}_cli_help"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $cliCommand `
        -Arguments @("--help"))

    $script:currentStep = "${Label}_webui_help"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $webuiCommand `
        -Arguments @("--help"))
}

try {
    $script:currentStep = "required_tools"
    if (-not (Test-Path -LiteralPath $Python)) {
        throw "Project Python executable not found: $Python"
    }
    $gitCommand = Get-Command -Name "git" -CommandType Application -ErrorAction Stop
    $uvCommand = Get-Command -Name "uv" -CommandType Application -ErrorAction Stop
    $nodeCommand = Get-Command -Name "node" -CommandType Application -ErrorAction Stop
    $npmCommand = Get-Command -Name "npm.cmd" -CommandType Application -ErrorAction Stop

    $script:currentStep = "git_version"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $gitCommand.Source `
        -Arguments @("--version"))

    $script:currentStep = "uv_version"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $uvCommand.Source `
        -Arguments @("--version"))

    $script:currentStep = "python_version"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $Python `
        -Arguments @("--version"))

    $script:currentStep = "node_version"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $nodeCommand.Source `
        -Arguments @("--version"))

    $script:currentStep = "npm_version"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $npmCommand.Source `
        -Arguments @("--version"))

    $script:currentStep = "pyinstaller_version"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $Python `
        -Arguments @("-m", "PyInstaller", "--version"))

    $script:currentStep = "git_clean"
    $gitStatusResult = Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $gitCommand.Source `
        -Arguments @("-C", $RepoRoot, "status", "--porcelain")
    $gitStatus = Get-Content -Raw -LiteralPath $gitStatusResult.stdout

    $script:currentStep = "git_head"
    $gitHeadResult = Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $gitCommand.Source `
        -Arguments @("-C", $RepoRoot, "rev-parse", "HEAD")
    $gitHead = (Get-Content -Raw -LiteralPath $gitHeadResult.stdout).Trim()
    if ([string]::IsNullOrWhiteSpace($gitHead)) {
        throw "Could not resolve Git HEAD."
    }
    if (-not [string]::IsNullOrWhiteSpace($gitStatus)) {
        $script:currentStep = "git_clean"
        Set-RecordedCommandFailure `
            -Result $gitStatusResult `
            -Message "Git working tree must be clean before release acceptance."
    }

    $script:currentStep = "uv_lock_check"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $uvCommand.Source `
        -Arguments @("lock", "--check"))

    $env:PYTHONNOUSERSITE = "1"
    foreach ($environmentVariable in @(
        "PYTHONPATH",
        "PYTHONHOME",
        "VIRTUAL_ENV",
        "UV_INTERNAL__PYTHONHOME",
        "UV_PROJECT_ENVIRONMENT"
    )) {
        [Environment]::SetEnvironmentVariable(
            $environmentVariable,
            $null,
            [EnvironmentVariableTarget]::Process
        )
    }

    $script:currentStep = "pytest_no_hardware"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $Python `
        -Arguments @(
            "-m", "pytest", "tests",
            "-q", "-p", "no:cacheprovider",
            "--basetemp", (Join-Path $runDir "pytest-no-hardware")
        ))

    $script:currentStep = "build_release"
    $finalArtifactsRoot = Join-Path $runDir "release"
    Assert-UnderTmpRoot -Path $finalArtifactsRoot
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath "powershell.exe" `
        -Arguments @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            (Join-Path $PSScriptRoot "build_release.ps1"),
            "-Version",
            $packageVersion,
            "-ReleaseRoot",
            $finalArtifactsRoot
        ))

    $script:currentStep = "validate_release_artifacts"
    $finalReleaseDir = Join-Path $finalArtifactsRoot $packageVersion
    Assert-UnderTmpRoot -Path $finalReleaseDir
    $expectedArtifactNames = @(
        "meters-tool-$packageVersion-windows-x64.zip",
        "meters_tool-$packageVersion-py3-none-any.whl",
        "meters_tool-$packageVersion.tar.gz"
    )
    $expectedReleaseNames = @($expectedArtifactNames + "checksums.txt")
    $releaseEntries = @(Get-ChildItem -LiteralPath $finalReleaseDir -Force)
    $invalidEntries = @(
        $releaseEntries |
            Where-Object { $_.PSIsContainer -or $_.Name -notin $expectedReleaseNames }
    )
    if (
        $releaseEntries.Count -ne $expectedReleaseNames.Count -or
        $invalidEntries.Count -ne 0
    ) {
        $found = ($releaseEntries.Name | Sort-Object) -join ", "
        throw "Final release directory does not contain exactly the expected files: $found"
    }
    foreach ($expectedName in $expectedReleaseNames) {
        if (-not (Test-Path -LiteralPath (Join-Path $finalReleaseDir $expectedName) -PathType Leaf)) {
            throw "Missing final release artifact: $expectedName"
        }
    }

    $windowsBundleZip = Get-Item -LiteralPath (Join-Path $finalReleaseDir $expectedArtifactNames[0])
    $wheel = Get-Item -LiteralPath (Join-Path $finalReleaseDir $expectedArtifactNames[1])
    $sdist = Get-Item -LiteralPath (Join-Path $finalReleaseDir $expectedArtifactNames[2])
    $checksumsPath = Join-Path $finalReleaseDir "checksums.txt"

    $script:currentStep = "validate_checksums"
    $checksumValidation = "failed"
    $checksumLines = @(Get-Content -LiteralPath $checksumsPath)
    if ($checksumLines.Count -ne $expectedArtifactNames.Count) {
        throw "checksums.txt must contain exactly $($expectedArtifactNames.Count) artifact entries."
    }
    $checksumEntries = @{}
    foreach ($line in $checksumLines) {
        if ($line -notmatch '^([0-9A-Fa-f]{64})  (.+)$') {
            throw "Malformed checksum entry: $line"
        }
        $filename = $Matches[2]
        if ($checksumEntries.ContainsKey($filename)) {
            throw "Duplicate checksum entry: $filename"
        }
        $checksumEntries[$filename] = $Matches[1].ToLowerInvariant()
    }
    foreach ($expectedName in $expectedArtifactNames) {
        if (-not $checksumEntries.ContainsKey($expectedName)) {
            throw "Missing checksum entry: $expectedName"
        }
    }
    foreach ($filename in $checksumEntries.Keys) {
        if ($filename -notin $expectedArtifactNames) {
            throw "Unexpected checksum entry: $filename"
        }
    }

    foreach ($artifact in @($windowsBundleZip, $wheel, $sdist)) {
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $artifact.FullName).Hash.ToLowerInvariant()
        if ($checksumEntries[$artifact.Name] -ne $hash) {
            throw "SHA-256 mismatch for $($artifact.Name)"
        }
        $artifactType = if ($artifact.Name -eq $expectedArtifactNames[0]) {
            "windows_bundle_zip"
        } elseif ($artifact.Name -eq $expectedArtifactNames[1]) {
            "wheel"
        } else {
            "sdist"
        }
        $relativePath = Get-RepoRelativePath -Path $artifact.FullName
        $artifacts.Add([pscustomobject][ordered]@{
            type = $artifactType
            path = $relativePath
            filename = $artifact.Name
            sha256 = $hash
            package_version = $packageVersion
        }) | Out-Null
    }
    $checksumValidation = "passed"

    $script:currentStep = "extract_windows_bundle"
    $bundleExtractRoot = Join-Path $runDir "windows-bundle"
    Assert-UnderTmpRoot -Path $bundleExtractRoot
    New-Item -ItemType Directory -Force -Path $bundleExtractRoot | Out-Null
    Expand-Archive `
        -LiteralPath $windowsBundleZip.FullName `
        -DestinationPath $bundleExtractRoot

    $expectedBundleDirName = "meters-tool-$packageVersion"
    $bundleRootEntries = @(Get-ChildItem -LiteralPath $bundleExtractRoot -Force)
    if (
        $bundleRootEntries.Count -ne 1 -or
        -not $bundleRootEntries[0].PSIsContainer -or
        $bundleRootEntries[0].Name -cne $expectedBundleDirName
    ) {
        $found = ($bundleRootEntries.Name | Sort-Object) -join ", "
        throw "Windows bundle ZIP must contain only $expectedBundleDirName`: $found"
    }

    $extractedBundleDir = $bundleRootEntries[0].FullName
    $requiredBundleFiles = @(
        "Meters Tool.exe",
        "meters-tool.exe",
        "meters-tool-webui-launcher.exe",
        "meters-tool-webui-host.exe"
    )
    foreach ($requiredFile in $requiredBundleFiles) {
        $requiredPath = Join-Path $extractedBundleDir $requiredFile
        if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
            throw "Unified Windows bundle is missing required file: $requiredFile"
        }
    }
    foreach ($requiredDirectory in @("_internal", "resources")) {
        $requiredPath = Join-Path $extractedBundleDir $requiredDirectory
        if (-not (Test-Path -LiteralPath $requiredPath -PathType Container)) {
            throw "Unified Windows bundle is missing required directory: $requiredDirectory"
        }
    }

    $cliExe = Get-Item -LiteralPath (Join-Path $extractedBundleDir "meters-tool.exe")
    $launcherExe = Get-Item -LiteralPath (
        Join-Path $extractedBundleDir "meters-tool-webui-launcher.exe"
    )
    $hostExe = Get-Item -LiteralPath (
        Join-Path $extractedBundleDir "meters-tool-webui-host.exe"
    )
    $internalDirectories = @(
        Get-ChildItem -LiteralPath $extractedBundleDir -Directory -Recurse -Force |
            Where-Object { $_.Name -eq "_internal" }
    )
    if ($internalDirectories.Count -ne 1) {
        throw "Unified Windows bundle must contain exactly one _internal directory."
    }
    if (-not $internalDirectories[0].FullName.Equals(
        (Join-Path $extractedBundleDir "_internal"),
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Unified Windows bundle _internal directory must be at the application root."
    }
    if (Test-Path -LiteralPath (Join-Path $extractedBundleDir "resources\backend")) {
        throw "Unified Windows bundle must not contain resources\backend."
    }
    $portableExecutables = @(
        Get-ChildItem -LiteralPath $extractedBundleDir `
            -Filter "*-portable.exe" -File -Recurse
    )
    if ($portableExecutables.Count -ne 0) {
        throw "Unified Windows bundle must not contain a portable executable."
    }

    Invoke-ArtifactSmoke -Label "wheel" -Artifact $wheel -UvPath $uvCommand.Source
    Invoke-ArtifactSmoke -Label "sdist" -Artifact $sdist -UvPath $uvCommand.Source

    $standaloneCliSmoke = "failed"
    $script:currentStep = "standalone_cli_version"
    $standaloneVersionResult = Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $cliExe.FullName `
        -Arguments @("--version")
    $standaloneVersionOutput = (Get-Content -Raw -LiteralPath $standaloneVersionResult.stdout).Trim()
    if ($standaloneVersionOutput -ne "meters-tool $packageVersion") {
        Set-RecordedCommandFailure `
            -Result $standaloneVersionResult `
            -Message "Standalone CLI version was '$standaloneVersionOutput'; expected 'meters-tool $packageVersion'."
    }

    $script:currentStep = "standalone_cli_help"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $cliExe.FullName `
        -Arguments @("--help"))

    $script:currentStep = "standalone_cli_simulator"
    $standaloneCsv = Join-Path $runDir "standalone-cli.csv"
    $standaloneResult = Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $cliExe.FullName `
        -Arguments @(
            "start-trigger-record",
            "--resource", $Resource,
            "--model", $targetModel,
            "--measurement", "current-dc",
            "--trigger-mode", "immediate",
            "--max-samples", "1",
            "--simulate",
            "--sw-trigger-port", "0",
            "--csv", $standaloneCsv,
            "--status-format", "jsonl"
        )
    $standaloneEvents = @(Read-JsonLines -Path $standaloneResult.stdout)
    $summaryEvents = @($standaloneEvents | Where-Object { $_.event -eq "summary" })
    if ($summaryEvents.Count -eq 0) {
        Set-RecordedCommandFailure `
            -Result $standaloneResult `
            -Message "Standalone CLI simulator did not produce a summary event."
    }
    $standaloneSummary = $summaryEvents[-1]
    if ([int]$standaloneSummary.captured -ne 1 -or [int]$standaloneSummary.errors -ne 0) {
        Set-RecordedCommandFailure `
            -Result $standaloneResult `
            -Message "Standalone CLI simulator summary did not report captured=1 and errors=0."
    }
    if ((Test-CsvRowCount -Path $standaloneCsv) -lt 1) {
        Set-RecordedCommandFailure `
            -Result $standaloneResult `
            -Message "Standalone CLI simulator CSV did not contain a data row."
    }

    $script:currentStep = "standalone_cli_manifest"
    $standaloneManifestResult = Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $cliExe.FullName `
        -Arguments @("manifest", "--json")
    $standaloneManifestEvents = @(Read-JsonLines -Path $standaloneManifestResult.stdout)
    if ($standaloneManifestEvents.Count -ne 1) {
        Set-RecordedCommandFailure `
            -Result $standaloneManifestResult `
            -Message "Standalone CLI manifest did not emit exactly one JSON object."
    }
    $standaloneManifest = $standaloneManifestEvents[0]
    if (
        $standaloneManifest.event -ne "tool_manifest" -or
        [int]$standaloneManifest.schema_version -ne 2 -or
        $standaloneManifest.tool_id -ne "meters" -or
        $standaloneManifest.tool_version -ne $packageVersion
    ) {
        Set-RecordedCommandFailure `
            -Result $standaloneManifestResult `
            -Message "Standalone CLI manifest payload did not match the expected tool manifest contract."
    }
    if (
        $standaloneManifest.worker_protocol.compatibility_policy -ne "v3-only" -or
        @($standaloneManifest.worker_protocol.schema_versions).Count -ne 1 -or
        [int]@($standaloneManifest.worker_protocol.schema_versions)[0] -ne 3
    ) {
        Set-RecordedCommandFailure `
            -Result $standaloneManifestResult `
            -Message "Standalone CLI manifest worker protocol did not report v3-only compatibility with schema versions [3]."
    }
    $standaloneCliSmoke = "passed"

    $launcherSelfTest = "failed"
    $script:currentStep = "launcher_self_test"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $launcherExe.FullName `
        -Arguments @("--self-test"))
    $launcherSelfTest = "passed"

    $script:currentStep = "preflight_cli"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath "powershell.exe" `
        -Arguments @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            ".\scripts\preflight-cli.ps1",
            "-Target",
            $resolvedTarget,
            "-OutputRoot",
            (Join-Path $runDir "preflight")
        ))

    $script:currentStep = "live_cli_plan_only"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath "powershell.exe" `
        -Arguments @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            ".\scripts\live-cli-check.ps1",
            "-Target",
            $resolvedTarget,
            "-Connection",
            "usb",
            "-Resource",
            $Resource,
            "-Suite",
            "minimal",
            "-PlanOnly",
            "-SkipPreflight"
        ))

    $script:currentStep = "git_diff_check_final"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $gitCommand.Source `
        -Arguments @("-C", $RepoRoot, "diff", "--check"))

    $script:currentStep = "git_clean_final"
    $finalGitStatusResult = Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $gitCommand.Source `
        -Arguments @("-C", $RepoRoot, "status", "--porcelain")
    $finalGitStatus = Get-Content -Raw -LiteralPath $finalGitStatusResult.stdout
    if (-not [string]::IsNullOrWhiteSpace($finalGitStatus)) {
        Set-RecordedCommandFailure `
            -Result $finalGitStatusResult `
            -Message "Git working tree must remain clean after release acceptance."
    }

    $script:currentStep = "git_head_final"
    $finalGitHeadResult = Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $gitCommand.Source `
        -Arguments @("-C", $RepoRoot, "rev-parse", "HEAD")
    $finalGitHead = (Get-Content -Raw -LiteralPath $finalGitHeadResult.stdout).Trim()
    if ([string]::IsNullOrWhiteSpace($finalGitHead)) {
        Set-RecordedCommandFailure `
            -Result $finalGitHeadResult `
            -Message "Could not resolve final Git HEAD."
    }
    if ($finalGitHead -cne $gitHead) {
        Set-RecordedCommandFailure `
            -Result $finalGitHeadResult `
            -Message "Git HEAD changed during release acceptance."
    }
} catch {
    $failedStep = $script:currentStep
    $failureMessage = $_.Exception.Message
}

$commandItems = @($commands.ToArray())
$artifactItems = @($artifacts.ToArray())
$status = if ($null -eq $failedStep) { "passed" } else { "failed" }
$relativeReportPath = Get-RepoRelativePath -Path $reportPath
$relativeSummaryPath = Get-RepoRelativePath -Path $summaryPath
$relativeOutputDir = Get-RepoRelativePath -Path $runDir
$relativeFinalReleaseDir = if ($null -ne $finalReleaseDir) {
    Get-RepoRelativePath -Path $finalReleaseDir
} else {
    $null
}

$report = [ordered]@{
    schema_version = 1
    kind = "release_acceptance"
    name = "Meters Tool Release Acceptance"
    target_release = $Release
    package_name = $packageName
    package_version = $packageVersion
    git_head = $gitHead
    final_git_head = $finalGitHead
    target = $resolvedTarget
    model_id = $resolvedTarget
    expected_model = $targetModel
    resource = $Resource
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    validation_mode = "release_acceptance_no_hardware"
    output_dir = $relativeOutputDir
    final_release_dir = $relativeFinalReleaseDir
    artifact_paths = [ordered]@{
        output_dir = $relativeOutputDir
        final_release_dir = $relativeFinalReleaseDir
        report = $relativeReportPath
        summary = $relativeSummaryPath
        checksums = if ($null -ne $checksumsPath -and (Test-Path -LiteralPath $checksumsPath)) {
            Get-RepoRelativePath -Path $checksumsPath
        } else {
            $null
        }
        windows_bundle_zip = if ($null -ne $windowsBundleZip) {
            Get-RepoRelativePath -Path $windowsBundleZip.FullName
        } else {
            $null
        }
        desktop_portable_exe = $null
        wheel = if ($null -ne $wheel) { Get-RepoRelativePath -Path $wheel.FullName } else { $null }
        sdist = if ($null -ne $sdist) { Get-RepoRelativePath -Path $sdist.FullName } else { $null }
    }
    checksum_validation = $checksumValidation
    standalone_cli_smoke = $standaloneCliSmoke
    launcher_self_test = $launcherSelfTest
    artifacts = $artifactItems
    status = $status
    failed_step = $failedStep
    error = $failureMessage
    commands = $commandItems
}
Write-JsonReport -LiteralPath $reportPath -Report $report -Depth 12

$summaryLines = @(
    "# Meters Tool Release Acceptance Summary",
    "",
    "- Package: $packageName $packageVersion",
    "- Target release: $Release",
    "- Target: $resolvedTarget",
    "- Expected model: $targetModel",
    "- Resource: $Resource",
    "- Git HEAD: $gitHead",
    "- Status: $status",
    "- Validation mode: release_acceptance_no_hardware",
    "- Output directory: $relativeOutputDir",
    "- Final release directory: $relativeFinalReleaseDir",
    "- Checksum validation: $checksumValidation",
    "- Standalone CLI smoke: $standaloneCliSmoke",
    "- Launcher self-test: $launcherSelfTest",
    "- Report: $relativeReportPath"
)
if ($null -ne $failedStep) {
    $summaryLines += "- Failed step: $failedStep"
    $summaryLines += "- Error: $failureMessage"
}
$summaryLines += @(
    "",
    "## Artifacts"
)
if ($artifactItems.Count -eq 0) {
    $summaryLines += "- No validated artifacts."
} else {
    foreach ($artifact in $artifactItems) {
        $summaryLines += "- $($artifact.type): $($artifact.filename) sha256=$($artifact.sha256)"
    }
}
$summaryLines += @(
    "",
    "## Commands"
)
foreach ($command in $commandItems) {
    $summaryLines += "- $($command.name): exit_code=$($command.exit_code) success=$($command.success)"
}
Write-Utf8NoBomLines -LiteralPath $summaryPath -Lines $summaryLines

Write-Host "release acceptance $status`: $Release"
Write-Host "summary: $relativeSummaryPath"
if ($status -ne "passed") {
    exit 1
}
Write-Host "GitHub Release upload directory: $relativeFinalReleaseDir"
