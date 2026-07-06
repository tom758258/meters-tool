from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from keysight_logger_cli.cli import FALLBACK_CLI_VERSION


REPO_ROOT = Path(__file__).resolve().parents[2]
POWERSHELL = shutil.which("powershell.exe")
PYTHON = REPO_ROOT / ".venv" / "Scripts" / "python.exe"


def require_wrapper_tools() -> None:
    if POWERSHELL is None:
        pytest.skip("powershell.exe is required for wrapper script tests")
    if not PYTHON.exists():
        pytest.skip(f"venv Python is required for wrapper script tests: {PYTHON}")


def run_wrapper(script: str, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    require_wrapper_tools()
    return subprocess.run(
        [
            POWERSHELL or "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(REPO_ROOT / script),
            *args,
        ],
        cwd=REPO_ROOT,
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
    )


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def assert_under_tmp_tests(path_text: str) -> Path:
    path = Path(path_text).resolve()
    tmp_root = (REPO_ROOT / ".tmp_tests").resolve()
    assert path == tmp_root or tmp_root in path.parents
    return path


def report_from_summary_output(output: str) -> Path:
    match = re.search(r"summary:\s*(.+)", output)
    assert match, output
    summary = Path(match.group(1).strip()).resolve()
    assert summary.exists()
    report = summary.with_name("report.json")
    assert report.exists()
    return report


def assert_command_artifacts(commands: list[dict], output_dir: Path) -> None:
    required = {
        "name",
        "command",
        "arguments",
        "exit_code",
        "duration_seconds",
        "stdout",
        "stderr",
        "success",
    }
    for command in commands:
        assert required <= command.keys()
        stdout = Path(command["stdout"]).resolve()
        stderr = Path(command["stderr"]).resolve()
        assert stdout.exists(), command
        assert stderr.exists(), command
        assert output_dir == stdout or output_dir in stdout.parents
        assert output_dir == stderr or output_dir in stderr.parents


def command_arguments(report: dict, command_name: str) -> list[str]:
    matches = [command for command in report["commands"] if command["name"] == command_name]
    assert len(matches) == 1
    return matches[0]["arguments"]


def test_release_check_rejects_mismatched_package_version():
    result = run_wrapper(
        "scripts/release-cli-check.ps1",
        "-Release",
        "1.4.0",
    )

    assert result.returncode != 0
    assert "Release 1.4.0 does not match package version 1.5.0" in (
        result.stdout + result.stderr
    )


def test_preflight_report_contract():
    output_root = REPO_ROOT / ".tmp_tests" / "pytest_wrappers" / f"preflight_{uuid4().hex}"
    result = run_wrapper(
        "scripts/preflight-cli.ps1",
        "-Target",
        "keysight-34461a",
        "-OutputRoot",
        str(output_root.relative_to(REPO_ROOT)),
    )
    assert result.returncode == 0, result.stderr + result.stdout

    output_dir = output_root / "keysight-34461a"
    report_path = output_dir / "report.json"
    summary_path = output_dir / "summary.md"
    assert report_path.exists()
    assert summary_path.exists()

    report = load_json(report_path)
    assert report["schema_version"] == 1
    assert report["target"] == "keysight-34461a"
    assert report["status"] == "passed"
    assert report["package_version"] == FALLBACK_CLI_VERSION
    assert report["validation_mode"] == "preflight"
    assert "git_head" in report
    assert set(report["artifact_paths"]) == {"output_dir", "report", "summary"}
    assert_under_tmp_tests(report["output_dir"])
    assert Path(report["output_dir"]).resolve() == output_dir.resolve()

    summary_counts = report["summary_counts"]
    for key in [
        "commands_total",
        "checks_total",
        "dry_run_cases",
        "simulate_cases",
        "soft_client_dry_runs",
        "list_resources_contract_checks",
        "mocked_pytest_checks",
    ]:
        assert key in summary_counts
    assert summary_counts["commands_total"] >= 1
    assert summary_counts["checks_total"] >= 1
    assert summary_counts["dry_run_cases"] >= 1
    assert summary_counts["simulate_cases"] >= 1

    assert_command_artifacts(report["commands"], output_dir.resolve())
    assert all(command["success"] for command in report["commands"])
    assert all(check["success"] for check in report["checks"])
    soft_cases = [
        command
        for command in report["commands"]
        if command["name"] in {"simulate_software_trigger", "simulate_software_custom"}
    ]
    assert len(soft_cases) == 2
    for command in soft_cases:
        client_names = [client["name"] for client in command["client_commands"]]
        assert any(name.endswith("_wait_ready") for name in client_names)
        assert any(name.endswith("_soft_status") for name in client_names)
        wait_ready = next(client for client in command["client_commands"] if client["name"].endswith("_wait_ready"))
        soft_status = next(client for client in command["client_commands"] if client["name"].endswith("_soft_status"))
        assert load_json(Path(wait_ready["stdout"]))["event"] == "wait-ready"
        assert load_json(Path(soft_status["stdout"]))["event"] == "status"

    measurements = set()
    read_paths = set()
    for check in report["checks"]:
        if not check["name"].startswith("dry_run_") or "jsonl" not in check:
            continue
        events = load_jsonl(Path(check["jsonl"]))
        assert len(events) == 1
        event = events[0]
        assert event["event"] == "dry_run"
        measurements.add(event["measurement_cli_name"])
        read_paths.add(event["read_path"])

    assert measurements == {
        "current-dc",
        "voltage-dc",
        "current-ac",
        "voltage-ac",
        "frequency",
        "period",
        "resistance-2w",
        "resistance-4w",
    }
    assert read_paths == {"READ?", "FETC?", "DATA:POINts? / DATA:REMove?"}

    dry_run_events = {
        event["measurement_cli_name"]: event
        for check in report["checks"]
        if check["name"].startswith("dry_run_immediate_") and "jsonl" in check
        for event in load_jsonl(Path(check["jsonl"]))
    }
    assert dry_run_events["frequency"]["measurement_unit"] == "Hz"
    assert dry_run_events["frequency"]["scpi_commands"] == [
        "CONF:FREQ",
        "FREQ:VOLT:RANG:AUTO ON",
        "FREQ:RANG:LOW 20",
        "FREQ:APER 0.1",
        "FREQ:TIM:AUTO ON",
    ]
    assert dry_run_events["period"]["measurement_unit"] == "s"
    assert dry_run_events["period"]["scpi_commands"] == [
        "CONF:PER",
        "PER:VOLT:RANG:AUTO ON",
        "PER:RANG:LOW 20",
        "PER:APER 0.1",
    ]

    summary = summary_path.read_text(encoding="utf-8")
    assert "- Status: passed" in summary
    assert "- Commands total: 29" in summary
    assert "- Checks total: 29" in summary
    assert "Measurements covered by dry-run and simulator immediate" in summary
    assert "Read paths covered: READ?, FETC?, DATA:POINts? / DATA:REMove?" in summary
    assert f"- Report: {report_path}" in summary


def test_preflight_list_targets_includes_supported_meter_targets():
    result = run_wrapper("scripts/preflight-cli.ps1", "-ListTargets")

    assert result.returncode == 0, result.stderr + result.stdout
    assert result.stdout.splitlines() == ["keysight-34461a", "keysight-34460a"]


def test_preflight_34460a_is_target_aware_without_external_positive_cases():
    output_root = REPO_ROOT / ".tmp_tests" / "pytest_wrappers" / f"preflight_34460a_{uuid4().hex}"
    result = run_wrapper(
        "scripts/preflight-cli.ps1",
        "-Target",
        "keysight-34460a",
        "-OutputRoot",
        str(output_root.relative_to(REPO_ROOT)),
    )
    assert result.returncode == 0, result.stderr + result.stdout

    output_dir = output_root / "keysight-34460a"
    report = load_json(output_dir / "report.json")
    assert report["target"] == "keysight-34460a"
    assert report["status"] == "passed"

    command_names = {command["name"] for command in report["commands"]}
    check_names = {check["name"] for check in report["checks"]}
    assert "dry_run_external_read_path" not in command_names
    assert "simulate_external" not in command_names
    assert "simulate_external_custom" not in command_names
    assert "dry_run_external_read_path" not in check_names
    assert "simulate_external" not in check_names
    assert "simulate_external_custom" not in check_names

    for command in report["commands"]:
        if command["name"].startswith(("dry_run_", "simulate_")):
            assert "--model" in command["arguments"]
            assert command["arguments"][command["arguments"].index("--model") + 1] == "34460A"

    summary = (output_dir / "summary.md").read_text(encoding="utf-8")
    assert "Read paths covered: READ?, DATA:POINts? / DATA:REMove?" in summary
    assert "external, external-custom" not in summary


def test_preflight_rejects_output_root_outside_tmp_tests():
    bad_root = REPO_ROOT / ".tmp_bad"
    assert not bad_root.exists()

    result = run_wrapper(
        "scripts/preflight-cli.ps1",
        "-Target",
        "keysight-34461a",
        "-OutputRoot",
        ".tmp_bad",
    )

    assert result.returncode != 0
    assert "Only paths under .tmp_tests are allowed" in result.stdout + result.stderr
    assert not bad_root.exists()


def test_live_plan_only_minimal_report_contract():
    result = run_wrapper(
        "scripts/live-cli-check.ps1",
        "-Target",
        "keysight-34461a",
        "-Connection",
        "usb",
        "-Resource",
        "SIM::34461A",
        "-Suite",
        "minimal",
        "-PlanOnly",
    )
    assert result.returncode == 0, result.stderr + result.stdout

    report = load_json(report_from_summary_output(result.stdout))
    assert report["schema_version"] == 1
    assert report["status"] == "planned"
    assert report["package_version"] == FALLBACK_CLI_VERSION
    assert report["validation_mode"] == "live_plan_only"
    assert "git_head" in report
    assert set(report["artifact_paths"]) == {"output_dir", "report", "summary"}
    assert report["plan_only"] is True
    assert report["live_executed"] is False
    assert report["suite"] == "minimal"
    assert report["resource"] == "SIM::34461A"
    assert report["cases"] == []
    assert report["scpi_diagnostics"] == []
    assert_under_tmp_tests(report["output_dir"])

    assert {dry_run["name"] for dry_run in report["dry_runs"]} == {
        "minimal_current_dc_immediate"
    }
    plan = report["dry_runs"][0]["plan"]
    assert plan["event"] == "dry_run"
    assert plan["trigger_mode"] == "immediate"
    assert plan["measurement_cli_name"] == "current-dc"
    assert plan["read_path"] == "READ?"
    assert plan["cleanup_steps"] == [
        "wait for worker",
        "release_to_local",
        "close",
        "cleanup_release_to_local",
        "stop_http_server",
    ]
    args = command_arguments(report, "minimal_current_dc_immediate_dry_run")
    assert args[args.index("--model") + 1] == "34461A"


def test_live_plan_only_full_report_contract():
    result = run_wrapper(
        "scripts/live-cli-check.ps1",
        "-Target",
        "keysight-34461a",
        "-Connection",
        "usb",
        "-Resource",
        "SIM::34461A",
        "-Suite",
        "full",
        "-PlanOnly",
    )
    assert result.returncode == 0, result.stderr + result.stdout

    report_path = report_from_summary_output(result.stdout)
    report = load_json(report_path)
    output_dir = Path(report["output_dir"]).resolve()
    assert report["status"] == "planned"
    assert report["plan_only"] is True
    assert report["live_executed"] is False
    assert report["cases"] == []
    assert report["scpi_diagnostics"] == []
    assert_under_tmp_tests(report["output_dir"])

    expected_names = [
        "basic_immediate_current_dc",
        "basic_immediate_voltage_dc",
        "basic_immediate_current_ac",
        "basic_immediate_voltage_ac",
        "basic_immediate_resistance_2w",
        "basic_immediate_resistance_4w",
        "basic_software_trigger",
        "basic_software_timer",
        "basic_immediate_custom",
        "basic_software_custom",
        "frequency_period_frequency_immediate",
        "frequency_period_period_immediate",
        "external_simple",
        "external_custom",
    ]
    assert {dry_run["name"] for dry_run in report["dry_runs"]} == set(expected_names)

    expected_read_paths = {
        "basic_immediate_current_dc": "READ?",
        "basic_immediate_voltage_dc": "READ?",
        "basic_immediate_current_ac": "READ?",
        "basic_immediate_voltage_ac": "READ?",
        "basic_immediate_resistance_2w": "READ?",
        "basic_immediate_resistance_4w": "READ?",
        "basic_software_trigger": "READ?",
        "basic_software_timer": "READ?",
        "basic_immediate_custom": "DATA:POINts? / DATA:REMove?",
        "basic_software_custom": "DATA:POINts? / DATA:REMove?",
        "frequency_period_frequency_immediate": "READ?",
        "frequency_period_period_immediate": "READ?",
        "external_simple": "FETC?",
        "external_custom": "DATA:POINts? / DATA:REMove?",
    }
    for dry_run in report["dry_runs"]:
        assert dry_run["plan"]["read_path"] == expected_read_paths[dry_run["name"]]
        command = dry_run["command"]
        assert command["success"]
        assert Path(command["stdout"]).resolve().exists()
        assert Path(command["stderr"]).resolve().exists()

    assert_command_artifacts(report["commands"], output_dir)


def test_live_plan_only_34460a_minimal_uses_34460a_model():
    result = run_wrapper(
        "scripts/live-cli-check.ps1",
        "-Target",
        "keysight-34460a",
        "-Connection",
        "usb",
        "-Resource",
        "SIM::34460A",
        "-Suite",
        "minimal",
        "-PlanOnly",
    )
    assert result.returncode == 0, result.stderr + result.stdout

    report = load_json(report_from_summary_output(result.stdout))
    assert report["target"] == "keysight-34460a"
    assert report["status"] == "planned"
    assert {dry_run["name"] for dry_run in report["dry_runs"]} == {
        "minimal_current_dc_immediate"
    }
    args = command_arguments(report, "minimal_current_dc_immediate_dry_run")
    assert args[args.index("--model") + 1] == "34460A"


def test_live_plan_only_34460a_basic_suite_supported_cases():
    result = run_wrapper(
        "scripts/live-cli-check.ps1",
        "-Target",
        "keysight-34460a",
        "-Connection",
        "usb",
        "-Resource",
        "SIM::34460A",
        "-Suite",
        "basic",
        "-PlanOnly",
    )
    assert result.returncode == 0, result.stderr + result.stdout

    report = load_json(report_from_summary_output(result.stdout))
    expected_names = {
        "basic_immediate_current_dc",
        "basic_immediate_voltage_dc",
        "basic_immediate_current_ac",
        "basic_immediate_voltage_ac",
        "basic_immediate_resistance_2w",
        "basic_immediate_resistance_4w",
        "basic_software_trigger",
        "basic_software_timer",
        "basic_immediate_custom",
        "basic_software_custom",
    }
    assert {dry_run["name"] for dry_run in report["dry_runs"]} == expected_names
    assert all("--model" in dry_run["command"]["arguments"] for dry_run in report["dry_runs"])
    assert all(
        dry_run["command"]["arguments"][dry_run["command"]["arguments"].index("--model") + 1] == "34460A"
        for dry_run in report["dry_runs"]
    )


def test_live_plan_only_34460a_frequency_period_suite():
    result = run_wrapper(
        "scripts/live-cli-check.ps1",
        "-Target",
        "keysight-34460a",
        "-Connection",
        "usb",
        "-Resource",
        "SIM::34460A",
        "-Suite",
        "frequency-period",
        "-PlanOnly",
    )
    assert result.returncode == 0, result.stderr + result.stdout

    report = load_json(report_from_summary_output(result.stdout))
    plans = {item["name"]: item["plan"] for item in report["dry_runs"]}
    assert set(plans) == {
        "frequency_period_frequency_immediate",
        "frequency_period_period_immediate",
    }
    assert plans["frequency_period_frequency_immediate"]["measurement_unit"] == "Hz"
    assert plans["frequency_period_period_immediate"]["measurement_unit"] == "s"
    assert all(plan["read_path"] == "READ?" for plan in plans.values())


def test_live_plan_only_34460a_full_excludes_external_cases():
    result = run_wrapper(
        "scripts/live-cli-check.ps1",
        "-Target",
        "keysight-34460a",
        "-Connection",
        "usb",
        "-Resource",
        "SIM::34460A",
        "-Suite",
        "full",
        "-PlanOnly",
    )
    assert result.returncode == 0, result.stderr + result.stdout

    report = load_json(report_from_summary_output(result.stdout))
    names = {dry_run["name"] for dry_run in report["dry_runs"]}
    assert names == {
        "basic_immediate_current_dc",
        "basic_immediate_voltage_dc",
        "basic_immediate_current_ac",
        "basic_immediate_voltage_ac",
        "basic_immediate_resistance_2w",
        "basic_immediate_resistance_4w",
        "basic_software_trigger",
        "basic_software_timer",
        "basic_immediate_custom",
        "basic_software_custom",
        "frequency_period_frequency_immediate",
        "frequency_period_period_immediate",
    }
    assert "external_simple" not in names
    assert "external_custom" not in names


def test_live_plan_only_34460a_rejects_external_suite():
    result = run_wrapper(
        "scripts/live-cli-check.ps1",
        "-Target",
        "keysight-34460a",
        "-Connection",
        "usb",
        "-Resource",
        "SIM::34460A",
        "-Suite",
        "external",
        "-PlanOnly",
    )

    assert result.returncode == 2
    assert "Suite 'external' is not supported for keysight-34460a" in (
        result.stdout + result.stderr
    )


def test_live_plan_only_frequency_period_report_contract():
    result = run_wrapper(
        "scripts/live-cli-check.ps1",
        "-Target",
        "keysight-34461a",
        "-Connection",
        "usb",
        "-Resource",
        "SIM::34461A",
        "-Suite",
        "frequency-period",
        "-PlanOnly",
    )
    assert result.returncode == 0, result.stderr + result.stdout

    report = load_json(report_from_summary_output(result.stdout))
    assert report["status"] == "planned"
    assert report["suite"] == "frequency-period"
    assert report["plan_only"] is True
    assert report["live_executed"] is False
    assert report["cases"] == []
    assert report["scpi_diagnostics"] == []
    assert not any(
        command["name"].endswith("_scpi_probe") for command in report["commands"]
    )

    plans = {item["name"]: item["plan"] for item in report["dry_runs"]}
    assert set(plans) == {
        "frequency_period_frequency_immediate",
        "frequency_period_period_immediate",
    }
    assert plans["frequency_period_frequency_immediate"]["measurement_unit"] == "Hz"
    assert plans["frequency_period_frequency_immediate"]["scpi_commands"] == [
        "CONF:FREQ",
        "FREQ:VOLT:RANG:AUTO ON",
        "FREQ:RANG:LOW 20",
        "FREQ:APER 0.1",
        "FREQ:TIM:AUTO ON",
    ]
    assert plans["frequency_period_period_immediate"]["measurement_unit"] == "s"
    assert plans["frequency_period_period_immediate"]["scpi_commands"] == [
        "CONF:PER",
        "PER:VOLT:RANG:AUTO ON",
        "PER:RANG:LOW 20",
        "PER:APER 0.1",
    ]
    assert all(plan["read_path"] == "READ?" for plan in plans.values())


def test_live_redirected_stdin_writes_confirmation_required_report():
    result = run_wrapper(
        "scripts/live-cli-check.ps1",
        "-Target",
        "keysight-34461a",
        "-Connection",
        "usb",
        "-Resource",
        "SIM::34461A",
        "-Suite",
        "minimal",
        stdin="",
    )
    assert result.returncode != 0
    assert "Live suite requires interactive Enter confirmation; stdin is redirected." in (
        result.stdout + result.stderr
    )

    report = load_json(report_from_summary_output(result.stdout + result.stderr))
    assert report["status"] == "confirmation_required"
    assert report["plan_only"] is False
    assert report["live_executed"] is False
    assert report["cases"] == []
    assert {dry_run["name"] for dry_run in report["dry_runs"]} == {
        "minimal_current_dc_immediate"
    }
