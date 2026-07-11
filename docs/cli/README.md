# Meters Tool CLI

## Documentation Set

- [CLI User Guide](USER_GUIDE.md) - operator workflow and common setting guidance.
- [CLI README](README.md) - detailed CLI reference, validation, and automation guide.
- [Changelog](CHANGELOG.md) - release notes and version history.
- [CLI Integration](cli-integration.md) - CLI adapter maintenance boundary.
- [Common CLI JSON / JSONL Contract](../contracts/common-cli-jsonl-contract.md) - shared command-line JSON envelope rules.
- [Meters CLI JSON / JSONL Contract](../contracts/meters-cli-jsonl-contract.md) - Meters command-line JSON schema and alias rules.
- [Common Orchestrator Workflows](../contracts/common-orchestrator-workflows.md) - shared subprocess lifecycle guidance.
- [Meters Orchestrator Workflows](../contracts/meters-orchestrator-workflows.md) - Meters subprocess examples for agents and automation.
- [Meters Worker Contract](../contracts/meters-worker-contract.md) - Meters worker control plane, JSONL, and artifact contract for agents and orchestrators.

CLI-first Python logger for supported digital multimeters, covering DC/AC
current, DC/AC voltage, DCV ratio, frequency, period, and 2-wire or 4-wire
resistance measurements over VISA.
It records one CSV row per captured sample and supports software, external
hardware, and immediate trigger modes.

For normal operator workflows, start with the [CLI User Guide](USER_GUIDE.md).
This README keeps the detailed command reference, validation paths, JSON/JSONL
contracts, examples, and maintainer-facing CLI behavior in one place.

`meters-tool` is the single-distribution baseline. Its package version is
`[project].version` in the root `pyproject.toml`. The CLI keeps its import
package, console command, JSON/JSONL contracts, wrapper scripts, and tests
while sharing that one version number with Core and WebUI. It
continues to expose Core measurement fields through the CLI:
`voltage-dc-ratio`, `frequency`, `period`, `--auto-zero once`,
`--ac-bandwidth-hz`, `--gate-time-s`, `--freq-period-timeout`, and
`--current-terminal`. Core start
validation, dry-run planning, runtime orchestration, public integration exports,
and measurement naming remain separated from adapter-only CLI concerns. This
baseline also keeps the legacy root-level import cleanup, CLI contract
diagnostics, no-hardware release validation, wrapper report metadata, and
Core/CLI boundary guards.

Python integrations should import shared APIs from `meters_tool_core` or
`meters_tool_core.*`. The old root-level Core module imports such as
`meters_tool.measurement` and `meters_tool.instrument` are no longer
supported.

## Current Scope

Implemented:

- VISA resource listing for USB and LAN resources discovered by PyVISA.
- DC current, DC voltage, DCV ratio, AC current, AC voltage, frequency, period,
  and 2-wire or 4-wire resistance measurement logging.
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
- Optional CLI-only PyVISA library/backend selection for VISA-opening commands
  through `--visa-library`, with `--backend` as an alias.
- Optional measurement controls: measurement type, Auto Range, manual range,
  DCV input impedance, Auto Zero including `once`, NPLC, AC bandwidth/filter,
  Frequency/Period gate time, Frequency timeout, current terminal selection, hardware
  trigger delay, hardware trigger slope, and VM Comp slope.
- Immediate CSV flush after every captured sample.

Important limitations:

- This project supports Keysight 34460A and 34461A Truevolt DMM logging. Live
  starts auto-detect the model from the connected instrument IDN when
  `--model` is omitted.
- Select `--model 34460A` when Start must require a 34460A IDN match. In live
  mode this is an expected-model guard only; it does not override the
  IDN-selected profile. In dry-run or simulate mode it selects the 34460A
  profile limits: no 10 A current range or current terminal selection, 1000
  readings of memory, and no base-profile external trigger modes.
- Select `--model 34461A` when Start must require a 34461A IDN match. Explicit
  live mismatches fail before setup SCPI. Model names are normalized and
  validated by Core profile logic; unknown models fail validation with the
  supported models listed.
- Live product support is feature-aware and exact-scope: the connection,
  measurement, and effective trigger mode must each be
  `live_validated_full_suite` for the detected model and exact transport/VISA
  backend. Missing feature metadata fails closed rather than inheriting
  support from another scope.
- 34460A DCV Ratio is implemented and profile-known but is
  `feature_pending` on USB/system-VISA. Normal CLI starts reject it. The hidden
  contributor validation mode may run a bounded evidence request, but does not
  promote product support.
- The 34460A has a lower maximum reading rate than the 34461A, but the CLI does
  not actively control high-speed reading rate in this release.
- AC, Frequency, and Period modes expose the 34461A `3`, `20`, and `200` Hz
  bandwidth/filter settings through
  `--ac-bandwidth-hz`. Before production use, run a low-risk live-resource
  smoke test with an operator-provided VISA resource and compare the CLI row to
  the 34461A front-panel reading.
- `--nplc` and `--auto-zero` are DC/resistance controls. AC current, AC
  voltage, Frequency, and Period accept only the neutral default `--nplc 1.0`;
  any other NPLC value is rejected because these modes do not write NPLC SCPI.
  They also do not write Auto Zero SCPI commands.
- Mixed software and hardware capture in the same run is not supported.
- Plain `list-resources` lists VISA resources returned by discovery and may
  include stale cached entries. Use `list-resources --verify` to open each
  resource and query `*IDN?`; successful non-ASRL verified resources are
  released back to local on a best-effort basis before closing. Use
  `list-resources --live-only` when you only want resources that answered.
  ASRL/RS-232 verification uses a short bounded open and query timeout so a
  stale serial entry does not block later USB or TCPIP resources.
- `immediate` mode can capture continuously and quickly. Use `--max-samples`
  unless you intentionally want a continuous run.

## Requirements

- Python 3.10 or newer.
- A VISA runtime, such as Keysight IO Libraries Suite or NI-VISA.
- A supported digital multimeter visible to VISA; see Supported Models for the
  currently validated models and connection scopes. The 34460A base profile
  does not assume optional LAN/LXI or external trigger support.

Optional pyvisa-py testing is supported through CLI arguments, but pyvisa-py is
not a required dependency. Install optional backend packages only when needed:

```powershell
uv pip install pyvisa-py pyserial psutil zeroconf
```

The validated optional pyvisa-py acquisition scope is 34461A over LAN/TCPIP.
34460A LAN/TCPIP and 34460A LAN/`@py` remain not open for the currently
available unit unless a future LAN/LXI-enabled 34460A is validated.

## Development

From PowerShell, change into the project directory, create or reuse the local
virtual environment, install the package with development dependencies, then
run the default tests:

```powershell
cd path\to\meters-tool
uv venv .venv
uv pip install -e ".[all,dev]"
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

If `uv` warns that hardlinking failed and it is falling back to copying files,
that warning is usually not a failed install. For cross-drive checkouts or
environments that do not support hardlinks, install with:

```powershell
uv pip install -e ".[all,dev]" --link-mode=copy
```

On Windows, the full pytest run may need an elevated PowerShell session because
VISA-related discovery or local environment access can require administrator
permissions.

After installation, use the `meters-tool` console script for project
commands:

```powershell
.\.venv\Scripts\meters-tool.exe <command> [options]
```

`.venv\Scripts\meters-tool.exe` is generated by installation and is not a
tracked project file. If it is missing, rerun `uv pip install -e ".[all,dev]"`.
If PowerShell blocks activation because of execution policy, keep using the
explicit `.venv\Scripts\...` commands shown in this guide.

The explicit module form is also supported as a development/fallback
alternative:

```powershell
.\.venv\Scripts\python.exe -m meters_tool_cli <command> [options]
```

Optional activation:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation because of execution policy, use the explicit
`.\.venv\Scripts\python.exe` commands shown above.

## Standalone EXE Build

The installed `.venv\Scripts\meters-tool.exe` is a virtualenv console
wrapper. It is not a standalone executable for machines without the project
environment.

To build the optional standalone console exe, use PyInstaller from an
environment that already has `meters-tool` installed. PyInstaller is a
local release-build tool, not a CLI runtime dependency, so install it into the
venv before rebuilding on a fresh machine:

```powershell
uv pip install pyinstaller
```

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_cli_exe.ps1
```

The output is:

```text
dist\meters-tool.exe
```

Run no-hardware smoke checks after rebuilding:

```powershell
.\dist\meters-tool.exe --version
.\dist\meters-tool.exe --help
.\dist\meters-tool.exe list-resources --dry-run --json
.\dist\meters-tool.exe start-trigger-record --resource SIM::34461A --simulate --measurement voltage-dc --trigger-mode immediate --max-samples 1 --csv .tmp_tests\cli_exe_smoke.csv --status-format jsonl
```

PyInstaller writes generated files under local `build\` and `dist\`
directories. Do not commit generated `.spec` files unless the project
intentionally switches to a checked-in PyInstaller spec.

## No-Hardware Validation

Run this recipe before live instrument work:

```powershell
uv pip install -e ".[all,dev]"
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\preflight-cli.ps1 -Target keysight-34461a
.\.venv\Scripts\meters-tool.exe list-resources --dry-run --json
```

`list-resources --dry-run` does not create a VISA resource manager, list VISA
resources, open resources, query `*IDN?`, or run release/local cleanup. If the
console script has not been generated yet, install the package first; the module
form above remains a development fallback.

## Live Instrument Validation

Use this section when moving to a new PC, a new VISA runtime, or a different
34460A or 34461A. Start with no-hardware validation, then discover a live
resource, then run a plan-only live wrapper before allowing the wrapper to touch
the instrument.

1. Run the no-hardware recipe above.
2. Discover resources that currently answer `*IDN?`:

```powershell
.\.venv\Scripts\meters-tool.exe list-resources --live-only --json
```

3. Copy one resource string from the JSON output and set it once for this
   PowerShell session. Use that exact value in the commands below. The live
   wrapper never scans for or guesses a resource:

```powershell
$env:METER_RESOURCE = "USB0::...::INSTR"
```

The value can be any live VISA resource returned by discovery, including USB
or TCPIP/LAN resources.

The live wrapper is a validation harness, not a product usage interface. It may
execute explicitly registered `transport_pending` connection scopes and
`feature_pending` measurement/trigger-mode entries with the exact operator-
provided resource so artifacts can be collected. A passing
`report.json` or `summary.md` does not by itself promote public support.
Normal CLI starts, the WebUI, and direct Core live calls remain product-gated
until reviewed artifacts are accepted and support metadata plus documentation
are updated.

4. Generate the live plan without opening VISA or changing the instrument:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\live-cli-check.ps1 `
  -Target keysight-34461a `
  -Connection usb `
  -Resource $env:METER_RESOURCE `
  -Suite minimal `
  -PlanOnly
```

5. If the plan looks correct, run the minimal live smoke test. The wrapper will
   run preflight first, print the planned instrument state changes, and require
   interactive Enter confirmation before live acquisition:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\live-cli-check.ps1 `
  -Target keysight-34461a `
  -Connection usb `
  -Resource $env:METER_RESOURCE `
  -Suite minimal
```

The minimal suite follows the existing `current-dc immediate` validation
convention and captures one bounded immediate-mode sample. It is live hardware
validation, not the generally safest smoke test; current cases require correct
current input wiring before execution. It writes `report.json`, `summary.md`,
command stdout/stderr files, and the case CSV under `.tmp_tests\cli_live\...`.
Check `summary.md` first; a passed case should show `captured=1`, `errors=0`,
and at least one CSV data row. Compare the CSV value with the instrument front
panel before trusting longer captures.

For broader live coverage, use `-Suite basic` after the minimal suite passes.
That suite covers immediate measurements and software-triggered paths. Current,
AC, resistance, Frequency, and Period live cases require the matching physical
wiring and/or stable signal source setup. The software timer case uses the CLI
PC-side path, `--trigger-mode software --timer-interval-s 0.5`; it does not mean
the 34460A profile supports instrument-side sample timer mode. Use
`-Suite frequency-period` when a stable input signal is connected and Frequency
and Period should each capture one immediate Auto Range sample. Use
`-Suite external` only with `-Target keysight-34461a` and only when an operator
can safely provide the required external trigger edge. Use `-Suite full` for
34461A only when basic, Frequency/Period, and external coverage are all
intended. For `-Target keysight-34460a`, `-Suite full` is `basic` plus
`frequency-period`; `external` is rejected because the base 34460A profile does
not support external trigger modes.

For validation of an optional PyVISA backend, pass `-VisaLibrary "@py"` to the
wrapper. `-Backend "@py"` is accepted as an alias, and `-visa-library "@py"`
is accepted as a convenience alias matching the CLI option name. The wrapper
forwards this to CLI `--visa-library` and records the backend in the artifacts.
When omitted, the wrapper uses system VISA and records `visa_library`/`backend`
as `system_visa`. If wrapper output says `VISA library/backend: system_visa`,
the run is not an `@py` validation artifact. Pending 34460A LAN/TCPIP
validation remains evidence collection only; it does not make normal 34460A
LAN/TCPIP product starts open.

Pending support means not open for product use yet, not impossible to validate.
The wrapper uses the hidden
`--validation-allow-pending-live-support` Core policy selector. It permits only
explicitly registered `transport_pending` and `feature_pending` entries; it is
not a general force option. Missing scope/feature metadata, unknown models,
unsupported profile capabilities, invalid requests, and hard safety limits
remain rejected. The 34460A base profile still keeps external/external-custom
closed, rejects 10 A/current-terminal requests, and preserves the 1000-reading
buffer limits. Its USB/system-VISA DCV Ratio entry is the explicit
`feature_pending` path that bounded validation may exercise. LAN/TCPIP or
pyvisa-py validation does not override hard limits.
For 34460A, LAN/TCPIP system-VISA and LAN/TCPIP pyvisa-py `@py` are future
validation paths for a LAN/LXI-capable unit or contributor-provided reviewed
artifact. They are not current maintainer validation debt for the available
USB-only 34460A unit and are not release blockers.

Preview the Frequency/Period live suite without opening VISA:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\live-cli-check.ps1 `
  -Target keysight-34461a `
  -Connection usb `
  -Resource $env:METER_RESOURCE `
  -Suite frequency-period `
  -PlanOnly
```

After reviewing the plans, remove `-PlanOnly` to run the two bounded live
cases. The suite uses Auto Range, a `20` Hz AC filter, a `0.1` second gate
time, automatic Frequency timeout, no Period timeout command, and one sample
per measurement.
Before each formal CLI case, a private diagnostic session validates identity
against the selected target model, sends the planned SCPI commands, and checks
`SYST:ERR?` after every command and after `READ?`. The report includes the IDN,
firmware revision, per-command error responses, and the diagnostic JSON path. A
probe error fails that case and skips its duplicate formal run while allowing
the other measurement to be diagnosed. Compare the reported value and CSV row
with the selected meter front panel. On a 34461A with firmware A.03.03, both
probes completed without SCPI errors and each formal case produced one sample
and CSV row after the Period timeout command was omitted. The
[Keysight Truevolt Series DMM Operating and Service Guide](https://www.keysight.com/us/en/assets/9018-03876/service-manuals/9018-03876.pdf),
Edition 10, May 2024, contains ambiguous timeout syntax; observed instrument
behavior is authoritative for the unsupported Period header.

If stdin is redirected and `-PlanOnly` is not set, `live-cli-check.ps1` refuses
live acquisition and writes a `confirmation_required` report. This is expected:
live instrument runs require an interactive confirmation.

## CLI Validation Scripts

The CLI package has three wrapper scripts:

| Script | Hardware use | Purpose |
| --- | --- | --- |
| `scripts\preflight-cli.ps1` | No hardware | Runs target-aware dry-run, simulator, client dry-run, mocked `list-resources`, and wrapper contract checks. Use this before live work. |
| `scripts\live-cli-check.ps1` | Live hardware unless `-PlanOnly` is set | Runs target-aware live-wrapper plans and, with interactive confirmation, bounded live validation cases against the explicit `-Resource`. Frequency/Period cases first run per-command SCPI error diagnostics. Suites are `minimal`, `basic`, `frequency-period`, `external`, and `full`; 34460A rejects `external` and its `full` suite excludes external cases. |
| `scripts\release-cli-check.ps1` | No hardware by default | Runs release gate checks, including full pytest, preflight, and `live-cli-check.ps1 -PlanOnly`. Its default validation mode is `release_no_hardware`. |

Promotion from `transport_pending` or `feature_pending` to
`live_validated_full_suite` requires reviewed artifacts and an explicit exact-
scope support metadata/docs update. Do not mark a pending scope or feature as
public live support in the same change that merely enables validation-mode
execution unless a reviewed artifact is already provided and approved.

## Basic Workflow

For a guided operator path with common setting explanations, use the
[CLI User Guide](USER_GUIDE.md). The short reference flow is:

1. List VISA resources.
2. Choose a resource string.
3. Start `start-trigger-record` in one terminal.
4. Send triggers, wait for external trigger edges, or use immediate mode.
5. Stop with `stop`, Ctrl+C, Ctrl+Break, `q`, or `--max-samples`.
6. Inspect the CSV output.

### 34460A Profile Examples

Use the 34460A expected-model guard when live-starting a 34460A. The same
`--model` value selects the 34460A profile for dry-run and simulator planning:

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --model 34460A `
  --resource "$env:METER_RESOURCE" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --max-samples 1
```

For 34460A custom modes, expected readings above its 1000-reading memory limit
require `--allow-buffer-overflow-risk`:

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --model 34460A `
  --resource "$env:METER_RESOURCE" `
  --trigger-mode immediate-custom `
  --measurement voltage-dc `
  --trigger-count 2 `
  --sample-count 1000 `
  --allow-buffer-overflow-risk
```

This flag only accepts the risk of `trigger_count * sample_count` exceeding
reading memory. It does not allow 10 A current range, `current_terminal=10`,
unsupported trigger modes, or `--buffer-drain-size` above the selected profile
reading memory.

### Optional PyVISA Backend Selection

By default, `meters-tool` uses `pyvisa.ResourceManager()` and therefore the
system VISA runtime, such as Keysight IO Libraries Suite or NI-VISA.

For advanced testing with pyvisa-py, install the optional backend packages and
pass `--visa-library "@py"` to CLI commands that open VISA resources:

```powershell
uv pip install pyvisa-py pyserial psutil zeroconf

uv run meters-tool list-resources --visa-library "@py" --verify

uv run meters-tool start-trigger-record `
  --model 34461A `
  --visa-library "@py" `
  --resource "$env:METER_RESOURCE" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --max-samples 1
```

`--backend "@py"` is accepted as an alias for `--visa-library "@py"`. This
option is intended for CLI diagnostics and optional backend validation. The
WebUI uses the default system VISA runtime and does not expose a backend
selector.

LAN/TCPIP is the validated 34461A pyvisa-py path. USBTMC on Windows may need
WinUSB/libusb setup and is often not simpler than Keysight IO Libraries Suite
or NI-VISA. RS-232/ASRL with pyvisa-py and pyserial is usually straightforward
when a supported instrument uses serial I/O, but the current Meters profiles
target USB/LAN Truevolt DMMs. `PYVISA_LIBRARY="@py"` can still affect PyVISA
directly, but this project recommends explicit `--visa-library "@py"` on CLI
commands so tests are reproducible.

## Command Reference

Use the installed console script:

```powershell
.\.venv\Scripts\meters-tool.exe <command> [options]
```

The module form remains an explicit development/fallback alternative:

```powershell
.\.venv\Scripts\python.exe -m meters_tool_cli <command> [options]
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
| `--version` | Print `meters-tool <package-version>` and exit without requiring a subcommand. |

`list-resources` options:

| Option | Description |
| --- | --- |
| none | Print raw VISA resources returned by PyVISA. This can include stale cached resources and does not open resources or run release-to-local cleanup. |
| `--verify` | Open each discovered resource and query `*IDN?`. Text output marks rows as `live` or `stale`; JSON output includes `live`, `status`, and `detail`. ASRL/RS-232 checks use a short bounded timeout. Successful non-ASRL live checks run best-effort release-to-local before closing. |
| `--live-only` | Verify resources and print only rows that answered. This implies `--verify`, suppresses stale resources, and still continues after an ASRL stale timeout. Successful non-ASRL live checks run best-effort release-to-local before closing. Text output prints `no live VISA resources found` if nothing is connected or reachable. |
| `--dry-run` | Print the resource-discovery contract and exit 0 without creating a VISA resource manager, listing resources, opening resources, querying `*IDN?`, or running release/local cleanup. Can be combined with `--verify`, `--live-only`, and `--json`. |
| `--visa-library TEXT`, `--backend TEXT` | Optional PyVISA library/backend argument, such as `@py`. Omit it to use the system default VISA runtime through `pyvisa.ResourceManager()`. |
| `--serial-read-termination VALUE` | CLI discovery/verification compatibility setting for ASRL resources only. Accepted values are `CRLF`, `LF`, `CR`, and `NONE`. It maps to the PyVISA session `read_termination` before querying `*IDN?`; it is not an acquisition setting. |
| `--serial-write-termination VALUE` | CLI discovery/verification compatibility setting for ASRL resources only. Accepted values are `CRLF`, `LF`, `CR`, and `NONE`. It maps to the PyVISA session `write_termination` before querying `*IDN?`; it is not an acquisition setting. |
| `--format json` | Emit one JSON object for scripts. Can be combined with `--verify` or `--live-only`. |
| `--json` | Alias for `--format json`. |

`send-command` options:

| Option | Default | Description |
| --- | --- | --- |
| `--port N` | `8765` | Local command endpoint port. Supported range: `1` to `65535`. |
| `--timeout-ms N` | `3000` | HTTP client timeout in milliseconds. Supported range: `100` to `600000`. |
| `--command NAME` | `software_trigger` | Meters command name. This revision supports only `software_trigger`. |
| `--arguments-json JSON` | `{}` | Complete JSON command arguments object. Use `{"metadata":{...}}` to attach trigger metadata written to CSV as `trigger_metadata`. Invalid JSON, non-object metadata, and other command validation failures are rejected before sending the request. |
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
| `--model MODEL`, `--instrument-model MODEL` | No | auto for live; required for non-deterministic dry-run/simulate | Expected model guard for live runs; model profile selector for dry-run/simulate. Core profile logic normalizes and validates model names, for example `34460A` or `34461A`, and reports unsupported models with the supported list. |
| `--visa-library TEXT`, `--backend TEXT` | No | system default | Optional PyVISA library/backend argument, such as `@py`. Dry-run and simulator runs accept the option but do not open VISA. |
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
| `--trigger-mode software\|external\|immediate\|immediate-custom\|software-custom\|external-custom` | No | `software` | Select exactly one acquisition mode. Supported choices are profile-specific; 34460A base profile excludes `external` and `external-custom`. |
| `--max-samples N` | Simple modes only | None | Stop simple modes automatically after N successful CSV samples. Supported range: `1` to `1000000`. Not valid with custom modes. |
| `--trigger-count N` | Custom modes only | None | Instrument trigger count. Supported range: `1` to `1000000`. Required with custom modes; not valid with simple modes. |
| `--sample-count N` | Custom modes only | None | Instrument sample count per trigger. Supported range: `1` to `1000000`. Required with custom modes; not valid with simple modes. |
| `--timer-interval-s SECONDS` | No | None | Enable fixed-delay software timer capture. Supported range: `0.5` to `86400` seconds. Valid only with `--trigger-mode software`; also valid when `--trigger-mode` is omitted because software is the default. May be combined with `--max-samples` for bounded timer runs. |
| `--buffer-drain-size N` | Custom modes only | None | Maximum readings to remove per buffer drain. Supported range: `1` to `10000`, capped by the instrument profile reading memory. Advanced option valid only with custom modes; does not change `TRIG:COUNT`, `SAMP:COUNT`, or instrument reading memory capacity. |
| `--allow-buffer-overflow-risk` | No | Off | Allow custom modes to request more readings than the selected profile reading memory. This depends on draining readings fast enough and may lose data or produce SCPI errors. It does not allow unsupported ranges, terminals, trigger modes, or `--buffer-drain-size` values above reading memory. |
| `--hw-trigger-slope pos\|neg` | No | `neg` | External trigger edge polarity. |
| `--hw-trigger-delay-s SECONDS` | No | `0.0` | Hardware trigger delay, mapped to `TRIG:DEL`. Supported range: `0` to `3600` seconds. |
| `--measurement current-dc\|voltage-dc\|voltage-dc-ratio\|current-ac\|voltage-ac\|frequency\|period\|resistance-2w\|resistance-4w` | No | `current-dc` | Measurement type. |
| `--nplc VALUE` | No | `1.0` | Integration time in power-line cycles for DC current, DC voltage, DCV ratio, and resistance. Allowed values for DC/resistance/ratio: `0.02`, `0.2`, `1`, `10`, `100`. AC current, AC voltage, Frequency, and Period accept only the neutral default `1.0`. |
| `--auto-zero on\|off\|once` | No | `on` | Auto Zero for supported measurements. `once` is valid with DC current, DC voltage, and 2-wire resistance. DCV ratio accepts only the default/on behavior and writes no Auto Zero SCPI; 4-wire resistance and AC measurements leave Auto Zero to the instrument. |
| `--auto-range on\|off` | No | `on` | Enable or disable Auto Range. |
| `--range VALUE` | Required when `--auto-range off` | None | Manual range for the selected measurement. Amps for current, volts for voltage, volts for Frequency/Period input range, and ohms for resistance. |
| `--current-range VALUE` | Current DC only | None | Compatibility alias for `--range` with `current-dc`. Do not combine with `--range`; invalid with AC current, voltage, and resistance measurements. |
| `--ac-bandwidth-hz 3\|20\|200` | AC/Frequency/Period only | Measurement-specific | AC bandwidth/filter setting. AC current/voltage leave it unchanged when omitted; Frequency/Period default to `20` Hz. |
| `--gate-time-s 0.01\|0.1\|1` | Frequency/Period only | `0.1` | Frequency/Period aperture or gate time in seconds. |
| `--freq-period-timeout auto\|1s` | Frequency only | `auto` | Use automatic Frequency timeout or disable auto timeout for the fixed 1-second behavior. Period rejects this option and sends no timeout SCPI. |
| `--current-terminal 3\|10` | Current only | None | Current input terminal for profiles that expose terminal selection. The 34461A 10 A range requires `--current-terminal 10`; `--current-terminal 10` is valid only with the 10 A range. The 34460A profile rejects current terminal selection. |
| `--dcv-input-impedance default\|10m\|auto` | DC Voltage or DCV Ratio only | `default` | DC voltage input impedance. `default` writes no impedance command; `10m` forces 10 MOhm; `auto` enables the instrument Auto mode, which may show HighZ on low DC voltage ranges. |
| `--vm-comp-slope pos\|neg` | No | None | Configure rear-panel VM Comp output pulse slope. Omit to leave VM Comp unchanged. |

`--measurement` defaults to `current-dc`, so existing current logging commands do
not need to specify it. New commands should prefer `--range`; `--current-range`
continues to work for existing DC current scripts. Use `--range` for
`current-ac`, `voltage-dc`, `voltage-dc-ratio`, `voltage-ac`, `frequency`,
`period`, `resistance-2w`, and `resistance-4w`; `--current-range` is rejected
with those measurements.
`--dcv-input-impedance` is valid only with `--measurement voltage-dc` or
`--measurement voltage-dc-ratio`. Use `default` to leave the instrument's
current Input Z setting unchanged, `10m` to force 10 MOhm, or `auto` to enable
the 34461A Auto Input Z behavior. The instrument may display HighZ while Auto
is active on lower DC voltage ranges.

## Agent-Friendly CLI Workflows

Use `--dry-run` to validate a command and inspect the planned SCPI/read path
without touching the instrument:

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --max-samples 1 `
  --dry-run `
  --status-format jsonl
```

Use `--simulate` for workflow checks without a real VISA session:

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
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

See [Meters CLI JSON / JSONL Contract](../../docs/contracts/meters-cli-jsonl-contract.md) for the current schema
and alias rules.

See [Meters Worker Contract](../../docs/contracts/meters-worker-contract.md) for the Meters worker modes, local
control endpoints, status payload, and wrapper artifact/report schema.

When the worker is running, `status` wraps non-mutating `GET /status` and
returns normalized JSON for orchestration health checks:

```powershell
.\.venv\Scripts\meters-tool.exe status --port 8765 --json
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

See [Meters Orchestrator Workflows](../../docs/contracts/meters-orchestrator-workflows.md) for a complete
Python subprocess workflow.

The `ready` event and `wait-ready` mean the local control plane can accept
`/command`, `/stop`, and `/status` requests. They are not first-sample signals.
Use the JSONL `run_id` as the correlation key between stdout runtime events,
`status` or direct `GET /status`, and wrapper artifacts from the same run.

### send-command --format json

```powershell
.\.venv\Scripts\meters-tool.exe send-command --port 8765 --format json
```

Output:

```json
{"command": "software_trigger", "event": "send-command", "http_status": 202,
 "job_id": null, "message": "command accepted", "schema_version": 1,
 "status": "accepted", "timestamp_utc": "2026-05-18T..."}
```

Local validation and worker HTTP `400` responses exit with code 2. HTTP `409`,
`429`, connection/request failures, and invalid or empty successful response
bodies exit with code 3. Structured JSON diagnostics merge worker `command`,
`job_id`, `reason`, `error`, and `message` fields when available.

### stop --format json

```powershell
.\.venv\Scripts\meters-tool.exe stop --port 8765 --format json
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
.\.venv\Scripts\meters-tool.exe status --port 8765 --format json
```

Output includes `event: "status"`, `reachable`, `ok`, `running`,
`stopping`, `run_id`, worker URLs, queue fields, `captured`, `errors`, and
`fatal_error`. `ok` is worker health: it is `true` only when the endpoint is
reachable and `fatal_error` is `null`.

### wait-ready --format json

```powershell
.\.venv\Scripts\meters-tool.exe wait-ready --port 8765 --timeout-ms 10000 --format json
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
| `--measurement` | `current-dc`, `voltage-dc`, `voltage-dc-ratio`, `current-ac`, `voltage-ac`, `frequency`, `period`, `resistance-2w`, `resistance-4w` |
| `--auto-zero` | `on`, `off`, or `once`, with measurement-specific limits |
| `--auto-range` | `on` or `off` |
| `--ac-bandwidth-hz` | `3`, `20`, or `200`, AC current/voltage and Frequency/Period only |
| `--gate-time-s` | `0.01`, `0.1`, or `1`, Frequency/Period only |
| `--freq-period-timeout` | `auto` or `1s`, Frequency only |
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
| `current-dc` | 34461A: `0.0001`, `0.001`, `0.01`, `0.1`, `1`, `3`, `10` A; 34460A: up to `3` A |
| `current-ac` | 34461A: `0.0001`, `0.001`, `0.01`, `0.1`, `1`, `3`, `10` A; 34460A: up to `3` A |
| `voltage-dc` | `0.1`, `1`, `10`, `100`, `1000` V |
| `voltage-dc-ratio` | `0.1`, `1`, `10`, `100`, `1000` V |
| `voltage-ac` | `0.1`, `1`, `10`, `100`, `750` V |
| `frequency` | `0.1`, `1`, `10`, `100`, `750` V input range |
| `period` | `0.1`, `1`, `10`, `100`, `750` V input range |
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
- AC current, AC voltage, Frequency, and Period reject non-default NPLC values.
  Omit `--nplc` or pass `--nplc 1.0`.
- `--auto-zero once` is valid only with `current-dc`, `voltage-dc`, and
  `resistance-2w`.
- `voltage-dc-ratio` accepts only default/on Auto Zero behavior.
- `--ac-bandwidth-hz` is valid only with `current-ac`, `voltage-ac`,
  `frequency`, or `period`.
- `--gate-time-s` is valid only with `frequency` or `period`.
- `--freq-period-timeout` is valid only with `frequency`.
- `--current-terminal` is valid only with current measurements on profiles that
  expose terminal selection. The 34461A 10 A range requires
  `--current-terminal 10`, and `--current-terminal 10` requires the 10 A range.
  The 34460A profile rejects current terminal selection.
- 34460A base profile rejects `external` and `external-custom` trigger modes.
- Custom modes require both `--trigger-count` and `--sample-count`; simple modes
  reject both options.
- Custom modes reject `--max-samples`; simple modes use `--max-samples` for
  bounded runs.
- `--buffer-drain-size` and `--allow-buffer-overflow-risk` are valid only with
  custom modes.
- Custom modes reject `trigger_count * sample_count` above the selected profile
  reading memory unless `--allow-buffer-overflow-risk` is set. The limit is
  10000 for 34461A and 1000 for 34460A.
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
.\.venv\Scripts\meters-tool.exe list-resources
```

Verify which resources are live:

```powershell
.\.venv\Scripts\meters-tool.exe list-resources --verify
```

Successful non-ASRL verified resources are released back to local on a
best-effort basis before the scan session closes. Stale resources that fail the
IDN query are closed without release SCPI. ASRL/RS-232 verification uses a
short bounded timeout and reports stale serial timeouts concisely.

Show only live resources and hide stale VISA cache entries:

```powershell
.\.venv\Scripts\meters-tool.exe list-resources --live-only
```

Use JSON output for scripts:

```powershell
.\.venv\Scripts\meters-tool.exe list-resources --verify --format json
```

For ASRL/RS-232 discovery only, optional termination settings can help a serial
device answer `*IDN?` during verification:

```powershell
.\.venv\Scripts\meters-tool.exe list-resources --verify `
  --serial-read-termination CRLF `
  --serial-write-termination LF
```

These serial termination options apply only while verifying ASRL resources in
`list-resources`. They are not acquisition runtime settings and are not applied
to USB or TCPIP resources.

Preview the discovery contract without touching VISA:

```powershell
.\.venv\Scripts\meters-tool.exe list-resources --dry-run --live-only --json
```

Verified output is tab-separated:

```text
live    USB0::<vendor_id>::<product_id>::<serial>::0::INSTR    Keysight Technologies,34461A,...
stale   USB0::OLD::RESOURCE::INSTR                     VisaIOError: ...
stale   ASRL6::INSTR                                   ASRL verification timed out after 1000 ms
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
2. Run a one-sample current, voltage, frequency, period, or resistance smoke test with
   `--trigger-mode immediate` and `--max-samples 1`.
3. Run the specific trigger mode needed for the experiment: software, timer,
   external, immediate, or custom/buffered.
4. Confirm the CSV `measurement_type`, `unit`, `trigger_source`, and row count.
5. Confirm graceful stop behavior with `stop`, Ctrl+C, Ctrl+Break, or `q`
   before relying on long unattended runs.

Before relying on unattended acquisition, validate the workflow with an
operator-provided Keysight 34461A VISA resource. Start with immediate mode, Auto
Range on, and `--max-samples 1`, then expand to the intended measurement,
trigger mode, and buffered mode. For AC current, AC voltage, Frequency, and
Period, compare the CLI CSV row to the 34461A front-panel reading during the
smoke test.

### Current DC Smoke Test

One immediate current sample:

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
.\.venv\Scripts\meters-tool.exe start-trigger-record `
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
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
.\.venv\Scripts\meters-tool.exe send-command --port 8765
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
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --auto-zero once `
  --max-samples 1 `
  --dry-run `
  --status-format jsonl
```

Simulated Auto Zero once workflow check:

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
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
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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

DCV Ratio uses the existing `VOLT:DC:RAT` implementation. It is product-open
for the validated 34461A scopes. The 34460A profile exposes the implemented
path for dry-run/simulator use, but its live USB/system-VISA measurement status
is `feature_pending`: normal CLI and WebUI starts reject it, while reviewed
hidden validation-mode use can collect bounded candidate evidence. Connect the
signal and reference leads according to the instrument manual before running
live; a miswired ratio measurement can look numerically plausible while
measuring the wrong relationship.

Dry-run DCV Ratio check:

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --trigger-mode immediate `
  --measurement voltage-dc-ratio `
  --max-samples 1 `
  --dry-run `
  --status-format jsonl
```

Simulated DCV Ratio workflow check:

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "SIM::34461A" `
  --csv ".\data\simulate_voltage_dc_ratio.csv" `
  --trigger-mode immediate `
  --measurement voltage-dc-ratio `
  --max-samples 1 `
  --simulate `
  --status-format jsonl
```

Product-open 34461A live DCV Ratio smoke check:

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --trigger-mode immediate `
  --measurement voltage-ac `
  --ac-bandwidth-hz 20 `
  --max-samples 1 `
  --dry-run `
  --status-format jsonl
```

Simulated AC bandwidth workflow check:

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
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
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --csv ".\data\voltage_ac_auto_smoke.csv" `
  --trigger-mode immediate `
  --measurement voltage-ac `
  --ac-bandwidth-hz 20 `
  --auto-range on `
  --max-samples 1
```

Suggested manual-range AC current smoke test:

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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

### Frequency And Period Smoke Tests

Frequency and Period share the scalar `READ?`, hardware-triggered `FETC?`, and
buffered capture paths. Their effective defaults are Auto Range, `20` Hz AC
filter, and `0.1` s gate time. Frequency defaults to automatic timeout. Period
sends no timeout SCPI and leaves the instrument's existing Period timeout state
unchanged.

Preview each setup before live I/O:

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --measurement frequency `
  --trigger-mode immediate `
  --max-samples 1 `
  --dry-run `
  --status-format jsonl

.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --measurement period `
  --trigger-mode immediate `
  --max-samples 1 `
  --dry-run `
  --status-format jsonl
```

After reviewing the plans, a bounded Auto Range live smoke run uses the same
commands without `--dry-run` and with an explicit `--csv` path. Run Frequency
and Period separately, one sample each, and compare the CSV value to the front
panel. Frequency rows use `measurement_type=frequency`, `unit=Hz`; Period rows
use `measurement_type=period`, `unit=s`.

The same pair of checks is available through
`scripts\live-cli-check.ps1 -Suite frequency-period`. The wrapper performs
preflight and dry-run planning first, requires interactive confirmation before
live I/O, checks the SCPI error queue after each planned Frequency/Period
command, and records the diagnostics plus each measured value and unit in
`report.json` and `summary.md`. `-PlanOnly` remains no-hardware and does not run
the SCPI probe.

### Validated Resistance 2-Wire Smoke Tests

These two resistance commands were reported OK on a real 34461A: Auto Range,
manual 1000 Ohm range, and CSV fields/values all looked normal.

Auto range, one immediate resistance sample:

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --csv ".\data\resistance_4w_auto_smoke.csv" `
  --trigger-mode immediate `
  --measurement resistance-4w `
  --auto-range on `
  --nplc 1.0 `
  --max-samples 1
```

Manual 1000 Ohm range, one immediate 4-wire resistance sample:

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
.\.venv\Scripts\meters-tool.exe send-command `
  --port 8765 `
  --arguments-json "{""metadata"":{""batch"":""A1"",""operator"":""lab""}}"
```

The metadata is accepted by the command endpoint and written to the CSV
`trigger_metadata` field as a JSON object string.

### Software Trigger Rate Limit And Queue Limit

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --csv ".\data\immediate_custom_1000.csv" `
  --trigger-mode immediate-custom `
  --trigger-count 1 `
  --sample-count 1000 `
  --auto-range off `
  --range 0.1 `
  --auto-zero off `
  --nplc 1.0
```

This mode uses the selected profile's reading memory to reduce per-sample
`READ?` communication overhead. It is not an instrument internal timer mode:
sample cadence is still
set by measurement speed, DC/resistance NPLC and Auto Zero, Auto Range, range
settling, and instrument trigger/sample behavior. CSV `trigger_metadata` marks
custom rows with `time_basis=pc_data_remove_time_not_instrument_sample_time`.
The expected row count is `trigger_count * sample_count`. Requests above the
selected profile reading memory are rejected unless `--allow-buffer-overflow-risk`
is set.

### Software Custom Mode

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
.\.venv\Scripts\meters-tool.exe send-command
.\.venv\Scripts\meters-tool.exe send-command
```

This mode arms the DMM with `TRIG:SOUR BUS`, `TRIG:COUNT`, and `SAMP:COUNT`.
Each accepted HTTP `send-command` sends one `*TRG`. The expected row count is
still `trigger_count * sample_count`; `trigger_count=2` and `sample_count=10`
should produce 20 CSV rows.

### External Custom Mode

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --csv ".\data\lan_software.csv" `
  --trigger-mode software `
  --max-samples 5
```

If `list-resources` still shows an old USB resource after unplugging, show only
resources that still answer with:

```powershell
.\.venv\Scripts\meters-tool.exe list-resources --live-only
```

Use `list-resources --verify` when you want to see both live and stale entries
for diagnosis.

### Slower High-Accuracy DC/Resistance Setup

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --csv ".\data\software_high_accuracy.csv" `
  --trigger-mode software `
  --auto-range off `
  --range 0.1 `
  --auto-zero on `
  --nplc 10.0
```

`--nplc 10.0` with `--auto-zero on` is slow for DC/resistance measurements. For
faster external trigger pacing, consider lower NPLC and Auto Zero off, for
example `--nplc 1.0 --auto-zero off`. AC, Frequency, and Period measurements
do not use Auto Zero and accept only neutral `--nplc 1.0`.

### VM Comp Slope

Omit `--vm-comp-slope` unless you need to configure the rear-panel VM Comp output
pulse slope.

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
.\.venv\Scripts\meters-tool.exe stop --port 8765
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
`ratio`, `Hz`, `s`, or `Ohm`). Custom/buffered modes may drain multiple
readings at once; the console status shows the last sample in that drain batch.

## CSV Output

If `--csv` is omitted, the logger writes to a UTC+8 timestamped file under
`data`, for example `data/2026-05-11-14-30-05.csv`. Passing `--csv PATH`
continues to write to that exact path.

CSV fields:

| Field | Description |
| --- | --- |
| `timestamp_utc_plus_8` | UTC+8 timestamp when the sample was read, serialized as ISO 8601 with a `+08:00` offset. |
| `measurement_type` | Selected measurement type, such as `current_dc`, `voltage_dc`, `voltage_dc_ratio`, `current_ac`, `voltage_ac`, `frequency`, `period`, `resistance_2w`, or `resistance_4w`. |
| `value` | Measured value. |
| `unit` | Unit, `A` for current, `V` for voltage, `ratio` for DCV Ratio, `Hz` for Frequency, `s` for Period, and `Ohm` for resistance. |
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
  `uv pip install -e ".[all,dev]" --link-mode=copy`.
- If `.\.venv\Scripts\meters-tool.exe` is missing, rerun
  `uv pip install -e ".[all,dev]"`. The console script is an install artifact, not
  a tracked project file.
- If PowerShell activation is blocked, keep using explicit
  `.\.venv\Scripts\python.exe` or `.\.venv\Scripts\meters-tool.exe`
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

Install development dependencies with `uv pip install -e ".[all,dev]"` as shown in
the Development section before running tests.

Default pytest run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

Unittest discovery, matching GitHub Actions:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

