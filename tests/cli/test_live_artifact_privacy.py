from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
POWERSHELL = shutil.which("powershell.exe")
VALIDATION_HELPER = REPO_ROOT / "scripts" / "_validation_helpers.ps1"
PRIVACY_HELPER = REPO_ROOT / "scripts" / "_artifact_privacy.ps1"


def ps_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def run_privacy_command(body: str) -> subprocess.CompletedProcess[str]:
    if POWERSHELL is None:
        pytest.skip("powershell.exe is required for artifact privacy tests")
    command = f". {ps_quote(VALIDATION_HELPER)}; . {ps_quote(PRIVACY_HELPER)}; {body}"
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-Command", command],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def privacy_context(
    tmp_path: Path,
    resource: str = "USB0::1::2::SERIAL12345::INSTR",
    connection: str = "usb",
) -> str:
    run_root = tmp_path / "run"
    private = run_root / "private"
    shareable = run_root / "shareable"
    private.mkdir(parents=True, exist_ok=True)
    shareable.mkdir(parents=True, exist_ok=True)
    return (
        "@{"
        f"RunRoot={ps_quote(run_root)};PrivateRoot={ps_quote(private)};"
        f"ShareableRoot={ps_quote(shareable)};RepoRoot={ps_quote(REPO_ROOT)};"
        f"Resource={ps_quote(resource)};Connection={ps_quote(connection)};"
        f"SensitiveValues=@(Get-DistinctiveSensitiveTokens -Resource {ps_quote(resource)})"
        "}"
    )


def private_report_payload(
    private: Path, resource: str, *, diagnostics: list[dict] | None = None
) -> dict:
    return {
        "schema_version": "1.1",
        "kind": "meters_tool_live_validation",
        "artifact_visibility": "private",
        "candidate_evidence_only": True,
        "promotes_live_support": False,
        "private_raw_artifacts_retained": True,
        "redaction_applied": False,
        "redaction_version": 1,
        "target": "keysight-34461a",
        "model_id": "keysight-34461a",
        "expected_model": "34461A",
        "connection": "lan",
        "backend": "system_visa",
        "suite": "frequency-period",
        "resource": resource,
        "package_version": "1.6.0",
        "git_head": "synthetic",
        "validation_mode": "live",
        "output_dir": str(private),
        "artifact_paths": {},
        "status": "passed",
        "plan_only": False,
        "live_executed": True,
        "cases": [],
        "dry_runs": [],
        "scpi_diagnostics": diagnostics or [],
        "commands": [],
    }


@pytest.mark.parametrize(
    ("secret", "expected"),
    [
        ("private host 192.168.1.50", "<redacted-ip>"),
        ("private host 10.2.3.4", "<redacted-ip>"),
        ("private host 172.16.0.1", "<redacted-ip>"),
        ("private host 172.20.10.5", "<redacted-ip>"),
        ("private host 172.31.255.254", "<redacted-ip>"),
        ("link-local host 169.254.8.9", "<redacted-ip>"),
        ("Keysight Technologies,34461A,SERIAL12345,A.03.03", "<redacted-idn>"),
        ("Agilent Technologies,34461A,SERIAL12345,A.03.03", "<redacted-idn>"),
        ("KEYSIGHT,34461A,DISTINCTIVE123,A.03.03", "<redacted-idn>"),
        ("AGILENT,34461A,DISTINCTIVE123,A.03.03", "<redacted-idn>"),
        (r"C:\Users\Alice\private\artifact.json", "<redacted-path>"),
        ("/home/alice/private/artifact.json", "<redacted-path>"),
        ("/Users/alice/private/artifact.json", "<redacted-path>"),
    ],
)
def test_free_form_redaction_covers_network_idn_and_personal_paths(
    tmp_path: Path, secret: str, expected: str
):
    context = privacy_context(tmp_path)
    result = run_privacy_command(
        f"$c={context}; Protect-ArtifactText -Text {ps_quote(secret)} "
        "-Resource $c.Resource -RepoRoot $c.RepoRoot -PrivateRoot $c.PrivateRoot "
        "-SensitiveValues $c.SensitiveValues"
    )
    assert result.returncode == 0, result.stderr
    assert secret not in result.stdout
    assert expected in result.stdout


def test_tcpip_hostname_is_redacted_when_detached_from_resource(tmp_path: Path):
    resource = "TCPIP0::meter-lab.local::inst0::INSTR"
    context = privacy_context(tmp_path, resource, "lan")
    result = run_privacy_command(
        f"$c={context}; Protect-ArtifactText -Text 'Could not connect to meter-lab.local' "
        "-Resource $c.Resource -RepoRoot $c.RepoRoot -PrivateRoot $c.PrivateRoot "
        "-SensitiveValues $c.SensitiveValues"
    )
    assert result.returncode == 0, result.stderr
    assert "meter-lab.local" not in result.stdout
    assert "Could not connect to <redacted>" in result.stdout


def test_short_tcpip_hostname_redaction_uses_token_boundaries(tmp_path: Path):
    resource = "TCPIP0::dmm01::inst0::INSTR"
    context = privacy_context(tmp_path, resource, "lan")
    text = "\n".join(
        [
            resource,
            "Could not connect to dmm01",
            "Could not connect to DMM01",
            "Socket dmm01:5025 refused",
            "Host (dmm01) unavailable",
            "prefixdmm01suffix",
            "collaborate",
        ]
    )
    result = run_privacy_command(
        f"$c={context}; Protect-ArtifactText -Text {ps_quote(text)} "
        "-Resource $c.Resource -RepoRoot $c.RepoRoot -PrivateRoot $c.PrivateRoot "
        "-SensitiveValues $c.SensitiveValues"
    )
    assert result.returncode == 0, result.stderr
    assert resource not in result.stdout
    assert "Could not connect to dmm01" not in result.stdout
    assert "Could not connect to DMM01" not in result.stdout
    assert "Socket dmm01:5025 refused" not in result.stdout
    assert "Host (dmm01) unavailable" not in result.stdout
    assert "prefixdmm01suffix" in result.stdout
    assert "collaborate" in result.stdout


def test_three_character_hostname_does_not_redact_inside_words(tmp_path: Path):
    resource = "TCPIP0::lab::inst0::INSTR"
    context = privacy_context(tmp_path, resource, "lan")
    result = run_privacy_command(
        f"$c={context}; Protect-ArtifactText -Text 'lab collaborate (LAB)' "
        "-Resource $c.Resource -RepoRoot $c.RepoRoot -PrivateRoot $c.PrivateRoot "
        "-SensitiveValues $c.SensitiveValues"
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "<redacted> collaborate (<redacted>)"


@pytest.mark.parametrize(
    "resource",
    [
        "TCPIP0::0::inst0::INSTR",
        "TCPIP0::localhost::inst0::INSTR",
        "TCPIP0::localhost.localdomain::inst0::INSTR",
        "TCPIP0::0.0.0.0::inst0::INSTR",
        "TCPIP0::127.0.0.1::inst0::INSTR",
        "TCPIP0::::1::inst0::INSTR",
        "TCPIP0::inst0::INSTR",
        "TCPIP0::instr::inst0::INSTR",
        "TCPIP0::socket::inst0::INSTR",
        "TCPIP0::hislip0::INSTR",
        "TCPIP0::tcpip::inst0::INSTR",
        "TCPIP0::tcpip0::inst0::INSTR",
    ],
)
def test_tcpip_reserved_tokens_are_not_sensitive_values(resource: str):
    result = run_privacy_command(
        f"@(Get-DistinctiveSensitiveTokens -Resource {ps_quote(resource)}) "
        "| ConvertTo-Json -Compress"
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() in {"", "null"}


def test_structured_redaction_preserves_safe_values_and_numeric_zero(tmp_path: Path):
    resource = "USB0::1::2::0::INSTR"
    context = privacy_context(tmp_path, resource)
    python_path = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    body = (
        f"$c={context}; $value=[ordered]@{{"
        f"resource={ps_quote(resource)};serial='DISTINCTIVE123';idn='Keysight Technologies,34461A,DISTINCTIVE123,A.03.03';"
        f"firmware='1.0';measurement=0.05;exit_code=0;captured=0;ok=$true;python={ps_quote(python_path)};"
        "nested=[ordered]@{resource_name='secret';path='C:\\Users\\Alice\\file.json';trigger_metadata=[ordered]@{note='secret'}}"
        "}; $safe=ConvertTo-ShareableArtifactValue -Value $value -RunRoot $c.RunRoot -PrivateRoot $c.PrivateRoot "
        "-RepoRoot $c.RepoRoot -Resource $c.Resource -Connection $c.Connection -SensitiveValues $c.SensitiveValues; "
        "$safe | ConvertTo-Json -Compress -Depth 10"
    )
    result = run_privacy_command(body)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["resource"] == "usb:<redacted-resource>"
    assert payload["serial"] == "<redacted>"
    assert payload["idn"] == "<redacted-idn>"
    assert payload["firmware"] == "1.0"
    assert payload["measurement"] == 0.05
    assert payload["exit_code"] == payload["captured"] == 0
    assert payload["ok"] is True
    assert payload["python"] == ".venv/Scripts/python.exe"
    assert payload["nested"]["resource_name"] == "usb:<redacted-resource>"
    assert payload["nested"]["path"] == "<redacted-path>"
    assert payload["nested"]["trigger_metadata"] == "<redacted-trigger-metadata>"


def test_read_response_is_redacted_but_scpi_error_evidence_is_preserved(tmp_path: Path):
    resource = "TCPIP0::meter-lab.local::inst0::INSTR"
    context = privacy_context(tmp_path, resource, "lan")
    private = tmp_path / "run" / "private"
    shareable = tmp_path / "run" / "shareable"
    diagnostic = {
        "measurement": "frequency",
        "firmware_revision": "A.03.03",
        "status": "passed",
        "read": {
            "command": "READ?",
            "operation": "query",
            "response": "98765.4321",
            "transport_error": None,
            "system_error_responses": [
                {
                    "raw": '+0,"No error"',
                    "code": 0,
                    "message": "No error",
                    "is_error": False,
                }
            ],
            "all_error_responses_zero": True,
        },
    }
    private_report = {
        "schema_version": "1.1",
        "kind": "meters_tool_live_validation",
        "artifact_visibility": "private",
        "candidate_evidence_only": True,
        "promotes_live_support": False,
        "private_raw_artifacts_retained": True,
        "redaction_applied": False,
        "redaction_version": 1,
        "target": "keysight-34461a",
        "model_id": "keysight-34461a",
        "expected_model": "34461A",
        "connection": "lan",
        "backend": "system_visa",
        "suite": "frequency-period",
        "resource": resource,
        "package_version": "1.6.0",
        "git_head": "synthetic",
        "validation_mode": "live",
        "output_dir": str(private),
        "artifact_paths": {},
        "status": "passed",
        "plan_only": False,
        "live_executed": True,
        "cases": [],
        "dry_runs": [],
        "scpi_diagnostics": [diagnostic],
        "commands": [],
    }
    (private / "diagnostic.json").write_text(
        json.dumps(diagnostic), encoding="utf-8"
    )
    (private / "report.json").write_text(
        json.dumps(private_report), encoding="utf-8"
    )
    (private / "summary.md").write_text("private summary", encoding="utf-8")
    result = run_privacy_command(
        f"$c={context}; $report=Get-Content -LiteralPath {ps_quote(private / 'report.json')} -Raw | ConvertFrom-Json; "
        "[void](New-ShareableArtifactSet -PrivateReport $report -RunRoot $c.RunRoot "
        "-PrivateRoot $c.PrivateRoot -ShareableRoot $c.ShareableRoot -RepoRoot $c.RepoRoot "
        "-Resource $c.Resource -Connection $c.Connection)"
    )
    assert result.returncode == 0, result.stderr

    shareable_diagnostic = json.loads(
        (shareable / "diagnostic.json").read_text(encoding="utf-8")
    )
    shareable_report = json.loads(
        (shareable / "report.json").read_text(encoding="utf-8")
    )
    for payload in (shareable_diagnostic, shareable_report["scpi_diagnostics"][0]):
        assert payload["read"]["response"] == "<redacted-measurement-value>"
        assert payload["read"]["response_omitted"] is True
        assert payload["read"]["system_error_responses"] == [
            {
                "raw": '+0,"No error"',
                "code": 0,
                "message": "No error",
                "is_error": False,
            }
        ]
        assert payload["measurement"] == "frequency"
        assert payload["firmware_revision"] == "A.03.03"
        assert payload["status"] == "passed"
    assert "98765.4321" not in "\n".join(
        path.read_text(encoding="utf-8-sig")
        for path in shareable.rglob("*")
        if path.is_file()
    )


def test_json_artifacts_fail_closed_for_malformed_and_missing_input(tmp_path: Path):
    context = privacy_context(tmp_path)
    malformed = tmp_path / "run" / "private" / "malformed.json"
    malformed.write_text('{"resource":', encoding="utf-8")
    missing = tmp_path / "run" / "private" / "missing.json"
    malformed_out = tmp_path / "run" / "shareable" / "malformed.json"
    missing_out = tmp_path / "run" / "shareable" / "missing.json"
    result = run_privacy_command(
        f"$c={context}; Convert-PrivateJsonArtifact -SourcePath {ps_quote(malformed)} -DestinationPath {ps_quote(malformed_out)} -Context $c; "
        f"Convert-PrivateJsonArtifact -SourcePath {ps_quote(missing)} -DestinationPath {ps_quote(missing_out)} -Context $c"
    )
    assert result.returncode == 0, result.stderr
    malformed_payload = json.loads(malformed_out.read_text(encoding="utf-8"))
    missing_payload = json.loads(missing_out.read_text(encoding="utf-8"))
    assert malformed_payload["parse_status"] == "failed"
    assert malformed_payload["private_raw_artifact_retained"] is True
    assert missing_payload["parse_status"] == "missing"
    assert missing_payload["private_raw_artifact_retained"] is False
    assert '{"resource":' not in malformed_out.read_text(encoding="utf-8")


def test_nested_preflight_report_and_summary_are_safely_preserved(tmp_path: Path):
    resource = "TCPIP0::meter-lab.local::inst0::INSTR"
    context = privacy_context(tmp_path, resource, "lan")
    private = tmp_path / "run" / "private"
    shareable = tmp_path / "run" / "shareable"
    preflight = private / "preflight"
    preflight.mkdir()
    (private / "report.json").write_text(
        json.dumps(private_report_payload(private, resource)), encoding="utf-8"
    )
    (private / "summary.md").write_text(
        f"root private {resource}", encoding="utf-8"
    )
    (preflight / "report.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "resource": resource,
                "idn": "KEYSIGHT,34461A,DISTINCTIVE123,A.03.03",
                "path": r"C:\Users\Alice\private\preflight.json",
            }
        ),
        encoding="utf-8",
    )
    (preflight / "summary.md").write_text(
        "\n".join(
            [
                f"Resource: {resource}",
                "IDN: KEYSIGHT,34461A,DISTINCTIVE123,A.03.03",
                "Host: meter-lab.local 172.20.10.5",
                r"Path: C:\Users\Alice\private\preflight.json",
            ]
        ),
        encoding="utf-8",
    )
    result = run_privacy_command(
        f"$c={context}; $report=Get-Content -LiteralPath {ps_quote(private / 'report.json')} -Raw | ConvertFrom-Json; "
        "[void](New-ShareableArtifactSet -PrivateReport $report -RunRoot $c.RunRoot "
        "-PrivateRoot $c.PrivateRoot -ShareableRoot $c.ShareableRoot -RepoRoot $c.RepoRoot "
        "-Resource $c.Resource -Connection $c.Connection)"
    )
    assert result.returncode == 0, result.stderr
    nested_report_path = shareable / "preflight" / "report.json"
    nested_summary_path = shareable / "preflight" / "summary.md"
    assert nested_report_path.exists()
    assert nested_summary_path.exists()
    assert json.loads(nested_report_path.read_text(encoding="utf-8")) == {
        "status": "passed",
        "resource": "lan:<redacted-resource>",
        "idn": "<redacted-idn>",
        "path": "<redacted-path>",
    }
    nested_text = nested_summary_path.read_text(encoding="utf-8")
    for forbidden in (
        resource,
        "meter-lab.local",
        "172.20.10.5",
        "DISTINCTIVE123",
        r"C:\Users\Alice\private\preflight.json",
    ):
        assert forbidden not in nested_text
    root_shareable_report = json.loads(
        (shareable / "report.json").read_text(encoding="utf-8")
    )
    assert root_shareable_report["artifact_visibility"] == "shareable"
    assert "root private" not in (shareable / "summary.md").read_text(encoding="utf-8")


def test_jsonl_redaction_keeps_valid_lines_and_replaces_malformed_line(tmp_path: Path):
    context = privacy_context(tmp_path)
    source = tmp_path / "run" / "private" / "events.jsonl"
    destination = tmp_path / "run" / "shareable" / "events.jsonl"
    source.write_text(
        '{"event":"ready","trigger_metadata":{"operator":"secret"},"captured":0}\n'
        "raw malformed private line\n"
        '{"event":"summary","firmware":"1.0","captured":1}\n',
        encoding="utf-8",
    )
    result = run_privacy_command(
        f"$c={context}; Convert-PrivateJsonLinesArtifact -SourcePath {ps_quote(source)} "
        f"-DestinationPath {ps_quote(destination)} -Context $c"
    )
    assert result.returncode == 0, result.stderr
    events = [json.loads(line) for line in destination.read_text(encoding="utf-8").splitlines()]
    assert [event["event"] for event in events] == ["ready", "artifact_redaction", "summary"]
    assert events[0]["trigger_metadata"] == "<redacted-trigger-metadata>"
    assert events[0]["captured"] == 0
    assert events[2]["firmware"] == "1.0"
    assert "raw malformed" not in destination.read_text(encoding="utf-8")


def test_csv_evidence_omits_measurement_value_and_trigger_metadata(tmp_path: Path):
    private = tmp_path / "run" / "private"
    shareable = tmp_path / "run" / "shareable"
    private.mkdir(parents=True)
    shareable.mkdir(parents=True)
    csv_path = private / "live.csv"
    evidence_path = shareable / "csv-evidence.json"
    csv_path.write_text(
        "timestamp_utc_plus_8,measurement_type,value,unit,trigger_id,trigger_source,trigger_metadata,measurement_metadata,resource_id,status\n"
        '2026-01-01T00:00:00+08:00,current_dc,0.05,A,id,immediate,"{}","{}",USB::SECRET,ok\n',
        encoding="utf-8",
    )
    result = run_privacy_command(
        f"$case=[pscustomobject]@{{expected_captured=1}}; [void](New-CsvEvidence -SourcePath {ps_quote(csv_path)} "
        f"-DestinationPath {ps_quote(evidence_path)} -Case $case)"
    )
    assert result.returncode == 0, result.stderr
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["header_valid"] is True
    assert evidence["row_count"] == evidence["expected_row_count"] == 1
    assert evidence["measurement_type"] == "current_dc"
    assert evidence["unit"] == "A"
    assert evidence["value_omitted"] is True
    assert evidence["trigger_metadata_omitted"] is True
    assert "0.05" not in evidence_path.read_text(encoding="utf-8")
    assert "USB::SECRET" not in evidence_path.read_text(encoding="utf-8")
    assert not any(shareable.rglob("*.csv"))


def test_shareable_tree_forbidden_string_scan(tmp_path: Path):
    resource = "TCPIP0::dmm01::inst0::INSTR"
    context = privacy_context(tmp_path, resource, "lan")
    private = tmp_path / "run" / "private"
    shareable = tmp_path / "run" / "shareable"
    python_path = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    private_path = private / "case" / "raw.json"
    source = private / "evidence.txt"
    source.write_text(
        "\n".join(
            [
                resource,
                "Could not connect to dmm01",
                "Could not connect to DMM01",
                "KEYSIGHT,34461A,DISTINCTIVE123,A.03.03",
                "192.168.4.5",
                "172.20.10.5",
                str(REPO_ROOT),
                str(python_path),
                r"C:\Users\Alice\secret.txt",
                "/home/alice/secret.txt",
                "/Users/alice/secret.txt",
                str(private_path),
                "firmware=1.0 model=34461A measurement=0.05 measurement_type=current_dc unit=A row_count=1 exit_code=0 captured=0 status=failed",
            ]
        ),
        encoding="utf-8",
    )
    (private / "scpi.json").write_text(
        json.dumps(
            {
                "command": "READ?",
                "response": "98765.4321",
                "firmware": "1.0",
                "measurement": 0.05,
                "exit_code": 0,
                "captured": 0,
            }
        ),
        encoding="utf-8",
    )
    (private / "unknown.bin").write_bytes(b"raw private binary")
    result = run_privacy_command(f"$c={context}; Copy-ShareableArtifactTree -Context $c")
    assert result.returncode == 0, result.stderr
    tree_text = "\n".join(
        path.read_text(encoding="utf-8-sig")
        for path in shareable.rglob("*")
        if path.is_file()
    )
    for forbidden in (
        resource,
        "dmm01",
        "DMM01",
        "DISTINCTIVE123",
        "KEYSIGHT,34461A,DISTINCTIVE123,A.03.03",
        "192.168.4.5",
        "172.20.10.5",
        "98765.4321",
        str(REPO_ROOT),
        str(python_path),
        r"C:\Users\Alice\secret.txt",
        "/home/alice/secret.txt",
        "/Users/alice/secret.txt",
        str(private_path),
    ):
        assert forbidden not in tree_text
    for safe in (
        "firmware=1.0",
        "model=34461A",
        "measurement=0.05",
        "measurement_type=current_dc",
        "unit=A",
        "row_count=1",
        "exit_code=0",
        "captured=0",
        "status=failed",
    ):
        assert safe in tree_text
    assert not (shareable / "unknown.bin").exists()
