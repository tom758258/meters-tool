# Meters Worker Contract

Worker schema version: `3`

Manifest schema version: `2`

Compatibility policy: `v3-only`

Implementation scope: Worker protocol v3; ordinary CLI and artifact schemas retain their independent versions.

This document defines the operational contract for the Meters worker
used by agents and orchestration tools. It follows the lifecycle shape in
[Common Worker Protocol](common-worker-protocol.md) and covers Meters-specific
process modes, local control HTTP, runtime JSONL, and wrapper artifacts. Instrument operations remain
Meters-specific, including the optional readiness observations defined below.

The Worker HTTP command/status/stop envelopes and runtime JSONL require exact
integer Worker `schema_version: 3`; the static Manifest retains schema 2.
Single-response CLI client and dry-run preview schemas remain independently
versioned at 2. Workers reject v2 requests without fallback.

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
normal runtime output. Without `--streaming`, CSV is written by default and
may be disabled with `--no-csv`. Simple simulate modes require `--max-samples`
unless `--streaming` is selected. Simple Streaming simulation may omit it and
continue until an existing Stop; an explicit `--max-samples N` still ends
naturally after N readings. There is no implicit sample cap. This opt-in does
not change WebUI/Desktop's non-streaming, finite Simple simulation.

On profiles supporting External, `external` and `external-custom` simulation
automatically generate virtual external triggers at an internal fixed cadence.
No manual trigger injection, HTTP injection endpoint, or user-adjustable
simulation interval is needed. INIT arms the simulated source; later simulator
observations advance virtual triggers. Waiting-for-trigger and completion are
distinct states. External Simple produces readings until `max_samples` or Stop.
External Custom produces `sample_count` readings per virtual trigger: finite
runs complete after `trigger_count` triggers, with
`expected_readings = trigger_count * sample_count`; infinite runs continue
after one INIT until Stop and still require `--allow-buffer-overflow-risk`.
Reading-memory limits and overflow monitoring remain in force. Abort stops new
virtual triggers while retaining buffered readings for existing tail handling;
another INIT resets the simulated acquisition. Simulation does not validate
physical External edge timing, hardware timeouts, or re-arm behavior.

Simple Immediate infinite simulation keeps its existing acquisition pace.
Consumers must arrange a bounded Stop and drain stdout continuously rather
than accumulate unlimited sample output in memory.

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

## Optional Run-Bound Streaming

`start-trigger-record --streaming --json` opts in to the
[Common Optional Streaming Extension](common-streaming-extension.md).
`--streaming` defaults off and requires `--status-format jsonl` (or the start
command's `--json` alias). Text output is rejected before profile resolution
or connection. JSONL alone does not select the extension.

The lifecycle is `run_bound`: one Worker owns one acquisition, including its
tail handling. There is no deferred start or reusable acquisition. The six
existing trigger modes retain their capture and stop behavior; Software Timer
remains an option of Software. Finite Custom runs end naturally, while Infinity
Custom runs continue until an existing stop condition. Capability, parameter,
and exact live-support checks still apply; opting in grants no additional
instrument or connection support.

Core owns one in-memory stream state shared by JSONL and HTTP. `ready` declares
only `stream.lifecycle: "run_bound"`. Every JSONL `status` and `GET /status`
contains `stream: {"lifecycle": "run_bound", "state": "waiting|active|ended"}`
and the runtime's `run_id`. HTTP status performs no instrument I/O. The state
advances once through `waiting -> active -> ended`, or `waiting -> ended`.

| Mode | Active evidence |
| --- | --- |
| Immediate | A successful measurement read, before its Sample Event. |
| Software | Initialization succeeded and execution entered the software-trigger handling loop. This is host readiness to handle a trigger, not a claim that hardware is already armed. |
| Software + Timer | Initialization succeeded and execution entered the existing timer workflow; this is host scheduling readiness. |
| Immediate Custom | Existing buffered-data availability or successful data retrieval. |
| Software Custom | A waiting-for-trigger observation before the first trigger, or buffered-data evidence. |
| External | A waiting-for-trigger observation, or existing completion handling followed by successful data retrieval. |
| External Custom | A waiting-for-trigger observation or buffered-data evidence. |

Active is a historical readiness milestone, not a promise of remaining
measurement time or immediate acceptance of another trigger. Fast runs may
emit active and ended close together. Worker readiness, an `INIT` write,
thread creation, and status message text are not acquisition evidence.

Software Custom and External Custom observe `STAT:OPER:COND?` in their existing
no-data execution paths; External observes it after a successful, incomplete
Status Byte poll. The operation-condition waiting bit (`0x0020`) is distinct
from the Status Byte completion indication. Queries run only when streaming
is selected, before active, and before stop. The first eligible query can run
immediately; subsequent queries start at least 200 ms after the previous query
finishes. There is no new polling thread or VISA timeout. External skips a
query if its existing remaining wait budget cannot accommodate the current
I/O timeout. Existing INIT, ABOR, trigger, timeout/re-arm, and per-trigger
Software Custom safety checks remain unchanged.

A valid not-ready reply leaves the stream waiting. A new observation timeout,
communication failure, or invalid register reply is a fatal acquisition error:
stop the run and perform existing finalization, without retry, fallback, or an
additional error-queue query. It is not a normal hardware-trigger timeout.
This is a Meters fail-closed policy, not a Common requirement. A synchronous
query can delay trigger handling even with the rate limit; model-appropriate
validation must establish waiting-bit meaning and acceptable behavior when a
trigger arrives during a query, including timeout/re-arm and stop handling.
Simulator behavior is not evidence of real-instrument timing or live support.

Emit active before the first Sample Event. Stop disables new observations,
but retained final-drain data can still establish active. Emit ended only after
the worker and its existing tail handling terminate, before summary. A failed
observation remains a failure even when tail data establishes active:
`waiting -> failure -> stop/drain -> active -> sample -> ended -> summary(ok=false)`.
Ended does not certify data integrity or successful cleanup. Sample and summary
payloads do not gain stream fields. Consumers must continue reading structured
cleanup output to EOF and separately inspect process exit. Early connection
failure does not manufacture ready or ended events.

With streaming, CSV is disabled unless `--csv PATH` is explicit.
An explicitly empty or whitespace-only CSV path is a parameter error
(exit code `2`) in both ordinary and Streaming runs, including dry-run.
It is rejected before profile resolution, instrument connection, HTTP
startup, or file creation.
`--streaming --no-csv` is accepted; `--csv` and `--no-csv` remain mutually
exclusive. CSV format options do not enable saving. Without streaming, existing
default CSV behavior remains. Dry-run validates these rules and previews CSV
selection but does not declare a runtime stream. The CLI does not create
additional JSONL, report, or log artifacts; wrappers retain their own rules.

## Orchestrator Quickstart

Use this order for agent-controlled runs:

1. Run `start-trigger-record --dry-run --status-format jsonl` and validate the
   single `dry_run` object. Dry-run has no `run_id` and emits no `ready` event.
2. Run the same acquisition shape with `--simulate --status-format jsonl` and a
   finite bound such as `--max-samples`, or opt in to `--streaming` and arrange
   a bounded Stop for infinite simulation.
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

Meters supports exactly one domain command, `software_trigger`, with
`kind: "control"`; no async job is created and no common job terminal is
emitted. The Worker has `execution.model: "run_bound"` and
`execution.context_binding: "startup"`. Command-level `context` is forbidden.

Request: `{"schema_version":3,"command":"software_trigger","arguments":{"metadata":{}},"job_id":"client-1"}`.
`arguments` and its `metadata` member may be omitted and default to objects.
String metadata is preserved; non-string JSON metadata values are compactly
serialized into sample `trigger_metadata`. A supplied `job_id` is echoed as
correlation only; it does not deduplicate work or enter measurement metadata.

Valid commands return HTTP 202:
`{"schema_version":3,"run_id":"r1","status":"accepted","command":"software_trigger","job_id":"client-1","kind":"control","worker_job_id":null,"error":null}`.

Invalid JSON, version tokens (including `3.0`, `3e0`, `true`, and `"3"`),
unknown top-level fields, request `context`, and invalid metadata return
HTTP 400 without queue admission or instrument I/O. Existing queue-full and
rate-limit admission rejection return HTTP 429. All responses carry the
Common command envelope, preserving the original `reason` diagnostics;
rejections and errors include a Common Error with domain diagnostics in
`details.domain_error`. Software-trigger commands in hardware-trigger modes
retain their existing possible ignored-event behavior.

### `POST /stop`

Accepts an empty body, `{}`, or an object containing only optional
`schema_version: 3` and `reason: string`. Invalid versions and fields return
HTTP 400 Common Error without publishing Stop. Valid Stop retains HTTP 202,
with `{"schema_version":3,"run_id":"r1","status":"accepted","error":null}`.
Repeated Stop acknowledges without publishing another control event or starting
another Stop callback. Stop acceptance is not evidence of acquisition
completion or cleanup. The original high-priority control event, cooperative
`engine.stop()`, worker join and Core-owned cleanup order are unchanged.

### `GET /status`

Returns a non-mutating HTTP 200 Common Status object with exact integer
`schema_version: 3`, `timestamp_utc`, non-empty `run_id`,
`worker_state` (`running`, `stopping`, or `failed`), `fatal_error`
(Common Error or null), the control URLs, and runtime `features`.
Existing Meters-specific `status`, queue, `captured`, `errors`,
`trigger_count_infinite`, `expected_readings`, `overflow_monitoring`,
`overflow_detected`, `stop_reason`, `final_drain_complete`, and
`data_integrity` fields are retained with their existing meanings.
A fatal acquisition error establishes `worker_state: "failed"` and preserves
the domain diagnostic under `fatal_error.details.domain_error`.

The runtime declares `features: {}` unless `--streaming` opted in. With
streaming it declares `common.streaming` contract version 1 and lifecycle
`run_bound` plus the existing monotonic stream state snapshot. There are no
common async jobs or job cancellation features.

A status-provider/handler failure that can be represented structurally returns
HTTP 500 with Common Error category `worker`, code `status_failed`, and the
runtime `run_id`; it cannot be treated as a valid status snapshot. Loss of
connection is a communication failure and may have no JSON response.
Status reads perform no instrument I/O and do not mutate queues.

The `meters-tool status --json` and `wait-ready --json` clients normalize
Worker 3 into their independent single-response CLI schema 2; `wait-ready`
requires `worker_state: "running"` and `fatal_error: null`, not merely
a reachable HTTP 200.

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
while `dry_run_writes_csv` remains false for every dry-run. The Worker
uses protocol schema 3; the independent dry-run and artifact schemas remain unchanged.

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
`finite-custom`, `infinite-custom`, `overflow`, `worker-streaming`, and `full`
suites. `keysight-34461a` also supports `external`; the base 34460A profile rejects
that suite and omits EXT cases from all Custom and Streaming selections. The old
`stream` suite name is rejected without an alias.

The Custom suites use DC current and cover each supported IMM/BUS/EXT mode
with monitoring alone and Stop on overflow. `finite-custom` checks normal finite
completion; `infinite-custom` preserves infinite acquisition with scheduled Stop,
continuous drain and cleanup without enabling `--streaming`. `overflow` covers
both finite and infinite counts. Selecting it supplies the script-level opt-in;
there is no additional script flag. The intentional-overflow warning, interactive
Enter confirmation, redirected-stdin refusal and CLI `--allow-buffer-overflow-risk`
acknowledgement remain in effect. Every overflow case requires exit `3`,
`summary.ok=false`, confirmed overflow, and incomplete data integrity. Monitor-only
cases also require a sample after overflow followed by an active status before
scheduled Stop; samples obtained only during final drain cannot satisfy this
check. The boolean result is retained as
`runtime_evidence.continued_drain_after_overflow`. The bounded final drain outcome
is recorded even when incomplete.

The `frequency-period` suite runs one immediate Auto Range Frequency sample and
one immediate Auto Range Period sample with a `20` Hz AC filter, `0.1` second
gate time, automatic Frequency timeout, and no Period timeout command.
`keysight-34461a` `full` includes basic, Frequency/Period, external and finite
Custom (20 cases). `keysight-34460a` `full` includes basic, Frequency/Period and
finite Custom (16 cases). Infinite Custom, intentional overflow and Worker
Streaming are excluded from `full`.

`worker-streaming` starts the CLI with `--streaming --json` and explicit CSV
output. It selects representative DC-current cases: immediate, software trigger,
software timer, and finite/infinite IMM/BUS Custom on both models (7 cases).
34461A adds simple external and finite/infinite EXT Custom (10 cases total).
Custom Streaming cases monitor overflow without intentionally inducing it.
During execution the wrapper observes ordered JSONL Active before sending a
software trigger or prompting for the stated number of external trigger edges.
It checks HTTP run correlation for cases needing harness control; HTTP Ready is
not an Active observation. Known errors, stopping or Ended observations withhold
further triggers. HTTP and JSONL snapshots need not have identical instantaneous
states. Software Timer remains runtime-scheduled; the wrapper checks Active
before Sample and does not send its trigger.

The wrapper accepts an omitted Waiting event, checks monotonic states and samples
only during Active, then requires Ended, matching Summary/sample/CSV counts and
exit status. Infinite cases require planned HTTP Stop and complete final drain.
Output is drained through EOF even after Summary or failure. Active, run, control
client, Stop grace and output-drain waits are bounded. A failed run requests HTTP
Stop before any forced termination. Forced termination always fails and marks
cleanup unconfirmed; subsequent cases stop and require operator inspection.
Cleanup messages are evidence of reported release results, not proof of close.
These checks do not change the worker lifecycle, HTTP protocol or product schemas.

The wrapper records `runtime_evidence.streaming` for lifecycle observations,
trigger counts, control gates, EOF and failures, plus cleanup/exit observations.
Its report and summary list `not_run_cases` and `unverified_observations`. The
live Stop Before Active race is excluded from routine execution and marked
`not_run`; no-hardware checks validate acceptance of the zero-sample, no-Active,
Ended/Summary/normal-exit outcome. The wrapper neither opens another VISA
session for `unverified_observations` nor adds runtime hooks.

Plans, simulator and synthetic results do not establish real-instrument support;
evidence applies only to the model, transport, backend, measurement and exact
scope exercised. The [CLI suite matrix](../cli/README.md#cli-validation-scripts)
describes case selection, deadlines and operator requirements.

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
`release_to_local`, and `close`.

`summary.md` is not a schema source of truth. Orchestrators should read
`report.json` for pass/fail decisions and use `summary.md` only for operator
handoff.
