from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from meters_tool_webui._desktop import select_directory_with_dialog


@pytest.mark.parametrize("stdout", (r"C:\Meter Data", ""))
def test_csv_folder_picker_suppresses_powershell_console(stdout: str) -> None:
    with patch.object(subprocess, "CREATE_NO_WINDOW", 0x08000000, create=True), patch(
        "meters_tool_webui._desktop.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, stdout=stdout, stderr=""),
    ) as run_mock:
        selected = select_directory_with_dialog()

    assert selected == (Path(stdout) if stdout else None)
    run_mock.assert_called_once()
    args, kwargs = run_mock.call_args
    assert args[0][:4] == ["powershell.exe", "-NoProfile", "-STA", "-Command"]
    assert "BrowseForFolder" in args[0][4]
    assert kwargs == {
        "check": False,
        "capture_output": True,
        "text": True,
        "creationflags": 0x08000000,
    }
