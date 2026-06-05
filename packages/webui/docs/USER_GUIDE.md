# Keysight Logger WebUI User Guide

This guide is for operators using the local WebUI to record measurements from a
Keysight 34461A. It avoids developer details and focuses on the normal
measurement workflow.

## What The WebUI Does

The WebUI starts a local browser page for configuring and monitoring an
acquisition run. It can:

- Find connected VISA instruments.
- Start one measurement run at a time.
- Record readings to a CSV file.
- Show the latest reading and recent readings while the run is active.
- Send a software trigger when the selected trigger mode needs it.
- Stop the current run and open the completed CSV file.

The WebUI runs on the same Windows computer that has access to the instrument.
It is not a cloud service.

## Start The WebUI

For normal use, double-click:

```text
keysight-logger-webui-launcher.exe
```

In the launcher window:

1. Keep `Use default port 8767` selected unless that port is already in use.
2. Click `Start`.
3. Wait for the browser to open.
4. Click `Quit` in the launcher when you are done with the WebUI.

If you start from a terminal instead, run:

```powershell
.\.venv\Scripts\keysight-logger-webui-launcher.exe
```

The browser address is normally:

```text
http://127.0.0.1:8767/
```

## Screen Overview

The WebUI is a local acquisition console. The main areas are:

- `VISA resource`: the instrument address to use for the run.
- `Live resource`: the instrument detected by a scan.
- `Scan Device`: searches for connected live instruments.
- `Run Setup`: CSV output path and run count settings.
- `Measurement`: measurement type and related options.
- `Trigger`: trigger mode and trigger-related options.
- `Status`: current run state, captured sample count, errors, CSV path, and log.
- `Live data`: latest reading, trend chart, recent samples, and selected sample
  details.

## First Run

Use this flow for a basic immediate measurement:

1. Turn on the Keysight 34461A and connect it to the computer.
2. Start the WebUI.
3. Click `Scan Device`.
4. Select or copy the detected VISA resource into `VISA resource`.
5. Choose the measurement type, such as DC voltage or DC current.
6. In `Run Setup`, choose the CSV location. Use `Select` to pick a folder and
   generate a timestamped CSV path.
7. Leave trigger mode on the immediate/default mode unless you specifically
   need software or external triggering.
8. Review the highlighted settings.
9. Click `Start`.
10. Watch `Captured`, `Status`, and `Live data`.
11. Click `Stop` when the run should end.
12. Click `Open CSV` after the run stops to open the completed CSV file.

Only one run can be active at a time. Starting a new run clears the displayed
recent samples from the previous run.

## Choosing A Trigger Mode

Use immediate mode for the simplest workflow. The instrument takes readings as
soon as the run starts.

Use software trigger mode when the run should wait for an operator action from
the WebUI. After the run starts, click `Trigger` to send each software trigger.

Use external or hardware trigger modes only when a physical trigger signal is
connected and configured for the instrument. Hardware trigger timeout is a
protective re-arm condition, not automatically a failed measurement.

Do not change trigger timing, trigger delay, NPLC, Auto Range, Auto Zero, VM
Comp, or current terminal settings unless the measurement setup requires it and
the operator understands the effect on the instrument.

## CSV Output

The CSV path shown in `Run Setup` is the file that will be used when `Start` is
clicked.

`Select` opens a folder picker on the Windows computer running the WebUI. After
you choose a folder, the WebUI fills in a timestamped CSV file path in that
folder. You can edit the path manually before clicking `Start`.

`Open CSV` is available after a completed run has a CSV path. It opens the last
completed run CSV using the Windows default app. It is disabled while a run is
active.

## Stop And Exit

Use `Stop` in the browser to stop the current acquisition run. The WebUI keeps
the latest readings visible after the run stops so you can review them.

Use `Quit` in the launcher window to stop the local WebUI server and close the
launcher. Closing only the browser tab does not necessarily stop the server.

If you started the WebUI from a terminal, use `Ctrl+C` in that terminal to stop
the server.

## Common Problems

### The browser does not open

Open this address manually:

```text
http://127.0.0.1:8767/
```

If the page still does not load, return to the launcher and check whether it
shows a startup error.

### The launcher says the port is already in use

Another program is already using the selected port. If another WebUI is already
running on that port, the launcher opens it. If the port is used by something
else, choose a different port or close the other program.

### Scan Device finds nothing

Check that:

- The instrument is powered on.
- The USB/LAN/GPIB connection is attached.
- The VISA driver can see the instrument.
- No other program is holding the instrument connection.

You can still type a known VISA resource manually.

### Start is blocked

Make sure `VISA resource` is filled in and highlighted settings have valid
values. The Status log shows the setting that needs attention.

### Open CSV is disabled

`Open CSV` is disabled until a run stops and a completed CSV path is available.
It also stays disabled while a run is active.

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

