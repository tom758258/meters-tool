# Meters Orchestrator Workflows

This document gives subprocess-oriented workflows for agents that drive the
Keysight meter CLI. Shared lifecycle guidance is defined in
[Common Orchestrator Workflows](common-orchestrator-workflows.md). Shared event
envelope rules are defined in
[Common CLI JSON / JSONL Contract](common-cli-jsonl-contract.md). Meters event
fields are defined in
[Meters CLI JSON / JSONL Contract](meters-cli-jsonl-contract.md), and meter
worker endpoints are defined in
[Meters Worker Contract](meters-worker-contract.md).

## Invocation Forms

The Meters contracts define CLI/worker subprocess behavior, not a required
binary packaging format. A conforming worker may be launched through any
equivalent subprocess command, including:

- `meters-tool ...` from an installed Python package.
- `meters-tool.exe ...` from a packaged Windows executable.
- `python -m meters_tool_cli ...` in a development checkout.

The invocation form is valid only when it preserves the documented stdout
JSON/JSONL behavior, local control endpoints, process exit codes, artifacts,
and `run_id` correlation rules. Direct in-process Python API calls, such as
importing core runner functions, are outside this CLI/worker subprocess
contract unless a separate Python API contract defines them.

## Simulator Software Trigger Workflow

Use a simulator-only worker for automated orchestration tests. The worker emits
JSONL on stdout; client commands emit one JSON object to stdout when called
with `--json` or `--format json`.

```python
from __future__ import annotations

import json
import subprocess
import sys

port = 8765
worker = subprocess.Popen(
    [
        sys.executable,
        "-u",
        "-m",
        "meters_tool_cli",
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
        "samples.csv",
    ],
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

try:
    assert worker.stdout is not None
    ready = None
    for line in worker.stdout:
        event = json.loads(line)
        if event["event"] == "ready":
            ready = event
            break
    assert ready is not None

    wait_ready = subprocess.run(
        [
            sys.executable,
            "-m",
            "meters_tool_cli",
            "wait-ready",
            "--port",
            str(port),
            "--json",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(wait_ready.stdout)["run_id"] == ready["run_id"]

    status = subprocess.run(
        [
            sys.executable,
            "-m",
            "meters_tool_cli",
            "status",
            "--port",
            str(port),
            "--json",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(status.stdout)["run_id"] == ready["run_id"]

    command_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "meters_tool_cli",
            "send-command",
            "--port",
            str(port),
            "--json",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    command_response = json.loads(command_result.stdout)
    assert command_response["status"] == "accepted"
    assert command_response["command"] == "software_trigger"

    for line in worker.stdout:
        event = json.loads(line)
        if event["event"] == "summary":
            assert event["ok"] is True
            assert event["captured"] == 1
            assert event["errors"] == 0
            break
    assert worker.wait(timeout=10) == 0
finally:
    if worker.poll() is None:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "meters_tool_cli",
                "stop",
                "--port",
                str(port),
                "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        worker.terminate()
```

## Readiness And Status

For Meters workers, the `ready` JSONL event and `wait-ready --json` mean the
local `/command`, `/stop`, and `/status` endpoints can accept requests. They do
not mean a measurement has completed.

Use `status --json` or direct `GET /status` as a non-mutating status
check. Verify that returned `run_id` values match the worker stdout JSONL for
the current run.

## Trigger And Stop

Use `send-command --json` or direct `POST /command` for software-triggered
Meters measurement requests. Use `stop --json` or direct `POST /stop` for
cooperative cleanup.

Treat `send-command` exit `2` as local or worker validation failure. Treat
HTTP `409`, `429`, other request failures, and invalid response bodies as exit
`3`. The JSON diagnostics echo worker `command`, `job_id`, `reason`, `error`,
and `message` fields when available.

If the process has already exited, `stop` may return
`status: "already_stopped"` with exit code `0`; this remains a successful
cleanup result for orchestrators.

## Live Mode Resource Rule

Live mode must use an explicit `--resource` selected by the operator or by a
previous explicit discovery step. Do not scan, guess, or rotate through VISA
resource strings inside an orchestrator. A live acquisition subprocess should
fail closed when `--resource` is missing or does not match the intended
instrument.
