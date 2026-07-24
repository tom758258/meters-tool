# Changelog

## Unreleased

- Limited live resource verification to opening the resource, querying `*IDN?`,
  and closing the session without acquisition cleanup commands.

## v2.0.0

v2.0.0 ships the breaking CLI command and import renames as part of the first
public Meters Tool release. Shared package metadata is now `2.0.0`, without
compatibility shims for the old names.

- Renamed the CLI command from `keysight-logger` to `meters-tool` and the CLI
  import package from `keysight_logger_cli` to `meters_tool_cli`.
- Bumped CLI-visible metadata to `2.0.0` through the shared distribution
  version plumbing.
- Added `--instrument-model` as an alias for `--model` and `--backend` as an
  alias for `--visa-library`; live model selection is an expected `*IDN?`
  match rather than a capability override.
- Applied the Core-owned exact connection, measurement, and trigger-mode
  support gate to live CLI starts, including product rejection of pending or
  unsupported scopes.
- Extended the preflight, live, and release wrappers for both 34460A and
  34461A targets, explicit backend forwarding, plan-only release gates, and
  validation-only execution of registered pending scopes. The live wrapper
  accepts `-VisaLibrary`, `-visa-library`, and `-Backend`.
- Recorded reviewed 34461A USB/system-VISA, LAN/system-VISA, and optional
  LAN/pyvisa-py support plus reviewed 34460A USB/system-VISA support. Normal CLI
  Product mode now accepts 34460A USB/system-VISA DCV Ratio after an explicit
  promotion based on separate bounded evidence; the existing 12-case wrapper
  full suite did not include Ratio. 34460A LAN scopes remain pending and
  product-closed.
- Refreshed English CLI documentation to describe `--model` as an expected IDN
  match for live starts and to keep dry-run/simulator examples tied to explicit
  deterministic simulator resources.
- Updated the release-skill simulator helper examples to use a version-neutral
  executable name.
- Split parser and client-command helpers and shared the PowerShell validation
  helpers while preserving JSON/JSONL schemas, report schemas, process
  lifecycle, and exit-code behavior.
- Finalized release metadata and notes without changing CLI runtime behavior.

## v1.5.0

- Added `frequency` and `period` CLI measurements with voltage range, AC filter,
  gate-time, and Frequency timeout arguments plus dry-run, simulator, CSV, and
  JSONL support.
- Added the `frequency-period` live suite, per-command SCPI diagnostics, and
  Frequency/Period coverage in the `full` live suite.
- Kept Frequency timeout control while rejecting Period timeout arguments
  before VISA I/O.
- Split parser construction and worker client commands into focused internal
  modules while preserving the `keysight-logger` entry point, arguments,
  output contracts, and exit-code behavior.
- Preserved direct `cli.py` execution for PyInstaller standalone builds after
  the internal module split.
- Shared PowerShell validation helpers across preflight, live, release, and
  release-build scripts without changing report schemas or artifact locations.
- Updated the release check to derive its default target from package metadata
  and reject an explicitly mismatched release version.

## v1.4.0

- CLI now ships inside the single root `keysight-logger` distribution while
  preserving the `keysight_logger_cli` import package and `keysight-logger`
  console command.
- Added an operator-facing CLI `USER_GUIDE.md` for executable-based workflows,
  while keeping detailed command reference, validation, JSON/JSONL, automation,
  and maintainer material in the CLI README.

## v1.3.2

- Updated `send-command` for runtime contract `v1.6`: shared pre-send command
  validation, complete arguments envelopes, response parsing, identity echo,
  and HTTP-specific exit codes.
- Added a packaged fallback version so PyInstaller-built CLI executables can
  answer `--version` when distribution metadata and local `pyproject.toml` are
  unavailable.
- Documented the optional standalone `dist\keysight-logger.exe` PyInstaller
  build and no-hardware smoke checks.
- Updated package metadata and wrapper report expectations to version `1.3.2`.

## v1.3.1

- Released the CLI package from the unified monorepo layout after merging the
  Core, CLI, and WebUI product branches into `main` while preserving package
  boundaries.
- Recorded full monorepo validation, full CLI live validation on a Keysight
  34461A, and release-wrapper validation for the package-separated layout.
- Updated the Core dependency range to `keysight-logger-core>=1.2.0,<1.3`.
- Updated package metadata to version `1.3.1`.

## v1.2.1

- Added CLI contract `v1.5` additive soft-client diagnostics, subprocess
  orchestrator workflow docs, simulator worker subprocess coverage, and
  wrapper `wait-ready` / `status` gates before software trigger calls.
- Added release-oriented no-hardware validation reporting through
  `scripts/release-cli-check.ps1` plus richer wrapper report metadata.
- Added Core/CLI boundary guards that prevent legacy root-level Core shim
  modules and CLI-only concerns from returning to Core.
- Removed legacy root-level Core module compatibility shims such as
  `keysight_logger.measurement` and `keysight_logger.instrument`. Python
  integrations should use `keysight_logger_core` or `keysight_logger_core.*`;
  CLI command behavior is unchanged.
- Updated package metadata to version `1.2.1`.

## v1.2.0

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

## v1.1.8

- Recorded the CLI branch merge-base baseline from Core v1.0.0 while preserving
  the CLI file tree and command-line behavior.
- Kept the CLI distribution as `keysight-logger` with the `keysight-logger`
  console script, adapter-owned JSON/JSONL contracts, wrapper scripts, and
  CLI-specific tests.
- Removed the retired `--enable-hw-trigger` CLI compatibility flag. Use
  `--trigger-mode external` for simple external hardware-triggered runs.
- No SCPI command sequences, VISA timeout behavior, trigger wait strategy,
  measurement logic, stop flow, cleanup order, release/local behavior, NPLC,
  Auto Range/Zero, VM Comp behavior, or CLI JSON/JSONL schema changed.

## v1.1.7

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
- Documented USB, AC, live discovery, and LAN smoke-test guidance for
  operator-provided resources.
- Updated active docs to prefer the installed console script and document
  no-hardware validation plus local install troubleshooting.

## v1.1.6

- Released the current patch baseline for control-plane and discovery behavior.
- Documented JSONL `ready` events for non-dry-run workers and preserved
  summary-based wrapper completion checks.
- Added preflight coverage for `list-resources --dry-run --live-only --json`
  and its no-VISA-I/O discovery contract.
- Kept SCPI command sequences, VISA timeout behavior, trigger wait strategy,
  acquisition/read paths, stop flow, cleanup order, and measurement logic
  unchanged.

## v1.1.5

- Kept acquisition behavior unchanged while making successful
  `list-resources --verify` / `--live-only` checks run best-effort
  release-to-local before closing the verification session.
