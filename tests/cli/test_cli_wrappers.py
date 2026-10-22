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
from meters_tool_core.support_policy import supported_custom_acquisition_features


pytestmark = pytest.mark.windows_powershell

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


def test_release_acceptance_rejects_mismatched_package_version():
    result = run_wrapper(
        "scripts/release-acceptance.ps1",
        "-Release",
        "1.4.0",
    )

    assert result.returncode != 0
    assert f"Release 1.4.0 does not match package version {FALLBACK_CLI_VERSION}" in (
        result.stdout + result.stderr
    )


@pytest.mark.windows_boundary_smoke
def test_release_acceptance_rejects_unknown_target_before_running_commands():
    result = run_wrapper(
        "scripts/release-acceptance.ps1",
        "-Target",
        "unknown",
    )

    assert result.returncode != 0
    assert "Unsupported target 'unknown'" in result.stdout + result.stderr


def test_release_acceptance_rejects_output_root_outside_tmp_tests():
    bad_root = REPO_ROOT / ".tmp_bad_release"
    assert not bad_root.exists()

    result = run_wrapper(
        "scripts/release-acceptance.ps1",
        "-OutputRoot",
        ".tmp_bad_release",
    )

    assert result.returncode != 0
    assert "Only paths under .tmp_tests are allowed" in result.stdout + result.stderr
    assert not bad_root.exists()


@pytest.mark.windows_boundary_smoke
def test_preflight_report_contract():
    output_root = REPO_ROOT / ".tmp_tests" / "pytest_wrappers" / f"preflight_{uuid4().hex}"
    result = run_wrapper(
        "scripts/preflight-cli.ps1",
        "-DebugArtifacts",
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
    assert report["commands"]
    assert report["checks"]
    assert summary_counts["commands_total"] == len(report["commands"])
    assert summary_counts["checks_total"] == len(report["checks"])
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
    assert f"- Commands total: {len(report['commands'])}" in summary
    assert f"- Checks total: {len(report['checks'])}" in summary
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
        "-DebugArtifacts",
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


@pytest.mark.windows_boundary_smoke
def test_live_plan_only_minimal_report_contract():
    raw_resource = "USB0::0x2A8D::0x1301::MY12345678::INSTR"
    result = run_wrapper(
        "scripts/live-cli-check.ps1",
        "-DebugArtifacts",
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
    assert "preflight" in {command["name"] for command in private_report["commands"]}
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


def test_live_plan_only_can_skip_duplicate_preflight():
    result = run_wrapper(
        "scripts/live-cli-check.ps1",
        "-DebugArtifacts",
        "-Target",
        "keysight-34461a",
        "-Connection",
        "usb",
        "-Resource",
        "SIM::34461A",
        "-Suite",
        "minimal",
        "-PlanOnly",
        "-SkipPreflight",
    )
    assert result.returncode == 0, result.stderr + result.stdout

    report_path = report_from_summary_output(result.stdout)
    private_report = load_json(report_path.parents[1] / "private" / "report.json")
    assert "preflight" not in {command["name"] for command in private_report["commands"]}


def test_live_plan_only_full_report_contract():
    result = run_wrapper(
        "scripts/live-cli-check.ps1",
        "-DebugArtifacts",
        "-Target",
        "keysight-34461a",
        "-Connection",
        "usb",
        "-Resource",
        "SIM::34461A",
        "-Suite",
        "full",
        "-PlanOnly",
        "-SkipPreflight",
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
    expected_names += [f"finite_{mode}_{handling}" for mode in ("immediate", "software", "external")
                       for handling in ("monitor", "stop_on_overflow")]
    assert len(report["dry_runs"]) == 20
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
    expected_read_paths.update({name: "DATA:POINts? / DATA:REMove?"
                                for name in expected_names if name.startswith("finite_")})
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
        "-SkipPreflight",
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
        "-SkipPreflight",
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
        "-SkipPreflight",
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
        "-SkipPreflight",
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
        "-SkipPreflight",
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
        "-SkipPreflight",
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
        "-SkipPreflight",
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
        "-SkipPreflight",
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
    } | {f"finite_{mode}_{handling}" for mode in ("immediate", "software")
         for handling in ("monitor", "stop_on_overflow")}
    assert len(report["dry_runs"]) == 16
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


@pytest.mark.parametrize("target", ["keysight-34461a", "keysight-34460a"])
@pytest.mark.parametrize("suite", ["finite-custom", "infinite-custom", "overflow"])
def test_live_custom_plan_only_matches_registered_scopes(target, suite):
    profile = find_instrument_profile_by_model(target)
    result = run_wrapper(
        "scripts/live-cli-check.ps1", "-Target", target, "-Connection", "usb",
        "-Resource", f"SIM::{profile.model}", "-Suite", suite, "-PlanOnly", "-SkipPreflight",
    )

    assert result.returncode == 0, result.stderr + result.stdout
    report = load_json(report_from_summary_output(result.stdout))
    assert report["live_executed"] is False
    expected = set(supported_custom_acquisition_features(profile))
    if suite != "overflow":
        count = "finite" if suite == "finite-custom" else "infinite"
        expected = {scope for scope in expected if scope.split(":")[1] == count}
    actual = set()
    for case in report["dry_runs"]:
        args = case["command"]["arguments"]
        mode = args[args.index("--trigger-mode") + 1]
        count = "infinite" if "--trigger-count-infinite" in args else "finite"
        handling = "stop_on_overflow" if "--stop-on-overflow" in args else "monitor"
        actual.add(f"{mode}:{count}:{handling}")
        if count == "infinite":
            assert "--allow-buffer-overflow-risk" in args
            assert "TRIG:COUNT INF" in case["plan"]["scpi_commands"]
        if suite == "overflow":
            assert "SAMP:COUNT 1000000" in case["plan"]["scpi_commands"]
            assert "--allow-buffer-overflow-risk" in args
    assert actual == expected
    assert len(report["dry_runs"]) == len(expected)


@pytest.mark.parametrize("target", ["keysight-34461a", "keysight-34460a"])
def test_live_overflow_still_requires_interactive_confirmation(target):
    profile = find_instrument_profile_by_model(target)
    args = (
        "-Target", target, "-Connection", "usb",
        "-Resource", f"SIM::{profile.model}", "-Suite", "overflow",
    )
    refused = run_wrapper("scripts/live-cli-check.ps1", *args)
    assert refused.returncode != 0
    report = load_json(report_from_summary_output(refused.stdout))
    assert report["status"] == "confirmation_required"
    assert report["live_executed"] is False


def test_live_custom_outcomes_require_matching_state_and_active_continued_drain(tmp_path: Path):
    source = (REPO_ROOT / "scripts/live-cli-check.ps1").read_text(encoding="utf-8")
    functions = []
    for name in ("New-LiveCase", "Get-LiveCases", "New-StartArgs", "Invoke-LiveCase"):
        match = re.search(rf"(?ms)^function {name} \{{.*?(?=^function |\Z)", source)
        assert match, name
        functions.append(match.group())
    results_path = tmp_path / "outcomes.json"
    script = tmp_path / "outcomes.ps1"
    script.write_text(
        "$ErrorActionPreference = 'Stop'\nSet-StrictMode -Version Latest\n"
        f"$RepoRoot = {ps_quote(REPO_ROOT)}\n$Python = {ps_quote(PYTHON)}\n"
        "$Resource = 'USB0::1::2::SYNTHETIC::INSTR'\n$DebugArtifacts = $false\n$resolvedVisaLibrary = ''\n"
        f"$caseRoot = {ps_quote(tmp_path)}\n$resultsPath = {ps_quote(results_path)}\n"
        f". {ps_quote(REPO_ROOT / 'scripts/_validation_helpers.ps1')}\n"
        + "\n".join(functions)
        + r'''
function Read-Host { param($Prompt) return '' }
function Invoke-CapturedStartProcess {
    param($Name, $Arguments, $StdOutPath, $StdErrPath, $TimeoutSeconds,
        $SoftTriggerCount, $SoftTriggerPort, $OutDir, $SoftTriggerRetryCount,
        $SoftTriggerRetryDelayMs, $InterTriggerDelayMs, $StopGracePeriodMs,
        $PlannedStopAfterSeconds, $ExpectedExitCode, [switch]$CaptureClientCommandsInMemory)
    $infinite = $Arguments -contains '--trigger-count-infinite'
    $expected = if ($infinite) { $null } else {
        [int]$Arguments[[array]::IndexOf($Arguments, '--trigger-count') + 1] *
            [int]$Arguments[[array]::IndexOf($Arguments, '--sample-count') + 1]
    }
    $overflow = $Case.expect_overflow -and $script:fault -ne 'no_overflow'
    $state = [ordered]@{
        event = 'status'; run_id = 'synthetic-run'; message = 'synthetic status'
        trigger_count_infinite = $infinite; expected_readings = $expected
        overflow_monitoring = 'active'; overflow_detected = $overflow
        stop_reason = 'unknown'; final_drain_complete = $null; data_integrity = 'unknown'
    }
    $events = @([ordered]@{event = 'ready'; run_id = 'synthetic-run'}, $state)
    foreach ($index in 1..2) {
        $events += [ordered]@{
            event = 'sample'; run_id = 'synthetic-run'; trigger_id = 'synthetic-trigger'; value = $index
        }
    }
    $afterSample = [ordered]@{}
    foreach ($key in $state.Keys) { $afterSample[$key] = $state[$key] }
    if ($script:fault -eq 'final_drain_only') { $afterSample.stop_reason = 'stop_requested' }
    $events += $afterSample
    $summary = [ordered]@{
        event = 'summary'; run_id = 'synthetic-run'; captured = 2; errors = 0
        ok = ($ExpectedExitCode -eq 0); fatal_error = $null
        trigger_count_infinite = $infinite; expected_readings = $expected
        overflow_monitoring = 'active'; overflow_detected = $overflow
        stop_reason = $Case.expected_stop_reason; final_drain_complete = $true
        data_integrity = if ($Case.expect_overflow) { 'incomplete' } elseif ($infinite) { 'unknown' } else { 'no_loss_detected' }
    }
    if ($script:fault -eq 'missing_summary_field') { $summary.Remove('overflow_detected') }
    if ($script:fault -eq 'wrong_count') { $summary.expected_readings = 123 }
    $events += $summary
    Write-Utf8NoBomLines -LiteralPath $StdOutPath -Lines @($events | ForEach-Object { $_ | ConvertTo-Json -Compress -Depth 8 })
    Write-Utf8NoBomText -LiteralPath $StdErrPath -Text ''
    $csvPath = $Arguments[[array]::IndexOf($Arguments, '--csv') + 1]
    Write-Utf8NoBomLines -LiteralPath $csvPath -Lines @(
        'timestamp_utc_plus_8,measurement_type,value,unit,trigger_id,trigger_metadata,resource_id,status',
        '2026-01-01T00:00:00+08:00,current_dc,1,A,synthetic-trigger,,SYNTHETIC,ok',
        '2026-01-01T00:00:01+08:00,current_dc,2,A,synthetic-trigger,,SYNTHETIC,ok')
    if ($script:fault -eq 'missing_status_field') { $state.Remove('overflow_monitoring') }
    return [ordered]@{
        name = $Name; success = $true; exit_code = $ExpectedExitCode
        client_commands = @([pscustomobject]@{
            name = "$Name`_soft_status"; stdout_text = ($state | ConvertTo-Json -Compress)
        })
    }
}
$outcomes = @()
foreach ($target in @('keysight-34461a', 'keysight-34460a')) {
    $resolvedCliModel = if ($target -eq 'keysight-34461a') { '34461A' } else { '34460A' }
    foreach ($suite in @('finite-custom', 'infinite-custom', 'overflow')) {
        foreach ($case in @(Get-LiveCases -SelectedSuite $suite -ResolvedTarget $target)) {
            $faults = @('none', 'missing_summary_field', 'wrong_count')
            if ($case.planned_stop_after_seconds -gt 0 -or $case.soft_trigger_count -gt 0 -or $case.expected_exit_code -ne 0) {
                $faults += 'missing_status_field'
            }
            if ($case.expect_overflow) { $faults += 'no_overflow' }
            if ($case.require_continued_drain) { $faults += 'final_drain_only' }
            foreach ($fault in $faults) {
                $script:fault = $fault
                $result = Invoke-LiveCase -Case $case -CaseDir $caseRoot -Port 0 -CsvPath (Join-Path $caseRoot 'case.csv')
                $outcomes += [ordered]@{
                    target = $target; case = $case.name; fault = $fault; status = $result.status
                    reasons = $result.failure_reasons
                    continued = $result.runtime_evidence.continued_drain_after_overflow
                }
            }
        }
    }
}
Write-Utf8NoBomText -LiteralPath $resultsPath -Text ($outcomes | ConvertTo-Json -Depth 8)
''',
        encoding="utf-8",
    )
    result = run_wrapper_path(script)
    assert result.returncode == 0, result.stderr + result.stdout
    outcomes = load_json(results_path)
    assert len([case for case in outcomes if case["fault"] == "none"]) == 40
    for case in outcomes:
        assert case["status"] == ("passed" if case["fault"] == "none" else "failed"), case
        if case["fault"] == "final_drain_only":
            assert case["continued"] is False
            assert any("continued drain" in reason for reason in case["reasons"])


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
        "-SkipPreflight",
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
        "-DebugArtifacts",
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


@pytest.mark.parametrize("mode", ["minimal", "artifact_failure"])
def test_live_probe_exception_reports_that_live_execution_began(tmp_path: Path, mode: str):
    raw_resource = "TCPIP0::meter-lab.local::inst0::INSTR"
    timestamp = f"synthetic-{uuid4().hex}"
    run_root = (
        REPO_ROOT / ".tmp_tests" / "cli_live" / "keysight-34461a"
        / "lan" / "frequency-period" / timestamp
    )
    private_path = run_root / "private" / "synthetic-private.json"
    reason = f"Synthetic live probe failure for {raw_resource} at {private_path}"
    synthetic_wrapper = tmp_path / "live-cli-check-synthetic-failure.ps1"
    synthetic_wrapper.write_text(synthetic_confirmed_live_wrapper(timestamp), encoding="utf-8")
    setup = (
        f"function Invoke-SyntheticProbe {{ throw {ps_quote(reason)} }}; "
        "Set-Alias Invoke-FrequencyPeriodScpiProbe Invoke-SyntheticProbe; "
    )
    if mode == "artifact_failure":
        setup += (
            f"function Invoke-SyntheticArtifactFailure {{ throw {ps_quote('Synthetic artifact failure ' + raw_resource)} }}; "
            "Set-Alias New-ShareableArtifactSet Invoke-SyntheticArtifactFailure; "
        )
    result = run_powershell_command(
        setup + f"& {ps_quote(synthetic_wrapper)} "
        + f"-Target keysight-34461a -Connection lan -Resource {ps_quote(raw_resource)} "
        "-Suite frequency-period; exit $LASTEXITCODE"
    )
    assert result.returncode == 1, result.stderr + result.stdout
    files = {p.relative_to(run_root).as_posix() for p in run_root.rglob("*") if p.is_file()}
    if mode == "artifact_failure":
        assert files == {"private/error-summary.md"}
        safe_text = (run_root / "private" / "error-summary.md").read_text(encoding="utf-8")
        assert "Synthetic artifact failure" in safe_text
    else:
        report_path = report_from_summary_output(result.stdout + result.stderr)
        assert report_path == run_root / "shareable" / "report.json"
        report = load_json(report_path)
        assert report["status"] == "wrapper_failed"
        assert report["live_executed"] is True
        assert report["validation_mode"] == "live"
        assert report["private_raw_artifacts_retained"] is False
        assert report["resource"] == "lan:<redacted-resource>"
        assert "Synthetic live probe failure" in report["failure_reason"]
        summary_text = report_path.with_name("summary.md").read_text(encoding="utf-8")
        assert report["failure_reason"] in summary_text
        safe_text = report_path.read_text(encoding="utf-8") + summary_text
        assert files == {"shareable/report.json", "shareable/summary.md"}
    for forbidden in (raw_resource, "meter-lab.local", str(private_path), str(REPO_ROOT)):
        assert forbidden not in safe_text
        assert forbidden not in result.stdout + result.stderr



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


@pytest.mark.parametrize("suite,missing_field", [
    ("minimal", None), ("minimal", "sample_run_id"), ("minimal", "sample_trigger_id"),
    ("minimal", "csv_trigger_id"), ("worker-streaming", None),
])
def test_live_runtime_evidence_survives_artifact_cleanup(tmp_path: Path, suite, missing_field):
    resource = "USB0::1::2::SERIAL12345::INSTR"
    value = "98765.4321"
    failure = f"capture failure: VisaIOError at {tmp_path} for {resource}"
    run_id = "synthetic-run"
    cleanup = [{"step": "release_to_local", "result": "SYST:LOC:failed:VisaIOError"}]
    events = [
        {"event": "ready", "run_id": run_id},
        {"event": "sample", "run_id": run_id, "trigger_id": "synthetic-trigger", "value": value,
         "trigger_metadata": {"secret": "private"}},
        {"event": "status", "message": f"captured=1 value={value} A"},
        {"event": "message", "message": "KEYSIGHT,34461A,SERIAL12345,A.03.03"},
        {"event": "summary", "run_id": run_id, "captured": 1, "errors": 1,
         "ok": False, "fatal_error": failure},
        {"event": "status", "message": 'capture error count=1 scpi_error=-113,"Undefined header"'},
        {"event": "error", "message": failure, "exit_code": 3},
        {"event": "message", "message": "release_to_local: SYST:LOC:failed:VisaIOError"},
    ]
    if missing_field in ("sample_run_id", "sample_trigger_id"):
        del events[1][missing_field.removeprefix("sample_")]
    events_path = tmp_path / "events.jsonl"
    events_path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    timestamp = f"synthetic-{uuid4().hex}"
    wrapper = tmp_path / "synthetic-live.ps1"
    wrapper.write_text(synthetic_confirmed_live_wrapper(timestamp), encoding="utf-8")
    csv = (
        "timestamp_utc_plus_8,measurement_type,value,unit,trigger_id,trigger_metadata,resource_id,status\n"
        f"2026-01-01T00:00:00+08:00,current_dc,{value},A,synthetic-trigger,private,{resource},ok\n"
    )
    if missing_field == "csv_trigger_id":
        csv = csv.replace("trigger_id,", "").replace("synthetic-trigger,", "")
    setup = (
        "function Invoke-SyntheticStartProcess { "
        "param($Name,$Arguments,$StdOutPath,$StdErrPath,$TimeoutSeconds,$SoftTriggerCount,"
        "$SoftTriggerPort,$OutDir,$SoftTriggerRetryCount,$SoftTriggerRetryDelayMs,"
        "$InterTriggerDelayMs,$StopGracePeriodMs,[switch]$CaptureClientCommandsInMemory,$Case,$Port); "
        f"Write-Utf8NoBomText -LiteralPath $StdOutPath -Text ([IO.File]::ReadAllText({ps_quote(events_path)})); "
        "Write-Utf8NoBomText -LiteralPath $StdErrPath -Text 'private stderr'; "
        f"Write-Utf8NoBomText -LiteralPath $Arguments[[array]::IndexOf($Arguments,'--csv')+1] -Text {ps_quote(csv)}; "
        "return [ordered]@{name=$Name;command=$Python;arguments=$Arguments;"
        "exit_code=3;success=$false;"
        "duration_seconds=0;stdout=$StdOutPath;stderr=$StdErrPath;client_commands=@();"
        "timed_out=$false;client_failure=$null;forced_termination=$true;cleanup_unconfirmed=$true;"
        "streaming_evidence=@{active=$true;stdout_eof=$true;failure_reasons=@('Stop grace period exceeded')}} }; "
        "Set-Alias Invoke-CapturedStartProcess Invoke-SyntheticStartProcess; "
        "Set-Alias Invoke-StreamingStartProcess Invoke-SyntheticStartProcess; "
    )
    result = run_powershell_command(
        setup + f"& {ps_quote(wrapper)} -Target keysight-34461a -Connection usb "
        + f"-Resource {ps_quote(resource)} -Suite {suite}; exit $LASTEXITCODE"
    )
    assert result.returncode == 1, result.stderr + result.stdout
    report_path = report_from_summary_output(result.stdout + result.stderr)
    report = load_json(report_path)
    assert report["status"] == "failed"
    case = report["cases"][0]
    assert case["status"] == "failed"
    assert case["run_id"] == run_id
    if missing_field:
        assert any("correlation" in reason for reason in case["failure_reasons"])
    else:
        assert not any("correlation" in reason for reason in case["failure_reasons"])
    evidence = case["runtime_evidence"]
    assert evidence["identity"]["status"] == "not_available"
    expected_cleanup = {
        "status": "observed", "results": cleanup, "close_status": "not_reported",
    }
    if suite == "worker-streaming":
        expected_cleanup.update(process_exit_observed=True, forced_termination=True, unconfirmed=True)
        assert evidence["streaming"]["active"] and evidence["streaming"]["stdout_eof"]
        assert len(report["cases"]) == 1 and len(report["not_run_cases"]) == 9
        assert report["unverified_observations"]
        assert any("operator must check" in reason for reason in case["failure_reasons"])
    assert evidence["cleanup"] == expected_cleanup
    assert evidence["summary"]["ok"] is False
    assert "VisaIOError" in evidence["summary"]["fatal_error"]
    assert case["captured"] == case["csv_rows"] == 1
    assert case["csv_validation"]["header_valid"] is True
    assert evidence["error_events"] == [
        {"message": evidence["summary"]["fatal_error"], "exit_code": 3}
    ]
    assert "Undefined header" in evidence["diagnostics"][0]["message"]
    run_root = report_path.parents[1]
    files = {p.relative_to(run_root).as_posix() for p in run_root.rglob("*") if p.is_file()}
    assert files == {"shareable/report.json", "shareable/summary.md"}
    safe_text = report_path.read_text(encoding="utf-8-sig") + report_path.with_name(
        "summary.md"
    ).read_text(encoding="utf-8-sig")
    for forbidden in (resource, "SERIAL12345", "KEYSIGHT,34461A", str(tmp_path), value, "private stderr"):
        assert forbidden not in safe_text



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
        "-DebugArtifacts",
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
        "-DebugArtifacts",
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


@pytest.mark.windows_boundary_smoke
def test_preflight_minimal_retains_only_shareable_reports():
    output_root = REPO_ROOT / ".tmp_tests" / "pytest_wrappers" / f"minimal_{uuid4().hex}"
    result = run_wrapper(
        "scripts/preflight-cli.ps1", "-Target", "all",
        "-OutputRoot", str(output_root.relative_to(REPO_ROOT)),
    )
    assert result.returncode == 0, result.stderr + result.stdout
    for model in ("keysight-34461a", "keysight-34460a"):
        target_root = output_root / model
        files = {p.relative_to(target_root).as_posix() for p in target_root.rglob("*") if p.is_file()}
        assert files == {"shareable/report.json", "shareable/summary.md"}
        report = load_json(target_root / "shareable" / "report.json")
        assert report["target"] == model
        assert report["status"] == "passed"
        assert report["artifact_mode"] == "minimal"
        assert report["private_raw_artifacts_retained"] is False
        assert report["commands"] and report["checks"]


@pytest.mark.windows_boundary_smoke
def test_live_plan_only_minimal_retains_only_shareable_reports():
    resource = "USB0::0x2A8D::0x1301::MY12345678::INSTR"
    result = run_wrapper(
        "scripts/live-cli-check.ps1", "-Target", "keysight-34461a",
        "-Connection", "usb", "-Resource", resource,
        "-Suite", "minimal", "-PlanOnly", "-SkipPreflight",
    )
    assert result.returncode == 0, result.stderr + result.stdout
    report_path = report_from_summary_output(result.stdout)
    run_root = report_path.parents[1]
    files = {p.relative_to(run_root).as_posix() for p in run_root.rglob("*") if p.is_file()}
    assert files == {"shareable/report.json", "shareable/summary.md"}
    report = load_json(report_path)
    assert report["artifact_mode"] == "minimal"
    assert report["private_raw_artifacts_retained"] is False
    assert report["status"] == "planned"
    assert report["plan_only"] is True and report["live_executed"] is False
    assert report["cases"] == []
    assert "runtime_evidence" not in report
    assert report["dry_runs"][0]["plan"]["read_path"] == "READ?"
    assert resource not in report_path.read_text(encoding="utf-8")



def test_live_minimal_confirmation_required_retains_two_reports():
    result = run_wrapper(
        "scripts/live-cli-check.ps1", "-Target", "keysight-34461a",
        "-Connection", "usb", "-Resource", "SIM::34461A",
        "-Suite", "minimal", stdin="",
    )
    assert result.returncode != 0
    report_path = report_from_summary_output(result.stdout + result.stderr)
    run_root = report_path.parents[1]
    files = {p.relative_to(run_root).as_posix() for p in run_root.rglob("*") if p.is_file()}
    assert files == {"shareable/report.json", "shareable/summary.md"}
    report = load_json(report_path)
    assert report["status"] == "confirmation_required"
    assert report["live_executed"] is False
    assert report["artifact_mode"] == "minimal"


def test_live_rejects_removed_stream_suite():
    result = run_wrapper("scripts/live-cli-check.ps1", "-Target", "keysight-34461a",
                         "-Connection", "usb", "-Resource", "SIM::34461A",
                         "-Suite", "stream", "-PlanOnly", "-SkipPreflight")
    assert result.returncode != 0


@pytest.mark.parametrize("target,count", [("keysight-34460a", 7), ("keysight-34461a", 10)])
def test_worker_streaming_plan_only_scopes_and_privacy(target, count):
    profile = find_instrument_profile_by_model(target)
    result = run_wrapper("scripts/live-cli-check.ps1", "-Target", target,
                         "-Connection", "usb", "-Resource", f"SIM::{profile.model}",
                         "-Suite", "worker-streaming", "-PlanOnly", "-SkipPreflight")
    assert result.returncode == 0, result.stdout + result.stderr
    path = report_from_summary_output(result.stdout)
    report = load_json(path)
    assert report["status"] == "planned" and report["live_executed"] is False
    assert report["cases"] == []
    assert len(report["dry_runs"]) == count
    assert len(report["not_run_cases"]) == count
    modes = set()
    for case in report["dry_runs"]:
        args = case["command"]["arguments"]
        assert "--streaming" in args and "--json" in args and "--dry-run" in args
        assert "--csv" in args
        assert case["plan"]["dry_run_writes_csv"] is False
        modes.add(args[args.index("--trigger-mode") + 1])
    expected = {"immediate", "software", "immediate-custom", "software-custom"}
    if target == "keysight-34461a":
        expected |= {"external", "external-custom"}
    assert modes == expected
    assert {item["status"] for item in report["unverified_observations"]} == {"not_run", "not_verified"}
    files = {p.relative_to(path.parents[1]).as_posix() for p in path.parents[1].rglob("*") if p.is_file()}
    assert files == {"shareable/report.json", "shareable/summary.md"}
    assert f"SIM::{profile.model}" not in path.read_text(encoding="utf-8")


def streaming_test_script(tmp_path: Path, body: str) -> Path:
    source = (REPO_ROOT / "scripts/live-cli-check.ps1").read_text(encoding="utf-8")
    functions = []
    for name in ("New-LiveCase", "Get-LiveCases", "New-StartArgs", "Add-StreamingObservation",
                 "Invoke-StreamingClient", "Invoke-StreamingStartProcess", "Invoke-LiveCase"):
        match = re.search(rf"(?ms)^function {name} \{{.*?(?=^function |\Z)", source)
        assert match, name
        functions.append(match.group())
    script = tmp_path / "streaming.ps1"
    script.write_text(
        "$ErrorActionPreference = 'Stop'\nSet-StrictMode -Version Latest\n"
        f"$RepoRoot = {ps_quote(REPO_ROOT)}\n$Python = {ps_quote(PYTHON)}\n"
        "$Resource = 'SIM::34461A'\n$DebugArtifacts = $false\n$resolvedVisaLibrary = ''\n"
        "$resolvedCliModel = '34461A'\n"
        f"$caseRoot = {ps_quote(tmp_path)}\n"
        f". {ps_quote(REPO_ROOT / 'scripts/_validation_helpers.ps1')}\n"
        "Add-RepoSrcToPythonPath -RepoRoot $RepoRoot\n"
        + "\n".join(functions) + "\n" + body,
        encoding="utf-8",
    )
    return script


@pytest.mark.parametrize("name", ["basic_immediate_current_dc", "basic_software_timer",
                                  "basic_software_trigger", "finite_software_monitor",
                                  "infinite_custom_software"])
def test_worker_streaming_simulated_control_and_finalization(tmp_path: Path, name):
    script = streaming_test_script(tmp_path, f"$selectedName = 'worker_streaming_{name}'\n" + r"""
$case = @(Get-LiveCases -SelectedSuite 'worker-streaming' -ResolvedTarget 'keysight-34461a' |
    Where-Object { $_.name -eq $selectedName })[0]
$case.mode_args += '--simulate'
$result = Invoke-LiveCase -Case $case -CaseDir $caseRoot -Port (Get-AvailableTcpPort) -CsvPath (Join-Path $caseRoot 'live.csv')
Write-Utf8NoBomText -LiteralPath (Join-Path $caseRoot 'result.json') -Text ($result | ConvertTo-Json -Depth 20)
""")
    result = run_wrapper_path(script)
    assert result.returncode == 0, result.stdout + result.stderr
    case = load_json(tmp_path / "result.json")
    assert case["status"] == "passed", case
    evidence = case["runtime_evidence"]["streaming"]
    assert evidence["transitions"] == ["active", "ended"]
    assert evidence["stdout_eof"]
    needs_manual_control = name not in ("basic_immediate_current_dc", "basic_software_timer")
    assert evidence["http_status_checked"] is needs_manual_control
    assert (evidence["software_triggers_sent"] > 0) is needs_manual_control
    assert evidence["sample_count"] == case["captured"] == case["csv_rows"]
    assert case["runtime_evidence"]["cleanup"]["unconfirmed"] is False
    if "infinite" in name:
        assert evidence["stop_requested"]
        assert case["runtime_evidence"]["summary"]["final_drain_complete"] is True
        assert case["runtime_evidence"]["summary"]["data_integrity"] == "unknown"


def test_worker_streaming_event_acceptance_including_stop_before_active(tmp_path: Path):
    ready = {"event": "ready", "stream": {"lifecycle": "run_bound"}}
    active = {"event": "status", "stream": {"lifecycle": "run_bound", "state": "active"}}
    ended = {"event": "status", "stream": {"lifecycle": "run_bound", "state": "ended"}}
    waiting = {"event": "status", "stream": {"lifecycle": "run_bound", "state": "waiting"}}
    sample = {"event": "sample", "captured": 1}
    summary = {"event": "summary", "captured": 1}
    scenarios = {
        "no_waiting_event": ([ready, active, sample, ended, summary], True),
        "stop_before_active": ([ready, waiting, ended, {**summary, "captured": 0}], True),
        "early_sample": ([ready, sample, active, ended, summary], False),
        "late_sample": ([ready, active, ended, sample, summary], False),
        "regression": ([ready, active, waiting], False),
        "wrong_run": ([ready, {**active, "run_id": "other"}], False),
        "missing_ended": ([ready, active, sample, summary], False),
        "wrong_count": ([ready, active, sample, ended, {**summary, "captured": 2}], False),
        "failure_with_tail": ([ready, {"event": "error"}, active, sample, ended, summary], False),
    }
    payload = [
        {"name": name, "events": [{"schema_version": 2, "run_id": "test-run", **event}
                                  for event in events]}
        for name, (events, _) in scenarios.items()
    ]
    (tmp_path / "events.json").write_text(json.dumps(payload), encoding="utf-8")
    script = streaming_test_script(tmp_path, r"""
$results = @()
foreach ($case in (Get-Content -LiteralPath (Join-Path $caseRoot 'events.json') -Raw | ConvertFrom-Json)) {
    $state = @{ run_id = $null; ready = $false; active = $false; phase = 'waiting'
        summary = $false; samples = 0; transitions = [System.Collections.Generic.List[string]]::new() }
    $accepted = $true
    foreach ($event in $case.events) {
        try { Add-StreamingObservation -State $state -Event $event }
        catch { $accepted = $false }
    }
    $results += @{ name = $case.name; accepted = $accepted; active = $state.active; phase = $state.phase }
}
Write-Utf8NoBomText -LiteralPath (Join-Path $caseRoot 'results.json') -Text ($results | ConvertTo-Json -Depth 8)
""")
    result = run_wrapper_path(script)
    assert result.returncode == 0, result.stdout + result.stderr
    for case in load_json(tmp_path / "results.json"):
        assert case["accepted"] is scenarios[case["name"]][1], case
        if case["name"] == "stop_before_active":
            assert case["active"] is False and case["phase"] == "ended"


@pytest.mark.parametrize("fault", ["missing_active", "forced", "malformed", "wrong_http_run",
                                  "http_failure", "http_stopping", "http_waiting", "http_ended",
                                  "http_invalid", "large_tail", "stopped_before_active",
                                  "missing_ended", "missing_summary", "exit_failure", "external"])
def test_worker_streaming_controlled_process_failures_and_external_gate(tmp_path: Path, fault):
    # The child never imports VISA. File signals stand in for control responses;
    # simulator tests above exercise the actual CLI HTTP clients.
    child = tmp_path / "worker.py"
    child.write_text(r'''
import json
from pathlib import Path
import sys
import time

fault, root = sys.argv[1], Path(sys.argv[2])
def emit(event, **fields):
    print(json.dumps(dict(schema_version=2, run_id="test-run", event=event, **fields)), flush=True)
def state(phase):
    emit("status", stream=dict(lifecycle="run_bound", state=phase))
emit("ready", stream=dict(lifecycle="run_bound"))
if fault == "malformed":
    print("invalid-json", flush=True)
if fault not in ("missing_active", "stopped_before_active"):
    state("active")
if fault == "forced":
    time.sleep(30)
elif fault in ("missing_active", "malformed", "wrong_http_run", "http_failure", "http_stopping",
               "http_waiting", "http_ended", "http_invalid", "large_tail"):
    deadline = time.monotonic() + 10
    while not (root / "stop").exists() and time.monotonic() < deadline:
        time.sleep(0.01)
elif fault == "external":
    time.sleep(0.3)
count = 1 if fault in ("external", "missing_ended", "missing_summary", "exit_failure") else 0
if fault == "large_tail":
    for _ in range(128):
        emit("message", message="x" * 1024)
if count:
    emit("sample", captured=1)
if fault != "missing_ended":
    state("ended")
if fault != "missing_summary":
    emit("summary", captured=count)
emit("message", message="cleanup tail")
sys.exit(3 if fault == "exit_failure" else 0)
''', encoding="utf-8")
    script = streaming_test_script(tmp_path, f"$fault = '{fault}'\n" + r"""
function Invoke-StreamingClient {
    param($Command, $Name, $Port, $OutDir)
    if ($Command -eq 'stop') { Write-Utf8NoBomText -LiteralPath (Join-Path $caseRoot 'stop') -Text 'stop' }
    $payload = @{ event = $Command; status = 'accepted'; run_id = 'test-run'
        ok = $true; fatal_error = $null; errors = 0; stopping = $false
        stream = @{ lifecycle = 'run_bound'; state = 'active' } }
    if ($fault -eq 'wrong_http_run') { $payload.run_id = 'other-run' }
    if ($fault -in @('http_failure', 'large_tail')) { $payload.ok = $false; $payload.fatal_error = 'test failure' }
    if ($fault -eq 'http_stopping') { $payload.stopping = $true }
    if ($fault -eq 'http_waiting') { $payload.stream.state = 'waiting' }
    if ($fault -eq 'http_ended') { $payload.stream.state = 'ended' }
    if ($fault -eq 'http_invalid') { $payload.stream.state = 'invalid' }
    return @{ name = $Name; success = $true; stdout_text = ($payload | ConvertTo-Json -Compress -Depth 5) }
}
$case = New-LiveCase -Name 'controlled' -ModeArgs @('--trigger-mode', 'software') -ExpectedCaptured 1 -SoftTriggerCount 1 -Streaming $true -TimeoutSeconds 3
if ($fault -eq 'external') { $case.soft_trigger_count = 0; $case.external_edges = 1 }
if ($fault -in @('http_waiting', 'http_ended', 'http_invalid', 'http_stopping')) { $case.external_edges = 1 }
if ($fault -eq 'stopped_before_active') { $case.soft_trigger_count = 0; $case.expected_captured = 0 }
$graceMs = if ($fault -eq 'large_tail') { 5000 } else { 300 }
$activeMs = if ($fault -eq 'missing_active') { 300 } else { 2000 }
$result = Invoke-StreamingStartProcess -Case $case -Arguments @('-u', (Join-Path $caseRoot 'worker.py'), $fault, $caseRoot) `
    -StdOutPath (Join-Path $caseRoot 'live.jsonl') -StdErrPath (Join-Path $caseRoot 'live.stderr.txt') `
    -Port 0 -OutDir $caseRoot -ActiveTimeoutMs $activeMs -StopGracePeriodMs $graceMs
Write-Utf8NoBomText -LiteralPath (Join-Path $caseRoot 'result.json') -Text ($result | ConvertTo-Json -Depth 20)
""")
    result = run_wrapper_path(script)
    assert result.returncode == 0, result.stdout + result.stderr
    case = load_json(tmp_path / "result.json")
    assert case["success"] is (fault in ("external", "stopped_before_active")), case
    evidence = case["streaming_evidence"]
    if fault in ("wrong_http_run", "http_failure", "http_stopping", "http_waiting",
                 "http_ended", "http_invalid", "large_tail"):
        assert any(command["name"] == "controlled_live_soft_status" for command in case["client_commands"])
    if fault in ("missing_active", "malformed", "wrong_http_run", "http_failure", "http_stopping",
                 "http_waiting", "http_ended", "http_invalid", "large_tail"):
        assert evidence["software_triggers_sent"] == 0
        assert evidence["stop_requested"]
        assert (tmp_path / "stop").exists()
        assert "cleanup tail" in (tmp_path / "live.jsonl").read_text(encoding="utf-8")
        assert not case["forced_termination"]
    if fault in ("http_waiting", "http_ended", "http_invalid", "http_stopping"):
        assert not evidence["external_prompt_after_active"]
        assert "external trigger edge(s) now" not in result.stdout
        assert evidence["http_status_checked"] is (fault == "http_ended")
    if fault == "missing_active":
        assert case["timed_out"] and not case["forced_termination"]
    if fault == "forced":
        assert case["forced_termination"] and case["cleanup_unconfirmed"]
        assert case["duration_seconds"] < 10
    if fault == "external":
        assert evidence["external_prompt_after_active"]
        assert "Apply 1 external trigger edge(s) now" in result.stdout
    if fault == "stopped_before_active":
        assert not evidence["active"] and evidence["sample_count"] == 0
        assert evidence["ended"] and evidence["summary"] and evidence["stdout_eof"]
        assert case["exit_code"] == 0


@pytest.mark.parametrize("fault", ["slow_stop", "stop_failure", "stop_timeout"])
def test_worker_streaming_controlled_stop_client_and_cleanup_deadlines(tmp_path: Path, fault):
    # A separate Stop client delivers its request late; only then can cleanup start.
    child = tmp_path / "worker_client.py"
    child.write_text(r'''
import json
from pathlib import Path
import sys
import time

role, fault, root = sys.argv[1], sys.argv[2], Path(sys.argv[3])
if role == "client":
    (root / "stop-requested").write_text("stop", encoding="utf-8")
    time.sleep(30 if fault == "stop_timeout" else 1.5)
    (root / "stop-delivered").write_text("stop", encoding="utf-8")
    print(json.dumps(dict(event="stop", status="accepted" if fault == "slow_stop" else "rejected")))
    sys.exit(0 if fault == "slow_stop" else 1)

def emit(event, **fields):
    print(json.dumps(dict(schema_version=2, run_id="test-run", event=event, **fields)), flush=True)

emit("ready", stream=dict(lifecycle="run_bound"))
emit("status", stream=dict(lifecycle="run_bound", state="active"))
if fault != "slow_stop":
    time.sleep(30)
else:
    deadline = time.monotonic() + 10
    while not (root / "stop-delivered").exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    time.sleep(0.3)
emit("sample", captured=1)
emit("status", stream=dict(lifecycle="run_bound", state="ended"))
emit("summary", captured=1)
emit("message", message="cleanup tail")
print("cleanup stderr", file=sys.stderr, flush=True)
''', encoding="utf-8")
    script = streaming_test_script(tmp_path, f"$fault = '{fault}'\n" + r"""
function Invoke-StreamingClient {
    param($Command, $Name, $Port, $OutDir)
    if ($Command -eq 'stop') {
        $clientTimeout = if ($fault -eq 'stop_timeout') { 1000 } else { 5000 }
        return Invoke-CapturedCommand -Name $Name -FilePath $Python `
            -Arguments @('-u', (Join-Path $caseRoot 'worker_client.py'), 'client', $fault, $caseRoot) `
            -StdOutPath (Join-Path $caseRoot 'client.json') -StdErrPath (Join-Path $caseRoot 'client.stderr.txt') `
            -CaptureInMemory -ProcessTimeoutMs $clientTimeout
    }
    $payload = @{ event = 'status'; run_id = 'test-run'; ok = $true
        fatal_error = $null; errors = 0; stopping = $false
        stream = @{ lifecycle = 'run_bound'; state = 'active' } }
    return @{ name = $Name; success = $true; stdout_text = ($payload | ConvertTo-Json -Compress -Depth 5) }
}
$case = New-LiveCase -Name 'controlled' -ModeArgs @('--trigger-mode', 'immediate-custom') `
    -ExpectedCaptured 1 -Streaming $true -PlannedStopAfterSeconds 1 -TimeoutSeconds 5
$result = Invoke-StreamingStartProcess -Case $case `
    -Arguments @('-u', (Join-Path $caseRoot 'worker_client.py'), 'worker', $fault, $caseRoot) `
    -StdOutPath (Join-Path $caseRoot 'live.jsonl') -StdErrPath (Join-Path $caseRoot 'live.stderr.txt') `
    -Port 0 -OutDir $caseRoot -StopGracePeriodMs 1000
Write-Utf8NoBomText -LiteralPath (Join-Path $caseRoot 'result.json') -Text ($result | ConvertTo-Json -Depth 20)
""")
    result = run_wrapper_path(script)
    assert result.returncode == 0, result.stdout + result.stderr
    case = load_json(tmp_path / "result.json")
    evidence = case["streaming_evidence"]
    assert evidence["active"] and evidence["http_status_checked"] and evidence["stop_requested"]
    assert (tmp_path / "stop-requested").exists()
    stops = [command for command in case["client_commands"] if command["name"] == "controlled_stop"]
    assert len(stops) == 1
    stop = stops[0]
    assert stop["timed_out"] is (fault == "stop_timeout")
    assert case["duration_seconds"] < 10, case
    assert evidence["stdout_eof"]
    if fault == "slow_stop":
        assert stop["success"] and stop["duration_seconds"] >= 1.5
        assert case["success"] and not case["forced_termination"] and not case["cleanup_unconfirmed"], case
        assert evidence["ended"] and evidence["summary"] and evidence["sample_count"] == 1
        assert case["exit_code"] == 0
        assert "cleanup tail" in (tmp_path / "live.jsonl").read_text(encoding="utf-8")
        assert "cleanup stderr" in (tmp_path / "live.stderr.txt").read_text(encoding="utf-8")
    else:
        assert not stop["success"] and not case["success"]
        assert case["forced_termination"] and case["cleanup_unconfirmed"]
        assert case["duration_seconds"] >= stop["duration_seconds"] + 1
