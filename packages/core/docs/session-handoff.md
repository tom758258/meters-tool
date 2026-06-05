# Core Branch Handoff

Updated: 2026-05-31

This file tracks current Core branch status, active risks, and next work.
Durable direction stays in `docs/project-plan.md`; the Core public contract
stays in `docs/integration.md`; hardware validation workflow stays in
`docs/hardware-test-plan.md`; historical Core validation records stay in
`docs/validation-history.md`.

## Current Status

- Branch: `Core`.
- Full Core Cut is complete for this branch: CLI runtime, wrapper scripts,
  CLI-specific tests, and old top-level compatibility shims have been removed.
- Distribution metadata is now `keysight-logger-core` version `1.1.1`.
- Core is ready for the `core-v1.1.1` tag after the 2026-05-31 no-hardware
  release regression.
- The package no longer declares a console script entry point.
- The maintained public Python API boundary is `keysight_logger_core`.
- Public Core symbols are covered by `tests/test_core_public_api.py`.
- Public adapter-facing capability introspection is exposed through
  `get_core_capabilities()`, `CoreCapabilities`, and
  `MeasurementCapability`.
- Structured buffer-overflow warning details are exposed through
  `generate_buffer_overflow_warning_details()` and `CoreWarning`; the existing
  string warning helper remains compatible.
- `StartRequest` is the shared request model for validation, dry-run planning,
  and runtime session setup.
- `StartPlan` is the shared dry-run plan model and uses Core-neutral fields
  such as `measurement_name`; v1.1.1 adds adapter-readable trigger, sample
  limit, and option summary fields without removing existing fields.
- `StartRunEvent` and `StartRunResult` are the typed runtime boundary.
- `StartControlPlane`, `StartControlPlaneHandle`, `NoOpControlPlane`, and
  `StopController` define the current single-session control-plane surface.
- Profile and model capability data remain centered on the Keysight 34461A.
- Core now supports Auto Zero Once for `current-dc`, `voltage-dc`, and
  `resistance-2w`; AC bandwidth selection for `current-ac` and `voltage-ac`;
  explicit current terminal selection for current measurements; and
  `voltage-dc-ratio` with signal/reference voltage measurement metadata.

## Latest Validation

Latest local no-hardware validation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_core_public_api.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py tests/test_simulator.py tests/test_csv_writer.py packages/core/tests/test_core_package_metadata.py packages/core/tests/test_core_docs_ownership.py -q -p no:cacheprovider
```

Result: 63 passed, 64 subtests passed on 2026-05-31.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_core_public_api.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py packages/core/tests/test_core_package_metadata.py packages/core/tests/test_core_docs_ownership.py -q -p no:cacheprovider
```

Result: 53 passed, 59 subtests passed on 2026-05-31.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

Result: 223 passed, 69 subtests passed on 2026-05-31.

Static residue checks should confirm that removed CLI modules, wrapper script
names, adapter-only measurement fields, project script metadata, and legacy
top-level import paths are absent from source, tests, and docs.

Result: adapter residue scan clean. Stale-version scan clean after updating
the handoff to the v1.1.1 tag target.

This pass adds DCV Ratio SCPI only when `measurement="voltage-dc-ratio"` is
explicitly requested. Existing measurement defaults preserve their prior command
sequences, VISA timeout behavior, trigger wait strategy, stop flow,
release/local behavior, cleanup order, Auto Range/Zero, and VM Comp behavior.

Live 34461A validation was run on 2026-05-27 with
`USB0::0x2A8D::0x1301::MY60045220::0::INSTR` through the Core API. The
baseline immediate `current-dc` smoke test captured one sample with
`ok=True`, `captured=1`, and `errors=0`. The new measurement options were also
validated live: Auto Zero Once passed, AC bandwidth values `3`, `20`, and
`200` passed, invalid AC bandwidth input produced a validation error, 10 A
current-terminal selection passed with an operator-confirmed safe setup, and
DCV Ratio captured five bounded immediate samples and five bounded external
hardware-trigger samples with `ok=True`, `captured=5`, `errors=0`, ratio
units, and `signal_voltage_v`, `reference_voltage_v`, and `secondary_source`
metadata. The external-trigger pass used `slope=NEG`, `delay_s=0.0`, and
reported `trigger_source="hardware"` for each sample.

The Auto Zero Once, AC bandwidth, current-terminal, DCV input impedance, and
DCV Ratio updates change SCPI only when the corresponding Core request fields or
`measurement="voltage-dc-ratio"` are explicitly set. Default requests preserve
previous command sequences.

## Active Risks

- Downstream adapter branches must carry their own runtime, packaging, and
  user-facing workflow documentation.
- Any environment with an older editable install may need reinstalling after
  the package metadata rename.
- Hardware validation should move through Core API snippets or adapter-owned
  tooling, not removed wrapper scripts from this branch.
- No open Core runtime blocker is known for `core-v1.1.1`. Remaining work is
  downstream adapter packaging and future model or measurement expansion.

## Next Work

1. Keep Core-only tests green after adapter branches merge this package.
2. Update downstream adapter packages to depend on `keysight-logger-core`.
3. Re-run no-hardware simulator validation after any runner or control-plane
   change.
4. Keep hardware-facing changes behind explicit user confirmation and update
   `docs/hardware-test-plan.md` before future live validation.
5. Keep future external-trigger live validation operator-driven with explicit
   trigger wiring and edge timing.
