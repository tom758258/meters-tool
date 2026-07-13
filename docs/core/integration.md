# Core Integration

This document is the Core package public contract for downstream adapters. It
defines the stable package-root API, request boundary, validation flow, dry-run
plan, runtime events/results, control plane, and safety rules for acquisition
runtime integration.

Adapters such as CLI and WebUI consume Core through `meters_tool_core` and
the package contracts documented here, then maintain their own package-local
documentation and user-facing workflows. Core does not maintain
adapter-specific JSON, terminal, websocket, wrapper, or UI contracts.

This contract does not change SCPI, VISA timeout behavior, trigger wait
strategy, stop flow, cleanup order, measurement behavior, or public runtime
behavior.

## Public Imports

Prefer package-root imports from `meters_tool_core`:

```python
from meters_tool_core import (
    CoreCapabilities,
    CoreWarning,
    FEATURE_KIND_MEASUREMENT,
    FEATURE_KIND_TRIGGER_MODE,
    InstrumentProfile,
    MeasurementCapability,
    NoOpControlPlane,
    StartControlPlane,
    StartControlPlaneHandle,
    StartPlan,
    StartRequest,
    StartFeatureSupportScope,
    StartRunEvent,
    StartRunEventSink,
    StartRunResult,
    StartWorkflowSupport,
    SUPPORT_POLICY_MODE_PRODUCT,
    SUPPORT_POLICY_MODE_VALIDATION,
    VALIDATION_STATUS_FEATURE_PENDING,
    StopController,
    build_start_plan,
    generate_buffer_overflow_warning_details,
    generate_buffer_overflow_warnings,
    get_core_capabilities,
    get_default_instrument_profile,
    find_feature_support,
    normalize_model_id,
    normalize_support_feature_value,
    resolve_instrument_profile,
    resolve_trigger_mode,
    run_start_session,
    start_request_feature_requirements,
    start_workflow_support,
    validate_start_request,
    validate_start_workflow_support,
    validate_start_workflow_support_metadata,
)
```

These names are the public package-root boundary covered by
`tests/test_core_public_api.py`. Implementation submodules remain importable for
internal maintenance and tests, but adapters should not depend on private
helpers or test hooks.

Do not treat these internal names as public root API:
`SoftwareTriggerControlPlane`, `StartRunnerDependencies`, `StartRunControls`,
`NoOpStartRunControls`, `new_run_id`, `NullStartRunEventSink`, legacy
`StartCommandPlan`, or `print_buffer_overflow_warnings`.

## Request Boundary

`StartRequest` is the shared request model for validation, dry-run planning,
and runtime session setup. Adapters own their source input format and should
convert it before Core sees the request.

Before constructing `StartRequest`, adapters should:

- Convert empty optional fields to `None`.
- Trim requested instrument model text without maintaining an adapter-local
  supported-model list.
- Convert numeric fields to `int` or `float`.
- Convert toggles to booleans.
- Normalize adapter-only aliases.
- Map adapter-owned display labels to Core-owned request values such as
  `auto_zero`, `ac_bandwidth_hz`, `gate_time_s`, `freq_period_timeout`, and
  `current_terminal`.
- Keep display labels, localized strings, terminal output options, websocket
  payloads, wrapper compatibility fields, and other adapter schema outside
  Core.

`argparse.Namespace` is CLI-only and should not cross into Core validation,
dry-run planning, or runtime orchestration.

Core request fields use stable numeric or semantic values: `auto_zero` accepts
`True`, `False`, `"on"`, `"off"`, or `"once"`; `ac_bandwidth_hz` accepts
`3`, `20`, or `200` for AC, Frequency, and Period measurements;
`gate_time_s` accepts `0.01`, `0.1`, or `1.0` for Frequency and Period;
`freq_period_timeout` accepts `auto` or `1s` for Frequency only;
`current_terminal` accepts `3` or
`10` for current measurements; and `dcv_input_impedance` accepts `default`,
`10m`, or `auto` for DCV measurements. Frequency and Period apply effective
defaults of Auto Range, `20` Hz AC filter, and `0.1` s gate time. Frequency
also defaults its timeout to `auto`. Period exposes no timeout choices, sends
no timeout SCPI, and rejects an explicitly supplied `freq_period_timeout`.
Adapter labels, menu text, and UI grouping remain adapter-owned.

Adapters that expose DCV Ratio as a `voltage-dc` option should translate that
adapter-owned selection into Core `measurement="voltage-dc-ratio"` before
constructing `StartRequest`. Core does not add a separate CLI/UI flag for this
mapping.

## Capabilities Lookup

Adapters can inspect the Core-owned profile surface without depending on
private profile internals:

```python
capabilities = get_core_capabilities()

assert isinstance(capabilities, CoreCapabilities)
for measurement in capabilities.measurements:
    assert isinstance(measurement, MeasurementCapability)
    print(measurement.measurement_name, measurement.range_values)
```

`get_core_capabilities()` derives its values from the active
`InstrumentProfile` and Core measurement definitions. It reports adapter-facing
measurement names such as `current-dc` while keeping internal normalized
measurement types such as `current_dc`. Per-measurement capabilities include
Frequency/Period gate-time choices and Frequency-only timeout choices plus
their effective defaults.

`CoreCapabilities.model_id` exposes the active profile's stable ID alongside
the unchanged canonical `model`. Each `available_profiles` entry likewise
contains `vendor`, `model`, and `model_id`. These fields come directly from the
authoritative profile registry and are additive metadata; they do not change
measurement, trigger, limit, selection, or support-policy behavior.

## Profile Identity

`InstrumentProfile.model` remains the canonical instrument model token used by
existing request, expected-model, IDN, CLI, WebUI, and runtime contracts.
`InstrumentProfile.model_id` is the explicit stable machine-readable profile
identifier. The maintained mappings are:

- `34461A` -> `keysight-34461a`
- `34460A` -> `keysight-34460a`

Display text such as `Keysight 34461A` is presentation only. Stable IDs are
declared explicitly by profiles and are not generated from vendor or display
text at runtime.

Profile lookup accepts a canonical model, stable model ID, or existing alias
case-insensitively. Use `normalize_model_id(...)` when an integration needs the
stable Core identity:

```python
assert normalize_model_id("34461a") == "keysight-34461a"
assert normalize_model_id("KEYSIGHT-34460A") == "keysight-34460a"
```

Requested-model normalization deliberately continues to return `34461A` or
`34460A`, not a model ID, so existing expected-model and adapter contracts do
not change. A selected live identity remains an expected-model guard only; the
detected `*IDN?` profile remains authoritative at runtime. A stable model ID is
identity metadata, not live-support authorization or promotion.

Downstream adapters should use public Core profile lookup and normalization
APIs instead of maintaining a competing model-ID mapping. Maintained validation
and release wrapper targets are aligned with the Core `model_id` inventory;
wrapper formats and artifact details remain CLI-owned contracts.

## Validation Flow

Adapters should validate a start request before showing a confirmation view or
starting a run:

```python
profile = get_default_instrument_profile()
trigger_mode = resolve_trigger_mode(request)
validate_start_request(request, trigger_mode, instrument_profile=profile)
validate_start_workflow_support(request, trigger_mode, profile)
warnings = generate_buffer_overflow_warnings(request, trigger_mode, profile)
```

The model field has mode-specific meaning:

- Dry-run and simulate: `StartRequest.instrument_model` is a no-hardware
  planning profile. It selects the profile used for validation, planning, and
  simulation without live VISA identity preflight.
- Live: `StartRequest.instrument_model` is an expected-model guard only. The
  live runtime profile comes from the connected instrument `*IDN?`; the
  selected model must never override detected IDN or unlock capabilities for a
  different instrument.
- Safety boundary: Core support policy and the `run_start_session()` runner
  final gate use the resolved profile and remain the final gate for CLI,
  WebUI backend, and direct Core/API submissions.

CLI/WebUI adapters should resolve the start profile once and reuse it for
validation, warnings, planning, and runtime. For live starts, omitted
`StartRequest.instrument_model` means IDN auto-detect. When a model string is
present, Core profile logic normalizes and validates it, such as `34461a` to
`34461A`, and rejects unknown models with the supported profile models listed.
Live explicit models are expected-model guards only and never override the
detected IDN-selected profile. A selected/detected mismatch must fail before
instrument-affecting setup/write SCPI. Adapters should pass the IDN-resolved
profile to `run_start_session(...)`, but the runner also re-resolves the start
profile from Core-owned request state as the final safety gate before opening
the runtime backend.

For dry-run and simulate, a selected model chooses the planning/simulator
profile and must not trigger a live VISA identity preflight. Omitted model is
accepted only when the simulator resource encodes a single supported model
token, such as `SIM::34460A` or `SIM::34461A`:

```python
request, profile = resolve_start_profile(request)
```

`resolve_instrument_profile(None)` remains a compatibility helper that returns
the default 34461A profile; do not use it to interpret omitted CLI/WebUI live
start model requests.

The final Core validation gate is profile-specific. In the base 34460A profile,
Core rejects external and external-custom trigger modes, current terminal
selection, 10 A current range requests, and custom trigger plans with more than
1000 expected readings unless `allow_buffer_overflow_risk` is true. Validated
34461A behavior remains allowed through the 34461A profile. Adapters should
surface capabilities for user convenience, but direct adapter calls must still
delegate unsupported combinations to Core validation instead of trusting UI or
CLI affordances.

`validate_start_workflow_support()` is the Core-owned live support policy gate
for `start-trigger-record`. Call it after profile-specific request validation
and before dry-run planning or `run_start_session(...)`. In live mode it uses
the detected IDN profile, not the selected expected-model guard. The runner
performs the same final validation/support gate after live IDN detection and
before backend connect/setup, so direct Core callers cannot use a selected or
externally supplied profile as a feature unlock. In dry-run and simulate modes
it leaves profile-supported planning/simulation open while hard profile limits
remain enforced by `validate_start_request(...)`.

Live policy evaluation has three required layers: the exact transport/backend
connection scope, the normalized measurement feature, and the effective
trigger-mode feature. Feature entries belong to one exact connection scope;
USB/system-VISA evidence does not open TCPIP/system-VISA or TCPIP/pyvisa-py.
Product mode requires `live_validated_full_suite` at all three layers.
Validation mode additionally permits an explicitly registered
`transport_pending` connection and explicitly registered `feature_pending`
features. A missing connection or feature entry, an unknown status, or
`not_supported_by_model` fails closed in both modes.

Adapters that need additive capability metadata can use
`start_workflow_support(profile)` and its `StartWorkflowSupport` values. Each
exact `StartWorkflowSupportScope` carries connection status plus explicit
`StartFeatureSupportScope` entries for measurement and trigger mode. Feature
values use normalized Core names. `start_request_feature_requirements()` and
`find_feature_support()` provide the matching lookup, while
`validate_start_workflow_support_metadata()` checks duplicate, missing,
unexpected, and unsupported-status registrations against the profile
inventory. Runtime lookup still fails closed independently of that consistency
check.

### Support Policy Granularity

Meters intentionally applies live support policy at the workflow level rather
than maintaining a policy entry for every internal SCPI or runtime operation.

The current independently promotable live workflow is
`start-trigger-record`. Its exact support key is:

```text
workflow + detected model + transport + backend + workflow-specific features
```

For `start-trigger-record`, the stable workflow-specific feature dimensions are
measurement and trigger mode. These dimensions can change the complete
acquisition profile, including measurement setup, trigger setup, timing, buffer
requirements, acquisition flow, and cleanup behavior.

Internal phases such as identity preflight, measurement setup, trigger setup,
initiate, wait, fetch or read, buffer drain, stop, cleanup, release, and
low-level SCPI operations are implementation details of the complete
acquisition workflow. They are not independently promotable Product
capabilities.

This granularity is deliberate. Splitting internal phases into separate support
entries would expose implementation details, create misleading partial-support
states, and still require a final workflow-level decision before acquisition
could run.

This policy follows the same fail-closed and evidence-backed promotion
principles as command-centric instrument projects while using a scope that
matches the Meters runtime model. Product mode requires the exact connection
scope and all requested workflow features to be validated. Validation mode
allows only explicitly registered pending scopes and features. Passing
validation evidence never promotes Product support automatically.

If another independently callable live workflow is added in the future, define
a separate workflow policy with its own exact connection scopes and stable
categorical feature dimensions. Do not turn internal setup, query, fetch, stop,
cleanup, or release operations into separate Product capabilities unless they
become independently callable public workflows with their own stable contract
and evidence boundary.

Current validated 34461A live scopes include USB/system-VISA, LAN/TCPIP with
system VISA, and LAN/TCPIP with optional CLI-only pyvisa-py `@py`. Current
34460A USB/system-VISA support includes the explicitly promoted DCV Ratio
measurement, while 34460A LAN/TCPIP scopes remain `transport_pending`; their
profile-supported features are explicitly `feature_pending`. WebUI
`/api/capabilities` exposes these facts along with display-oriented model
support summaries so the browser can show connection and feature status without
changing the Core runtime gate.

`ValueError` from validation is a normal adapter-facing input error. Buffer
warnings are warnings, not errors, unless an adapter requires explicit user
confirmation and the user declines.

### Validation Harness Support Policy Mode

Normal product integrations should use the default support policy mode,
`SUPPORT_POLICY_MODE_PRODUCT`. In that mode, CLI, WebUI, and direct Core live
starts remain gated to scopes marked `live_validated_full_suite`.

`SUPPORT_POLICY_MODE_VALIDATION` exists only for validation tooling such as
`scripts/live-cli-check.ps1`. It allows known `transport_pending` connection
scopes and `feature_pending` measurement/trigger-mode entries to execute so an
operator can collect artifacts with an exact operator-provided VISA resource.
It does not promote public support, treat missing metadata as pending, or
bypass unsupported-by-model workflows and hard profile limits. The 34460A base
profile still rejects external/external-custom workflows, the 10 A/current-
terminal path, and buffer drain sizes above the profile reading-memory limit.
34460A DCV Ratio is Product-open on USB/system-VISA after maintainer review and
explicit promotion of separate bounded evidence. The existing 12-case wrapper
full suite did not include Ratio. Its measurement status combines with the
Product-open immediate, software, immediate-custom, and software-custom trigger
modes; this does not open either 34460A LAN scope.

The runner has the same final gate:

```python
result = run_start_session(
    request,
    trigger_mode,
    profile,
    EventSink(),
    controls=None,
    support_policy_mode=SUPPORT_POLICY_MODE_VALIDATION,
)
```

Use that mode only from reviewed validation harnesses. Public support promotion
requires reviewed artifacts plus an explicit support metadata and documentation
update.

Validation mode does not imply maintainers must validate every pending scope
immediately. Pending 34460A LAN/TCPIP scopes are future evidence-collection
paths for matching LAN/LXI hardware or contributors. Without matching hardware,
they remain pending and product-closed.

Adapters that need stable warning codes can use the structured helper:

```python
warning_details = generate_buffer_overflow_warning_details(
    request,
    trigger_mode,
    profile,
)

for warning in warning_details:
    assert isinstance(warning, CoreWarning)
    assert warning.severity == "warning"
```

`generate_buffer_overflow_warnings()` remains the compatibility string helper
and returns the same messages as `[warning.message for warning in
generate_buffer_overflow_warning_details(...)]`.

## Dry-Run Plan

`build_start_plan(...)` returns a `StartPlan` after validation succeeds. It is
the Core dry-run preview contract for resource, CSV path, trigger mode,
measurement, SCPI plan, read path, cleanup steps, and buffer warnings.
Dry-run planning is pure Core planning: it does not open VISA, construct
runtime trigger adapters, start control servers, or wait for hardware trigger
events. External-trigger dry-run previews are computed from Core planning data;
runtime trigger adapters remain responsible for non-dry-run execution only.

`StartPlan` uses Core-neutral fields such as `measurement_name`.
Adapters may derive their own display or compatibility fields, but those fields
are outside the Core schema and are not returned by Core.

```python
plan = build_start_plan(request, trigger_mode, profile, buffer_warnings=warnings)

assert isinstance(plan, StartPlan)
print(plan.trigger_description)
print(plan.sample_limit_description)
print(plan.option_summary)
```

## Runtime Session

`run_start_session(...)` owns non-dry-run start orchestration. It accepts the
request, resolved trigger mode, adapter-resolved profile, optional event sink,
optional controls, and optional control plane. Before creating the runtime
backend, it resolves the effective start profile again: live uses the detected
`*IDN?` profile, while simulate uses the no-hardware simulator profile. It then
reruns request validation and support policy checks with that resolved profile.

Runtime status is emitted as typed `StartRunEvent` objects. Final state is
returned as `StartRunResult`, including `ok`, `reason`, `captured`, `errors`,
`fatal_error`, `csv_path`, `run_id`, and optional control-plane handle data.

Adapters own serialization. Core does not define terminal output, HTTP
payloads, websocket messages, artifact formats, or localized display text.

```python
class EventSink:
    def emit(self, event: StartRunEvent) -> None:
        if event.event == "sample":
            print(event.captured, event.sample.value)


result = run_start_session(
    request,
    trigger_mode,
    profile,
    EventSink(),
    controls=None,
    control_plane=NoOpControlPlane(),
)

assert isinstance(result, StartRunResult)
```

## Control Plane And Stop

Core exposes `StartControlPlane`, `StartControlPlaneHandle`,
`NoOpControlPlane`, and `StopController` for integrations that need software
trigger or stop routing.

The public model is single-session: one `StartRequest`, one resolved trigger
mode, one run, and one `StartRunResult`. Multi-instrument orchestration should
start multiple independent sessions and aggregate them at the adapter or
application layer.

Stop behavior must stay aligned with the runner design. A stop request signals
the running engine through the control path; VISA I/O remains on the worker or
cleanup path.

## Safety Rules

Adapters must not call acquisition engine internals, close VISA handles
directly, perform release/local cleanup, or re-order runner cleanup steps. The
runner owns acquisition setup, worker lifecycle, release-to-local, close,
cleanup release, and control server shutdown.

Do not introduce adapter behavior that changes SCPI commands, VISA timeout
strategy, trigger wait strategy, `TRIG:DEL`, NPLC, Auto Zero, Auto Range,
VM Comp, stop/release/local behavior, or repeated `*OPC?` polling without an
explicit project decision and hardware validation plan.

