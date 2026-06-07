# Common Worker Protocol

Schema version: `1`

This provisional protocol defines the minimum lifecycle shape shared by
instrument workers that are launched and observed by an orchestrator. It lives
in this repository until a shared orchestrator repository or common contract
document set exists.

This document is lifecycle-only. It does not define instrument configuration,
domain commands, transport behavior, device command languages, or
worker-specific runtime semantics. Each instrument family must document those
details in its own worker contract.

## Lifecycle

An orchestrator starts a worker as a subprocess and observes stdout. In JSON or
JSONL mode, stdout must contain only JSON object lines. Empty stdout lines are
ignored by consumers, but workers should avoid emitting them in machine mode.

Human-readable text is diagnostic output, not the agent contract. It belongs in
text mode or stderr, and orchestrators must not parse it for pass/fail
decisions.

A worker emits a `ready` JSONL event when its local control plane is ready to
accept lifecycle requests. `ready` is not a measurement-complete signal and
does not imply instrument readiness beyond the worker-specific contract.

`run_id` correlates stdout JSONL, status responses, and artifacts for one
runtime session. Dry-run or plan-only commands may omit `run_id` when they do
not create a runtime session.

Consumers must ignore unknown fields in JSON objects. Workers may add optional
fields under schema version `1`; removing required fields or changing required
field types requires a major schema version bump.

## HTTP Endpoints

Common lifecycle endpoints are:

- `GET /status`: non-mutating health and progress check. It must not trigger
  unplanned work, mutate queues, or perform device I/O.
- `POST /command`: worker command envelope. The common protocol defines only
  the envelope shape; each worker contract defines supported command names,
  arguments, acceptance, rejection, and side effects.
- `POST /stop`: graceful stop request. Stop should request orderly worker
  shutdown through the worker's documented cleanup path.

The common `POST /command` request envelope is a JSON object with these allowed
top-level fields:

- `command`: required string command name.
- `arguments`: optional JSON object; omitted means `{}`.
- `job_id`: optional client-provided string that workers echo in command
  responses.

Workers should reject malformed JSON, a non-object body, unknown top-level
fields, a missing or non-string `command`, a non-object `arguments`, and a
non-string `job_id` with a structured validation error. Validation failures
must not perform device I/O or enqueue domain work.

Every `POST /command` HTTP response is a JSON object with this common
envelope:

- `status`: `accepted`, `rejected`, or `error`.
- `command`: the safely identifiable client-provided command string, or
  `null`.
- `job_id`: the safely identifiable client-provided string, or `null`.

Accepted responses use `status: "accepted"`. Queue, rate, or other
worker-specific admission failures use `status: "rejected"` and a
worker-specific `reason`. Validation and runtime errors use `status: "error"`
with `error` and `message`. The common protocol does not define
worker-specific rejection reasons.

This common protocol does not define `POST /start`. Instrument-specific
commands belong in the worker-specific contract for that instrument family.

## Exit Codes

Workers should preserve these process exit code meanings:

- `0`: success, accepted request, or dry-run success.
- `2`: usage error, validation error, or bad input.
- `3`: runtime error, connection error, HTTP request failure, or fatal worker
  failure.

Workers may emit structured JSON errors before exiting when command handling
has reached JSON or JSONL mode. Argument parser usage errors may still use
process stderr plus exit code `2`.
