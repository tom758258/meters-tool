Set-StrictMode -Version Latest

function Get-PortableRelativePath {
    param(
        [Parameter(Mandatory = $true)][string]$BasePath,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $baseFull = [System.IO.Path]::GetFullPath($BasePath).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    $pathFull = [System.IO.Path]::GetFullPath($Path)
    $baseUri = [Uri]::new($baseFull)
    $pathUri = [Uri]::new($pathFull)
    return [Uri]::UnescapeDataString($baseUri.MakeRelativeUri($pathUri).ToString()).Replace('/', [System.IO.Path]::DirectorySeparatorChar)
}

function Test-ArtifactPathUnderRoot {
    param(
        [Parameter(Mandatory = $true)][string]$RootPath,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $rootFull = [System.IO.Path]::GetFullPath($RootPath).TrimEnd('\', '/')
    $pathFull = [System.IO.Path]::GetFullPath($Path)
    return $pathFull.StartsWith(
        $rootFull + [System.IO.Path]::DirectorySeparatorChar,
        [System.StringComparison]::OrdinalIgnoreCase
    )
}

function Get-RedactedResourceDisplay {
    param(
        [Parameter(Mandatory = $true)][string]$Resource,
        [string]$Connection
    )

    if (-not [string]::IsNullOrWhiteSpace($Connection)) {
        return "$($Connection.ToLowerInvariant()):<redacted-resource>"
    }
    if ($Resource -match '^(?i)USB') { return 'usb:<redacted-resource>' }
    if ($Resource -match '^(?i)TCPIP') { return 'lan:<redacted-resource>' }
    return '<redacted-resource>'
}

function Get-DistinctiveSensitiveTokens {
    param([AllowNull()][AllowEmptyString()][string]$Resource)

    if ([string]::IsNullOrWhiteSpace($Resource)) { return @() }
    $parts = @($Resource -split '::')
    if ($Resource -match '^(?i)USB') {
        if ($parts.Count -lt 5) { return @() }
        $serial = $parts[3]
        if ($serial.Length -lt 6 -or $serial -match '^[0]+$') { return @() }
        return @($serial)
    }
    if ($Resource -match '^(?i)TCPIP') {
        if ($parts.Count -lt 2) { return @() }
        $hostValue = $parts[1].Trim()
        $reservedTokens = @(
            '0', 'localhost', 'localhost.localdomain', '0.0.0.0', '127.0.0.1', '::1',
            'inst0', 'instr', 'socket', 'hislip0', 'tcpip', 'tcpip0'
        )
        if (
            $hostValue.Length -lt 3 -or
            $hostValue -match '^[0]+$' -or
            $hostValue -in $reservedTokens -or
            $hostValue -notmatch '^[A-Za-z0-9][A-Za-z0-9.:%_-]*$'
        ) {
            return @()
        }
        return @($hostValue)
    }
    return @()
}

function Protect-ArtifactText {
    param(
        [AllowNull()][AllowEmptyString()][string]$Text,
        [AllowNull()][AllowEmptyString()][string]$Resource,
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$PrivateRoot,
        [string[]]$SensitiveValues = @()
    )

    if ($null -eq $Text) { return $null }
    $safe = [string]$Text
    if (-not [string]::IsNullOrWhiteSpace($Resource)) {
        $safe = $safe -replace [regex]::Escape($Resource), '<redacted-resource>'
    }
    foreach ($item in @($SensitiveValues)) {
        if (-not [string]::IsNullOrWhiteSpace($item)) {
            $escaped = [regex]::Escape($item)
            $pattern = "(?<![A-Za-z0-9_.-])$escaped(?![A-Za-z0-9_.-])"
            $safe = [regex]::Replace(
                $safe,
                $pattern,
                '<redacted>',
                [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
            )
        }
    }
    $safe = $safe -replace [regex]::Escape($PrivateRoot), '<private-local-path>'
    $safe = $safe -replace [regex]::Escape($RepoRoot), '<repository-root>'
    $safe = $safe -replace '(?im)(Keysight(?: Technologies)?|Agilent(?: Technologies)?),[^\r\n]+', '<redacted-idn>'
    $safe = $safe -replace '(?i)TCPIP\d*::[^\s"'',]+(?:::[^\s"'',]+)*', 'lan:<redacted-resource>'
    $safe = $safe -replace '(?i)USB\d*::[^\s"'',]+(?:::[^\s"'',]+)*', 'usb:<redacted-resource>'
    $octet = '(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)'
    $privateIpPattern = "(?<![\d.])(?:10\.$octet\.$octet\.$octet|172\.(?:1[6-9]|2\d|3[01])\.$octet\.$octet|192\.168\.$octet\.$octet|169\.254\.$octet\.$octet)(?![\d.])"
    $safe = $safe -replace $privateIpPattern, '<redacted-ip>'
    $safe = $safe -replace '(?i)(?:[A-Z]:\\(?:Users|Documents and Settings|Temp)\\[^\s"'']+)', '<redacted-path>'
    $safe = $safe -replace '(?i)(?:[A-Z]:\\[^\s"'']+)', '<redacted-path>'
    $safe = $safe -replace '(?i)(?:/(?:home|Users|mnt|tmp)/[^\s"'']+)', '<redacted-path>'
    return $safe
}

function ConvertTo-SafeConsoleFailureReasons {
    param(
        [AllowNull()][AllowEmptyCollection()][object[]]$FailureReasons,
        [Parameter(Mandatory = $true)][string]$Resource,
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$PrivateRoot
    )

    $sensitiveValues = @(Get-DistinctiveSensitiveTokens -Resource $Resource)
    return @(
        foreach ($reason in @($FailureReasons)) {
            Protect-ArtifactText `
                -Text ([string]$reason) `
                -Resource $Resource `
                -RepoRoot $RepoRoot `
                -PrivateRoot $PrivateRoot `
                -SensitiveValues $sensitiveValues
        }
    )
}

function ConvertTo-ShareableArtifactValue {
    param(
        [AllowNull()]$Value,
        [string]$FieldName = '',
        [Parameter(Mandatory = $true)][string]$RunRoot,
        [Parameter(Mandatory = $true)][string]$PrivateRoot,
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$Resource,
        [Parameter(Mandatory = $true)][string]$Connection,
        [string[]]$SensitiveValues = @()
    )

    if ($null -eq $Value) { return $null }
    $key = $FieldName.ToLowerInvariant()
    if ($key -eq 'trigger_metadata') { return '<redacted-trigger-metadata>' }
    if ($key -in @('resource', 'resource_alias', 'visa_resource', 'resource_name', 'resource_id')) {
        return Get-RedactedResourceDisplay -Resource $Resource -Connection $Connection
    }
    if ($key -in @('serial', 'serial_number')) { return '<redacted>' }
    if ($key -eq 'idn' -or $key -eq 'raw_idn' -or $key -eq 'idn.raw') { return '<redacted-idn>' }
    if ($key -eq 'value') { return '<redacted>' }

    if ($Value -is [string]) {
        $text = [string]$Value
        $isRootedPath = $false
        try { $isRootedPath = [System.IO.Path]::IsPathRooted($text) } catch { $isRootedPath = $false }
        if ($isRootedPath) {
            if (Test-ArtifactPathUnderRoot -RootPath $PrivateRoot -Path $text) {
                if ([System.IO.Path]::GetExtension($text) -ieq '.csv') { return '<private-local-path>' }
                $relative = Get-PortableRelativePath -BasePath $PrivateRoot -Path $text
                return ('shareable/' + $relative.Replace('\', '/'))
            }
            if (Test-ArtifactPathUnderRoot -RootPath $RepoRoot -Path $text) {
                return (Get-PortableRelativePath -BasePath $RepoRoot -Path $text).Replace('\', '/')
            }
            return '<redacted-path>'
        }
        return Protect-ArtifactText -Text $text -Resource $Resource -RepoRoot $RepoRoot -PrivateRoot $PrivateRoot -SensitiveValues $SensitiveValues
    }
    if ($Value -is [System.Collections.IDictionary]) {
        $result = [ordered]@{}
        foreach ($entryKey in $Value.Keys) {
            $result[[string]$entryKey] = ConvertTo-ShareableArtifactValue -Value $Value[$entryKey] -FieldName ([string]$entryKey) -RunRoot $RunRoot -PrivateRoot $PrivateRoot -RepoRoot $RepoRoot -Resource $Resource -Connection $Connection -SensitiveValues $SensitiveValues
        }
        if (
            $Value.Contains('command') -and
            [string]$Value['command'] -eq 'READ?' -and
            $Value.Contains('response')
        ) {
            $result['response'] = '<redacted-measurement-value>'
            $result['response_omitted'] = $true
        }
        return $result
    }
    if ($Value -is [pscustomobject]) {
        $result = [ordered]@{}
        foreach ($property in $Value.PSObject.Properties) {
            $result[$property.Name] = ConvertTo-ShareableArtifactValue -Value $property.Value -FieldName $property.Name -RunRoot $RunRoot -PrivateRoot $PrivateRoot -RepoRoot $RepoRoot -Resource $Resource -Connection $Connection -SensitiveValues $SensitiveValues
        }
        $commandProperty = $Value.PSObject.Properties['command']
        $responseProperty = $Value.PSObject.Properties['response']
        if ($null -ne $commandProperty -and [string]$commandProperty.Value -eq 'READ?' -and $null -ne $responseProperty) {
            $result['response'] = '<redacted-measurement-value>'
            $result['response_omitted'] = $true
        }
        return $result
    }
    if ($Value -is [System.Collections.IEnumerable] -and -not ($Value -is [string])) {
        $items = @($Value | ForEach-Object { ConvertTo-ShareableArtifactValue -Value $_ -FieldName $FieldName -RunRoot $RunRoot -PrivateRoot $PrivateRoot -RepoRoot $RepoRoot -Resource $Resource -Connection $Connection -SensitiveValues $SensitiveValues })
        return ,$items
    }
    return $Value
}

function New-SafeJsonPlaceholder {
    param([Parameter(Mandatory = $true)][string]$ArtifactKind, [Parameter(Mandatory = $true)][string]$ParseStatus)
    return [ordered]@{
        artifact_available = $false
        artifact_kind = $ArtifactKind
        parse_status = $ParseStatus
        parse_error = if ($ParseStatus -eq 'failed') { "Could not parse $ArtifactKind." } else { $null }
        private_raw_artifact_retained = ($ParseStatus -ne 'missing')
    }
}

function Convert-PrivateJsonArtifact {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$DestinationPath,
        [Parameter(Mandatory = $true)][hashtable]$Context,
        [string]$ArtifactKind = 'command_json'
    )

    $payload = $null
    if (-not (Test-Path -LiteralPath $SourcePath)) {
        $payload = New-SafeJsonPlaceholder -ArtifactKind $ArtifactKind -ParseStatus 'missing'
    } else {
        try {
            $raw = Get-Content -LiteralPath $SourcePath -Raw
            if ([string]::IsNullOrWhiteSpace($raw)) { throw 'empty' }
            $parsed = $raw | ConvertFrom-Json -ErrorAction Stop
            $payload = ConvertTo-ShareableArtifactValue -Value $parsed -RunRoot $Context.RunRoot -PrivateRoot $Context.PrivateRoot -RepoRoot $Context.RepoRoot -Resource $Context.Resource -Connection $Context.Connection -SensitiveValues $Context.SensitiveValues
        } catch {
            $payload = New-SafeJsonPlaceholder -ArtifactKind $ArtifactKind -ParseStatus 'failed'
        }
    }
    $parent = Split-Path -Parent $DestinationPath
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    Write-Utf8NoBomText -LiteralPath $DestinationPath -Text ($payload | ConvertTo-Json -Depth 20)
}

function Convert-PrivateJsonLinesArtifact {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$DestinationPath,
        [Parameter(Mandatory = $true)][hashtable]$Context
    )

    $lines = [System.Collections.Generic.List[string]]::new()
    if (Test-Path -LiteralPath $SourcePath) {
        foreach ($line in Get-Content -LiteralPath $SourcePath) {
            if ([string]::IsNullOrWhiteSpace($line)) { continue }
            try {
                $parsed = $line | ConvertFrom-Json -ErrorAction Stop
                $safe = ConvertTo-ShareableArtifactValue -Value $parsed -RunRoot $Context.RunRoot -PrivateRoot $Context.PrivateRoot -RepoRoot $Context.RepoRoot -Resource $Context.Resource -Connection $Context.Connection -SensitiveValues $Context.SensitiveValues
            } catch {
                $safe = [ordered]@{ event = 'artifact_redaction'; artifact_available = $false; parse_status = 'failed'; private_raw_artifact_retained = $true }
            }
            $lines.Add(($safe | ConvertTo-Json -Compress -Depth 20)) | Out-Null
        }
    }
    $parent = Split-Path -Parent $DestinationPath
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    Write-Utf8NoBomLines -LiteralPath $DestinationPath -Lines @($lines.ToArray())
}

function New-CsvEvidence {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$DestinationPath,
        [AllowNull()]$Case
    )

    try {
        if (-not (Test-Path -LiteralPath $SourcePath)) { return $null }
        $rows = @(Import-Csv -LiteralPath $SourcePath -ErrorAction Stop)
        $header = @(Get-Content -LiteralPath $SourcePath -TotalCount 1)
        $required = @('timestamp_utc_plus_8', 'measurement_type', 'value', 'unit', 'trigger_metadata', 'resource_id', 'status')
        $columns = if ($header.Count -eq 0) { @() } else { @($header[0] -split ',') }
        $evidence = [ordered]@{
            artifact_kind = 'acquisition_csv_evidence'
            artifact_available = $true
            parse_status = 'parsed'
            full_csv_private = $true
            private_raw_artifact_retained = $true
            header_valid = (@($required | Where-Object { $_ -notin $columns }).Count -eq 0)
            row_count = $rows.Count
            expected_row_count = if ($null -eq $Case) { $null } else { $Case.expected_captured }
            measurement_type = if ($rows.Count -eq 0) { $null } else { $rows[0].measurement_type }
            unit = if ($rows.Count -eq 0) { $null } else { $rows[0].unit }
            value_omitted = $true
            trigger_metadata_omitted = $true
        }
    } catch {
        $evidence = New-SafeJsonPlaceholder -ArtifactKind 'acquisition_csv_evidence' -ParseStatus 'failed'
        $evidence.full_csv_private = $true
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $DestinationPath) | Out-Null
    Write-Utf8NoBomText -LiteralPath $DestinationPath -Text ($evidence | ConvertTo-Json -Depth 10)
    return $evidence
}

function Copy-ShareableArtifactTree {
    param([Parameter(Mandatory = $true)][hashtable]$Context)

    $privateReportPath = [System.IO.Path]::GetFullPath((Join-Path $Context.PrivateRoot 'report.json'))
    $privateSummaryPath = [System.IO.Path]::GetFullPath((Join-Path $Context.PrivateRoot 'summary.md'))
    foreach ($file in Get-ChildItem -LiteralPath $Context.PrivateRoot -File -Recurse) {
        if ($file.FullName -ieq $privateReportPath -or $file.FullName -ieq $privateSummaryPath) { continue }
        $relative = Get-PortableRelativePath -BasePath $Context.PrivateRoot -Path $file.FullName
        if ($file.Extension -ieq '.csv') { continue }
        $destination = Join-Path $Context.ShareableRoot $relative
        switch ($file.Extension.ToLowerInvariant()) {
            '.json' { Convert-PrivateJsonArtifact -SourcePath $file.FullName -DestinationPath $destination -Context $Context }
            '.jsonl' { Convert-PrivateJsonLinesArtifact -SourcePath $file.FullName -DestinationPath $destination -Context $Context }
            { $_ -in @('.txt', '.md', '.log') } {
                New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
                $raw = Get-Content -LiteralPath $file.FullName -Raw
                $safe = Protect-ArtifactText -Text $raw -Resource $Context.Resource -RepoRoot $Context.RepoRoot -PrivateRoot $Context.PrivateRoot -SensitiveValues $Context.SensitiveValues
                Write-Utf8NoBomText -LiteralPath $destination -Text $safe
            }
            default {
                # Unknown formats stay private. Raw bytes are never copied as a fallback.
            }
        }
    }
}

function Add-ShareableCsvEvidence {
    param(
        [Parameter(Mandatory = $true)]$ShareableReport,
        [Parameter(Mandatory = $true)]$PrivateReport,
        [Parameter(Mandatory = $true)][hashtable]$Context
    )

    for ($index = 0; $index -lt @($PrivateReport.cases).Count; $index++) {
        $privateCase = @($PrivateReport.cases)[$index]
        $shareableCase = @($ShareableReport.cases)[$index]
        if ($null -eq $privateCase.csv -or -not (Test-Path -LiteralPath ([string]$privateCase.csv))) { continue }
        $caseRelative = Get-PortableRelativePath -BasePath $Context.PrivateRoot -Path (Split-Path -Parent ([string]$privateCase.csv))
        $evidencePath = Join-Path (Join-Path $Context.ShareableRoot $caseRelative) 'csv-evidence.json'
        [void](New-CsvEvidence -SourcePath ([string]$privateCase.csv) -DestinationPath $evidencePath -Case $privateCase)
        $shareableCase['csv'] = '<private-local-path>'
        $shareableCase['csv_evidence'] = ('shareable/' + (Get-PortableRelativePath -BasePath $Context.ShareableRoot -Path $evidencePath).Replace('\', '/'))
        $shareableCase['csv_artifact_visibility'] = 'private'
    }
}

function New-ShareableSummaryLines {
    param([Parameter(Mandatory = $true)]$Report)

    $lines = @(
        '# Live CLI Check Shareable Summary', '',
        "- Target: $($Report.target)",
        "- Model ID: $($Report.model_id)",
        "- Expected model: $($Report.expected_model)",
        "- Connection: $($Report.connection)",
        "- VISA library/backend: $($Report.backend)",
        "- Suite: $($Report.suite)",
        "- Status: $($Report.status)",
        "- Package version: $($Report.package_version)",
        "- Git HEAD: $($Report.git_head)",
        "- Validation mode: $($Report.validation_mode)",
        "- Plan only: $($Report.plan_only)",
        "- Live executed: $($Report.live_executed)",
        "- Resource: $($Report.resource)",
        '- Candidate evidence only: true',
        '- Promotes product support: false', '',
        '## Cases'
    )
    if (@($Report.cases).Count -eq 0) {
        $lines += '- No live cases executed.'
    } else {
        foreach ($case in @($Report.cases)) {
            $lines += "- $($case.name): status=$($case.status) expected_captured=$($case.expected_captured) captured=$($case.captured) errors=$($case.errors) csv_rows=$($case.csv_rows) measurement_type=$($case.measurement_type) unit=$($case.unit)"
            foreach ($failure in @($case.failure_reasons)) { $lines += "  - Failure: $failure" }
        }
    }
    $lines += @('', '## Shareable Artifacts', '- Report: shareable/report.json', '- Summary: shareable/summary.md')
    return $lines
}

function Write-MinimalShareableFailure {
    param(
        [Parameter(Mandatory = $true)][string]$ShareableRoot,
        [Parameter(Mandatory = $true)][string]$Status
    )

    New-Item -ItemType Directory -Force -Path $ShareableRoot | Out-Null
    $report = [ordered]@{
        schema_version = '1.1'
        kind = 'meters_tool_live_validation'
        artifact_visibility = 'shareable'
        candidate_evidence_only = $true
        promotes_live_support = $false
        private_raw_artifacts_retained = $true
        redaction_applied = $true
        redaction_version = 1
        status = $Status
        failure = 'Shareable artifact generation failed.'
        artifact_paths = [ordered]@{ output_dir = 'shareable'; report = 'shareable/report.json'; summary = 'shareable/summary.md' }
    }
    Write-Utf8NoBomText -LiteralPath (Join-Path $ShareableRoot 'report.json') -Text ($report | ConvertTo-Json -Depth 8)
    Write-Utf8NoBomLines -LiteralPath (Join-Path $ShareableRoot 'summary.md') -Lines @('# Live CLI Check Shareable Summary', '', '- Status: artifact_generation_failed', '- Private raw artifacts retained: true')
}

function New-ShareableArtifactSet {
    param(
        [Parameter(Mandatory = $true)]$PrivateReport,
        [Parameter(Mandatory = $true)][string]$RunRoot,
        [Parameter(Mandatory = $true)][string]$PrivateRoot,
        [Parameter(Mandatory = $true)][string]$ShareableRoot,
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$Resource,
        [Parameter(Mandatory = $true)][string]$Connection
    )

    $context = @{
        RunRoot = $RunRoot
        PrivateRoot = $PrivateRoot
        ShareableRoot = $ShareableRoot
        RepoRoot = $RepoRoot
        Resource = $Resource
        Connection = $Connection
        SensitiveValues = @(Get-DistinctiveSensitiveTokens -Resource $Resource)
    }
    Copy-ShareableArtifactTree -Context $context
    $report = ConvertTo-ShareableArtifactValue -Value $PrivateReport -RunRoot $RunRoot -PrivateRoot $PrivateRoot -RepoRoot $RepoRoot -Resource $Resource -Connection $Connection -SensitiveValues $context.SensitiveValues
    $report.schema_version = '1.1'
    $report.kind = 'meters_tool_live_validation'
    $report.artifact_visibility = 'shareable'
    $report.candidate_evidence_only = $true
    $report.promotes_live_support = $false
    $report.private_raw_artifacts_retained = $true
    $report.redaction_applied = $true
    $report.redaction_version = 1
    $report.output_dir = 'shareable'
    $report.artifact_paths = [ordered]@{ output_dir = 'shareable'; report = 'shareable/report.json'; summary = 'shareable/summary.md' }
    Add-ShareableCsvEvidence -ShareableReport $report -PrivateReport $PrivateReport -Context $context
    Write-Utf8NoBomText -LiteralPath (Join-Path $ShareableRoot 'report.json') -Text ($report | ConvertTo-Json -Depth 20)
    Write-Utf8NoBomLines -LiteralPath (Join-Path $ShareableRoot 'summary.md') -Lines (New-ShareableSummaryLines -Report $report)
    return $report
}
