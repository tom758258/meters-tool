# Core Branch Handoff

Updated: 2026-05-27

This file tracks current Core branch status, active risks, and next work.
Durable direction stays in `docs/project-plan.md`; the Core public contract
stays in `docs/core-integration.md`; hardware validation workflow stays in
`docs/hardware-test-plan.md`; historical Core validation records stay in
`docs/validation-history.md`.

## Current Status

- Branch: `Core`.
- Full Core Cut is complete for this branch: CLI runtime, wrapper scripts,
  CLI-specific tests, and old top-level compatibility shims have been removed.
- Distribution metadata is now `keysight-logger-core` version `1.0.0`.
- Intended release tag: `core-v1.0.0`.
- The package no longer declares a console script entry point.
- The maintained public Python API boundary is `keysight_logger.core`.
- Public Core symbols are covered by `tests/test_core_public_api.py`.
- `StartRequest` is the shared request model for validation, dry-run planning,
  and runtime session setup.
- `StartPlan` is the shared dry-run plan model and uses Core-neutral fields
  such as `measurement_name`.
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
.\.venv\Scripts\python.exe -m pytest tests/test_capabilities.py tests/test_measurement.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_csv_writer.py tests/test_simulator.py -q -p no:cacheprovider
```

Result: 124 passed, 59 subtests passed.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_core_public_api.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py tests/test_package_metadata.py tests/test_docs_integration_ownership.py -q -p no:cacheprovider
```

Result: 47 passed, 59 subtests passed.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

Result: 216 passed, 64 subtests passed.

Static residue checks should confirm that removed CLI modules, wrapper script
names, adapter-only measurement fields, project script metadata, and legacy
top-level import paths are absent from source, tests, and docs.

Result: clean for the planned residue scans.

This pass adds DCV Ratio SCPI only when `measurement="voltage-dc-ratio"` is
explicitly requested. Existing measurement defaults preserve their prior command
sequences, VISA timeout behavior, trigger wait strategy, stop flow,
release/local behavior, cleanup order, Auto Range/Zero, and VM Comp behavior.

Live 34461A validation was run on 2026-05-27 with
`USB0::0x2A8D::0x1301::MY60045220::0::INSTR` through the Core API. The
baseline immediate `current-dc` smoke test captured one sample with
`ok=True`, `captured=1`, and `errors=0`. The new measurement options were also
validated live: Auto Zero Once passed, AC bandwidth values `3`, `20`, and
`200` passed, invalid AC bandwidth input produced a validation error, and 10 A
current-terminal selection passed with an operator-confirmed safe setup.

The Auto Zero Once, AC bandwidth, current-terminal, DCV input impedance, and
DCV Ratio updates change SCPI only when the corresponding Core request fields or
`measurement="voltage-dc-ratio"` are explicitly set. Default requests preserve
previous command sequences. DCV Ratio has no live hardware validation recorded
yet in this handoff.

## Active Risks

- Downstream adapter branches must carry their own runtime, packaging, and
  user-facing workflow documentation.
- Any environment with an older editable install may need reinstalling after
  the package metadata rename.
- Hardware validation should move through Core API snippets or adapter-owned
  tooling, not removed wrapper scripts from this branch.
- DCV Ratio should receive an operator-wired live 34461A validation before it is
  treated as hardware-proven.

## Next Work

1. Keep Core-only tests green after adapter branches merge this package.
2. Update downstream adapter packages to depend on `keysight-logger-core`.
3. Re-run no-hardware simulator validation after any runner or control-plane
   change.
4. Keep hardware-facing changes behind explicit user confirmation and update
   `docs/hardware-test-plan.md` before future live validation.
5. Keep external-trigger live validation operator-driven with explicit trigger
   wiring and edge timing.
6. Run optional live DCV Ratio validation with the Input and Sense wiring limits
   documented in `docs/hardware-test-plan.md`.
