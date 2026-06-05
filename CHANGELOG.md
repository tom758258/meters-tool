# Changelog

## Unreleased

No unreleased changes.

## webui-v1.1.0 - 2026-05-29

- Added the WebUI Live data panel with latest sample, trend chart, statistics,
  recent-samples table, and selected-sample metadata while keeping acquisition,
  trigger, SCPI, VISA, CSV, and cleanup behavior routed through Core.
- Added Open CSV behavior for the latest completed run through the WebUI
  manager state, without accepting frontend-supplied file paths.
- Updated WebUI branch documentation so `docs/web-ui-session-handoff.md` is the
  detailed WebUI status source and `docs/session-handoff.md` is only a thin
  branch-neutral handoff index.
- Added `docs/Webui-README.md` as the detailed WebUI operator and maintainer
  guide.
- Recorded current no-hardware release validation: JavaScript syntax check
  passed, focused WebUI/Core pytest passed with 74 tests and 123 subtests, and
  full pytest passed with 243 tests and 128 subtests.
- Bumped package metadata to `keysight-logger-webui 1.1.0` for the
  `webui-v1.1.0` tag.

## webui-v1.0.0 - 2026-05-26

- Migrated the Web UI adapter from the old CLI-backed runtime path to the
  independent Core `StartRequest` / `run_start_session()` architecture while
  preserving the existing browser endpoints and static UI.
- Updated WebUI package metadata to `keysight-logger-webui` and restored WebUI
  runtime/test dependencies in project metadata.
- Added the `keysight-logger-webui` console script and `--version` support for
  parity with uv-installed adapter workflows.
- Recorded WebUI/Core validation for release: JavaScript syntax check passed,
  focused pytest passed with 63 tests and 63 subtests, full pytest passed with
  213 tests and 68 subtests, and the uv-installed console wrapper reported
  `keysight-logger-webui 1.0.0`.
- User-reported WebUI real/manual smoke validation passed before tagging.

## v1.0.0-core - 2026-05-26

- Completed the Core/Cli separation on the Core branch by removing adapter
  runtime code, wrapper scripts, adapter-specific tests, and legacy top-level
  re-export shims.
- Renamed package metadata to `keysight-logger-core` and removed console
  script metadata while preserving the `keysight_logger.core` public import
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
