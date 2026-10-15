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



def test_invoke_captured_command_memory_mode_keeps_output_off_disk(tmp_path: Path):
    if POWERSHELL is None:
        pytest.skip("powershell.exe is required")
    if not PYTHON.exists():
        pytest.skip("venv Python is required")
    stdout_path = tmp_path / "should_not_exist.stdout.txt"
    stderr_path = tmp_path / "should_not_exist.stderr.txt"
    child_code = 'import sys; print("test-json"); sys.stderr.write("test-error")'
    command = (
        f"$RepoRoot = {ps_quote(REPO_ROOT)}; "
        f". {ps_quote(HELPER)}; "
        "$r = Invoke-CapturedCommand -Name 'memory' "
        f"-FilePath {ps_quote(PYTHON)} -Arguments @('-c', {ps_quote(child_code)}) "
        f"-StdOutPath {ps_quote(stdout_path)} -StdErrPath {ps_quote(stderr_path)} "
        "-CaptureInMemory; $r | ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-Command", command],
        cwd=REPO_ROOT, text=True, capture_output=True, check=False, timeout=10,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["stdout"] is None and payload["stderr"] is None
    assert payload["stdout_text"].strip() == "test-json"
    assert payload["stderr_text"] == "test-error"
    assert not stdout_path.exists()
    assert not stderr_path.exists()


@pytest.mark.parametrize("count", [0, 1, 2])
def test_minimal_redaction_preserves_json_array_shapes(tmp_path: Path, count: int):
    if POWERSHELL is None:
        pytest.skip("powershell.exe is required")
    privacy = REPO_ROOT / "scripts" / "_artifact_privacy.ps1"
    source = (
        "[ordered]@{ cases=@(); dry_runs=@(); scpi_diagnostics=@(); "
        "commands=@([ordered]@{arguments=@('--test-flag','value')}) }"
    )
    command = (
        f"$RepoRoot={ps_quote(REPO_ROOT)}; "
        f". {ps_quote(HELPER)}; . {ps_quote(privacy)}; "
        f"$r={source}; "
        f"for ($n=0; $n -lt {count}; $n++) {{ "
        "$r.dry_runs += [ordered]@{ name=('run' + $n); "
        "plan=[ordered]@{ read_path='READ?'; cleanup_steps=@('close') } } "
        "}; "
        "$minimal=ConvertTo-MinimalEvidenceValue -Value $r; "
        "$safe=ConvertTo-ShareableArtifactValue -Value $minimal "
        f"-RunRoot {ps_quote(tmp_path)} -PrivateRoot {ps_quote(tmp_path)} "
        f"-RepoRoot {ps_quote(REPO_ROOT)} -Resource 'SIM::34461A' -Connection 'usb'; "
        "ConvertTo-Json -InputObject $safe -Compress -Depth 20"
    )
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-Command", command],
        cwd=REPO_ROOT, text=True, capture_output=True, check=False, timeout=15,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["cases"] == []
    assert payload["scpi_diagnostics"] == []
    assert isinstance(payload["commands"], list)
    assert payload["commands"][0]["arguments"] == ["--test-flag", "value"]
    assert isinstance(payload["dry_runs"], list)
    assert len(payload["dry_runs"]) == count
    assert all(
        isinstance(item["plan"]["cleanup_steps"], list)
        and item["plan"]["cleanup_steps"] == ["close"]
        for item in payload["dry_runs"]
    )
