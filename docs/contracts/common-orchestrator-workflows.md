# Common Orchestrator Workflows

Schema version: `2`

Contract revision: `2.1`

Compatibility policy: `v2-only`

The contract revision identifies this Common document-set revision. Runtime
wire compatibility is determined by `schema_version`, not by the contract
revision.

This document defines the abstract cross-tool lifecycle for agents that drive
Worker subprocesses. Tool-specific commands, execution context and identity,
resources, trigger semantics, and artifacts belong in Worker-specific workflow
documents.

## Lifecycle

1. Build a plan or dry-run request when the Worker supports one.
2. Start the Worker subprocess in machine-output mode.
3. Read stdout as JSONL and wait for a `ready` event with the Common required
   fields, or poll `GET /status` until a valid status object is reachable.
4. Correlate stdout events, status responses, and artifacts with `run_id` when
   the Worker creates a runtime session.
5. Build and supply schema-2 `context` only as required or allowed by the
   Worker-specific contract. If execution context is startup-bound and the
   Worker contract forbids request-level context, omit it from
   `POST /command`.
6. Use Worker-specific `POST /command` requests only after the control plane is
   ready. Parse the Common command response envelope and correlate echoed
   `command` and `job_id` identities.
7. Use `GET /status` for non-mutating health and progress checks.
8. Use `POST /stop` or the Worker-specific stop client for cooperative
   cleanup.
9. Read structured output and artifacts for pass/fail decisions. Human text is
   diagnostic output only.

When a Worker-specific contract defines an alternative deterministic planning
or simulation identity, orchestrators must use that identity and must not
synthesize a physical `planning_model_id`.

## Failure Handling

Treat failure to establish control-plane readiness through the documented
`ready` event or `GET /status` fallback, malformed JSON, a non-zero process exit
code, a missing final summary, or a final `ok: false` summary as failed or
incomplete until the Worker-specific contract says otherwise.

`GET /status` must be non-mutating. Orchestrators can poll it for readiness,
but should avoid adding extra request loops to device I/O paths.

## Live Resource Safety

Live runs should use an explicit resource selected by the operator or by a
previous explicit discovery step. Cross-tool orchestrators should not scan,
guess, or rotate through resource strings inside an active workflow unless the
Worker-specific contract explicitly allows it.

## Cleanup

Prefer cooperative stop before terminating a Worker process. If a process has
already exited, client-side cleanup may report that the endpoint is no longer
listening; Worker-specific contracts define whether that is a successful
cleanup result.
