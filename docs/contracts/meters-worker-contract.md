# Meters Worker Contract

Schema version: `1`

This document defines the operational contract for the Keysight meter worker
used by agents and orchestration tools. It follows the lifecycle shape in
[Common Worker Protocol](common-worker-protocol.md) and covers Meters-specific
process modes, local control HTTP, runtime JSONL, and wrapper artifacts. It
does not change instrument behavior.

## Cross-Instrument Compatibility

This is the Meters worker contract only. Future instrument workers should keep
their own worker contracts for their command models and instrument-specific
runtime behavior.

Orchestrators should depend only on the common lifecycle for cross-instrument
coordination: process start, stdout JSONL observation, the JSONL `ready` event,
`GET /status`, `POST /command`, `POST /stop`, runtime events, process exit
codes, and artifacts. Meters-specific trigger behavior, measurement fields,
CSV columns, and instrument setup belong to this document, not the common
protocol.

## CLI/Worker Subprocess Boundary

This contract is defined at the CLI/worker subprocess boundary, not at a
specific packaging boundary. `keysight-logger`, `keysight-logger.exe`, and
`python -m keysight_logger_cli` are equivalent invocation forms only when they
preserve the documented stdout JSON/JSONL behavior, local control HTTP
endpoints, process exit codes, artifacts, and `run_id` correlation semantics.

Direct in-process Python API calls, such as importing core runner functions,
are outside this CLI/worker subprocess contract unless a separate Python API
contract defines them.

## Worker Modes

`start-trigger-record --dry-run` validates arguments and emits a planned
execution contract. It does not open VISA, create the CSV writer, start the
HTTP control server, start the acquisition worker, or write to the instrument.

`start-trigger-record --simulate` runs the normal acquisition engine against
the deterministic simulator. It starts the local HTTP control server, writes
normal CSV/runtime output, and is intended for workflow validation without
hardware. Simple simulate modes require a finite bound such as `--max-samples`.

Live `start-trigger-record` is the default mode. It opens the explicit VISA
resource, validates the instrument identity against the selected model profile
(default 34461A), starts the local HTTP control server, runs acquisition, and
performs the documented release/local cleanup. Live runs must keep using
explicit resources; wrappers must not scan or guess live instrument resources.
When a CLI caller passes an optional PyVISA library/backend value such as
`--visa-library "@py"`, live resource manager creation uses that backend. If it
is omitted, live mode uses the system default `pyvisa.ResourceManager()`
behavior. This option does not change the worker JSONL, CSV, HTTP control, or
cleanup contracts.

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
5. Call `keysight-logger status --port <port> --json` or direct
   `GET /status` and verify the returned `run_id` matches stdout JSONL.
6. Use `POST /command` for Meters software-triggered measurement requests. Use
   `POST /stop` for graceful stop.
7. Read stdout JSONL, CSV, `report.json`, and any wrapper summary artifacts.
   Machine decisions should come from structured files and JSON events, not
   human text messages.

`run_id` is the correlation key between stdout JSONL, `GET /status`, and
wrapper artifacts for one non-dry-run session.

For a complete Python subprocess example, see
[Meters Orchestrator Workflows](meters-orchestrator-workflows.md).

## Control Plane

The worker listens on `127.0.0.1` by default. Orchestrators should pass an
explicit `--sw-trigger-port` when they need a stable port. `--sw-trigger-port
0` lets the operating system choose a port; JSONL callers should read the
`ready` event to discover the selected local control URLs.

In JSONL mode, non-dry-run `start-trigger-record` emits one `ready` event after
the HTTP control plane starts and before the measurement worker thread starts.
This is a control-plane readiness signal only. It means `/command`, `/stop`,
and `/status` can accept requests; it does not mean the first measurement has
completed. The `ready` event includes `run_id`, a UUID string that identifies
the runtime session.

### `POST /command`

Publishes one Meters software-triggered measurement request. The only Meters
command in this contract revision is `software_trigger`.

Request body:

```json
{
  "command": "software_trigger",
  "arguments": {
    "metadata": {}
  },
  "job_id": "optional-client-generated-id"
}
```

`arguments` may be omitted and defaults to `{}`. If present, it must be a JSON
object. `arguments.metadata` may be omitted and defaults to `{}`. If present,
it must be a JSON object with string keys. String metadata values are preserved;
other JSON values are stored as compact JSON literals in `trigger_metadata` on
captured samples. `job_id` must be a client-provided string when present and is
not written to measurement metadata.

Malformed JSON, non-object bodies, unknown top-level fields, a missing or
non-string `command`, unknown commands, non-object `arguments`, non-object
metadata, non-string metadata keys, and a non-string `job_id` return `400` with
structured JSON and do not publish queue events or touch instrument I/O.

Every response includes `status`, `command`, and `job_id`. A valid
client-provided string identity is echoed even when the request has an unknown
command or unknown top-level field. Malformed JSON, non-object bodies, and
non-string command identities use `command: null`; omitted or non-string
`job_id` values use `job_id: null`.

Accepted requests return `202`:

```json
{"status":"accepted","command":"software_trigger","job_id":"job-1"}
```

Queue and rate-limit rejections return `429` with `reason: "queue_full"` or
`reason: "rate_limited"`:

```json
{"status":"rejected","command":"software_trigger","job_id":"job-1","reason":"queue_full"}
```

Validation failures return `400`:

```json
{"status":"error","command":"software_trigger","job_id":"job-1","error":"validation_error","message":"metadata must be a JSON object"}
```

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

`keysight-logger status` is the CLI client wrapper for this endpoint. It
normalizes the worker status into the CLI single-response JSON contract without
mutating worker state. `keysight-logger wait-ready` polls this same endpoint
until any successful `200` JSON status response is reachable or its deadline
expires.

Status response v1:

```json
{
  "schema_version": 1,
  "service": "keysight-meter",
  "run_id": "9f84b6ad-d2aa-4d68-9133-f33a5f6bcb9c",
  "status": "running",
  "command_url": "http://127.0.0.1:8765/command",
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
- `run_id`: current runtime UUID, or `null` if no runtime provider supplied
  one.
- `status`: `running` or `stopping`.
- `command_url`, `stop_url`, `status_url`: absolute local HTTP URLs.
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

See [Meters CLI JSON / JSONL Contract](meters-cli-jsonl-contract.md) for the
event schema, single-response client JSON, alias rules, and dry-run preview
objects.

## Artifacts

Primary worker artifacts:

- CSV: one row per captured sample using the field order documented in the CLI
  guide.
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
- `commands`: captured command result objects. Software-triggered simulator
  cases include nested `client_commands` for `wait-ready`, `status`, and
  `send-command` calls.
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
- `plan_only`: `true` when `live-cli-check.ps1 -PlanOnly` generated only live
  dry-run plans.
- `live_executed`: `true` only after the wrapper starts live acquisition cases.
- `cases`: live case result objects.
- `dry_runs`: dry-run plan records for each selected live case.
- `scpi_diagnostics`: Frequency/Period probe records. This is empty for
  `-PlanOnly` and suites without Frequency/Period cases.
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
- `measurement_type`: measurement type from the first captured CSV row.
- `value`: raw value text from the first captured CSV row.
- `unit`: unit from the first captured CSV row.
- `csv`
- `failure_reasons`
- `command`
- `live_command_skipped`: `true` when a failed SCPI probe prevents the
  duplicate formal CLI acquisition run.
- `scpi_probe_command`: captured private probe command, or `null`.
- `scpi_diagnostic_path`: probe JSON artifact path, or `null`.
- `scpi_diagnostic`: the associated probe record, or `null`.

The live wrapper supports the `keysight-34461a` and `keysight-34460a` targets
and passes the matching CLI model to every generated `start-trigger-record`
command. Both targets support `minimal`, `basic`, `frequency-period`, and
`full` suites. `keysight-34461a` also supports `external`; `keysight-34460a`
rejects `external` because the base 34460A profile does not support external
trigger modes.

The `frequency-period` suite runs one immediate Auto Range Frequency sample and
one immediate Auto Range Period sample with a `20` Hz AC filter, `0.1` second
gate time, automatic Frequency timeout, and no Period timeout command.
`keysight-34461a` `full` includes the basic, Frequency/Period, and external
cases. `keysight-34460a` `full` is basic plus Frequency/Period only.

Before each live Frequency/Period CLI case, the wrapper runs a private probe
against the explicit `-Resource`. The probe records `*IDN?`, firmware revision,
the `READ?` response, and up to 10 `SYST:ERR?` responses immediately after each
planned SCPI command. A case passes only when the probe reports zero for every
SCPI error response and the formal CLI sample/CSV checks also pass. A failed
probe skips the duplicate formal CLI run but does not prevent the other
Frequency/Period measurement from being diagnosed.

The probe sends only the runtime's planned SCPI commands; it does not search
for alternate timeout syntax. Probe cleanup records the order `abort`,
`release_to_local`, and `close`. Live validation on a 34461A with firmware
A.03.03 found no SCPI errors for the Frequency or Period probe after the Period
timeout command was removed, and both formal cases produced one sample and CSV
row. This behavior resolves ambiguity in the
[Keysight Truevolt Series DMM Operating and Service Guide](https://www.keysight.com/us/en/assets/9018-03876/service-manuals/9018-03876.pdf)
without recording a real VISA resource or serial number.

`summary.md` is not a schema source of truth. Orchestrators should read
`report.json` for pass/fail decisions and use `summary.md` only for operator
handoff.
