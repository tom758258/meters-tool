# Changelog

Component release notes:

- [Core](docs/core/CHANGELOG.md)
- [CLI](docs/cli/CHANGELOG.md)
- [WebUI](docs/webui/CHANGELOG.md)

## v1.6.0

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
  feature. Missing, unknown, pending, or model-unsupported entries remain
  closed in normal product mode.
- Opened the reviewed 34461A USB/system-VISA, LAN/system-VISA, and optional
  CLI-only LAN/pyvisa-py scopes for their registered profile-supported
  workflows, including external trigger support where applicable.
- Opened the reviewed 34460A USB/system-VISA scope for its suite-covered
  profile-supported workflows. DCV Ratio remains feature-pending, external
  triggers and 34461A-only limits remain unsupported, and the 34460A
  LAN/system-VISA and LAN/pyvisa-py scopes remain pending future validation.

### Adapters, validation, and maintenance

- Added `--backend` as an alias for the CLI `--visa-library` option and allowed
  the live validation wrapper to accept `-VisaLibrary`, `-visa-library`, or
  `-Backend` while continuing to record the effective backend scope.
- Added WebUI support-status UX driven by Core capabilities, including the
  auto-detect fallback view, expected-model guidance, exact support status,
  open workflows, limits, and pending scopes. The WebUI continues to use the
  system VISA runtime and does not expose the optional CLI backend selector.
- Extended the no-hardware and live validation harnesses for both model
  targets, explicit backend forwarding, plan-only gates, and validation-only
  execution of registered pending scopes without promoting product support.
- Split and streamlined CLI parser/client helpers, WebUI payload helpers, and
  shared PowerShell validation helpers while preserving public CLI, HTTP, and
  report contracts.
- Updated development checks to Ruff `0.15.20` or newer and `httpx2`, and
  layered CI into Ruff, Linux and Windows Python matrices, and a dedicated
  Windows wrapper-contract job.

### Release preparation

- Bumped the single `meters-tool` distribution version to `1.6.0` across
  package metadata, fallback version plumbing, lock metadata, and version
  tests.
- Refreshed English Core, CLI, and WebUI documentation to describe expected
  model / IDN-match behavior consistently for live starts and deterministic
  simulator resources.
- Updated the bundled Codex skill simulator helper and examples so no-hardware
  workflows stay tied to explicit `SIM::34460A` or `SIM::34461A` resources.
- The final release-preparation change updates release notes and artifacts only;
  it does not change Core, CLI, WebUI, SCPI, VISA, trigger, or cleanup runtime
  behavior.

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
