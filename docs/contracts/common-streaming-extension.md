# Common Optional Streaming Extension

Schema version: `2`

Contract revision: `2.2`

Compatibility policy: `v2-only`

The contract revision identifies this Common document-set revision. Runtime
wire compatibility is determined by `schema_version`, not by the contract
revision.

This optional contract defines source readiness, data output ordering, and
logical stream termination for one data stream per Worker runtime. It builds
on the [Common Worker Protocol](common-worker-protocol.md). Wire fields and
examples are defined in the
[Common CLI JSON / JSONL Contract](common-cli-jsonl-contract.md#optional-streaming-fields);
consumer behavior is defined in
[Common Orchestrator Workflows](common-orchestrator-workflows.md#optional-streaming-workflows).

## Adoption and boundaries

A runtime must explicitly opt in at Worker startup using a setting defined by
its Worker-specific contract. Opt-in selects this contract, not an instruction
to start hardware. The tool defines how and when the source starts. Runs
without opt-in retain their existing behavior and output.

Adoption is declared by `ready.stream.lifecycle`, or by `stream.lifecycle`
and `stream.state` in HTTP status when the consumer uses the existing status
fallback. Document publication or schema version `2` alone does not establish
implementation or adoption. A tool must define and validate its source
readiness boundary, output ordering, and status reporting before advertising
this extension. Unsupported or undeclared behavior must not be treated as
conformant by consumers.

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
It does not change existing process exit meanings or cleanup procedures.

## Lifecycle and state

`stream.lifecycle` is fixed for one runtime:

- `run_bound`: the source starts as part of the Worker-specific startup flow
  without a separate source-start command. It may finish naturally or continue
  until stopped.
- `deferred_start`: the source waits for a Worker-specific command through
  `POST /command`. Control-plane readiness alone does not start the source.

A tool may implement either lifecycle without implementing the other.

| `stream.state` | Meaning |
| --- | --- |
| `waiting` | The source has not reached its defined effective capture or monitoring readiness condition. |
| `active` | The source has reliably reached that condition; a first data event is not required. |
| `ended` | The logical stream and its tail-handling procedure have terminated, and no more data events from this source will be emitted. |

The Worker-specific contract must define a reliably observable active boundary.
Worker readiness or creation of a processing thread is insufficient. A source
that is effectively ready to wait for an external input may be active before
any data arrives. The declaration must not claim hardware guarantees beyond
what the tool can establish. Active does not prohibit otherwise legal
Worker-specific commands.

The source lifecycle advances from `waiting` to `active` to `ended`, or directly
from `waiting` to `ended` if it is stopped before starting or startup fails.
It must not move backward or restart within the same runtime. A fast run-bound
startup need not emit an otherwise unnecessary waiting status event.

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
`GET /status` must not perform additional device I/O, start work, or mutate
state to discover readiness. The source execution path establishes state
transitions; the HTTP path observes them.

Status snapshots contain the fixed lifecycle and current state. State changes
must be reported through JSONL status while structured output is possible,
subject to the startup and failure rules below. Snapshot delivery across JSONL
and HTTP is not atomic and does not establish a total cross-channel order.
No extra sequence field or synchronization handshake is introduced.

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
structured messages. Consumers must continue to stdout EOF and separately
confirm process exit. The Worker need not retain its HTTP server so that a
consumer can poll ended; the JSONL terminal status provides that observation.

An early startup failure may occur before ready and must not be forced to emit
a readiness declaration. A source can fail without emitting active or data.
A crash or output failure may prevent ended or summary emission. Missing
terminal information is not proof of successful completion and must be handled
as failed or incomplete according to the Common and Worker-specific contracts.

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
