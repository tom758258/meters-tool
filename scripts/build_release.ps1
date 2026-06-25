param(
    [string]$Version,
    [string]$ReleaseRoot = "release"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python executable not found: $Python"
}

function Get-ProjectVersion {
    $pyproject = Join-Path $RepoRoot "pyproject.toml"
    $match = Select-String -LiteralPath $pyproject -Pattern '^version\s*=\s*"([^"]+)"' | Select-Object -First 1
    if ($null -eq $match) {
        throw "Could not read project version from $pyproject"
    }
    return $match.Matches[0].Groups[1].Value
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

if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = Get-ProjectVersion
}

if ([System.IO.Path]::IsPathRooted($ReleaseRoot)) {
    $releaseRootFull = [System.IO.Path]::GetFullPath($ReleaseRoot)
} else {
    $releaseRootFull = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $ReleaseRoot))
}
$repoFull = [System.IO.Path]::GetFullPath($RepoRoot)
$repoPrefix = $repoFull.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
if (-not (
    $releaseRootFull.Equals($repoFull, [System.StringComparison]::OrdinalIgnoreCase) -or
    $releaseRootFull.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)
)) {
    throw "ReleaseRoot must stay under the repository: $releaseRootFull"
}

$versionDir = Join-Path $releaseRootFull $Version
New-Item -ItemType Directory -Force -Path $versionDir | Out-Null

& $Python -m build
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "build_cli_exe.ps1") -DistPath $versionDir -Name "keysight-logger-$Version"
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "build_webui_exe.ps1") -DistPath $versionDir -Name "keysight-logger-webui-launcher-$Version"
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Copy-Item -LiteralPath (Join-Path $RepoRoot "dist\keysight_logger-$Version-py3-none-any.whl") -Destination $versionDir -Force
Copy-Item -LiteralPath (Join-Path $RepoRoot "dist\keysight_logger-$Version.tar.gz") -Destination $versionDir -Force

$checksums = foreach ($artifact in Get-ChildItem -LiteralPath $versionDir -File | Sort-Object Name) {
    $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $artifact.FullName
    "$($hash.Hash.ToLowerInvariant())  $($artifact.Name)"
}
Write-Utf8NoBomLines -LiteralPath (Join-Path $versionDir "checksums.txt") -Lines $checksums

Write-Host "release artifacts: $versionDir"
