# CLI JSON / JSONL Contract

Schema version: `1`

Runtime contract revision: `v1.5`

For the broader worker control plane, runtime modes, and wrapper artifact
schema, see [Meters Worker Contract](worker-contract.md).

## JSONL events

`start-trigger-record --status-format jsonl` emits one JSON object per line.
`start-trigger-record --json` is an alias for the same JSONL output.

In JSON or JSONL mode, every non-empty stdout line must be a JSON object.
Human-readable text belongs to text mode or stderr. Orchestrators should not
depend on text-mode stdout.

Consumers must ignore unknown fields. New optional fields may be added under
schema version `1`. Removing required fields or changing required field types
requires a major schema version bump.

Supported event values:

- `message`
- `ready`
- `status`
- `sample`
- `error`
- `summary`
- `dry_run`

Common fields:

- `event`
- `schema_version`
- `timestamp_utc`
- `run_id` on non-dry-run `start-trigger-record` runtime events

Selected fields:

- `ready`: `run_id`, `service`, `host`, `port`, `trigger_url`, `stop_url`, `status_url`
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

Machine callers should parse JSONL, single-response JSON, CSV files, and
wrapper `report.json` artifacts. Human-readable text is diagnostic output, not
the agent contract.

`run_id` is a UUID string generated after validation for each non-dry-run
`start-trigger-record` session. It is included on runtime JSONL events so
agents can correlate stdout JSONL, `/status`, and wrapper artifacts for the
same acquisition run. This is backward-compatible: `schema_version` remains
`1`, and existing parsers may ignore the optional field.

Dry-run preview objects do not include `run_id` because dry-run does not start
a runtime session.

`summary.ok` is `true` when the runtime completed without a fatal error and
`false` when `fatal_error` is present. Consumers should still check the process
exit code and treat a missing final summary as an incomplete or failed runtime.

The `ready` event is emitted only by non-dry-run
`start-trigger-record --status-format jsonl` and the `--json` alias after the
HTTP control plane starts. It means `/trigger`, `/stop`, and `/status` can
accept local HTTP requests. It does not mean the acquisition worker has
captured a first sample.

Argparse usage errors may still be reported on process stderr with exit code
`2`. Structured errors that occur after command handling has entered JSON or
JSONL mode are emitted as JSON objects.

## Single-response JSON

These commands accept `--format json` and the `--json` alias:

- `list-resources`
- `soft-trigger`
- `soft-stop`
- `soft-status`
- `wait-ready`

Alias rules:

- `list-resources --json` is the same as `--format json`
- `soft-trigger --json` is the same as `--format json`
- `soft-stop --json` is the same as `--format json`
- `soft-status --json` is the same as `--format json`
- `wait-ready --json` is the same as `--format json`
- `start-trigger-record --json` is the same as `--status-format jsonl`

Conflicts exit with code `2`.

`soft-trigger`, `soft-stop`, and `soft-status` accept client `--timeout-ms`
values from `100` to `600000`. Their default is `3000` ms.
`wait-ready --timeout-ms` uses the same validation range, defaults to
`10000` ms, and is an overall readiness deadline. Each `/status` request made
by `wait-ready` uses at most `1000` ms and polling uses a fixed 200 ms interval.

`soft-status` wraps non-mutating `GET /status` and emits a flat normalized JSON
object. `wait-ready` emits the same status fields after any successful `200`
JSON response from `/status`, plus `attempts`, `elapsed_ms`, and `timeout_ms`.
The normalized status fields include:

- `event`: `soft-status` or `wait-ready`
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
- `trigger_url`
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
health from client reachability. Unreachable endpoints, HTTP request failures,
invalid `/status` JSON, and `wait-ready` deadline expiry exit `3` and emit a
JSON object with `event`, `ok: false`, `reachable: false`, `running: false`,
`stopping: false`, `port`, `request_sent`, `error_phase: "request"`,
`client_command`, `method`, `url`, `endpoint`, `timeout_ms`, `elapsed_ms`,
`exit_code: 3`, and `message`. `http_status` is included only when an HTTP
response was received.

`soft-trigger` and `soft-stop` keep `event: "error"` for request and
validation failures. In contract `v1.5`, those JSON error objects add
`client_command`, `ok: false`, `port`, `request_sent`, `error_phase`,
`reachable`, `method`, `url`, `endpoint`, `timeout_ms`, optional `elapsed_ms`,
and optional `http_status`. Validation errors use `error_phase: "validation"`
and `request_sent: false`; request failures use `error_phase: "request"` and
`request_sent: true`.

Successful `soft-trigger` and `soft-stop` responses include the same additive
client diagnostics when knowable: `method`, `url`, `endpoint`, `timeout_ms`,
and `elapsed_ms`.

## Dry-run previews

`soft-trigger --dry-run`, `soft-stop --dry-run`, and
`soft-status --dry-run` do not send HTTP requests. `wait-ready` has no dry-run
mode.

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

`soft-trigger --dry-run` still validates `--port` and `--meta` JSON first.
`soft-status --dry-run` previews `method: GET`,
`url: http://127.0.0.1:<port>/status`, and `body: null`.

`list-resources --dry-run` emits text by default and one dry-run contract object
when combined with `--json`. It exits `0` and does not create a VISA resource
manager, list VISA resources, open resources, query `*IDN?`, or run
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
