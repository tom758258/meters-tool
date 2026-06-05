from __future__ import annotations

import json
import os
import queue
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOTS = [
    REPO_ROOT / "packages" / "core" / "src",
    REPO_ROOT / "packages" / "cli" / "src",
]


def unused_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    src_path = os.pathsep.join(str(path) for path in SRC_ROOTS)
    env["PYTHONPATH"] = src_path if not existing else f"{src_path}{os.pathsep}{existing}"
    return env


def run_client(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "keysight_logger_cli", *args],
        cwd=REPO_ROOT,
        env=subprocess_env(),
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )


def start_stdout_reader(process: subprocess.Popen[str]) -> queue.Queue[str]:
    lines: queue.Queue[str] = queue.Queue()

    def read_lines() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            lines.put(line)

    threading.Thread(target=read_lines, daemon=True).start()
    return lines


def read_event_until(lines: queue.Queue[str], event_name: str, timeout_s: float = 15.0) -> dict:
    deadline = time.monotonic() + timeout_s
    last_line = ""
    while time.monotonic() < deadline:
        try:
            line = lines.get(timeout=0.25)
        except queue.Empty:
            continue
        last_line = line
        payload = json.loads(line)
        if payload.get("event") == event_name:
            return payload
    raise AssertionError(f"timed out waiting for {event_name}; last line: {last_line!r}")


def test_simulator_worker_subprocess_control_plane(tmp_path: Path):
    port = unused_tcp_port()
    csv_path = tmp_path / "samples.csv"
    process = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "-m",
            "keysight_logger_cli",
            "start-trigger-record",
            "--resource",
            "SIM::34461A",
            "--simulate",
            "--trigger-mode",
            "software",
            "--max-samples",
            "1",
            "--status-format",
            "jsonl",
            "--sw-trigger-port",
            str(port),
            "--csv",
            str(csv_path),
        ],
        cwd=REPO_ROOT,
        env=subprocess_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    lines = start_stdout_reader(process)

    try:
        ready = read_event_until(lines, "ready")
        assert ready["port"] == port
        assert ready["run_id"]

        wait_ready = run_client("wait-ready", "--port", str(port), "--json")
        assert wait_ready.returncode == 0, wait_ready.stderr + wait_ready.stdout
        wait_ready_event = json.loads(wait_ready.stdout)
        assert wait_ready_event["event"] == "wait-ready"
        assert wait_ready_event["run_id"] == ready["run_id"]
        assert wait_ready_event["reachable"] is True

        status = run_client("soft-status", "--port", str(port), "--json")
        assert status.returncode == 0, status.stderr + status.stdout
        status_event = json.loads(status.stdout)
        assert status_event["event"] == "soft-status"
        assert status_event["run_id"] == ready["run_id"]
        assert status_event["reachable"] is True

        trigger = run_client("soft-trigger", "--port", str(port), "--json")
        assert trigger.returncode == 0, trigger.stderr + trigger.stdout
        trigger_event = json.loads(trigger.stdout)
        assert trigger_event["event"] == "soft-trigger"
        assert trigger_event["status"] == "accepted"

        summary = read_event_until(lines, "summary")
        assert summary["captured"] == 1
        assert summary["errors"] == 0
        assert summary["ok"] is True
        assert process.wait(timeout=10) == 0
    finally:
        if process.poll() is None:
            run_client("soft-stop", "--port", str(port), "--json")
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
