# Web UI Session Handoff

Updated: 2026-05-29

This file is the single source of current WebUI branch status, validation,
active risks, and next work. Keep `docs/session-handoff.md` as a thin index so
Core and WebUI branch merges do not repeatedly conflict on detailed status.

Durable direction stays in `docs/project-plan.md`; the shared Core contract
stays in `docs/integration.md`; WebUI-specific UI rules stay in
`docs/web-ui-ai-change-rules.md`; hardware validation workflow stays in
`docs/hardware-test-plan.md`.

## Current Status

- Branch: `Webui`.
- Release tag target: `webui-v1.1.0`.
- Purpose: WebUI adapter branch on top of the independent Core runtime.
- Core `core-v1.1.0` runtime changes have been merged into this branch.
- Distribution metadata is the WebUI adapter package
  `keysight-logger-webui` version `1.1.0`.
- The Web UI starts with the uv-installed console wrapper
  `keysight-logger-webui`; the wrapper supports `--version`.
- `packages/webui/src/keysight_logger_webui/web_ui.py` adapts browser payloads to Core
  `StartRequest`, validates through Core, and runs Core `run_start_session()`.
- The Web UI API preserves the existing browser-facing endpoints:
  `/api/capabilities`, `/api/resources`, `/api/runs`,
  `/api/runs/current`, `/api/runs/current/trigger`,
  `/api/runs/current/stop`, and `/api/runs/current/open-csv`.
- `/api/runs/current` exposes WebUI-owned Live data fields:
  `latest_sample`, `recent_samples`, and `sample_capacity`.
- The browser UI remains in `packages/webui/src/keysight_logger_webui/static/`.
- The Live data panel is implemented. It renders the latest sample, a
  browser-side trend chart, a recent-samples table, and selected-sample
  metadata details from Core sample events.
- WebUI trigger and stop actions route through a Core control plane; WebUI code
  does not directly call acquisition engine internals or close VISA sessions.
- Core now supports Auto Zero Once for `current-dc`, `voltage-dc`, and
  `resistance-2w`; AC bandwidth selection for `current-ac` and `voltage-ac`;
  explicit current terminal selection for current measurements; and
  `voltage-dc-ratio` with signal/reference voltage measurement metadata.
- No intentional changes were made to default NPLC, Auto Zero, Auto Range,
  VM Comp, trigger delay, trigger wait strategy, VISA timeout defaults, stop
  flow, release/local behavior, cleanup order, or default SCPI command
  sequences as part of the WebUI work.

## Project Status

- Core: complete as an independent `keysight-logger-core` runtime package.
  Core owns validation, planning, acquisition, trigger routing, stop behavior,
  cleanup order, instrument/profile metadata, and safety rules.
- CLI: complete on the separate CLI branch. CLI-specific runtime, wrapper,
  console behavior, and JSONL/artifact contracts remain adapter-owned and are
  not part of this WebUI release.
- WebUI: ready for `webui-v1.1.0` after current no-hardware validation.
  Existing browser UI and API behavior are preserved while using Core
  `StartRequest`, Core validation, and Core `run_start_session()` underneath.

## Current Web UI Layout

Runtime entry point:

```powershell
.\.venv\Scripts\keysight-logger-webui.exe --port 8767
```

Version check:

```powershell
.\.venv\Scripts\keysight-logger-webui.exe --version
```

Local URL:

```text
http://127.0.0.1:8767/
```

The Web UI now uses this structure:

- Header title is `Keysight Meters`; subtitle is `Local acquisition console`.
- Resource row is above the status strip.
- Resource row contains `VISA resource`, `Live resource`, and `Scan Device`.
- Scan still calls `/api/resources?verify=true&live_only=true`.
- Status strip shows `State`, `Captured`, `Errors`, and `CSV`.
- `Open CSV` sits after `Stop`.
- Measurement, trigger, run setup, and status detail controls are grouped into
  collapsible panels.
- Live data contains a latest-reading summary, UTC+8 sample times, an SVG trend
  chart, a recent-samples table, and a selected-sample metadata detail area.

## Live Data Behavior

Backend source:

```text
GET /api/runs/current
```

Additional status fields:

- `latest_sample`: latest serialized Core sample, or `null`.
- `recent_samples`: bounded list of the latest 100 serialized samples.
- `sample_capacity`: `100`.

Sample fields:

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

Behavior:

- Samples are captured from Core `sample` events already emitted by
  `run_start_session()`.
- WebUI does not perform extra VISA reads for Live data.
- Stopped runs keep the latest 100 samples for operator review.
- Starting a new run creates a fresh sample window.
- The chart is browser-side only and does not change CSV output.

## Open CSV Behavior

Backend endpoint:

```text
POST /api/runs/current/open-csv
```

Behavior:

- Opens only the current/latest run CSV from manager state.
- Does not accept a frontend-supplied file path.
- Returns `409` with `run is still active` while a run is active.
- Returns `409` with `no completed CSV available` if no completed CSV path is
  available.
- Returns `404` with `CSV file not found` if the recorded CSV path is missing.
- On success, uses the Windows default app opener and returns:
  `{ "opened": true, "csv_path": "..." }`.

Frontend behavior:

- Disabled and gray by default.
- Disabled while `status.active === true`.
- Enabled and black when `status.active === false` and `csv_path` is present.
- Refreshing the browser after a completed run can still show `Open CSV`
  because the backend intentionally preserves the latest completed CSV path.
- Click calls `/api/runs/current/open-csv`.
- Success and failure messages are appended to the Status log.

## UI Resource Listing Behavior

- Scan Device calls the shared resource listing backend with verification and
  live-only filtering enabled.
- Scan Device calls the Core VISA resource listing helper through the WebUI
  backend.
- `/api/resources?verify=true&live_only=true` opens each resource, queries
  `*IDN?`, returns only live rows, and includes `live_only: true`.
- This behavior benefits Web UI Scan Device and future agent workflows that
  scan through the WebUI/Core path.

## UI Trigger And Display Notes

- Hardware trigger timeout remains a protective re-arm condition, not an
  acquisition error.
- For UI work, show the trigger timeout control only for the external trigger
  modes (`external` and `external-custom`) and hide it for non-external modes.
  This is a UI clarity change, not a CLI contract change.
- Null/relative is not implemented as instrument NULL state. If needed later for
  the UI, prefer a software relative/offset display first so raw measured values
  remain available.

## Latest Validation

Latest no-hardware validation for the `webui-v1.1.0` release tag target was
run on 2026-05-29:

```powershell
node --check packages\webui\src\keysight_logger_webui\static\app.js
```

```powershell
uv run pytest tests/test_web_ui.py tests/test_core_public_api.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py packages/webui/tests/test_webui_package_metadata.py packages/webui/tests/test_webui_docs_ownership.py -q -p no:cacheprovider
```

Result: `node --check` passed; focused pytest passed with 74 tests and 123
subtests; broader `tests` pytest passed with 243 tests and 128 subtests.

Core `core-v1.1.0` no-hardware validation from the merged branch:

```powershell
uv run pytest tests/test_capabilities.py tests/test_measurement.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_csv_writer.py tests/test_simulator.py -q -p no:cacheprovider
```

Recorded Core result: 124 passed, 59 subtests passed.

```powershell
uv run pytest tests -q -p no:cacheprovider
```

Recorded Core result: 216 passed, 64 subtests passed. Re-run on 2026-05-28
with the same result.

WebUI console wrapper/version validation:

```powershell
uv pip install -e ".[dev]" --link-mode=copy
.\.venv\Scripts\keysight-logger-webui.exe --version
```

Recorded WebUI result for `webui-v1.1.0`: editable uv install succeeded,
upgraded `keysight-logger-webui` from `1.0.0` to `1.1.0`, and `--version`
printed `keysight-logger-webui 1.1.0`.

User-reported WebUI real/manual smoke validation: Pass.

Live 34461A Core validation was run on 2026-05-27 with
`USB0::0x2A8D::0x1301::MY60045220::0::INSTR` through the Core API. Baseline
immediate `current-dc` captured one sample with `ok=True`, `captured=1`, and
`errors=0`. Auto Zero Once passed, AC bandwidth values `3`, `20`, and `200`
passed, invalid AC bandwidth input produced a validation error, 10 A
current-terminal selection passed with an operator-confirmed safe setup, and
DCV Ratio captured five bounded immediate samples and five bounded external
hardware-trigger samples with `ok=True`, `captured=5`, `errors=0`, ratio units,
and `signal_voltage_v`, `reference_voltage_v`, and `secondary_source`
metadata. The external-trigger pass used `slope=NEG`, `delay_s=0.0`, and
reported `trigger_source="hardware"` for each sample.

The Auto Zero Once, AC bandwidth, current-terminal, DCV input impedance, and
DCV Ratio updates change SCPI only when the corresponding Core request fields
or `measurement="voltage-dc-ratio"` are explicitly set. Default requests
preserve previous command sequences, VISA timeout behavior, trigger wait
strategy, stop flow, release/local behavior, cleanup order, Auto Range/Zero,
and VM Comp behavior.

Live data implementation validation on 2026-05-29:

```powershell
node --check packages\webui\src\keysight_logger_webui\static\app.js
```

Result: passed.

Focused WebUI/Core validation was rerun after the Live data implementation and
passed with 74 tests and 123 subtests.

## Active Risks

- The WebUI control plane uses Core router events for software trigger and stop.
  Focused API tests should cover start, trigger, stop, and Open CSV behavior.
- The WebUI server process is Uvicorn/FastAPI, so `q` is not a supported
  server-exit key. `Ctrl+C` depends on the terminal delivering SIGINT; if it
  does not, stop the listening `python.exe` by PID.
- Avoid reintroducing CLI adapter imports or top-level legacy backend imports.
- Hardware-facing changes must stay behind explicit user confirmation and be
  recorded in `docs/hardware-test-plan.md`.

## Next Conversation

1. Commit the WebUI release-ready state.
2. Tag the commit as `webui-v1.1.0`.
3. Keep LAN validation and real AC signal validation deferred until those test
   environments are available.
4. Record any future live validation results in this file and
   `docs/validation-history.md`.
