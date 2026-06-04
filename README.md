# Keysight 34461A CLI Logger

Current CLI baseline: `v1.0.0-cli`.

CLI-first Python logger for Keysight 34461A DC/AC current, DC/AC voltage, and
2-wire or 4-wire resistance measurements over VISA.
It records one CSV row per captured sample and supports software, external
hardware, and immediate trigger modes.

## Current Scope

Implemented:

- VISA resource listing for USB and LAN resources discovered by PyVISA..
- DC current, DC voltage, AC current, AC voltage, and 2-wire or 4-wire
  resistance measurement logging.
- Software trigger mode through a local HTTP endpoint.
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
  DCV input impedance, Auto Zero, NPLC, hardware trigger delay, hardware
  trigger slope, and VM Comp slope.
- Immediate CSV flush after every captured sample.

Important limitations:

- This project is currently focused on Keysight 34461A current, voltage, and
  2-wire or 4-wire resistance logging.
- AC current and AC voltage trigger/acquisition flows have been checked on a
  real instrument without a connected AC signal source. Actual AC signal values
  and accuracy still need validation in a real AC measurement setup. AC modes
  do not currently expose AC bandwidth/filter controls.
- `--nplc` and `--auto-zero` are DC/resistance controls. They are accepted by
  the shared CLI, but `current-ac` and `voltage-ac` do not write NPLC or Auto
  Zero SCPI commands.
- Mixed software and hardware capture in the same run is not supported.
- Plain `list-resources` calls VISA discovery directly and may show stale
  resources cached by the VISA runtime. Use `list-resources --verify` to open
  each resource and query `*IDN?`; use `list-resources --live-only` when you
  only want resources that answered.
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

The `py -3.10` command selects Python 3.10 through the Windows Python launcher.
If your installed supported version is newer, use that version instead, for
example `py -3.11 -m venv .venv` or `py -3.12 -m venv .venv`.

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
| `list-resources` | Print VISA resources discovered by PyVISA. | Find the USB or LAN resource string. Add `--verify` to query `*IDN?`; add `--live-only` to hide stale cached resources. |
| `start-trigger-record` | Connect to the instrument and record samples to CSV. | Main logging command. |
| `soft-trigger` | POST one software trigger to the local trigger endpoint. | Used with `--trigger-mode software`. |
| `soft-stop` | POST a graceful stop request to the local stop endpoint. | Stop a running logger from another terminal. |

`list-resources` options:

| Option | Description |
| --- | --- |
| none | Print raw VISA resources returned by PyVISA. This can include stale cached resources. |
| `--verify` | Open each discovered resource and query `*IDN?`. Text output marks rows as `live` or `stale`; JSON output includes `live`, `status`, and `detail`. |
| `--live-only` | Verify resources and print only rows that answered. Text output prints `no live VISA resources found` if nothing is connected or reachable. |
| `--format json` | Emit one JSON object for scripts. Can be combined with `--verify` or `--live-only`. |

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
| `--csv PATH` | No | `data/YYYY-MM-DD-HH-MM-SS.csv` | CSV output path. If omitted, a UTC+8 timestamped file is created under `data`. Parent directories are created automatically. |
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
| `--measurement current-dc\|voltage-dc\|current-ac\|voltage-ac\|resistance-2w\|resistance-4w` | No | `current-dc` | Measurement type. |
| `--nplc VALUE` | No | `1.0` | Integration time in power-line cycles for DC current, DC voltage, and resistance. Must be greater than 0. Ignored by AC current and AC voltage. |
| `--auto-zero on\|off` | No | `on` | Enable or disable Auto Zero for DC current, DC voltage, and 2-wire resistance. 4-wire resistance and AC measurements leave Auto Zero to the instrument. |
| `--auto-range on\|off` | No | `on` | Enable or disable Auto Range. |
| `--range VALUE` | Required when `--auto-range off` | None | Manual range for the selected measurement. Amps for current, volts for voltage, ohms for resistance. |
| `--current-range VALUE` | Current DC only | None | Compatibility alias for `--range` with `current-dc`. Do not combine with `--range`; invalid with AC current, voltage, and resistance measurements. |
| `--dcv-input-impedance default\|10m\|auto` | DC Voltage only | `default` | DC voltage input impedance. `default` writes no impedance command; `10m` forces 10 MOhm; `auto` enables the instrument Auto mode, which may show HighZ on low DC voltage ranges. |
| `--vm-comp-slope pos\|neg` | No | None | Configure rear-panel VM Comp output pulse slope. Omit to leave VM Comp unchanged. |

`--measurement` defaults to `current-dc`, so existing current logging commands do
not need to specify it. New commands should prefer `--range`; `--current-range`
continues to work for existing DC current scripts. Use `--range` for
`current-ac`, `voltage-dc`, `voltage-ac`, `resistance-2w`, and
`resistance-4w`; `--current-range` is rejected with those measurements.
`--dcv-input-impedance` is valid only with `--measurement voltage-dc`. Use
`default` to leave the instrument's current Input Z setting unchanged, `10m` to
force 10 MOhm, or `auto` to enable the 34461A Auto Input Z behavior. The
instrument may display HighZ while Auto is active on lower DC voltage ranges.

## Examples

These examples are ordered as a practical validation path: first identify a live
resource, then run one-sample smoke checks, then use the trigger mode that fits
the experiment. The USB resource shown below is the 34461A used during project
validation; replace resource strings and CSV paths with values appropriate for
your instrument and test run.

### List VISA Resources

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli list-resources
```

Verify which resources are live:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli list-resources --verify
```

Show only live resources and hide stale VISA cache entries:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli list-resources --live-only
```

Use JSON output for scripts:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli list-resources --verify --format json
```

Verified output is tab-separated:

```text
live    USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR    Keysight Technologies,34461A,...
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
      "resource": "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR",
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
      "resource": "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR",
      "status": "live"
    }
  ],
  "verify": true
}
```

Example resource strings:

```text
USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR
TCPIP0::<IP_ADDRESS>::hislip0::INSTR
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
5. Confirm graceful stop behavior with `soft-stop`, Ctrl+C, Ctrl+Break, or `q`
   before relying on long unattended runs.

The project has been validated on a Keysight 34461A for DC current logging,
DC voltage smoke checks, 2-wire and 4-wire resistance smoke checks,
software/timer/external/immediate modes, all three custom buffered modes, JSON
resource verification, live-resource filtering, and the documented stop paths.
AC current and AC voltage trigger/acquisition flows have also been checked on a
real instrument, including software timer under software mode, but without a
connected AC signal source. Run actual AC signal validation before relying on
AC measurement values or accuracy.

### Current DC Smoke Test

One immediate current sample:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR" `
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

### Software Trigger, Bounded Run

Terminal 1, start recording and wait for five software triggers:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR" `
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
.\.venv\Scripts\python.exe -m keysight_logger.cli soft-trigger --port 8765
```

Run the `soft-trigger` command five times. The logger stops automatically after
five successful samples because of `--max-samples 5`.

### Validated Voltage DC Smoke Tests

These two voltage commands were reported OK on a real 34461A: Auto Range,
manual 10 V range, and CSV fields/values all looked normal.

Additional voltage trigger checks were also reported OK on the same instrument:
software trigger with 1-2 rows, software timer with 2-3 rows, and external
trigger with one external edge. Rough checks with `voltage-dc` plus
`immediate-custom`, `software-custom`, and `external-custom` were also normal.

Auto range, one immediate voltage sample:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR" `
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
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR" `
  --csv ".\data\voltage_range10_smoke.csv" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --auto-range off `
  --range 10 `
  --auto-zero off `
  --nplc 1.0 `
  --max-samples 1
```

For voltage rows, expect `measurement_type=voltage_dc` and `unit=V` in the CSV.
Voltage can also be selected with custom/buffered modes through
`--measurement voltage-dc`; those paths use the same measurement configuration
and the existing custom-mode trigger/read flow. The voltage custom-mode
combinations have only had rough real-instrument checks so far; run a longer
buffered validation before relying on voltage buffered acquisition for
production runs.

DCV Input Z smoke check, Auto mode:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR" `
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
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR" `
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

### AC Current And Voltage Smoke Tests

AC current and AC voltage use the same trigger/read flow as other scalar
measurements. They configure the 34461A AC function and Auto Range/manual range
only. The CLI does not write NPLC, Auto Zero, or AC bandwidth/filter SCPI for AC
measurements. Trigger/acquisition flows have been checked on a real instrument
without a connected AC signal source; validate actual AC values in your AC
measurement setup before relying on them.

Suggested Auto Range AC voltage smoke test:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR" `
  --csv ".\data\voltage_ac_auto_smoke.csv" `
  --trigger-mode immediate `
  --measurement voltage-ac `
  --auto-range on `
  --max-samples 1
```

Suggested manual-range AC current smoke test:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR" `
  --csv ".\data\current_ac_range100ma_smoke.csv" `
  --trigger-mode immediate `
  --measurement current-ac `
  --auto-range off `
  --range 0.1 `
  --max-samples 1
```

For AC rows, expect `measurement_type=voltage_ac` with `unit=V`, or
`measurement_type=current_ac` with `unit=A`. AC trigger/acquisition flows were
checked on a real instrument without a connected AC signal source; actual AC
value and accuracy validation remains deferred until an AC measurement setup is
available.

### Validated Resistance 2-Wire Smoke Tests

These two resistance commands were reported OK on a real 34461A: Auto Range,
manual 1000 Ohm range, and CSV fields/values all looked normal.

Auto range, one immediate resistance sample:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR" `
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
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR" `
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
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR" `
  --csv ".\data\resistance_4w_auto_smoke.csv" `
  --trigger-mode immediate `
  --measurement resistance-4w `
  --auto-range on `
  --nplc 1.0 `
  --max-samples 1
```

Manual 1000 Ohm range, one immediate 4-wire resistance sample:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR" `
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
.\.venv\Scripts\python.exe -m keysight_logger.cli soft-trigger `
  --port 8765 `
  --meta "{""batch"":""A1"",""operator"":""lab""}"
```

The metadata is accepted by the trigger endpoint and written to the CSV
`trigger_metadata` field as a JSON object string.

### Software Trigger Rate Limit And Queue Limit

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR" `
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
  --resource "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR" `
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
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR" `
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

### Legacy Hardware Trigger Flag

This is equivalent to `--trigger-mode external`:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR" `
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
  --resource "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR" `
  --csv ".\data\immediate_100.csv" `
  --trigger-mode immediate `
  --max-samples 100 `
  --auto-range off `
  --range 0.1 `
  --auto-zero off `
  --nplc 1.0
```

Immediate mode does not wait for `soft-trigger` or external trigger edges. Use
`--max-samples` to avoid an accidental long continuous run.

### Immediate Custom Mode

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR" `
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
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR" `
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
  --resource "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR" `
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
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "TCPIP0::<IP_ADDRESS>::hislip0::INSTR" `
  --csv ".\data\lan_software.csv" `
  --trigger-mode software `
  --max-samples 5
```

If `list-resources` still shows an old USB resource after unplugging, show only
resources that still answer with:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli list-resources --live-only
```

Use `list-resources --verify` when you want to see both live and stale entries
for diagnosis.

### Slower High-Accuracy DC/Resistance Setup

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR" `
  --csv ".\data\software_high_accuracy.csv" `
  --trigger-mode software `
  --auto-range off `
  --range 0.1 `
  --auto-zero on `
  --nplc 10.0
```

`--nplc 10.0` with `--auto-zero on` is slow for DC/resistance measurements. For
faster external trigger pacing, consider lower NPLC and Auto Zero off, for
example `--nplc 1.0 --auto-zero off`. AC measurements do not use these two
settings.

### VM Comp Slope

Omit `--vm-comp-slope` unless you need to configure the rear-panel VM Comp output
pulse slope.

```powershell
.\.venv\Scripts\python.exe -m keysight_logger.cli start-trigger-record `
  --resource "USB0::<VENDOR_ID>::<PRODUCT_ID>::<SERIAL_NUMBER>::0::INSTR" `
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

## Console Status Output

During software-triggered runs, `waiting trigger` is printed once for each
continuous wait period instead of repeating on every short poll timeout.
`software-custom` mode follows the same policy for
`waiting software custom trigger`.

Successful captures print the count and latest display value, for example:

```text
[status] captured=1 value=12.3 mA
[status] captured=2 value=1.23 kOhm
```

Display prefixes such as `mA`, `mV`, `kOhm`, and `MOhm` are console-only. CSV
rows continue to store the raw value in the measurement base unit (`A`, `V`, or
`Ohm`). Custom/buffered modes may drain multiple readings at once; the console
status shows the last sample in that drain batch.

## CSV Output

If `--csv` is omitted, the logger writes to a UTC+8 timestamped file under
`data`, for example `data/2026-05-11-14-30-05.csv`. Passing `--csv PATH`
continues to write to that exact path.

CSV fields:

| Field | Description |
| --- | --- |
| `timestamp_utc_plus_8` | UTC+8 timestamp when the sample was read, serialized as ISO 8601 with a `+08:00` offset. |
| `measurement_type` | Selected measurement type, such as `current_dc`, `voltage_dc`, `current_ac`, `voltage_ac`, `resistance_2w`, or `resistance_4w`. |
| `value` | Measured value. |
| `unit` | Unit, `A` for current, `V` for voltage, and `Ohm` for resistance. |
| `trigger_id` | UUID assigned to the trigger event. |
| `trigger_source` | `software`, `timer`, `hardware`, `immediate`, `immediate-custom`, `software-custom`, or `external-custom`. |
| `trigger_metadata` | JSON object string from `soft-trigger --meta`, or `{}`. |
| `resource_id` | VISA resource used for the run. |
| `status` | Sample status, currently `ok` for successful captures. |

## Troubleshooting

- If no VISA resources appear, confirm the VISA runtime is installed and the
  instrument is visible in the vendor connection utility.
- If `list-resources` shows stale cached resources, run `list-resources --live-only`
  to hide stale entries. Use `list-resources --verify` when you need to inspect
  stale-resource errors.
- If the CLI says it cannot open the CSV output file, close the file in Excel
  or any other program, or choose a different `--csv` path.
- If `--auto-range off` is used, `--range` or `--current-range` is required.
- If `--dcv-input-impedance` is used with anything other than
  `--measurement voltage-dc`, the CLI rejects the command.
- If external trigger edges are missed with high accuracy DC/resistance
  settings, try `--nplc 1.0 --auto-zero off` before changing trigger behavior.
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