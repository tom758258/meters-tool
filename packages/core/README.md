# Keysight Logger Core

This package contains the Core public API and acquisition runtime contract used
by downstream adapters for Keysight 34461A integrations.

Core owns the shared request model, validation, dry-run planning, runtime
session orchestration, event/result types, control-plane interfaces, profile
metadata, and safety rules for the Keysight 34461A acquisition runtime.
Core v1.1.1 adds adapter-facing capability introspection and structured warning
details without changing SCPI, VISA timeout behavior, trigger wait strategy,
stop flow, cleanup order, or measurement behavior.

The maintained Python import boundary is `keysight_logger_core`. Adapter
branches own their command-line, web, wrapper, and serialization layers after
merging this Core package.

## Validation

No-hardware Core validation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_core_public_api.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py packages/core/tests/test_core_package_metadata.py packages/core/tests/test_core_docs_ownership.py -q -p no:cacheprovider
```

This Core cut changes only public Core API exports, docs, tests, validation
messages, simulator coverage, and package version metadata.

## Documentation

- [Core Integration](docs/integration.md)
- [Hardware Test Plan](docs/hardware-test-plan.md)
- [Supported Models](docs/supported-models.md)
- [Branch Handoff Index](docs/session-handoff.md)
- [Core Handoff](docs/session-handoff.md)
- [Validation History](docs/validation-history.md)
- [Project Plan](docs/project-plan.md)
- [Changelog](CHANGELOG.md)
