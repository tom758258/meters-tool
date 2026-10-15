from __future__ import annotations

import os
from pathlib import Path
import sys
import threading

from meters_tool_webui._run_manager import CsvFolderSelectionUnavailable


def open_with_default_app(path: Path) -> None:
    os.startfile(path)  # type: ignore[attr-defined]


_FOLDER_PICKER_LOCK = threading.Lock()


def _is_windows() -> bool:
    return sys.platform == "win32"


def _ask_directory(title: str) -> str:
    """Show a native picker owned by an invisible, topmost Tk window."""
    import tkinter as tk
    from tkinter import filedialog

    owner = tk.Tk()
    try:
        # A mapped owner (rather than a withdrawn root) makes the native
        # dialog topmost and keeps it above the browser that requested it.
        # The transparent, borderless owner does not appear on the taskbar.
        owner.withdraw()
        owner.overrideredirect(True)
        owner.attributes("-alpha", 0.0)
        owner.attributes("-topmost", True)
        owner.geometry(
            f"1x1+{owner.winfo_screenwidth() // 2}+{owner.winfo_screenheight() // 2}"
        )
        owner.deiconify()
        owner.update()
        owner.lift()
        owner.focus_force()
        return filedialog.askdirectory(parent=owner, title=title, mustexist=True)
    finally:
        owner.destroy()


def select_directory_with_dialog() -> Path | None:
    """Select a Windows folder without spawning PowerShell or a console."""
    if not _is_windows():
        raise CsvFolderSelectionUnavailable("folder selection dialog is unavailable")
    if not _FOLDER_PICKER_LOCK.acquire(blocking=False):
        raise CsvFolderSelectionUnavailable("folder selection dialog is already open")
    try:
        try:
            selected = _ask_directory("Select CSV output folder")
        except Exception as exc:  # pragma: no cover - native GUI/runtime dependent
            raise CsvFolderSelectionUnavailable("folder selection dialog is unavailable") from exc
    finally:
        _FOLDER_PICKER_LOCK.release()
    return Path(selected) if selected else None
