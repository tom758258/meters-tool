# Keysight 34461A CLI Logger

CLI-first Python logger for Keysight 34461A DC current measurements over VISA.
It records one CSV row per captured sample and supports software, external
hardware, and immediate trigger modes.

## Current Scope

Implemented:

- VISA resource listing for USB and LAN resources discovered by PyVISA.
- DC current measurement logging.
- Software trigger mode through a local HTTP endpoint.
- Software timer capture as part of software trigger mode.
- External hardware trigger mode.
- Immediate capture mode.
- Bounded runs with `--max-samples`.
- Graceful stop through HTTP, Ctrl+C, Ctrl+Break, or `q`.
- Software trigger metadata persisted to CSV as `trigger_metadata`.
- Optional resource verification with `list-resources --verify`.
- Optional measurement controls: Auto Range, manual current range, Auto Zero,
  NPLC, hardware trigger delay, hardware trigger slope, and VM Comp slope.
- Immediate CSV flush after every captured sample.

Important limitations:

- This project is currently focused on Keysight 34461A current logging.
- Mixed software and hardware capture in the same run is not supported.
- Plain `list-resources` calls VISA discovery directly and may show stale
  resources cached by the VISA runtime. Use `list-resources --verify` to open
  each resource and query `*IDN?`.
- `immediate` mode can capture continuously and quickly. Use `--max-samples`
  unless you intentionally want a continuous run.

## Requirements

- Python 3.10 or newer.
- A VISA runtime, such as Keysight IO Libraries Suite or NI-VISA.
- A Keysight 34461A visible to VISA over USB or LAN.

## Install

Windows PowerShell, without relying on activation:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e .
```

For tests:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Optional activation:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation because of execution policy, use the explicit
`.\.venv\Scripts\python.exe` commands shown above.

## Basic Workflow

1. List VISA resources.
2. Choose a resource string.
3. Start `start-trigger-record` in one terminal.
4. Send triggers, wait for external trigger edges, or use immediate mode.
5. Stop with `soft-stop`, Ctrl+C, Ctrl+Break, `q`, or `--max-samples`.
6. Inspect the CSV output.

## Command Reference

Use the module form unless this project later adds a console script:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli <command> [options]
```

| Command | Purpose | Typical use |
| --- | --- | --- |
| `list-resources` | Print VISA resources discovered by PyVISA. | Find the USB or LAN resource string. Add `--verify` to query `*IDN?`. |
| `start-trigger-record` | Connect to the instrument and record samples to CSV. | Main logging command. |
| `soft-trigger` | POST one software trigger to the local trigger endpoint. | Used with `--trigger-mode software`. |
| `soft-stop` | POST a graceful stop request to the local stop endpoint. | Stop a running logger from another terminal. |

## Trigger Modes

| Mode | How capture starts | Read path | CSV `trigger_source` | Notes |
| --- | --- | --- | --- | --- |
| `software` | `soft-trigger` posts to the local HTTP endpoint, or `--timer-interval-s` creates automatic timer events. | `READ?` | `software` or `timer` | Default when `--trigger-mode` is omitted. Timer mode uses fixed-delay spacing after each capture attempt. |
| `external` | The instrument receives an external hardware trigger edge. | `FETC?` | `hardware` | `--enable-hw-trigger` is the legacy alias for this mode. |
| `immediate` | The worker captures without waiting for a trigger event. | `READ?` | `immediate` | Use `--max-samples` for bounded runs. |
| `immediate-custom` | The instrument runs an explicit immediate trigger/sample sequence and stores readings in memory. | `INIT` + `DATA:POINts?` / `DATA:REMove?` | `immediate-custom` | Requires `--trigger-count` and `--sample-count`; `--max-samples` is not valid. |
| `software-custom` | The instrument is armed for bus triggers; each accepted `soft-trigger` sends `*TRG`. | `INIT` + `*TRG` + `DATA:POINts?` / `DATA:REMove?` | `software-custom` | Requires `--trigger-count` and `--sample-count`; `--max-samples` and `--timer-interval-s` are not valid. |
| `external-custom` | The instrument is armed for external trigger edges and stores readings in memory. | `INIT` + external edge + `DATA:POINts?` / `DATA:REMove?` | `external-custom` | Requires `--trigger-count` and `--sample-count`; `--max-samples` and `--timer-interval-s` are not valid. |

In `external` mode, accidental software triggers are ignored and should not
break the hardware-trigger flow. In `immediate` mode, software triggers are also
ignored.

When `--timer-interval-s` is active, ordinary `soft-trigger` requests are
ignored while `soft-stop` still stops the run. The first timer sample is captured
when recording starts; each later timer sample waits at least the configured
interval after the previous capture attempt finishes.

## `start-trigger-record` Options

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `--resource RESOURCE` | Yes | None | VISA resource string, for example USB or TCPIP HiSLIP. |
| `--csv PATH` | Yes | None | CSV output path. Parent directories are created automatically. |
| `--timeout-ms N` | No | `5000` | VISA session timeout in milliseconds. |
| `--trigger-timeout-ms N` | No | `10000` | External trigger wait timeout. Timeout re-arms hardware mode and is not itself a capture error. |
| `--sw-trigger-port N` | No | `8765` | Local HTTP port for `/trigger` and `/stop`. |
| `--sw-min-interval-ms N` | No | `0` | Minimum interval between accepted software triggers. `0` disables rate limiting. |
| `--sw-queue-max N` | No | `0` | Maximum queued software triggers. `0` means no queue limit. |
| `--trigger-mode software\|external\|immediate\|immediate-custom\|software-custom\|external-custom` | No | `software` | Select exactly one acquisition mode. |
| `--max-samples N` | No | None | Stop simple modes automatically after N successful CSV samples. Must be greater than 0. Not valid with custom modes. |
| `--trigger-count N` | Custom modes only | None | Instrument trigger count. Required with custom modes; not valid with simple modes. |
| `--sample-count N` | Custom modes only | None | Instrument sample count per trigger. Required with custom modes; not valid with simple modes. |
| `--timer-interval-s SECONDS` | No | None | Enable fixed-delay software timer capture. Must be greater than 0 and used only with software trigger mode. |
| `--buffer-drain-size N` | No | None | Maximum readings to remove per buffer drain. Advanced option valid only with custom modes; does not change `TRIG:COUNT`, `SAMP:COUNT`, or instrument reading memory capacity. |
| `--allow-buffer-overflow-risk` | No | Off | Allow custom modes to request more readings than the 34461A 10,000-reading memory limit. This depends on draining readings fast enough and may lose data or produce SCPI errors. |
| `--enable-hw-trigger` | No | Off | Legacy flag that maps to `--trigger-mode external`. Do not combine with `software` or `immediate`. |
| `--hw-trigger-slope pos\|neg` | No | `neg` | External trigger edge polarity. |
| `--hw-trigger-delay-s SECONDS` | No | `0.0` | Hardware trigger delay, mapped to `TRIG:DEL`. |
| `--nplc VALUE` | No | `1.0` | Current DC integration time in power-line cycles. Must be greater than 0. |
| `--auto-zero on\|off` | No | `on` | Enable or disable Auto Zero. |
| `--auto-range on\|off` | No | `on` | Enable or disable Auto Range. |
| `--current-range VALUE` | Required when `--auto-range off` | None | Manual current range in amps. |
| `--vm-comp-slope pos\|neg` | No | None | Configure rear-panel VM Comp output pulse slope. Omit to leave VM Comp unchanged. |

## Examples

Replace the resource strings and CSV paths with values appropriate for your
instrument and test run.

### List VISA Resources

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli list-resources
```

Verify which resources are live:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli list-resources --verify
```

Verified output is tab-separated:

```text
live    USB0::0x2A8D::0x1301::MYXXXXXXXX::0::INSTR    Keysight Technologies,34461A,..
stale   USB0::OLD::RESOURCE::INSTR                     VisaIOError:
```

Example resource strings:

```text
USB0::0x2A8D::0x1301::MYXXXXXXXX::0::INSTR
TCPIP0::169.254.x.x::hislip0::INSTR
```

### Software Trigger, Bounded Run

Terminal 1, start recording and wait for five software triggers:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::0x2A8D::0x1301::MYXXXXXXXX::0::INSTR" `
  --csv ".\data\software_5.csv" `
  --trigger-mode software `
  --max-samples 5 `
  --auto-range off `
  --current-range 0.1 `
  --auto-zero on `
  --nplc 1.0
```

Terminal 2, send one software trigger:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli soft-trigger --port 8765
```

Run the `soft-trigger` command five times. The logger stops automatically after
five successful samples because of `--max-samples 5`.

### Software Trigger With Metadata

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli soft-trigger `
  --port 8765 `
  --meta "{""batch"":""A1"",""operator"":""lab""}"
```

The metadata is accepted by the trigger endpoint and written to the CSV
`trigger_metadata` field as a JSON object string.

### Software Trigger Rate Limit And Queue Limit

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::0x2A8D::0x1301::MYXXXXXXXX::0::INSTR" `
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
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::0x2A8D::0x1301::MYXXXXXXXX::0::INSTR" `
  --csv ".\data\software_timer_100.csv" `
  --trigger-mode software `
  --timer-interval-s 1.0 `
  --max-samples 100 `
  --auto-range off `
  --current-range 0.1 `
  --auto-zero off `
  --nplc 1.0
```

This mode is PC-controlled and uses `READ?`. It is intended as a convenience
logger, not a no-loss precision timing mode.

### External Hardware Trigger, Bounded Run

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::0x2A8D::0x1301::MYXXXXXXXX::0::INSTR" `
  --csv ".\data\external_10.csv" `
  --trigger-mode external `
  --max-samples 10 `
  --hw-trigger-slope neg `
  --trigger-timeout-ms 10000 `
  --auto-range off `
  --current-range 0.1 `
  --auto-zero on `
  --nplc 1.0
```

Each accepted external trigger edge should produce one CSV row with
`trigger_source=hardware`. Hardware trigger timeout is treated as a normal
protective re-arm condition; it should not be counted as an error by itself.

### Legacy Hardware Trigger Flag

This is equivalent to `--trigger-mode external`:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::0x2A8D::0x1301::MYXXXXXXXX::0::INSTR" `
  --csv ".\data\external_legacy.csv" `
  --enable-hw-trigger `
  --max-samples 10
```

Do not combine `--enable-hw-trigger` with `--trigger-mode software`,
`--trigger-mode immediate`, `--trigger-mode immediate-custom`, or
`--trigger-mode software-custom`, or `--trigger-mode external-custom`.

### Immediate Mode, Bounded Run

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::0x2A8D::0x1301::MYXXXXXXXX::0::INSTR" `
  --csv ".\data\immediate_100.csv" `
  --trigger-mode immediate `
  --max-samples 100 `
  --auto-range off `
  --current-range 0.1 `
  --auto-zero off `
  --nplc 1.0
```

Immediate mode does not wait for `soft-trigger` or external trigger edges. Use
`--max-samples` to avoid an accidental long continuous run.

### Immediate Custom Mode

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::0x2A8D::0x1301::MYXXXXXXXX::0::INSTR" `
  --csv ".\data\immediate_custom_1000.csv" `
  --trigger-mode immediate-custom `
  --trigger-count 1 `
  --sample-count 1000 `
  --auto-range off `
  --current-range 0.1 `
  --auto-zero off `
  --nplc 1.0
```

This mode uses 34461A reading memory to reduce per-sample `READ?` communication
overhead. It is not an instrument internal timer mode: sample cadence is still
set by measurement speed, NPLC, Auto Zero, Auto Range, range settling, and
instrument trigger/sample behavior. CSV `trigger_metadata` marks custom rows
with `time_basis=pc_data_remove_time_not_instrument_sample_time`.
The expected row count is `trigger_count * sample_count`. Requests above the
34461A 10,000-reading memory limit are rejected unless
`--allow-buffer-overflow-risk` is set.

### Software Custom Mode

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::0x2A8D::0x1301::MYXXXXXXXX::0::INSTR" `
  --csv ".\data\software_custom_20.csv" `
  --trigger-mode software-custom `
  --trigger-count 2 `
  --sample-count 10 `
  --auto-range off `
  --current-range 0.1 `
  --auto-zero off `
  --nplc 1.0
```

From another PowerShell window, send one bus trigger per requested trigger:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli soft-trigger
.\.venv\Scripts\python.exe -m keysight_logger.cli soft-trigger
```

This mode arms the DMM with `TRIG:SOUR BUS`, `TRIG:COUNT`, and `SAMP:COUNT`.
Each accepted HTTP `soft-trigger` sends one `*TRG`. The expected row count is
still `trigger_count * sample_count`; `trigger_count=2` and `sample_count=10`
should produce 20 CSV rows.

### External Custom Mode

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::0x2A8D::0x1301::MYXXXXXXXX::0::INSTR" `
  --csv ".\data\external_custom_10.csv" `
  --trigger-mode external-custom `
  --trigger-count 1 `
  --sample-count 10 `
  --hw-trigger-slope neg `
  --hw-trigger-delay-s 0 `
  --auto-range off `
  --current-range 0.1 `
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
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "TCPIP0::169.254.x.x::hislip0::INSTR" `
  --csv ".\data\lan_software.csv" `
  --trigger-mode software `
  --max-samples 5
```

If `list-resources` still shows an old USB resource after unplugging, verify the
live connection with:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli list-resources --verify
```

### Slower High-Accuracy Measurement Setup

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::0x2A8D::0x1301::MYXXXXXXXX::0::INSTR" `
  --csv ".\data\software_high_accuracy.csv" `
  --trigger-mode software `
  --auto-range off `
  --current-range 0.1 `
  --auto-zero on `
  --nplc 10.0
```

`--nplc 10.0` with `--auto-zero on` is slow. For faster external trigger pacing,
consider lower NPLC and Auto Zero off, for example `--nplc 1.0 --auto-zero off`.

### VM Comp Slope

Omit `--vm-comp-slope` unless you need to configure the rear-panel VM Comp output
pulse slope.

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::0x2A8D::0x1301::MYXXXXXXXX::0::INSTR" `
  --csv ".\data\vm_comp_pos.csv" `
  --trigger-mode software `
  --max-samples 5 `
  --vm-comp-slope pos
```

## Stopping A Run

The logger prints both endpoints when it starts:

```text
software trigger endpoint: http://127.0.0.1:8765/trigger
software stop endpoint: http://127.0.0.1:8765/stop
local stop keys: Ctrl+C, Ctrl+Break, q
```

Stop from another terminal:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli soft-stop --port 8765
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

If `soft-stop` is sent after the logger already exited, it may print:

```text
already stopped (endpoint not listening)
```

That is treated as success.

## CSV Output

CSV fields:

| Field | Description |
| --- | --- |
| `timestamp_utc` | UTC timestamp when the sample was read. |
| `measurement_type` | Current measurement type, currently `current_dc`. |
| `value` | Measured current value. |
| `unit` | Unit, currently `A`. |
| `trigger_id` | UUID assigned to the trigger event. |
| `trigger_source` | `software`, `timer`, `hardware`, or `immediate`. |
| `trigger_metadata` | JSON object string from `soft-trigger --meta`, or `{}`. |
| `resource_id` | VISA resource used for the run. |
| `status` | Sample status, currently `ok` for successful captures. |

## Troubleshooting

- If no VISA resources appear, confirm the VISA runtime is installed and the
  instrument is visible in the vendor connection utility.
- If `list-resources` shows stale cached resources, run `list-resources --verify`
  and use only rows marked `live`.
- If `--auto-range off` is used, `--current-range` is required.
- If external trigger edges are missed with high accuracy settings, try
  `--nplc 1.0 --auto-zero off` before changing trigger behavior.
- If a long-running Windows console appears frozen, make sure QuickEdit/text
  selection is not pausing the terminal.
- If PowerShell activation is blocked, keep using
  `.\.venv\Scripts\python.exe` directly.

## Tests

Focused CLI and measurement tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cli_args.py tests/test_measurement.py -q -p no:cacheprovider
```

Broader test run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```
