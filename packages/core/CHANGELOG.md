# Changelog

## Unreleased

## core-v1.2.0 - 2026-06-01

- Released the Core package from the unified monorepo layout after merging the
  Core, CLI, and WebUI product branches into `main` while preserving Core's
  public API and package boundary.
- Updated downstream CLI and WebUI package dependency ranges to require
  `keysight-logger-core>=1.2.0,<1.3`.
- Bumped `keysight-logger-core` package metadata from `1.1.1` to `1.2.0`.

## core-v1.1.1 - 2026-05-31

- Added public Core capability introspection through `get_core_capabilities()`,
  `CoreCapabilities`, and `MeasurementCapability`.
- Added structured buffer-overflow warning details through `CoreWarning` and
  `generate_buffer_overflow_warning_details()` while preserving the existing
  string warning helper.
- Added adapter-readable dry-run plan descriptions and option summaries without
  changing existing `StartPlan` fields or SCPI planning.
- Strengthened no-hardware validation, simulator, runner, CSV metadata, public
  API, docs ownership, and package metadata coverage.
- Bumped `keysight-logger-core` package metadata from `1.1.0` to `1.1.1`.

## v1.0.0-core - 2026-05-26

- Completed the Core/Cli separation on the Core branch by removing adapter
  runtime code, wrapper scripts, adapter-specific tests, and legacy top-level
  re-export shims.
- Renamed package metadata to `keysight-logger-core` and removed console
  script metadata while preserving the `keysight_logger_core` public import
  boundary.
- Removed the adapter measurement-name alias from Core measurement metadata.

## v1.1.7-cli

- Added an internal `InstrumentBackend` Protocol and start/acquisition-path
  factory for live VISA, simulator, and test backends.
- Completed the Core/CLI boundary cleanup baseline: Core start validation,
  dry-run planning, runtime orchestration, public integration exports, and
  measurement naming now avoid adapter-only CLI concepts while preserving
  compatibility output fields.
- Added root `keysight-logger --version`, parser/help coverage, and dry-run
  contract assertions for no-hardware CLI workflows.
- Added preflight `-ListTargets`, constrained `-OutputRoot`, and summary count
  reporting.
- Recorded completed USB hardware validation, AC real-signal sanity checks,
  live discovery checks, and LAN basic wrapper validation.
- Updated active docs to prefer the installed console script and document
  no-hardware validation plus local install troubleshooting.

## v1.1.6-cli

- Released the current patch baseline for control-plane and discovery behavior.
- Documented JSONL `ready` events for non-dry-run workers and preserved
  summary-based wrapper completion checks.
- Added preflight coverage for `list-resources --dry-run --live-only --json`
  and its no-VISA-I/O discovery contract.
- Kept SCPI command sequences, VISA timeout behavior, trigger wait strategy,
  acquisition/read paths, stop flow, cleanup order, and measurement logic
  unchanged.

## v1.1.5-cli

- Kept acquisition behavior unchanged while making successful
  `list-resources --verify` / `--live-only` checks run best-effort
  release-to-local before closing the verification session.
