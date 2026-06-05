# Hardware Test Plan

This is the Core API validation guide for the Keysight 34461A acquisition
runtime. It validates Core behavior directly through Python APIs instead of
using CLI wrapper scripts as the primary entry point.

Use a real explicit VISA resource for live passes. Do not scan, guess, or
auto-select a resource in Core branch validation.

## No-Hardware Validation

Run the focused Core tests first:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_core_public_api.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py -q -p no:cacheprovider
```

Optional broader no-runtime-change checks:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_core_public_api.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py tests/test_measurement.py tests/test_instrument.py tests/test_simulator.py -q -p no:cacheprovider
```

On Windows, a broad run may encounter local temp, cache, or environment
permission issues. Record the exact failure and rely on focused Core tests plus
operator-approved live validation when broad local checks are blocked.

## Core Dry-Run Validation

Use `StartRequest`, `resolve_trigger_mode()`, `validate_start_request()`, and
`build_start_plan()` for dry-run planning:

```python
from keysight_logger_core import (
    StartRequest,
    build_start_plan,
    get_default_instrument_profile,
    resolve_trigger_mode,
    validate_start_request,
)

request = StartRequest(
    resource="SIM::34461A",
    csv=None,
    trigger_mode="immediate",
    measurement="current-dc",
    max_samples=1,
)
profile = get_default_instrument_profile()
trigger_mode = resolve_trigger_mode(request)
validate_start_request(request, trigger_mode, instrument_profile=profile)
plan = build_start_plan(request, trigger_mode, instrument_profile=profile)
print(plan)
```

Expected result: validation succeeds and the plan uses Core-neutral fields such
as `measurement_name`.

Additional no-hardware dry-run checks for Core measurement options:

- `StartRequest(measurement="current-dc", auto_zero="once")` includes
  `ZERO:AUTO ONCE`.
- `StartRequest(measurement="voltage-dc", auto_zero="once")` includes
  `VOLT:DC:ZERO:AUTO ONCE`.
- `StartRequest(measurement="resistance-2w", auto_zero="once")` includes
  `RES:ZERO:AUTO ONCE`.
- `StartRequest(measurement="current-ac", ac_bandwidth_hz=3)` includes
  `CURR:AC:BAND 3`.
- `StartRequest(measurement="voltage-ac", ac_bandwidth_hz=200)` includes
  `VOLT:AC:BAND 200`.
- `StartRequest(measurement="current-dc", auto_range=False,
  measurement_range=10, current_terminal=10)` includes `CURR:DC:TERM 10` and
  does not include `CURR:DC:RANG 10`.
- `StartRequest(measurement="current-ac", auto_range=False,
  measurement_range=10, current_terminal=10)` includes `CURR:AC:TERM 10` and
  does not include `CURR:AC:RANG 10`.
- `StartRequest(measurement="voltage-dc-ratio", dcv_input_impedance="10m")`
  includes `CONF:VOLT:DC:RAT AUTO`, `VOLT:DC:IMP:AUTO OFF`,
  `VOLT:DC:NPLC 1.0`, and `VOLT:RAT:SEC "SENS:DATA"`; it does not include
  Auto Zero SCPI.
- `StartRequest(measurement="voltage-dc-ratio", auto_zero="off")` and
  `auto_zero="once"` produce validation errors.

## Core Simulator Validation

Use `run_start_session()` with `SIM::34461A` and bounded sample counts:

```python
from keysight_logger_core import (
    NoOpControlPlane,
    StartRequest,
    StartRunEvent,
    get_default_instrument_profile,
    resolve_trigger_mode,
    run_start_session,
    validate_start_request,
)


class PrintEventSink:
    def emit(self, event: StartRunEvent) -> None:
        if event.event == "summary":
            print(
                f"summary: captured={event.captured}, "
                f"errors={event.errors}, fatal_error={event.fatal_error}"
            )

request = StartRequest(
    resource="SIM::34461A",
    csv=".tmp_tests/core_simulate.csv",
    trigger_mode="immediate",
    measurement="current-dc",
    max_samples=1,
    simulate=True,
)
profile = get_default_instrument_profile()
trigger_mode = resolve_trigger_mode(request)
validate_start_request(request, trigger_mode, instrument_profile=profile)
result = run_start_session(
    request,
    trigger_mode,
    profile,
    PrintEventSink(),
    None,
    control_plane=NoOpControlPlane(),
)
print(result)
```

Expected result: `result.ok` is true, `result.captured == 1`, and
`result.errors == 0`.

## Live Validation

Live validation requires an operator-provided VISA resource. Replace
`<RESOURCE>` with the exact resource string supplied by the operator:

```python
from keysight_logger_core import (
    NoOpControlPlane,
    StartRequest,
    StartRunEvent,
    get_default_instrument_profile,
    resolve_trigger_mode,
    run_start_session,
    validate_start_request,
)


class PrintEventSink:
    def emit(self, event: StartRunEvent) -> None:
        if event.event == "summary":
            print(
                f"summary: captured={event.captured}, "
                f"errors={event.errors}, fatal_error={event.fatal_error}"
            )

request = StartRequest(
    resource="<RESOURCE>",
    csv=".tmp_tests/core_live_smoke.csv",
    trigger_mode="immediate",
    measurement="current-dc",
    max_samples=1,
)
profile = get_default_instrument_profile()
trigger_mode = resolve_trigger_mode(request)
validate_start_request(request, trigger_mode, instrument_profile=profile)
result = run_start_session(
    request,
    trigger_mode,
    profile,
    PrintEventSink(),
    None,
    control_plane=NoOpControlPlane(),
)
print(result)
```

Expected result: one bounded immediate capture, normal cleanup, and
`errors == 0`. External trigger validation must be operator-driven and requires
the operator to provide the trigger edge after the run arms.

Optional live 34461A checks for the new measurement options should use bounded
immediate captures and an operator-provided safe setup:

- `current-dc` or `voltage-dc` with `auto_zero="once"`.
- `current-ac` or `voltage-ac` with `ac_bandwidth_hz` set to one of `3`,
  `20`, or `200`.
- Current 10 A terminal validation only with the instrument physically wired to
  the 10 A input and the operator confirming the expected current path.
- DCV Ratio with `measurement="voltage-dc-ratio"`, `trigger_mode="immediate"`,
  and `max_samples=1`. Connect the signal to Input HI/LO and the reference
  through the Sense terminals. Sense terminal measurements must stay within
  +/-12 VDC, and Input LO and Sense LO must share a common reference with less
  than +/-2 V difference. Expected result: `ok=True`, `captured=1`, `errors=0`,
  and the CSV row contains the ratio plus `signal_voltage_v` and
  `reference_voltage_v` measurement metadata.

Latest live result, 2026-05-28:

- Resource: `USB0::0x2A8D::0x1301::MY60045220::0::INSTR`.
- Baseline immediate `current-dc` smoke passed with `ok=True`, `captured=1`,
  and `errors=0`.
- Auto Zero Once passed.
- AC bandwidth `3`, `20`, and `200` passed.
- Invalid AC bandwidth input produced the expected validation error.
- 10 A current terminal selection passed with an operator-confirmed safe setup.
- DCV Ratio immediate capture passed with `max_samples=5`, `ok=True`,
  `captured=5`, `errors=0`, ratio units, and `signal_voltage_v`,
  `reference_voltage_v`, and `secondary_source` measurement metadata.
- DCV Ratio external hardware-trigger capture passed with `slope=NEG`,
  `delay_s=0.0`, `max_samples=5`, `ok=True`, `captured=5`, `errors=0`,
  `trigger_source="hardware"`, ratio units, and `signal_voltage_v`,
  `reference_voltage_v`, and `secondary_source` measurement metadata.

## Safety Rules

- Do not change SCPI behavior without explicit user approval.
- Do not change VISA timeout strategy without explicit user approval.
- Do not change trigger wait strategy, `TRIG:DEL`, NPLC, Auto Zero, Auto Range,
  VM Comp, stop behavior, release/local behavior, or cleanup order without
  explicit user approval.
- Preserve the stop design: `engine.stop()` only sets stop state and stop
  events; VISA I/O belongs on the worker or cleanup path.
- Preserve cleanup order unless the requested task explicitly changes it:
  wait for worker, `release_to_local`, close, cleanup release, stop HTTP
  server.
- Hardware trigger timeout is a protective re-arm condition, not a capture
  error by itself.
- Hardware-triggered simple reads use `FETC?` after the trigger adapter arms
  and completes measurement.
- Software-triggered and immediate simple reads use `READ?`.
- Do not introduce repeated `*OPC?` polling without explicit approval.
