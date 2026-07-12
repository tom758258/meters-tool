from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from meters_tool_cli.cli import FALLBACK_CLI_VERSION
from meters_tool_core.models import INSTRUMENT_PROFILES, find_instrument_profile_by_model


REPO_ROOT = Path(__file__).resolve().parents[2]
POWERSHELL = shutil.which("powershell.exe")
PYTHON = REPO_ROOT / ".venv" / "Scripts" / "python.exe"


def ps_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def require_wrapper_tools() -> None:
    if POWERSHELL is None:
        pytest.skip("powershell.exe is required for wrapper script tests")
    if not PYTHON.exists():
        pytest.skip(f"venv Python is required for wrapper script tests: {PYTHON}")


def run_wrapper_path(
    script_path: Path, *args: str, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    require_wrapper_tools()
    return subprocess.run(
        [
            POWERSHELL or "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            *args,
        ],
        cwd=REPO_ROOT,
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
    )


def run_wrapper(script: str, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return run_wrapper_path(REPO_ROOT / script, *args, stdin=stdin)


def run_powershell_command(command: str) -> subprocess.CompletedProcess[str]:
    require_wrapper_tools()
    return subprocess.run(
        [POWERSHELL or "powershell.exe", "-NoProfile", "-Command", command],
        cwd=REPO_ROOT,
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
    summary = Path(match.group(1).strip())
    if not summary.is_absolute():
        summary = REPO_ROOT / summary
    summary = summary.resolve()
    assert summary.exists()
    report = summary.with_name("report.json")
    assert report.exists()
    return report


def assert_command_artifacts(commands: list[dict], output_dir: Path, run_root: Path | None = None) -> None:
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
        stdout = Path(command["stdout"])
        stderr = Path(command["stderr"])
        if run_root is not None and not stdout.is_absolute():
            stdout = run_root / stdout
        if run_root is not None and not stderr.is_absolute():
            stderr = run_root / stderr
        stdout = stdout.resolve()
        stderr = stderr.resolve()
        assert stdout.exists(), command
        assert stderr.exists(), command
        assert output_dir == stdout or output_dir in stdout.parents
        assert output_dir == stderr or output_dir in stderr.parents


def command_arguments(report: dict, command_name: str) -> list[str]:
    matches = [command for command in report["commands"] if command["name"] == command_name]
    assert len(matches) == 1
    return matches[0]["arguments"]


def test_shared_validation_target_inventory_matches_core_profiles():
    helper = REPO_ROOT / "scripts" / "_validation_helpers.ps1"
    command = (
        f". '{helper}'; "
        "$items = @(Get-SupportedTargetModelIds | ForEach-Object { "
        "[pscustomobject]@{ model_id = $_; model = Get-TargetCliModel -ResolvedTarget $_ } "
        "}); ConvertTo-Json -InputObject $items -Compress"
    )
    result = run_powershell_command(command)

    assert result.returncode == 0, result.stderr + result.stdout
    wrapper_profiles = json.loads(result.stdout)
    core_by_id = {profile.model_id: profile for profile in INSTRUMENT_PROFILES}
    wrapper_by_id = {item["model_id"]: item["model"] for item in wrapper_profiles}

    assert len(wrapper_profiles) == len(wrapper_by_id)
    assert set(wrapper_by_id) == set(core_by_id)
    assert all(model_id == model_id.lower() for model_id in wrapper_by_id)
    for model_id, model in wrapper_by_id.items():
        profile = find_instrument_profile_by_model(model_id)
        assert profile is core_by_id[model_id]
        assert model == profile.model


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("KEYSIGHT-34461A", "keysight-34461a"),
        ("Keysight-34460A", "keysight-34460a"),
    ],
)
def test_shared_validation_target_normalizes_case(value: str, expected: str):
    helper = REPO_ROOT / "scripts" / "_validation_helpers.ps1"
    result = run_powershell_command(
        f". '{helper}'; Resolve-ValidationTarget -Target '{value}'"
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert result.stdout.strip() == expected


@pytest.mark.parametrize(("argument", "message"), [("$null", "Missing target"), ("'unknown'", "Unsupported target")])
def test_shared_validation_target_rejects_missing_and_unknown(argument: str, message: str):
    helper = REPO_ROOT / "scripts" / "_validation_helpers.ps1"
    result = run_powershell_command(
        f". '{helper}'; Resolve-ValidationTarget -Target {argument}"
    )

    assert result.returncode != 0
    assert message in result.stdout + result.stderr


def test_shared_validation_target_registry_rejects_duplicates():
    helper = REPO_ROOT / "scripts" / "_validation_helpers.ps1"
    command = (
        f". '{helper}'; "
        "$script:ValidationTargetProfiles = @("
        "[pscustomobject]@{ model_id = 'duplicate'; model = 'A' }, "
        "[pscustomobject]@{ model_id = 'duplicate'; model = 'B' }); "
        "Get-SupportedTargetModelIds"
    )
    result = run_powershell_command(command)

    assert result.returncode != 0
    assert "Duplicate validation target model_id 'duplicate'" in result.stdout + result.stderr


def test_release_check_rejects_mismatched_package_version():
    result = run_wrapper(
        "scripts/release-cli-check.ps1",
        "-Release",
        "1.4.0",
    )

    assert result.returncode != 0
    assert "Release 1.4.0 does not match package version 1.6.0" in (
        result.stdout + result.stderr
    )


def test_release_check_rejects_unknown_target_before_running_commands():
    result = run_wrapper(
        "scripts/release-cli-check.ps1",
        "-Target",
        "unknown",
    )

    assert result.returncode != 0
    assert "Unsupported target 'unknown'" in result.stdout + result.stderr


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
    raw_resource = "USB0::0x2A8D::0x1301::MY12345678::INSTR"
    result = run_wrapper(
        "scripts/live-cli-check.ps1",
        "-Target",
        "keysight-34461a",
        "-Connection",
        "usb",
        "-Resource",
        raw_resource,
        "-Suite",
        "minimal",
        "-PlanOnly",
    )
    assert result.returncode == 0, result.stderr + result.stdout

    report_path = report_from_summary_output(result.stdout)
    report = load_json(report_path)
    run_root = report_path.parents[1]
    private_report = load_json(run_root / "private" / "report.json")
    assert report["schema_version"] == "1.1"
    assert report["kind"] == "meters_tool_live_validation"
    assert report["artifact_visibility"] == "shareable"
    assert report["candidate_evidence_only"] is True
    assert report["promotes_live_support"] is False
    assert report["private_raw_artifacts_retained"] is True
    assert report["redaction_applied"] is True
    assert report["redaction_version"] == 1
    assert report["status"] == "planned"
    assert report["target"] == "keysight-34461a"
    assert report["model_id"] == "keysight-34461a"
    assert report["expected_model"] == "34461A"
    assert report["package_version"] == FALLBACK_CLI_VERSION
    assert report["validation_mode"] == "live_plan_only"
    assert report["support_policy_mode"] == "validation"
    assert report["pending_live_support_allowed"] is True
    assert report["visa_library"] == "system_visa"
    assert report["backend"] == "system_visa"
    assert "git_head" in report
    assert set(report["artifact_paths"]) == {"output_dir", "report", "summary"}
    assert report["plan_only"] is True
    assert report["live_executed"] is False
    assert report["suite"] == "minimal"
    assert report["resource"] == "usb:<redacted-resource>"
    assert private_report["resource"] == raw_resource
    assert private_report["artifact_visibility"] == "private"
    assert private_report["redaction_applied"] is False
    assert report["cases"] == []
    assert report["scpi_diagnostics"] == []
    assert report["output_dir"] == "shareable"
    assert report["artifact_paths"] == {
        "output_dir": "shareable",
        "report": "shareable/report.json",
        "summary": "shareable/summary.md",
    }
    assert {path.name for path in run_root.iterdir()} == {"private", "shareable"}
    assert not (run_root / "report.json").exists()
    assert not (run_root / "summary.md").exists()
    assert raw_resource not in result.stdout + result.stderr
    assert str(REPO_ROOT) not in result.stdout + result.stderr
    assert str(PYTHON) not in result.stdout + result.stderr

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
    assert "--validation-allow-pending-live-support" in args
    assert args[args.index("--model") + 1] == "34461A"
    assert args[args.index("--resource") + 1] == "<redacted-resource>"
    summary = (run_root / report["artifact_paths"]["summary"]).read_text(encoding="utf-8")
    assert "- Model ID: keysight-34461a" in summary
    assert "- Expected model: 34461A" in summary
    assert_command_artifacts(report["commands"], report_path.parent, run_root)
    assert_command_artifacts(private_report["commands"], run_root / "private")
    shareable_text = "\n".join(
        path.read_text(encoding="utf-8-sig", errors="strict")
        for path in (run_root / "shareable").rglob("*")
        if path.is_file()
    )
    for forbidden in (raw_resource, "MY12345678", str(REPO_ROOT), str(PYTHON)):
        assert forbidden not in shareable_text


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
    run_root = report_path.parents[1]
    output_dir = report_path.parent.resolve()
    assert report["status"] == "planned"
    assert report["plan_only"] is True
    assert report["live_executed"] is False
    assert report["cases"] == []
    assert report["scpi_diagnostics"] == []
    assert report["output_dir"] == "shareable"

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
        assert (run_root / command["stdout"]).resolve().exists()
        assert (run_root / command["stderr"]).resolve().exists()

    assert_command_artifacts(report["commands"], output_dir, run_root)


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
    assert report["model_id"] == "keysight-34460a"
    assert report["expected_model"] == "34460A"
    assert report["status"] == "planned"
    assert {dry_run["name"] for dry_run in report["dry_runs"]} == {
        "minimal_current_dc_immediate"
    }
    args = command_arguments(report, "minimal_current_dc_immediate_dry_run")
    assert "--validation-allow-pending-live-support" in args
    assert args[args.index("--model") + 1] == "34460A"
    assert report["output_dir"] == "shareable"


def test_live_plan_only_mixed_case_target_normalizes_to_model_id():
    result = run_wrapper(
        "scripts/live-cli-check.ps1",
        "-Target",
        "KEYSIGHT-34461A",
        "-Connection",
        "usb",
        "-Resource",
        "SIM::34461A",
        "-PlanOnly",
    )
    assert result.returncode == 0, result.stderr + result.stdout

    report = load_json(report_from_summary_output(result.stdout))
    assert report["target"] == "keysight-34461a"
    assert report["model_id"] == "keysight-34461a"
    assert report["expected_model"] == "34461A"
    assert report["output_dir"] == "shareable"


def test_live_rejects_unknown_target_with_usage_failure():
    result = run_wrapper(
        "scripts/live-cli-check.ps1",
        "-Target",
        "unknown",
        "-Connection",
        "usb",
        "-Resource",
        "SIM::34461A",
        "-PlanOnly",
    )

    assert result.returncode == 2
    assert "Unsupported target 'unknown'" in result.stdout + result.stderr


def test_live_rejects_missing_target_with_usage_failure():
    result = run_wrapper(
        "scripts/live-cli-check.ps1",
        "-Connection",
        "usb",
        "-Resource",
        "SIM::34461A",
        "-PlanOnly",
    )

    assert result.returncode == 2
    assert "Missing target" in result.stdout + result.stderr


def test_live_plan_only_forwards_visa_library_to_start_args():
    result = run_wrapper(
        "scripts/live-cli-check.ps1",
        "-Target",
        "keysight-34460a",
        "-Connection",
        "lan",
        "-Resource",
        "TCPIP0::host::inst0::INSTR",
        "-Suite",
        "minimal",
        "-VisaLibrary",
        "@py",
        "-PlanOnly",
    )
    assert result.returncode == 0, result.stderr + result.stdout

    report = load_json(report_from_summary_output(result.stdout))
    assert report["visa_library"] == "@py"
    assert report["backend"] == "@py"
    args = command_arguments(report, "minimal_current_dc_immediate_dry_run")
    assert "--validation-allow-pending-live-support" in args
    assert args[args.index("--visa-library") + 1] == "@py"


def test_live_plan_only_backend_alias_forwards_visa_library_to_start_args():
    result = run_wrapper(
        "scripts/live-cli-check.ps1",
        "-Target",
        "keysight-34460a",
        "-Connection",
        "lan",
        "-Resource",
        "TCPIP0::host::inst0::INSTR",
        "-Suite",
        "minimal",
        "-Backend",
        "@py",
        "-PlanOnly",
    )
    assert result.returncode == 0, result.stderr + result.stdout

    report = load_json(report_from_summary_output(result.stdout))
    args = command_arguments(report, "minimal_current_dc_immediate_dry_run")
    assert args[args.index("--visa-library") + 1] == "@py"


def test_live_plan_only_kebab_visa_library_alias_forwards_visa_library_to_start_args():
    result = run_wrapper(
        "scripts/live-cli-check.ps1",
        "-Target",
        "keysight-34460a",
        "-Connection",
        "lan",
        "-Resource",
        "TCPIP0::host::inst0::INSTR",
        "-Suite",
        "minimal",
        "-visa-library",
        "@py",
        "-PlanOnly",
    )
    assert result.returncode == 0, result.stderr + result.stdout

    report = load_json(report_from_summary_output(result.stdout))
    assert report["visa_library"] == "@py"
    assert report["backend"] == "@py"
    args = command_arguments(report, "minimal_current_dc_immediate_dry_run")
    assert "--validation-allow-pending-live-support" in args
    assert "--visa-library" in args
    assert args[args.index("--visa-library") + 1] == "@py"


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


def test_live_frequency_period_probe_args_include_selected_model():
    script = (REPO_ROOT / "scripts" / "live-cli-check.ps1").read_text(
        encoding="utf-8-sig"
    )
    match = re.search(
        r"function Invoke-FrequencyPeriodScpiProbe \{(?P<body>.*?)"
        r"\nfunction New-ScpiProbeFailureCaseResult",
        script,
        flags=re.S,
    )
    assert match, "Invoke-FrequencyPeriodScpiProbe block not found"
    body = match.group("body")

    assert '"--model", $resolvedCliModel' in body


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

    report_path = report_from_summary_output(result.stdout + result.stderr)
    report = load_json(report_path)
    run_root = report_path.parents[1]
    assert report["status"] == "confirmation_required"
    assert report["plan_only"] is False
    assert report["live_executed"] is False
    assert report["cases"] == []
    assert {dry_run["name"] for dry_run in report["dry_runs"]} == {
        "minimal_current_dc_immediate"
    }
    assert {path.name for path in run_root.iterdir()} == {"private", "shareable"}
    assert report_path == run_root / "shareable" / "report.json"
    assert (run_root / "private" / "report.json").exists()
    assert not (run_root / "report.json").exists()


def test_live_probe_exception_reports_that_live_execution_began(tmp_path: Path):
    raw_resource = "TCPIP0::meter-lab.local::inst0::INSTR"
    timestamp = f"synthetic-{uuid4().hex}"
    run_root = (
        REPO_ROOT
        / ".tmp_tests"
        / "cli_live"
        / "keysight-34461a"
        / "lan"
        / "frequency-period"
        / timestamp
    )
    private_path = run_root / "private" / "synthetic-private.json"
    wrapper_text = (REPO_ROOT / "scripts" / "live-cli-check.ps1").read_text(
        encoding="utf-8-sig"
    )
    timestamp_line = '$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"'
    stdin_line = "$stdinRedirected = [Console]::IsInputRedirected"
    confirmation_line = (
        "[void](Read-Host \"Press Enter to run suite '$Suite', or Ctrl+C to cancel\")"
    )
    probe_line = "$probe = Invoke-FrequencyPeriodScpiProbe -CaseInfo $caseInfo"
    assert wrapper_text.count(timestamp_line) == 1
    assert wrapper_text.count(stdin_line) == 1
    assert wrapper_text.count(confirmation_line) == 1
    assert wrapper_text.count(probe_line) == 1
    scripts_root = ps_quote(REPO_ROOT / "scripts")
    wrapper_text = wrapper_text.replace("$PSScriptRoot", scripts_root)
    wrapper_text = wrapper_text.replace(
        timestamp_line,
        f"$timestamp = '{timestamp}'",
    )
    wrapper_text = wrapper_text.replace(
        stdin_line,
        "$stdinRedirected = $false",
    )
    wrapper_text = wrapper_text.replace(
        confirmation_line,
        "[void]$null",
    )
    wrapper_text = wrapper_text.replace(
        probe_line,
        "throw "
        + ps_quote(
            f"Synthetic live probe failure for {raw_resource} at {private_path}"
        ),
    )
    synthetic_wrapper = tmp_path / "live-cli-check-synthetic-failure.ps1"
    synthetic_wrapper.write_text(wrapper_text, encoding="utf-8")

    result = run_wrapper_path(
        synthetic_wrapper,
        "-Target",
        "keysight-34461a",
        "-Connection",
        "lan",
        "-Resource",
        raw_resource,
        "-Suite",
        "frequency-period",
    )
    assert result.returncode != 0
    report_path = report_from_summary_output(result.stdout + result.stderr)
    assert report_path == run_root / "shareable" / "report.json"
    private_report = load_json(run_root / "private" / "report.json")
    shareable_report = load_json(report_path)
    for report in (private_report, shareable_report):
        assert report["status"] == "wrapper_failed"
        assert report["live_executed"] is True
        assert report["validation_mode"] == "live"
        assert report["private_raw_artifacts_retained"] is True
    assert private_report["resource"] == raw_resource
    assert shareable_report["resource"] == "lan:<redacted-resource>"
    assert (run_root / "shareable" / "summary.md").exists()
    console = result.stdout + result.stderr
    assert raw_resource not in console
    assert "meter-lab.local" not in console
    assert str(private_path) not in console
    assert str(REPO_ROOT) not in console


def synthetic_confirmed_live_wrapper(timestamp: str) -> str:
    wrapper_text = (REPO_ROOT / "scripts" / "live-cli-check.ps1").read_text(
        encoding="utf-8-sig"
    )
    wrapper_text = wrapper_text.replace("$PSScriptRoot", ps_quote(REPO_ROOT / "scripts"))
    replacements = {
        '$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"': f"$timestamp = '{timestamp}'",
        "$stdinRedirected = [Console]::IsInputRedirected": "$stdinRedirected = $false",
        "[void](Read-Host \"Press Enter to run suite '$Suite', or Ctrl+C to cancel\")": "[void]$null",
    }
    for source, replacement in replacements.items():
        assert wrapper_text.count(source) == 1, source
        wrapper_text = wrapper_text.replace(source, replacement)
    return wrapper_text


def assert_normal_failure_artifact_privacy(
    result: subprocess.CompletedProcess[str],
    run_root: Path,
    raw_reasons: list[str],
) -> None:
    assert result.returncode != 0
    report_path = report_from_summary_output(result.stdout + result.stderr)
    assert report_path == run_root / "shareable" / "report.json"
    private_report = load_json(run_root / "private" / "report.json")
    shareable_report = load_json(report_path)
    for report in (private_report, shareable_report):
        assert report["status"] == "failed"
        assert report["live_executed"] is True
        assert report["validation_mode"] == "live"
    private_failure_reasons = [
        reason
        for case in private_report["cases"]
        for reason in case["failure_reasons"]
    ]
    shareable_report_text = json.dumps(shareable_report, ensure_ascii=False)
    shareable_tree_text = "\n".join(
        path.read_text(encoding="utf-8-sig")
        for path in (run_root / "shareable").rglob("*")
        if path.is_file()
    )
    console = result.stdout + result.stderr
    for reason in raw_reasons:
        assert reason in private_failure_reasons
        assert reason not in shareable_report_text
        assert reason not in shareable_tree_text
        assert reason not in console
    assert "failure reasons:" in console
    assert "summary: .tmp_tests/cli_live/" in console
    assert "/shareable/summary.md" in console


def test_normal_scpi_probe_failure_console_is_sanitized(tmp_path: Path):
    raw_resource = "TCPIP0::dmm01::inst0::INSTR"
    timestamp = f"synthetic-{uuid4().hex}"
    run_root = (
        REPO_ROOT
        / ".tmp_tests"
        / "cli_live"
        / "keysight-34461a"
        / "lan"
        / "frequency-period"
        / timestamp
    )
    private_path = run_root / "private" / "synthetic-probe.json"
    raw_reasons = [
        raw_resource,
        "dmm01",
        "172.20.10.5",
        "KEYSIGHT,34461A,DISTINCTIVE123,A.03.03",
        r"C:\Users\Alice\private\probe.json",
        str(REPO_ROOT),
        str(private_path),
    ]
    wrapper_text = synthetic_confirmed_live_wrapper(timestamp)
    probe_line = "$probe = Invoke-FrequencyPeriodScpiProbe -CaseInfo $caseInfo"
    assert wrapper_text.count(probe_line) == 1
    synthetic_reasons = ",".join(ps_quote(reason) for reason in raw_reasons)
    probe_result = "\n".join(
        [
            "$probe = [pscustomobject]@{",
            "  success = $false",
            "  command = [pscustomobject]@{ name='synthetic_probe'; command='python'; arguments=@(); exit_code=1; duration_seconds=0; stdout=(Join-Path $caseInfo.case_dir 'scpi_probe.json'); stderr=(Join-Path $caseInfo.case_dir 'scpi_probe.stderr.txt'); success=$false }",
            "  diagnostic = [pscustomobject]@{ schema_version=1; resource=$Resource; measurement=$caseInfo.plan.measurement_cli_name; status='failed'; all_scpi_error_responses_zero=$false; idn='KEYSIGHT,34461A,DISTINCTIVE123,A.03.03'; firmware_revision='A.03.03'; identity_system_errors=$null; commands=@(); read=$null; failure_reasons=@("
            + synthetic_reasons
            + "); cleanup=$null; artifact_path=(Join-Path $caseInfo.case_dir 'scpi_probe.json'); stderr_path=(Join-Path $caseInfo.case_dir 'scpi_probe.stderr.txt') }",
            "}",
        ]
    )
    wrapper_text = wrapper_text.replace(probe_line, probe_result)
    synthetic_wrapper = tmp_path / "live-cli-check-synthetic-probe-failure.ps1"
    synthetic_wrapper.write_text(wrapper_text, encoding="utf-8")

    result = run_wrapper_path(
        synthetic_wrapper,
        "-Target",
        "keysight-34461a",
        "-Connection",
        "lan",
        "-Resource",
        raw_resource,
        "-Suite",
        "frequency-period",
    )
    assert_normal_failure_artifact_privacy(result, run_root, raw_reasons)
    assert "SCPI probe failed:" in result.stdout


def test_normal_live_case_failure_console_is_sanitized(tmp_path: Path):
    raw_resource = "TCPIP0::dmm01::inst0::INSTR"
    timestamp = f"synthetic-{uuid4().hex}"
    run_root = (
        REPO_ROOT
        / ".tmp_tests"
        / "cli_live"
        / "keysight-34461a"
        / "lan"
        / "minimal"
        / timestamp
    )
    private_path = run_root / "private" / "synthetic-live.jsonl"
    raw_reasons = [
        raw_resource,
        "dmm01",
        "172.20.10.5",
        "KEYSIGHT,34461A,DISTINCTIVE123,A.03.03",
        r"C:\Users\Alice\private\live.jsonl",
        str(REPO_ROOT),
        str(private_path),
    ]
    wrapper_text = synthetic_confirmed_live_wrapper(timestamp)
    live_call = "\n".join(
        [
            "    $liveResult = Invoke-LiveCase `",
            "        -Case $case `",
            "        -CaseDir $caseInfo.case_dir `",
            "        -Port $caseInfo.port `",
            "        -CsvPath $caseInfo.csv `",
            "        -ScpiProbeCommand $scpiProbeCommand `",
            "        -ScpiDiagnostic $scpiDiagnostic",
        ]
    )
    assert wrapper_text.count(live_call) == 1
    synthetic_reasons = ",".join(ps_quote(reason) for reason in raw_reasons)
    live_result = "\n".join(
        [
            "    $liveResult = [pscustomobject]@{",
            "        command=[pscustomobject]@{ name='synthetic_live'; command='python'; arguments=@(); exit_code=1; duration_seconds=0; stdout=(Join-Path $caseInfo.case_dir 'live.jsonl'); stderr=(Join-Path $caseInfo.case_dir 'live.stderr.txt'); success=$false }",
            "        name=$case.name; status='failed'; failure_reasons=@("
            + synthetic_reasons
            + "); run_id=$null; expected_captured=$case.expected_captured; captured_count=0; captured=0; errors=0; ready_events=0; csv_row_count=0; csv_rows=0; measurement_type=$case.expected_measurement_type; unit=$case.expected_unit; value=$null; csv=$caseInfo.csv; jsonl=(Join-Path $caseInfo.case_dir 'live.jsonl'); stderr=(Join-Path $caseInfo.case_dir 'live.stderr.txt'); live_command_skipped=$false; scpi_probe_command=$null; scpi_diagnostic_path=$null; scpi_diagnostic=$null",
            "    }",
        ]
    )
    wrapper_text = wrapper_text.replace(live_call, live_result)
    synthetic_wrapper = tmp_path / "live-cli-check-synthetic-live-failure.ps1"
    synthetic_wrapper.write_text(wrapper_text, encoding="utf-8")

    result = run_wrapper_path(
        synthetic_wrapper,
        "-Target",
        "keysight-34461a",
        "-Connection",
        "lan",
        "-Resource",
        raw_resource,
        "-Suite",
        "minimal",
    )
    assert_normal_failure_artifact_privacy(result, run_root, raw_reasons)
    assert "live case failed:" in result.stdout
