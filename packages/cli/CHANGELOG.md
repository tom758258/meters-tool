# Changelog

## Unreleased

## cli-v1.3.1 - 2026-06-01

- Released the CLI package from the unified monorepo layout after merging the
  Core, CLI, and WebUI product branches into `main` while preserving package
  boundaries.
- Recorded full monorepo validation, full CLI live validation on a Keysight
  34461A, and release-wrapper validation for the package-separated layout.
- Updated the Core dependency range to `keysight-logger-core>=1.2.0,<1.3`.
- Updated package metadata to version `1.3.1`.

## cli-v1.2.1 - 2026-05-31

- Added CLI contract `v1.5` additive soft-client diagnostics, subprocess
  orchestrator workflow docs, simulator worker subprocess coverage, and
  wrapper `wait-ready` / `soft-status` gates before software trigger calls.
- Added release-oriented no-hardware validation reporting through
  `scripts/release-cli-check.ps1` plus richer wrapper report metadata.
- Added Core/CLI boundary guards that prevent legacy root-level Core shim
  modules and CLI-only concerns from returning to Core.
- Removed legacy root-level Core module compatibility shims such as
  `keysight_logger.measurement` and `keysight_logger.instrument`. Python
  integrations should use `keysight_logger_core` or `keysight_logger_core.*`;
  CLI command behavior is unchanged.
- Updated package metadata to version `1.2.1`.

## cli-v1.2.0 - 2026-05-29

- Released the CLI branch after merging `Core-v1.1.0` while preserving the
  `keysight-logger` package identity, console script, CLI JSON/JSONL contract,
  wrapper scripts, compatibility shims, and CLI-owned tests.
- Exposed Core v1.1.0 measurement capabilities through the CLI:
  `--measurement voltage-dc-ratio`, `--auto-zero once`, `--ac-bandwidth-hz`,
  and `--current-terminal`.
- Documented DCV Ratio `measurement_metadata`, CLI exit code meanings,
  agent/orchestrator JSONL parsing rules, and the worker flow:
  dry-run, simulate, live worker, wait for `ready`, `GET /status`,
  trigger/stop, then read JSONL/CSV/report artifacts.
- Strengthened CLI JSONL schema tests for `ready` fields, dry-run absence of
  runtime identifiers, consistent runtime `run_id`, sample
  `measurement_metadata`, summary counts, and structured JSON error exit-code
  behavior.
- Updated package metadata to version `1.2.0`.

## cli-v1.1.8 - 2026-05-26

- Recorded the `core-v1.0.0` merge-base baseline on the CLI branch while
  preserving the CLI file tree and command-line behavior.
- Kept the CLI distribution as `keysight-logger` with the `keysight-logger`
  console script, adapter-owned JSON/JSONL contracts, wrapper scripts, and
  CLI-specific tests.
- Removed the retired `--enable-hw-trigger` CLI compatibility flag. Use
  `--trigger-mode external` for simple external hardware-triggered runs.
- No SCPI command sequences, VISA timeout behavior, trigger wait strategy,
  measurement logic, stop flow, cleanup order, release/local behavior, NPLC,
  Auto Range/Zero, VM Comp behavior, or CLI JSON/JSONL schema changed.

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
