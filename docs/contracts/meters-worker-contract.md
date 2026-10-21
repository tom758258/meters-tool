# Meters Worker Contract

Common schema version: `2`

Compatibility policy: `v2-only`

Implementation status: `Common v2-only conformant`

This document defines the operational contract for the Meters worker
used by agents and orchestration tools. It follows the lifecycle shape in
[Common Worker Protocol](common-worker-protocol.md) and covers Meters-specific
process modes, local control HTTP, runtime JSONL, and wrapper artifacts. It
does not change instrument behavior.

The current implementation enforces Common schema `2` for Worker command
requests and responses, status responses, and CLI JSON/JSONL output. Schema
`1`, missing, and non-integer schema versions are not accepted at v2-only
runtime boundaries.

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
specific packaging boundary. `meters-tool`, `meters-tool.exe`, and
`python -m meters_tool_cli` are equivalent invocation forms only when they
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
the deterministic simulator. It starts the local HTTP control server and emits
normal runtime output. CSV is written by default and may be disabled with
`--no-csv`. Simple simulate modes require a finite bound such as
`--max-samples`.

Live `start-trigger-record` is the default mode. It opens the explicit VISA
resource, resolves the instrument profile through IDN-only auto-detect when
`--model` is omitted, validates explicit model requests against that IDN, starts
the local HTTP control server, runs acquisition, and performs the documented
release/local cleanup. Live runs must keep using explicit resources; wrappers
must not scan or guess live instrument resources.
An explicit live model is an expected-model guard only: unsupported model names
fail Core profile validation, mismatches fail before setup SCPI, and the
selected model never overrides the detected IDN-selected profile. Dry-run and
simulate use the selected model profile unless a deterministic simulator
resource supplies the model.

Common execution context is bound at Worker startup. In live mode, `--model`
maps to `expected_model_id`; in simulate and dry-run modes it maps to
`planning_model_id`. Meters does not define `planning_profile_id`. Because the
context is startup-bound, `POST /command` does not include `context`.
When a CLI caller passes an optional PyVISA library/backend value such as
`--visa-library "@py"`, live resource manager creation uses that backend. If it
is omitted, live mode uses System VISA through `pyvisa.ResourceManager("@ivi")`,
without automatic pyvisa-py fallback or a `PYVISA_LIBRARY` override. This option
does not change the worker JSONL, CSV, HTTP control, or
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
   `meters-tool wait-ready --port <port> --json`. `ready` and
   `wait-ready` are control-plane readiness only; they do not mean a
   measurement has completed.
5. Call `meters-tool status --port <port> --json` or direct
   `GET /status` and verify the returned `run_id` matches stdout JSONL.
6. Use `POST /command` for Meters software-triggered measurement requests. Use
   `POST /stop` for graceful stop.
7. Read stdout JSONL, the default CSV when enabled, `report.json`, and any
   wrapper summary artifacts. With `--no-csv`, persist stdout JSONL `sample`
   events as the measurement-data source. Machine decisions should come from
   structured files and JSON events, not human text messages.

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
  "schema_version": 2,
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

Malformed JSON, non-object bodies, a missing or non-exact-integer
`schema_version: 2`, unknown top-level fields, a missing or non-string
`command`, unknown commands, non-object `arguments`, non-object
metadata, non-string metadata keys, and a non-string `job_id` return `400` with
structured JSON and do not publish queue events or touch instrument I/O.

Every response includes exact integer `schema_version: 2`, `status`,
`command`, and `job_id`. A valid
client-provided string identity is echoed even when the request has an unknown
command or unknown top-level field. Malformed JSON, non-object bodies, and
non-string command identities use `command: null`; omitted or non-string
`job_id` values use `job_id: null`.

Accepted requests return `202`:

```json
{"schema_version":2,"status":"accepted","command":"software_trigger","job_id":"job-1"}
```

Queue and rate-limit rejections return `429` with `reason: "queue_full"` or
`reason: "rate_limited"`:

```json
{"schema_version":2,"status":"rejected","command":"software_trigger","job_id":"job-1","reason":"queue_full"}
```

Validation failures return `400`:

```json
{"schema_version":2,"status":"error","command":"software_trigger","job_id":"job-1","error":"validation_error","message":"metadata must be a JSON object"}
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

`meters-tool status` is the CLI client wrapper for this endpoint. It
normalizes the worker status into the CLI single-response JSON contract without
mutating worker state. `meters-tool wait-ready` polls this same endpoint
until any successful `200` JSON status response is reachable or its deadline
expires.

Status response v2:

```json
{
  "schema_version": 2,
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
  "trigger_count_infinite": false,
  "expected_readings": null,
  "overflow_monitoring": "off",
  "overflow_detected": null,
  "stop_reason": "unknown",
  "final_drain_complete": null,
  "data_integrity": "unknown",
  "timestamp_utc": "2026-05-23T00:00:00+00:00"
}
```

Fields:

- `schema_version`: exact integer `2`.
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
- `trigger_count_infinite`: whether the Custom run uses an unbounded trigger
  count.
- `expected_readings`: finite Custom expected reading count, or `null` for
  infinite or non-Custom runs.
- `overflow_monitoring`: `off`, `starting`, `active`, or `failed`.
- `overflow_detected`: `null` when monitoring is unavailable, otherwise `false`
  or `true`. Once observed, `true` remains latched even if a later poll fails.
- `stop_reason`: `stop_requested`, `completed`, `overflow_detected`,
  `overflow_monitor_failed`, `fatal_error`, `max_samples_reached`, or
  `unknown`.
- `final_drain_complete`: `null` when no final drain ran, otherwise a boolean.
- `data_integrity`: `unknown`, `no_loss_detected`, or `incomplete`.
- `timestamp_utc`: UTC timestamp serialized as ISO 8601.

If the dynamic status provider fails, the endpoint still returns the base
status object with nullable `captured`, `errors`, and `fatal_error`. The
structured acquisition outcome fields remain present with their non-Custom
defaults.

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

- CSV: a Meters-specific artifact enabled by default, with one row per captured
  sample. Default `data` columns are `timestamp_utc_plus_8,value,unit`;
  explicit `full` preserves the former 10-column schema and its field order.
  Optional `elapsed_s` and `delta_t_s` columns use PC writer-arrival timing,
  with one shared time for buffered readings from the same fetch. `--no-csv`
  disables the writer, file, and CSV-only parent-directory creation.
- stdout: human text by default, or JSONL when `--status-format jsonl` or
  `--json` is used.
- stderr: validation, connection, or request errors that are not represented as
  JSONL in text mode.

Disabling CSV does not change worker lifecycle, HTTP control, JSONL `sample`
events, status, summary, process exit meanings, stop behavior, or cleanup.
Dry-run reports `csv_enabled: false` and `csv_path: null` for a no-CSV plan,
while `dry_run_writes_csv` remains false for every dry-run. Common schema
version remains `2`; the Common Worker Protocol is unchanged.

Schedulers that retain launch requests, complete stdout/stderr, terminal
results, or derived sample files own those filenames and layouts. See
[Meters Orchestrator Workflows](meters-orchestrator-workflows.md#orchestrator-owned-sample-persistence);
they are not additional Meters Worker artifacts.

Wrapper artifacts:

- `report.json`: machine-readable wrapper report.
- `summary.md`: human-readable wrapper summary.
- Captured command stdout/stderr files referenced from `report.json`.
- Case CSV outputs referenced from live reports.

## Report Contract

Preflight, live, and release wrapper reports use `schema_version: 1`. Their
`target` is the canonical lower-case wrapper target and equals the Core profile
`model_id`. Current targets are `keysight-34461a` and `keysight-34460a`.

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
- `model_id`: the same canonical stable ID as `target`.
- `expected_model`: the physical model token passed to CLI model arguments.
- `connection`
- `visa_library`
- `backend`
- `support_policy_mode`
- `pending_live_support_allowed`
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

Release `report.json` preserves its existing fields and additively includes
`model_id` and `expected_model` with the same meanings as the live report. The
release wrapper normalizes its target before choosing `SIM::34461A` or
`SIM::34460A`, naming the output directory, and forwarding preflight and live
PlanOnly commands. Additive identity fields do not change `schema_version: 1`.

For `scripts/live-cli-check.ps1`, `support_policy_mode` is `validation` and
`pending_live_support_allowed` is `true`. These fields identify the wrapper as
a validation harness that may execute known pending transport/backend scopes to
collect artifacts. They do not promote public product support. When
`visa_library` or `backend` is omitted by the operator, the report records the
default system VISA runtime as `system_visa`.

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
- `expected_captured`: exact count, or `-1` when no exact row count is required.
- `expected_exit_code`: process exit code required by the case.
- `expected_stop_reason`: required reason for monitored Custom cases.
- `planned_stop_after_seconds`: acquisition interval before scheduled Stop;
  `0` disables scheduled Stop. Watchdog expiry remains a failure.
- `expect_overflow`: whether confirmed overflow is required.
- `require_continued_drain`: whether samples must continue after overflow while
  the run is still active, before Stop or final drain.
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
command. Both targets support `minimal`, `basic`, `frequency-period`,
`finite-custom`, `stream`, `overflow`, and `full` suites. `keysight-34461a` also
supports `external`; the base 34460A profile rejects that suite and omits EXT
cases from all Custom suites.

The Custom suites use DC current and cover each supported IMM/BUS/EXT mode
with monitoring alone and Stop on overflow. `finite-custom` checks normal finite
completion; `stream` checks infinite acquisition with scheduled Stop. `overflow`
covers both finite and infinite counts and requires the additional
`-AllowIntentionalOverflow` opt-in for live execution. Every overflow case
requires exit `3`, `summary.ok=false`, confirmed overflow, and incomplete data
integrity. Monitor-only cases also require a sample after overflow followed by
an active status before scheduled Stop; samples obtained only during final
drain cannot satisfy this check. The boolean result is retained as
`runtime_evidence.continued_drain_after_overflow`. The bounded final drain
outcome is recorded even when incomplete. None of these suites is included in
`full`. Plans and synthetic results do not establish real-instrument support;
evidence applies only to the model, transport, backend, measurement, and exact
Custom scope actually exercised.

The `frequency-period` suite runs one immediate Auto Range Frequency sample and
one immediate Auto Range Period sample with a `20` Hz AC filter, `0.1` second
gate time, automatic Frequency timeout, and no Period timeout command.
`keysight-34461a` `full` includes the basic, Frequency/Period, and external
cases. `keysight-34460a` `full` is basic plus Frequency/Period only.

Before each live Frequency/Period CLI case, the wrapper runs a private probe
against the explicit `-Resource` and validates identity against the selected
target model. The probe records `*IDN?`, firmware revision, the `READ?`
response, and up to 10 `SYST:ERR?` responses immediately after each planned SCPI
command. A case passes only when the probe reports zero for every SCPI error
response and the formal CLI sample/CSV checks also pass. A failed probe skips
the duplicate formal CLI run but does not prevent the other Frequency/Period
measurement from being diagnosed.

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
