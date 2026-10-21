# Common CLI JSON / JSONL Contract

Schema version: `2`

Contract revision: `2.2`

Compatibility policy: `v2-only`

The contract revision identifies this Common document-set revision. Runtime
wire compatibility is determined by `schema_version`, not by the contract
revision.

This document defines shared JSON and JSONL envelope rules for command-line
Tool Workers and their client commands. Tool-specific commands, event payloads,
aliases, execution context, identity fields, and artifact fields belong in
Worker-specific contract documents.

## Machine Output

In JSON or JSONL mode, every non-empty stdout line must be a JSON object.
JSONL mode emits one JSON object per line. Single-response JSON mode emits one
JSON object for a completed command.

Human-readable text is diagnostic output, not the agent contract. Machine
callers should parse JSONL events, single-response JSON, structured artifacts,
and process exit codes instead of text-mode stdout.

Every Common v2 machine-output object must contain exact integer
`schema_version: 2`. Missing, boolean, string, floating-point, and schema
version `1` values are invalid.

Consumers must ignore unknown fields. Producers may add optional fields under
schema version `2`. Removing required fields or changing required field types
requires a major schema version bump.

## Common Fields

Common JSON object fields:

- `event`: object type or command result type.
- `schema_version`: exact integer `2`.
- `timestamp_utc`: UTC timestamp serialized as ISO 8601.
- `run_id`: runtime correlation ID when the command creates a runtime session.
- `ok`: boolean command or runtime health summary when the object represents a
  result.
- `message`: diagnostic message intended for logs and operator context.
- `fatal_error`: fatal runtime error text or object when a Worker cannot
  continue.
- `exit_code`: intended process exit code when the object represents an error.

Common event values:

- `ready`: local control plane can accept lifecycle requests.
- `status`: runtime progress or state update.
- `error`: structured usage, request, or runtime error after JSON handling has
  started.
- `summary`: final runtime summary.
- `dry_run`: plan-only preview object that does not start a runtime session.
- `message`: structured informational message.

A runtime `ready` event must contain `event: "ready"`, exact integer
`schema_version: 2`, a non-empty string `run_id`, and non-empty string
`status_url`, `command_url`, and `stop_url` fields. Worker-specific
contracts may add fields.

Worker-specific contracts may define additional event values and fields.

## Optional Streaming Fields

These fields apply only to runtimes explicitly adopting the
[Common Optional Streaming Extension](common-streaming-extension.md). Presence
of the `stream` object declares adoption for this runtime, not merely an
available capability. No separate enabled flag or extension version is added.
Absence of `stream` must not be interpreted as adoption.

| Output | Required extension fields |
| --- | --- |
| `ready` | `stream.lifecycle` |
| JSONL `status` and `GET /status` | `stream.lifecycle`, `stream.state` |

`stream` is a JSON object. `lifecycle` is the string `run_bound` or
`deferred_start` and remains fixed for the runtime. `state` is the string
`waiting`, `active`, or `ended`; its meaning and event ordering are defined in
the [extension lifecycle](common-streaming-extension.md#lifecycle-and-state).
`ready.stream` declares only the lifecycle, without a state field. Every JSONL
status event and HTTP status response in an opted-in runtime carries the
current stream snapshot, together with the same non-empty top-level `run_id`.
This does not replace any Worker-specific top-level `status` field.

The extension adds no `stream` object to data events or `summary`. Existing
event names, payloads, counts, and quality fields remain Worker-specific.
Data events retain the runtime's `run_id`; the extension adds no stream ID,
sequence, or last-sequence field. Workers and consumers continue to follow the
Common unknown-field compatibility rule.

The following examples show complete Common envelopes; Worker-specific
contracts may require additional fields. Endpoint URLs are illustrative.
An opted-in `ready` declaration does not assert source readiness:

```json
{
  "event": "ready",
  "schema_version": 2,
  "timestamp_utc": "2026-01-01T00:00:00Z",
  "run_id": "example-run",
  "status_url": "http://localhost:8000/status",
  "command_url": "http://localhost:8000/command",
  "stop_url": "http://localhost:8000/stop",
  "stream": {"lifecycle": "run_bound"}
}
```

A subsequent JSONL status reports source readiness before the first data event:

```json
{
  "event": "status",
  "schema_version": 2,
  "timestamp_utc": "2026-01-01T00:00:01Z",
  "run_id": "example-run",
  "stream": {"lifecycle": "run_bound", "state": "active"}
}
```

While HTTP is still available, a later `GET /status` response can report the
terminal source state. This does not assert successful cleanup:

```json
{
  "schema_version": 2,
  "timestamp_utc": "2026-01-01T00:00:02Z",
  "run_id": "example-run",
  "stream": {"lifecycle": "run_bound", "state": "ended"}
}
```

## Parsing Guidance

For one runtime session, all non-dry-run runtime events should use the same
`run_id`. A dry-run object should omit `run_id` when no runtime session is
created.

A final summary with `ok: true` indicates normal command-level completion. A
summary with `ok: false`, a structured error object, a non-zero process exit
code, or a missing final summary should be treated as failed or incomplete by
orchestrators.

A summary is a result report, not an assertion that Worker cleanup has
completed or that stdout has ended. Cleanup may emit further structured
messages. Consumers must continue reading through stdout EOF and also observe
the process exit code. The extension's terminal `status` event does not replace
these checks; see its [event ordering](common-streaming-extension.md#event-ordering-and-shutdown).

Usage and validation failures should exit `2`. Runtime, connection, request,
and fatal Worker failures should exit `3`. Success, accepted requests, and
dry-run success should exit `0`.

Argument parser usage errors may still be reported on process stderr with exit
code `2`. Structured errors that occur after command handling has entered JSON
or JSONL mode should be emitted as JSON objects.

## Client Diagnostics

Client commands that contact a local Worker should include request diagnostics
when knowable:

- `client_command`
- `method`
- `url`
- `endpoint`
- `timeout_ms`
- `elapsed_ms`
- `request_sent`
- `reachable`
- `http_status`
- `error_phase`

Validation errors should use `request_sent: false`. Request failures should use
`request_sent: true` when an HTTP request was attempted.
