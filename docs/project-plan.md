# Keysight Logger Core Project Plan

Updated: 2026-05-26

## Purpose

This is the durable project plan for the Core runtime package. Current status
and handoff notes live in `docs/session-handoff.md`. Hardware and no-hardware
validation workflows live in `docs/hardware-test-plan.md`. The public Core
contract for adapters lives in `docs/core-integration.md`.

The Core package provides the shared request model, validation, dry-run
planning, acquisition runtime, event/result types, control-plane interfaces,
profile metadata, simulator, and safety rules used by downstream adapters.
Adapter branches own their user interfaces, process entry points, wrapper
scripts, transport payloads, and display formats.

## Current Baseline

The maintained Python package boundary is `keysight_logger.core`.
`keysight_logger.__init__` remains as the package marker, but the old
top-level module re-export shims are no longer part of this branch.

The distribution metadata is `keysight-logger-core`. It does not publish a
console entry point. Downstream adapters may package their own executables
against the Core API.

The current runtime supports these measurement types:

- `current-dc`
- `voltage-dc`
- `current-ac`
- `voltage-ac`
- `resistance-2w`
- `resistance-4w`

The current runtime supports these trigger and acquisition modes:

- `software`
- software timer through `timer_interval_s`
- `external`
- `immediate`
- `immediate-custom`
- `software-custom`
- `external-custom`

## Core Architecture

`src/keysight_logger/core/models.py` owns `StartRequest`,
`InstrumentProfile`, the Keysight 34461A profile, trigger and sample models,
and shared configuration types.

`src/keysight_logger/core/validation.py` owns trigger mode resolution, profile
backed request validation, CSV path planning, and buffer overflow warnings.

`src/keysight_logger/core/run_plan.py` owns dry-run `StartPlan` construction.

`src/keysight_logger/core/session.py` owns typed runtime events/results,
control-plane handles, no-op controls, and stop controller state.

`src/keysight_logger/core/runner.py` owns start-session orchestration:
instrument/backend creation, trigger router, CSV writer, measurement plugin,
acquisition engine, software trigger server, worker lifecycle, summary events,
and final cleanup.

`src/keysight_logger/core/acquisition.py` owns acquisition flow, buffered
drains, stop state, and capture statistics.

`src/keysight_logger/core/trigger.py` owns the software trigger server,
trigger router, worker status endpoint, and hardware trigger adapter.

`src/keysight_logger/core/instrument.py` owns VISA connection, IDN validation,
query/write helpers, release-to-local, cleanup release, close behavior, and
resource discovery helpers.

`src/keysight_logger/core/instrument_backend.py` owns the internal backend
protocol and factory for live VISA, simulator, and test backends.

`src/keysight_logger/core/measurement.py` owns measurement definitions,
canonical measurement name normalization, the registry, plugin creation, DMM
setup, and readout behavior.

`src/keysight_logger/core/storage.py` owns CSV formatting and row writing.

`src/keysight_logger/core/simulator.py` owns deterministic fake instrument
behavior for no-hardware workflows.

`src/keysight_logger/core/constants.py` owns lightweight shared constants.

## Public API

`keysight_logger.core` is the formal package-root API for adapters. The
exported names are verified by `tests/test_core_public_api.py` and documented
in `docs/core-integration.md`.

Adapters should construct `StartRequest`, resolve the trigger mode, validate
the request, generate warnings, build a dry-run plan when needed, and call
`run_start_session()` for runtime acquisition. Adapters own serialization and
presentation.

Implementation submodules remain importable for internal maintenance and
focused tests. New adapters should prefer package-root imports from
`keysight_logger.core`.

## Safety Rules

Treat instrument-affecting behavior as high risk.

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
- Do not add automatic reconnect or automatic reset as part of unrelated work.

## Validation Workflow

For no-hardware Core validation, prefer focused tests first:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_core_public_api.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py tests/test_package_metadata.py tests/test_docs_integration_ownership.py -q -p no:cacheprovider
```

Then run the broader Core suite when practical:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

Live validation requires an explicit operator-provided VISA resource and should
follow `docs/hardware-test-plan.md`.

## Roadmap

1. Keep Core API tests and metadata tests aligned with the public adapter
   contract.
2. Re-run simulator and no-hardware validation after adapter merge points.
3. Add new instrument models through profile work first.
4. Standardize external-trigger live validation through explicit operator
   steps, not simulated trigger coverage.
5. Consider AC bandwidth or filter controls only after confirming exact 34461A
   SCPI commands, allowed values, and real-instrument behavior.
6. Treat multi-instrument orchestration as an adapter-layer design until a
   second real use case proves the need for aggregate Core APIs.

## Documentation Ownership

- Durable direction: `docs/project-plan.md`
- Current handoff and latest validation status: `docs/session-handoff.md`
- Historical validation records: `docs/validation-history.md`
- Shared Core public API contract: `docs/core-integration.md`
- Hardware and no-hardware validation workflow: `docs/hardware-test-plan.md`
- Core profile and model capability reference: `docs/supported-models.md`
