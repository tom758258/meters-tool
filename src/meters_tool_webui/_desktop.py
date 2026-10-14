from __future__ import annotations

import os
from pathlib import Path
import subprocess

from meters_tool_webui._run_manager import CsvFolderSelectionUnavailable


def open_with_default_app(path: Path) -> None:
    os.startfile(path)  # type: ignore[attr-defined]


def select_directory_with_dialog() -> Path | None:
    script = (
        "$shell = New-Object -ComObject Shell.Application; "
        "$folder = $shell.BrowseForFolder(0, 'Select CSV output folder', 0); "
        "if ($folder -ne $null) { [Console]::Out.Write($folder.Self.Path) }"
    )
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-STA", "-Command", script],
            check=False,
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:  # pragma: no cover - platform/runtime dependent
        raise CsvFolderSelectionUnavailable("folder selection dialog is unavailable") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "folder selection dialog is unavailable"
        raise CsvFolderSelectionUnavailable(detail)

    selected = completed.stdout.strip()
    return Path(selected) if selected else None
