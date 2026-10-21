# Meters CLI JSON / JSONL Contract

Common schema version: `2`

Compatibility policy: `v2-only`

Implementation status: `Common v2-only conformant`

Runtime contract revision: `v2.1`

The runtime contract revision tracks this document's evolution only.
Orchestrators must use the JSON `schema_version` field to determine runtime
compatibility and must not use the document revision for runtime negotiation.

This document defines Meters-specific CLI JSON and JSONL payloads. Shared
envelope rules, schema version policy, parsing guidance, and generic client
diagnostics are defined in
[Common CLI JSON / JSONL Contract](common-cli-jsonl-contract.md). The Meters
worker control plane and artifacts are defined in
[Meters Worker Contract](meters-worker-contract.md).

Consumers must ignore unknown fields, following the common envelope contract.

The current CLI implementation produces Common schema `2` machine output and
rejects non-v2 Worker lifecycle responses. Wrapper `report.json` schemas remain
separately versioned at schema `1` and are unchanged by this migration.

Every Common v2 JSON or JSONL object uses exact integer
`schema_version: 2`.

## Execution Context

Meters binds Common execution context at `start-trigger-record` startup. Live
`--model` maps to `expected_model_id`; simulate and dry-run `--model` map to
`planning_model_id`. Meters does not define `planning_profile_id`. The
startup-bound context is derived from the start arguments and is not
repeated in `POST /command`.

## JSONL Events

`start-trigger-record --status-format jsonl` emits one JSON object per line.
`start-trigger-record --json` is an alias for the same JSONL output.

Supported event values:

- `message`
- `ready`
- `status`
- `sample`
- `error`
- `summary`
- `dry_run`

Selected fields:

- `ready`: `run_id`, `service`, `host`, `port`, `command_url`, `stop_url`,
  `status_url`
- `status`: `message`, `run_id`, and the structured acquisition outcome fields
  listed for `summary` below
- `sample`: `run_id`, `captured`, `measurement_type`,
  `measurement_metadata`, `message`, `resource_id`, `status`, `trigger_id`,
  `trigger_metadata`, `trigger_source`, `unit`, `value`
- `summary`: `run_id`, `captured`, `errors`, `ok`, optional `fatal_error`,
  `trigger_count_infinite`, `expected_readings`, `overflow_monitoring`,
  `overflow_detected`, `stop_reason`, `final_drain_complete`, `data_integrity`
- `error`: `message`, `exit_code`, optional `run_id`
- `dry_run`: plan fields for the command being previewed, including
  `csv_enabled` and nullable `csv_path`; no `run_id` and no `ready` event

For one non-dry-run `start-trigger-record` session, `ready`, `status`,
`sample`, and `summary` events use the same `run_id`. Sample
`measurement_metadata` is always present and is `{}` when the selected
measurement has no extra metadata. `voltage-dc-ratio` can include
signal/reference voltage metadata when the backend supports `DATA2?`.

`run_id` is a UUID string generated after validation for each non-dry-run
`start-trigger-record` session. It is included on runtime JSONL events so
agents can correlate stdout JSONL, `/status`, and wrapper artifacts for the
same acquisition run. Dry-run preview objects do not include `run_id` because
dry-run does not start a runtime session.

For Custom trigger modes, acquisition `status` and final `summary` events carry
the structured acquisition outcome fields. `trigger_count_infinite` is always
a boolean. `expected_readings` is
`null` for infinite runs. `overflow_monitoring` is `off`, `starting`, `active`,
or `failed`. `overflow_detected` is `null` when monitoring is unavailable,
otherwise `false` or `true`. Once observed, `true` remains latched even if a
later poll fails. `stop_reason` is one of `stop_requested`, `completed`,
`overflow_detected`, `overflow_monitor_failed`, `fatal_error`,
`max_samples_reached`, or `unknown`. `final_drain_complete` is `null` when no
final drain ran, otherwise a boolean. `data_integrity` is `unknown`,
`no_loss_detected`, or `incomplete`. Non-Custom modes report
`overflow_monitoring: "off"`, `overflow_detected: null`,
`final_drain_complete: null`, and `data_integrity: "unknown"`.

`summary.ok` is `false` when `fatal_error` is present, overflow monitoring
failed, overflow was detected, the final drain did not complete, or a finite
Custom capture with overflow monitoring enabled stopped before its expected
reading count. With Infinity, monitor, and Stop on overflow all disabled, a
normal early Stop preserves the legacy successful result and exit `0`, even
when `data_integrity` is `incomplete` because fewer than the requested readings
were captured. This does not claim that the requested count was acquired.
Consumers should still check the process exit code and
treat a missing final summary as an incomplete or failed runtime. A `false`
`summary.ok` exits `3`; this includes structured overflow and incomplete-capture
outcomes as well as fatal worker failures. Meters fatal acquisition failures are
fatal worker failures for the common envelope contract and must exit `3`.

The `ready` event is emitted only by non-dry-run
`start-trigger-record --status-format jsonl` and the `--json` alias after the
HTTP control plane starts. It means `/command`, `/stop`, and `/status` can
accept local HTTP requests. It does not mean the acquisition worker has
captured a first sample.

## Single-Response JSON

These commands accept `--format json` and the `--json` alias:

- `capabilities`
- `list-resources`
- `manifest`
- `send-command`
- `stop`
- `status`
- `wait-ready`

Alias rules:

- `capabilities --json` is the same as `--format json`
- `list-resources --json` is the same as `--format json`
- `manifest --json` is the same as `--format json`
- `send-command --json` is the same as `--format json`
- `stop --json` is the same as `--format json`
- `status --json` is the same as `--format json`
- `wait-ready --json` is the same as `--format json`
- `start-trigger-record --json` is the same as `--status-format jsonl`

Conflicts exit with code `2`.

### Capability Discovery

`capabilities --json` emits one `event: capabilities` object and exits `0`.
It does not create a VISA resource manager, scan or open resources, start a
Worker or HTTP server, or create CSV or other output files. Optional
`--model MODEL` selects an offline Core capability profile using the normal
Core profile-resolution rules. It is not persisted and never overrides the
model detected from `*IDN?` by a later live run.

The capability object contains:

- `selection`: the optional `requested_model` and a `source` of
  `requested_model` or `default_fallback`.
- `runtime_identity`: `detection_performed: false` with null identity fields,
  because capability discovery performs no live detection.
- `capability_profile`: Core-owned `vendor`, `model`, canonical `model_id`,
  `reading_memory_limit`, and buffered-reading-memory support.
- `available_profiles`, `measurements`, `trigger_modes`, and `limits` derived
  from Core capability, profile, and validation data.
- `support`: Core `start-trigger-record` mode and exact live support scopes,
  including `validation_status`, `transport_scope`, `backend_scope`, and each
  measurement/trigger feature's canonical `feature_kind`, `feature_value`, and
  validation status.

`measurements[].measurement_name` is the canonical CLI request spelling, such
as `current-dc`, while `measurements[].measurement_type` is the Core-normalized
type, such as `current_dc`. For measurement feature scopes, `feature_value`
uses that Core-normalized type, so consumers can join it to
`measurements[].measurement_type`. Trigger-mode feature values retain the
existing Core canonical semantics.

For Product support decisions, consumers must not treat the aggregate live
`validation_status` as sufficient. Product mode requires an exact matching
transport/backend scope whose connection status is
`live_validated_full_suite`, plus `live_validated_full_suite` entries for the
requested measurement and trigger mode in that same scope. Pending, missing,
unknown, and model-unsupported scopes remain fail-closed. The CLI serializes
Core statuses and does not add a separate `product_open` decision field.

The machine payload excludes WebUI presentation fields and Core support-policy
evidence, notes, and private validation artifact paths. An unsupported model is
a validation error: JSON mode emits one `event: error` object with
`exit_code: 2`, while text mode writes the diagnostic to stderr.

`send-command`, `stop`, and `status` accept client `--timeout-ms`
values from `100` to `600000`. Their default is `3000` ms.
`wait-ready --timeout-ms` uses the same validation range, defaults to
`10000` ms, and is an overall readiness deadline. Each `/status` request made
by `wait-ready` uses at most `1000` ms and polling uses a fixed 200 ms
interval.

### Tool Manifest

`manifest --json` emits one `event: tool_manifest` object and exits `0`. The
command is pure static introspection: it does not create a VISA resource
manager, enumerate or open resources, query `*IDN?`, start acquisition,
start a Worker runtime session or HTTP server, create CSV or other output
files, or modify persistent configuration. It describes the tool itself and
its protocol compatibility; instrument/model capabilities remain the
responsibility of `capabilities`.

The manifest object contains:

- `event`: `tool_manifest`.
- `schema_version`: exact integer `2`, the Common runtime schema version this
  tool emits.
- `tool_id`: `meters`.
- `tool_version`: the single distribution package version.
- `worker_protocol`: `schema_versions: [2]` with compatibility policy
  `v2-only`; the Worker command/status protocol accepts Common schema `2`
  only, without fallback or negotiation.

`send-command` defaults to `--command software_trigger`,
`--arguments-json {}`, no `--job-id`, `--format text`, and
`--timeout-ms 3000`. It places the complete JSON object from
`--arguments-json` in the command envelope and validates the envelope with the
Meters command parser before sending. Under Common v2 the sent envelope also
contains exact integer `schema_version: 2`. Invalid JSON, a non-object arguments
value, non-object metadata, and unknown commands exit `2` without a request.

`status` wraps non-mutating `GET /status` and emits a flat normalized JSON
object. `wait-ready` emits the same status fields after any successful `200`
JSON response from `/status`, plus `attempts`, `elapsed_ms`, and `timeout_ms`.

The normalized status fields include:

- `event`: `status` or `wait-ready`
- `client_command`
- `method`
- `url`
- `endpoint`
- `schema_version`
- `timestamp_utc`
- `ok`: `true` only when the endpoint was reachable and `fatal_error` is
  `null`
- `reachable`
- `request_sent`
- `running`
- `stopping`
- `port`
- `http_status`
- `timeout_ms`
- `elapsed_ms`
- `worker_schema_version`
- `worker_timestamp_utc`
- `service`
- `run_id`
- `status`
- `command_url`
- `stop_url`
- `status_url`
- `queue_size`
- `queue_max`
- `min_interval_ms`
- `captured`
- `errors`
- `fatal_error`
- `trigger_count_infinite`
- `expected_readings`
- `overflow_monitoring`
- `overflow_detected`
- `stop_reason`
- `final_drain_complete`
- `data_integrity`

Reachable status responses exit `0` even when `fatal_error` is not `null`.
Machine callers should read `ok` and `fatal_error` to distinguish worker
health from client reachability.

Unreachable endpoints, HTTP request failures, invalid `/status` JSON, and
`wait-ready` deadline expiry exit `3` and emit a JSON object with request
diagnostics, `ok: false`, `reachable: false`, `running: false`,
`stopping: false`, `error_phase: "request"`, `exit_code: 3`, and `message`.
`http_status` is included only when an HTTP response was received.

`send-command` and `stop` keep `event: "error"` for request and
validation failures. In contract `v1.5`, those JSON error objects add
`client_command`, `ok: false`, `port`, `request_sent`, `error_phase`,
`reachable`, `method`, `url`, `endpoint`, `timeout_ms`, optional `elapsed_ms`,
and optional `http_status`. Validation errors use
`error_phase: "validation"` and `request_sent: false`; request failures use
`error_phase: "request"` and `request_sent: true`.

Successful `send-command` and `stop` responses include the same additive
client diagnostics when knowable: `method`, `url`, `endpoint`, `timeout_ms`,
and `elapsed_ms`.

In contract `v1.6`, `send-command` parses the worker response envelope and
merges `command`, `job_id`, `reason`, `error`, and `message` into its JSON
diagnostics when present. Worker HTTP `400` is a validation failure and exits
`2`. HTTP `409`, `429`, other HTTP/request failures, and invalid or empty
successful response bodies exit `3`.

## Dry-Run Previews

`send-command --dry-run`, `stop --dry-run`, and `status --dry-run`
do not send HTTP requests. `wait-ready` has no dry-run mode.

Preview objects include:

- `event: dry_run`
- `status: dry_run`
- `method`
- `url`
- `endpoint`
- `body`
- `send_request: false`
- `client_command`
- `ok: true`
- `port`
- `request_sent: false`
- `schema_version`
- `timestamp_utc`

`send-command --dry-run` still validates `--port` and `--arguments-json` JSON first.
`status --dry-run` previews `method: GET`,
`url: http://127.0.0.1:<port>/status`, and `body: null`.

`list-resources --dry-run` emits text by default and one dry-run contract
object when combined with `--json`. It exits `0` and does not create a VISA
resource manager, list VISA resources, open resources, query `*IDN?`, or run
release/local cleanup.

The JSON dry-run object includes:

- `event: dry_run`
- `command: list-resources`
- `status: dry_run`
- `output_format`
- `verify`
- `live_only`
- `effective_verify`
- `dry_run_performs_visa_io: false`
- `planned_real_run`
- `schema_version`
- `timestamp_utc`

`planned_real_run` describes what a real run would do, including
`list_visa_resources`, `open_each_resource`, `query_idn`,
`release_to_local_after_successful_verify`, `close_each_resource`, and
`filter_live_only`. `--live-only` still sets `effective_verify: true` in the
contract because a real live-only run would verify and filter resources.
The existing release-to-local fields remain in the schema with value `false`;
resource verification closes the session immediately after its `*IDN?` query.

`list-resources --json` real-run output keeps `resources`, `verify`, and
`live_only` semantics and adds `event: list-resources`, `schema_version`,
`timestamp_utc`, `count`, `live_count`, `stale_count`, and
`diagnostic_hints`.

`start-trigger-record --dry-run --status-format jsonl` keeps the existing plan
fields and adds explicit safety fields: `dry_run_performs_visa_io: false`,
`dry_run_writes_csv: false`, and `dry_run_starts_http_server: false`.

Contract revision `v2.1` additively adds `csv_enabled` to this dry-run object.
`csv_path` is a Meters-specific, conditionally nullable dry-run plan field,
not a Common required envelope field. When `csv_enabled` is `true`, `csv_path`
is the resolved explicit or timestamped default path; when `csv_enabled` is
`false`, `csv_path` is `null`. Consumers using `--no-csv` must accept this null
value under Common `schema_version: 2`.
`dry_run_writes_csv` remains `false` in both cases because dry-run itself never
writes a file. Consumers must not use it as a substitute for `csv_enabled`.
This Meters-specific additive extension does not change Common
`schema_version: 2`.
