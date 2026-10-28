param(
    [string]$DistPath = "dist",
    [string]$WorkRoot = "build",
    [string]$SourceRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$SpecPath = Join-Path $PSScriptRoot "meters-tool-windows.spec"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python executable not found: $Python"
}
if (-not (Test-Path -LiteralPath $SpecPath -PathType Leaf)) {
    throw "PyInstaller spec not found: $SpecPath"
}

$pythonBits = (& $Python -c "import struct; print(struct.calcsize('P') * 8)").Trim()
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
if ($pythonBits -ne "64") {
    throw "Windows x64 bundle requires a 64-bit Python environment."
}

$repoFull = [System.IO.Path]::GetFullPath($RepoRoot)
$repoPrefix = $repoFull.TrimEnd([System.IO.Path]::DirectorySeparatorChar) +
    [System.IO.Path]::DirectorySeparatorChar

if ([System.IO.Path]::IsPathRooted($DistPath)) {
    $distFull = [System.IO.Path]::GetFullPath($DistPath)
} else {
    $distFull = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $DistPath))
}
if (-not (
    $distFull.Equals($repoFull, [System.StringComparison]::OrdinalIgnoreCase) -or
    $distFull.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)
)) {
    throw "DistPath must stay under the repository: $distFull"
}

if ([System.IO.Path]::IsPathRooted($WorkRoot)) {
    $workRootFull = [System.IO.Path]::GetFullPath($WorkRoot)
} else {
    $workRootFull = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $WorkRoot))
}
if (-not $workRootFull.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "WorkRoot must stay under the repository: $workRootFull"
}

if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
    $sourceRootFull = $repoFull
} elseif ([System.IO.Path]::IsPathRooted($SourceRoot)) {
    $sourceRootFull = [System.IO.Path]::GetFullPath($SourceRoot)
} else {
    $sourceRootFull = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $SourceRoot))
}
if (-not (Test-Path -LiteralPath $sourceRootFull -PathType Container)) {
    throw "SourceRoot directory not found: $sourceRootFull"
}
$sourceRootFull = (Resolve-Path -LiteralPath $sourceRootFull).Path
if (-not (
    $sourceRootFull.Equals($repoFull, [System.StringComparison]::OrdinalIgnoreCase) -or
    $sourceRootFull.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)
)) {
    throw "SourceRoot must stay under the repository: $sourceRootFull"
}

$sourcePath = Join-Path $sourceRootFull "src"
$previousPythonPath = $env:PYTHONPATH
$pyinstallerExitCode = 1

try {
    $env:PYTHONPATH = $sourcePath
    & $Python -m PyInstaller `
        --noconfirm `
        --distpath $distFull `
        --workpath (Join-Path $workRootFull "pyinstaller-windows-bundle") `
        $SpecPath `
        -- `
        --source-root $sourceRootFull
    $pyinstallerExitCode = $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $previousPythonPath
}

if ($pyinstallerExitCode -ne 0) {
    exit $pyinstallerExitCode
}

# Preserve project and LGPL library license notices in standalone and Desktop bundles.
# The Desktop builder copies the shared onedir bundle, and release packaging copies
# the Desktop directory. Use SourceRoot so release builds use their source snapshot.
$zeroconfVersion = (& $Python -c "from importlib.metadata import version; print(version('zeroconf'))").Trim()
if ($LASTEXITCODE -ne 0 -or $zeroconfVersion -ne "0.151.5") {
    throw "Bundled zeroconf version '$zeroconfVersion' differs from the reviewed 0.151.5 license notice. Update third-party notices before building."
}

$bundleDirectory = Join-Path $distFull "meters-tool"
if (-not (Test-Path -LiteralPath $bundleDirectory -PathType Container)) {
    throw "Windows bundle directory not found: $bundleDirectory"
}

$noticePaths = @(
    "LICENSE",
    "THIRD_PARTY_NOTICES.txt",
    "third_party/licenses/zeroconf-COPYING"
)
foreach ($relativePath in $noticePaths) {
    $sourceNotice = Join-Path $sourceRootFull $relativePath
    if (-not (Test-Path -LiteralPath $sourceNotice -PathType Leaf)) {
        throw "Required license notice not found: $sourceNotice"
    }
    $targetNotice = Join-Path $bundleDirectory $relativePath
    $targetParent = Split-Path -Parent $targetNotice
    New-Item -ItemType Directory -Force -Path $targetParent | Out-Null
    Copy-Item -LiteralPath $sourceNotice -Destination $targetNotice -Force
}
