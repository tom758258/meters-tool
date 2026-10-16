from __future__ import annotations

import argparse
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--source-root", required=True)
args = parser.parse_args()

source_root = Path(args.source_root).resolve()
source_path = source_root / "src"
application_icon = source_root / "desktop" / "assets" / "meters-icon.ico"

cli_analysis = Analysis(
    [str(source_path / "meters_tool_cli" / "cli.py")],
    pathex=[str(source_path)],
    binaries=[],
    datas=[
        (
            str(source_path / "meters_tool_cli" / "help"),
            "meters_tool_cli/help",
        ),
    ],
    hiddenimports=["pyvisa_py"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
cli_pyz = PYZ(cli_analysis.pure)
cli_exe = EXE(
    cli_pyz,
    cli_analysis.scripts,
    [],
    exclude_binaries=True,
    name="meters-tool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(application_icon),
    contents_directory="_internal",
)

launcher_analysis = Analysis(
    [str(source_path / "meters_tool_webui" / "launcher.py")],
    pathex=[str(source_path)],
    binaries=[],
    datas=[
        (
            str(source_path / "meters_tool_webui" / "static"),
            "meters_tool_webui/static",
        ),
        (str(application_icon), "meters_tool_webui/assets"),
    ],
    hiddenimports=["pyvisa_py"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
launcher_pyz = PYZ(launcher_analysis.pure)
launcher_exe = EXE(
    launcher_pyz,
    launcher_analysis.scripts,
    [],
    exclude_binaries=True,
    name="meters-tool-webui-launcher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(application_icon),
    contents_directory="_internal",
)

host_analysis = Analysis(
    [str(source_path / "meters_tool_webui" / "_desktop_host.py")],
    pathex=[str(source_path)],
    binaries=[],
    datas=[
        (
            str(source_path / "meters_tool_webui" / "static"),
            "meters_tool_webui/static",
        )
    ],
    hiddenimports=["pyvisa_py"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
host_pyz = PYZ(host_analysis.pure)
host_exe = EXE(
    host_pyz,
    host_analysis.scripts,
    [],
    exclude_binaries=True,
    name="meters-tool-webui-host",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory="_internal",
)

bundle = COLLECT(
    cli_exe,
    launcher_exe,
    host_exe,
    cli_analysis.binaries,
    cli_analysis.datas,
    launcher_analysis.binaries,
    launcher_analysis.datas,
    host_analysis.binaries,
    host_analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="meters-tool",
)
