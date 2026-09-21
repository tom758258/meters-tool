# Changelog

## Unreleased

## v3.1.2

- Expands English and Traditional Chinese CLI and WebUI operator guidance for
  trigger workflows, custom and buffered acquisition, software trigger timing
  and metadata, and related measurement settings.
- Refreshes the bundled CLI and WebUI Help from the canonical operator guides
  and corrects the documented WebUI scope for DC voltage input impedance.

## v3.1.1

- Fixes piped JSONL event delivery by flushing CLI machine-output events to
  stdout immediately, ensuring readiness and other runtime events are visible
  to pipe-based clients without waiting for the process to exit.

## v3.1.0

- Adds the `meters-tool manifest --json` machine introspection command for
  discovering tool identity, version, and Worker protocol compatibility
  without opening VISA resources or starting a runtime session.
- Adds WebUI state indicators for WebUI health, command activity, and Live Data
  monitoring so users can distinguish ready, busy, error, waiting, live, and
  inactive states at a glance.
- Improves the WebUI appearance and language controls with clearly labeled
  Appearance and Language settings. The language control now displays the
  current locale while retaining immediate English / Traditional Chinese
  switching.
- Prevents stale WebUI pages and static assets from surviving an application
  update, so the browser reliably loads the current interface after upgrading.
- Adds a shared Meters application icon to the user-facing Windows Desktop,
  CLI, and WebUI Launcher executables.
- Adds bundled offline Help for CLI and WebUI/Desktop, including the CLI
  `user-guide` command and English / Traditional Chinese operator guides.

## v3.0.0

- Adds the Windows Electron Desktop and replaces separate Windows executable
  artifacts with one versioned Windows x64 ZIP containing the Desktop, CLI,
  and WebUI Launcher.
- Adds optional CSV output control to both CLI and WebUI while preserving CSV
  as the default.
- Adds persistent WebUI `System / Light / Dark` theme selection with matching
  Electron Desktop window theme synchronization.
- Adds WebUI `Real / Simulate / Dry-run` execution mode selection.
- Adds a Supported Devices modal in WebUI showing currently supported hardware
  models and connections.

## v2.0.0

This is the first public Meters Tool release after the breaking project
identity, distribution, import-package, and console-command rename. The old
names have no compatibility shims; Keysight profile names and runtime
contracts remain unchanged.

### Breaking changes

- Renamed the project identity from Keysight Logger / `keysight-logger` to
  Meters Tool / `meters-tool` in one breaking pass.
- Renamed the import packages to `meters_tool_core`, `meters_tool_cli`, and
  `meters_tool_webui` without compatibility shims for the old imports.
- Preserved Keysight hardware profile names, `keysight-34460a` /
  `keysight-34461a` validation targets, SCPI/VISA behavior, CSV schema,
  JSON/JSONL fields, WebUI endpoints, and the worker `service` value.

### Model profiles and live support policy

- Added distinct 34460A and 34461A Core profiles and made live starts select
  the runtime profile from `*IDN?`. An explicitly selected model is now an
  expected-model guard; a mismatch fails before setup SCPI instead of
  unlocking the selected profile's capabilities.
- Added a fail-closed live support policy that evaluates the exact model,
  transport/backend connection scope, measurement feature, and trigger-mode
  feature. Missing, unknown, unsupported, or model-mismatched entries remain
  closed in normal product mode.
- Opened the 34461A USB/system-VISA, LAN/system-VISA, and optional
  CLI-only LAN/pyvisa-py scopes for their registered profile-supported
  workflows, including external trigger support where applicable.
- Opened the 34460A USB/system-VISA scope for its profile-supported workflows,
  including DCV Ratio. External triggers and 34461A-only limits remain
  unsupported, and 34460A LAN/system-VISA and LAN/pyvisa-py scopes are not
  currently supported.
- Consolidated live-start resolution on the detected profile and recomputed
  trigger routing afterward so support validation and execution use the same
  live identity.

### Documentation and contracts

- Updated the copied Common contracts to the v2-only schema.
- Added the minimum Meters contract changes for schema-2 command envelopes
  and startup-bound expected/planning model identity while preserving existing
  Worker, CLI, orchestration, CSV, trigger, and cleanup details.
- Migrated the Meters Worker command/status runtime, CLI machine output and
  lifecycle clients, and browser software-trigger request to Common schema 2.
  Wrapper `report.json` schemas remain separately versioned at schema 1.

### CLI

- Limited live resource verification to opening the resource, querying
  `*IDN?`, and closing the session without acquisition cleanup commands.

### WebUI

- The Windows launcher now binds the first available loopback port from a
  bounded 100-port search, hands that same socket to Uvicorn, waits for the
  WebUI capabilities identity before opening the browser, and shows the manual
  port window only when automatic selection is exhausted.
- The launcher now exits only after active-run cleanup completes and rejects
  new runs after shutdown begins.
- Added a headless launcher self-test for required WebUI imports and packaged
  static resources.

### Adapters, validation, and maintenance

- Added `--instrument-model` as an alias for the CLI `--model` option.
- Added `--backend` as an alias for the CLI `--visa-library` option and allowed
  the live validation wrapper to accept `-VisaLibrary`, `-visa-library`, or
  `-Backend` while continuing to record the effective backend scope.
- Added WebUI support-status UX driven by Core capabilities, including the
  auto-detect fallback view, expected-model guidance, exact support status,
  open workflows, limits, and unsupported scopes. The WebUI continues to use the
  system VISA runtime and does not expose the optional CLI backend selector.
- Added the dependency-free WebUI locale runtime with English fallback, safe
  named interpolation, matching English and Traditional Chinese catalogs, and
  localized static and dynamic browser presentation. The initial catalog-backed
  presentation kept English as the startup locale; HTTP API, Core, and
  acquisition behavior remained unchanged.
- Added support-summary semantic localization metadata while preserving every
  existing English prose field as the browser fallback. The browser prefers
  recognized semantic keys and safely ignores missing, unknown, or mismatched
  list keys.
- Activated browser locale selection and English / Traditional Chinese
  switching through the permanent top-right globe button. Saved locale values
  take precedence over browser detection and use `meters-tool.webui.locale`;
  switching is immediate, state-preserving, and performs no page reload or
  runtime/API request. Unknown diagnostics remain raw, and Core, CLI, HTTP,
  SSE, instrument, and schema behavior remain unchanged.
- Completed English / Traditional Chinese catalog quality, terminology,
  browser-presentation, and operator-documentation review. The Traditional
  Chinese Auto range control now shows `自動量程（Auto range）`, while compact
  summaries remain concise; AC filter and Current terminal optional markers
  now use the shared inline label layout. Runtime, API, support-policy,
  instrument, and schema contracts remain unchanged.
- Split and streamlined CLI parser/client helpers, WebUI payload helpers, and
  shared PowerShell validation helpers while preserving public CLI, HTTP, and
  report contracts.
- Updated development checks to Ruff `0.15.20` or newer and `httpx2`, and
  layered CI into Ruff, Linux and Windows Python matrices, and a dedicated
  Windows wrapper-contract job.

### Packaging and release

- Added PyInstaller to the Windows development dependency set.
- Formal release acceptance now runs the complete no-hardware suite including
  wrapper tests, invokes the release build once, and validates the final wheel,
  sdist, standalone CLI and WebUI Launcher executables, and SHA-256 checksums.
  A passing run produces a directory ready for direct GitHub Release upload.
- Formal release acceptance now verifies that Git HEAD remains unchanged, and
  builds all four release artifacts from the same tracked source snapshot.
- Formal release acceptance now drains captured stdout and stderr concurrently
  to avoid pipe deadlock, shows per-command start/pass/fail progress, and keeps
  child-process output in run-directory artifacts. Its final live wrapper check
  remains `minimal + PlanOnly` and does not open VISA resources.

- Bumped the single `meters-tool` distribution version to `2.0.0` across
  package metadata, fallback version plumbing, lock metadata, version tests,
  and release-facing fixtures.
- Refreshed English Core, CLI, and WebUI documentation to describe expected
  model / IDN-match behavior consistently for live starts and deterministic
  simulator resources.
- Updated the bundled Codex skill simulator helper and examples so no-hardware
  workflows stay tied to explicit `SIM::34460A` or `SIM::34461A` resources.
- Finalized release metadata and notes without changing Core, CLI, WebUI,
  SCPI, VISA, trigger, or cleanup runtime behavior.

## v1.5.0

### Frequency and Period measurements

- Added Frequency and Period measurement support across Core, CLI, and WebUI,
  including capability discovery, validation, dry-run plans, simulator paths,
  CSV/JSONL output, and live display units.
- Added measurement-specific voltage ranges, `3`, `20`, and `200` Hz AC filter
  choices, and `0.01`, `0.1`, and `1` second gate-time choices.
- Added Frequency timeout control with `auto` and `1s` choices. Period exposes
  no timeout option and sends no timeout SCPI because the supported 34461A
  firmware rejects the corresponding Period header.
- Added bounded Frequency/Period live validation with per-command SCPI error
  diagnostics and included both measurements in the full live CLI suite.

### Internal maintenance

- Centralized package version fallback handling and WebUI static-module
  cachebusting.
- Split CLI parser/client helpers, WebUI frontend modules, Core request
  validation/mapping helpers, and software-trigger HTTP handling into focused
  internal units while preserving existing public commands and contracts.
- Simplified measurement SCPI configuration helpers without changing command
  ordering or established acquisition behavior.
- Deduplicated Core test fixtures and PowerShell validation/report helpers.
- Added UTF-8 without BOM guards and normalized the modified text files.

## v1.4.0

### Single distribution packaging

- Unified Core, CLI, and WebUI under one distribution, `keysight-logger` `1.4.0`.
- Moved import packages to root `src/`, tests to root `tests/`, component docs to root `docs/`, and release scripts to root `scripts/`.
- Preserved Python imports: `keysight_logger_core`, `keysight_logger_cli`, and `keysight_logger_webui`.
- Preserved console commands: `keysight-logger`, `keysight-logger-webui`, and `keysight-logger-webui-launcher`.
- Kept runtime behavior contracts unchanged; this migration changes distribution metadata, dependency declarations, build flow, docs, tests, and CI layout only.
- Finalized the CLI and WebUI operator guide split: `USER_GUIDE.md` files cover operator workflows, while README files retain engineering setup, reference, validation, and maintainer details.

## Historical component releases before v1.4.0

Before v1.4.0, Core, CLI, and WebUI were versioned and released independently.

### Core

#### Core v1.2.1

- Unified `/command` accepted, rejected, and validation responses under the
  common JSON envelope with safe `command` and `job_id` echoing.

#### Core v1.2.0

- Released Core from the unified monorepo layout after merging the product
  branches while preserving its public API and package boundary.

#### Core v1.1.1

- Added public capability introspection through `get_core_capabilities()`,
  `CoreCapabilities`, and `MeasurementCapability`.
- Added structured buffer-overflow warning details while preserving the
  existing string warning helper.
- Added adapter-readable dry-run plan descriptions and option summaries
  without changing existing `StartPlan` fields or SCPI planning.
- Strengthened no-hardware validation, simulator, runner, CSV metadata, public
  API, documentation ownership, and package metadata coverage.

#### Core v1.0.0

- Completed the Core/CLI separation by removing adapter runtime code, wrapper
  scripts, adapter-specific tests, and legacy top-level re-export shims.
- Renamed the package to `keysight-logger-core` and removed console script
  metadata while preserving the `keysight_logger_core` public import boundary.
- Removed the adapter measurement-name alias from Core measurement metadata.

### CLI

#### CLI v1.3.2

- Updated `send-command` for runtime contract v1.6 with shared pre-send
  validation, complete argument envelopes, response parsing, identity echo,
  and HTTP-specific exit codes.
- Added a packaged fallback version for PyInstaller executables when
  distribution metadata and the local `pyproject.toml` are unavailable.
- Documented the optional standalone `dist\keysight-logger.exe` build and
  no-hardware smoke checks.

#### CLI v1.3.1

- Released CLI from the unified monorepo layout while preserving package
  boundaries.
- Updated the Core dependency range to `keysight-logger-core>=1.2.0,<1.3`.

#### CLI v1.2.1

- Added CLI contract v1.5 soft-client diagnostics, subprocess orchestration
  documentation, simulator worker subprocess coverage, and wrapper
  `wait-ready` / `status` gates before software trigger calls.
- Added release-oriented no-hardware validation reporting and richer wrapper
  report metadata.
- Added Core/CLI boundary guards and removed legacy root-level Core import
  shims. Python integrations use `keysight_logger_core`; CLI behavior was
  unchanged.

#### CLI v1.2.0

- Released CLI after merging Core v1.1.0 while preserving its package identity,
  console script, JSON/JSONL contracts, wrapper scripts, compatibility shims,
  and CLI-owned tests.
- Exposed Core measurement capabilities through the CLI, including DCV Ratio,
  Auto Zero Once, AC bandwidth, and current-terminal selection.
- Expanded the documented JSONL schema, exit codes, orchestrator parsing rules,
  and worker lifecycle.

#### CLI v1.1.8

- Recorded the Core v1.0.0 merge baseline while preserving the CLI file tree,
  distribution, console script, adapter contracts, wrappers, and tests.
- Removed the retired `--enable-hw-trigger` compatibility flag in favor of
  `--trigger-mode external`.

#### CLI v1.1.7

- Added an internal instrument-backend protocol and factory for live VISA,
  simulator, and test backends.
- Completed the Core/CLI boundary cleanup while preserving compatibility output
  fields.
- Added root `keysight-logger --version`, parser/help coverage, and dry-run
  contract assertions.
- Added preflight target listing, constrained output-root handling, and summary
  count reporting.

#### CLI v1.1.6

- Documented JSONL `ready` events for non-dry-run workers and preserved
  summary-based wrapper completion checks.
- Added no-I/O preflight coverage for
  `list-resources --dry-run --live-only --json`.

#### CLI v1.1.5

- Made successful `list-resources --verify` and `--live-only` checks attempt a
  best-effort release to local before closing the verification session.

### WebUI

#### WebUI v1.2.2

- Unified WebUI software-command responses with the Core command envelope and
  refreshed current run status after accepted frontend requests.

#### WebUI v1.2.1

- Added the `keysight-logger-webui-launcher` GUI entry point for double-click
  local startup with browser auto-open and Quit-driven server shutdown.
- Shared shutdown-friendly Uvicorn server creation between the terminal entry
  point and launcher without changing instrument behavior.
- Added an operator-facing WebUI user guide and removed the temporary legacy
  `keysight_logger.web_ui` compatibility shim.

#### WebUI v1.2.0

- Released WebUI from the unified monorepo layout while preserving package
  boundaries.
- Updated the Core dependency range to `keysight-logger-core>=1.2.0,<1.3`.

#### WebUI v1.1.0

- Added the Live data panel with latest sample, trend chart, statistics,
  recent-samples table, and selected-sample metadata.
- Added Open CSV behavior for the latest completed run without accepting
  frontend-supplied file paths.
- Added a detailed WebUI operator and maintainer guide.

#### WebUI v1.0.0

- Migrated the WebUI adapter from the old CLI-backed runtime to the independent
  Core `StartRequest` / `run_start_session()` architecture while preserving
  browser endpoints and static UI.
- Established `keysight-logger-webui` package metadata, runtime/test
  dependencies, console script, and `--version` support.
