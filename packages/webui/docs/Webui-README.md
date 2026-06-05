# Keysight Logger WebUI README

Updated: 2026-05-29

This document is the detailed operator and maintainer guide for the WebUI
adapter branch. It explains how to install, run, use, validate, and maintain the
local browser console for Keysight 34461A acquisition.

For release notes, use the package changelog. For Core API and ownership rules,
use the Core integration guide. Keep this guide focused on durable public
operator and maintainer behavior.

## Purpose

The WebUI adapter provides a local FastAPI and browser interface around the
shared Core runtime in `keysight_logger_core`.

The WebUI owns:

- Browser interface in `packages/webui/src/keysight_logger_webui/static/`.
- FastAPI route shape in `packages/webui/src/keysight_logger_webui/web_ui.py`.
- Browser-facing request and response serialization.
- Live data display state derived from Core sample events.
- Resource scanning display.
- Open CSV behavior.
- Start, Trigger, Stop, and status polling UI behavior.

Core owns:

- Request validation.
- Dry-run planning.
- Acquisition runtime.
- Trigger routing.
- Stop controller behavior.
- CSV writing.
- Measurement and instrument metadata.
- SCPI command generation and instrument I/O.
- Release-to-local, close, cleanup release, and control-plane shutdown order.

The WebUI must use Core public APIs instead of depending on CLI adapter code or
directly reaching into acquisition engine internals.

## Package And Entry Point

This branch packages the WebUI adapter as:

```text
keysight-logger-webui
```

The Windows console wrapper is:

```powershell
.\.venv\Scripts\keysight-logger-webui.exe
```

The Windows GUI launcher wrapper is:

```powershell
.\.venv\Scripts\keysight-logger-webui-launcher.exe
```

The default local server is:

```text
http://127.0.0.1:8767/
```

The server is a Uvicorn/FastAPI process. The terminal key `q` does not stop it.
Use `Ctrl+C`; if the terminal does not deliver SIGINT, stop the listening
`python.exe` process by PID.

## Install Or Refresh

From the repository root:

```powershell
uv pip install -e ".[dev]" --link-mode=copy
```

Check the wrapper:

```powershell
.\.venv\Scripts\keysight-logger-webui.exe --version
```

Expected package metadata version for this release branch:

```text
keysight-logger-webui 1.2.2
```

Start the server:

```powershell
.\.venv\Scripts\keysight-logger-webui.exe --port 8767
```

Or start the double-click launcher:

```powershell
.\.venv\Scripts\keysight-logger-webui-launcher.exe
```

The launcher defaults to `127.0.0.1:8767`, disables the port field while
`Use default port 8767` is selected, opens the browser after Start, and keeps
the window available so Quit can stop the local Uvicorn server.

Open:

```text
http://127.0.0.1:8767/
```

Optional host and port flags:

```powershell
.\.venv\Scripts\keysight-logger-webui.exe --host 127.0.0.1 --port 8767
```

Keep the default host as `127.0.0.1` unless there is a deliberate reason to
expose the server beyond the local machine.

## Browser Layout

The current WebUI layout is a direct acquisition console, not a landing page.

Main areas:

- Header: `Keysight Meters` and `Local acquisition console`.
- Resource row: `VISA resource`, `Live resource`, and `Scan Device`.
- Status strip: `State`, `Captured`, `Errors`, and `CSV`.
- Action buttons: `Start`, `Trigger`, `Stop`, and `Open CSV`.
- Collapsible setup panels for run configuration, measurement settings,
  trigger settings, Live data, and status details.
- Live data panel with latest value, sample time, trigger source, trend chart,
  statistics, recent sample table, and selected-sample metadata.

The UI intentionally has no frontend build step, Node package manager, external
CDN, or framework runtime. Static assets are plain HTML, CSS, and JavaScript.

## Basic Workflow

1. Start the WebUI server.
2. Open `http://127.0.0.1:8767/`.
3. Enter a VISA resource manually or click `Scan Device`.
4. Select measurement and trigger settings.
5. Keep low-risk defaults for first contact with a real instrument:
   Auto Range on, immediate trigger, and a small `max_samples` value.
6. Click `Start`.
7. Watch the status strip and Live data panel.
8. For manual software trigger modes, click `Trigger` when ready.
9. Click `Stop` to request a Core-routed stop.
10. After the run is inactive and a CSV exists, click `Open CSV`.

The WebUI allows only one active run per backend process.

## Resource Scanning

`Scan Device` calls:

```text
GET /api/resources?verify=true&live_only=true
```

The backend uses Core resource listing behavior. With verification enabled, it
opens each candidate resource and queries `*IDN?`. With `live_only=true`, it
returns only resources that respond as live devices.

Selecting a live resource copies it into the `VISA resource` input. The user can
still type a resource manually.

## Measurement Modes

Measurement options are loaded from Core through:

```text
GET /api/capabilities
```

Currently surfaced measurement modes include:

- `current-dc`
- `voltage-dc`
- `voltage-dc-ratio`
- `current-ac`
- `voltage-ac`
- `resistance-2w`
- `resistance-4w`

The frontend must not invent measurement options. It should populate choices,
defaults, ranges, NPLC options, AC bandwidth options, current terminal options,
and measurement-specific controls from `/api/capabilities`.

Measurement-specific UI behavior:

- NPLC appears only for supported measurements.
- AC measurements do not show NPLC.
- AC bandwidth appears only for AC current and AC voltage where supported.
- Current terminal selection appears only for current measurements where
  supported.
- DCV Input Z appears only for `voltage-dc`.
- VM Comp remains a measurement option where supported by Core.
- Auto Zero Once is available for supported DC/resistance measurements through
  Core capabilities.

## Trigger Modes

Trigger options are also loaded from `/api/capabilities`.

Currently surfaced trigger modes include:

- `immediate`
- `software`
- `external`
- `immediate-custom`
- `software-custom`
- `external-custom`

Simple immediate and software-triggered reads use Core's `READ?` path.
Hardware-triggered simple reads use Core's `FETC?` path after the trigger
adapter arms and completes measurement.

UI behavior:

- Non-custom trigger modes show `max_samples`.
- `software` mode can use an optional software timer.
- Manual software-triggered modes show the `Trigger` button.
- Custom trigger modes show trigger count, sample count, buffer drain size, and
  buffer overflow risk.
- External trigger modes show hardware slope, hardware delay, and trigger
  timeout.
- Hardware trigger timeout is a protective re-arm condition, not a capture
  error by itself.

The WebUI trigger button posts metadata to the backend. Empty trigger metadata
sends:

```json
{ "source": "web-ui" }
```

Non-empty metadata must be valid JSON and is merged into that default object.

## Start, Stop, And Cleanup

Start calls:

```text
POST /api/runs
```

The backend converts the browser payload into a Core `StartRequest`, validates
through Core, builds adapter-visible status, and starts Core
`run_start_session()` on a background worker.

Stop calls:

```text
POST /api/runs/current/stop
```

Stop is routed through the Core control plane. WebUI code must not directly
close VISA handles, call acquisition engine internals, or reorder cleanup.

Preserved cleanup order:

1. Wait for worker.
2. Release instrument to local.
3. Close instrument/session resources.
4. Cleanup release.
5. Stop the HTTP/control-plane path.

## Live Data

Live data and status updates are driven primarily by Server-Sent Events (SSE):

```text
GET /api/runs/current/events
```

This returns a `text/event-stream` with `run-status` events containing a snapshot of the current status.
If the SSE connection fails, the frontend falls back automatically to standard polling:

```text
GET /api/runs/current
```

The status response includes Live data fields owned by the WebUI:

- `latest_sample`
- `recent_samples`
- `sample_capacity`

The sample window is bounded to the latest 5000 samples.

Sample fields include:

- `sequence`
- `timestamp_utc_plus_8`
- `measurement_type`
- `value`
- `unit`
- `trigger_id`
- `trigger_source`
- `trigger_metadata`
- `measurement_metadata`
- `resource_id`
- `status`

Live data is derived from Core `sample` events emitted by `run_start_session()`.
The WebUI must not perform extra VISA reads or read the CSV file to update the
live panel.

Stopped runs keep the latest sample window for operator review. Starting a new
run creates a fresh sample window.

The browser-side trend chart keeps the first numeric sample in a run as the
baseline and rescales on every render so the largest visible deviation maps to
four grid steps from the center line. This affects only chart display, not raw
sample values, statistics, CSV output, or API sample payloads.

## CSV Output, Select, And Open CSV

The run payload can include an optional `csv` path. If omitted, Core/default
behavior chooses the CSV output path.

The `CSV path` field also has a `Select` button. It calls:

```text
POST /api/csv/select-folder
```

Backend behavior:

- Opens a folder picker on the machine running the WebUI backend.
- On selection, returns:

```json
{
  "selected": true,
  "folder_path": "C:\\path\\to\\folder",
  "csv_path": "C:\\path\\to\\folder\\2026-06-01-14-30-05.csv"
}
```

- On cancel, returns:

```json
{ "selected": false, "folder_path": null, "csv_path": null }
```

- Returns `503` if the folder picker is unavailable.

Frontend behavior:

- A selected folder fills the existing `CSV path` input with the returned
  timestamped `.csv` path.
- Operators can still manually edit or clear the CSV path.
- `Start` uses the input value at the moment it is clicked.

The Open CSV button calls:

```text
POST /api/runs/current/open-csv
```

Backend behavior:

- Opens only the current or latest completed run CSV from manager state.
- Does not accept a frontend-supplied file path.
- Returns `409` with `run is still active` while a run is active.
- Returns `409` with `no completed CSV available` if no completed CSV path is
  available.
- Returns `404` with `CSV file not found` if the recorded CSV path is missing.
- On success, uses the Windows default app opener and returns:

```json
{ "opened": true, "csv_path": "..." }
```

Frontend behavior:

- Disabled by default.
- Disabled while a run is active.
- Enabled when the run is inactive and `csv_path` is present.
- Appends success and failure messages to the Status log.

## HTTP API Summary

The browser-facing API surface is:

- `GET /`: serves `index.html`.
- `GET /api/capabilities`: returns Core-backed measurement and trigger
  capabilities.
- `GET /api/resources?verify=true&live_only=true`: scans VISA resources.
- `POST /api/runs`: validates and starts a run.
- `GET /api/runs/current`: returns current or latest run status.
- `GET /api/runs/current/events`: returns Server-Sent Events (SSE) stream of run status changes.
- `POST /api/runs/current/command`: queues a software trigger for supported
  modes.
- `POST /api/runs/current/stop`: requests stop through the Core control plane.
- `POST /api/runs/current/open-csv`: opens the latest completed CSV.
- `POST /api/csv/select-folder`: opens a local folder picker and returns a
  timestamped CSV path for the existing CSV input.

Do not rename, remove, or repurpose these endpoints without updating frontend
code, tests, and documentation together.

## Frontend Payload Fields

Important fields sent by the WebUI include:

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
- `ac_bandwidth_hz`
- `current_terminal`

Hidden controls must be disabled so stale values are not submitted from inactive
modes.

## Safety Rules

Treat all instrument-affecting changes as high risk.

Do not change any of the following without explicit user approval:

- SCPI commands or command ordering.
- VISA timeout behavior.
- Trigger wait strategy.
- `TRIG:DEL`.
- NPLC behavior.
- Auto Zero behavior.
- Auto Range behavior.
- VM Comp behavior.
- DCV Input Z behavior.
- Stop behavior.
- Release/local behavior.
- Cleanup order.
- Hardware trigger timeout handling.
- Whether hardware-triggered reads use `FETC?`.
- Whether software-triggered or immediate reads use `READ?`.

For first real-instrument smoke tests, use low-risk immediate mode, Auto Range
on, and a small bounded sample count.

## Development Boundaries

Preferred WebUI frontend files:

- `packages/webui/src/keysight_logger_webui/static/index.html`
- `packages/webui/src/keysight_logger_webui/static/styles.css`
- `packages/webui/src/keysight_logger_webui/static/app.js`

Backend adapter file:

- `packages/webui/src/keysight_logger_webui/web_ui.py`
- `packages/webui/src/keysight_logger_webui/launcher.py`

Tests:

- `tests/test_web_ui.py`
- `packages/webui/tests/test_launcher.py`
- Core contract and package boundary tests listed in the validation commands
  below.

Do not change package metadata in `pyproject.toml` without explicit user
approval. Package name, version, dependencies, console scripts, build system,
pytest/ruff/mypy configuration, and Core/CLI/WebUI ownership are product
boundary decisions.

## Validation

Run the narrowest relevant checks first.

For JavaScript syntax after editing `app.js`:

```powershell
node --check packages\webui\src\keysight_logger_webui\static\app.js
```

Focused WebUI/Core no-hardware validation:

```powershell
.\.venv\Scripts\python.exe -m pytest packages/webui/tests/test_webui_package_metadata.py packages/webui/tests/test_web_ui.py packages/webui/tests/test_launcher.py -q -p no:cacheprovider
```

Build the optional local launcher exe with PyInstaller from an environment that
already has WebUI and Core installed. PyInstaller is a local release-build tool,
not a WebUI runtime dependency, so install it into the venv before rebuilding on
a fresh machine:

```powershell
uv pip install pyinstaller
```

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --onefile --windowed --name keysight-logger-webui-launcher --paths packages/webui/src --paths packages/core/src --add-data "packages/webui/src/keysight_logger_webui/static;keysight_logger_webui/static" packages/webui/src/keysight_logger_webui/launcher.py
```

Broader no-hardware validation when practical:

```powershell
uv run pytest tests -q -p no:cacheprovider
```

Live validation requires an operator-provided VISA resource. Start with a
low-risk immediate-mode smoke test, Auto Range on, and `max_samples=1` before
using trigger modes or longer acquisitions.

Full test runs may hit local Windows temp or pytest cache permission warnings.
Report those clearly and rely on focused tests plus real instrument validation
when the broader suite is blocked by environment permissions.

## Manual UI Smoke Checklist

For no-hardware UI smoke:

- The page loads at `http://127.0.0.1:8767/`.
- No browser console errors appear on first load.
- `Scan Device` updates the live resource selector or reports no live
  resources cleanly.
- Measurement changes update range unit, range choices, and NPLC visibility.
- `voltage-dc` shows DCV Input Z; other measurements hide it.
- AC measurements show AC bandwidth where supported and hide NPLC.
- Current measurements show current terminal where supported.
- Trigger mode changes show and hide only relevant fields.
- Trigger button appears only for manual software-triggered modes.
- Status log appends meaningful messages without spamming repeated poll states.
- `Show Details` toggles fatal error, cleanup status, and raw status.
- Live data renders latest value, chart, statistics, table, and selected-sample
  metadata after simulated or real samples are captured.
- Mobile width around 390 px has no text or control overlap.
- Desktop width around 1280 px remains dense but scannable.

For real-instrument smoke, do not run high-risk trigger experiments unless the
operator explicitly asks. Start with immediate mode, Auto Range on, and
`max_samples=1`.

## Troubleshooting

Wrapper is missing:

- Re-run `uv pip install -e ".[dev]" --link-mode=copy`.
- Confirm `.venv\Scripts\keysight-logger-webui.exe` exists.

Port is already in use:

- Start with another port, for example `--port 8768`.
- Or stop the existing listening process.

`q` does not stop the server:

- This is expected. Use `Ctrl+C`, or stop the listening `python.exe` by PID.

Scan finds no live resources:

- Confirm the instrument is connected and powered.
- Confirm VISA drivers are installed and the resource appears outside the app.
- Try entering the known VISA resource manually.
- Before live acquisition, start with a low-risk immediate-mode smoke test,
  Auto Range on, and `max_samples=1`.

Open CSV is disabled:

- Wait until the run is inactive.
- Confirm the run produced a `csv_path`.
- Refreshing the browser after a completed run can still show `Open CSV`
  because the backend preserves the latest completed CSV path.

Trigger button is hidden:

- The button is shown only for manual software-triggered modes:
  `software` without timer trigger, and `software-custom`.

Live panel has no samples:

- Confirm the run has captured samples.
- Confirm status polling is active.
- The panel uses Core sample events only; it does not query the instrument or
  parse CSV files independently.

## Documentation Map

- `README.md`: top-level quick start.
- `docs/USER_GUIDE.md`: operator-facing WebUI usage guide.
- `docs/Webui-README.md`: this detailed WebUI guide.
- `docs/web-ui-ai-change-rules.md`: rules for UI changes.
- `../CHANGELOG.md`: package release notes.
