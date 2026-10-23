# Meters Orchestrator Workflows

Worker schema version: `3`

Independent CLI single-response schema version: `2`

Compatibility policy: `v3-only`

This document gives subprocess-oriented workflows for agents that drive the
Keysight meter CLI. Shared lifecycle guidance is defined in
[Common Orchestrator Workflows](common-orchestrator-workflows.md). Shared event
envelope rules are defined in
[Common CLI JSON / JSONL Contract](common-cli-jsonl-contract.md). Meters event
fields are defined in
[Meters CLI JSON / JSONL Contract](meters-cli-jsonl-contract.md), and meter
worker endpoints are defined in
[Meters Worker Contract](meters-worker-contract.md).

Meters runtime Worker HTTP and JSONL require exact integer schema `3`;
the Manifest and independently wrapped CLI client responses use schema `2`.
There is no v2 fallback or version negotiation.

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

## Model Context

Meters context is fixed at startup. Live model selection is an
`expected_model_id` guard; simulate and dry-run selection is a
`planning_model_id`. Meters does not use `planning_profile_id`, and command
requests do not override startup context.

Use `meters-tool capabilities --json` to discover the default Core capability
view, or add `--model MODEL` to inspect one registered profile. This command
performs no live identity detection or VISA I/O. A requested capability profile
does not become a live runtime driver override; live runs still use detected
identity and Core Product support policy.

## Streaming Consumer Workflow

Select `--streaming --json` explicitly. The Worker defaults to no CSV in this
mode; pass `--csv PATH` only when a Worker-owned CSV is required. The
Orchestrator owns persistence of the received Sample Events. JSONL without
`--streaming` retains the existing CSV default.

Observe adoption through `ready.stream.lifecycle` or the HTTP status fallback,
then wait for `stream.state: "active"` before issuing a trigger when the
workflow needs that readiness milestone. `wait-ready` alone confirms only the
control endpoint. Use the mode-specific Active meaning in the
[Meters Worker Contract](meters-worker-contract.md#optional-run-bound-streaming);
Active does not provide synchronization before measurement starts.

The Orchestrator should impose its own configurable Active deadline. If it
expires while the stream remains waiting, request the existing graceful Stop,
record that Streaming readiness was not reached, and still consume tail data,
ended, summary, EOF, and process exit. Do not modify Meters hardware timeouts
to implement this scheduling policy. An Active event during final drain does
not retroactively satisfy the earlier orchestration deadline or erase a
Worker failure. Do not treat a rapidly ended stream as still active merely
because an earlier Active event was received.

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
    assert ready["schema_version"] == 3

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
    wait_ready_result = json.loads(wait_ready.stdout)
    assert wait_ready_result["schema_version"] == 2
    assert wait_ready_result["run_id"] == ready["run_id"]

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
    status_result = json.loads(status.stdout)
    assert status_result["schema_version"] == 2
    assert status_result["run_id"] == ready["run_id"]

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
    assert command_response["schema_version"] == 2
    assert command_response["status"] == "accepted"
    assert command_response["command"] == "software_trigger"

    for line in worker.stdout:
        event = json.loads(line)
        if event["event"] == "summary":
            assert event["schema_version"] == 3
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

## Orchestrator-Owned Sample Persistence

Keep the preceding `--csv samples.csv` workflow when Meters should own its CSV
artifact. When the orchestrator owns persistence instead, replace those two
arguments with `--no-csv`. Persist the complete raw stdout JSONL stream, not
only its `sample` events, while separately parsing events needed for control
and sample storage:

```python
worker_args = [
    *worker_args_without_csv,
    "--status-format",
    "jsonl",
    "--no-csv",
]

for line in worker.stdout:
    persist_stdout_jsonl(line)
    event = json.loads(line)
    if event["event"] == "sample":
        persist_measurement(event)
```

For a complete scheduler job history, the orchestrator should retain:

1. The submitted request and effective launch configuration before starting
   Meters. This may be the command/argv or the scheduler's canonical request
   representation.
2. The complete unmodified Worker stdout JSONL stream, including `ready`,
   `status`, `sample`, `error`, `message`, and final `summary` events.
3. Worker stderr as diagnostics. Stderr does not replace structured pass/fail
   evaluation.
4. The final `summary` event, when emitted, and process exit code.
5. An orchestrator-owned terminal result that correlates the scheduler job
   identity and process exit code, plus the Meters `run_id` and final `summary`
   when available. Validation or support admission can fail before a runtime
   session exists, so either optional value may be absent.
6. Scheduler-owned sample persistence derived from JSONL `sample` events when
   `--no-csv` is used.

A non-zero process exit, a missing final summary, or `summary.ok: false` makes
the run failed or incomplete under the existing Common and Meters contracts.
The terminal result should record that outcome; stderr alone must not decide it.

An orchestrator might choose an artifact layout such as:

```text
request.json
stdout.jsonl
stderr.txt
result.json
samples.csv
```

These names and the containing layout are entirely orchestrator-owned examples,
not Meters Worker artifact names or a new runtime schema. Meters does not create
or manage these files. In particular, an orchestrator may create `samples.csv`
from JSONL `sample` events while Meters runs with `--no-csv`.

If Meters should own CSV persistence instead, keep the existing `--csv PATH` or
default CSV workflow. Do not layer a new storage contract on top of it.
`persist_stdout_jsonl`, `persist_measurement`, and terminal-result construction
are orchestrator responsibilities. Meters creates no CSV file or CSV-only
parent directory with `--no-csv`, and its `ready`, `status`, `summary`, process
exit, `run_id`, and Common Worker `schema_version: 3` semantics apply; independent wrappers remain 2.

## Readiness And Status

For Meters workers, the `ready` JSONL event and `wait-ready --json` mean the
local `/command`, `/stop`, and `/status` endpoints can accept requests. They do
not mean a measurement has completed.

Use `status --json` or direct `GET /status` as a non-mutating status
check. Verify that returned `run_id` values match the worker stdout JSONL for
the current run.

## Trigger And Stop

Use `send-command --json` or direct `POST /command` for software-triggered
Meters measurement requests. The Common v3 Worker command envelope includes exact
integer `schema_version: 3` and omits `context` because Meters binds it at
startup. Use `stop --json` or direct `POST /stop` for cooperative cleanup.

Treat `send-command` exit `2` as local or worker validation failure. Treat
HTTP `409`, `429`, other request failures, and invalid response bodies as exit
`3`. The JSON diagnostics echo worker `command`, `job_id`, `reason`, `error`,
and `message` fields when available.

If the process has already exited, `stop` may return
`status: "already_stopped"` with exit code `0`; this remains a successful
cleanup result for orchestrators.

## Custom Count And Overflow Workflows

Custom modes require `--sample-count` and either `--trigger-count N` or
`--trigger-count-infinite`. Infinity also requires
`--allow-buffer-overflow-risk`. For example, a simulator-only immediate stream
can use these acquisition arguments with the subprocess lifecycle above:

```python
acquisition_args = [
    "start-trigger-record", "--resource", "SIM::34461A", "--simulate",
    "--trigger-mode", "immediate-custom", "--measurement", "current-dc",
    "--trigger-count-infinite", "--sample-count", "2",
    "--allow-buffer-overflow-risk", "--status-format", "jsonl", "--no-csv",
    "--sw-trigger-port", "8765",
]
```

IMM runs continuously after one INIT. BUS requires software commands and
produces `sample_count` readings per instrument trigger. On a profile that
supports EXT, each external edge produces `sample_count` readings. Infinity
does not introduce finite automatic re-arm cycles. Simulator-only EXT does not
provide a complete external-edge injection workflow; it cannot establish live
EXT timing or edge behavior.

Infinity and `--stop-on-overflow` force monitoring; `--monitor-overflow` also
enables it for finite Custom acquisition. Status and summary carry
`trigger_count_infinite`, `expected_readings`, `overflow_monitoring`,
`overflow_detected`, `stop_reason`, `final_drain_complete`, and `data_integrity`.
Check these fields with the matching `run_id`. A readiness response means the
control endpoints are available; it does not mean BUS is ready for another
instrument trigger or that an EXT edge has occurred.

Without Stop on overflow, confirmed overflow remains latched while acquisition
continues draining. With Stop on overflow, the worker stops and reports
`overflow_detected`. Both outcomes are unsuccessful and exit `3`; continuing
after overflow does not restore data integrity. Failed monitoring must not be
interpreted as no overflow. A finite monitored run uses instrument completion
as well as draining, since overflow can prevent the captured count from ever
reaching the requested count.

For an infinite stream, send cooperative `stop --json` or `POST /stop` when the
orchestrator's acquisition interval ends, then keep consuming stdout until the
final summary and process exit. Stop signals state; the worker performs ABOR,
final status, and final drain before release/local and close. These finalization
operations share a two-second soft budget beginning before ABOR. No new
finalization I/O starts after expiry; an in-progress I/O keeps the existing VISA
timeout and may outlast the budget. Release/local and close are outside this
budget. Complete readings obtained before a later query failure remain
persisted and emitted.
An incomplete final drain is still an unsuccessful outcome. A scheduler
watchdog is a separate failure boundary and must not be reported as a normal
scheduled Stop.

For finite Custom runs with all new options disabled, a normal early Stop
retains legacy success and exit `0`, while `data_integrity: "incomplete"`
truthfully reports a short capture. Count-sensitive orchestrators must inspect
`captured` and `expected_readings` as well as `ok`.

Dry-run plans may show `TRIG:COUNT INF` and overflow notes, but are not a trace
of executed runtime queries or proof of completion, overflow, or final drain.
Live support remains subject to the exact Core support-policy scope.

## Live Mode Resource Rule

Live mode must use an explicit `--resource` selected by the operator or by a
previous explicit discovery step. Do not scan, guess, or rotate through VISA
resource strings inside an orchestrator. A live acquisition subprocess should
fail closed when `--resource` is missing or does not match the intended
instrument.
