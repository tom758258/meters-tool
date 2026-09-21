# Meters Tool CLI User Guide

This guide is for operators who receive the built CLI executable or an
already-installed `meters-tool` command and use it to record measurements
from a supported digital multimeter. It focuses on the normal measurement workflow and common settings.

## Start The CLI

For a release build, extract `meters-tool-<version>-windows-x64.zip`, open
PowerShell in the extracted `meters-tool-<version>` folder, and check the CLI:

```powershell
.\meters-tool.exe --version
```

The executable name remains unversioned inside the versioned bundle folder.

## Open The User Guide

The release CLI can open its bundled offline User Guide in the default browser:

```powershell
.\meters-tool.exe user-guide
.\meters-tool.exe user-guide --lang en
.\meters-tool.exe user-guide --lang zh-TW
```

The default guide language is English. Use `--lang zh-TW` for Traditional
Chinese. The guide is bundled with the CLI and does not require an online
documentation site. For exact command options, accepted values, ranges, or
defaults, use `.\meters-tool.exe <command> --help`.

## First Live Run

Use this flow when checking a new computer, VISA runtime, connection, or
instrument setup.

Before a real live run, ensure no other Meters CLI, WebUI, logger, test
process, or external VISA application is controlling the same physical
instrument. Concurrent control can interfere with SCPI responses or instrument
state. Meters Tool does not enforce this with an automatic lock.

1. Turn on the Keysight 34460A or 34461A and connect it to the computer.
2. List resources that currently answer `*IDN?`:

```powershell
.\meters-tool.exe list-resources --live-only
```

3. Copy the resource string for the instrument and set it once for this
   PowerShell session:

```powershell
$env:METER_RESOURCE = "USB0::...::INSTR"
```

   The value can be any live VISA resource returned by discovery, including
   USB or TCPIP/LAN resources.

4. Run one bounded immediate-mode sample:

```powershell
.\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --measurement voltage-dc `
  --trigger-mode immediate `
  --max-samples 1 `
  --csv ".\data\cli_smoke.csv"
```

5. Confirm the command exits, the CSV file exists, and the CSV has one data
   row.
6. Compare the CSV value with the front-panel reading before trusting longer
   captures.

Use an explicit `--resource` value for live acquisition. Passing
`"$env:METER_RESOURCE"` still gives the CLI an explicit resource; do
not rely on a script or unattended workflow to guess which instrument should be
used.

Live starts auto-detect 34460A or 34461A from the connected instrument IDN when
`--model` is omitted. Add `--model 34460A` or `--model 34461A` only when Start
must require that IDN match; a live mismatch fails before setup, and the
selected model never overrides the IDN-selected profile. `--model` also accepts
the stable IDs `keysight-34460a` and `keysight-34461a`. In live mode, any
model value remains an expected-model guard and does not unlock another support
scope. Dry-run and simulate commands use the selected model profile and need
`--model` unless the resource is the deterministic simulator resource
`SIM::34460A` or `SIM::34461A`. Model names are normalized and validated by Core
profile logic, so unknown models fail with a clear validation error.

## Live Support Scope Reminder

A VISA resource that answers `*IDN?` or appears in `list-resources` is not by
itself Product-open for every model and transport/backend combination. Model,
transport, backend, measurement, and trigger support are exact and must match
Core policy. Unsupported combinations fail closed instead of being unlocked by
`--model` or a scan result.

For the exact current support matrix, see [Supported Models](../core/supported-models.md).

By default, the CLI uses the computer's System VISA runtime, such as Keysight
IO Libraries Suite or NI-VISA. Backend selection does not change or expand
Product support. The bundled Windows CLI executable supports only the fixed
System VISA path and does not bundle optional backends.

## Check Settings Without Hardware

Before a first live run, you can check the same request without controlling a
physical instrument.

Use `--dry-run` to validate the request and print the execution plan without
starting acquisition or performing live VISA I/O. Supply `--model 34460A` or
`--model 34461A` when the resource does not identify a simulator model.

Use `--simulate` with a deterministic simulator resource such as
`SIM::34461A` to exercise the acquisition workflow without real hardware. Keep
simulator runs bounded just as you would a first live run.

For example:

```powershell
.\meters-tool.exe start-trigger-record `
  --resource SIM::34461A `
  --simulate `
  --measurement voltage-dc `
  --trigger-mode immediate `
  --max-samples 3 `
  --no-csv
```

Dry-run and simulation are useful setup checks, but neither is evidence that a
real instrument and connection scope have been validated.

## Choosing A Measurement

Choose the measurement type that matches the instrument wiring and the signal
being measured:

- `voltage-dc`: DC voltage.
- `voltage-dc-ratio`: DC voltage ratio.
- `current-dc`: DC current.
- `voltage-ac`: AC voltage.
- `current-ac`: AC current.
- `frequency`: signal frequency in Hz.
- `period`: signal period in seconds.
- `resistance-2w`: 2-wire resistance.
- `resistance-4w`: 4-wire resistance.

Confirm the input terminals before measuring current or 4-wire resistance.
For AC, Frequency, and Period modes, run a low-risk smoke test and compare the
CSV value with the front-panel reading before using the setup for longer
captures.

## Choosing A Trigger Mode

Choose the trigger mode by deciding **what starts a capture** and whether you
need a simple reading workflow or a buffered custom acquisition.

| Mode | Use it when | Capture behavior |
| --- | --- | --- |
| `immediate` | The run should begin taking readings as soon as it starts. | Simple readings; bound the run with `--max-samples` unless continuous capture is intentional. |
| `software` | An operator or another process should decide when each reading is taken. | Waits for accepted software trigger commands. |
| `external` | A fixture, DUT, PLC, or other hardware signal should synchronize readings. | Waits for physical external trigger edges. |
| `immediate-custom` | The run should immediately acquire a defined batch into instrument reading memory. | Buffered custom acquisition. |
| `software-custom` | Each accepted software trigger should start a defined buffered acquisition. | Buffered custom acquisition controlled by software triggers. |
| `external-custom` | Each physical trigger event should drive a defined buffered acquisition. | Buffered custom acquisition controlled by external trigger edges. |

For the simplest workflow, use `--trigger-mode immediate` and add
`--max-samples`.

For manual software triggering, start a `software` or `software-custom` run
in one terminal and send triggers from another:

```powershell
.\meters-tool.exe send-command
```

Software mode can also trigger automatically on a timer. Timer capture is not a
separate `--trigger-mode timer` value: use `--trigger-mode software` together
with `--timer-interval-s`. For example, this takes one software-triggered
reading every second and stops after 60 readings:

```powershell
.\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --measurement voltage-dc `
  --trigger-mode software `
  --timer-interval-s 1 `
  --max-samples 60
```

### Custom / Buffered Trigger Modes

The three `*-custom` modes are for buffered acquisition rather than the simple
`--max-samples` workflow. They require both `--trigger-count` and
`--sample-count`.

The planned number of readings is:

```text
trigger count x sample count
```

For example, `--trigger-count 10 --sample-count 100` plans 1000 readings.
`--max-samples` is not used with custom modes.

`--buffer-drain-size` controls how many buffered readings are requested from
instrument reading memory at a time. Leave it unset unless the test procedure
needs a specific drain size.

If `trigger count x sample count` exceeds the model reading-memory size, Core
requires explicit `--allow-buffer-overflow-risk` acknowledgement before the
custom run can start. That acknowledgement does **not** increase instrument
memory or remove the buffer-drain hard limit. The current reading-memory limits
are 10000 readings for 34461A and 1000 readings for 34460A; see
[Supported Models](../core/supported-models.md) for exact current limits and
support scope.

Use `external` or `external-custom` only when the physical trigger signal is
connected and the operator understands the trigger edge and delay settings.
Hardware trigger timeout is a protective re-arm condition, not automatically a
failed measurement.

## Common Settings

`--resource` is the VISA address of the instrument. Use a value returned by
`list-resources --live-only` or a known operator-provided resource. In
PowerShell examples, set `$env:METER_RESOURCE` once and pass
`--resource "$env:METER_RESOURCE"` so copied commands continue to use
the selected instrument.

`--visa-library` is an advanced CLI backend selector. Omit it for normal Product use and rely on System VISA.
Selecting a backend does not unlock unsupported models, transports, measurements, or other Product support.

`list-resources --verify` opens discovered VISA resources and queries `*IDN?`.
`list-resources --live-only` implies verification and hides stale entries.
ASRL/RS-232 verification uses a short bounded timeout so a stale serial entry
does not block later USB or TCPIP resources. The serial termination options
`--serial-read-termination` and `--serial-write-termination` are CLI discovery
compatibility settings for ASRL verification only; they are not acquisition
settings.

`--csv` is the output file path. If omitted, the CLI creates a timestamped CSV
path. Use an explicit path when you need predictable file locations for review
or automation. Use `--no-csv` to disable CSV output for a run; it cannot be combined with `--csv`.

`--max-samples` bounds simple runs. Use it during smoke tests and validation so
the command stops by itself.

`--auto-range` lets the instrument choose the range. Keep Auto Range enabled
unless the measurement setup requires a fixed range.

`--range` selects a manual range when Auto Range is disabled. Choose a range
that safely covers the expected signal.

`--nplc` controls integration time for DC and resistance measurements. Higher
values are slower and can be more stable. AC, Frequency, and Period modes
accept only the neutral default because they do not write NPLC SCPI.

`--auto-zero` controls offset handling for DC and resistance measurements.
It can improve accuracy but may slow readings. AC, Frequency, and Period modes
do not write Auto Zero SCPI.

`--ac-bandwidth-hz` applies to AC voltage, AC current, Frequency, and Period.
Frequency and Period default to `20` Hz.

`--gate-time-s` applies only to Frequency and Period. Choose `0.01`, `0.1`, or
`1` second; the default is `0.1` second.

`--freq-period-timeout` applies only to Frequency. Keep the default `auto`
unless the measurement procedure requires the `1s` behavior. Period does not
send a timeout command; specifying this option with Period is rejected.

`--current-terminal` applies to current measurements. Match it to the physical
current terminal used on the instrument.

`--dcv-input-impedance` applies to DC voltage and DC voltage ratio. `default`
leaves the current instrument setting unchanged, `10m` selects 10 MOhm, and
`auto` enables the instrument automatic/high-impedance behavior. Keep
`default` unless the measurement procedure requires another input impedance.

`--vm-comp-slope` controls the rear-panel VM Comp output pulse slope. Omit it to
leave VM Comp unchanged; use `pos` or `neg` only when the test setup explicitly
uses that output.

For external trigger modes, `--hw-trigger-delay-s` sets the delay after the
trigger and `--hw-trigger-slope` selects the physical trigger edge. Match both
to the connected trigger source.

For manual software-triggered runs, `--sw-min-interval-ms` can limit how quickly
software triggers are accepted and `--sw-queue-max` limits queued trigger work.
Leave them at their defaults unless the trigger producer or test procedure needs
explicit throttling or queue control. A software trigger can also carry
metadata; metadata is recorded with the trigger/sample output and is useful for
labels such as DUT, batch, or step identifiers.

`--trigger-timeout-ms` controls how long trigger workflows wait before the
protective timeout path is used. Increase it only when the measurement setup
intentionally waits longer.

For command options and CLI-level accepted values, ranges, and defaults, run
`meters-tool <command> --help` (for example,
`.\meters-tool.exe start-trigger-record --help`).
Model-specific support and limits remain subject to Core validation and the
Supported Models scope described above.

## CSV Output

With the default CSV output enabled, each captured sample is written as one
row. Check the CSV after a smoke run for:

- at least one data row;
- expected `measurement_type`;
- expected `unit`;
- expected `trigger_source`;
- a value that matches the front panel closely enough for the test setup.

The CSV is flushed after each captured sample, so completed rows should be
available even during longer runs.

## Stop A Run

For bounded validation runs, prefer `--max-samples` so the run stops by itself.

For a running worker, use one of these stop paths:

- press `q` in the logger terminal;
- press `Ctrl+C` or `Ctrl+Break`;
- run the stop command from another terminal:

```powershell
.\meters-tool.exe stop
```

After stopping, confirm the command exits cleanly and the CSV contains the
expected rows.

## Common Problems

If `meters-tool.exe` is missing, fully extract the ZIP, open the versioned
release folder, and confirm that `meters-tool.exe` exists there.

If `list-resources` shows stale resources, use `list-resources --verify` to see
which resources answer and why others failed. Use `--live-only` when you only
want resources that answered `*IDN?`. If an ASRL/RS-232 resource reports a
termination-related stale result, retry discovery with
`--serial-read-termination` or `--serial-write-termination`; those options only
affect ASRL verification.

If no live resource is found, check instrument power, USB/LAN/GPIB connection,
VISA driver visibility, and whether another program is holding the instrument.

If a run is blocked before opening the instrument, read the validation error and
adjust the option it names. The CLI validates common settings before live I/O.

If a hardware trigger run appears to wait, confirm the physical trigger signal,
slope, delay, and timeout. Missing trigger edges can make the run wait or re-arm
according to the configured timeout behavior.
