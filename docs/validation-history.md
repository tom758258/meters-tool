# Core Validation History

Updated: 2026-05-26

This file records Core branch validation history only. Detailed CLI live
validation, CLI wrapper, JSONL, soft-trigger, soft-stop, and artifact history
belongs to the `Cli` branch.

## Core Baseline

The Full Core Cut baseline removes adapter runtime files and validates the
Core-only package surface with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_core_public_api.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py tests/test_package_metadata.py tests/test_docs_integration_ownership.py -q -p no:cacheprovider
```

Latest result: 41 passed, 46 subtests passed.

The broader Core suite was also run with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

Latest result: 191 passed, 51 subtests passed.

The Core public API boundary is defined by `keysight_logger.core.__all__` and
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
.\.venv\Scripts\python.exe -m pytest tests/test_docs_integration_ownership.py -q -p no:cacheprovider
```

## Docs-Only Branch Reframe

The current Core baseline replaces copied CLI branch documentation with a
Core-focused documentation set:

- `README.md` is the Core branch entry point.
- `docs/core-integration.md` is the public Core contract.
- `docs/hardware-test-plan.md` describes Core API validation.
- `docs/supported-models.md` describes Core profile/model capability.
- `docs/session-handoff.md` records current Core branch status.

This pass removed Core-branch ownership of CLI/WebUI adapter documents and did
not change runtime behavior, SCPI/VISA handling, cleanup flow, JSON schema, or
public Core API exports.

## Full Core Cut

The Core branch now validates that the package is named
`keysight-logger-core`, uses package version `1.0.0`, has no console entry
point, exposes the maintained public API through `keysight_logger.core`, and
does not keep removed adapter runtime files or legacy top-level module shims.

No live hardware validation was run for this cut because no SCPI, VISA timeout,
trigger wait, cleanup order, or measurement behavior changed.
