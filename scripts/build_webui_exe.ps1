param(
    [string]$DistPath = "dist",
    [string]$Name = "meters-tool-webui-launcher"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python executable not found: $Python"
}

if ([System.IO.Path]::IsPathRooted($DistPath)) {
    $distFull = [System.IO.Path]::GetFullPath($DistPath)
} else {
    $distFull = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $DistPath))
}
$repoFull = [System.IO.Path]::GetFullPath($RepoRoot)
$repoPrefix = $repoFull.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
if (-not (
    $distFull.Equals($repoFull, [System.StringComparison]::OrdinalIgnoreCase) -or
    $distFull.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)
)) {
    throw "DistPath must stay under the repository: $distFull"
}

& $Python -m PyInstaller `
    --onefile `
    --windowed `
    --name $Name `
    --distpath $distFull `
    --workpath (Join-Path $RepoRoot "build\pyinstaller-webui") `
    --specpath (Join-Path $RepoRoot "build\pyinstaller-specs") `
    --paths (Join-Path $RepoRoot "src") `
    --add-data "$(Join-Path $RepoRoot 'src\meters_tool_webui\static');meters_tool_webui\static" `
    (Join-Path $RepoRoot "src\meters_tool_webui\launcher.py")

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
