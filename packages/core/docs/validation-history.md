# Core Validation History

Updated: 2026-05-31

This file records Core branch validation history only. Detailed CLI live
validation, CLI wrapper, JSONL, soft-trigger, soft-stop, and artifact history
belongs to the `Cli` branch.

## Core Baseline

The Full Core Cut baseline removes adapter runtime files and validates the
Core-only package surface with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_core_public_api.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py packages/core/tests/test_core_package_metadata.py packages/core/tests/test_core_docs_ownership.py -q -p no:cacheprovider
```

Latest result: 48 passed, 59 subtests passed after the branch-specific handoff
split added one docs ownership check.

The broader Core suite was also run with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

Latest result: 216 passed, 64 subtests passed.

## core-v1.1.1 No-Hardware Refresh

The core-v1.1.1 pass adds public capability introspection, structured
buffer-overflow warning details, adapter-readable dry-run plan descriptions,
validation-message coverage, simulator session coverage, and package metadata
version `1.1.1`.

No live hardware validation is required for this pass because it does not
change SCPI commands, VISA timeout behavior, trigger wait strategy, stop flow,
release/local behavior, cleanup order, VM Comp behavior, or measurement
runtime behavior.

Latest focused and full validation results are recorded in
`docs/session-handoff.md`.

The Core public API boundary is defined by `keysight_logger_core.__all__` and
verified by:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_core_public_api.py -q -p no:cacheprovider
```

Core request validation, dry-run planning, and runtime orchestration are
covered by:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py -q -p no:cacheprovider
```

Documentation ownership for this branch is covered by:

```powershell
.\.venv\Scripts\python.exe -m pytest packages/core/tests/test_core_docs_ownership.py -q -p no:cacheprovider
```

## Docs-Only Branch Reframe

The current Core baseline replaces copied CLI branch documentation with a
Core-focused documentation set:

- `README.md` is the Core branch entry point.
- `docs/integration.md` is the public Core contract.
- `docs/hardware-test-plan.md` describes Core API validation.
- `docs/supported-models.md` describes Core profile/model capability.
- `docs/session-handoff.md` routes to branch-specific handoff files.
- `docs/session-handoff.md` records current Core branch status.

This pass removed Core-branch ownership of CLI/WebUI adapter documents and did
not change runtime behavior, SCPI/VISA handling, cleanup flow, JSON schema, or
public Core API exports.

## Full Core Cut

The Core branch now validates that the package is named
`keysight-logger-core`, uses package version `1.0.0`, has no console entry
point, exposes the maintained public API through `keysight_logger_core`, and
does not keep removed adapter runtime files or legacy top-level module shims.

No live hardware validation was run for this cut because no SCPI, VISA timeout,
trigger wait, cleanup order, or measurement behavior changed.

## DCV Ratio Core Implementation

Core DCV Ratio implementation and no-hardware validation were completed on
2026-05-27. The change adds `measurement="voltage-dc-ratio"`, ratio sample
metadata from `DATA2?`, stricter `dcv_input_impedance` validation, and CSV
`measurement_metadata` output.

Focused no-hardware validation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_capabilities.py tests/test_measurement.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_csv_writer.py tests/test_simulator.py -q -p no:cacheprovider
```

Result: 124 passed, 59 subtests passed.

Required Core guard validation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_core_public_api.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py packages/core/tests/test_core_package_metadata.py packages/core/tests/test_core_docs_ownership.py -q -p no:cacheprovider
```

Result: 47 passed, 59 subtests passed.

Full Core suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

Result: 216 passed, 64 subtests passed.

No live 34461A DCV Ratio validation was run in this pass. Live validation
should follow `docs/hardware-test-plan.md` and use operator-confirmed Input and
Sense wiring limits.

## Live 34461A Measurement Options

Live Core API validation was run on 2026-05-27 with explicit resource
`USB0::0x2A8D::0x1301::MY60045220::0::INSTR`.

Baseline live smoke:

- `measurement="current-dc"`, `trigger_mode="immediate"`, `max_samples=1`.
- Result: `ok=True`, `reason="completed"`, `captured=1`, `errors=0`,
  `fatal_error=None`.
- Cleanup completed and released the instrument to local.

New measurement option live checks:

- Auto Zero Once passed on the operator-selected supported measurements.
- AC bandwidth values `3`, `20`, and `200` passed.
- Invalid AC bandwidth input produced the expected validation error.
- 10 A current terminal selection passed with an operator-confirmed safe setup.

These checks validate the new explicit Core request fields. Default requests
continue to preserve the previous command sequence.
