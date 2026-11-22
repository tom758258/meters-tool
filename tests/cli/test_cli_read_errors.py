import json
from unittest.mock import Mock

import pytest

from meters_tool_cli.cli import main


@pytest.mark.parametrize(("mode", "reads"), [("--simulate", 1), ("--dry-run", 0)])
def test_read_errors_machine_mode_emits_one_result_without_visa(monkeypatch, capsys, mode, reads):
    factory = Mock(side_effect=AssertionError("unexpected VISA I/O"))
    monkeypatch.setattr("meters_tool_core.diagnostics._create_resource_manager", factory)
    assert main(["read-errors", mode, "--model", "34461A", "--json"]) == 0
    stdout, stderr = capsys.readouterr()
    assert not stderr
    result = json.loads(stdout)
    assert result["schema_version"] == 2
    assert result["command"] == "read-errors"
    assert result["reads"] == reads
    assert result["max_reads"] == 20
    assert result["queue_cleared"] is (reads == 1)
    assert result["errors"] == []
    factory.assert_not_called()


def test_read_errors_text_reports_entry_and_limit(monkeypatch, capsys):
    factory = Mock()
    instrument = factory.return_value.open_resource.return_value
    instrument.query.side_effect = [
        "Keysight Technologies,34461A,FAKE,1.0", '-222,"Data out of range"'
    ]
    monkeypatch.setattr("meters_tool_core.diagnostics._create_resource_manager", factory)
    resource = "TCPIP::meter.example::INSTR"
    assert main(["read-errors", "--resource", resource, "--visa-library", "@py", "--max-reads", "1"]) == 0
    assert "-222: Data out of range" in capsys.readouterr().out
    factory.assert_called_once_with("@py")
    factory.return_value.open_resource.assert_called_once_with(resource)


@pytest.mark.parametrize("options", [[], ["--json"]], ids=["text", "json"])
def test_read_errors_keeps_consumed_entry_on_failed_query(monkeypatch, capsys, options):
    factory = Mock()
    factory.return_value.open_resource.return_value.query.side_effect = [
        "Keysight Technologies,34461A,FAKE,1.0", '-113,"Undefined header"', TimeoutError("timed out")
    ]
    monkeypatch.setattr("meters_tool_core.diagnostics._create_resource_manager", factory)
    assert main(["read-errors", "--resource", "USB::FAKE::INSTR", "--max-reads", "3", *options]) == 3
    stdout, stderr = capsys.readouterr()
    if options:
        assert not stderr
        result = json.loads(stdout)
        assert result["event"] == result["status"] == "error"
        assert result["exit_code"] == 3
        assert "timed out" in result["message"]
        partial = result["partial_result"]
        assert partial["reads"] == 1
        assert partial["max_reads"] == 3
        assert partial["termination"] == "failed"
        assert partial["queue_cleared"] is False
        assert partial["errors"] == [{"code": -113, "message": "Undefined header"}]
    else:
        assert "-113: Undefined header" in stdout
        assert "1/3" in stderr
        assert "timed out" in stderr


@pytest.mark.parametrize(
    "args", [[], ["--resource", "USB::FAKE::INSTR", "--max-reads", "1.5"]]
)
def test_read_errors_validation_emits_one_error_without_visa(monkeypatch, capsys, args):
    factory = Mock(side_effect=AssertionError("unexpected VISA I/O"))
    monkeypatch.setattr("meters_tool_core.diagnostics._create_resource_manager", factory)
    assert main(["read-errors", "--json", *args]) == 2
    stdout, stderr = capsys.readouterr()
    assert not stderr
    assert json.loads(stdout)["exit_code"] == 2
    factory.assert_not_called()
