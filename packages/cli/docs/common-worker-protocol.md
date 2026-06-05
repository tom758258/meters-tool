# Common Worker Protocol

Schema version: `1`

This provisional protocol defines the minimum lifecycle shape shared by
instrument workers that are launched and observed by an orchestrator. It is
kept in the Meters repository until a shared orchestrator or common-docs
location exists.

This document is lifecycle-only. It does not define instrument setup,
measurement commands, SCPI, VISA behavior, Power commands, Scope commands, KSON
commands, or worker-specific acquisition semantics. Each worker must document
those details in its own worker contract.

## Lifecycle

An orchestrator starts a worker as a subprocess and observes stdout. In JSON or
JSONL mode, stdout must contain only JSON object lines; human-readable messages
belong in text mode or stderr. Empty stdout lines are ignored by consumers, but
workers should avoid emitting them in machine mode.

A worker emits a `ready` JSONL event when its local control plane is ready to
accept lifecycle requests. `ready` is not a measurement-complete signal and
does not imply instrument readiness beyond the worker-specific contract.

`run_id` correlates stdout JSONL, status responses, and artifacts for one
runtime session. Dry-run or plan-only commands may omit `run_id` when they do
not create a runtime session.

## HTTP Endpoints

Common lifecycle endpoints are:

- `GET /status`: non-mutating health and progress check. It must not trigger
  acquisition, mutate queues, or perform instrument I/O.
- `POST /trigger`: generic worker trigger hook. Each worker contract defines
  what trigger means and when it is accepted, ignored, or rejected.
- `POST /stop`: graceful stop request. Stop should request orderly worker
  shutdown through the worker's documented cleanup path.

This common protocol does not define `POST /start` or a generic
`POST /command`. Instrument-specific commands belong in the worker-specific
contract for that instrument family.

## Exit Codes

Workers should preserve these process exit code meanings:

- `0`: success, accepted request, or dry-run success.
- `2`: usage error, validation error, or bad input.
- `3`: runtime error, connection error, HTTP request failure, or fatal
  acquisition failure.

Workers may emit structured JSON errors before exiting when command handling
has reached JSON or JSONL mode. Argument parser usage errors may still use
process stderr plus exit code `2`.
