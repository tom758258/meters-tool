# Core Integration

This document is the Core branch public contract for downstream adapters. It
defines the stable package-root API, request boundary, validation flow, dry-run
plan, runtime events/results, control plane, and safety rules for acquisition
runtime integration.

Adapter branches such as CLI and WebUI should merge Core, then maintain their
own adapter documentation and user-facing workflows from this contract. Core
does not maintain adapter-specific JSON, terminal, websocket, wrapper, or UI
contracts on this branch.

This contract does not change SCPI, VISA timeout behavior, trigger wait
strategy, stop flow, cleanup order, measurement behavior, or public runtime
behavior.

## Public Imports

Prefer package-root imports from `keysight_logger_core`:

```python
from keysight_logger_core import (
    CoreCapabilities,
    CoreWarning,
    InstrumentProfile,
    MeasurementCapability,
    NoOpControlPlane,
    StartControlPlane,
    StartControlPlaneHandle,
    StartPlan,
    StartRequest,
    StartRunEvent,
    StartRunEventSink,
    StartRunResult,
    StopController,
    build_start_plan,
    generate_buffer_overflow_warning_details,
    generate_buffer_overflow_warnings,
    get_core_capabilities,
    get_default_instrument_profile,
    resolve_trigger_mode,
    run_start_session,
    validate_start_request,
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
- Convert numeric fields to `int` or `float`.
- Convert toggles to booleans.
- Normalize adapter-only aliases.
- Map adapter-owned display labels to Core-owned request values such as
  `auto_zero`, `ac_bandwidth_hz`, and `current_terminal`.
- Keep display labels, localized strings, terminal output options, websocket
  payloads, wrapper compatibility fields, and other adapter schema outside
  Core.

`argparse.Namespace` is CLI-only and should not cross into Core validation,
dry-run planning, or runtime orchestration.

Core request fields use stable numeric or semantic values: `auto_zero` accepts
`True`, `False`, `"on"`, `"off"`, or `"once"`; `ac_bandwidth_hz` accepts
`3`, `20`, or `200` for AC measurements; `current_terminal` accepts `3` or
`10` for current measurements; and `dcv_input_impedance` accepts `default`,
`10m`, or `auto` for DCV measurements. Adapter labels, menu text, and UI
grouping remain adapter-owned.

Adapters that expose DCV Ratio as a `voltage-dc` option should translate that
adapter-owned selection into Core `measurement="voltage-dc-ratio"` before
constructing `StartRequest`. Core does not add a separate CLI/UI flag for this
mapping on this branch.

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
measurement types such as `current_dc`.

## Validation Flow

Adapters should validate a start request before showing a confirmation view or
starting a run:

```python
profile = get_default_instrument_profile()
trigger_mode = resolve_trigger_mode(request)
validate_start_request(request, trigger_mode, instrument_profile=profile)
warnings = generate_buffer_overflow_warnings(request, trigger_mode, profile)
```

`ValueError` from validation is a normal adapter-facing input error. Buffer
warnings are warnings, not errors, unless an adapter requires explicit user
confirmation and the user declines.

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

`StartPlan` uses Core-neutral fields such as `measurement_name`.
Adapter branches may derive their own display or compatibility fields, but
those fields are outside the Core schema and are not returned by Core.

```python
plan = build_start_plan(request, trigger_mode, profile, buffer_warnings=warnings)

assert isinstance(plan, StartPlan)
print(plan.trigger_description)
print(plan.sample_limit_description)
print(plan.option_summary)
```

## Runtime Session

`run_start_session(...)` owns non-dry-run start orchestration. It accepts the
validated request, resolved trigger mode, profile, optional event sink,
optional controls, and optional control plane.

Runtime status is emitted as typed `StartRunEvent` objects. Final state is
returned as `StartRunResult`, including `ok`, `reason`, `captured`, `errors`,
`fatal_error`, `csv_path`, `run_id`, and optional control-plane handle data.

Adapters own serialization. Core does not define terminal output, HTTP
payloads, websocket messages, artifact formats, or localized display text on
this branch.

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
