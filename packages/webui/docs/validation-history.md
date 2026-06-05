# Web UI Validation History

Updated: 2026-06-01

This file records validation history for the WebUI adapter package after
merging the independent Core runtime. Detailed CLI wrapper, JSONL,
soft-trigger, and artifact validation belongs to the CLI package docs.

## WebUI v1.2.0 Release Validation

- Target release: `webui-v1.2.0`.
- Package metadata: `keysight-logger-webui` version `1.2.0`.
- Core dependency range was updated to `keysight-logger-core>=1.2.0,<1.3`.
- No WebUI endpoint, browser UI, Core runtime, SCPI, VISA timeout, trigger wait
  strategy, cleanup order, measurement logic, or CSV behavior changed in this
  package/dependency release.
- `.\.venv\Scripts\keysight-logger-webui.exe --version` reported
  `keysight-logger-webui 1.2.0`.
- `node --check packages\webui\src\keysight_logger_webui\static\app.js`
  passed.
- `.\.venv\Scripts\python.exe -m pytest packages\webui\tests -q -p no:cacheprovider --basetemp .tmp_tests\pytest_tmp_webui120`
  passed with `31 passed, 1 warning, 64 subtests passed`.
- Full workspace validation passed with
  `389 passed, 1 warning, 145 subtests passed`.

## Core v1.1.0 Merge

The WebUI branch keeps the WebUI adapter package identity while using the
merged Core `core-v1.1.0` runtime. The package was initially
`keysight-logger-webui` version `1.0.0` with the
`keysight-logger-webui` console script.

## WebUI v1.1.0 Release-Target Validation

No-hardware validation was rerun on 2026-05-29 for the `webui-v1.1.0` release
tag target.

```powershell
node --check packages\webui\src\keysight_logger_webui\static\app.js
```

Result: passed.

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui.py tests\test_core_public_api.py tests\test_core_validation.py tests\test_core_run_plan.py tests\test_core_runner.py packages\webui\tests\test_webui_package_metadata.py packages\webui\tests\test_webui_docs_ownership.py -q -p no:cacheprovider
```

Result: 74 passed, 123 subtests passed.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

Result: 243 passed, 128 subtests passed.

The package metadata was then bumped to `keysight-logger-webui` version
`1.1.0` for the `webui-v1.1.0` tag.

```powershell
uv pip install -e ".[dev]" --link-mode=copy
.\.venv\Scripts\keysight-logger-webui.exe --version
```

Result: editable install upgraded `keysight-logger-webui` from `1.0.0` to
`1.1.0`, and `--version` printed `keysight-logger-webui 1.1.0`.

Focused validation target for this merge:

```powershell
node --check packages\webui\src\keysight_logger_webui\static\app.js
uv run pytest tests/test_web_ui.py tests/test_core_public_api.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py packages/webui/tests/test_webui_package_metadata.py packages/webui/tests/test_webui_docs_ownership.py -q -p no:cacheprovider
```

Expected coverage:

- WebUI API start/status/trigger/stop/Open CSV behavior.
- Static UI contract for the existing page layout and controls.
- Core public API, validation, dry-run plan, and runner behavior.
- WebUI package metadata and documentation ownership.

Recorded WebUI results before this merge resolution:

- `node --check packages\webui\src\keysight_logger_webui\static\app.js`: passed.
- Focused WebUI/Core pytest command: 63 passed, 63 subtests passed.
- Broader `tests` pytest command: 213 passed, 68 subtests passed.
- WebUI package metadata publishes `keysight-logger-webui`, and `--version` is
  covered by `tests/test_web_ui.py`.
- `uv pip install -e ".[dev]" --link-mode=copy` succeeded, and
  `.venv\Scripts\keysight-logger-webui.exe --version` printed
  `keysight-logger-webui 1.0.0`.

## Core v1.1.0 Validation Brought Forward

Core DCV Ratio implementation and no-hardware validation were completed on
2026-05-27. The change adds `measurement="voltage-dc-ratio"`, ratio sample
metadata from `DATA2?`, stricter `dcv_input_impedance` validation, and CSV
`measurement_metadata` output.

Focused no-hardware Core validation:

```powershell
uv run pytest tests/test_capabilities.py tests/test_measurement.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_csv_writer.py tests/test_simulator.py -q -p no:cacheprovider
```

Recorded Core result: 124 passed, 59 subtests passed.

Required Core guard validation:

```powershell
uv run pytest tests/test_core_public_api.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py packages/webui/tests/test_webui_package_metadata.py packages/webui/tests/test_webui_docs_ownership.py -q -p no:cacheprovider
```

Recorded Core result: 47 passed, 59 subtests passed.

Full Core suite:

```powershell
uv run pytest tests -q -p no:cacheprovider
```

Recorded Core result: 216 passed, 64 subtests passed.

## Prior WebUI Baseline

The previous WebUI integration baseline validated:

```powershell
node --check packages\webui\src\keysight_logger_webui\static\app.js
uv run pytest tests\test_web_ui.py -q -p no:cacheprovider
uv run pytest tests\test_web_ui.py tests\test_capabilities.py tests\test_measurement.py -q -p no:cacheprovider
```

Recorded result from the prior handoff: `tests/test_web_ui.py` passed with 21
tests and 17 subtests; the combined WebUI/capability/measurement pass recorded
87 tests and 17 subtests.

## Hardware Status

User-reported WebUI real/manual smoke validation passed before the
`webui-v1.0.0` tag. The exact VISA resource and detailed run log were not
recorded in this file.

Live Core API validation was run on 2026-05-27 with explicit resource
`USB0::0x2A8D::0x1301::MY60045220::0::INSTR`.

Baseline live smoke:

- `measurement="current-dc"`, `trigger_mode="immediate"`, `max_samples=1`.
- Result: `ok=True`, `reason="completed"`, `captured=1`, `errors=0`,
  `fatal_error=None`.
- Cleanup completed and released the instrument to local.

New Core measurement option live checks:

- Auto Zero Once passed on the operator-selected supported measurements.
- AC bandwidth values `3`, `20`, and `200` passed.
- Invalid AC bandwidth input produced the expected validation error.
- 10 A current terminal selection passed with an operator-confirmed safe setup.
- DCV Ratio immediate and external hardware-trigger captures passed with
  bounded sample counts, ratio units, and signal/reference metadata.

These checks validate explicit Core request fields. Default requests continue
to preserve the previous command sequence, VISA timeout behavior, trigger wait
strategy, stop flow, cleanup order, measurement behavior, NPLC, Auto Zero, Auto
Range, and VM Comp behavior.

## Operational Note

The WebUI process is a Uvicorn/FastAPI server. The old CLI `q` stop behavior is
not a WebUI server-exit control. `Ctrl+C` should work only when the terminal
delivers SIGINT to the Python process; otherwise stop the listening process by
PID, for example by finding the owner of port `8767` and stopping that process.

Documentation ownership for this branch is covered by:

```powershell
uv run pytest packages/webui/tests/test_webui_docs_ownership.py -q -p no:cacheprovider
```
