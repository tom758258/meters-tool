Set-StrictMode -Version Latest

function Get-PackageVersion {
    param(
        [string]$ProjectRoot,
        [switch]$Required
    )

    if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
        $ProjectRoot = $RepoRoot
    }
    $pyproject = Join-Path $ProjectRoot "pyproject.toml"
    $match = Select-String -LiteralPath $pyproject -Pattern '^version\s*=\s*"([^"]+)"' | Select-Object -First 1
    if ($null -eq $match) {
        if ($Required) {
            throw "Could not read project version from $pyproject"
        }
        return $null
    }
    return $match.Matches[0].Groups[1].Value
}

function Get-GitHead {
    param([string]$ProjectRoot)

    if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
        $ProjectRoot = $RepoRoot
    }
    try {
        $head = & git -C $ProjectRoot rev-parse HEAD 2>$null
        if ($LASTEXITCODE -eq 0) {
            return $head.Trim()
        }
    } catch {
    }
    return $null
}

function Add-RepoSrcToPythonPath {
    param([Parameter(Mandatory = $true)][string]$RepoRoot)

    $packageSrcRoots = @(
        (Join-Path $RepoRoot "src")
    )
    $existingPythonPath = [Environment]::GetEnvironmentVariable("PYTHONPATH", "Process")
    if ([string]::IsNullOrWhiteSpace($existingPythonPath)) {
        [Environment]::SetEnvironmentVariable("PYTHONPATH", ($packageSrcRoots -join [System.IO.Path]::PathSeparator), "Process")
    } else {
        [Environment]::SetEnvironmentVariable(
            "PYTHONPATH",
            (($packageSrcRoots + $existingPythonPath) -join [System.IO.Path]::PathSeparator),
            "Process"
        )
    }
}

function Get-FullPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [System.IO.Path]::GetFullPath($Path)
}

function Assert-PathUnderRoot {
    param(
        [Parameter(Mandatory = $true)][string]$RootPath,
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Message
    )

    $rootFull = (Get-FullPath $RootPath).TrimEnd([System.IO.Path]::DirectorySeparatorChar)
    $pathFull = Get-FullPath $Path
    $comparison = [System.StringComparison]::OrdinalIgnoreCase
    if (-not $pathFull.StartsWith($rootFull + [System.IO.Path]::DirectorySeparatorChar, $comparison)) {
        throw ($Message -f $pathFull)
    }
}

function Get-AvailableTcpPort {
    $listener = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Parse("127.0.0.1"),
        0
    )
    $listener.Start()
    try {
        return [int]$listener.LocalEndpoint.Port
    } finally {
        $listener.Stop()
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

function Write-Utf8NoBomText {
    param(
        [Parameter(Mandatory = $true)][string]$LiteralPath,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Text
    )

    [System.IO.File]::WriteAllText(
        $LiteralPath,
        $Text,
        [System.Text.UTF8Encoding]::new($false)
    )
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

function Write-JsonReport {
    param(
        [Parameter(Mandatory = $true)][string]$LiteralPath,
        [Parameter(Mandatory = $true)]$Report,
        [int]$Depth = 12
    )

    Write-Utf8NoBomText -LiteralPath $LiteralPath -Text ($Report | ConvertTo-Json -Depth $Depth)
}

function Invoke-CapturedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$StdOutPath,
        [Parameter(Mandatory = $true)][string]$StdErrPath,
        [string]$WorkingDirectory = $RepoRoot
    )

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $FilePath
    $psi.WorkingDirectory = $WorkingDirectory
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

    Write-Utf8NoBomText -LiteralPath $StdOutPath -Text $stdout
    Write-Utf8NoBomText -LiteralPath $StdErrPath -Text $stderr

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
