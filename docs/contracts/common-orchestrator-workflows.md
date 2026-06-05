# Common Orchestrator Workflows

This document defines the abstract cross-instrument lifecycle for agents that
drive worker subprocesses. Instrument-specific commands, resources, trigger
semantics, and artifacts belong in instrument-specific workflow documents.

## Lifecycle

1. Build a plan or dry-run request when the worker supports one.
2. Start the worker subprocess in machine-output mode.
3. Read stdout as JSONL and wait for a `ready` event, or poll
   `GET /status` until a valid status object is reachable.
4. Correlate stdout events, status responses, and artifacts with `run_id` when
   the worker creates a runtime session.
5. Use the worker-specific trigger mechanism only after the control plane is
   ready.
6. Use `GET /status` for non-mutating health and progress checks.
7. Use `POST /stop` or the worker-specific stop client for cooperative
   cleanup.
8. Read structured output and artifacts for pass/fail decisions. Human text is
   diagnostic output only.

## Failure Handling

Treat a missing `ready` event, unreachable status endpoint, malformed JSON,
non-zero process exit code, missing final summary, or final `ok: false` summary
as failed or incomplete until the instrument-specific contract says otherwise.

`GET /status` must be non-mutating. Orchestrators can poll it for readiness,
but should avoid adding extra request loops to instrument I/O paths.

## Live Resource Safety

Live runs should use an explicit resource selected by the operator or by a
previous explicit discovery step. Cross-instrument orchestrators should not
scan, guess, or rotate through resource strings inside an active workflow
unless the worker-specific contract explicitly allows it.

## Cleanup

Prefer cooperative stop before terminating a worker process. If a process has
already exited, client-side cleanup may report that the endpoint is no longer
listening; instrument-specific contracts define whether that is a successful
cleanup result.
