# Common CLI JSON / JSONL Contract

Worker schema version: `3`

Manifest schema version: `2`

Contract revision: `3.0`

Compatibility policy: `v3-only`

The Common v3.0 specification is finalized, with its major contract design
frozen. Specification, implementation, conformance, and release are distinct:

| Status | Common v3.0 |
| --- | --- |
| Specification | Finalized |
| Implementation | Pending across the five Tool projects and Orchestrator (six projects) |
| Conformance | Pending test verification |
| Release | No formal v3 cutover |

The five Tools' existing v2 implementations continue under Common v2, contract
revision `2.2`. These finalized requirements do not upgrade those runtimes or
establish v3 implementation, conformance, or release. Implementation and
no-hardware acceptance require separate authorization.

This document owns Worker event envelopes, terminal events, summary, EOF, and
process exit. The [Worker protocol](common-worker-protocol.md) owns discovery,
HTTP, Common Error, and job snapshots. The
[streaming extension](common-streaming-extension.md) owns optional source
ordering; [orchestrator workflows](common-orchestrator-workflows.md) own
consumer correlation and completion decisions. The four files are manually
synchronized.

## Machine output

Every non-empty machine stdout line must be one JSON object. Workers should
avoid empty lines; consumers ignore them. Human-readable diagnostics belong
on stderr. Single-response CLI JSON emits one object for the command; its
independent result contract is not automatically upgraded to Worker v3.

Worker runtime events use the integer token `schema_version: 3`,
`timestamp_utc` as an ISO 8601 UTC string, and a non-empty `run_id` once the
runtime identity exists. Early failure before runtime creation may omit
`run_id`. Missing, string, boolean, fractional, and exponent-form Worker
versions are invalid: `"3"`, `true`, `3.0`, and `3e0` must be rejected.

Direct CLI passthrough of Worker JSON preserves v3. Ordinary CLI envelopes,
dry-run previews, capabilities, artifacts, CSV, and WebUI APIs keep their
independent versions. Manifest schema remains 2; feature versions are
independent of both Manifest and Worker versions.

Unknown optional output fields may be ignored. A malformed known common event
must not be accepted as a valid state update. Domain events and their payloads
remain tool-specific; consumers must not guess their meaning from names alone.

## Common events

| Event | Meaning and required payload beyond the runtime envelope |
| --- | --- |
| `ready` | Control interface ready; control URLs and runtime `features`, plus adopted feature fields |
| `status` | Observation containing `worker_state` and `fatal_error`, plus adopted feature fields |
| `error` | Common Error with `scope` and `fatal` |
| `summary` | Worker result with `ok`, `fatal_error`, and intended `exit_code` |
| `message` | Structured information; diagnostic text does not establish completion |
| `job_finished` | Optional async-job terminal with identity, state, and result |

The runtime envelope comprises `event`, `schema_version`,
`timestamp_utc`, and `run_id`, subject only to the early-failure exception.
Runtime events share the same `run_id`. A standalone dry-run preview that
creates no runtime does not invent one.

### Ready and status

Ready follows the [required fields](common-worker-protocol.md#lifecycle).
It indicates control readiness, not device readiness, accepted or completed
work, active streaming, or successful safety cleanup. An early failure may
emit neither ready nor a normal event sequence.

This fictional example adopts async jobs:

```json
{
  "event": "ready",
  "schema_version": 3,
  "timestamp_utc": "2026-10-23T10:00:00Z",
  "run_id": "r1",
  "status_url": "http://127.0.0.1:8765/status",
  "command_url": "http://127.0.0.1:8765/command",
  "stop_url": "http://127.0.0.1:8765/stop",
  "features": {
    "common.async_jobs": {"contract_version": 1}
  }
}
```

JSONL status uses the
[common status and snapshot fields](common-worker-protocol.md#worker-status-and-job-snapshots).
Every status in an async runtime includes `active_job` and `last_job`;
every status in a streaming runtime includes the current `stream` snapshot.
HTTP status additionally supplies control URLs and runtime features for
readiness fallback.

Worker states are vocabulary, not a required event sequence. Natural
completion without `stopping` is valid for every Worker. Do not issue extra
stop operations or keep HTTP alive merely to produce a state event.

### Error events

An `error` event contains:

| Field | Requirement |
| --- | --- |
| `scope` | `request`, `job`, or `worker` |
| `fatal` | Boolean; `true` only for fatal Worker failure with `scope: "worker"` |
| `error` | [Common Error](common-worker-protocol.md#common-error) |
| `worker_job_id`, `job_id`, `command` | Required for job scope, following job identity types |

Request- and job-scope errors must use `fatal: false`. A fatal Worker failure
must use `scope: "worker"` and `fatal: true`; Common Error category does not
itself determine fatality. A job failure already fully represented by its
terminal needs no duplicate error event.
Preserve domain error details rather than replacing them with generic text.

## Async job terminal

A runtime adopting `common.async_jobs` uses `event: "job_finished"` for
every normal, controllable async termination. `job_failed` and
`job_cancelled` are not v3 common terminal events.

| Field | Requirement |
| --- | --- |
| `event` | `job_finished` |
| `schema_version` | Integer token `3` |
| `timestamp_utc` | Fixed ISO 8601 UTC terminal creation time |
| `run_id` | Non-empty runtime identity string |
| `worker_job_id` | Non-empty job identity string, unique within the run |
| `job_id` | Client correlation string or `null` |
| `command` | Non-empty command string |
| `state` | `succeeded`, `failed`, or `cancelled` |
| `ok` | Boolean |
| `result` | Any JSON value or `null`; field required |
| `error` | Common Error or `null`; field required |

| State | `ok` | `error` |
| --- | --- | --- |
| `succeeded` | `true` | `null` |
| `failed` | `false` | Required Common Error |
| `cancelled` | `false` | May be `null`; existing cancellation diagnostics must be retained |

Each accepted async job produces exactly one JSONL terminal on a normal,
controllable path. Worker job IDs must not be reused within a run. Repeated
HTTP observations of the same terminal snapshot are not additional
terminations. The terminal may reach the orchestrator before its HTTP
accepted response. A crash or output failure may prevent terminal emission;
never fabricate success or cancellation to fill the gap.

Failed or cancelled jobs may still return partial results, artifacts, files,
transcripts, and warnings. Preserve existing domain fields and memory/files
modes; Common does not require moving all domain data into `result`.
Stop-induced termination keeps the tool's existing classification rather than
automatically becoming `cancelled`. Adopting async jobs does not require
cancellation, queues, or parallelism.

### Terminal and snapshot equivalence

A complete terminal snapshot can confirm completion without a JSONL terminal
observation. It carries the terminal fields above except `event`, and
inherits `schema_version` and `run_id` from status. See the
[snapshot contract](common-worker-protocol.md#optional-job-snapshots).

The following failed terminal preserves its partial output and domain error:

```json
{
  "event": "job_finished",
  "schema_version": 3,
  "timestamp_utc": "2026-10-23T10:01:00Z",
  "run_id": "r1",
  "worker_job_id": "w1",
  "job_id": "client-1",
  "command": "measure",
  "state": "failed",
  "ok": false,
  "result": {"sample_count": 2, "partial": true},
  "files": ["partial.csv"],
  "error": {
    "category": "execution",
    "code": "measurement_failed",
    "message": "Measurement stopped before completion.",
    "details": {
      "domain_error": {"code": "EXAMPLE_READ_ERROR"}
    }
  }
}
```

A later HTTP 200 status can report the same terminal while the Worker remains
available. Its observation time changes; the terminal time and result do not:

```json
{
  "schema_version": 3,
  "timestamp_utc": "2026-10-23T10:05:00Z",
  "run_id": "r1",
  "worker_state": "running",
  "fatal_error": null,
  "status_url": "http://127.0.0.1:8765/status",
  "command_url": "http://127.0.0.1:8765/command",
  "stop_url": "http://127.0.0.1:8765/stop",
  "features": {
    "common.async_jobs": {"contract_version": 1}
  },
  "active_job": null,
  "last_job": {
    "timestamp_utc": "2026-10-23T10:01:00Z",
    "worker_job_id": "w1",
    "job_id": "client-1",
    "command": "measure",
    "state": "failed",
    "ok": false,
    "result": {"sample_count": 2, "partial": true},
    "files": ["partial.csv"],
    "error": {
      "category": "execution",
      "code": "measurement_failed",
      "message": "Measurement stopped before completion.",
      "details": {
        "domain_error": {"code": "EXAMPLE_READ_ERROR"}
      }
    }
  }
}
```

These observations confirm the same failed job. They need not have identical
field order, whole JSON, outer timestamps, or additional diagnostics.
Identity, terminal state, and result/error semantics must agree. Later
artifact-availability diagnostics may supplement the record but must not
replace the original result. See the
[shared job tracker](common-orchestrator-workflows.md#shared-job-tracker)
for duplicate, stale, and contradictory observations.

## Optional streaming fields

These fields apply only when the runtime explicitly opts in to the
[streaming extension](common-streaming-extension.md), adopts
`common.streaming`, and supplies matching `stream` fields. Manifest
support, the `stream` object alone without its runtime feature declaration,
or ordinary data output is not sufficient for v3 adoption.

| Output | Required extension fields |
| --- | --- |
| Ready | `stream.lifecycle`; no `stream.state` |
| JSONL status and HTTP status | `stream.lifecycle` and `stream.state` |

`stream` is an object. Its lifecycle is `run_bound` or `deferred_start`,
fixed for the runtime and matching the single lifecycle selected in the
runtime feature declaration. State is `waiting`, `active`, or `ended`.
This does not replace `worker_state` or any tool-specific status fields.

The extension adds no `stream` object to data events or summary. Data events
keep their runtime `run_id`; event names, payloads, counts, and quality
fields remain tool-specific. No stream ID, sequence, or last-sequence field
is added.

These are complete common examples; tool contracts may require extra fields.
The streaming feature must also be supported in the tool's Manifest:

```json
{
  "event": "ready",
  "schema_version": 3,
  "timestamp_utc": "2026-10-23T10:00:00Z",
  "run_id": "stream-run",
  "status_url": "http://127.0.0.1:8765/status",
  "command_url": "http://127.0.0.1:8765/command",
  "stop_url": "http://127.0.0.1:8765/stop",
  "features": {
    "common.streaming": {
      "contract_version": 1,
      "lifecycles": ["run_bound"]
    }
  },
  "stream": {"lifecycle": "run_bound"}
}
```

A JSONL active status precedes the first source data event:

```json
{
  "event": "status",
  "schema_version": 3,
  "timestamp_utc": "2026-10-23T10:00:01Z",
  "run_id": "stream-run",
  "worker_state": "running",
  "fatal_error": null,
  "stream": {"lifecycle": "run_bound", "state": "active"}
}
```

A later HTTP status may report ended while the control interface remains
running. Neither fact asserts cleanup completion:

```json
{
  "schema_version": 3,
  "timestamp_utc": "2026-10-23T10:00:02Z",
  "run_id": "stream-run",
  "worker_state": "running",
  "fatal_error": null,
  "status_url": "http://127.0.0.1:8765/status",
  "command_url": "http://127.0.0.1:8765/command",
  "stop_url": "http://127.0.0.1:8765/stop",
  "features": {
    "common.streaming": {
      "contract_version": 1,
      "lifecycles": ["run_bound"]
    }
  },
  "stream": {"lifecycle": "run_bound", "state": "ended"}
}
```

## Summary, EOF, and exit

A normal, controllable Worker shutdown emits one summary with:

| Field | Requirement |
| --- | --- |
| `event` | `summary` |
| `schema_version` | Integer token `3` |
| `timestamp_utc` | ISO 8601 UTC string |
| `run_id` | Non-empty runtime identity string |
| `ok` | Boolean Worker/run result |
| `fatal_error` | Common Error or `null` |
| `exit_code` | Integer intended process exit code at summary time |

An ordinary job failure in a multi-job Worker need not fail its Worker
summary. A run-bound Worker's summary preserves the tool's existing run
result meaning.

Summary need not be the last stdout event and does not assert cleanup
completion. Consumers must continue reading to stdout EOF, collect later
error and cleanup evidence, and observe actual process exit. Summary's
`exit_code` is an intention at emission time, not a substitute for actual
exit. Neither stop acknowledgement, summary, nor EOF alone proves shutdown
completion. See the
[three completion conditions](common-orchestrator-workflows.md#completion-conditions).

Actual exit `0` must not override `summary.ok: false`, a known fatal Worker
failure, or known cleanup failure. Retain that failure evidence and do not
classify the affected Worker shutdown or workflow as successful.

Preserve process exit meanings: success `0`, usage/validation error `2`,
and runtime/Worker error `3`. Existing interruption values such as `130`
are not reclassified. Argument parser usage failures may use stderr and
exit `2`. An early failure or crash may omit summary; missing evidence must
not be interpreted as success or cause an unbounded wait.

### Cleanup failure evidence

This contract preserves and propagates failures already observed by the
existing cleanup implementation. A structured error, an existing cleanup
diagnostic, or a non-zero actual exit may report failure after summary.
An earlier `summary.ok: true` must not overwrite that later evidence.

An already confirmed job terminal remains intact. Worker shutdown and
workflow outcomes separately record closure or safety-cleanup failure. The
common protocol does not add device queries, transport I/O, output-off
operations, error draining, or a new cleanup order to obtain evidence.

If Core currently swallows an error and exposing it requires changing Core
execution or error handling, assess that change separately; it is not
implicitly authorized as envelope migration. Human diagnostic text is not a
new common parser contract; existing tool-specific cleanup evidence is
interpreted through its documented adapter.

For example, `summary.ok: true` followed by an existing cleanup failure or
actual exit `3` cannot yield fully successful Worker/workflow completion.
Conversely, a natural end with valid result, summary, EOF, and successful
actual exit is not invalid merely because no `stopping` event appeared.

## Conformance examples

The following mutations apply to otherwise complete valid messages; they are
not standalone envelopes:

| Mutation or observation | Required interpretation |
| --- | --- |
| Worker version `"3"`, `true`, `3.0`, or `3e0` | Invalid version token |
| Accepted async job has `worker_job_id: null` | Protocol error |
| Failed terminal has `error: null` | Invalid terminal |
| Succeeded terminal has `ok: false` | Invalid terminal |
| Terminal snapshot omits `result` or `error` | Insufficient to confirm completion |
| Same job first succeeds, then fails | Preserve the confirmed result and conflict evidence; the affected workflow cannot be verified successful |
| Only outer status observation time changes | Valid; not a conflict |
| Old queued/running snapshot follows a terminal | Do not regress the job |
| Accepted HTTP response is lost, but a complete terminal is observed | May confirm the job using correct identity |
| Crash with no terminal or complete snapshot | Result unconfirmed; no automatic side-effecting retry |
| Successful summary followed by known cleanup failure | Worker/workflow cannot be fully successful |
| Failed summary or known Worker fatal/cleanup failure followed by exit `0` | Retain failure; exit `0` cannot establish success |
| `fatal: true` with request or job scope | Invalid error event |
| Natural completion omits `stopping`, with all required result and shutdown evidence | Valid |

Schema checks validate structure. Raw JSON fixtures check representation
details such as exact version tokens. Behavioral conformance checks cover
event ordering, races, and completion decisions. None replaces the others.
These requirements are validation criteria, not claims that v3 has passed
them.

## Client diagnostics

Client commands contacting a local Worker should retain these diagnostics
when knowable:

- `client_command`, `method`, `url`, and `endpoint`.
- `timeout_ms` and `elapsed_ms`.
- `request_sent`, `reachable`, and `http_status`.
- `error_phase`.

Validation failures before sending use `request_sent: false`. A request
attempt uses `request_sent: true`. These observations do not prove whether
a side-effecting command executed when its response is missing.
