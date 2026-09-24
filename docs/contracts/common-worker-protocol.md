# Common Worker Protocol

Schema version: `2`

Contract revision: `2.1`

Compatibility policy: `v2-only`

The contract revision identifies this Common document-set revision. Runtime
wire compatibility is determined by `schema_version`, not by the contract
revision.

This provisional protocol defines the minimum lifecycle shape shared by Tool
Workers that are launched and observed by an orchestrator. It lives in this
repository until a shared orchestrator repository or Common contract document
set exists.

This document is lifecycle-only. It does not define tool configuration, domain
commands, transport behavior, device command languages, or Worker-specific
runtime semantics. Each tool project must document those details in its own
Worker contract.

## Lifecycle

An orchestrator starts a Worker as a subprocess and observes stdout. In JSON or
JSONL mode, stdout must contain only JSON object lines. Empty stdout lines are
ignored by consumers, but Workers should avoid emitting them in machine mode.

Human-readable text is diagnostic output, not the agent contract. It belongs in
text mode or stderr, and orchestrators must not parse it for pass/fail
decisions.

A Worker emits a `ready` JSONL event when its local control plane is ready to
accept lifecycle requests. `ready` is not a command-complete signal and does
not imply device readiness beyond the Worker-specific contract.

A runtime `ready` event must include `event: "ready"`, exact integer
`schema_version: 2`, a non-empty string `run_id`, and non-empty string
`status_url`, `command_url`, and `stop_url` fields. Worker-specific
contracts may add fields.

`run_id` correlates stdout JSONL, status responses, and artifacts for one
runtime session. Dry-run or plan-only commands may omit `run_id` when they do
not create a runtime session.

Consumers must ignore unknown fields in JSON output objects. Workers may add
optional output fields under schema version `2`; removing required fields or
changing required field types requires a major schema version bump.

## HTTP Endpoints

Common lifecycle endpoints are:

- `GET /status`: non-mutating health and progress check. It must not trigger
  unplanned work, mutate queues, or perform device I/O.
- `POST /command`: Worker command envelope. The Common protocol defines only
  the envelope shape; each Worker contract defines supported command names,
  arguments, acceptance, rejection, and side effects.
- `POST /stop`: graceful stop request. Stop should request orderly Worker
  shutdown through the Worker's documented cleanup path. The endpoint must
  accept an empty request body and may also accept an empty JSON object
  (`{}`). A successful response may be empty or may use Worker-specific
  structured JSON.

The Common `POST /command` request envelope is a JSON object with these allowed
top-level fields:

- `schema_version`: required exact integer `2`.
- `command`: required string command name.
- `arguments`: optional JSON object; omitted means `{}`.
- `job_id`: optional client-provided string that Workers echo in command
  responses.
- `context`: required, optional, or forbidden JSON object as defined by the
  Worker-specific contract.

Unknown top-level fields must be rejected. A top-level field explicitly
forbidden by the Worker-specific contract must also be rejected.

## Mode and Model Context

Common context fields are:

- `mode`
- `expected_model_id`
- `planning_model_id`

`mode` must be `live`, `simulate`, or `dry_run`.

| Mode | Required or allowed | Forbidden |
| --- | --- | --- |
| `live` | optional `expected_model_id` | `planning_model_id` |
| `simulate` | required deterministic planning or simulation identity; use `planning_model_id` unless the Worker-specific contract defines another identity | `expected_model_id` |
| `dry_run` | `planning_model_id`, unless the Worker-specific contract defines another planning identity | `expected_model_id` |

`expected_model_id` is a live identity guard. `planning_model_id` identifies a
physical model used for simulation or planning. Values are canonical,
project-owned identifiers.

A Worker-specific contract may define additional context fields, such as a
nonphysical planning profile. Every `simulate` execution must have a
deterministic planning or simulation identity. A Worker-specific contract may
define another such identity instead of `planning_model_id`. The alternative
remains Worker-specific and does not change the type or meaning of the Common
fields above.

Each Worker-specific contract defines whether context is supplied at Worker
startup, in each command request, or is forbidden in command requests because
execution context is already startup-bound. Unknown context fields not defined
by the Common and Worker-specific contracts, and invalid mode/identity
combinations, must be rejected.

Workers should reject malformed JSON, a non-object body, an invalid or missing
`schema_version`, unknown top-level fields, a missing or non-string `command`,
a non-object `arguments` or `context`, a non-string `job_id`, and an invalid
execution context with a structured validation error. Validation failures must
not perform device I/O or enqueue domain work.

Every `POST /command` HTTP response is a JSON object with this Common envelope:

- `schema_version`: exact integer `2`.
- `status`: `accepted`, `rejected`, or `error`.
- `command`: the safely identifiable client-provided command string, or
  `null`.
- `job_id`: the safely identifiable client-provided string, or `null`.

Accepted responses use `status: "accepted"`. Queue, rate, or other
Worker-specific admission failures use `status: "rejected"` and a
Worker-specific `reason`. Validation and runtime errors use `status: "error"`
with `error` and `message`. The Common protocol does not define
Worker-specific rejection reasons.

This Common protocol does not define `POST /start`. Tool-specific commands
belong in the Worker-specific contract for that tool.

## Exit Codes

Workers should preserve these process exit code meanings:

- `0`: success, accepted request, or dry-run success.
- `2`: usage error, validation error, or bad input.
- `3`: runtime error, connection error, HTTP request failure, or fatal Worker
  failure.

Workers may emit structured JSON errors before exiting when command handling
has reached JSON or JSONL mode. Argument parser usage errors may still use
process stderr plus exit code `2`.
