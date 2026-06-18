# Web UI Change Rules

This document is the working contract for Web UI polish and reorganization
work. It exists to let UI work move quickly without damaging the measurement,
trigger, VISA, or cleanup behavior underneath.

Read this file before changing code. Also read `AGENTS.md` and the current
task context.

## Goal

Improve the browser UI only:

- Make the existing Web UI clearer, denser, more polished, or easier to use.
- Preserve the current instrument behavior and API contracts.
- Leave backend, SCPI, trigger, acquisition, storage, and cleanup behavior
  untouched unless the user explicitly asks for a backend change and confirms
  the risk.

Assume the Keysight 34461A is real hardware. A UI mistake can start the wrong
measurement, arm the wrong trigger mode, or leave the instrument in a bad
state, so treat all non-visual changes as high risk.

## Files You May Change For UI Polish

Preferred editable files:

- `src/keysight_logger_webui/static/index.html`
- `src/keysight_logger_webui/static/styles.css`
- `src/keysight_logger_webui/static/app.js`

Optional, only when a stable UI contract changes or a new public behavior needs
contract coverage:

- `tests/webui/test_web_ui.py`

Optional documentation updates:

- `docs/web-ui-change-rules.md`, only when the UI contract itself changes or
  this document becomes stale.

Keep edits surgical. Do not touch unrelated files.

## Files And Behavior You Must Not Change

Do not change these files for a visual UI task:

- `src/keysight_logger_core/acquisition.py`
- `src/keysight_logger_cli/cli.py`
- `src/keysight_logger_core/instrument.py`
- `src/keysight_logger_core/measurement.py`
- `src/keysight_logger_core/models.py`
- `src/keysight_logger_core/storage.py`
- `src/keysight_logger_core/command.py`
- Backend behavior in `src/keysight_logger_webui/web_ui.py`

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

Runtime entry point:

```powershell
.\.venv\Scripts\keysight-logger-webui.exe --port 8767
```

Local URL:

```text
http://127.0.0.1:8767/
```

The Web UI is intentionally simple:

- Backend: FastAPI/Uvicorn in `src/keysight_logger_webui/web_ui.py`.
- Frontend: static HTML/CSS/JavaScript in `src/keysight_logger_webui/static/`.
- No Node build step.
- No frontend package manager.
- No external CDN dependency.
- No framework migration unless explicitly approved by the user.

## API Contract To Preserve

Do not rename, remove, or repurpose these endpoints:

- `GET /`
- `GET /api/capabilities`
- `GET /api/resources?verify=true&live_only=true`
- `POST /api/runs`
- `GET /api/runs/current`
- `POST /api/runs/current/command`
- `POST /api/runs/current/stop`

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
root [Testing Guidelines](../../../docs/testing-guidelines.md).

Important IDs:

- `run-form`
- `refresh-resources`
- `start-run`
- `trigger-run`
- `stop-run`
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
- `measurement`
- `measurement-range`
- `range-unit`
- `range-suffix`
- `nplc-field`
- `nplc`
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

Important UI scoping attributes:

- `data-mode-scope="simple"`
- `data-mode-scope="software"`
- `data-mode-scope="custom"`
- `data-mode-scope="hardware"`
- `data-mode-scope="software-trigger"`
- `data-mode-scope="trigger-timeout"`
- `data-measurement-scope="voltage-dc"`

Keep `.is-hidden` behavior available. Hidden controls must be disabled so stale
values are not submitted from inactive modes.

## Behavior That Must Stay True

The UI may look different, but these behaviors must remain true:

- Start refuses to run until a VISA resource is entered or selected.
- Scan Device calls `/api/resources?verify=true&live_only=true`.
- Selecting a live resource copies it into the VISA resource input.
- Measurement options are populated from `/api/capabilities`.
- Range choices are populated from the selected measurement definition.
- NPLC choices are populated from the selected measurement definition.
- NPLC is hidden/disabled when unsupported.
- DCV Input Z appears only for `voltage-dc`.
- AC measurements do not show NPLC.
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
- Live data and status updates are driven by Server-Sent Events (SSE) via `GET /api/runs/current/events` as the primary mechanism, falling back to polling `GET /api/runs/current` every 1s if the SSE connection is lost or unavailable.
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
.\.venv\Scripts\python.exe -m pytest tests/webui/test_web_ui.py -q -p no:cacheprovider
```

If `app.js` changed, also run:

```powershell
node --check src\keysight_logger_webui\static\app.js
```

When practical, run broader smoke tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/webui/test_web_ui.py tests/core/test_capabilities.py tests/core/test_measurement.py -q -p no:cacheprovider
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
