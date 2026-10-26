# Common Orchestrator Workflows

Worker schema version: `3`

Manifest schema version: `2`

Contract revision: `3.0`

Compatibility policy: `v3-only`

This document defines shared consumer behavior for Worker subprocesses.
The [Worker protocol](common-worker-protocol.md) owns discovery and HTTP;
the [JSONL contract](common-cli-jsonl-contract.md) owns event envelopes,
terminals, summary, and exit; the
[streaming extension](common-streaming-extension.md) owns optional source
ordering. These four documents are manually synchronized. Domain commands,
resource selection, results, session ownership, queue policy, and safety
operations remain in tool contracts and thin adapters.

## Lifecycle

1. Read the Manifest from the actual executable that will be launched.
2. Validate tool identity, Manifest schema, Worker protocol, execution model,
   context binding, and required features. Reject incompatibilities knowable
   from the Manifest before startup.
3. Let the thin adapter construct existing startup arguments and context.
   Use a supported plan or dry-run path where the workflow requires it.
4. Launch the Worker and continuously drain stdout and stderr. Observe ready
   or use the existing HTTP status fallback. Before any HTTP request,
   validate the selected URL under the local connection rules below.
5. Validate the runtime `run_id`, adopted features, and advertised control
   URLs. A readiness fallback must provide valid common status, URLs, runtime
   features, and adopted feature fields, with both `worker_state: "running"`
   and `fatal_error: null`. Bind and validate the HTTP origin and session
   `run_id` as described below. HTTP 200 alone, or a starting, stopping, or
   failed Worker, cannot establish readiness.
6. Only after these checks, submit commands requiring those capabilities.
   Use command kinds from the Manifest or an explicit tool contract, with
   agreement when both exist.
7. Let the shared layer handle transport, common state, jobs, timeouts, and
   process results. Delegate domain results and existing safety operations
   to the adapter.
8. Complete the workflow's existing data and cleanup responsibilities,
   observing the separate completion conditions below.

Runtime features must be a valid subset of the Manifest with matching contract
versions, fixed for the runtime. Required features must be adopted before
dependent commands are sent. Unknown non-required features are not adopted;
known malformed declarations or runtime contradictions reject the affected
integration. Feature compatibility uses explicit supported versions, not
greater-than-or-equal comparisons. A valid v2 Manifest remains a valid v2
document even when it cannot satisfy a v3-only integration.

A run-bound Worker may already perform its existing device operations during
startup. Failed runtime negotiation does not prove that hardware was untouched
and does not introduce a new wait-for-orchestrator-approval lifecycle.

For startup-bound execution, omit request-level `context`. For per-command
binding, supply it. Preserve tool-defined deterministic planning or simulation
identities; do not synthesize a physical `planning_model_id`.

## Loopback connection rules

These rules apply only to local Workers managed by the orchestrator. Validate
each URL before making any HTTP request, including:

- URLs supplied by ready.
- The initial status fallback URL, before its first request.
- URLs returned by HTTP status that the client intends to adopt.
- Status, command, stop, and optional cancel endpoints.

The local connection profile requires:

- Scheme `http`.
- A valid numeric IPv4 loopback address; accept `[::1]` when the client
  supports IPv6. Tools need not add an IPv6 listener.
- If `localhost` compatibility is retained, pin it to a local loopback
  connection instead of arbitrary DNS resolution. Numeric loopback URLs are
  the recommended producer output.
- Rejection of non-loopback addresses, wildcard bind addresses, arbitrary
  domain names, and control URLs containing userinfo.
- No following HTTP redirects.
- No proxies, including environment-configured proxies.
- Use of the validated target for the actual connection. Revalidate any new
  URL before adopting it; do not switch to an unvalidated destination.

Bind one validated HTTP origin to the current WorkerSession from its
startup endpoint or validated ready declaration. Status, command, stop, and
optional cancel URLs must all use that same origin: the parsed scheme,
canonical host, and effective port. A different loopback host or port is
not interchangeable merely because it is also local. Pinning `localhost`
does not authorize changing the declared origin. Revalidate replacement URLs
and reject an origin change before connection, including during cleanup.

Every HTTP status response's `run_id` must match the runtime identity bound
to the current WorkerSession before its data or advertised URLs are used.
When a valid status fallback establishes the initial identity before ready,
bind it once to that launched WorkerSession; subsequent ready, HTTP, and
JSONL observations must agree. A mismatch is a protocol/session failure,
not permission to rebind the session or adopt another Worker's endpoints.

These illustrative addresses are not live resource configuration:

| URL | Local integration result |
| --- | --- |
| `http://127.0.0.1:8765/status` | Accept |
| `http://[::1]:8765/status` | Accept when IPv6 is supported |
| `http://localhost:8765/status` | Accept only with the pinned loopback compatibility behavior |
| `http://203.0.113.10:8765/status` | Reject non-loopback address |
| `http://0.0.0.0:8765/status` | Reject wildcard bind address |
| `https://example.com/status` | Reject |
| `http://user@127.0.0.1:8765/status` | Reject userinfo |

Rejected URLs enter the existing failure and safe cleanup path. Do not bypass
validation to send stop or cancel. These requirements do not remove an
independent tool CLI's host option and do not introduce remote control.

## Completion conditions

| Level | Evidence and decision | What does not establish it |
| --- | --- | --- |
| Job completion | Valid `job_finished`, or a complete contract-valid terminal snapshot with matching identity | HTTP accepted or cancel acknowledgement; a multi-job Worker need not shut down |
| Worker shutdown completion | Evaluate summary, subsequent errors and cleanup evidence, stdout EOF, and actual process exit to classify success, failure, or unconfirmed shutdown | Stop acknowledgement, summary, or EOF alone |
| Workflow completion | Required steps and the workflow's existing data, Worker shutdown, and safety-cleanup responsibilities are complete | Any individual successful job |

A terminal job may have succeeded, failed, or been cancelled. Completion
does not mean success. A successful multi-job operation may be followed by
other work in the same process. Later Worker failure does not erase an already
confirmed job result, but may fail or leave unconfirmed the Worker shutdown
or workflow result.

A run-bound tool without async jobs uses its existing run result and shutdown
evidence; it need not manufacture a job. Missing required terminal, summary,
or exit evidence must not be guessed as success or awaited indefinitely.
A complete terminal snapshot can replace observation of a JSONL job terminal,
but it cannot replace Worker shutdown evidence when shutdown is required.

Use tool/workflow-appropriate deadlines for readiness, requests, jobs, source
readiness, and shutdown. This contract introduces no universal timeout value.
Record an unconfirmed outcome internally when evidence is insufficient;
`unconfirmed` is not an invented Worker terminal state.

Natural completion may proceed directly through summary, cleanup, EOF, and
exit. No Worker must perform an additional stop, emit `stopping`, or keep
HTTP alive merely to make that state observable.

## Shared job tracker

The shared layer must own:

- `run_id`, `worker_job_id`, client `job_id`, and command correlation.
- Races between HTTP acceptance and JSONL terminal observations.
- Completion confirmation from complete terminal snapshots.
- Duplicate observations, stale status, timeouts, crashes, and unconfirmed
  outcomes.
- Common Error, status, and protocol-error handling.

Every new submission uses a unique, non-empty client `job_id`. The Worker
does not promise idempotency or deduplication for that value. Distinguish
control commands from async jobs using explicit declarations; do not wait
for an async terminal merely because a control command was accepted.

Tracker behavior:

1. Retain a terminal observed before its HTTP response and associate it using
   the complete run and job identity. A lost accepted response does not
   invalidate an otherwise correctly associated complete terminal.
2. Keep confirmed terminals in the current execution's tracker independently
   of the Worker's `last_job` retention.
3. A later job replacing `last_job` must not overwrite an earlier job's
   confirmed result. `last_job` is not job history.
4. Repeated observations of one terminal must not send duplicate completion
   notifications.
5. Stale queued or running snapshots must not regress a terminal job.
6. Conflicting common identity, terminal state, `ok`, or common error
   category/code for the same job is a protocol conflict. Mark it and retain
   both the confirmed result and conflicting evidence. The affected workflow
   must not be reported as verified successful. A substantive domain-result
   conflict established by the adapter has the same workflow consequence.
7. Do not compare whole JSON objects for equality. Field order, outer status
   observation time, and extra diagnostics need not match. Domain result
   consistency checks beyond the common fields belong to the thin adapter.
8. Additional diagnostics may supplement evidence, but may not silently
   replace the confirmed terminal outcome. Terminal creation time remains
   fixed even as status observation time changes.
9. If no valid terminal or complete snapshot confirms the outcome, record it
   as unconfirmed internally rather than inventing success, failure, or
   cancellation on the Worker's behalf.
10. Do not automatically retry potentially side-effecting commands after
    timeout, crash, HTTP 500, disconnect, or a missing response.

The [job snapshot contract](common-worker-protocol.md#optional-job-snapshots)
and [terminal contract](common-cli-jsonl-contract.md#async-job-terminal)
define completeness and semantic equivalence. A snapshot missing required
`result` or `error` cannot confirm completion even if its state says
succeeded. No persistent job ledger, replay service, or Worker job-history
requirement is introduced.

## Optional streaming workflows

Use the [streaming extension](common-streaming-extension.md) only when the
runtime explicitly opts in through the documented tool setting, adopts
`common.streaming`, and supplies the matching
[stream fields](common-cli-jsonl-contract.md#optional-streaming-fields).
Manifest support alone or receiving samples does not establish adoption.
Use the existing tool contract for runs without the extension.

Keep consuming stdout independently of foreground jobs or recording windows.
Use `run_id` to correlate the one logical stream, and the tool contract to
distinguish data events from job and control events. Job IDs keep their own
meaning. Dataset and recording-window identities belong to the consumer and
need not be known to the Worker. Closing a recording window must not stop
stdout consumption or block draining the pipe.

### Waiting for source readiness

For `run_bound`, source startup follows the tool's existing startup behavior.
For `deferred_start`, send the documented source-start command through
`POST /command` after control readiness. Acceptance is not confirmation of
active source readiness. Only one deferred source-start opportunity exists.

A step requiring source readiness waits for `stream.state: "active"` for the
intended `run_id`, using JSONL or non-mutating HTTP status. Other steps need
not wait. Neither ready nor thread creation establishes this condition; no
first data event is required.

Bound the wait and simultaneously observe source termination, relevant
Worker/source errors, and process exit. If the source ends before active,
startup fails, the process exits, or the timeout expires, stop waiting and
do not release the dependent step as ready. An unrelated ordinary job failure
does not automatically mean source failure.

HTTP and JSONL have no total cross-channel order. Do not regress ended to
active or waiting, or active to waiting, because of a delayed snapshot. A
known stop, relevant failure, or process exit must not be overridden by an
earlier active observation. Active is an observed readiness milestone, not
an atomic promise that the source remains ready for a later step.

## Failure handling

Malformed JSON or a malformed known common event is a protocol error, not a
valid state update. Invalid ready/status declarations cannot establish
readiness. Unknown optional output fields may be ignored.

Successful `GET /status` uses the Common Status schema. A structured handler
failure uses the [status error envelope](common-worker-protocol.md#status-handler-failures)
and is not a status or readiness update. Disconnects and Worker exits remain
communication/lifecycle failures; no extra device operation is required to
obtain an error response.

Keep request errors, admission rejection, ordinary job failure, fatal Worker
failure, and cleanup failure distinct. Error category alone is not fatality.
Preserve domain details through the adapter. A protocol conflict does not
authorize replacing an earlier confirmed terminal or retrying a command.

Use failure or unconfirmed outcomes when required completion evidence is
missing. Do not treat every job failure as Worker failure in a multi-job
process, or use a successful job to disregard a later Worker failure.

`GET /status` must remain non-mutating and read existing memory state; do not
add device I/O or work to implement polling or readiness fallback.

## Live resource safety

Live runs use explicit operator-selected resources or resources from a
previous explicitly authorized discovery step. Do not scan, guess, or rotate
through resource strings inside a workflow unless the tool contract and
authorization explicitly permit it.

Protocol migration must preserve device commands, transport I/O, session
creation/ownership/closure, trigger and capture behavior, output safety, and
stop/cancel/cleanup operations and order. Do not automatically enable optional
features that add hardware observations.

If exposing a swallowed error requires changing Core execution or error
handling, or any of these hardware behaviors must change, assess that change
separately. First reconsider whether the common contract is demanding too
much. Such work is not implicitly part of an envelope-only migration and
requires its own authorization and appropriate validation.

## Cleanup

Prefer the existing cooperative stop path before process termination when
shutdown requires stopping an active Worker. Common clients accept both
HTTP 200 and 202 stop acknowledgements with the same meaning and without
tool-specific status-code branches. Stop acceptance is not job, output,
hardware-stop, or cleanup completion. Cancel acceptance likewise does not
guarantee a cancelled result.

If the Worker has already exited naturally, do not require an extra stop.
An unavailable endpoint is interpreted under the tool's existing cleanup
contract; it cannot independently prove successful cleanup. Never contact a
rejected URL as a cleanup workaround.

For an opted-in stream, consume retained tail data before ended, then summary,
on paths where structured output remains possible. No source data may follow
ended. The Worker need not keep HTTP alive for a terminal status poll.
Ended closes the logical stream; it does not establish complete data,
successful hardware stop, or successful cleanup.

Continue through stdout EOF and separately observe actual exit. Preserve
already observed errors, existing cleanup diagnostics, and non-zero exit
evidence even when they follow `summary.ok: true`. The summary's intended
exit code cannot overwrite actual exit. Conversely, actual exit `0` must not
override `summary.ok: false`, a known fatal Worker failure, or known cleanup
failure to produce a successful shutdown or workflow result. Preserve a
confirmed job terminal while recording shutdown or workflow failure separately.

Combine stream state, tool-specific quality and errors, summary, subsequent
cleanup evidence, EOF, and actual exit as applicable to the workflow. Keep
received partial data when a run fails or is unconfirmed. Consumer reception,
buffering, and persistence can lose data independently of the Worker; Worker
quality is not an end-to-end guarantee. Artifact paths, formats, storage,
privacy, publication, and ownership remain governed by existing contracts.

## Adapter boundary and integration acceptance

Adding a conforming v3 tool should primarily require tool registration,
required capabilities, startup/context construction, and a thin adapter for
domain commands, results, and existing safety cleanup.

Common Manifest, ready, status, error, job-tracker, and HTTP parsing must not
gain `tool_id`-specific branches for a new tool. Existing tool integrations
must actually transfer their principal job tracking into the shared layer.
Adding common types while keeping separate per-tool tracking implementations
does not satisfy this requirement.

Accept an additional conformance fake tool through registration and a thin
adapter to demonstrate this boundary. Existing multi-job integrations must
use the shared tracker in real workflows, including mixed-tool simulation.
This does not require adding new domain workflow actions or changing tool
execution, queue, session, cancellation, or source capabilities.

## Conformance and validation requirements

| Area | Required no-hardware verification |
| --- | --- |
| Version separation | Manifest/Worker/feature versions, exact raw version tokens, and unchanged independent CLI and artifact formats |
| Discovery | Manifest preflight, required capabilities, and runtime feature consistency with fixtures and fake Workers |
| Request handling | Context binding, HTTP envelopes, Common Error, and rejected requests causing no queue or device side effects |
| Async terminal | All three terminal states, retained partial results/artifacts, and one terminal on controllable paths using fake devices |
| Tracker races and failure | Terminal before HTTP response, lost response, snapshot recovery, stale status, conflicts, timeout, and crash |
| Shutdown | Stop 200/202, cancellation races, natural end without stopping, and cleanup failure after summary using subprocesses and fake cleanup |
| Streaming | Opt-in, active/data/tail/ended ordering, and delayed snapshots using simulation and existing streaming fakes |
| Preserved domain behavior | Existing fake transport/device call sequences and domain tests for sessions, triggers, safety, and cleanup |
| Actual Workers | Real Worker subprocesses in simulation exercising ready, HTTP, JSONL, EOF, and actual exit; fake Workers alone are insufficient |
| Cross-tool workflows | Mixed simulation covering run-bound and multi-job tools and actual use of common tracking |
| New tool integration | An additional conformance fake tool plus thin adapter without common parser branches |
| Project and release compatibility | Applicable existing CI, release acceptance, and packaged executable smoke checks |
| Local connections | Validation before connection, initial status fallback, replacement URLs, redirects, and proxies using local servers or controlled transports |

Additional positive and negative cases:

| Input or observation | Expected result |
| --- | --- |
| Startup-bound request adds `context: {}` | HTTP 400 before admission or device I/O |
| Request contains an unknown top-level field | HTTP 400 |
| Required feature absent or unsupported | Reject the affected integration |
| Runtime declares a Common feature absent from the Manifest | Reject the contradiction |
| Ready or initial fallback points to a wildcard or non-loopback host | Reject before any HTTP connection |
| Status supplies an unvalidated replacement URL | Validate before use; require the session's bound origin |
| A command, stop, or cancel URL uses a different loopback host or port | Reject before connection; all endpoints must share the session's origin |
| HTTP status `run_id` differs from the current WorkerSession | Reject the response as a session failure; do not rebind or adopt its URLs |
| Status has `worker_state: "running"` but non-null `fatal_error` | Not ready |
| Valid matching status has `worker_state: "running"` and `fatal_error: null` | May establish readiness after feature and URL validation |
| Status handler returns HTTP 500 with Common Error | Handle the failure; do not apply it as a status snapshot |
| Valid local endpoint redirects elsewhere | Do not follow the redirect |
| Environment defines a proxy | Local Worker transport must not use it |
| Job succeeds and Worker continues serving | Job complete; Worker shutdown not required for that job |
| Job succeeds and Worker later crashes | Retain job success; assess shutdown and workflow failure/unconfirmed outcome separately |
| Stop accepted but summary/EOF/exit evidence is incomplete | No shutdown-success inference |
| Natural end has complete result and shutdown evidence but no stopping | Valid |
| Summary succeeds and existing cleanup failure is observed later | Retain the failure; no fully successful workflow |
| Failed summary or known Worker fatal/cleanup failure is followed by exit `0` | Retain failure; no successful shutdown or workflow |
| The same job has a substantive terminal conflict | Retain the confirmed result and conflict evidence; no verified successful workflow |
| Only status observation time or optional diagnostics differ | Do not require whole-object equality |

See also the [terminal counterexamples](common-cli-jsonl-contract.md#conformance-examples)
and [streaming cases](common-streaming-extension.md#conformance-examples).
