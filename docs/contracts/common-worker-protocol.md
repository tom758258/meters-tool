# Common Worker Protocol

Worker schema version: `3`

Manifest schema version: `2`

Contract revision: `3.0`

Compatibility policy: `v3-only`

This protocol is lifecycle-only: it defines shared communication, control,
and job handling, not domain commands, device operations, session management,
queue scheduling, or output safety. Tool-specific contracts retain those
responsibilities. No tool is required to add jobs, cancellation, streaming,
parallelism, or reusable sessions.

The four Common documents are manually synchronized:

| Document | Responsibility |
| --- | --- |
| This document | Manifest, versions, features, ready, HTTP, status, job snapshots, errors, stop, and cancel |
| [CLI JSON / JSONL contract](common-cli-jsonl-contract.md) | Runtime envelopes, events, job terminals, summary, EOF, and exit |
| [Streaming extension](common-streaming-extension.md) | Optional source adoption, state, ordering, and termination |
| [Orchestrator workflows](common-orchestrator-workflows.md) | Capability validation, shared job tracking, completion, local connections, and adapter boundaries |

## Versions and compatibility

| Layer | Version | Responsibility |
| --- | --- | --- |
| Common document revision | `3.0` | Identifies specification content; not runtime negotiation |
| Manifest schema | `2` | Manifest shape and backward-compatible extensions |
| Worker protocol | `3` | Worker HTTP, JSONL, and common runtime semantics |
| Feature contract | Each feature's `contract_version` | Independently versioned optional capability |
| Tool package | Tool-owned | Release identity; never evidence of Worker capabilities |

A v3 Worker declares:

```json
{
  "compatibility_policy": "v3-only",
  "schema_versions": [3]
}
```

Worker `schema_version` must be the integer JSON token `3`. Missing values,
`"3"`, `true`, `3.0`, and `3e0` are invalid, even if a language decoder
treats some of them as numerically equivalent. Manifest `schema_version`
remains the integer token `2`. Feature compatibility uses explicit supported
version sets, never a rule that all higher versions are compatible.

A v3 orchestrator executes only Workers satisfying this contract. Unknown
optional output fields may be ignored, and unknown non-required features are
not adopted. Missing required features, unsupported required versions,
malformed known declarations, or contradictory runtime declarations must
reject the affected integration.

The additional Manifest schema-2 fields below are required only when the
Manifest declares Worker protocol 3. Their absence does not make an otherwise
valid v2 Manifest malformed, although that Worker is incompatible with a
v3-only orchestrator.

Ordinary CLI results, capability output, artifacts, CSV, and WebUI APIs do not
automatically change version with the Worker protocol. Directly forwarded
Worker JSON retains its Worker version. Independently wrapped results retain
their own contract; embedded Worker data needs explicit inner/outer version
handling rather than a shared constant being changed indiscriminately.

## Manifest and feature discovery

| Field | Type and requirement |
| --- | --- |
| `event` | String `tool_manifest` |
| `schema_version` | Integer token `2` |
| `tool_id` | Non-empty stable tool identity string |
| `tool_version` | Non-empty release identity string |
| `worker_protocol` | Object declaring `compatibility_policy: "v3-only"` and `schema_versions: [3]` |
| `execution.model` | `run_bound` or `multi_job` |
| `execution.context_binding` | `startup` or `per_command` |
| `features` | Feature object; `{}` is valid |
| `commands` | Optional object describing command kinds needed for integration |

`multi_job` means one Worker can handle multiple jobs over its lifetime. It
does not imply parallel execution, multiple active slots, or a particular
queue model. Each `commands` entry is an object with `kind: "control"` or
`kind: "async_job"`. Command kinds may instead come from an explicit tool
contract used by a thin adapter. If both sources provide them, they must
agree. Never infer kind from a command's name or response speed.

| Common feature | Required declaration | Constraints |
| --- | --- | --- |
| `common.async_jobs` | `contract_version: 1` | Adopts common job snapshots and terminals |
| `common.job_cancel` | `contract_version: 1`, non-empty `commands` array of command strings | Requires async jobs; lists only commands actually supporting cancellation |
| `common.streaming` | `contract_version: 1`, non-empty `lifecycles` array | Values are `run_bound` and/or `deferred_start` |

Tool-specific features use their own namespaces; their semantics remain in
tool contracts. The Manifest describes program capabilities, not a promise
that every model, mode, or runtime can use every feature.

The following fictional tool illustrates v3 declarations without claiming
support in any existing tool:

```json
{
  "event": "tool_manifest",
  "schema_version": 2,
  "tool_id": "example",
  "tool_version": "0.1.0",
  "worker_protocol": {
    "compatibility_policy": "v3-only",
    "schema_versions": [3]
  },
  "execution": {
    "model": "multi_job",
    "context_binding": "startup"
  },
  "features": {
    "common.async_jobs": {"contract_version": 1}
  },
  "commands": {
    "measure": {"kind": "async_job"}
  }
}
```

## Lifecycle

An orchestrator starts a Worker subprocess and continuously observes stdout
and stderr. Machine stdout contains JSON object lines only; human-readable
diagnostics belong on stderr. The
[JSONL contract](common-cli-jsonl-contract.md) defines event envelopes.

A normal, controllable startup emits `ready` with:

| Field | Required value |
| --- | --- |
| `event` | `ready` |
| `schema_version` | Integer token `3` |
| `timestamp_utc` | ISO 8601 UTC string |
| `run_id` | Non-empty runtime identity string |
| `status_url`, `command_url`, `stop_url` | Non-empty URL strings |
| `features` | Features actually adopted by this runtime |

An adopted `common.job_cancel` requires `cancel_url`. An adopted
`common.streaming` requires `stream.lifecycle`; ready does not contain
`stream.state`.

Runtime features must form a valid subset of the Manifest, with the same
contract versions, and remain fixed for that runtime. Cancellation commands
must be supported by the Manifest. Streaming retains only the selected
lifecycle in the runtime feature's `lifecycles` array, matching
`stream.lifecycle`.

Ready means the control interface accepts requests. It does not establish
device initialization, command acceptance or completion, active streaming,
output safety, or cleanup completion. Early startup failure may omit ready;
never manufacture readiness to satisfy an event sequence.

`run_id` correlates runtime output, HTTP responses, and associated artifacts.
A command that creates no runtime need not invent a runtime identity.

## Worker status and job snapshots

### Common status

Every successful HTTP status response and JSONL status event uses the
Common Status schema with these required fields:

| Field | Type and meaning |
| --- | --- |
| `schema_version` | Integer token `3` |
| `timestamp_utc` | ISO 8601 UTC time of this observation |
| `run_id` | Non-empty runtime identity string |
| `worker_state` | `starting`, `running`, `stopping`, or `failed` |
| `fatal_error` | [Common Error](#common-error) object or `null` |

JSONL adds `event: "status"`. Successful `GET /status` returns HTTP 200 and
also supplies the control URLs and runtime `features` declared by ready,
including `cancel_url` when cancellation is adopted. This supports the
existing HTTP readiness fallback. Readiness requires both
`worker_state: "running"` and `fatal_error: null`, in addition to a valid
schema, matching WorkerSession identity, and validated runtime declarations
and URLs. HTTP 200 alone is insufficient. An opted-in stream includes its
lifecycle and current state in both status channels.

| Worker state | Meaning |
| --- | --- |
| `starting` | HTTP can respond, but control-interface readiness is not complete |
| `running` | The control interface operates normally; not a claim of idleness or device readiness |
| `stopping` | The existing stop procedure has begun |
| `failed` | Fatal Worker failure; `fatal_error` must be non-null |

These are state terms, not a mandatory sequence. Natural completion may
proceed directly through the existing summary, cleanup, EOF, and exit path.
All Workers may finish without a `stopping` event; do not invoke an extra
stop, fabricate that state, or prolong HTTP lifetime to produce it.

Status is non-mutating: no device I/O, work startup, queue mutation, or error
clearing may be performed to answer a status request. Queue, trigger,
protection, receive-buffer, and domain progress fields remain tool-specific.

### Status handler failures

If the `GET /status` handler can provide a structured failure response, it
uses HTTP 500 with `schema_version: 3`, the runtime's non-empty `run_id`,
`status: "error"`, and `error` containing a [Common Error](#common-error).
Handler failures use category `worker`; `code` is a stable non-empty string,
`message` is a non-empty diagnostic string, and `details` is an object.

This failure envelope is not a Common Status snapshot and cannot establish
readiness or update job/stream state. It need not fabricate `worker_state`,
control URLs, or feature snapshots. For example:

```json
{
  "schema_version": 3,
  "run_id": "r1",
  "status": "error",
  "error": {
    "category": "worker",
    "code": "status_failed",
    "message": "Status request failed.",
    "details": {}
  }
}
```

Connection loss, process exit, or inability to emit a structured response
remains a communication/lifecycle failure. No response is guaranteed in those
cases, and no device I/O or new cleanup operation is required to produce one.

### Optional job snapshots

Every status in a runtime adopting `common.async_jobs` contains:

- `active_job`: one non-terminal job snapshot, or `null`.
- `last_job`: the most recent complete terminal snapshot, or `null`.

`active_job` describes one active or queued job, not the entire queue.
It introduces no scheduling rule. `last_job` is not a job history.

| Field | Non-terminal snapshot | Terminal snapshot |
| --- | --- | --- |
| `worker_job_id` | Non-empty string | Non-empty string |
| `job_id` | String or `null` | String or `null` |
| `command` | Non-empty string | Non-empty string |
| `state` | `queued` or `running` | `succeeded`, `failed`, or `cancelled` |
| `timestamp_utc` | ISO 8601 UTC time this state was established | Fixed ISO 8601 UTC terminal creation time |
| `ok` | Not required | Boolean |
| `result` | Not required | Any JSON value or `null`; field required |
| `error` | Not required | Common Error or `null`; field required |

Snapshots inherit `schema_version` and `run_id` from the enclosing status;
nested repetition is not required. Terminal snapshots must preserve the
original terminal result and any partial results, artifacts, or domain error
information required by the tool contract. State, `ok`, and `error` follow
the [terminal rules](common-cli-jsonl-contract.md#async-job-terminal).

The outer observation timestamp may change on every poll. The inner terminal
timestamp is fixed. JSONL terminal events and HTTP terminal snapshots must
agree in job identity, terminal state, and result/error semantics. Field
order, complete JSON equality, outer observation times, and extra diagnostic
fields need not match. Later diagnostics such as current artifact
availability must not rewrite the original completion result.

No complete job history, replay, or persistence requirement is introduced.

## HTTP endpoints

The common endpoints are `GET /status`, `POST /command`, and `POST /stop`.
Only a runtime adopting cancellation provides its declared cancel endpoint.
This protocol does not define `POST /start`. Domain commands and their
side effects remain tool-specific.

Before an orchestrator connects to a managed local Worker, it must apply the
[loopback connection rules](common-orchestrator-workflows.md#loopback-connection-rules)
to every URL it intends to use, including the initial status fallback URL.
Status, command, stop, and optional cancel URLs must share the same validated
HTTP origin (scheme, host, and effective port) bound to that WorkerSession.
HTTP status `run_id` must match that session's established runtime identity;
the workflow contract defines initial fallback binding and mismatch handling.

### Command request

`POST /command` accepts only these top-level fields:

| Field | Requirement |
| --- | --- |
| `schema_version` | Required integer token `3` |
| `command` | Required non-empty string |
| `arguments` | Optional object; omission means `{}` |
| `job_id` | Optional string for correlation, not idempotency |
| `context` | Object governed by the declared context binding |

For `startup` binding, request-level context is forbidden. For `per_command`
binding, context is required.

Malformed JSON, a non-object body, unknown top-level fields, invalid types,
invalid versions, and invalid context must be rejected before enqueueing work
or performing device I/O. Each new orchestrator submission uses a unique,
non-empty `job_id`. Reusing a job ID does not promise deduplication or safe
retry.

### Mode and model context

| Mode | Required or allowed | Forbidden |
| --- | --- | --- |
| `live` | Optional `expected_model_id` | `planning_model_id` |
| `simulate` | Explicit deterministic simulation identity; `planning_model_id` unless a tool-defined alternative applies | `expected_model_id` |
| `dry_run` | Explicit planning identity; `planning_model_id` unless a tool-defined alternative applies | `expected_model_id` |

`mode` is `live`, `simulate`, or `dry_run`. `expected_model_id` is a
live identity guard. `planning_model_id` names a physical model used for
planning or simulation; values are canonical, project-owned identifiers.
Existing tool-defined alternatives, including nonphysical planning profiles,
remain valid. Do not fabricate a physical model to satisfy the common
envelope. Reject context fields defined by neither Common nor the tool
contract, and reject invalid mode/identity combinations.

### Command response

Every command HTTP response is an object containing:

| Field | Requirement |
| --- | --- |
| `schema_version` | Integer token `3` |
| `run_id` | Non-empty runtime identity string |
| `status` | `accepted`, `rejected`, or `error` |
| `command` | Safely identifiable command string, otherwise `null` |
| `job_id` | Safely identifiable client string, otherwise `null` |
| `kind` | `control`, `async_job`, or `null` if unidentifiable |
| `worker_job_id` | Non-empty string for an accepted async job; `null` when no job was created |
| `error` | `null` when accepted; otherwise a Common Error |

| HTTP code | Meaning |
| --- | --- |
| 202 | Accepted control or async job |
| 400 | Invalid format, version, arguments, or context; `status: "error"` |
| 409 | Busy or other admission rejection; `status: "rejected"` |
| 429 | Queue/rate rejection; `status: "rejected"` |
| 500 | Request handling error; `status: "error"` |

An accepted control command requires no async terminal and does not
automatically establish domain completion. An accepted async job adopts the
common job feature and receives a `worker_job_id` unique within `run_id`;
IDs must not be reused.

HTTP 500, timeout, disconnect, or a lost response does not prove that a command
was never executed. Never automatically resend a command with possible
device side effects on that basis.

For the fictional startup-bound Manifest above, a request and HTTP 202
response are:

```json
{
  "schema_version": 3,
  "command": "measure",
  "arguments": {},
  "job_id": "client-1"
}
```

```json
{
  "schema_version": 3,
  "run_id": "r1",
  "status": "accepted",
  "command": "measure",
  "job_id": "client-1",
  "kind": "async_job",
  "worker_job_id": "w1",
  "error": null
}
```

## Common Error

```json
{
  "category": "execution",
  "code": "measurement_failed",
  "message": "Measurement failed.",
  "details": {}
}
```

| Field | Requirement |
| --- | --- |
| `category` | `validation`, `admission`, `execution`, or `worker` |
| `code` | Non-empty stable machine-readable string |
| `message` | Non-empty diagnostic string |
| `details` | Object; `{}` when empty |

Validation means an invalid request; admission means a valid request was not
accepted; execution means domain work failed; worker means infrastructure or
communication handling failed. Category alone does not establish fatality.
Preserve existing domain errors in `details.domain_error` or existing domain
fields instead of reducing them to generic text.

## Stop acknowledgement

`POST /stop` must accept an empty body, `{}`, or an object containing only
optional `schema_version: 3` and `reason: string`. A supplied version must
be valid. Reject unknown fields and invalid types.

A successful response uses HTTP 200 or 202 with identical meaning:

```json
{
  "schema_version": 3,
  "run_id": "r1",
  "status": "accepted",
  "error": null
}
```

Producers may preserve their existing successful status code. Common clients
must accept both without tool-specific branches. Acceptance confirms only
that the stop request was accepted, not job completion, output completion,
device stop, or cleanup. Repeated stop must not restart work or trigger new
duplicate stop side effects.

Validation failures use HTTP 400 and handling failures HTTP 500, with the same
envelope, `status: "error"`, and a Common Error. Existing stop behavior and
cleanup order remain tool-owned.

## Optional job cancellation

Only runtimes adopting `common.job_cancel` expose `cancel_url`. The request
contains required `schema_version` and non-empty `worker_job_id`, plus
optional string `reason`; unknown fields are rejected:

```json
{
  "schema_version": 3,
  "worker_job_id": "w1",
  "reason": "operator_request"
}
```

Successful HTTP 202 response:

```json
{
  "schema_version": 3,
  "run_id": "r1",
  "status": "accepted",
  "worker_job_id": "w1",
  "error": null
}
```

Malformed requests use HTTP 400. Missing, already terminal, or non-cancellable
jobs use HTTP 409. Handling failures use HTTP 500. Error responses retain the
cancel envelope and Common Error; echo a safely identifiable job ID, otherwise
`null`. Admission rejection uses `status: "rejected"`; validation and
handling errors use `status: "error"`.

Cancel acceptance does not guarantee a `cancelled` terminal. Completion and
cancellation races follow the existing execution outcome. No forced interrupt
or new safety operation is introduced. A job terminated by Worker stop keeps
its tool-defined classification; it is not automatically cancelled.

## Optional streaming extension

Streaming requires both explicit opt-in through the existing tool setting and
a runtime `common.streaming` declaration with matching `stream` fields.
Manifest support alone, JSONL mode, or observing data is insufficient. See the
[streaming contract](common-streaming-extension.md) for source readiness,
ordering, and termination. The extension adds no endpoint or generic start
command and does not change stop or cleanup responsibilities.

## Exit codes

Preserve existing meanings: success `0`, usage/validation error `2`, and
runtime/Worker error `3`. Existing interruption codes such as `130` are not
reclassified by v3. Argument parser errors may use stderr and exit `2`;
failures after structured output handling begins use JSON events.

The [summary and cleanup rules](common-cli-jsonl-contract.md#summary-eof-and-exit)
explain why a summary's intended exit code cannot replace actual process exit,
and why later cleanup evidence must be preserved.
