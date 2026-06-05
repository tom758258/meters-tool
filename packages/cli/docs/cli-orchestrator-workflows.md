# CLI Orchestrator Workflows

This document gives subprocess-oriented workflows for agents that drive the
Keysight meter CLI. Shared event fields are defined in
[`cli-jsonl-contract.md`](cli-jsonl-contract.md); meter worker endpoints are
defined in [`worker-contract.md`](worker-contract.md).

## Simulator Software Trigger Workflow

Use a simulator-only worker for automated orchestration tests. The worker emits
JSONL on stdout; client commands emit one JSON object to stdout when called with
`--json` or `--format json`.

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
        [sys.executable, "-m", "keysight_logger_cli", "wait-ready", "--port", str(port), "--json"],
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(wait_ready.stdout)["run_id"] == ready["run_id"]

    status = subprocess.run(
        [sys.executable, "-m", "keysight_logger_cli", "soft-status", "--port", str(port), "--json"],
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(status.stdout)["run_id"] == ready["run_id"]

    subprocess.run(
        [sys.executable, "-m", "keysight_logger_cli", "soft-trigger", "--port", str(port), "--json"],
        text=True,
        capture_output=True,
        check=True,
    )

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
            [sys.executable, "-m", "keysight_logger_cli", "soft-stop", "--port", str(port), "--json"],
            text=True,
            capture_output=True,
            check=False,
        )
        worker.terminate()
```

## Live Mode Resource Rule

Live mode must use an explicit `--resource` selected by the operator or by a
previous explicit discovery step. Do not scan, guess, or rotate through VISA
resource strings inside an orchestrator. A live acquisition subprocess should
fail closed when `--resource` is missing or does not match the intended
instrument.

## Cleanup Rule

Use `soft-stop --json` for cooperative cleanup when the worker is still running.
If the process has already exited, `soft-stop` may return
`status: "already_stopped"` with exit code `0`; this remains a successful cleanup
result for orchestrators.
