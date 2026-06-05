# Common CLI JSON / JSONL Contract

Schema version: `1`

This document defines shared JSON and JSONL envelope rules for command-line
instrument workers and their client commands. Instrument-specific commands,
event payloads, aliases, and artifact fields belong in instrument-specific
contract documents.

## Machine Output

In JSON or JSONL mode, every non-empty stdout line must be a JSON object.
JSONL mode emits one JSON object per line. Single-response JSON mode emits one
JSON object for a completed command.

Human-readable text is diagnostic output, not the agent contract. Machine
callers should parse JSONL events, single-response JSON, structured artifacts,
and process exit codes instead of text-mode stdout.

Consumers must ignore unknown fields. Producers may add optional fields under
schema version `1`. Removing required fields or changing required field types
requires a major schema version bump.

## Common Fields

Common JSON object fields:

- `event`: object type or command result type.
- `schema_version`: integer schema version, currently `1`.
- `timestamp_utc`: UTC timestamp serialized as ISO 8601.
- `run_id`: runtime correlation ID when the command creates a runtime session.
- `ok`: boolean command or runtime health summary when the object represents a
  result.
- `message`: diagnostic message intended for logs and operator context.
- `fatal_error`: fatal runtime error text or object when a worker cannot
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

Instrument-specific contracts may define additional event values and fields.

## Parsing Guidance

For one runtime session, all non-dry-run runtime events should use the same
`run_id`. A dry-run object should omit `run_id` when no runtime session is
created.

A final summary with `ok: true` indicates normal command-level completion. A
summary with `ok: false`, a structured error object, a non-zero process exit
code, or a missing final summary should be treated as failed or incomplete by
orchestrators.

Usage and validation failures should exit `2`. Runtime, connection, request,
and fatal worker failures should exit `3`. Success, accepted requests, and
dry-run success should exit `0`.

Argument parser usage errors may still be reported on process stderr with exit
code `2`. Structured errors that occur after command handling has entered JSON
or JSONL mode should be emitted as JSON objects.

## Client Diagnostics

Client commands that contact a local worker should include request diagnostics
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
