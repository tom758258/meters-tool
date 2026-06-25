# Keysight Logger CLI User Guide

This guide is for operators who receive the built CLI executable or an
already-installed `keysight-logger` command and use it to record measurements
from a Keysight 34461A. It focuses on the normal measurement workflow and
common settings. For developer setup, validation scripts, JSON/JSONL output,
and automation contracts, see the [CLI README](README.md).

## Start The CLI

Open PowerShell in the folder that contains the CLI executable and check it:

```powershell
.\keysight-logger.exe --version
```

Release folders may include a versioned executable name, such as:

```text
keysight-logger-<version>.exe
```

Use that file name in the commands below if your release folder uses a
versioned executable. Developers or source-checkout users should use the
[CLI README](README.md) for virtual environment, module, validation, and build
commands.

## First Live Run

Use this flow when checking a new computer, VISA runtime, connection, or
instrument setup.

1. Turn on the Keysight 34461A and connect it to the computer.
2. List resources that currently answer `*IDN?`:

```powershell
.\keysight-logger.exe list-resources --live-only
```

3. Copy the resource string for the 34461A.
4. Run one bounded immediate-mode sample:

```powershell
.\keysight-logger.exe start-trigger-record `
  --resource "<VISA_RESOURCE>" `
  --measurement voltage-dc `
  --trigger-mode immediate `
  --max-samples 1 `
  --csv ".\data\cli_smoke.csv"
```

5. Confirm the command exits, the CSV file exists, and the CSV has one data
   row.
6. Compare the CSV value with the front-panel reading before trusting longer
   captures.

Use an explicit resource string for live acquisition. Do not rely on a script
or unattended workflow to guess which instrument should be used.

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

Use `--trigger-mode immediate` for the simplest workflow. The instrument starts
capturing when the run starts. Add `--max-samples` unless you intentionally want
a continuous run.

Use `--trigger-mode software` when the run should wait for software trigger
commands. Start the logger in one terminal, then send triggers from another:

```powershell
.\keysight-logger.exe send-command
```

Use timer capture when the run should take software-triggered readings on a
schedule. Set the timer interval explicitly and keep the run bounded while
validating the setup.

Use external or hardware trigger modes only when the physical trigger signal is
connected and the operator understands the trigger edge and delay settings.
Hardware trigger timeout is a protective re-arm condition, not automatically a
failed measurement.

## Common Settings

`--resource` is the VISA address of the instrument. Use a value returned by
`list-resources --live-only` or a known operator-provided resource.

`--csv` is the output file path. If omitted, the CLI creates a timestamped CSV
path. Use an explicit path when you need predictable file locations for review
or automation.

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

`--trigger-timeout-ms` controls how long trigger workflows wait before the
protective timeout path is used. Increase it only when the measurement setup
intentionally waits longer.

For complete accepted values and validation limits, see
[Validated Argument Limits](README.md#validated-argument-limits).

## CSV Output

Each captured sample is written as one CSV row. Check the CSV after a smoke run
for:

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
.\keysight-logger.exe stop
```

After stopping, confirm the command exits cleanly and the CSV contains the
expected rows.

## Common Problems

If `keysight-logger.exe` is missing, confirm you are in the release folder that
contains the CLI executable. If your release uses a versioned name such as
`keysight-logger-<version>.exe`, use that file name in the commands.

If `list-resources` shows stale resources, use `list-resources --verify` to see
which resources answer and why others failed. Use `--live-only` when you only
want resources that answered `*IDN?`.

If no live resource is found, check instrument power, USB/LAN/GPIB connection,
VISA driver visibility, and whether another program is holding the instrument.

If a run is blocked before opening the instrument, read the validation error and
adjust the option it names. The CLI validates common settings before live I/O.

If a hardware trigger run appears to wait, confirm the physical trigger signal,
slope, delay, and timeout. Missing trigger edges can make the run wait or re-arm
according to the configured timeout behavior.

## More CLI Documentation

- [CLI README](README.md): full command reference, validation scripts, examples,
  argument limits, and automation workflows.
- [CLI Integration](cli-integration.md): CLI adapter maintenance boundary.
- [Meters CLI JSON / JSONL Contract](../contracts/meters-cli-jsonl-contract.md):
  structured output schema for automation.
- [Meters Worker Contract](../contracts/meters-worker-contract.md): worker
  control plane and artifact contract.
