# Meters Tool WebUI / Desktop User Guide

This guide is for operators who use either `Meters Tool.exe` or
`meters-tool-webui-launcher.exe` to record measurements from a supported digital
multimeter. Both provide the same local acquisition interface and normal
measurement workflow.

## What The WebUI / Desktop Interface Does

Meters Tool provides the same local acquisition interface either in the Electron
Desktop application window or in a normal browser through the WebUI launcher.
It can:

- Find connected VISA instruments.
- Start one measurement run at a time.
- Record readings to a CSV file.
- Show the latest reading and recent readings while the run is active.
- Send a software trigger when the selected trigger mode needs it.
- Stop the current run and open the completed CSV file.

The WebUI runs on the same Windows computer that has access to the instrument.
It is not a cloud service.

## Choose Desktop Or Browser WebUI

### Desktop Application

For a release build, extract `meters-tool-<version>-windows-x64.zip`, open the
extracted `meters-tool-<version>` application directory, and double-click:

```text
Meters Tool.exe
```

Desktop opens the shared WebUI inside the application window. No separate WebUI
Launcher is required, no port selection is required, and no manual browser URL
is required. After startup, use the same Screen Overview and workflow documented
below.

### Browser WebUI

For a release build, extract `meters-tool-<version>-windows-x64.zip`, open the
`meters-tool-<version>` folder, and double-click:

```text
meters-tool-webui-launcher.exe
```

The executable name remains unversioned inside the versioned bundle folder.

The launcher starts automatically. It begins at port `8767`, tries up to 100
local ports when needed, waits until the WebUI is ready, and then opens the
browser at the port it actually bound. Another running Meters Tool WebUI is
treated as a port owner and is not reused.

During normal startup no port window or Start action is required. After startup,
a small launcher window shows the running URL and `Quit`. Use `Quit` when you
are done so active-run cleanup can finish before the local server closes.

Only when all automatic candidates are occupied does the full port window
appear. Enter another port from `1` through `65535` and click `Start`. Each
manual retry tries only that port once and leaves the window open if it fails.

If the browser does not open automatically, open this address manually:

```text
http://127.0.0.1:8767/
```

The actual port may be higher; use the URL shown in the launcher window.

## Screen Overview

The WebUI / Desktop interface is the same local acquisition console in both
entry points. The main areas are:

- Top-right toolbar: language, theme, and `Help` controls.
- `Help`: opens the bundled User Guide.
- `Device / Resource`: the instrument address, last scanned live resource,
  `Scan Device` button, `Supported devices` list, and `Device options` gear for
  execution mode and model selection. It starts expanded and can collapse to a
  short summary that identifies the selected execution mode.
- `Run Setup`: CSV output path and run count settings.
- `Measurement`: measurement type and related options.
- `Trigger`: trigger mode and trigger-related options.
- `Status`: current run state, captured sample count, errors, CSV path, and log.
- `Live data`: latest reading, trend chart, recent samples, and selected sample
  details.

Select `Supported devices` to see the supported WebUI connection list. The list
is derived from Core capability and support metadata, so it reflects the
current supported connection coverage without hard-coding a transient USB/LAN
matrix. For the exact current Product support scope, see
[Supported Models](../core/supported-models.md).

## Language

The top-right appearance and language controls are labeled settings. Use the
globe-and-text button to switch between English and Traditional Chinese. The
button names the current language: English shows `English`, and Traditional
Chinese shows `繁體中文`. Its screen-reader label describes the destination
language.

The first page load uses a valid saved locale when available, then the browser
language, then English. Manual choices are saved under
`meters-tool.webui.locale`; browser detection is not saved automatically.
Switching is immediate and does not reload the page or contact a runtime API.
The current form values, active run, panels, status log, Live data selection,
chart settings, resource scan, and support summary remain in place. Unknown
diagnostic text remains unchanged.

In Traditional Chinese, the Measurement options control displays
`自動量程（Auto range）`; summaries use the shorter `自動量程`. Optional markers
stay beside their field titles at ordinary desktop widths, including AC filter
and Current terminal, and wrap naturally on very narrow screens.

## Help

Click `Help` in the top-right toolbar. In Browser WebUI, the bundled User Guide
opens in a new browser tab. In Desktop, it opens in the system default browser.
The guide follows the currently selected WebUI language, and both entry points
use the same underlying Help content. Change the WebUI language before opening
Help when a different language is wanted.

## Theme

Use the theme button beside the language button to cycle through `System`,
`Light`, and `Dark`. `System` follows the browser or operating-system color
scheme and updates when that setting changes. The selected preference is saved
for the interface and restored on later browser visits or Desktop starts.
Switching theme is immediate and does not reload the page or reset the current
form, run, Live data, or status.
In Electron Desktop, `System` also keeps the native window UI aligned with the
operating-system appearance. Selecting `Light` or `Dark` applies that preference
to the native window UI as well, and Desktop restores it on later starts.

## Choosing An Execution Mode

Open `Device options` and choose one mode:

- `Real` uses the configured VISA resource and keeps the normal scan, identity
  check, acquisition, trigger, CSV, Stop, and cleanup workflow.
- `Simulate` requires `34460A` or `34461A`. It does not use or query real VISA
  hardware. The deterministic simulated instrument runs through the complete
  acquisition runtime, so Live data latest value, chart, statistics, recent
  samples, Stop, and normal CSV output work as they do for a runtime run.
- `Dry-run` requires a planning model and changes Start to `Preview plan`. It
  validates and displays the Core plan in Status details but starts no
  acquisition, creates no active run, performs no real VISA I/O, and produces
  no Live data samples. Previewing a plan clears samples left on screen by an
  earlier run.

Execution mode is page-local and cannot be changed while a Start or Preview
request is pending or a run is active. It is not saved: reloading always
returns to `Real`. Simulation and dry-run are useful no-hardware checks, but
neither is live-hardware validation evidence.

## First Run

Use this flow for a basic immediate measurement:

Before a real live run, ensure no other Meters CLI, WebUI, logger, test
process, or external VISA application is controlling the same physical
instrument. Concurrent control can interfere with SCPI responses or instrument
state. Meters Tool does not enforce this with an automatic lock.

1. Turn on the Keysight 34460A or 34461A and connect it to the computer.
2. Start Desktop or the Browser WebUI.
3. Click `Scan Device`.
4. Select or copy the detected VISA resource into `VISA resource`.
5. Leave `Expected model` in `Device options` on Auto-detect unless you need to
   require 34460A or 34461A.
6. Choose the measurement type, such as DC voltage or DC current.
7. Keep `CSV output` checked and choose the CSV location. Use `Select` to pick
   a folder and generate a timestamped CSV path. Clear `CSV output` only when
   no CSV file is wanted.
8. Leave trigger mode on the immediate/default mode unless you specifically
   need software or external triggering.
9. Review the highlighted settings.
10. Click `Start`.
11. Watch `Captured`, `Status`, and `Live data`.
12. Click `Stop` when the run should end.
13. For a CSV-enabled run, click `Open CSV` after it stops.

Only one run can be active at a time. Starting a new run clears the displayed
recent samples from the previous run.

## Choosing A Trigger Mode

Choose the trigger mode by deciding **what should start a capture** and whether
you need simple readings or a buffered custom acquisition.

| Mode | Use it when | What happens |
| --- | --- | --- |
| `Immediate` | The run should start taking readings as soon as Start is pressed. | Simple readings controlled by the run sample limit. |
| `Software` | An operator should decide when each reading is taken, or a timer should send software triggers. | Manual `Trigger` button when Timer trigger is off; scheduled software triggers when Timer trigger is on. |
| `External` | A fixture, DUT, PLC, or other hardware signal should synchronize readings. | Waits for physical external trigger edges. |
| `Immediate Custom` | Start should immediately acquire a defined batch into instrument reading memory. | Buffered custom acquisition. |
| `Software Custom` | Each WebUI software trigger should start a defined buffered acquisition. | Buffered custom acquisition controlled by the `Trigger` button. |
| `External Custom` | Each physical trigger event should drive a defined buffered acquisition. | Buffered custom acquisition controlled by external trigger edges. |

Immediate mode is the simplest first-run choice.

### Software Trigger Controls

In `Software` mode with `Timer trigger` cleared, click `Trigger` after the run
starts to send each software trigger. Turning on `Timer trigger` changes the
workflow to scheduled software triggers; set `Timer interval s` to the desired
interval. Timer is part of Software mode, not a separate trigger mode.

For manual software-triggered modes, `SW min interval ms` can limit how quickly
software triggers are accepted, and `SW queue max` limits queued trigger work.
Leave these at their defaults unless the trigger producer or test procedure
requires explicit throttling or queue control.

`Trigger metadata JSON` attaches an optional JSON object to a manual software
trigger. For example:

```json
{"batch":"A1"}
```

Use metadata for labels such as DUT, batch, or test step. It is trigger metadata,
not an instrument command or script.

### Custom / Buffered Trigger Controls

Selecting any `* Custom` mode shows `Trigger count`, `Sample count`,
`Buffer drain size`, and `Allow buffer risk`.

`Trigger count` is the number of instrument trigger events in the custom
sequence. `Sample count` is the number of readings taken for each trigger. The
planned reading count is therefore:

```text
trigger count x sample count
```

For example, Trigger count `10` and Sample count `100` plan 1000 readings.

`Buffer drain size` controls how many buffered readings are requested from
instrument reading memory at a time. Leave it at the default unless the test
procedure requires a specific drain size.

If the planned reading count exceeds the selected model's reading memory,
`Allow buffer risk` is the explicit acknowledgement required to proceed. It does
**not** increase the instrument memory or remove the buffer-drain hard limit.
The current reading-memory limits are 10000 readings for 34461A and 1000
readings for 34460A. See [Supported Models](../core/supported-models.md) for
exact current support and limits.

Use External or External Custom only when a physical trigger signal is connected
and configured for the instrument. `External trigger slope` selects the physical
edge, `Trigger delay` waits after the edge before measurement, and `Trigger
timeout` controls the protective wait/re-arm path. A hardware trigger timeout
is not automatically a failed measurement.

Do not change trigger timing, trigger delay, NPLC, Auto Range, Auto Zero, VM
Comp, or current terminal settings unless the measurement setup requires it and
the operator understands the effect on the instrument.

## Settings Reference

The WebUI checks settings before starting a run. If `Start` is blocked, read
the Status log and adjust the field it names.

`VISA resource` is the instrument address used for the run. Prefer a resource
found by `Scan Device`, or type a known resource provided by the operator or
test procedure. Do not guess a resource when more than one instrument may be
connected.

The WebUI uses the computer's fixed default System VISA runtime. It does not
include a PyVISA backend selector, and its resource scan and run API accept no
backend override. Exact live model and connection support is governed by Core
policy and documented in [Supported Models](../core/supported-models.md).

`Live resource` shows the result of the last scan. Use it to confirm which
instrument answered before copying or selecting a resource for the run. When
the scan recognizes a supported 34460A or 34461A IDN, the WebUI may reload
model-specific options for display while keeping `Expected model` on
Auto-detect.

`CSV output` is checked by default. While enabled, `CSV path` is where readings
will be written. Use `Select` to choose a folder and let the WebUI generate a
timestamped file name, or type a specific file path before clicking `Start`.

Run count and sample limit fields control how long a run can continue. Keep new
setups bounded while checking wiring, measurement type, and trigger behavior.

`Expected model` is an optional check in `Device options`. Auto-detect uses a
fresh IDN preflight at Start to resolve the connected instrument. Select
`Require 34460A` or `Require 34461A` only when you want Start to read IDN and
fail unless the connected instrument reports that supported model. With 34460A
required, the WebUI hides 10 A current ranges,
current terminal selection, and external trigger modes; custom mode reading
memory is 1000 readings. These disabled controls are guidance only. The
selected model is an expected-model guard and display context; it does not
override the detected IDN, unlock capabilities for another instrument, or
replace the Core safety checks.

`Measurement type` selects what the instrument measures: DC or AC voltage, DC
or AC current, DC voltage ratio, Frequency, Period, or 2-wire or 4-wire resistance.
Match this to the instrument wiring before starting a run.

`Auto Range` lets the instrument choose the measurement range. Keep it enabled
for first runs unless the measurement procedure requires a fixed range.

Manual range fields are used when Auto Range is disabled. Choose a range that
safely covers the expected signal.

`NPLC` controls integration time for DC and resistance measurements. Higher
values are slower and can be more stable. AC, Frequency, and Period modes use
their AC filter setting instead.

`Auto Zero` controls offset handling for DC and resistance measurements. It can
improve accuracy but may slow readings. Leave it at the normal setup value
unless the measurement procedure calls for a change.

`AC filter` applies to AC voltage, AC current, Frequency, and Period. For AC
voltage and AC current, `Keep current setting` leaves the instrument's current
filter unchanged. Frequency and Period select `20 Hz` by default; the summary
may show this as `>20 Hz`.

`Gate time` applies only to Frequency and Period. The default is `0.1 s`;
available choices are `0.01`, `0.1`, and `1 s`.

`Timeout` in the Measurement options applies only to Frequency. Keep `Auto`
unless the procedure requires `1 s`. Period hides this control and does not send
a timeout command.

Frequency values are shown and stored in `Hz`. Period values are shown and
stored in `s`; the WebUI does not automatically rescale these units.

`Current terminal` applies to current measurements. Confirm the physical lead is
connected to the matching current terminal before starting the run.

`DCV input Z` appears for DC voltage and DC voltage ratio. `Default` leaves the
current instrument setting unchanged, `10M` selects 10 MOhm, and `Auto` enables
the instrument automatic/high-impedance behavior. Keep `Default` unless the
measurement procedure requires another input impedance.

DC voltage ratio is a specialized measurement mode. Use it only when the test
setup explicitly requires ratio measurement.

`VM Comp slope` controls the rear-panel VM Comp output pulse slope. `Leave
unchanged` preserves the current setting; choose `Pos` or `Neg` only when the
test setup explicitly uses the VM Comp output.

`Trigger mode` controls when samples are taken. The Choosing A Trigger Mode
section above explains the simple and Custom workflows and the fields that
appear for each mode.

`Trigger delay` waits after an external trigger before measurement. Leave it
unchanged unless the external setup requires a delay.

`Trigger timeout` controls how long trigger workflows wait before the protective
timeout path is used. Increase it only when the measurement setup intentionally
waits longer.

`External trigger slope` selects the physical trigger edge. Match it to the
signal source connected to the instrument.

## Live Data Chart Scale

The `Live data` panel has chart scale controls in the `Trend` section. These
settings affect only the interface chart display. They do not affect instrument
settings, SCPI commands, CSV output, or recorded values.

The trend chart shows Y-axis labels on the left side of each grid line using
the active scale mode.

`Auto deviation` is the default. It centers the chart on the first numeric
sample in the run and shows later samples as differences from that first
sample. This is best for small drift or stability changes. It is not an
absolute Y-axis chart. If the first sample is `5.0000 V` and later samples are
`5.0002 V` and `4.9998 V`, the chart shows `+0.0002 V` and `-0.0002 V`
relative to the first sample.

`Auto absolute` uses the actual minimum and maximum of the visible recent
samples. This is best for seeing the measured range. If samples range from
`4.9998 V` to `5.0004 V`, the chart range is based on those actual values.
Outliers may rescale the chart and make small variations look flatter.

`Manual span` uses the first numeric sample as the center and a fixed positive
span entered by the operator. The span uses the raw measurement unit: `V` means
volts, `A` means amps, `Ohm` means ohms, `Hz` means hertz, and `s` means
seconds. For voltage, `0.01` means `0.01 V`, not `0.01 mV`. If the first sample
is `5.000 V` and Manual span is `0.010 V`, the chart shows `4.990 V` to
`5.010 V`. Values outside `baseline +/- span` are clamped to the chart
boundary, so the first version does not show a separate clipped indicator.

`Range step` uses the manually selected `Range` as the chart display span. It
is available only when `Auto Range` is off and a manual range is selected. It
does not reflect the instrument's actual auto-selected range, because the WebUI
does not know that hardware range while Auto Range is enabled. If the first
sample is `5.000 V` and the selected manual Range is `0.010 V`, the chart shows
`4.990 V` to `5.010 V`. Values outside `baseline +/- selected Range` may be
clamped to the chart boundary. Like the other chart scale modes, Range step
affects only the interface chart display and does not change instrument settings,
SCPI commands, CSV output, or recorded values.

## CSV Output

`CSV output` is checked by default. Clear it to run without creating a CSV.
This disables `CSV path` and `Select` but preserves the current path so it is
available if CSV output is re-enabled.

When enabled, the CSV path shown in `Run Setup` is the file that will be used
when `Start` is clicked.

`Select` opens a folder picker on the Windows computer running the WebUI. After
you choose a folder, the WebUI fills in a timestamped CSV file path in that
folder. You can edit the path manually before clicking `Start`.

`Open CSV` is available after a completed run has a CSV path. It opens the last
completed run CSV using the Windows default app. It is disabled while a run is
active and after a no-CSV run. Live data, captured samples, status, Stop, and
cleanup continue normally when CSV output is disabled.

## Stop And Exit

### Desktop Application

Use `Stop` when intentionally ending the current acquisition run. When finished
with Desktop, close the Desktop application window normally. Desktop requests
graceful shutdown and cleanup before exiting. If Desktop reports that cleanup is
not complete, wait for cleanup to finish and then close the window again.

### Browser WebUI

Use `Stop` to stop the active acquisition run. The WebUI keeps the latest
readings visible after the run stops so you can review them. Then use `Quit` in
the small running launcher window to stop the local WebUI server and close the
launcher. Closing only the browser tab does not stop the server.

## Common Problems

### The Browser WebUI does not open

Open the running URL shown in the launcher window. The default starting address
is:

```text
http://127.0.0.1:8767/
```

If the page still does not load, return to the launcher and check whether it
shows a startup error.

### The launcher says the port is already in use

The default launcher mode automatically tries the next port. This also applies
when another Meters Tool WebUI owns the port, because separate instances may be
needed for different instruments. A fixed `--port` reports the conflict without
incrementing. If the automatic 100-port search is exhausted, enter another
legal port in the fallback window; each manual retry tries only that port.

### Scan Device finds nothing

Check that:

- The instrument is powered on.
- The USB/LAN/GPIB connection is attached.
- The VISA driver can see the instrument.
- No other program is holding the instrument connection.

You can still type a known VISA resource manually.

### Scan Device cannot infer the model

Leave `Expected model` on Auto-detect and click `Start`; the backend performs a
fresh IDN preflight. Require a model only when you intentionally want Start to
fail unless the connected instrument reports 34460A or 34461A.

### Start says the selected model does not match the IDN

Select the model named in the message from `Device options`, or return
`Expected model` to Auto-detect. This means the connected instrument IDN clearly
matched a supported model different from the required WebUI model.

### Start is blocked

Make sure `VISA resource` is filled in and highlighted settings have valid
values. The Status log shows the setting that needs attention.

### Open CSV is disabled

`Open CSV` is disabled until a CSV-enabled run stops and a completed CSV path is
available. It also stays disabled while a run is active or when `CSV output`
was cleared.

### A hardware trigger run appears to wait

External trigger modes wait for the physical trigger signal. If the trigger
signal is missing, the run can wait or re-arm according to the configured
timeout behavior.

## Operator Safety Notes

- Confirm the instrument input wiring and current terminal before measuring
  current.
- Use immediate mode first when checking a new setup.
- Keep Auto Range enabled unless a fixed range is required.
- Treat external trigger wiring and polarity as part of the measurement setup.
- Stop the run before disconnecting the instrument when practical.
