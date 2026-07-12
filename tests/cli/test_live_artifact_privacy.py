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


def privacy_context(tmp_path: Path, resource: str = "USB0::1::2::SERIAL12345::INSTR") -> str:
    run_root = tmp_path / "run"
    private = run_root / "private"
    shareable = run_root / "shareable"
    private.mkdir(parents=True, exist_ok=True)
    shareable.mkdir(parents=True, exist_ok=True)
    return (
        "@{"
        f"RunRoot={ps_quote(run_root)};PrivateRoot={ps_quote(private)};"
        f"ShareableRoot={ps_quote(shareable)};RepoRoot={ps_quote(REPO_ROOT)};"
        f"Resource={ps_quote(resource)};Connection='usb';"
        f"SensitiveValues=@(Get-DistinctiveSensitiveTokens -Resource {ps_quote(resource)})"
        "}"
    )


@pytest.mark.parametrize(
    ("secret", "expected"),
    [
        ("private host 192.168.1.50", "<redacted-ip>"),
        ("private host 10.2.3.4", "<redacted-ip>"),
        ("link-local host 169.254.8.9", "<redacted-ip>"),
        ("Keysight Technologies,34461A,SERIAL12345,A.03.03", "<redacted-idn>"),
        ("Agilent Technologies,34461A,SERIAL12345,A.03.03", "<redacted-idn>"),
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
    assert json.loads(malformed_out.read_text(encoding="utf-8"))["parse_status"] == "failed"
    assert json.loads(missing_out.read_text(encoding="utf-8"))["parse_status"] == "missing"
    assert '{"resource":' not in malformed_out.read_text(encoding="utf-8")


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
    resource = "USB0::1::2::DISTINCTIVE123::INSTR"
    context = privacy_context(tmp_path, resource)
    private = tmp_path / "run" / "private"
    shareable = tmp_path / "run" / "shareable"
    python_path = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    private_path = private / "case" / "raw.json"
    source = private / "evidence.txt"
    source.write_text(
        "\n".join(
            [
                resource,
                "DISTINCTIVE123",
                "Keysight Technologies,34461A,DISTINCTIVE123,A.03.03",
                "192.168.4.5",
                str(REPO_ROOT),
                str(python_path),
                r"C:\Users\Alice\secret.txt",
                "/home/alice/secret.txt",
                "/Users/alice/secret.txt",
                str(private_path),
                "firmware=1.0 model=34461A measurement_type=current_dc unit=A row_count=1 exit_code=0 status=passed",
            ]
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
        "DISTINCTIVE123",
        "Keysight Technologies,34461A,DISTINCTIVE123,A.03.03",
        "192.168.4.5",
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
        "measurement_type=current_dc",
        "unit=A",
        "row_count=1",
        "exit_code=0",
        "status=passed",
    ):
        assert safe in tree_text
    assert not (shareable / "unknown.bin").exists()
