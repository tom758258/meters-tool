# Keysight 34461A CLI Logger

Current CLI baseline: `cli-v1.3.2`.

## Documentation Set

- [CLI Guide - English](README_CLI_EN.md) - current document.
- [Changelog](../CHANGELOG.md) - release notes and pending baseline.
- [CLI Integration](cli-integration.md) - CLI adapter maintenance boundary.
- [Common CLI JSON / JSONL Contract](../../../docs/contracts/common-cli-jsonl-contract.md) - shared command-line JSON envelope rules.
- [Meters CLI JSON / JSONL Contract](../../../docs/contracts/meters-cli-jsonl-contract.md) - Meters command-line JSON schema and alias rules.
- [Common Orchestrator Workflows](../../../docs/contracts/common-orchestrator-workflows.md) - shared subprocess lifecycle guidance.
- [Meters Orchestrator Workflows](../../../docs/contracts/meters-orchestrator-workflows.md) - Meters subprocess examples for agents and automation.
- [Meters Worker Contract](../../../docs/contracts/meters-worker-contract.md) - Meters worker control plane, JSONL, and artifact contract for agents and orchestrators.
- [CLI Guide - Traditional Chinese](README_CLI_ZH-TW.md) - planned.
- [UI Guide - English](README_UI_EN.md) - planned.
- [UI Guide - Traditional Chinese](README_UI_ZH-TW.md) - planned.

CLI-first Python logger for Keysight 34461A DC/AC current, DC/AC voltage,
DCV ratio, and 2-wire or 4-wire resistance measurements over VISA.
It records one CSV row per captured sample and supports software, external
hardware, and immediate trigger modes.

`cli-v1.3.2` is the current CLI baseline after unifying the former Core, CLI,
and WebUI branches into the monorepo `main` branch while keeping independent
package metadata, console scripts, JSON/JSONL contracts, wrapper scripts, and
tests. It continues to expose Core v1.1.0 measurement fields through the CLI:
`voltage-dc-ratio`,
`--auto-zero once`, `--ac-bandwidth-hz`, and `--current-terminal`. Core start
validation, dry-run planning, runtime orchestration, public integration exports,
and measurement naming remain separated from adapter-only CLI concerns. This
baseline also records the legacy root-level import cleanup, CLI contract v1.5
additive client diagnostics, no-hardware release validation, wrapper report
metadata, Core/CLI boundary guards, and the Core `1.2.x` dependency alignment.

Python integrations should import shared APIs from `keysight_logger_core` or
`keysight_logger_core.*`. The old root-level Core module imports such as
`keysight_logger.measurement` and `keysight_logger.instrument` are no longer
supported.

## Current Scope

Implemented:

- VISA resource listing for USB and LAN resources discovered by PyVISA.
- DC current, DC voltage, DCV ratio, AC current, AC voltage, and 2-wire or
  4-wire resistance measurement logging.
- Software trigger mode through a local HTTP endpoint.
- Local worker status endpoint through `GET /status`.
- Software timer capture as part of software trigger mode.
- External hardware trigger mode.
- Immediate capture mode.
- Bounded runs with `--max-samples`.
- Graceful stop through HTTP, Ctrl+C, Ctrl+Break, or `q`.
- Software trigger metadata persisted to CSV as `trigger_metadata`.
- Optional UTC+8 timestamped CSV output path when `--csv` is omitted.
- Optional resource verification with `list-resources --verify`.
- Optional live-resource filtering with `list-resources --live-only`.
- Optional measurement controls: measurement type, Auto Range, manual range,
  DCV input impedance, Auto Zero including `once`, NPLC, AC bandwidth,
  current terminal selection, hardware trigger delay, hardware trigger slope,
  and VM Comp slope.
- Immediate CSV flush after every captured sample.

Important limitations:

- This project is currently focused on Keysight 34461A current, voltage,
  DCV ratio, and 2-wire or 4-wire resistance logging.
- AC modes expose the 34461A `3`, `20`, and `200` Hz bandwidth settings through
  `--ac-bandwidth-hz`. Before production use, run a low-risk live-resource
  smoke test with an operator-provided VISA resource and compare the CLI row to
  the 34461A front-panel reading.
- `--nplc` and `--auto-zero` are DC/resistance controls. AC current and AC
  voltage accept only the neutral default `--nplc 1.0`; any other NPLC value is
  rejected because AC modes do not write NPLC SCPI. AC modes also do not write
  Auto Zero SCPI commands.
- Mixed software and hardware capture in the same run is not supported.
- Plain `list-resources` calls VISA discovery directly and may show stale
  resources cached by the VISA runtime. Use `list-resources --verify` to open
  each resource and query `*IDN?`; successful verified resources are released
  back to local on a best-effort basis before closing. Use
  `list-resources --live-only` when you only want resources that answered.
- `immediate` mode can capture continuously and quickly. Use `--max-samples`
  unless you intentionally want a continuous run.

## Requirements

- Python 3.10 or newer.
- A VISA runtime, such as Keysight IO Libraries Suite or NI-VISA.
- A Keysight 34461A visible to VISA over USB or LAN.

## Development

From PowerShell, change into the project directory, create or reuse the local
virtual environment, install the package with development dependencies, then
run the default tests:

```powershell
cd path\to\Keysight
uv venv .venv
uv pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

If `uv` warns that hardlinking failed and it is falling back to copying files,
that warning is usually not a failed install. For cross-drive checkouts or
environments that do not support hardlinks, install with:

```powershell
uv pip install -e ".[dev]" --link-mode=copy
```

On Windows, the full pytest run may need an elevated PowerShell session because
VISA-related discovery or local environment access can require administrator
permissions.

After installation, use the `keysight-logger` console script for project
commands:

```powershell
.\.venv\Scripts\keysight-logger.exe <command> [options]
```

`.venv\Scripts\keysight-logger.exe` is generated by installation and is not a
tracked project file. If it is missing, rerun `uv pip install -e ".[dev]"`.
If PowerShell blocks activation because of execution policy, keep using the
explicit `.venv\Scripts\...` commands shown in this guide.

The explicit module form is also supported as a development/fallback
alternative:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger_cli <command> [options]
```

Optional activation:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation because of execution policy, use the explicit
`.\.venv\Scripts\python.exe` commands shown above.

## Standalone EXE Build

The installed `.venv\Scripts\keysight-logger.exe` is a virtualenv console
wrapper. It is not a standalone executable for machines without the project
environment.

To build the optional standalone console exe, use PyInstaller from an
environment that already has the CLI and Core packages installed. PyInstaller
is a local release-build tool, not a CLI runtime dependency, so install it into
the venv before rebuilding on a fresh machine:

```powershell
uv pip install pyinstaller
```

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --onefile --console --name keysight-logger --paths packages\cli\src --paths packages\core\src packages\cli\src\keysight_logger_cli\cli.py
```

The output is:

```text
dist\keysight-logger.exe
```

Run no-hardware smoke checks after rebuilding:

```powershell
.\dist\keysight-logger.exe --version
.\dist\keysight-logger.exe --help
.\dist\keysight-logger.exe list-resources --dry-run --json
.\dist\keysight-logger.exe start-trigger-record --resource SIM::34461A --simulate --measurement voltage-dc --trigger-mode immediate --max-samples 1 --csv .tmp_tests\cli_exe_smoke.csv --status-format jsonl
```

PyInstaller writes `keysight-logger.spec` in the current directory. That file
is a local build recipe generated from the command above. Do not commit it
unless the project intentionally switches to a checked-in PyInstaller spec.

## No-Hardware Validation

Run this recipe before live instrument work:

```powershell
uv pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packages\cli\scripts\preflight-cli.ps1 -Target keysight-34461a
.\.venv\Scripts\keysight-logger.exe list-resources --dry-run --json
```

`list-resources --dry-run` does not create a VISA resource manager, list VISA
resources, open resources, query `*IDN?`, or run release/local cleanup. If the
console script has not been generated yet, install the package first; the module
form above remains a development fallback.

## Basic Workflow

1. List VISA resources.
2. Choose a resource string.
3. Start `start-trigger-record` in one terminal.
4. Send triggers, wait for external trigger edges, or use immediate mode.
5. Stop with `stop`, Ctrl+C, Ctrl+Break, `q`, or `--max-samples`.
6. Inspect the CSV output.

## Command Reference

Use the installed console script:

```powershell
.\.venv\Scripts\keysight-logger.exe <command> [options]
```

The module form remains an explicit development/fallback alternative:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger_cli <command> [options]
```

| Command | Purpose | Typical use |
| --- | --- | --- |
| `list-resources` | Print VISA resources discovered by PyVISA. | Find the USB or LAN resource string. Add `--verify` to query `*IDN?`; add `--live-only` to hide stale cached resources; add `--dry-run` to preview discovery actions without touching VISA. |
| `start-trigger-record` | Connect to the instrument and record samples to CSV. | Main logging command. |
| `send-command` | POST one `software_trigger` command to the local command endpoint. | Used with `--trigger-mode software`. |
| `stop` | POST a graceful stop request to the local stop endpoint. | Stop a running logger from another terminal. |
| `status` | GET the local status endpoint and normalize the worker status. | Check worker health and correlate `run_id` without mutating state. |
| `wait-ready` | Poll the local status endpoint until the worker control plane is reachable. | Orchestrator readiness gate before trigger/stop/status calls. |

Root options:

| Option | Description |
| --- | --- |
| `--version` | Print `keysight-logger <package-version>` and exit without requiring a subcommand. |

`list-resources` options:

| Option | Description |
| --- | --- |
| none | Print raw VISA resources returned by PyVISA. This can include stale cached resources and does not open resources or run release-to-local cleanup. |
| `--verify` | Open each discovered resource and query `*IDN?`. Text output marks rows as `live` or `stale`; JSON output includes `live`, `status`, and `detail`. Successful live checks run best-effort release-to-local before closing. |
| `--live-only` | Verify resources and print only rows that answered. Successful live checks run best-effort release-to-local before closing. Text output prints `no live VISA resources found` if nothing is connected or reachable. |
| `--dry-run` | Print the resource-discovery contract and exit 0 without creating a VISA resource manager, listing resources, opening resources, querying `*IDN?`, or running release/local cleanup. Can be combined with `--verify`, `--live-only`, and `--json`. |
| `--format json` | Emit one JSON object for scripts. Can be combined with `--verify` or `--live-only`. |
| `--json` | Alias for `--format json`. |

`send-command` options:

| Option | Default | Description |
| --- | --- | --- |
| `--port N` | `8765` | Local command endpoint port. Supported range: `1` to `65535`. |
| `--timeout-ms N` | `3000` | HTTP client timeout in milliseconds. Supported range: `100` to `600000`. |
| `--command NAME` | `software_trigger` | Meters command name. This revision supports only `software_trigger`. |
| `--arguments-json JSON` | `{}` | JSON command arguments. Use `{"metadata":{...}}` to attach trigger metadata written to CSV as `trigger_metadata`. Invalid JSON is rejected before sending the request. |
| `--job-id TEXT` | unset | Optional client-generated job id echoed by the command envelope only. |
| `--format text\|json` | `text` | Response output format. `json` emits one structured object for agent callers. |
| `--json` | No | Off | Alias for `--format json`. |
| `--dry-run` | No | Off | Preview the request locally without sending HTTP. |

`stop` options:

| Option | Default | Description |
| --- | --- | --- |
| `--port N` | `8765` | Local stop endpoint port. Supported range: `1` to `65535`. |
| `--timeout-ms N` | `3000` | HTTP client timeout in milliseconds. Supported range: `100` to `600000`. |
| `--format text\|json` | `text` | Response output format. `json` emits one structured object for agent callers. |
| `--json` | No | Off | Alias for `--format json`. |
| `--dry-run` | No | Off | Preview the request locally without sending HTTP. |

`status` options:

| Option | Default | Description |
| --- | --- | --- |
| `--port N` | `8765` | Local status endpoint port. Supported range: `1` to `65535`. |
| `--timeout-ms N` | `3000` | HTTP client timeout in milliseconds. Supported range: `100` to `600000`. |
| `--format text\|json` | `text` | Response output format. `json` emits one normalized status object. |
| `--json` | No | Off | Alias for `--format json`. |
| `--dry-run` | No | Off | Preview the non-mutating GET request locally without sending HTTP. |

`wait-ready` options:

| Option | Default | Description |
| --- | --- | --- |
| `--port N` | `8765` | Local status endpoint port. Supported range: `1` to `65535`. |
| `--timeout-ms N` | `10000` | Overall readiness deadline in milliseconds. Supported range: `100` to `600000`. |
| `--format text\|json` | `text` | Response output format. `json` emits normalized status plus readiness timing fields. |
| `--json` | No | Off | Alias for `--format json`. |

## Trigger Modes

| Mode | How capture starts | Read path | CSV `trigger_source` | Notes |
| --- | --- | --- | --- | --- |
| `software` | `send-command` posts to the local HTTP endpoint, or `--timer-interval-s` creates automatic timer events. | `READ?` | `software` or `timer` | Default when `--trigger-mode` is omitted. Timer mode uses fixed-delay spacing after each capture attempt. |
| `external` | The instrument receives an external hardware trigger edge. | `FETC?` | `hardware` | Use `--trigger-mode external`. |
| `immediate` | The worker captures without waiting for a trigger event. | `READ?` | `immediate` | Use `--max-samples` for bounded runs. |
| `immediate-custom` | The instrument runs an explicit immediate trigger/sample sequence and stores readings in memory. | `INIT` + `DATA:POINts?` / `DATA:REMove?` | `immediate-custom` | Requires `--trigger-count` and `--sample-count`; `--max-samples` is not valid. |
| `software-custom` | The instrument is armed for bus triggers; each accepted `send-command` sends `*TRG`. | `INIT` + `*TRG` + `DATA:POINts?` / `DATA:REMove?` | `software-custom` | Requires `--trigger-count` and `--sample-count`; `--max-samples` and `--timer-interval-s` are not valid. |
| `external-custom` | The instrument is armed for external trigger edges and stores readings in memory. | `INIT` + external edge + `DATA:POINts?` / `DATA:REMove?` | `external-custom` | Requires `--trigger-count` and `--sample-count`; `--max-samples` and `--timer-interval-s` are not valid. |

In `external` mode, accidental software triggers are ignored and should not
break the hardware-trigger flow. In `immediate` mode, software triggers are also
ignored.

When `--timer-interval-s` is active, ordinary `send-command` requests are
ignored while `stop` still stops the run. The first timer sample is captured
when recording starts; each later timer sample waits at least the configured
interval after the previous capture attempt finishes. Timer mode is a simple
software-mode acquisition path, so `--max-samples` is valid and stops the run
after that many successful timer CSV rows.

## `start-trigger-record` Options

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `--resource RESOURCE` | Yes | None | VISA resource string, for example USB or TCPIP HiSLIP. |
| `--csv PATH` | No | `data/YYYY-MM-DD-HH-MM-SS.csv` | CSV output path. If omitted, a UTC+8 timestamped file is created under `data`. Parent directories are created automatically. |
| `--status-format text\|jsonl` | No | `text` | Runtime status output format. `jsonl` emits one JSON object per line for agent callers. |
| `--dry-run` | No | Off | Validate arguments and print the planned measurement, SCPI, read path, and cleanup contract without opening VISA, writing CSV, or starting the HTTP server. |
| `--simulate` | No | Off | Run against a deterministic simulated instrument backend instead of opening a real VISA session. Simple modes require bounded runs such as `--max-samples`. |
| `--json` | No | Off | Alias for `--status-format jsonl`. |
| `--timeout-ms N` | No | `5000` | VISA session timeout in milliseconds. Supported range: `100` to `600000`. |
| `--trigger-timeout-ms N` | No | `10000` | External/custom trigger wait timeout. Supported range: `500` to `600000`. Timeout re-arms hardware mode and is not itself a capture error. Values that are too short for the expected external edge timing will repeatedly re-arm instead of capturing. |
| `--sw-trigger-port N` | No | `8765` | Local HTTP port for `/command`, `/stop`, and `/status`. Use `0` to let the server choose a port, or use `1024` to `65535`. |
| `--sw-min-interval-ms N` | No | `0` | Minimum interval between accepted software triggers. Use `0` to disable rate limiting, or use `50` to `600000`. |
| `--sw-queue-max N` | No | `0` | Maximum queued software triggers. Supported range: `0` to `10000`; `0` uses the default safety cap. |
| `--trigger-mode software\|external\|immediate\|immediate-custom\|software-custom\|external-custom` | No | `software` | Select exactly one acquisition mode. |
| `--max-samples N` | Simple modes only | None | Stop simple modes automatically after N successful CSV samples. Supported range: `1` to `1000000`. Not valid with custom modes. |
| `--trigger-count N` | Custom modes only | None | Instrument trigger count. Supported range: `1` to `1000000`. Required with custom modes; not valid with simple modes. |
| `--sample-count N` | Custom modes only | None | Instrument sample count per trigger. Supported range: `1` to `1000000`. Required with custom modes; not valid with simple modes. |
| `--timer-interval-s SECONDS` | No | None | Enable fixed-delay software timer capture. Supported range: `0.5` to `86400` seconds. Valid only with `--trigger-mode software`; also valid when `--trigger-mode` is omitted because software is the default. May be combined with `--max-samples` for bounded timer runs. |
| `--buffer-drain-size N` | Custom modes only | None | Maximum readings to remove per buffer drain. Supported range: `1` to `10000`, capped by the instrument profile reading memory. Advanced option valid only with custom modes; does not change `TRIG:COUNT`, `SAMP:COUNT`, or instrument reading memory capacity. |
| `--allow-buffer-overflow-risk` | No | Off | Allow custom modes to request more readings than the 34461A 10,000-reading memory limit. This depends on draining readings fast enough and may lose data or produce SCPI errors. |
| `--hw-trigger-slope pos\|neg` | No | `neg` | External trigger edge polarity. |
| `--hw-trigger-delay-s SECONDS` | No | `0.0` | Hardware trigger delay, mapped to `TRIG:DEL`. Supported range: `0` to `3600` seconds. |
| `--measurement current-dc\|voltage-dc\|voltage-dc-ratio\|current-ac\|voltage-ac\|resistance-2w\|resistance-4w` | No | `current-dc` | Measurement type. |
| `--nplc VALUE` | No | `1.0` | Integration time in power-line cycles for DC current, DC voltage, DCV ratio, and resistance. Allowed values for DC/resistance/ratio: `0.02`, `0.2`, `1`, `10`, `100`. AC current and AC voltage accept only the neutral default `1.0`; omit `--nplc` for AC modes unless you intentionally pass `1.0`. |
| `--auto-zero on\|off\|once` | No | `on` | Auto Zero for supported measurements. `once` is valid with DC current, DC voltage, and 2-wire resistance. DCV ratio accepts only the default/on behavior and writes no Auto Zero SCPI; 4-wire resistance and AC measurements leave Auto Zero to the instrument. |
| `--auto-range on\|off` | No | `on` | Enable or disable Auto Range. |
| `--range VALUE` | Required when `--auto-range off` | None | Manual range for the selected measurement. Amps for current, volts for voltage, ohms for resistance. |
| `--current-range VALUE` | Current DC only | None | Compatibility alias for `--range` with `current-dc`. Do not combine with `--range`; invalid with AC current, voltage, and resistance measurements. |
| `--ac-bandwidth-hz 3\|20\|200` | AC only | None | AC bandwidth/filter setting for AC current and AC voltage. Omit to leave the instrument default/current setting unchanged. |
| `--current-terminal 3\|10` | Current only | `3` | Current input terminal. The 10 A range requires `--current-terminal 10`; `--current-terminal 10` is valid only with the 10 A range. |
| `--dcv-input-impedance default\|10m\|auto` | DC Voltage or DCV Ratio only | `default` | DC voltage input impedance. `default` writes no impedance command; `10m` forces 10 MOhm; `auto` enables the instrument Auto mode, which may show HighZ on low DC voltage ranges. |
| `--vm-comp-slope pos\|neg` | No | None | Configure rear-panel VM Comp output pulse slope. Omit to leave VM Comp unchanged. |

`--measurement` defaults to `current-dc`, so existing current logging commands do
not need to specify it. New commands should prefer `--range`; `--current-range`
continues to work for existing DC current scripts. Use `--range` for
`current-ac`, `voltage-dc`, `voltage-dc-ratio`, `voltage-ac`, `resistance-2w`, and
`resistance-4w`; `--current-range` is rejected with those measurements.
`--dcv-input-impedance` is valid only with `--measurement voltage-dc` or
`--measurement voltage-dc-ratio`. Use `default` to leave the instrument's
current Input Z setting unchanged, `10m` to force 10 MOhm, or `auto` to enable
the 34461A Auto Input Z behavior. The instrument may display HighZ while Auto
is active on lower DC voltage ranges.

## Agent-Friendly CLI Workflows

Use `--dry-run` to validate a command and inspect the planned SCPI/read path
without touching the instrument:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --max-samples 1 `
  --dry-run `
  --status-format jsonl
```

Use `--simulate` for workflow checks without a real VISA session:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "SIM::34461A" `
  --csv ".\data\simulate.csv" `
  --trigger-mode immediate `
  --measurement current-dc `
  --max-samples 2 `
  --simulate `
  --status-format jsonl
```

JSONL output is one JSON object per line. It is intended for agents and scripts;
the default text output remains the human-facing interface. Simulator values are
deterministic workflow data, not real 34461A measurement validation.

Machine callers should parse JSONL, single-response JSON, CSV files, and wrapper
`report.json` artifacts for decisions. Human text messages are diagnostic and
may change for readability.

See [Meters CLI JSON / JSONL Contract](../../../docs/contracts/meters-cli-jsonl-contract.md) for the current schema
and alias rules.

See [Meters Worker Contract](../../../docs/contracts/meters-worker-contract.md) for the Meters worker modes, local
control endpoints, status payload, and wrapper artifact/report schema.

When the worker is running, `status` wraps non-mutating `GET /status` and
returns normalized JSON for orchestration health checks:

```powershell
.\.venv\Scripts\keysight-logger.exe status --port 8765 --json
```

Recommended orchestrator flow:

1. Run `start-trigger-record --dry-run --status-format jsonl` and validate the
   plan object.
2. Run the same command with `--simulate --status-format jsonl` and a finite
   bound such as `--max-samples`.
3. For live acquisition, start the worker with an explicit `--resource`; do not
   scan, infer, or guess the VISA resource in an unattended live run.
4. Wait for the JSONL `ready` event or run `wait-ready --port 8765 --json`,
   then call `status --port 8765 --json` to verify the `run_id`.
5. Use `POST /command` only for software-triggered modes, and `POST /stop` for
   graceful stop.
6. Read stdout JSONL plus CSV and wrapper artifacts such as `report.json` for
   pass/fail decisions.

See [Meters Orchestrator Workflows](../../../docs/contracts/meters-orchestrator-workflows.md) for a complete
Python subprocess workflow.

The `ready` event and `wait-ready` mean the local control plane can accept
`/command`, `/stop`, and `/status` requests. They are not first-sample signals.
Use the JSONL `run_id` as the correlation key between stdout runtime events,
`status` or direct `GET /status`, and wrapper artifacts from the same run.

### send-command --format json

```powershell
.\.venv\Scripts\keysight-logger.exe send-command --port 8765 --format json
```

Output:

```json
{"event": "send-command", "http_status": 202, "message": "command accepted",
 "schema_version": 1, "status": "accepted", "timestamp_utc": "2026-05-18T..."}
```

Invalid `--arguments-json` JSON exits with code 2. Connection or request failures exit
with code 3. Both emit structured error JSON objects.

### stop --format json

```powershell
.\.venv\Scripts\keysight-logger.exe stop --port 8765 --format json
```

Output:

```json
{"event": "stop", "http_status": 202, "message": "stop accepted",
 "schema_version": 1, "status": "accepted", "timestamp_utc": "2026-05-18T..."}
```

If the endpoint is not listening (process already stopped), exits with code 0
and emits `{"status": "already_stopped", ...}`.

### status --format json

```powershell
.\.venv\Scripts\keysight-logger.exe status --port 8765 --format json
```

Output includes `event: "status"`, `reachable`, `ok`, `running`,
`stopping`, `run_id`, worker URLs, queue fields, `captured`, `errors`, and
`fatal_error`. `ok` is worker health: it is `true` only when the endpoint is
reachable and `fatal_error` is `null`.

### wait-ready --format json

```powershell
.\.venv\Scripts\keysight-logger.exe wait-ready --port 8765 --timeout-ms 10000 --format json
```

`wait-ready` succeeds on any valid `200` JSON response from `/status` and adds
`attempts`, `elapsed_ms`, and `timeout_ms` to the normalized status object.
Timeout or invalid status JSON exits with code 3.

### Exit Codes

| Code | Meaning |
| --- | --- |
| `0` | Success, including reachable `status` with `fatal_error` and `stop` when the endpoint is already stopped. |
| `2` | Validation or usage error before the requested operation runs. |
| `3` | Runtime, connection, HTTP request failure, invalid `/status` JSON, or `wait-ready` timeout. |


## Validated Argument Limits

The CLI validates user input before opening the instrument. Values outside these
ranges fail fast with a clear error.

| Argument | Accepted values |
| --- | --- |
| `--measurement` | `current-dc`, `voltage-dc`, `voltage-dc-ratio`, `current-ac`, `voltage-ac`, `resistance-2w`, `resistance-4w` |
| `--auto-zero` | `on`, `off`, or `once`, with measurement-specific limits |
| `--auto-range` | `on` or `off` |
| `--ac-bandwidth-hz` | `3`, `20`, or `200`, AC current/voltage only |
| `--current-terminal` | `3` or `10`, current measurements only |
| `--status-format` | `text` or `jsonl` |
| `--timeout-ms` | `100` to `600000` |
| `--trigger-timeout-ms` | `500` to `600000` |
| `--sw-trigger-port` | `0`, or `1024` to `65535`; `0` lets the server choose |
| `--sw-min-interval-ms` | `0`, or `50` to `600000`; `0` disables throttling |
| `--sw-queue-max` | `0` to `10000`; `0` uses the default safety cap |
| `--max-samples` | `1` to `1000000`, simple modes only |
| `--trigger-count`, `--sample-count` | `1` to `1000000`, custom modes only |
| `--timer-interval-s` | `0.5` to `86400` seconds, software mode only |
| `--buffer-drain-size` | `1` to `10000`, custom modes only and capped by reading memory |
| `--hw-trigger-delay-s` | `0` to `3600` seconds |
| `send-command --port`, `stop --port`, `status --port`, `wait-ready --port` | `1` to `65535` |
| `send-command --timeout-ms`, `stop --timeout-ms`, `status --timeout-ms`, `wait-ready --timeout-ms` | `100` to `600000` |
| `send-command --format`, `stop --format`, `status --format`, `wait-ready --format` | `text` or `json` |

For Agent or automation use, `start-trigger-record --status-format jsonl` and
the `--json` alias emit one `ready` event after the local HTTP control plane
starts. The event includes `command_url`, `stop_url`, and `status_url`. Treat it
as the signal that `/command`, `/stop`, and non-mutating `/status` requests can
be sent; it is not a first-sample or measurement-complete signal.

`--trigger-timeout-ms` is most important for external trigger modes. If it is
shorter than the expected time between external edges, the console will keep
printing hardware trigger timeout/re-arm status and no capture may occur until a
future edge arrives inside the timeout window. In software mode, this value is
used only as part of the worker polling cadence and is capped internally at
200 ms per wait; it is not a measurement-completion timeout.

For Agent or automation use, classify trigger wait outcomes conservatively:
an external trigger edge that has not arrived yet is a normal waiting condition,
not an error. In simple external mode, repeated PyVISA status-byte poll timeouts
are diagnosed without becoming fatal acquisition failures: the 5th consecutive
timeout emits a warning, the 25th consecutive timeout increments `errors` and
emits a degraded status, and every additional 25 consecutive timeouts increments
`errors` again. A successful status-byte poll resets the consecutive timeout
count. Actual `READ?`, `FETC?`, connection, identity, or SCPI command failures
are acquisition errors and may be fatal.

Manual range values are whitelisted per measurement type:

| Measurement | Allowed `--range` values |
| --- | --- |
| `current-dc` | `0.0001`, `0.001`, `0.01`, `0.1`, `1`, `3`, `10` A |
| `current-ac` | `0.0001`, `0.001`, `0.01`, `0.1`, `1`, `3`, `10` A |
| `voltage-dc` | `0.1`, `1`, `10`, `100`, `1000` V |
| `voltage-dc-ratio` | `0.1`, `1`, `10`, `100`, `1000` V |
| `voltage-ac` | `0.1`, `1`, `10`, `100`, `750` V |
| `resistance-2w` | `100`, `1000`, `10000`, `100000`, `1000000`, `10000000`, `100000000` Ohm |
| `resistance-4w` | `100`, `1000`, `10000`, `100000`, `1000000`, `10000000`, `100000000` Ohm |

Additional validation rules:

- `--auto-range off` requires a manual range. For `current-dc`, either
  `--range` or the compatibility alias `--current-range` is accepted. For all
  other measurements, use `--range`.
- `--range` and `--current-range` cannot be used together.
- `--current-range` is valid only with `--measurement current-dc`.
- `--dcv-input-impedance` values other than `default` are valid only with
  `--measurement voltage-dc` or `--measurement voltage-dc-ratio`.
- DC, DCV ratio, and resistance measurements accept only these NPLC values:
  `0.02`, `0.2`, `1`, `10`, `100`.
- AC current and AC voltage reject non-default NPLC values. Omit `--nplc` or
  pass `--nplc 1.0`.
- `--auto-zero once` is valid only with `current-dc`, `voltage-dc`, and
  `resistance-2w`.
- `voltage-dc-ratio` accepts only default/on Auto Zero behavior.
- `--ac-bandwidth-hz` is valid only with `current-ac` or `voltage-ac`.
- `--current-terminal` is valid only with current measurements. The 10 A range
  requires `--current-terminal 10`, and `--current-terminal 10` requires the
  10 A range.
- Custom modes require both `--trigger-count` and `--sample-count`; simple modes
  reject both options.
- Custom modes reject `--max-samples`; simple modes use `--max-samples` for
  bounded runs.
- `--buffer-drain-size` and `--allow-buffer-overflow-risk` are valid only with
  custom modes.
- Custom modes reject `trigger_count * sample_count > 10000` for the 34461A
  unless `--allow-buffer-overflow-risk` is set.
- `--timer-interval-s` requires software mode. It is valid with the default
  trigger mode because omitted `--trigger-mode` resolves to `software`. It may
  be combined with `--max-samples` to stop after a fixed number of timer rows.

## Examples

These examples are ordered as a practical validation path: first identify a live
resource, then run one-sample smoke checks, then use the trigger mode that fits
the experiment. The USB resource shown below is the 34461A used during project
validation; replace resource strings and CSV paths with values appropriate for
your instrument and test run.

### List VISA Resources

```powershell
.\.venv\Scripts\keysight-logger.exe list-resources
```

Verify which resources are live:

```powershell
.\.venv\Scripts\keysight-logger.exe list-resources --verify
```

Successful verified resources are released back to local on a best-effort basis
before the scan session closes. Stale resources that fail the IDN query are
closed without release SCPI.

Show only live resources and hide stale VISA cache entries:

```powershell
.\.venv\Scripts\keysight-logger.exe list-resources --live-only
```

Use JSON output for scripts:

```powershell
.\.venv\Scripts\keysight-logger.exe list-resources --verify --format json
```

Preview the discovery contract without touching VISA:

```powershell
.\.venv\Scripts\keysight-logger.exe list-resources --dry-run --live-only --json
```

Verified output is tab-separated:

```text
live    USB0::<vendor_id>::<product_id>::<serial>::0::INSTR    Keysight Technologies,34461A,...
stale   USB0::OLD::RESOURCE::INSTR                     VisaIOError: ...
```

`--live-only` still verifies each resource, but suppresses stale rows. If no
resource answers, text output prints:

```text
no live VISA resources found
```

Verified JSON output is a single object:

```json
{
  "resources": [
    {
      "detail": "Keysight Technologies,34461A,...",
      "live": true,
      "resource": "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR",
      "status": "live"
    }
  ],
  "verify": true
}
```

`--live-only --format json` keeps the same resource record shape, filters out
stale entries, and adds `live_only`:

```json
{
  "live_only": true,
  "resources": [
    {
      "detail": "Keysight Technologies,34461A,...",
      "live": true,
      "resource": "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR",
      "status": "live"
    }
  ],
  "verify": true
}
```

Example resource strings:

```text
USB0::<vendor_id>::<product_id>::<serial>::0::INSTR
TCPIP0::<host>::hislip0::INSTR
```

### Real-Instrument Validation Path

Use this order when checking a setup:

1. Run `list-resources --live-only` and choose a live resource. Use
   `list-resources --verify` instead when you need to diagnose stale VISA cache
   entries.
2. Run a one-sample current, voltage, or resistance smoke test with
   `--trigger-mode immediate` and `--max-samples 1`.
3. Run the specific trigger mode needed for the experiment: software, timer,
   external, immediate, or custom/buffered.
4. Confirm the CSV `measurement_type`, `unit`, `trigger_source`, and row count.
5. Confirm graceful stop behavior with `stop`, Ctrl+C, Ctrl+Break, or `q`
   before relying on long unattended runs.

Before relying on unattended acquisition, validate the workflow with an
operator-provided Keysight 34461A VISA resource. Start with immediate mode, Auto
Range on, and `--max-samples 1`, then expand to the intended measurement,
trigger mode, and buffered mode. For AC current and AC voltage, compare the CLI
CSV row to the 34461A front-panel reading during the smoke test.

### Current DC Smoke Test

One immediate current sample:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\current_smoke.csv" `
  --trigger-mode immediate `
  --measurement current-dc `
  --auto-range off `
  --range 0.1 `
  --auto-zero off `
  --nplc 1.0 `
  --max-samples 1
```

For current rows, expect `measurement_type=current_dc` and `unit=A` in the CSV.

Dry-run 10 A terminal check:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --trigger-mode immediate `
  --measurement current-dc `
  --auto-range off `
  --range 10 `
  --current-terminal 10 `
  --max-samples 1 `
  --dry-run `
  --status-format jsonl
```

Simulated 10 A terminal workflow check:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "SIM::34461A" `
  --csv ".\data\simulate_current_10a_terminal.csv" `
  --trigger-mode immediate `
  --measurement current-dc `
  --auto-range off `
  --range 10 `
  --current-terminal 10 `
  --max-samples 1 `
  --simulate `
  --status-format jsonl
```

Live 10 A terminal smoke check. Run this only after the operator has confirmed
the current path is safe for the 10 A input terminal and expected current.

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\current_10a_terminal_smoke.csv" `
  --trigger-mode immediate `
  --measurement current-dc `
  --auto-range off `
  --range 10 `
  --current-terminal 10 `
  --auto-zero once `
  --nplc 1.0 `
  --max-samples 1 `
  --status-format jsonl
```

### Software Trigger, Bounded Run

Terminal 1, start recording and wait for five software triggers:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\software_5.csv" `
  --trigger-mode software `
  --max-samples 5 `
  --measurement current-dc `
  --auto-range off `
  --range 0.1 `
  --auto-zero on `
  --nplc 1.0
```

Terminal 2, send one software trigger:

```powershell
.\.venv\Scripts\keysight-logger.exe send-command --port 8765
```

Run the `send-command` command five times. The logger stops automatically after
five successful samples because of `--max-samples 5`.

### Validated Voltage DC Smoke Tests

These two voltage commands were reported OK on a real 34461A: Auto Range,
manual 10 V range, and CSV fields/values all looked normal.

Additional voltage trigger checks were also reported OK on the same instrument:
software trigger with 1-2 rows, software timer with 2-3 rows, and external
trigger with one external edge. Rough checks with `voltage-dc` plus
`immediate-custom`, `software-custom`, and `external-custom` were also normal.

Dry-run Auto Zero once check:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --auto-zero once `
  --max-samples 1 `
  --dry-run `
  --status-format jsonl
```

Simulated Auto Zero once workflow check:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "SIM::34461A" `
  --csv ".\data\simulate_voltage_auto_zero_once.csv" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --auto-zero once `
  --max-samples 1 `
  --simulate `
  --status-format jsonl
```

Auto range, one immediate voltage sample:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\voltage_auto_smoke.csv" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --auto-range on `
  --auto-zero off `
  --nplc 1.0 `
  --max-samples 1
```

Manual 10 V range, one immediate voltage sample:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\voltage_range10_smoke.csv" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --auto-range off `
  --range 10 `
  --auto-zero off `
  --nplc 1.0 `
  --max-samples 1
```

Live Auto Zero once smoke check:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\voltage_auto_zero_once_smoke.csv" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --auto-range on `
  --auto-zero once `
  --nplc 1.0 `
  --max-samples 1 `
  --status-format jsonl
```

For voltage rows, expect `measurement_type=voltage_dc` and `unit=V` in the CSV.
Voltage can also be selected with custom/buffered modes through
`--measurement voltage-dc`; those paths use the same measurement configuration
and the existing custom-mode trigger/read flow. Run a longer buffered validation
with the operator-provided VISA resource before relying on voltage buffered
acquisition for production runs.

DCV Input Z smoke check, Auto mode:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\voltage_dcv_input_z_auto_smoke.csv" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --auto-range on `
  --dcv-input-impedance auto `
  --auto-zero off `
  --nplc 1.0 `
  --max-samples 1
```

DCV Input Z smoke check, fixed 10 MOhm:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\voltage_dcv_input_z_10m_smoke.csv" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --auto-range on `
  --dcv-input-impedance 10m `
  --auto-zero off `
  --nplc 1.0 `
  --max-samples 1
```

For these checks, confirm the front panel Input Z state changes as expected:
`auto` should select Auto and may show HighZ on lower DC voltage ranges, while
`10m` should select fixed 10 MOhm. These two DCV Input Z smoke checks were
reported OK on a real 34461A before the `v1.0.0-cli` baseline.

### DCV Ratio Smoke Tests

DCV Ratio uses the 34461A `VOLT:DC:RAT` function. Connect the signal and
reference leads according to the instrument manual before running live; a
miswired ratio measurement can look numerically plausible while measuring the
wrong relationship.

Dry-run DCV Ratio check:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --trigger-mode immediate `
  --measurement voltage-dc-ratio `
  --max-samples 1 `
  --dry-run `
  --status-format jsonl
```

Simulated DCV Ratio workflow check:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "SIM::34461A" `
  --csv ".\data\simulate_voltage_dc_ratio.csv" `
  --trigger-mode immediate `
  --measurement voltage-dc-ratio `
  --max-samples 1 `
  --simulate `
  --status-format jsonl
```

Live DCV Ratio smoke check:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\voltage_dc_ratio_smoke.csv" `
  --trigger-mode immediate `
  --measurement voltage-dc-ratio `
  --auto-range on `
  --nplc 1.0 `
  --max-samples 1 `
  --status-format jsonl
```

For DCV Ratio rows, expect `measurement_type=voltage_dc_ratio`, `unit=ratio`,
and CSV/JSONL `measurement_metadata` containing signal/reference voltage fields
when the backend supports `DATA2?`.

### AC Current And Voltage Smoke Tests

AC current and AC voltage use the same trigger/read flow as other scalar
measurements. They configure the 34461A AC function, Auto Range/manual range,
and optional AC bandwidth. The CLI does not write NPLC or Auto Zero SCPI for AC
measurements. For live smoke testing, start with immediate mode, Auto Range on,
and `--max-samples 1`, then compare the CLI CSV row to the 34461A front-panel
reading.

Dry-run AC bandwidth check:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --trigger-mode immediate `
  --measurement voltage-ac `
  --ac-bandwidth-hz 20 `
  --max-samples 1 `
  --dry-run `
  --status-format jsonl
```

Simulated AC bandwidth workflow check:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "SIM::34461A" `
  --csv ".\data\simulate_voltage_ac_bw20.csv" `
  --trigger-mode immediate `
  --measurement voltage-ac `
  --ac-bandwidth-hz 20 `
  --max-samples 1 `
  --simulate `
  --status-format jsonl
```

Suggested Auto Range AC voltage smoke test:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\voltage_ac_auto_smoke.csv" `
  --trigger-mode immediate `
  --measurement voltage-ac `
  --ac-bandwidth-hz 20 `
  --auto-range on `
  --max-samples 1
```

Suggested manual-range AC current smoke test:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\current_ac_range100ma_smoke.csv" `
  --trigger-mode immediate `
  --measurement current-ac `
  --auto-range off `
  --range 0.1 `
  --max-samples 1
```

For AC rows, expect `measurement_type=voltage_ac` with `unit=V`, or
`measurement_type=current_ac` with `unit=A`. During live smoke testing, compare
the CLI CSV row to the 34461A front-panel reading before relying on longer
acquisitions.

### Validated Resistance 2-Wire Smoke Tests

These two resistance commands were reported OK on a real 34461A: Auto Range,
manual 1000 Ohm range, and CSV fields/values all looked normal.

Auto range, one immediate resistance sample:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\resistance_2w_auto_smoke.csv" `
  --trigger-mode immediate `
  --measurement resistance-2w `
  --auto-range on `
  --auto-zero off `
  --nplc 1.0 `
  --max-samples 1
```

Manual 1000 Ohm range, one immediate resistance sample:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\resistance_2w_range1000_smoke.csv" `
  --trigger-mode immediate `
  --measurement resistance-2w `
  --auto-range off `
  --range 1000 `
  --auto-zero off `
  --nplc 1.0 `
  --max-samples 1
```

For resistance rows, expect `measurement_type=resistance_2w` and `unit=Ohm` in
the CSV. The measured value should be plausible for the connected resistor or
open/fixture condition. `resistance-2w` can also be selected with the existing
software, timer, external, and custom/buffered modes; run a focused
real-instrument check before relying on those resistance trigger paths in
production.

### Resistance 4-Wire Smoke Tests

These commands use the same trigger/read flow as other scalar measurements, but
the 4-wire SCPI function is `FRES`. The CLI does not write `FRES:ZERO:AUTO`
because the 34461A handles 4-wire resistance Auto Zero internally. These smoke
tests were reported OK on a real 34461A after removing `FRES:ZERO:AUTO`.

Auto range, one immediate 4-wire resistance sample:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\resistance_4w_auto_smoke.csv" `
  --trigger-mode immediate `
  --measurement resistance-4w `
  --auto-range on `
  --nplc 1.0 `
  --max-samples 1
```

Manual 1000 Ohm range, one immediate 4-wire resistance sample:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\resistance_4w_range1000_smoke.csv" `
  --trigger-mode immediate `
  --measurement resistance-4w `
  --auto-range off `
  --range 1000 `
  --nplc 1.0 `
  --max-samples 1
```

For 4-wire resistance rows, expect `measurement_type=resistance_4w` and
`unit=Ohm` in the CSV. Use Kelvin leads or the appropriate HI/LO Sense wiring
for the selected front or rear terminals.

### Software Trigger With Metadata

```powershell
.\.venv\Scripts\keysight-logger.exe send-command `
  --port 8765 `
  --arguments-json "{""metadata"":{""batch"":""A1"",""operator"":""lab""}}"
```

The metadata is accepted by the command endpoint and written to the CSV
`trigger_metadata` field as a JSON object string.

### Software Trigger Rate Limit And Queue Limit

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\software_limited.csv" `
  --trigger-mode software `
  --sw-min-interval-ms 250 `
  --sw-queue-max 10 `
  --max-samples 10
```

If triggers arrive faster than `--sw-min-interval-ms` or the software queue is
full, the HTTP endpoint returns `429`.

### Software Timer, Bounded Run

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\software_timer_100.csv" `
  --trigger-mode software `
  --timer-interval-s 1.0 `
  --max-samples 100 `
  --auto-range off `
  --range 0.1 `
  --auto-zero off `
  --nplc 1.0
```

This mode is PC-controlled and uses `READ?`. It is intended as a convenience
logger, not a no-loss precision timing mode.

### External Hardware Trigger, Bounded Run

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\external_10.csv" `
  --trigger-mode external `
  --max-samples 10 `
  --hw-trigger-slope neg `
  --trigger-timeout-ms 10000 `
  --auto-range off `
  --range 0.1 `
  --auto-zero on `
  --nplc 1.0
```

Each accepted external trigger edge should produce one CSV row with
`trigger_source=hardware`. Hardware trigger timeout is treated as a normal
protective re-arm condition; it should not be counted as an error by itself.

### Immediate Mode, Bounded Run

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\immediate_100.csv" `
  --trigger-mode immediate `
  --max-samples 100 `
  --auto-range off `
  --range 0.1 `
  --auto-zero off `
  --nplc 1.0
```

Immediate mode does not wait for `send-command` or external trigger edges. Use
`--max-samples` to avoid an accidental long continuous run.

### Immediate Custom Mode

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\immediate_custom_1000.csv" `
  --trigger-mode immediate-custom `
  --trigger-count 1 `
  --sample-count 1000 `
  --auto-range off `
  --range 0.1 `
  --auto-zero off `
  --nplc 1.0
```

This mode uses 34461A reading memory to reduce per-sample `READ?` communication
overhead. It is not an instrument internal timer mode: sample cadence is still
set by measurement speed, DC/resistance NPLC and Auto Zero, Auto Range, range
settling, and instrument trigger/sample behavior. CSV `trigger_metadata` marks
custom rows with `time_basis=pc_data_remove_time_not_instrument_sample_time`.
The expected row count is `trigger_count * sample_count`. Requests above the
34461A 10,000-reading memory limit are rejected unless
`--allow-buffer-overflow-risk` is set.

### Software Custom Mode

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\software_custom_20.csv" `
  --trigger-mode software-custom `
  --trigger-count 2 `
  --sample-count 10 `
  --auto-range off `
  --range 0.1 `
  --auto-zero off `
  --nplc 1.0
```

From another PowerShell window, send one bus trigger per requested trigger:

```powershell
.\.venv\Scripts\keysight-logger.exe send-command
.\.venv\Scripts\keysight-logger.exe send-command
```

This mode arms the DMM with `TRIG:SOUR BUS`, `TRIG:COUNT`, and `SAMP:COUNT`.
Each accepted HTTP `send-command` sends one `*TRG`. The expected row count is
still `trigger_count * sample_count`; `trigger_count=2` and `sample_count=10`
should produce 20 CSV rows.

### External Custom Mode

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\external_custom_10.csv" `
  --trigger-mode external-custom `
  --trigger-count 1 `
  --sample-count 10 `
  --hw-trigger-slope neg `
  --hw-trigger-delay-s 0 `
  --auto-range off `
  --range 0.1 `
  --auto-zero off `
  --nplc 1.0
```

This mode arms the DMM with `TRIG:SOUR EXT`, `TRIG:SLOP`, `TRIG:COUNT`,
`SAMP:COUNT`, and `TRIG:DEL`, then drains completed readings from memory with
`DATA:POINts?` / `DATA:REMove?`. Each external trigger edge advances the DMM
trigger sequence. The expected row count is `trigger_count * sample_count`;
`trigger_count=1` and `sample_count=10` should produce 10 CSV rows after one
external edge.

### LAN Resource Example

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "TCPIP0::<host>::hislip0::INSTR" `
  --csv ".\data\lan_software.csv" `
  --trigger-mode software `
  --max-samples 5
```

If `list-resources` still shows an old USB resource after unplugging, show only
resources that still answer with:

```powershell
.\.venv\Scripts\keysight-logger.exe list-resources --live-only
```

Use `list-resources --verify` when you want to see both live and stale entries
for diagnosis.

### Slower High-Accuracy DC/Resistance Setup

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\software_high_accuracy.csv" `
  --trigger-mode software `
  --auto-range off `
  --range 0.1 `
  --auto-zero on `
  --nplc 10.0
```

`--nplc 10.0` with `--auto-zero on` is slow for DC/resistance measurements. For
faster external trigger pacing, consider lower NPLC and Auto Zero off, for
example `--nplc 1.0 --auto-zero off`. AC measurements do not use Auto Zero and
accept only neutral `--nplc 1.0`.

### VM Comp Slope

Omit `--vm-comp-slope` unless you need to configure the rear-panel VM Comp output
pulse slope.

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\vm_comp_pos.csv" `
  --trigger-mode software `
  --max-samples 5 `
  --vm-comp-slope pos
```

## Stopping A Run

The logger prints the local control endpoints when it starts:

```text
command endpoint: http://127.0.0.1:8765/command
software stop endpoint: http://127.0.0.1:8765/stop
software status endpoint: http://127.0.0.1:8765/status
local stop keys: Ctrl+C, Ctrl+Break, q
```

Stop from another terminal:

```powershell
.\.venv\Scripts\keysight-logger.exe stop --port 8765
```

Other supported stop methods:

- Press Ctrl+C in the recording terminal.
- Press Ctrl+Break in the recording terminal.
- Press `q` in the recording terminal.
- Use `--max-samples N` so the worker stops after N successful captures.

Expected cleanup output includes:

```text
stop request received
recording stopped
release_to_local: ...
cleanup_release_to_local: ...
software trigger server stopped
```

If `stop` is sent after the logger already exited, it may print:

```text
already stopped (endpoint not listening)
```

That is treated as success.

## Console Status Output

During software-triggered runs, `waiting trigger` is printed once for each
continuous wait period instead of repeating on every short poll timeout.
`software-custom` mode follows the same policy for
`waiting software custom trigger`.

For Agent automation, human-readable status lines can help diagnose waiting and
polling behavior, but stable pass/fail decisions should still rely on process
exit code, CSV row count, `captured=X errors=Y`, and explicit fatal error text.

Successful captures print the count and latest display value, for example:

```text
[status] captured=1 value=12.3 mA
[status] captured=2 value=1.23 kOhm
```

Display prefixes such as `mA`, `mV`, `kOhm`, and `MOhm` are console-only. CSV
rows continue to store the raw value in the measurement base unit (`A`, `V`,
`ratio`, or `Ohm`). Custom/buffered modes may drain multiple readings at once;
the console status shows the last sample in that drain batch.

## CSV Output

If `--csv` is omitted, the logger writes to a UTC+8 timestamped file under
`data`, for example `data/2026-05-11-14-30-05.csv`. Passing `--csv PATH`
continues to write to that exact path.

CSV fields:

| Field | Description |
| --- | --- |
| `timestamp_utc_plus_8` | UTC+8 timestamp when the sample was read, serialized as ISO 8601 with a `+08:00` offset. |
| `measurement_type` | Selected measurement type, such as `current_dc`, `voltage_dc`, `voltage_dc_ratio`, `current_ac`, `voltage_ac`, `resistance_2w`, or `resistance_4w`. |
| `value` | Measured value. |
| `unit` | Unit, `A` for current, `V` for voltage, `ratio` for DCV Ratio, and `Ohm` for resistance. |
| `trigger_id` | UUID assigned to the trigger event. |
| `trigger_source` | `software`, `timer`, `hardware`, `immediate`, `immediate-custom`, `software-custom`, or `external-custom`. |
| `trigger_metadata` | JSON object string from `send-command --arguments-json`, or `{}`. |
| `measurement_metadata` | JSON object string for measurement-specific context, or `{}`. DCV Ratio can include signal/reference voltage fields from `DATA2?`. |
| `resource_id` | VISA resource used for the run. |
| `status` | Sample status, currently `ok` for successful captures. |

## Troubleshooting

- If `uv` warns that hardlinking failed and it is falling back to copying
  files, the install usually still succeeded. On cross-drive or
  hardlink-restricted setups, rerun install with
  `uv pip install -e ".[dev]" --link-mode=copy`.
- If `.\.venv\Scripts\keysight-logger.exe` is missing, rerun
  `uv pip install -e ".[dev]"`. The console script is an install artifact, not
  a tracked project file.
- If PowerShell activation is blocked, keep using explicit
  `.\.venv\Scripts\python.exe` or `.\.venv\Scripts\keysight-logger.exe`
  commands instead of activating the environment.
- If no VISA resources appear, confirm the VISA runtime is installed and the
  instrument is visible in the vendor connection utility.
- If `list-resources` shows stale cached resources, run `list-resources --live-only`
  to hide stale entries. Use `list-resources --verify` when you need to inspect
  stale-resource errors.
- If the CLI says it cannot open the CSV output file, close the file in Excel
  or any other program, or choose a different `--csv` path.
- If `--auto-range off` is used, `--range` or `--current-range` is required.
- If `--dcv-input-impedance` is used with anything other than
  `--measurement voltage-dc` or `--measurement voltage-dc-ratio`, the CLI
  rejects the command.
- If external trigger edges are missed with high accuracy DC/resistance
  settings, try `--nplc 1.0 --auto-zero off` before changing trigger behavior.
- If a long-running Windows console appears frozen, make sure QuickEdit/text
  selection is not pausing the terminal.

## Tests

Install development dependencies with `uv pip install -e ".[dev]"` as shown in
the Development section before running tests.

Default pytest run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

Unittest discovery, matching GitHub Actions:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```
