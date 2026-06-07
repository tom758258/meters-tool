# Meters CLI JSON / JSONL Contract

Schema version: `1`

Runtime contract revision: `v1.6`

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
- `status`: `message`, `run_id`
- `sample`: `run_id`, `captured`, `measurement_type`,
  `measurement_metadata`, `message`, `resource_id`, `status`, `trigger_id`,
  `trigger_metadata`, `trigger_source`, `unit`, `value`
- `summary`: `run_id`, `captured`, `errors`, `ok`, optional `fatal_error`
- `error`: `message`, `exit_code`, optional `run_id`
- `dry_run`: plan fields for the command being previewed; no `run_id` and no
  `ready` event

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

`summary.ok` is `true` when the runtime completed without a fatal error and
`false` when `fatal_error` is present. Consumers should still check the process
exit code and treat a missing final summary as an incomplete or failed runtime.
Meters fatal acquisition failures are fatal worker failures for the common
envelope contract and must exit `3`.

The `ready` event is emitted only by non-dry-run
`start-trigger-record --status-format jsonl` and the `--json` alias after the
HTTP control plane starts. It means `/command`, `/stop`, and `/status` can
accept local HTTP requests. It does not mean the acquisition worker has
captured a first sample.

## Single-Response JSON

These commands accept `--format json` and the `--json` alias:

- `list-resources`
- `send-command`
- `stop`
- `status`
- `wait-ready`

Alias rules:

- `list-resources --json` is the same as `--format json`
- `send-command --json` is the same as `--format json`
- `stop --json` is the same as `--format json`
- `status --json` is the same as `--format json`
- `wait-ready --json` is the same as `--format json`
- `start-trigger-record --json` is the same as `--status-format jsonl`

Conflicts exit with code `2`.

`send-command`, `stop`, and `status` accept client `--timeout-ms`
values from `100` to `600000`. Their default is `3000` ms.
`wait-ready --timeout-ms` uses the same validation range, defaults to
`10000` ms, and is an overall readiness deadline. Each `/status` request made
by `wait-ready` uses at most `1000` ms and polling uses a fixed 200 ms
interval.

`send-command` defaults to `--command software_trigger`,
`--arguments-json {}`, no `--job-id`, `--format text`, and
`--timeout-ms 3000`. It places the complete JSON object from
`--arguments-json` in the command envelope and validates the envelope with the
Meters command parser before sending. Invalid JSON, a non-object arguments
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

`list-resources --json` real-run output keeps `resources`, `verify`, and
`live_only` semantics and adds `event: list-resources`, `schema_version`,
`timestamp_utc`, `count`, `live_count`, `stale_count`, and
`diagnostic_hints`.

`start-trigger-record --dry-run --status-format jsonl` keeps the existing plan
fields and adds explicit safety fields: `dry_run_performs_visa_io: false`,
`dry_run_writes_csv: false`, and `dry_run_starts_http_server: false`.
