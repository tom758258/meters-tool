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


def run_powershell(command: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-Command", "$ErrorActionPreference='Stop'; " + command],
            cwd=REPO_ROOT, text=True, capture_output=True, check=False, timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(f"PowerShell exceeded 30s; stdout={exc.stdout!r}; stderr={exc.stderr!r}")


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
        "[Console]::Error.WriteLine('helper loaded; starting child'); "
        f"$result = Invoke-CapturedCommand "
        f"-Name 'pipe_deadlock' "
        f"-FilePath {ps_quote(PYTHON)} "
        f"-Arguments @('-c', {ps_quote(child_code)}) "
        f"-StdOutPath {ps_quote(stdout_path)} "
        f"-StdErrPath {ps_quote(stderr_path)} "
        f"-WorkingDirectory {ps_quote(REPO_ROOT)}; "
        "[Console]::Error.WriteLine('child output captured'); $result | ConvertTo-Json -Compress"
    )

    result = run_powershell(command)

    assert result.returncode == 0, result.stderr + result.stdout
    captured = json.loads(result.stdout)
    assert captured["exit_code"] == 0
    assert captured["success"] is True, captured
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
        "[Console]::Error.WriteLine('helper loaded; starting child'); "
        "$r = Invoke-CapturedCommand -Name 'memory' "
        f"-FilePath {ps_quote(PYTHON)} -Arguments @('-c', {ps_quote(child_code)}) "
        f"-StdOutPath {ps_quote(stdout_path)} -StdErrPath {ps_quote(stderr_path)} "
        "-CaptureInMemory; [Console]::Error.WriteLine('child output captured'); $r | ConvertTo-Json -Compress"
    )
    result = run_powershell(command)
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
    result = run_powershell(command)
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


@pytest.mark.parametrize("overflow", [False, True])
def test_start_helper_checks_planned_stop_and_expected_failure(tmp_path: Path, overflow: bool):
    if POWERSHELL is None or not PYTHON.exists():
        pytest.skip("Windows PowerShell and venv Python are required")
    mode_args = (
        "'--trigger-count','1','--sample-count','1001','--monitor-overflow'"
        if overflow else "'--trigger-count-infinite','--sample-count','1'"
    )
    command = (
        f"$RepoRoot={ps_quote(REPO_ROOT)}; $Python={ps_quote(PYTHON)}; "
        f". {ps_quote(HELPER)}; Add-RepoSrcToPythonPath -RepoRoot $RepoRoot; "
        "$port=Get-AvailableTcpPort; "
        "$args=@('-m','meters_tool_cli','start-trigger-record','--simulate',"
        "'--model','34460A','--resource','SIM::34460A','--trigger-mode','software-custom',"
        "'--allow-buffer-overflow-risk','--no-csv','--status-format','jsonl',"
        f"'--sw-trigger-port',[string]$port,{mode_args}); "
        "$r=Invoke-CapturedStartProcess -Name 'outcome' -Arguments $args "
        f"-StdOutPath {ps_quote(tmp_path / 'run.jsonl')} "
        f"-StdErrPath {ps_quote(tmp_path / 'run.stderr')} -OutDir {ps_quote(tmp_path)} "
        f"-TimeoutSeconds 5 -PlannedStopAfterSeconds {0 if overflow else 1} "
        f"-ExpectedExitCode {3 if overflow else 0} "
        "-SoftTriggerPort $port -SoftTriggerCount 1 -SoftTriggerRetryCount 2 "
        "-SoftTriggerRetryDelayMs 50 -InterTriggerDelayMs 0 -StopGracePeriodMs 5000 "
        "-CaptureInMemory -CaptureClientCommandsInMemory; "
        "$r | ConvertTo-Json -Depth 10 -Compress"
    )

    result = run_powershell(command)

    assert result.returncode == 0, result.stderr + result.stdout
    captured = json.loads(result.stdout)
    assert captured["success"] is True, captured
    assert captured["timed_out"] is False
    events = [json.loads(line) for line in captured["stdout_text"].splitlines()]
    summary = next(event for event in events if event["event"] == "summary")
    assert summary["ok"] is not overflow
    assert summary["overflow_detected"] is overflow
    names = [command["name"] for command in captured["client_commands"]]
    assert ("outcome_planned_stop" in names) is not overflow
    assert not any("timeout_soft_stop" in name for name in names)
