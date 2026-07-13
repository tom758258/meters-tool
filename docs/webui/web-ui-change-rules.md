# Web UI Change Rules

This document is the maintainer and agent-facing working contract for Web UI
polish and reorganization work. It is not an operator guide. It exists to let
UI work move quickly without damaging the measurement, trigger, VISA, or
cleanup behavior underneath.

Read this file before changing code. Also read `AGENTS.md` and the current
task context.

## Goal

Improve the browser UI only:

- Make the existing Web UI clearer, denser, more polished, or easier to use.
- Preserve the current instrument behavior and API contracts.
- Leave backend, SCPI, trigger, acquisition, storage, and cleanup behavior
  untouched unless the user explicitly asks for a backend change and confirms
  the risk.

Assume a supported digital multimeter is connected as real hardware. A UI
mistake can start the wrong measurement, arm the wrong trigger mode, or leave
the instrument in a bad state, so treat all non-visual changes as high risk.

## Files You May Change For UI Polish

Preferred editable files:

- `src/meters_tool_webui/static/index.html`
- `src/meters_tool_webui/static/styles.css`
- `src/meters_tool_webui/static/*.js`

Optional, only when a stable UI contract changes or a new public behavior needs
contract coverage:

- `tests/webui/test_webui_api.py`
- `tests/webui/test_webui_static.py`

Optional documentation updates:

- `docs/webui/web-ui-change-rules.md`, only when the UI contract itself
  changes or this document becomes stale.

Keep edits surgical. Do not touch unrelated files.

## Files And Behavior You Must Not Change

Do not change these files for a visual UI task:

- `src/meters_tool_core/acquisition.py`
- `src/meters_tool_cli/cli.py`
- `src/meters_tool_core/instrument.py`
- `src/meters_tool_core/measurement.py`
- `src/meters_tool_core/models.py`
- `src/meters_tool_core/storage.py`
- `src/meters_tool_core/command.py`
- Backend behavior in `src/meters_tool_webui/web_ui.py`

Do not change any SCPI, VISA, measurement, trigger, timeout, or cleanup
behavior. Specifically do not change:

- SCPI commands or command ordering.
- VISA timeout behavior.
- Trigger wait strategy.
- `TRIG:DEL`, `NPLC`, Auto Zero, Auto Range, VM Comp, DCV Input Z behavior.
- Stop/release/local behavior.
- Hardware trigger timeout handling.
- Whether hardware-triggered reads use `FETC?`.
- Whether software-triggered reads use `READ?`.
- Cleanup order.
- The one-active-run-per-backend-process design.

If a UI idea seems to require any of the above, stop and write the requested
backend/API change as a proposal instead of implementing it.

## Current Web UI Shape

Developer runtime entry point:

```powershell
.\.venv\Scripts\meters-tool-webui.exe --port 8767
```

Operator releases normally start from the built launcher executable documented
in `USER_GUIDE.md`. Source-checkout and validation workflows belong in
`README.md`.

Local URL:

```text
http://127.0.0.1:8767/
```

The Web UI is intentionally simple:

- Backend: FastAPI/Uvicorn in `src/meters_tool_webui/web_ui.py`.
- Frontend: static HTML/CSS/JavaScript in `src/meters_tool_webui/static/`.
- No Node build step.
- No frontend package manager.
- No external CDN dependency.
- No framework migration unless explicitly approved by the user.

## Localization Boundary

Read the [WebUI Localization Contract](localization-contract.md) before any
localization change. Preserve element IDs, form names, canonical values, API
fields, and runtime schemas. Raw machine values drive comparison,
de-duplication, suppression, validation, and control logic; translations are
display-only, with English as the mandatory fallback.

Use one HTML page for all locales. Do not add a duplicate page per locale, an
external translation service, a CDN dependency, a frontend framework or build
system, or backend locale coupling. Browser locale state must not alter Core or
API behavior.

Support-summary semantic keys are additive presentation metadata. Preserve the
existing English `status_text`, `runtime_driver_note`, `open_workflows`,
`limits`, and `pending` fields as backward-compatible fallbacks. Semantic keys
must never authorize a workflow or affect support policy. Raw
`validation_status`, transport, backend, model, and profile identity remain
machine values. Do not add a backend locale input or return locale-dependent
support behavior.

P2.6 owns the active browser locale control. Keep the permanent top-right
globe-and-text button limited to `en` and `zh-TW`, with saved locale precedence,
browser detection, English fallback, and the `meters-tool.webui.locale` key.
Runtime switching must update presentation from cached browser state without a
reload, API request, polling/SSE restart, form reset, or active-run reset.
Preserve raw diagnostic text and all canonical form/runtime values. P2.7 owns
final translation-quality and cross-Part integration validation.

## API Contract To Preserve

Do not rename, remove, or repurpose these endpoints:

- `GET /`
- `GET /api/capabilities`
- `GET /api/resources?verify=true&live_only=true`
- `POST /api/runs`
- `GET /api/runs/current`
- `GET /api/runs/current/events`
- `POST /api/runs/current/command`
- `POST /api/runs/current/stop`
- `POST /api/runs/current/open-csv`
- `POST /api/csv/select-folder`

Do not change request payload names in `app.js` unless the backend and tests
are intentionally changed by a separate approved backend task.

`GET /api/runs/current` also carries WebUI-owned Live data display fields:

- `latest_sample`
- `recent_samples`
- `sample_capacity`

Do not remove or rename those fields without updating the Live data panel,
tests, and relevant WebUI docs. They are derived from Core `sample` events and
must not trigger extra VISA reads.

Important payload fields currently sent by the UI include:

- `resource`
- `instrument_model`
- `csv`
- `timeout_ms`
- `trigger_timeout_ms`
- `trigger_mode`
- `measurement`
- `nplc`
- `auto_zero`
- `auto_range`
- `measurement_range`
- `dcv_input_impedance`
- `vm_comp_slope`
- `ac_bandwidth_hz`
- `gate_time_s`
- `freq_period_timeout`
- `current_terminal`
- `max_samples`
- `timer_interval_s`
- `trigger_count`
- `sample_count`
- `buffer_drain_size`
- `allow_buffer_overflow_risk`
- `hw_trigger_slope`
- `hw_trigger_delay_s`
- `sw_min_interval_ms`
- `sw_queue_max`

The Web Trigger button sends a separate JSON object to
`POST /api/runs/current/command`. Empty trigger metadata sends
`{ "source": "web-ui" }`; non-empty metadata must remain a JSON object and is
merged into that default object.

The command endpoint uses the Core command response envelope and must not use
FastAPI's `{"detail": ...}` wrapper for command validation or admission
failures. After `202`, the frontend fetches current run status separately.

The UI must continue to use `/api/capabilities` as the source of truth for
measurement options, range options, NPLC options, defaults, and trigger modes.
Do not invent measurement or trigger options in the frontend.

## DOM And Form Contract To Preserve

You may reorganize layout and visual grouping, but preserve functional IDs,
`name` attributes, and scope attributes unless the stable UI contract changes.
Only update source-string/static tests for those stable contracts; do not lock
CSS colors, layout measurements, helper function names, local JavaScript
variable names, or panel copy as a substitute for behavioral coverage. See the
root [Testing Guidelines](../testing-guidelines.md).

Important IDs:

- `run-form`
- `refresh-resources`
- `select-csv-folder`
- `start-run`
- `trigger-run`
- `stop-run`
- `open-csv`
- `status-state`
- `status-captured`
- `status-errors`
- `status-csv`
- `latest-status`
- `toggle-status-details`
- `status-details`
- `fatal-error`
- `cleanup-status`
- `raw-status`
- `resource`
- `resource-select`
- `instrument-model`
- `measurement`
- `measurement-range`
- `range-unit`
- `range-suffix`
- `nplc-field`
- `nplc`
- `ac-bandwidth-container`
- `ac-bandwidth`
- `gate-time-container`
- `gate-time`
- `freq-period-timeout-container`
- `freq-period-timeout`
- `current-terminal-container`
- `current-terminal`
- `trigger-mode`
- `timer-trigger-checkbox`
- `sw-min-interval-container`
- `sw-queue-max-container`
- `timer-interval-container`
- `trigger-metadata-container`
- `trigger-metadata`
- `trigger-options-panel`
- `live-data-summary`
- `live-data-run`
- `live-latest-value`
- `live-latest-meta`
- `live-latest-time`
- `live-latest-trigger`
- `live-trend-chart`
- `live-chart-empty`
- `live-samples-body`
- `live-selected-sample`
- `live-sample-details`
- `toggle-live-chart`
- `live-chart-shell`
- `toggle-live-stats`
- `live-stats-grid`
- `toggle-live-samples`
- `live-table-wrap`
- `live-sample-metadata`
- `close-live-sample-details`

Important UI scoping attributes:

- `data-mode-scope="simple"`
- `data-mode-scope="software"`
- `data-mode-scope="custom"`
- `data-mode-scope="hardware"`
- `data-mode-scope="software-trigger"`
- `data-mode-scope="trigger-timeout"`
- `data-measurement-scope="voltage-dc,voltage-dc-ratio"`

Keep `.is-hidden` behavior available. Hidden controls must be disabled so stale
values are not submitted from inactive modes.

## Behavior That Must Stay True

The UI may look different, but these behaviors must remain true:

- Start refuses to run until a VISA resource is entered or selected.
- Scan Device calls `/api/resources?verify=true&live_only=true`.
- Selecting a live resource copies it into the VISA resource input.
- Measurement options are populated from `/api/capabilities`.
- The Expected model selector reloads `/api/capabilities?model=<model>` only
  for explicit 34460A/34461A choices; Auto sends no `instrument_model` and
  relies on backend Start IDN preflight.
- The selector wording stays `Expected model`, `Auto-detect`, `Require 34460A`,
  and `Require 34461A`.
- Scanned live resource metadata may reload capabilities while Auto is
  selected, but it must not overwrite an explicitly selected expected model.
- `/api/capabilities?model=34460A` must surface the limited 34460A profile:
  no external trigger modes, no current terminal choices, no 10 A current
  range, and a 1000-reading memory limit.
- Direct `POST /api/runs` must still be rejected through Core validation for
  unsupported 34460A combinations, even when frontend controls are bypassed.
- The selected Expected model must remain an expected-model guard and display
  context only. Do not treat it as a live feature unlock or let it override the
  detected `*IDN?` profile.
- Disabled or hidden frontend controls are UX only. Core support policy and
  the `run_start_session()` runner final gate must remain the safety boundary
  for browser, WebUI backend, and direct API submissions.
- Do not expose a PyVISA backend selector in the WebUI without a future
  explicit product decision. Backend selection remains CLI-only.
- Do not promote LAN/TCPIP or pyvisa-py `@py` support from USB/system-VISA
  validation alone. They require separate operator-approved validation
  artifacts; the current promoted optional `@py` scope is 34461A LAN/TCPIP and
  remains CLI-only.
- Range choices are populated from the selected measurement definition.
- NPLC choices are populated from the selected measurement definition.
- NPLC is hidden/disabled when unsupported.
- DCV Input Z appears only for `voltage-dc`.
- AC, Frequency, and Period measurements do not show NPLC.
- AC measurements show AC filter where supported.
- Frequency and Period show AC Filter and Gate Time from `/api/capabilities`.
  Frequency also shows Timeout. Period and other measurements hide and disable
  Timeout.
- Current measurements show current terminal where supported.
- Non-custom trigger modes show `max_samples`.
- `software` mode shows `timer_interval_s` only when Timer trigger is checked.
- Custom trigger modes show trigger count, sample count, buffer drain size,
  and buffer overflow risk.
- External trigger modes show hardware slope and delay.
- Software-triggered manual modes show software minimum interval, software queue
  max, and trigger metadata. These controls are hidden/disabled while the
  software timer is enabled.
- The Trigger button appears only for manual software-triggered modes:
  `software` without Timer trigger, and `software-custom`.
- Stop calls `POST /api/runs/current/stop`.
- Open CSV calls `POST /api/runs/current/open-csv` and must use the backend's
  current or latest completed CSV path, not a frontend-supplied path.
- Select CSV folder calls `POST /api/csv/select-folder` and fills the existing
  CSV input with the returned timestamped path when a folder is selected.
- Live data and status updates are driven by Server-Sent Events (SSE) via
  `GET /api/runs/current/events` as the primary mechanism, falling back to
  polling `GET /api/runs/current` every 1s if the SSE connection is lost or
  unavailable.
- The Status panel keeps a five-line terminal-style log. It starts blank, adds
  frontend operation messages and changed backend `latest_status` values, and
  does not spam identical poll results or multiple SSE fallback messages.
- Fatal error, cleanup status, and raw status remain available in the
  `Show Details` / `Hide Details` collapsible area.
- Live data renders from the SSE stream snapshots (which share the same JSON shape as `GET /api/runs/current`). It shows the
  latest sample, a browser-side trend chart, the latest 5000 samples, and
  selected-sample trigger/measurement metadata. It must not query the
  instrument or read the CSV to update the live view.
- A stopped run keeps its Live data sample window until the next Start creates
  a fresh run.
- Blankable input and textarea labels may show `(Optional)`. Do not mark fields
  optional if they are required in the current mode, such as VISA resource,
  Range when Auto Range is off, custom trigger count/sample count, or Timer
  interval when Timer trigger is checked.
- CLI compatibility-only controls remain omitted from the UI:
  `current_range`, `enable_hw_trigger`, and `sw_trigger_port`.

## Visual Design Boundaries

Allowed:

- Improve layout, grouping, spacing, colors, typography, responsive behavior,
  focus states, disabled states, and status readability.
- Reword visible labels when the meaning stays identical.
- Add static helper text only when it reduces operational ambiguity.
- Add purely client-side affordances such as tabs, collapsible panels, badges,
  warnings, or summaries.
- Add small CSS-only motion if it does not distract from measurement safety.

Avoid:

- Marketing-style landing pages. The first screen should remain the usable
  control console.
- Decorative changes that make controls harder to scan.
- Hidden controls that still submit stale values.
- Extra network dependencies.
- A frontend build chain.
- Broad rewrites of `app.js` when a small change is enough.

For this project, clarity beats spectacle. The UI should feel like an
instrument control console: readable, calm, direct, and hard to misuse.

## When To Ask Before Continuing

Ask the user before implementing if the request requires:

- New backend endpoints.
- New payload fields.
- New measurement modes.
- New trigger modes.
- Any change to SCPI, VISA, trigger timing, timeout, cleanup, or stop behavior.
- A new dependency, frontend framework, build tool, icon package, charting
  library, or CDN.
- Removing an existing control.
- Changing what Start, Trigger, Stop, or Scan Device does.

If unsure whether a change is visual or behavioral, treat it as behavioral and
ask.

## Required Checks Before Completion

Run the narrowest relevant checks first:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/webui/test_webui_api.py tests/webui/test_webui_static.py -q -p no:cacheprovider
```

If any JavaScript module changed, also run:

```powershell
Get-ChildItem src\meters_tool_webui\static\*.js |
  ForEach-Object { node --check $_.FullName }
```

When practical, run broader smoke tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/webui/test_webui_api.py tests/webui/test_webui_static.py tests/core/test_capabilities.py tests/core/test_measurement.py -q -p no:cacheprovider
```

If the local environment lacks dependencies, say exactly what could not run and
why. Do not claim validation that did not happen.

## Manual UI Smoke Checklist

If you can run the app locally, verify:

- The page loads at `http://127.0.0.1:8767/`.
- No browser console errors appear on first load.
- Scan Device updates the live resource selector or shows no live resources.
- Changing measurement updates range unit, range options, and NPLC visibility.
- `voltage-dc` shows DCV Input Z; other measurements hide it.
- Frequency shows AC Filter, Gate Time, and Timeout with defaults `20 Hz`,
  `0.1 s`, and `Auto`. Period shows the same filter and gate time defaults but
  hides Timeout.
- Trigger mode changes show and hide only the relevant fields.
- Trigger button visibility matches manual software-triggered modes.
- Status log appends messages without layout breakage, and Show Details toggles
  the raw detail area open and closed.
- Live data latest value, chart, table, and sample details update after a
  simulated or real sample is captured.
- Optional markers appear only on blankable inputs/textarea fields.
- Mobile width around 390 px does not overlap text or controls.
- Desktop width around 1280 px remains scannable.

Do not perform real-instrument high-risk trigger experiments unless the user
explicitly asks. If an instrument is connected and the user requests a smoke
test, start with low-risk immediate mode, Auto Range on, `max_samples=1`.

## Completion Summary

When finished, provide this short summary:

- Files changed.
- What visual/user workflow problem was addressed.
- Any behavior intentionally preserved.
- Tests and checks run, with pass/fail results.
- Manual UI checks run, with viewport notes if relevant.
- Any skipped validation and why.
- Any risk or follow-up that requires backend approval.
