# Changelog

## Unreleased — target v2.0.0

These WebUI changes were not released as `v1.6.0`. The breaking WebUI import
and command renames are planned for `v2.0.0`. Shared package metadata
temporarily remains at the validated `1.6.0` pre-v2 baseline; the final
`2.0.0` bump has not occurred.

- Renamed the WebUI commands from `keysight-logger-webui` /
  `keysight-logger-webui-launcher` to `meters-tool-webui` /
  `meters-tool-webui-launcher`, and renamed the WebUI import package from
  `keysight_logger_webui` to `meters_tool_webui`.
- Prepared WebUI-visible metadata at the accepted `1.6.0` pre-v2 development
  baseline through the shared distribution version plumbing. The final public
  `2.0.0` version bump is intentionally deferred.
- Applied Core's live `*IDN?` profile selection and exact fail-closed support
  policy to WebUI starts. `Expected model` is an identity guard and does not
  override the detected instrument profile.
- Added capability-driven support UX showing the auto-detect fallback view,
  validation status, transport/backend scope, open workflows, model limits,
  and pending features.
- Reflected reviewed 34461A USB and LAN support and reviewed 34460A USB support
  while keeping 34460A LAN scopes, DCV Ratio, and model-unsupported features
  visibly closed. The WebUI continues to use the system VISA runtime.
- Refreshed English WebUI documentation and maintainer change rules so
  `Expected model`, `Auto-detect`, `Require 34460A`, and `Require 34461A`
  consistently describe Start-time IDN matching.
- Extracted WebUI request-payload mapping into focused helpers while preserving
  HTTP endpoints and request payload contracts.
- Added the dependency-free `en` / `zh-TW` browser locale runtime foundation
  with English fallback and safe named interpolation. P2.1 does not migrate
  browser prose or activate user-visible language switching, and API, Core,
  and runtime behavior remain unchanged.
- Moved static browser prose into matching `en` / `zh-TW` catalogs and bound it
  through a dependency-free DOM adapter. P2.2 still initializes in English and
  adds no language selector, browser detection, or persistence; API, Core, and
  runtime behavior remain unchanged.
- Moved dynamic run-form, measurement, trigger, validation, summary, subtitle,
  and rebuilt model-option presentation into matching English and Traditional
  Chinese catalogs. P2.3 still does not activate language switching; API,
  Core, support policy, SCPI, VISA, acquisition, schemas, and cleanup behavior
  are unchanged.
- Moved P2.4 app/resource, status/log, Live data, dynamic ARIA, and known
  browser-error presentation into matching English and Traditional Chinese
  catalogs. Raw status comparisons, suppression, de-duplication, unknown
  Core/backend diagnostics, status JSON, and sample metadata remain raw.
  Structured command-response `message` values now reach exact browser-error
  translations, while unknown `reason` values remain raw diagnostics and
  FastAPI `detail` remains first priority. Language switching is still
  inactive, and API endpoints, status codes, response schemas, Core, support
  policy, SCPI, VISA, trigger, acquisition, CSV/JSON/JSONL schemas, and cleanup
  behavior are unchanged.
- Added P2.5 support-summary semantic localization metadata alongside the
  existing English prose fields. The browser prefers recognized semantic keys
  and safely falls back to the corresponding prose when keys are missing,
  unknown, or positionally mismatched. Language switching remains inactive;
  API behavior, Core authority, support policy, instrument runtime, and
  schemas are unchanged.
- Activated P2.6 browser locale selection and English / Traditional Chinese
  switching with the permanent top-right globe-and-text button. Valid saved
  locale values use `meters-tool.webui.locale` and take precedence over
  browser detection; switching updates `<html lang>` without reload or runtime
  requests, preserves form/run/status/Live/chart/resource state, and keeps
  unknown diagnostics raw.
- Completed P2.7 final catalog-quality, terminology, browser-presentation,
  cross-Part integration, and operator-documentation review. The Traditional
  Chinese Auto range control now shows `自動量程（Auto range）`, while compact
  summaries remain `自動量程`; AC filter and Current terminal optional markers
  now share the inline label-title layout. API, Core, support-policy, runtime,
  and schema behavior remain unchanged.
- The final release-preparation change updates release notes only and does not
  change WebUI runtime behavior.

## v1.5.0

- Added Frequency and Period measurement controls driven by Core capabilities,
  including AC filter, gate time, Frequency timeout, defaults, payload fields,
  and raw `Hz` or `s` live-data units.
- Hid and disabled timeout for Period so the WebUI does not submit unsupported
  Period timeout requests.
- Split the frontend into native JavaScript modules for DOM, API, form,
  live-data, and status responsibilities while keeping `app.js` as the workflow
  entry point.
- Added aggregate JavaScript content hashing to the versioned static cachebuster
  so changes to any frontend module invalidate the browser cache.
- Moved SSE event generation into the run manager while preserving event names,
  IDs, payloads, keepalives, polling fallback, and API endpoints.

## v1.4.0

- WebUI now ships inside the single root `keysight-logger` distribution while
  preserving the `keysight_logger_webui` import package and WebUI console
  commands.
- Updated the WebUI `USER_GUIDE.md` for launcher-exe operator workflows and
  field guidance, while keeping engineering setup, API behavior, validation,
  build, and maintainer details in the WebUI README.

## v1.2.2

- Unified WebUI software-command responses with the Core command envelope and
  refreshed current run status after accepted frontend requests.
- Bumped package metadata and fallback version to `keysight-logger-webui 1.2.2`
  for the patch release baseline without changing WebUI runtime behavior.

## v1.2.1

- Bumped package metadata to `keysight-logger-webui 1.2.1` for the
  `v1.2.1` tag target.
- Added the `keysight-logger-webui-launcher` GUI entry point for double-click
  local startup on `127.0.0.1:8767` with browser auto-open and Quit-driven
  server shutdown.
- Shared shutdown-friendly Uvicorn server creation between the terminal entry
  point and launcher without changing Core, SCPI, VISA, trigger, stop, or CSV
  behavior.
- Added `docs/USER_GUIDE.md` as the operator-facing WebUI guide.
- Removed the temporary legacy `keysight_logger.web_ui` compatibility shim so
  the workspace keeps the Core/CLI/WebUI import boundaries clean.

## v1.2.0

- Released the WebUI package from the unified monorepo layout after merging the
  Core, CLI, and WebUI product branches into `main` while preserving WebUI
  package boundaries.
- Updated the Core dependency range to `keysight-logger-core>=1.2.0,<1.3`.
- Bumped package metadata to `keysight-logger-webui 1.2.0`.

## v1.1.0

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
  `v1.1.0` tag.

## v1.0.0

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
