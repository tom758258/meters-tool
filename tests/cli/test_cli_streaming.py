from __future__ import annotations

import json
import queue
import subprocess
import sys
import time
from pathlib import Path

import pytest

from meters_tool_cli.cli import build_parser, cmd_start
from meters_tool_core.session import NoOpStartRunControls

from cli_command_helpers import FakeStartServer
from test_cli_worker_subprocess import (
    read_event_until, run_client, start_stdout_reader, subprocess_env,
)


@pytest.mark.parametrize("options,enabled", [
    ([], True), (["--streaming"], False), (["--streaming", "--no-csv"], False),
    (["--streaming", "--csv", "chosen.csv"], True), (["--no-csv"], False),
    (["--csv", "chosen.csv"], True),
    (["--streaming", "--csv-format", "full", "--csv-time-columns", "elapsed"], False),
])
def test_streaming_dry_run_csv_defaults_are_independent_of_jsonl(options, enabled, capsys):
    args = build_parser().parse_args([
        "start-trigger-record", "--resource", "SIM::34461A", "--dry-run", "--json",
        "--trigger-mode", "immediate", "--max-samples", "1", *options,
    ])
    assert cmd_start(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["event"] == "dry_run"
    assert result["csv_enabled"] is enabled
    assert (result["csv_path"] is not None) is enabled
    assert result["dry_run_writes_csv"] is False
    assert "stream" not in result
    assert "run_id" not in result


@pytest.mark.parametrize("csv_path,options", [
    ("", []),
    ("   ", ["--dry-run"]),
    ("   ", ["--streaming"]),
    ("", ["--streaming", "--dry-run"]),
])
def test_blank_csv_rejected_before_profile_resolution(csv_path, options, monkeypatch, capsys, tmp_path):
    def unexpected(*args, **kwargs):
        raise AssertionError("must reject before resolving a live profile")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("meters_tool_cli.cli.resolve_start_profile", unexpected)
    args = build_parser().parse_args([
        "start-trigger-record", "--resource", "FAKE::UNOPENED", "--json",
        "--csv", csv_path, *options,
    ])
    assert cmd_start(args) == 2
    output = capsys.readouterr()
    error = json.loads(output.out)
    assert error["event"] == "error"
    assert error["exit_code"] == 2
    assert "--csv" in error["message"]
    assert "run_id" not in error
    assert list(tmp_path.iterdir()) == []


def test_streaming_text_rejected_before_profile_resolution(monkeypatch, capsys):
    def unexpected(*args, **kwargs):
        raise AssertionError("must reject before resolving a live profile")

    monkeypatch.setattr("meters_tool_cli.cli.resolve_start_profile", unexpected)
    args = build_parser().parse_args([
        "start-trigger-record", "--resource", "FAKE::UNOPENED", "--streaming",
    ])
    assert cmd_start(args) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "jsonl" in output.err


def test_streaming_explicit_csv_writes_only_requested_file(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("meters_tool_cli.cli.CliStartRunControls", NoOpStartRunControls)
    monkeypatch.setattr("meters_tool_core.runner.SoftwareTriggerAdapter", FakeStartServer)
    args = build_parser().parse_args([
        "start-trigger-record", "--resource", "SIM::34461A", "--simulate",
        "--streaming", "--json", "--csv", "chosen.csv",
        "--trigger-mode", "immediate", "--max-samples", "1",
    ])
    assert cmd_start(args) == 0
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    summary = next(e for e in events if e["event"] == "summary")
    assert summary["ok"] is True
    assert summary["captured"] == 1
    assert list(tmp_path.iterdir()) == [tmp_path / "chosen.csv"]
    assert len((tmp_path / "chosen.csv").read_text(encoding="utf-8").splitlines()) == 2


@pytest.mark.parametrize("streaming", [False, True])
def test_runtime_warnings_and_ready_share_stream_state_only_when_opted_in(
    streaming, monkeypatch, capsys, tmp_path,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("meters_tool_cli.cli.generate_buffer_overflow_warnings", lambda *a, **kw: ["test warning"])
    monkeypatch.setattr("meters_tool_cli.cli.CliStartRunControls", NoOpStartRunControls)
    monkeypatch.setattr("meters_tool_core.runner.SoftwareTriggerAdapter", FakeStartServer)
    args = build_parser().parse_args([
        "start-trigger-record", "--resource", "SIM::34461A", "--simulate",
        "--status-format", "jsonl", "--trigger-mode", "immediate", "--max-samples", "1",
        *(["--streaming"] if streaming else ["--no-csv"]),
    ])
    assert cmd_start(args) == 0
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert list(tmp_path.iterdir()) == []
    statuses = [e for e in events if e["event"] == "status"]
    ready = next(e for e in events if e["event"] == "ready")
    if streaming:
        assert ready["stream"] == {"lifecycle": "run_bound"}
        assert statuses[0]["stream"]["state"] == "waiting"
        assert statuses[-1]["stream"]["state"] == "ended"
        assert all(e["stream"]["lifecycle"] == "run_bound" for e in statuses)
        assert all(e["run_id"] == ready["run_id"] for e in statuses)
    else:
        assert all("stream" not in e for e in events)


@pytest.mark.parametrize("mode", ["software", "software-custom"])
def test_streaming_worker_active_before_first_trigger_and_http_matches(mode, tmp_path: Path):
    count_args = ["--trigger-count", "1", "--sample-count", "1"] if mode.endswith("custom") else ["--max-samples", "1"]
    process = subprocess.Popen(
        [sys.executable, "-m", "meters_tool_cli", "start-trigger-record",
         "--resource", "SIM::34461A", "--simulate", "--streaming", "--json",
         "--trigger-mode", mode, "--sw-trigger-port", "0", *count_args],
        cwd=tmp_path, env=subprocess_env(), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    lines = start_stdout_reader(process)
    try:
        ready = read_event_until(lines, "ready", 10)
        assert ready["stream"] == {"lifecycle": "run_bound"}
        active = None
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            event = read_event_until(lines, "status", 2)
            if event["stream"]["state"] == "active":
                active = event
                break
        assert active is not None
        assert process.poll() is None
        for command in ("status", "wait-ready"):
            response = run_client(command, "--port", str(ready["port"]), "--json")
            assert response.returncode == 0, response.stdout + response.stderr
            status = json.loads(response.stdout)
            assert status["stream"] == active["stream"]
            assert status["run_id"] == active["run_id"] == ready["run_id"]
            assert status["captured"] == 0
        trigger = run_client("send-command", "--port", str(ready["port"]), "--json")
        assert trigger.returncode == 0, trigger.stderr
        tail = []
        deadline = time.monotonic() + 10
        while process.poll() is None and time.monotonic() < deadline:
            try:
                tail.append(json.loads(lines.get(timeout=0.1)))
            except queue.Empty:
                pass
        assert process.wait(timeout=2) == 0
        # Wait for the stdout reader to observe EOF and deliver all queued lines.
        assert process.stdout is not None
        for _ in range(20):
            try:
                tail.append(json.loads(lines.get(timeout=0.05)))
            except queue.Empty:
                break
        sample_index = next(i for i, e in enumerate(tail) if e["event"] == "sample")
        ended_index = next(i for i, e in enumerate(tail) if e.get("stream", {}).get("state") == "ended")
        summary_index = next(i for i, e in enumerate(tail) if e["event"] == "summary")
        assert sample_index < ended_index < summary_index
        assert tail[summary_index]["ok"] is True
        assert tail[summary_index]["captured"] == 1
        assert "stream" not in tail[sample_index]
        assert "stream" not in tail[summary_index]
        assert list(tmp_path.iterdir()) == []
        assert process.stderr.read() == ""
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@pytest.mark.parametrize("mode", ["external", "external-custom"])
@pytest.mark.parametrize("infinite", [False, True])
def test_external_simulation_streams_until_finite_completion_or_stop(mode, infinite, tmp_path):
    custom = mode.endswith("-custom")
    if custom:
        count_args = ["--sample-count", "2", "--monitor-overflow"]
        count_args += (
            ["--trigger-count-infinite", "--allow-buffer-overflow-risk"]
            if infinite else ["--trigger-count", "3"]
        )
    else:
        count_args = [] if infinite else ["--max-samples", "3"]
    process = subprocess.Popen(
        [sys.executable, "-m", "meters_tool_cli", "start-trigger-record",
         "--resource", "SIM::34461A", "--simulate", "--streaming", "--json",
         "--trigger-mode", mode, "--sw-trigger-port", "0", *count_args],
        cwd=tmp_path, env=subprocess_env(), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    lines = start_stdout_reader(process)
    events = []
    ready = None
    stopped = False
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                event = json.loads(lines.get(timeout=0.1))
            except queue.Empty:
                if process.poll() is not None:
                    break
                continue
            events.append(event)
            assert len(events) < 1000
            if event["event"] == "ready":
                ready = event
            if infinite and not stopped and event["event"] == "sample" and event["captured"] >= 4:
                assert ready is not None
                response = run_client("stop", "--port", str(ready["port"]), "--json")
                assert response.returncode == 0, response.stdout + response.stderr
                assert json.loads(response.stdout)["status"] == "accepted"
                stopped = True
        assert process.wait(timeout=2) == 0
        assert ready is not None
        ready_index = events.index(ready)
        active_index = next(i for i, e in enumerate(events) if e.get("stream", {}).get("state") == "active")
        ended_index = next(i for i, e in enumerate(events) if e.get("stream", {}).get("state") == "ended")
        summary_index = next(i for i, e in enumerate(events) if e["event"] == "summary")
        sample_indices = [i for i, e in enumerate(events) if e["event"] == "sample"]
        assert ready_index < active_index < min(sample_indices)
        assert max(sample_indices) < ended_index < summary_index
        assert all(e["schema_version"] == 3 and e["run_id"] == ready["run_id"] for e in events)
        summary = events[summary_index]
        assert summary["ok"] is True
        assert summary["errors"] == 0
        assert summary["captured"] == len(sample_indices)
        if infinite:
            assert stopped and len(sample_indices) >= 4
            assert summary["stop_reason"] == "stop_requested"
        else:
            assert len(sample_indices) == (6 if custom else 3)
            assert summary["stop_reason"] == ("completed" if custom else "max_samples_reached")
        if custom:
            assert summary["expected_readings"] == (None if infinite else 6)
            assert summary["final_drain_complete"] is True
            assert summary["overflow_detected"] is False
        assert list(tmp_path.iterdir()) == []
        assert process.stderr.read() == ""
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
