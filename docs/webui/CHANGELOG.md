# Changelog

## v1.4.0

- WebUI now ships inside the single root `keysight-logger` distribution while
  preserving the `keysight_logger_webui` import package and WebUI console
  commands.
- Updated the WebUI `USER_GUIDE.md` for launcher-exe operator workflows and
  field guidance, while keeping engineering setup, API behavior, validation,
  build, and maintainer details in the WebUI README.

## webui-v1.2.2

- Unified WebUI software-command responses with the Core command envelope and
  refreshed current run status after accepted frontend requests.
- Bumped package metadata and fallback version to `keysight-logger-webui 1.2.2`
  for the patch release baseline without changing WebUI runtime behavior.

## webui-v1.2.1

- Bumped package metadata to `keysight-logger-webui 1.2.1` for the
  `webui-v1.2.1` tag target.
- Added the `keysight-logger-webui-launcher` GUI entry point for double-click
  local startup on `127.0.0.1:8767` with browser auto-open and Quit-driven
  server shutdown.
- Shared shutdown-friendly Uvicorn server creation between the terminal entry
  point and launcher without changing Core, SCPI, VISA, trigger, stop, or CSV
  behavior.
- Added `docs/USER_GUIDE.md` as the operator-facing WebUI guide.
- Removed the temporary legacy `keysight_logger.web_ui` compatibility shim so
  the workspace keeps the Core/CLI/WebUI import boundaries clean.

## webui-v1.2.0

- Released the WebUI package from the unified monorepo layout after merging the
  Core, CLI, and WebUI product branches into `main` while preserving WebUI
  package boundaries.
- Updated the Core dependency range to `keysight-logger-core>=1.2.0,<1.3`.
- Bumped package metadata to `keysight-logger-webui 1.2.0`.

## webui-v1.1.0

- Added the WebUI Live data panel with latest sample, trend chart, statistics,
  recent-samples table, and selected-sample metadata while keeping acquisition,
  trigger, SCPI, VISA, CSV, and cleanup behavior routed through Core.
- Added Open CSV behavior for the latest completed run through the WebUI
  manager state, without accepting frontend-supplied file paths.
- Updated WebUI branch documentation so transient branch status is separated
  from the detailed WebUI operator and maintainer guide.
- Added a detailed WebUI operator and maintainer guide.
- Recorded current no-hardware release validation: JavaScript syntax check
  passed, focused WebUI/Core pytest passed with 74 tests and 123 subtests, and
  full pytest passed with 243 tests and 128 subtests.
- Bumped package metadata to `keysight-logger-webui 1.1.0` for the
  `webui-v1.1.0` tag.

## webui-v1.0.0

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
