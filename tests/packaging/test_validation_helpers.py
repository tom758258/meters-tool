from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


pytestmark = pytest.mark.windows_powershell

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER = REPO_ROOT / "scripts" / "_validation_helpers.ps1"
POWERSHELL = shutil.which("powershell.exe")
PYTHON = REPO_ROOT / ".venv" / "Scripts" / "python.exe"


def ps_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def test_invoke_captured_command_drains_stdout_and_stderr_without_deadlock(
    tmp_path: Path,
):
    if POWERSHELL is None:
        pytest.skip("powershell.exe is required for PowerShell helper tests")
    if not PYTHON.exists():
        pytest.skip(f"venv Python is required for PowerShell helper tests: {PYTHON}")

    stdout_path = tmp_path / "captured.stdout.txt"
    stderr_path = tmp_path / "captured.stderr.txt"
    child_code = (
        'import sys; sys.stdout.write("stdout sentinel\\n"); '
        'sys.stderr.write("e" * (256 * 1024))'
    )
    command = (
        f"$RepoRoot = {ps_quote(REPO_ROOT)}; "
        f". {ps_quote(HELPER)}; "
        f"$result = Invoke-CapturedCommand "
        f"-Name 'pipe_deadlock' "
        f"-FilePath {ps_quote(PYTHON)} "
        f"-Arguments @('-c', {ps_quote(child_code)}) "
        f"-StdOutPath {ps_quote(stdout_path)} "
        f"-StdErrPath {ps_quote(stderr_path)} "
        f"-WorkingDirectory {ps_quote(REPO_ROOT)}; "
        "$result | ConvertTo-Json -Compress"
    )

    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-Command", command],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    captured = json.loads(result.stdout)
    assert captured["exit_code"] == 0
    assert captured["success"] is True
    assert Path(captured["stdout"]).resolve() == stdout_path.resolve()
    assert Path(captured["stderr"]).resolve() == stderr_path.resolve()
    assert stdout_path.is_file()
    assert stderr_path.is_file()
    assert stdout_path.read_text(encoding="utf-8") == "stdout sentinel\n"
    assert stderr_path.read_text(encoding="utf-8") == "e" * (256 * 1024)
