# Meters Worker Contract

Schema version: `1`

This document defines the operational contract for the Keysight meter worker
used by agents and orchestration tools. It follows the lifecycle shape in
[Common Worker Protocol](common-worker-protocol.md) and covers Meters-specific
process modes, local control HTTP, runtime JSONL, and wrapper artifacts. It
does not change instrument behavior.

## Cross-Instrument Compatibility

This is the Meters worker contract only. Future Power, Scope, and KSON workers
should keep their own worker contracts for their command models and
instrument-specific runtime behavior.

Orchestrators should depend only on the common lifecycle for cross-instrument
coordination: process start, stdout JSONL observation, the JSONL `ready` event,
`GET /status`, `POST /stop`, runtime events, process exit codes, and artifacts.
Meters-specific trigger behavior, measurement fields, CSV columns, and
instrument setup belong to this document, not the common protocol.

## Worker Modes

`start-trigger-record --dry-run` validates arguments and emits a planned
execution contract. It does not open VISA, create the CSV writer, start the
HTTP control server, start the acquisition worker, or write to the instrument.

`start-trigger-record --simulate` runs the normal acquisition engine against the
deterministic simulator. It starts the local HTTP control server, writes normal
CSV/runtime output, and is intended for workflow validation without hardware.
Simple simulate modes require a finite bound such as `--max-samples`.

Live `start-trigger-record` is the default mode. It opens the explicit VISA
resource, validates the 34461A identity, starts the local HTTP control server,
runs acquisition, and performs the documented release/local cleanup. Live runs
must keep using explicit resources; wrappers must not scan or guess live
instrument resources.

## Orchestrator Quickstart

Use this order for agent-controlled runs:

1. Run `start-trigger-record --dry-run --status-format jsonl` and validate the
   single `dry_run` object. Dry-run has no `run_id` and emits no `ready` event.
2. Run the same acquisition shape with `--simulate --status-format jsonl` and a
   finite bound such as `--max-samples`.
3. Start live `start-trigger-record` with an explicit `--resource`. Live
   wrappers must not scan for resources or guess a VISA address.
4. Wait for either the JSONL `ready` event or
   `keysight-logger wait-ready --port <port> --json`. `ready` and
   `wait-ready` are control-plane readiness only; they do not mean a
   measurement has completed.
5. Call `keysight-logger soft-status --port <port> --json` or direct
   `GET /status` and verify the returned `run_id` matches stdout JSONL.
6. Use `POST /trigger` for Meters software-triggered measurement requests. Use
   `POST /stop` for graceful stop.
7. Read stdout JSONL, CSV, `report.json`, and any wrapper summary artifacts.
   Machine decisions should come from structured files and JSON events, not
   human text messages.

`run_id` is the correlation key between stdout JSONL, `GET /status`, and
wrapper artifacts for one non-dry-run session.

For a complete Python subprocess example, see
[`cli-orchestrator-workflows.md`](cli-orchestrator-workflows.md).

## Control Plane

The worker listens on `127.0.0.1` by default. Orchestrators should pass an
explicit `--sw-trigger-port` when they need a stable port. `--sw-trigger-port 0`
lets the operating system choose a port; JSONL callers should read the
`ready` event to discover the selected local control URLs.

In JSONL mode, non-dry-run `start-trigger-record` emits one `ready` event after
the HTTP control plane starts and before the measurement worker thread starts.
This is a control-plane readiness signal only. It means `/trigger`, `/stop`,
and `/status` can accept requests; it does not mean the first measurement has
completed. The `ready` event includes `run_id`, a UUID string that identifies
the runtime session.

### `POST /trigger`

Publishes one Meters software-triggered measurement request. The request body
may be a JSON object containing metadata; object values are stored as strings
in `trigger_metadata` on captured samples. Accepted requests return `202`.
Rejected requests return `429` with JSON status, for example
`{"status":"rejected","reason":"queue_full"}` or
`{"status":"rejected","reason":"rate_limited"}`.

This endpoint must not be used as a stop mechanism. In hardware-triggered
simple and external-custom modes, software trigger events may be ignored by the
Meters acquisition flow.

### `POST /stop`

Publishes a stop control event and requests graceful worker stop. Accepted
requests return `202`. Stop control events use a priority queue and remain
deliverable even when the normal trigger queue is full.

The stop design is unchanged: `engine.stop()` sets stop state/events only.
VISA I/O remains on the worker or cleanup path.

### `GET /status`

Returns `200` with a JSON status object. It does not change state, publish a
trigger, request stop, mutate queues, trigger measurement, or touch VISA. It is
safe for non-mutating readiness and progress checks. Unknown `GET` paths return
`404`.

`keysight-logger soft-status` is the CLI client wrapper for this endpoint. It
normalizes the worker status into the CLI single-response JSON contract without
mutating worker state. `keysight-logger wait-ready` polls this same endpoint
until any valid `200` JSON status response is reachable or its deadline expires.

Status response v1:

```json
{
  "schema_version": 1,
  "service": "keysight-meter",
  "run_id": "9f84b6ad-d2aa-4d68-9133-f33a5f6bcb9c",
  "status": "running",
  "trigger_url": "http://127.0.0.1:8765/trigger",
  "stop_url": "http://127.0.0.1:8765/stop",
  "status_url": "http://127.0.0.1:8765/status",
  "queue_size": 0,
  "queue_max": 10000,
  "min_interval_ms": 0,
  "captured": 0,
  "errors": 0,
  "fatal_error": null,
  "timestamp_utc": "2026-05-23T00:00:00+00:00"
}
```

Fields:

- `schema_version`: integer contract version, currently `1`.
- `service`: fixed string, `keysight-meter`.
- `run_id`: current runtime UUID, or `null` if no runtime provider supplied one.
- `status`: `running` or `stopping`.
- `trigger_url`, `stop_url`, `status_url`: absolute local HTTP URLs.
- `queue_size`: pending normal software trigger events.
- `queue_max`: effective normal trigger queue limit.
- `min_interval_ms`: configured software trigger rate limit.
- `captured`: current successful capture count, or `null` if unavailable.
- `errors`: current acquisition error count, or `null` if unavailable.
- `fatal_error`: fatal acquisition error text, or `null`.
- `timestamp_utc`: UTC timestamp serialized as ISO 8601.

If the dynamic status provider fails, the endpoint still returns the base
status object with nullable `captured`, `errors`, and `fatal_error`.

`run_id` is the correlation key between runtime JSONL emitted on stdout,
`GET /status`, and wrapper artifacts for a single non-dry-run
`start-trigger-record` session. Dry-run plans do not have a `run_id`.

## Runtime JSONL

`start-trigger-record --status-format jsonl` and the `--json` alias emit one
JSON object per line for runtime events. Use JSONL for process observation,
sample events, errors, and final summaries.

See [CLI JSON / JSONL Contract](cli-jsonl-contract.md) for the event schema,
single-response client JSON, alias rules, and dry-run preview objects.

## Artifacts

Primary worker artifacts:

- CSV: one row per captured sample using the field order documented in
  `docs/README_CLI_EN.md`.
- stdout: human text by default, or JSONL when `--status-format jsonl` or
  `--json` is used.
- stderr: validation, connection, or request errors that are not represented as
  JSONL in text mode.

Wrapper artifacts:

- `report.json`: machine-readable wrapper report.
- `summary.md`: human-readable wrapper summary.
- Captured command stdout/stderr files referenced from `report.json`.
- Case CSV outputs referenced from live reports.

## Report Contract

Preflight and live wrapper reports use `schema_version: 1`.

Preflight `report.json` fields:

- `schema_version`
- `target`
- `generated_at`
- `package_version`
- `git_head`
- `validation_mode`
- `output_dir`
- `artifact_paths`
- `status`: currently `passed` on successful report generation.
- `summary_counts`: aggregate counts for pinned wrapper coverage:
  `commands_total`, `checks_total`, `dry_run_cases`, `simulate_cases`,
  `soft_client_dry_runs`, `list_resources_contract_checks`, and
  `mocked_pytest_checks`.
- `commands`: captured command result objects.
  Software-triggered simulator cases include nested `client_commands` for
  `wait-ready`, `soft-status`, and `soft-trigger` calls.
- `checks`: named verification records.

Live `report.json` fields:

- `schema_version`
- `target`
- `connection`
- `suite`
- `resource`
- `generated_at`
- `package_version`
- `git_head`
- `validation_mode`
- `output_dir`
- `artifact_paths`
- `status`: `planned`, `confirmation_required`, `passed`, `failed`, or
  `preflight_failed`.
- `plan_only`: `true` when `live-cli-check.ps1 -PlanOnly` generated only
  live dry-run plans.
- `live_executed`: `true` only after the wrapper starts live acquisition
  cases.
- `cases`: live case result objects.
- `dry_runs`: dry-run plan records for each selected live case. Planned,
  confirmation-required, and live reports all include dry-run records after
  those plans are generated.
- `commands`: captured command result objects.

Interactive live and `-PlanOnly` wrapper runs execute preflight before case
planning. Redirected-stdin live wrapper runs do not run acquisition; they
generate dry-run plans without nested preflight and write
`status: confirmation_required`.

Captured command result objects include:

- `name`
- `command`
- `arguments`
- `exit_code`
- `duration_seconds`
- `stdout`
- `stderr`
- `success`

Long-running captured command objects may also include:

- `timed_out`
- `client_failure`
- `client_commands`

Live case result objects include:

- `name`
- `status`
- `run_id`
- `expected_captured`
- `captured_count`
- `captured`
- `errors`
- `csv_row_count`
- `csv_rows`
- `csv`
- `failure_reasons`
- `command`

`summary.md` is not a schema source of truth. Orchestrators should read
`report.json` for pass/fail decisions and use `summary.md` only for operator
handoff.
