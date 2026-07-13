# Meters Tool WebUI README

This document is the WebUI behavior, API, validation, and maintainer guide for
the WebUI component. For normal operator workflows and field explanations, use
the [WebUI User Guide](USER_GUIDE.md).

For release notes, use the package changelog. For Core API and ownership rules,
use the Core integration guide. Keep this guide focused on durable public
WebUI behavior and maintainer boundaries.

The [WebUI Localization Contract](localization-contract.md) defines the v2
localization of browser presentation. P2.1 provides the dependency-free browser
i18n foundation; P2.2 through P2.5 cover static and dynamic form, app/resource,
status/log, Live data, ARIA, browser-error, and support-summary presentation.
P2.6 activates English / Traditional Chinese selection through the permanent
top-right globe-and-text button. A valid saved locale takes precedence over
browser detection and English fallback; manual choices use the
`meters-tool.webui.locale` storage key. Switching updates the page immediately
without reload or runtime/API requests and re-renders from cached state while
preserving form values, active runs, panels, status logs, Live samples, chart
settings, resource metadata, and support summaries. Unknown Core/backend/status
diagnostics, raw status JSON, sample metadata, and schemas remain raw. Core,
HTTP API endpoints and status codes, existing response fields, form values,
support policy, instrument runtime, and CSV/JSON/JSONL schemas remain
unchanged. P2.7 completes the final catalog-quality and terminology review,
cross-Part integration validation, operator documentation, and focused label
polish without changing those boundaries.

## Purpose

The WebUI adapter provides a local FastAPI and browser interface around the
shared Core runtime in `meters_tool_core`.

The WebUI owns:

- Browser interface in `src/meters_tool_webui/static/`.
- FastAPI route shape in `src/meters_tool_webui/web_ui.py`.
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

Core validates measurement requests and protects instrument-facing limits. The
WebUI user guide explains fields in UI terms; this README keeps WebUI behavior,
API, validation, and maintainer boundaries in one place.

## Package And Entry Point

The WebUI ships inside the single distribution:

```text
meters-tool
```

The Windows console wrapper is:

```powershell
.\.venv\Scripts\meters-tool-webui.exe
```

The Windows GUI launcher wrapper is:

```powershell
.\.venv\Scripts\meters-tool-webui-launcher.exe
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
uv pip install -e ".[all,dev]" --link-mode=copy
```

Check the wrapper:

```powershell
.\.venv\Scripts\meters-tool-webui.exe --version
```

Expected version format:

```text
meters-tool-webui <package-version>
```

Start the server:

```powershell
.\.venv\Scripts\meters-tool-webui.exe --port 8767
```

Or start the double-click launcher:

```powershell
.\.venv\Scripts\meters-tool-webui-launcher.exe
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
.\.venv\Scripts\meters-tool-webui.exe --host 127.0.0.1 --port 8767
```

Keep the default host as `127.0.0.1` unless there is a deliberate reason to
expose the server beyond the local machine.

## Browser Layout

The current WebUI layout is a direct acquisition console, not a landing page.

Main areas:

- Header: `Meters Tool` and `Local acquisition console`.
- Device / Resource row: `VISA resource`, `Live resource`, `Scan Device`, and a
  `Device options` gear for the `Expected model` selector and model support
  summary. The row starts expanded and can collapse to a resource/model
  summary.
- The Expected model selector defaults to `Auto-detect`, which uses the
  connected instrument IDN at Start. Explicit `Require 34460A` or
  `Require 34461A` choices still read IDN and start only when it matches. The
  detected IDN-selected profile remains the live runtime profile.
- The model support summary displays validation status, open workflow groups,
  model limits, and transport/backend scope status from `/api/capabilities`.
  This is operator-facing visibility only; Core still rejects unsupported
  direct backend submissions through the support policy and runner final gate.
- Status strip: `State`, `Captured`, `Errors`, and `CSV`.
- Action buttons: `Start`, `Trigger`, `Stop`, and `Open CSV`.
- Collapsible setup panels for device/resource setup, run configuration,
  measurement settings, trigger settings, Live data, and status details.
- Live data panel with latest value, sample time, trigger source, trend chart,
  statistics, recent sample table, and selected-sample metadata.

### Browser Language

The permanent globe-and-text button at the top right switches between English
and Traditional Chinese. Its destination label is `繁體中文` in English and
`English` in Traditional Chinese. On first load, the WebUI uses a valid saved
locale, then browser language detection, then English. Manual choices persist
under `meters-tool.webui.locale`; detected locales are not written
automatically. Switching changes `<html lang>` without reloading or calling a
runtime endpoint, and preserves the current form, active run, panel, status,
Live data, chart, resource, and support-summary state. Unknown diagnostics stay
raw.

P2.7 completes the English / Traditional Chinese presentation review. The
Traditional Chinese Measurement options control shows
`自動量程（Auto range）`; compact summaries continue to use `自動量程`. Optional
markers share the inline field-title layout, including AC filter and Current
terminal, and may wrap naturally only when the viewport is too narrow.

The UI intentionally has no frontend build step, Node package manager, external
CDN, or framework runtime. Static assets are plain HTML, CSS, and native
JavaScript modules.

## Basic Workflow

1. Start the WebUI server.
2. Open `http://127.0.0.1:8767/`.
3. Enter a VISA resource manually or click `Scan Device`.
4. Leave `Expected model` in `Device options` on Auto-detect unless you need to
   require 34460A or 34461A, then select measurement and trigger settings.
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

Verified scan results include nullable model metadata when the returned IDN
matches a supported Core profile. A 34460A IDN returns
`instrument_model: "34460A"` and `instrument_model_id:
"keysight-34460a"`; a 34461A IDN returns the corresponding `34461A` and
`keysight-34461a` values. The nested `matched_profile` includes `vendor`,
`model`, and `model_id`. Unknown or empty live IDNs remain in the resource list
with `instrument_model`, `instrument_model_id`, and `matched_profile` set to
null, so the backend never guesses a detected identity from the fallback
capability profile.

Selecting a live resource copies it into the `VISA resource` input. When the
scan inferred a supported model and `Expected model` remains Auto-detect, the
browser may reload `/api/capabilities?model=<model>` for display options, but it
leaves `Expected model` on Auto-detect. Start always performs a fresh backend
IDN preflight.

The user can still type a resource manually and can require a specific Expected
model from `Device options` after scanning.

The WebUI uses the default system VISA runtime through Core. It does not expose
a PyVISA backend selector in the browser. 34461A LAN/TCPIP is validated through
this default system VISA path. Use the CLI-only `--visa-library` advanced
option when optional pyvisa-py backend diagnostics are required; the validated
optional `@py` acquisition scope is 34461A LAN/TCPIP.

The WebUI does not expose validation mode. Pending transport/backend scopes and
pending measurement or trigger-mode features remain blocked for browser starts
until reviewed artifacts promote public support through exact-scope Core
support metadata and documentation. The browser disables product-unavailable
feature options, but that state is UX only; Core validation, the support policy
gate, and the `run_start_session()` final gate remain the safety boundary for
forged or stale requests.
34460A LAN/TCPIP pending scopes are future validation paths only and remain
product-closed in the WebUI.

## Measurement Modes

Measurement options are loaded from Core through:

```text
GET /api/capabilities
GET /api/capabilities?model=34460A
GET /api/capabilities?model=34461A
GET /api/capabilities?model=keysight-34461a
```

When `model` is omitted, `/api/capabilities` returns the compatibility
34461A-shaped capability surface with `defaults.instrument_model = null` and
`model_resolution.resolved = false`. The browser sends no `instrument_model`
for Auto; explicit Expected model choices send `"34460A"` or `"34461A"`.
In Auto-detect mode, capability controls and support summaries use that
fallback capability view until Start or Scan detects IDN. This display context
does not select the live driver; live runs still use the detected IDN-selected
profile as the runtime driver.

Model identity metadata is additive; existing model fields keep their current
values and meanings:

| Field | Example | Meaning |
| --- | --- | --- |
| `model` | `34461A` | Canonical instrument model token and existing public model contract. |
| `model_id` | `keysight-34461a` | Stable machine-readable profile identifier. |
| `display_model` | `Auto-detect` or `34461A` | Display-oriented UI text. |
| `capability_profile` | `34461A` | Profile whose capabilities are currently being displayed. |
| `capability_profile_id` | `keysight-34461a` | Stable ID for the displayed capability profile. |
| `instrument_model` | `34461A` | Existing selected or detected model field according to the owning payload. |
| `instrument_model_id` | `keysight-34461a` | Stable ID only after a resource IDN matches a profile. |

`instrument_profile` and every `available_profiles` entry include both
`model` and `model_id`. `support_summary.model_id` corresponds to its existing
`model`, while `capability_profile_id` corresponds to `capability_profile`.
For unresolved Auto-detect, both IDs describe the displayed 34461A fallback
capability profile: `display_model` remains `Auto-detect`,
`defaults.instrument_model` remains null, and `model_resolution` remains
unresolved while adding `fallback_profile_id: "keysight-34461a"`. This fallback
ID does not mean that a live instrument has been detected. Explicit profile
queries keep both fallback fields null.

`support_summary` preserves its existing English presentation fields and adds
the following sibling semantic-key metadata:

```text
status_key
runtime_driver_note_key
open_workflow_keys
limit_keys
pending_keys
```

The scalar keys correspond to `status_text` and `runtime_driver_note`; the key
lists correspond positionally to `open_workflows`, `limits`, and `pending`.
The browser uses recognized keys when available. Missing, malformed, unknown,
shorter, or longer key lists cannot remove, reorder, or add prose entries: the
existing prose list remains the authoritative display inventory and fallback.
These keys are presentation metadata only and do not affect support-policy
enforcement. Raw `validation_status`, transport, backend, model, and profile
identity values remain machine values. The latest raw summary can be
re-rendered from memory without another capability request. P2.6 uses that
cache during locale switching and does not send the browser locale to the API.
P2.7 completes the final translation-quality and cross-Part integration
validation for this behavior.

Canonical model names remain valid for normal use, and stable model IDs are
also accepted profile lookup inputs. A selected model remains an expected-model
guard; the profile detected from live `*IDN?` remains the runtime driver. Model
IDs do not represent support status or lifecycle state.

`/api/capabilities` also includes additive support metadata. Every exact live
connection scope keeps its existing `validation_status`, `transport_scope`,
and `backend_scope` fields and adds `features.measurement` and
`features.trigger_mode` maps. Feature entries expose their own
`validation_status`; measurement keys use the existing adapter-facing names
such as `voltage-dc-ratio`. Existing response fields are not removed or
renamed.

The browser uses this metadata to show model live support and to disable
features that are not product-open for the current resource transport and the
WebUI's fixed system-VISA backend. It distinguishes pending live validation,
not supported by model, and unavailable exact scope. Before a resource is
known, Auto-detect keeps the existing fallback capability view and uses only
the fallback profile's declared product scope; it never promotes a pending
feature. For 34461A the metadata includes validated USB/system-VISA,
LAN/system-VISA, and optional CLI-only LAN/pyvisa-py `@py` scopes. For 34460A,
DCV Ratio is Product-open on USB/system-VISA, while LAN/TCPIP scopes remain
`transport_pending`. The Ratio promotion followed maintainer review of separate
bounded evidence; the existing 12-case wrapper full suite did not include
Ratio. Existing measurement, trigger, range, and limit fields remain the source
of truth for control definitions.

The Expected model check is optional. Core validates the connected instrument
identity at Start. If an explicit expected model does not match the fresh IDN
preflight, the WebUI reports which model was selected and which supported model
was found in the IDN.

The selected WebUI model must not be treated as a feature unlock. Disabled or
hidden controls are UX only; the Core support policy and `run_start_session()`
runner final gate remain the safety boundary for WebUI backend submissions.
The WebUI should not add a pyvisa-py backend selector as part of validation
tooling work; backend diagnostics remain CLI-only unless a later product
decision changes that boundary.

Currently surfaced measurement modes include:

- `current-dc`
- `voltage-dc`
- `voltage-dc-ratio`
- `current-ac`
- `voltage-ac`
- `frequency`
- `period`
- `resistance-2w`
- `resistance-4w`

The frontend must not invent measurement options. It should populate choices,
defaults, ranges, NPLC options, AC bandwidth/filter options, Frequency/Period
gate-time options, Frequency timeout options, current terminal options, and
measurement-specific controls from `/api/capabilities`.

Measurement-specific UI behavior:

- NPLC appears only for supported measurements.
- AC, Frequency, and Period measurements do not show NPLC.
- AC filter appears for AC current, AC voltage, Frequency, and Period where
  supported.
- AC current and AC voltage offer `Keep current setting`, which omits the AC
  filter payload. Frequency and Period select their `20 Hz` default directly.
- Gate Time appears only for Frequency and Period, with an effective default of
  `0.1` s. Timeout appears only for Frequency and defaults to `auto`; Period
  hides it and sends no timeout payload.
- Current terminal selection appears only for current measurements where
  supported.
- With the 34460A profile selected, current ranges exclude 10 A and current
  terminal selection is hidden because the base 34460A profile has no 10 A
  terminal/path. Custom-mode reading memory is limited to 1000 readings.
- With the 34460A USB/system-VISA scope, `voltage-dc-ratio` is enabled from
  capability metadata and direct Product-mode WebUI starts accept it. This does
  not open Ratio on 34460A LAN scopes or expose a pyvisa-py selector.
- DCV Input Z appears only for `voltage-dc` and `voltage-dc-ratio`.
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

The exact list is profile-specific. The 34460A base profile hides `external`
and `external-custom` because LAN/LXI/external trigger capability is optional
and not assumed. Unsupported 34460A options are omitted through
`/api/capabilities?model=34460A`; the frontend does not maintain a separate
hard-coded 34460A option list.

For trigger modes that remain in the profile list, the browser also applies the
exact-scope feature status. `feature_pending` and `not_supported_by_model`
options are disabled, while `live_validated_full_suite` options remain
selectable. There is no validation-mode toggle or backend selector.

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

The browser-side trend chart has three frontend-only scale modes:

- `Auto deviation` is the default and preserves the original chart behavior.
  It keeps the first numeric sample in a run as the baseline and rescales on
  every render so the largest visible deviation maps to four grid steps from
  the center line.
- `Auto absolute` uses the absolute minimum and maximum of the visible recent
  numeric samples, with small padding so the line does not sit on the chart
  edges.
- `Manual span` keeps the first numeric sample as the center and uses the
  operator-entered positive raw-unit span as a fixed `baseline +/- span` range.
  Values outside that range are clamped to the chart boundary.

These modes affect only chart display, not raw sample values, statistics, CSV
output, API sample payloads, instrument settings, or SCPI commands. The chart
scale controls are not included in `POST /api/runs`.

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
  capabilities. Optional canonical models or registered stable model IDs select
  the profile; omitted model returns unresolved auto metadata and a
  compatibility 34461A-shaped capability surface. Profile identity and exact
  live support scopes add metadata without removing existing fields.
- `GET /api/resources?verify=true&live_only=true`: scans VISA resources and,
  for verified supported IDNs, includes nullable `instrument_model`,
  `instrument_model_id`, and `matched_profile` metadata.
- `POST /api/runs`: validates and starts a run.
- `GET /api/runs/current`: returns current or latest run status.
- `GET /api/runs/current/events`: returns Server-Sent Events (SSE) stream of run status changes.
- `POST /api/runs/current/command`: queues a software trigger for supported
  modes. Returns the common command response envelope: `202` accepted, `400`
  validation error, `429` queue/rate rejection, or `409` when no run is active
  or the run is not ready.
- `POST /api/runs/current/stop`: requests stop through the Core control plane.
- `POST /api/runs/current/open-csv`: opens the latest completed CSV.
- `POST /api/csv/select-folder`: opens a local folder picker and returns a
  timestamped CSV path for the existing CSV input.

Do not rename, remove, or repurpose these endpoints without updating frontend
code, tests, and documentation together.

After an accepted command response, the frontend fetches
`GET /api/runs/current` to refresh the displayed run status. Command responses
do not embed the full run status.

## Frontend Payload Fields

Important fields sent by the WebUI include:

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
- `gate_time_s`
- `freq_period_timeout`
- `current_terminal`

Hidden controls must be disabled so stale values are not submitted from inactive
modes.

Frequency and Period payloads keep raw numeric values: AC Filter `20 Hz` is
sent as `ac_bandwidth_hz: 20`, Gate Time as seconds, and Timeout as `auto` or
`1s`. Live data displays Frequency in `Hz` and Period in `s` without automatic
unit scaling.

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

- `src/meters_tool_webui/static/index.html`
- `src/meters_tool_webui/static/styles.css`
- `src/meters_tool_webui/static/*.js`

Backend adapter file:

- `src/meters_tool_webui/web_ui.py`
- `src/meters_tool_webui/launcher.py`

Tests:

- `tests/webui/test_webui_api.py`
- `tests/webui/test_webui_static.py`
- `tests/webui/test_launcher.py`
- Core contract and package boundary tests listed in the validation commands
  below.

Do not change root package metadata in `pyproject.toml` without explicit user
approval. Package name, version, dependencies, console scripts, build system,
pytest/ruff/mypy configuration, and Core/CLI/WebUI ownership are product
boundary decisions.

## Validation

Run the narrowest relevant checks first.

For JavaScript syntax after editing frontend modules:

```powershell
Get-ChildItem src\meters_tool_webui\static\*.js |
  ForEach-Object { node --check $_.FullName }
```

Focused WebUI/Core no-hardware validation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/webui/test_webui_package_metadata.py tests/webui/test_webui_api.py tests/webui/test_webui_static.py tests/webui/test_launcher.py -q -p no:cacheprovider
```

Build the optional local launcher exe with PyInstaller from an environment that
already has `meters-tool` installed. PyInstaller is a local release-build tool,
not a WebUI runtime dependency, so install it into the venv before rebuilding on
a fresh machine:

```powershell
uv pip install pyinstaller
```

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_webui_exe.ps1
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
- AC measurements show AC filter where supported and hide NPLC.
- Frequency and Period show AC Filter and Gate Time. Frequency also shows
  Timeout; Period and other measurements hide and disable it.
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

For Frequency and Period real-instrument inspection:

- Connect a stable signal that the 34461A front panel can measure.
- Select Frequency, confirm Auto Range, `20 Hz` AC Filter, `0.1 s` Gate Time,
  and `Auto` Timeout, then capture one immediate sample.
- Confirm the Live data value uses raw `Hz` and compare it with the front panel.
- Repeat with Period and confirm the raw unit is `s`.
- Stop the run before changing measurement type, and inspect the generated CSV
  row after each sample.

## Troubleshooting

Wrapper is missing:

- Re-run `uv pip install -e ".[all,dev]" --link-mode=copy`.
- Confirm `.venv\Scripts\meters-tool-webui.exe` exists.

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

- [WebUI User Guide](USER_GUIDE.md): operator-facing WebUI usage guide.
- [WebUI README](README.md): this WebUI behavior, API, validation, and
  maintainer guide.
- [WebUI Change Rules](web-ui-change-rules.md): maintainer and agent-facing
  rules for UI changes.
- [WebUI Changelog](CHANGELOG.md): package release notes.
