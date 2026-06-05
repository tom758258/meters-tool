# Keysight Logger Core

This package contains the Core public API and acquisition runtime contract used
by downstream adapters for Keysight 34461A integrations.

Core owns the shared request model, validation, dry-run planning, runtime
session orchestration, event/result types, control-plane interfaces, profile
metadata, and safety rules for the Keysight 34461A acquisition runtime.
Core v1.2.0 is the monorepo package baseline for downstream CLI and WebUI
adapters. It keeps the Core public API and runtime behavior stable while
aligning package metadata and adapter dependency ranges.

The maintained Python import boundary is `keysight_logger_core`. Adapter
branches own their command-line, web, wrapper, and serialization layers after
merging this Core package.

## Validation

No-hardware Core validation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_core_public_api.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py packages/core/tests/test_core_package_metadata.py packages/core/tests/test_core_docs_ownership.py -q -p no:cacheprovider
```

This Core cut changes only package metadata, downstream adapter dependency
ranges, docs, and tests.

## Documentation

- [Core Integration](docs/integration.md)
- [Hardware Test Plan](docs/hardware-test-plan.md)
- [Supported Models](docs/supported-models.md)
- [Branch Handoff Index](docs/session-handoff.md)
- [Core Handoff](docs/session-handoff.md)
- [Validation History](docs/validation-history.md)
- [Project Plan](docs/project-plan.md)
- [Changelog](CHANGELOG.md)
