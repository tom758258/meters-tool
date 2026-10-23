from __future__ import annotations

import json
from pathlib import Path

import pytest

from meters_tool_cli._runtime_output import CliEventEmitter
from meters_tool_core.command import (
    CommandValidationError,
    parse_command_envelope_json,
    parse_stop_request_json,
)

_FIXTURES = Path(__file__).with_name("fixtures")
_RAW = json.loads((_FIXTURES / "meters_worker_v3_raw_cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("raw", _RAW["valid_command"])
def test_v3_command_accepts_valid_raw_tokens(raw):
    assert parse_command_envelope_json(raw) is not None


@pytest.mark.parametrize("raw", _RAW["invalid_command"])
def test_v3_command_rejects_invalid_raw_tokens(raw):
    with pytest.raises(CommandValidationError):
        parse_command_envelope_json(raw)


@pytest.mark.parametrize("raw", _RAW["valid_stop"])
def test_v3_stop_accepts_valid_raw_tokens(raw):
    assert parse_stop_request_json(raw) is None


@pytest.mark.parametrize("raw", _RAW["invalid_stop"])
def test_v3_stop_rejects_invalid_raw_tokens(raw):
    with pytest.raises(CommandValidationError):
        parse_stop_request_json(raw)


def test_v3_machine_events_match_local_schema_required_fields():
    schema = json.loads((_FIXTURES / "meters_worker_v3_schema.json").read_text(encoding="utf-8"))
    output: list[str] = []
    emitter = CliEventEmitter(print_fn=output.append, output_format="jsonl")
    emitter.ready("127.0.0.1", 8765, run_id="sim-run")
    emitter.status("observed", run_id="sim-run")
    emitter.summary(0, 0, ok=True, run_id="sim-run")

    for line in output:
        event = json.loads(line)
        definition = schema["$defs"][event["event"]]
        assert all(key in event for key in definition["required"])
        assert type(event["schema_version"]) is int and event["schema_version"] == 3
        assert event["run_id"] == "sim-run"
        assert event["event"] == definition["properties"]["event"]["const"]
    assert json.loads(output[0])["features"] == {}
    assert json.loads(output[-1])["fatal_error"] is None
    assert json.loads(output[-1])["exit_code"] == 0
