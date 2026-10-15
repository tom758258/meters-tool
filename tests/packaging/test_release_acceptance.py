from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_ACCEPTANCE = REPO_ROOT / "scripts" / "release-acceptance.ps1"
BUILD_RELEASE = REPO_ROOT / "scripts" / "build_release.ps1"
BUILD_DESKTOP = REPO_ROOT / "scripts" / "build_desktop.ps1"
BUILD_DESKTOP_BACKEND = REPO_ROOT / "scripts" / "build_desktop_backend.ps1"
BUILD_WINDOWS_BUNDLE = REPO_ROOT / "scripts" / "build_windows_bundle.ps1"
WINDOWS_SPEC = REPO_ROOT / "scripts" / "meters-tool-windows.spec"
DESKTOP_MAIN = REPO_ROOT / "desktop" / "main.cjs"
DESKTOP_PACKAGE = REPO_ROOT / "desktop" / "package.json"
TESTS_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "tests.yml"
OLD_CLI_BUILDER = REPO_ROOT / "scripts" / "build_cli_exe.ps1"
OLD_WEBUI_BUILDER = REPO_ROOT / "scripts" / "build_webui_exe.ps1"
OLD_RELEASE_CHECK = REPO_ROOT / "scripts" / "release-cli-check.ps1"


def release_acceptance_text() -> str:
    return RELEASE_ACCEPTANCE.read_text(encoding="utf-8-sig")


def test_release_acceptance_replaces_cli_release_check():
    assert RELEASE_ACCEPTANCE.exists()
    assert not OLD_RELEASE_CHECK.exists()


def test_release_acceptance_keeps_target_and_package_version_guards():
    script = release_acceptance_text()

    for contract in (
        '[string]$Target = "keysight-34461a"',
        "$resolvedTarget = Resolve-ValidationTarget -Target $Target",
        "$targetModel = Get-TargetCliModel -ResolvedTarget $resolvedTarget",
        '$Resource = "SIM::$targetModel"',
        "Release acceptance requires simulator resource",
        '$packageName -ne "meters-tool"',
        "$Release = $packageVersion",
        "Release $Release does not match package version $packageVersion",
    ):
        assert contract in script


def test_release_acceptance_checks_tools_lock_and_clean_git_tree():
    script = release_acceptance_text()

    for contract in (
        'Get-Command -Name "git"',
        'Get-Command -Name "uv"',
        'Get-Command -Name "node"',
        'Get-Command -Name "npm.cmd"',
        "Project Python executable not found",
        '$script:currentStep = "node_version"',
        '$script:currentStep = "npm_version"',
        '@("-m", "PyInstaller", "--version")',
        '@("lock", "--check")',
        '@("-C", $RepoRoot, "status", "--porcelain")',
        "Git working tree must be clean before release acceptance.",
    ):
        assert contract in script


def test_release_acceptance_runs_complete_no_hardware_suite():
    script = release_acceptance_text()

    assert '$script:currentStep = "pytest_no_hardware"' in script
    assert '"-m", "pytest", "tests"' in script
    assert '"--ignore=tests\\cli\\test_cli_wrappers.py"' not in script
    assert '"--basetemp", (Join-Path $runDir "pytest-no-hardware")' in script
    assert "pytest_metadata_docs" not in script


def test_release_acceptance_isolates_python_process_environment():
    script = release_acceptance_text()
    isolation_start = script.index('$env:PYTHONNOUSERSITE = "1"')
    pytest_start = script.index('$script:currentStep = "pytest_no_hardware"')
    isolation_block = script[isolation_start:pytest_start]

    assert "SetEnvironmentVariable(" in isolation_block
    assert "$null" in isolation_block
    assert "[EnvironmentVariableTarget]::Process" in isolation_block
    for variable in (
        "PYTHONPATH",
        "PYTHONHOME",
        "VIRTUAL_ENV",
        "UV_INTERNAL__PYTHONHOME",
        "UV_PROJECT_ENVIRONMENT",
    ):
        assert f'"{variable}"' in isolation_block


def test_release_acceptance_builds_release_once_without_direct_distribution_build():
    script = release_acceptance_text()

    assert script.count("build_release.ps1") == 1
    assert '@("-m", "build"' not in script


def test_release_acceptance_validates_final_artifacts_and_checksums():
    script = release_acceptance_text()
    artifact_smoke_start = script.index("function Invoke-ArtifactSmoke")
    artifact_smoke_end = script.index("\ntry {", artifact_smoke_start)
    artifact_smoke = script[artifact_smoke_start:artifact_smoke_end]

    for contract in (
        '"meters-tool-$packageVersion-windows-x64.zip"',
        '"meters_tool-$packageVersion-py3-none-any.whl"',
        '"meters_tool-$packageVersion.tar.gz"',
        '"checksums.txt"',
        "$releaseEntries.Count -ne $expectedReleaseNames.Count",
        "$checksumLines.Count -ne $expectedArtifactNames.Count",
        "Get-FileHash -Algorithm SHA256",
        "SHA-256 mismatch",
        'Invoke-ArtifactSmoke -Label "wheel"',
        'Invoke-ArtifactSmoke -Label "sdist"',
        "import meters_tool_core, meters_tool_cli, meters_tool_webui",
        "from importlib.resources import files",
        "'index.html'",
        "'styles.css'",
        "'app.js'",
        "static_root.joinpath(name).is_file()",
        "assert not missing_static",
        "Scripts\\meters-tool.exe",
        "Scripts\\meters-tool-webui.exe",
        "Scripts\\meters-tool-webui-launcher.exe",
        "Path(sys.argv[1]).is_file()",
        '${Label}_launcher_entry_point',
    ):
        assert contract in script

    for contract in (
        "cli_help_root = files('meters_tool_cli').joinpath('help')",
        "required_cli_help = ('cli.html', 'cli.zh-TW.html', "
        "'supported-models.html', 'supported-models.zh-TW.html', 'help.css')",
        "missing_cli_help = [name for name in required_cli_help "
        "if not cli_help_root.joinpath(name).is_file()]",
        "assert not missing_cli_help",
        "webui_help_root = static_root.joinpath('help')",
        "required_webui_help = ('webui.html', 'webui.zh-TW.html', "
        "'supported-models.html', 'supported-models.zh-TW.html', 'help.css')",
        "missing_webui_help = [name for name in required_webui_help "
        "if not webui_help_root.joinpath(name).is_file()]",
        "assert not missing_webui_help",
    ):
        assert contract in artifact_smoke

    assert "Meters-Tool-Desktop-$packageVersion-portable.exe" not in script
    assert "foreach ($artifact in @($windowsBundleZip, $wheel, $sdist))" in script


def test_release_acceptance_runs_minimal_standalone_smokes_and_existing_preflight():
    script = release_acceptance_text()

    for contract in (
        '$script:currentStep = "standalone_cli_version"',
        '$script:currentStep = "standalone_cli_help"',
        '$script:currentStep = "standalone_cli_simulator"',
        '$script:currentStep = "standalone_cli_manifest"',
        '@("manifest", "--json")',
        '"tool_manifest"',
        '"meters"',
        '"v2-only"',
        '"--measurement", "current-dc"',
        '"--trigger-mode", "immediate"',
        '"--max-samples", "1"',
        '"--simulate"',
        '"--status-format", "jsonl"',
        'Where-Object { $_.event -eq "summary" }',
        "Test-CsvRowCount",
        '$script:currentStep = "launcher_self_test"',
        '@("--self-test")',
        ".\\scripts\\preflight-cli.ps1",
        ".\\scripts\\live-cli-check.ps1",
        '"-Suite"',
        '"minimal"',
        '"-PlanOnly"',
        '"-SkipPreflight"',
    ):
        assert contract in script


def test_release_acceptance_report_uses_project_release_semantics():
    script = release_acceptance_text()

    for contract in (
        "schema_version = 1",
        'kind = "release_acceptance"',
        'name = "Meters Tool Release Acceptance"',
        'validation_mode = "release_acceptance_no_hardware"',
        "failed_step = $failedStep",
        "error = $failureMessage",
        "final_release_dir = $relativeFinalReleaseDir",
        "windows_bundle_zip = if ($null -ne $windowsBundleZip)",
        "desktop_portable_exe = $null",
        "checksum_validation = $checksumValidation",
        "standalone_cli_smoke = $standaloneCliSmoke",
        "launcher_self_test = $launcherSelfTest",
        "artifacts = $artifactItems",
        "commands = $commandItems",
    ):
        assert contract in script

    assert "cli_exe = if" not in script
    assert "webui_launcher_exe = if" not in script


def test_release_acceptance_extracts_and_validates_unified_windows_bundle():
    script = release_acceptance_text()

    for contract in (
        '$script:currentStep = "extract_windows_bundle"',
        "Expand-Archive",
        '"meters-tool-$packageVersion"',
        '"Meters Tool.exe"',
        '"meters-tool.exe"',
        '"meters-tool-webui-launcher.exe"',
        '"meters-tool-webui-host.exe"',
        '"_internal"',
        '"resources"',
        "$bundleRootEntries.Count -ne 1",
        "exactly one _internal directory",
        "_internal directory must be at the application root",
        'Join-Path $extractedBundleDir "resources\\backend"',
        'Filter "*-portable.exe"',
    ):
        assert contract in script

    assert "$expectedBundleEntryNames" not in script


def test_release_acceptance_keeps_output_under_tmp_tests():
    script = release_acceptance_text()

    assert '[string]$OutputRoot = ".tmp_tests\\release_acceptance"' in script
    assert "Assert-PathUnderRoot" in script
    assert "Only paths under .tmp_tests are allowed for release output" in script


def test_release_acceptance_rechecks_final_working_tree_hygiene():
    script = release_acceptance_text()
    plan_only_start = script.index('$script:currentStep = "live_cli_plan_only"')
    final_head_start = script.index('$script:currentStep = "git_head_final"')
    final_diff_start = script.index('$script:currentStep = "git_diff_check_final"')
    final_clean_start = script.index('$script:currentStep = "git_clean_final"')
    catch_start = script.index("} catch {", final_head_start)
    final_block = script[final_diff_start:catch_start]

    assert plan_only_start < final_diff_start < final_clean_start < final_head_start
    assert '@("-C", $RepoRoot, "rev-parse", "HEAD")' in final_block
    assert script.count('@("-C", $RepoRoot, "rev-parse", "HEAD")') == 2
    assert "$finalGitHead -cne $gitHead" in final_block
    assert "Git HEAD changed during release acceptance." in final_block
    assert '@("-C", $RepoRoot, "diff", "--check")' in final_block
    assert '@("-C", $RepoRoot, "status", "--porcelain")' in final_block
    assert script.count('@("-C", $RepoRoot, "status", "--porcelain")') == 2
    assert "Git working tree must remain clean after release acceptance." in final_block


def test_release_build_passes_one_source_snapshot_to_desktop_builder_only():
    script = BUILD_RELEASE.read_text(encoding="utf-8-sig")

    assert '$sourceRoot = Join-Path $buildRoot "source"' in script
    assert script.count("-SourceRoot $sourceRoot") == 1
    desktop_invocation = next(
        line for line in script.splitlines() if "build_desktop.ps1" in line
    )
    assert "-SourceRoot $sourceRoot" in desktop_invocation
    assert "build_windows_bundle.ps1" not in script
    assert r'Join-Path $sourceRoot "dist\desktop\win-unpacked"' in script
    assert r'Join-Path $sourceRoot "desktop\package.json"' in script
    assert "Desktop package version" in script
    assert "does not match release version" in script
    assert "build_cli_exe.ps1" not in script
    assert "build_webui_exe.ps1" not in script


def test_windows_bundle_builder_and_spec_define_shared_onedir_contract():
    builder = BUILD_WINDOWS_BUNDLE.read_text(encoding="utf-8-sig")
    spec = WINDOWS_SPEC.read_text(encoding="utf-8-sig")

    assert BUILD_WINDOWS_BUNDLE.exists()
    assert WINDOWS_SPEC.exists()
    assert not OLD_CLI_BUILDER.exists()
    assert not OLD_WEBUI_BUILDER.exists()

    for contract in (
        "[string]$SourceRoot",
        "$sourceRootFull = $repoFull",
        "SourceRoot directory not found",
        "SourceRoot must stay under the repository",
        "DistPath must stay under the repository",
        "WorkRoot must stay under the repository",
        "meters-tool-windows.spec",
        "--source-root $sourceRootFull",
        '$sourcePath = Join-Path $sourceRootFull "src"',
        "$env:PYTHONPATH = $sourcePath",
        "$env:PYTHONPATH = $previousPythonPath",
    ):
        assert contract in builder

    assert spec.count("Analysis(") == 3
    assert spec.count("PYZ(") == 3
    assert spec.count("EXE(") == 3
    assert spec.count("COLLECT(") == 1
    assert "MERGE(" not in spec
    assert 'name="meters-tool"' in spec
    assert 'name="meters-tool-webui-launcher"' in spec
    assert 'name="meters-tool-webui-host"' in spec
    assert 'source_path / "meters_tool_webui" / "_desktop_host.py"' in spec
    assert "console=True" in spec
    assert "console=False" in spec
    assert spec.count('contents_directory="_internal"') == 3
    assert 'application_icon = source_root / "desktop" / "assets" / "meters-icon.ico"' in spec
    assert spec.count("icon=str(application_icon)") == 2
    cli_exe = spec[spec.index("cli_exe = EXE(") : spec.index("launcher_analysis = Analysis(")]
    launcher_exe = spec[
        spec.index("launcher_exe = EXE(") : spec.index("host_analysis = Analysis(")
    ]
    host_exe = spec[spec.index("host_exe = EXE(") : spec.index("bundle = COLLECT(")]
    assert "icon=str(application_icon)" in cli_exe
    assert "icon=str(application_icon)" in launcher_exe
    assert "icon=" not in host_exe
    launcher_analysis = spec[
        spec.index("launcher_analysis = Analysis(") : spec.index("launcher_pyz = PYZ(")
    ]
    host_analysis = spec[
        spec.index("host_analysis = Analysis(") : spec.index("host_pyz = PYZ(")
    ]
    assert '(str(application_icon), "meters_tool_webui/assets")' in launcher_analysis
    assert "str(application_icon)" not in host_analysis
    assert '"meters_tool_webui/static"' in spec
    assert '"_internal/meters_tool_webui/static"' not in spec

    cli_analysis = spec[spec.index("cli_analysis = Analysis(") : spec.index("cli_pyz = PYZ(")]
    assert 'source_path / "meters_tool_cli" / "help"' in cli_analysis
    assert '"meters_tool_cli/help"' in cli_analysis
    assert '"meters_tool_cli/help"' not in launcher_analysis
    assert '"meters_tool_cli/help"' not in host_analysis

    collect = spec[spec.index("bundle = COLLECT(") :]
    for entry in (
        "cli_exe",
        "launcher_exe",
        "host_exe",
        "cli_analysis.datas",
        "cli_analysis.binaries",
        "host_analysis.binaries",
        "host_analysis.datas",
    ):
        assert entry in collect


def test_release_build_creates_zip_and_hashes_expected_artifact_set():
    script = BUILD_RELEASE.read_text(encoding="utf-8-sig")

    for contract in (
        '"meters-tool-$Version-windows-x64.zip"',
        '"meters_tool-$Version-py3-none-any.whl"',
        '"meters_tool-$Version.tar.gz"',
        "Compress-Archive",
        '$versionedBundleDir = Join-Path $archiveRoot "meters-tool-$Version"',
        "$releaseEntries.Count -ne $expectedArtifactNames.Count",
        "foreach ($artifactName in ($expectedArtifactNames | Sort-Object))",
    ):
        assert contract in script

    assert "Meters-Tool-Desktop-$Version-portable.exe" not in script


def test_desktop_build_assembles_shared_onedir_into_electron_directory():
    script = BUILD_DESKTOP.read_text(encoding="utf-8-sig")
    main = DESKTOP_MAIN.read_text(encoding="utf-8-sig")
    package = DESKTOP_PACKAGE.read_text(encoding="utf-8-sig")

    assert "[string]$SourceRoot" in script
    assert not BUILD_DESKTOP_BACKEND.exists()
    assert "build_windows_bundle.ps1" in script
    assert "-SourceRoot $sourceRootFull" in script
    assert '"win-unpacked"' in script
    assert '"meters-tool-webui-host.exe"' in script
    assert '"resources\\backend"' in script
    assert "exactly one _internal directory" in script
    assert "desktop-backend-dist" not in script
    assert "pyinstaller-desktop-backend" not in script

    assert 'path.dirname(process.execPath), "meters-tool-webui-host.exe"' in main
    assert "process.resourcesPath" not in main
    assert '"dist:win": "electron-builder --dir --win --x64"' in package
    assert '"icon": "assets/meters-icon.ico"' in package
    assert '"extraResources"' not in package
    assert '"portable"' not in package
    assert (REPO_ROOT / "desktop" / "assets" / "meters-icon.ico").is_file()
    assert (REPO_ROOT / "desktop" / "assets" / "meters-icon.png").is_file()


def test_desktop_native_theme_tracks_the_host_scoped_webui_cookie():
    main = DESKTOP_MAIN.read_text(encoding="utf-8-sig")

    assert 'const THEME_COOKIE_NAME = "meters-tool.webui.theme";' in main
    assert 'const THEME_COOKIE_URL = "http://127.0.0.1/";' in main
    assert 'new Set(["system", "light", "dark"])' in main
    assert "THEME_PREFERENCES.has(preference) ? preference : \"system\"" in main
    assert 'let preference = "system";' in main
    assert 'nativeTheme.themeSource = "system";' in main
    assert 'cookies.on("changed", (_event, cookie) =>' in main
    assert "cookie.name !== THEME_COOKIE_NAME" in main
    assert "cookie.domain" not in main
    assert "syncNativeThemePreference(cookies)" in main
    assert "await initialThemeSync;" in main

    for setting in (
        "nodeIntegration: false",
        "contextIsolation: true",
        "sandbox: true",
        "webSecurity: true",
    ):
        assert setting in main
    for unsupported_window_option in (
        "titleBarStyle",
        "titleBarOverlay",
        "frame: false",
        "preload:",
    ):
        assert unsupported_window_option not in main


def test_desktop_help_theme_bridge_uses_query_override_in_external_browser():
    main = DESKTOP_MAIN.read_text(encoding="utf-8-sig")

    assert 'target.origin === allowedOrigin && target.pathname.startsWith("/help/")' in main
    assert "nativeTheme.themeSource" in main
    assert "THEME_PREFERENCES.has(nativeTheme.themeSource)" in main
    assert 'searchParams.set("theme"' in main
    assert "shell.openExternal(target.href)" in main
    assert "shell.openExternal(url)" not in main
    assert 'return { action: "deny" }' in main


def test_python_windows_matrix_does_not_build_desktop_or_release():
    workflow = TESTS_WORKFLOW.read_text(encoding="utf-8")
    windows_matrix = workflow.split("  pytest-windows:", 1)[1].split("  windows-validation:", 1)[0]
    assert "build_desktop.ps1" not in windows_matrix
    assert "build_release.ps1" not in windows_matrix


def test_desktop_build_validates_help_artifact_layout():
    script = BUILD_DESKTOP.read_text(encoding="utf-8-sig")

    assert 'Join-Path $DesktopDirectory "_internal\\meters_tool_cli\\help"' in script
    assert 'Join-Path $DesktopDirectory "_internal\\meters_tool_webui\\static\\help"' in script
    for name in ("cli.html", "cli.zh-TW.html"):
        assert name in script
    for name in ("webui.html", "webui.zh-TW.html"):
        assert name in script
    for name in ("supported-models.html", "supported-models.zh-TW.html", "help.css"):
        assert name in script
    for fragment in (
        'Join-Path $cliHelpDirectory "webui.html"',
        'Join-Path $cliHelpDirectory "webui.zh-TW.html"',
        'Join-Path $webuiHelpDirectory "cli.html"',
        'Join-Path $webuiHelpDirectory "cli.zh-TW.html"',
    ):
        assert fragment in script
    assert 'Join-Path $DesktopDirectory "meters_tool_cli\\help"' in script
    assert 'Join-Path $DesktopDirectory "meters_tool_webui\\static\\help"' in script
