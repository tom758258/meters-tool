# Changelog

Component release notes:

- [Core](docs/core/CHANGELOG.md)
- [CLI](docs/cli/CHANGELOG.md)
- [WebUI](docs/webui/CHANGELOG.md)

## v1.6.0

### Release cleanup

- Bumped the single `keysight-logger` distribution version to `1.6.0` across
  package metadata, fallback version plumbing, lock metadata, and version
  tests.
- Refreshed English Core, CLI, and WebUI documentation to describe expected
  model / IDN-match behavior consistently for live starts and deterministic
  simulator resources.
- Updated the bundled Codex skill simulator helper and examples so no-hardware
  workflows stay tied to explicit `SIM::34460A` or `SIM::34461A` resources.

### Runtime behavior

- No Core, CLI, WebUI, SCPI, VISA, trigger, cleanup, parser, profile, or WebUI
  runtime behavior changed in this cleanup.

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
