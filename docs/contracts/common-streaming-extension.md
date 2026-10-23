# Common Optional Streaming Extension

Worker schema version: `3`

Manifest schema version: `2`

Contract revision: `3.0`

Compatibility policy: `v3-only`

Feature: `common.streaming`, `contract_version: 1`

The Common v3.0 specification is finalized, with its major contract design
frozen. Runtime adoption is declared by each Tool's Manifest and tool-specific
contracts. The specification alone does not establish implementation,
conformance, release, or cross-project integration.

This optional contract defines source readiness, data output ordering, and
logical stream termination for one data stream per Worker runtime. It builds
on the [Common Worker Protocol](common-worker-protocol.md). Wire fields and
examples are defined in the
[Common CLI JSON / JSONL Contract](common-cli-jsonl-contract.md#optional-streaming-fields);
consumer behavior is defined in
[Common Orchestrator Workflows](common-orchestrator-workflows.md#optional-streaming-workflows).
These four documents are manually synchronized.

## Adoption and boundaries

A runtime must explicitly opt in at Worker startup using an existing setting
defined by its Worker-specific contract. Opt-in selects this contract, not
an instruction to start hardware. The tool defines how and when the source
starts. Runs without opt-in retain their existing behavior and output.

The Manifest declares `common.streaming` with `contract_version: 1` and a
non-empty `lifecycles` array containing supported `run_bound` and/or
`deferred_start` values. Manifest capability does not establish runtime
adoption. Runtime `features` must declare the same feature version, with
`lifecycles` containing only the selected lifecycle. That selection must be
supported by the Manifest and remain fixed for the runtime.

Ready must contain both the runtime feature declaration and
`stream.lifecycle`, without `stream.state`. HTTP readiness fallback
contains runtime `features`, `stream.lifecycle`, and `stream.state`.
Every JSONL and HTTP status carries the lifecycle and current state, together
with the base status fields and the same non-empty `run_id`.

Document publication, Worker schema 3, a `stream` object without the
runtime feature, JSONL mode, or ordinary sample output is not sufficient.
A tool must define and validate its source readiness boundary, output ordering,
and status reporting before advertising this extension. Unsupported,
undeclared, or contradictory behavior must not be treated as conformant.

The existing `run_id` identifies the runtime's sole logical stream. This
extension does not define stream IDs, event sequences, last-sequence fields,
or sequence capabilities. Worker-specific counters retain their meaning and
must not automatically be treated as common event sequence numbers. No common
sequence-gap detection is promised.

Data event names and payloads, source controls, device operations, job
admission, and quality fields remain Worker-specific. Job and control events
may interleave with data events without becoming additional streams. The
extension defines no multi-stream operation, replay, acknowledgement, repeated
source restart, generic stream start/stop command, or additional HTTP endpoint.
It does not change existing process exit meanings or cleanup procedures,
require async jobs or cancellation, or impose a shared data storage format.

In particular, v3 must not automatically enable streaming for Meters.
Additional hardware observations already confined to its explicit streaming
opt-in must not become requirements for every run.

## Lifecycle and state

`stream.lifecycle` is fixed for one runtime:

- `run_bound`: the source starts as part of the Worker-specific startup flow
  without a separate source-start command. It may finish naturally or continue
  until stopped.
- `deferred_start`: the source waits for a Worker-specific command through
  `POST /command`. Control-plane readiness alone does not start the source.

A tool may implement either lifecycle without implementing the other.
Streaming lifecycle and the Worker's execution model describe different
boundaries; do not infer one from the other's name.

| `stream.state` | Meaning |
| --- | --- |
| `waiting` | The source has not reached its defined effective capture or monitoring readiness condition. |
| `active` | The source has reliably reached that condition; a first data event is not required. |
| `ended` | The logical stream and its tail-handling procedure have terminated, and no more data events from this source will be emitted. |

The Worker-specific contract must define a reliably observable active boundary
using existing source-readiness observations. Worker readiness or creation of
a processing thread is insufficient. A source that is effectively ready to
wait for an external input may be active before any data arrives. The
declaration must not claim hardware guarantees beyond what the tool can
establish. Active does not prohibit otherwise legal Worker-specific commands.

The source lifecycle advances from `waiting` to `active` to `ended`, or
directly from `waiting` to `ended` if it is stopped before starting or
startup fails. It must not move backward or restart within the same runtime.
A fast run-bound startup need not emit an otherwise unnecessary waiting status
event.

Ended applies when tail handling has finished successfully or terminated with
failure or cancellation, including exhaustion of a tool-defined handling
limit. It does not guarantee complete data, a successful hardware stop, or
successful Worker cleanup. These outcomes remain independently reportable
through Worker-specific quality, error, and summary fields.

### One-time deferred source startup

A runtime may accept at most one deferred source-start request, and only while
waiting and before stop has taken effect. Acceptance consumes that opportunity;
duplicate starts must be rejected, including while startup is in progress or
after startup fails. Acceptance is not proof of active readiness. Command names,
arguments, and rejection details remain Worker-specific within the Common
command envelope.

Stop before source startup must clean up without starting the source, and
must prevent subsequent startup. The stream may move directly to ended.
Zero data events alone do not make this a failure; actual startup or cleanup
failures must still be reported according to the Worker-specific contract.
These deferred-start rules do not introduce a start command or redefine stop
races for existing run-bound behavior.

One-time startup concerns the source lifecycle, not ordinary jobs, transmissions,
or repeated triggers within that lifecycle. It does not require reusable source
sessions or alter normal command admission.

## Status snapshots

JSONL status and HTTP status must read from the same in-memory stream state.
`GET /status` must not perform additional device I/O, start work, mutate
queues, or clear errors to discover readiness. The source execution path
establishes state transitions; the HTTP path observes them.

Status snapshots contain the fixed lifecycle and current state. State changes
must be reported through JSONL status while structured output is possible,
subject to the startup and failure rules below. Snapshot delivery across JSONL
and HTTP is not atomic and does not establish a total cross-channel order.
No extra sequence field or synchronization handshake is introduced.

A delayed snapshot must not regress an already observed state from ended to
active or waiting, or from active to waiting. A later HTTP observation
timestamp does not change this rule.

## Event ordering and shutdown

On a normal, controllable startup path, emit ready before the JSONL active
status, and emit that active status before the first data event. Internal data
availability must not cause data events to overtake the active status. This
ordering does not require a waiting event or a first sample to establish active.

During stop, natural completion, or failure handling, finish the tool-defined
tail-handling procedure and emit any retained tail data before the terminal
JSONL ended status. Where structured output remains possible, emit one ended
transition status before the summary. No data event from the source may follow
ended. The summary does not repeat stream metadata.

Ended may precede a failed summary when tail handling or hardware stop fails.
The summary need not be the last stdout event: subsequent cleanup may emit
structured messages or existing failure evidence. Consumers must continue to
stdout EOF and separately confirm process exit. A successful summary cannot
erase a later known cleanup failure. See the
[cleanup evidence rules](common-cli-jsonl-contract.md#cleanup-failure-evidence).

The Worker need not retain its HTTP server so that a consumer can poll ended;
the JSONL terminal status provides that observation. Natural completion does
not require an extra stop or a `worker_state: "stopping"` event. Stream
termination, job completion, Worker shutdown, and workflow success remain
distinct; see the
[completion conditions](common-orchestrator-workflows.md#completion-conditions).

An early startup failure may occur before ready and must not be forced to emit
a readiness declaration. A source can fail without emitting active or data.
A crash or output failure may prevent ended or summary emission. Missing
terminal information is not proof of successful completion and must be handled
as failed or unconfirmed according to the Common and Worker-specific contracts.

## Data quality and time

Common quality vocabulary describes meaning, not required wire fields:

| Quality | Meaning |
| --- | --- |
| `unknown` | Completeness cannot be established. |
| `no_loss_detected` | No loss was detected within the tool's observation scope; this is not a zero-loss guarantee. |
| `incomplete` | Data is known to be incomplete, including loss, truncation, or failure to reach an expected amount. |

Each Worker-specific contract defines its actual fields, detection scope, and
how consumers map reported outcomes to these meanings. This extension does not
require `stream.data_integrity` or duplicate existing fields. Monitoring failure
is not itself confirmation of overflow. Known loss must not be erased by later
continued output or successful cleanup.

Execution success and data completeness are separate judgments. Common does
not change `summary.ok` or exit codes solely because of a quality classification;
the Worker-specific contract determines those outcomes. Consumer-side reception,
buffering, and persistence can lose data independently of the Worker, so Worker
quality is not an end-to-end guarantee.

Keep existing Common `timestamp_utc` formatting. The Worker-specific contract
must explain the time basis of data events, such as host observation or device
time. Common does not promise synchronized clocks or strictly increasing data
timestamps across or within tools.

## Conformance examples

| Observation | Required interpretation |
| --- | --- |
| Manifest supports streaming, but runtime does not opt in | Use the existing non-streaming tool contract |
| Samples arrive without runtime feature and stream declarations | Do not infer Common streaming adoption |
| Runtime selects a lifecycle absent from its Manifest | Reject the contradictory declaration |
| Ready, active status, data, retained tail, ended, summary | Valid controllable ordering; shutdown still requires EOF and actual exit |
| Ready, ended, summary, with no data after stop before source startup | Valid if existing result and cleanup semantics are satisfied |
| Thread created, with no reliable source-ready observation | Insufficient to report active |
| Source is reliably ready but has produced no first sample | May report active |
| Source data emitted after ended | Contract violation |
| Delayed active status after an observed ended state | Do not regress the state |
| Natural end omits Worker stopping | Valid; do not add a stop operation |
| Ended and successful summary followed by known cleanup failure | Retain the failure; do not report complete workflow success |

SIM, existing streaming fakes, and controlled delayed snapshots validate these
requirements without introducing hardware observations. They do not establish
real-device readiness or timing guarantees. V3 implementation and validation
remain separate from publication of this specification.
