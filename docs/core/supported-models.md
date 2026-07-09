# Supported Models

This file is the Core profile and model capability reference. Update it when
Core profile data, supported measurements, validation bounds, or live
validation expectations change.

This public document summarizes stable user-facing support behavior. The
internal model live support policy remains the source of truth for validation
evidence, implementation status, and future promotion decisions.

## Model Profiles

Core currently provides these instrument profiles:

| Profile | Instrument | Reading memory | Current max | External trigger | Live validation |
| --- | --- | ---: | ---: | --- | --- |
| `keysight-34461a` | Keysight 34461A | 10000 | 10 A with 10A terminal | supported | `live_validated_full_suite` for currently implemented profile-supported suite coverage |
| `keysight-34460a` | Keysight 34460A | 1000 | 3 A | base profile disabled; optional LAN/external trigger not assumed | `live_validated_full_suite` for USB/system-VISA suite-covered profile-supported workflows |

CLI and WebUI live starts auto-detect 34460A/34461A from `*IDN?` when the model
request is omitted. Explicit model selection is an expected-model guard for
live starts: Core validates it against the detected IDN and fails before setup
SCPI if the connected IDN reports a different supported model. The selected
model never overrides the live IDN-selected profile. Dry-run and simulator
starts use the selected model profile unless the simulator resource encodes a
single supported model token such as `SIM::34460A` or `SIM::34461A`.

Core profile logic normalizes requested model names, including lowercase input
such as `34460a` or `34461a`, and rejects unknown models with a validation
message that lists the supported models from the profile registry.

Live validation must use the explicit VISA resource supplied by the operator.
Core component validation must not scan, guess, or auto-select a resource. A
selected model in live mode is never a feature unlock; Core support policy and
the `run_start_session()` final gate use the detected `*IDN?` profile.

## Validation-Scoped Live Support

Live support is validation-scope based. A workflow is live-open only when an
operator-approved hardware validation pass covers that model, workflow, mode,
transport, and backend scope. Full-suite validation opens only the workflows in
that suite and only where the detected live profile supports the capability.
It does not override hard model/profile limits and does not promote untested
interfaces or VISA backends.

Validation tooling is separate from product support. The
`scripts/live-cli-check.ps1` harness may execute known pending live
transport/backend scopes with an exact operator-provided VISA resource to
collect evidence. Passing validation artifacts do not by themselves promote
public support. Normal CLI, WebUI, and direct Core live entry points remain
product-gated until reviewed artifacts are accepted and the support metadata
and documentation are updated.

Pending support means not open for product use yet, not impossible to validate.
Validation-mode execution is limited to known pending transport/backend scopes.
It cannot bypass unsupported-by-model workflows or hard profile limits.

In live mode, CLI `--model` and WebUI `Expected model` are expected-model
guards only. The runtime driver/profile is selected from the connected
instrument `*IDN?`. A selected/detected mismatch fails before setup SCPI.
Dry-run and simulator runs use the selected/no-hardware planning profile and
do not query live hardware.

| Capability / workflow | 34461A | 34460A |
| --- | --- | --- |
| Immediate DC/AC voltage/current | Open | Open for USB/system-VISA suite-covered scope |
| 2W/4W resistance | Open | Open for USB/system-VISA suite-covered scope |
| Software trigger/timer | Open | Open for USB/system-VISA suite-covered scope |
| Custom buffered workflows | Open | Open, limited by 1000-reading memory |
| Frequency | Open | Open for USB/system-VISA suite-covered scope |
| Period | Open, no Period timeout SCPI | Open, no Period timeout SCPI |
| External simple/custom | Open | Not open in base 34460A profile |
| DCV Ratio | Open for validated 34461A scope | Not promoted without separate 34460A artifact |
| 10 A / current-terminal | Open with operator-confirmed wiring | Not supported |
| Buffer drain above profile memory | Up to 10000 readings | Not supported above 1000 |
| LAN/TCPIP with system VISA | Open for validated 34461A scope | Not open for the currently available unit |
| LAN/TCPIP with pyvisa-py `@py` | Open for optional CLI-only validated 34461A LAN scope | Not open for the currently available unit |

34461A live support:

- Status: `live_validated_full_suite`.
- Open for currently implemented 34461A profile-supported full-suite workflows,
  including immediate, software, software timer, custom buffered, Frequency,
  Period, external simple, and external custom workflows.
- Validated transport/backend scopes are USB/system-VISA, LAN/TCPIP with the
  default system VISA runtime, and LAN/TCPIP with optional CLI-only pyvisa-py
  `@py`.
- Documented validated manual option smokes, including DCV Ratio and the 10 A
  current-terminal path, remain available where the profile supports them and
  the operator confirms safe wiring.

34460A live support:

- Status: `live_validated_full_suite` for USB/system-VISA scope.
- Open only for 34460A profile-supported workflows covered by the 2026-07-08
  USB full live CLI suite: immediate DC current, immediate DC voltage,
  immediate AC current, immediate AC voltage, immediate 2-wire resistance,
  immediate 4-wire resistance, software trigger, software timer, immediate
  custom buffered workflow, software custom buffered workflow, Frequency, and
  Period.
- Hard limits remain blocked: no 10 A current path, no current-terminal
  selection, 1000-reading memory limit, no buffer drain size above 1000, no
  base-profile external simple trigger, no base-profile external custom
  trigger, and no 34460A DCV Ratio live support unless a separate 34460A DCV
  Ratio validation artifact promotes it later.
- LAN/TCPIP with system VISA and LAN/TCPIP with pyvisa-py `@py` are not open
  for the currently available 34460A unit. Open those scopes only after a
  LAN/LXI-enabled 34460A TCPIP resource and operator-approved validation
  artifact exist.
- The live validation harness may collect artifacts for the known pending
  34460A LAN/TCPIP system-VISA and LAN/TCPIP pyvisa-py `@py` scopes. This does
  not make those scopes product-open.
- Hard limits remain closed during validation: base-profile 34460A external
  and external-custom workflows remain closed, 34460A DCV Ratio remains
  closed, the 10 A/current-terminal path remains unsupported, and buffer drain
  size remains capped by the 1000-reading profile limit. LAN/TCPIP or
  pyvisa-py validation does not override those limits.

Transport/backend scope status:

- USB/system-VISA validation does not validate LAN/TCPIP.
- USB/system-VISA validation does not validate pyvisa-py `@py`.
- 34461A LAN/TCPIP with system VISA is validated for the currently implemented
  suite-covered 34461A workflows.
- 34461A LAN/TCPIP with optional CLI-only pyvisa-py `@py` is validated for the
  currently implemented suite-covered 34461A workflows.
- 34460A LAN/TCPIP and 34460A LAN/`@py` remain pending/not open for the
  currently available unit.

Promotion from pending to `live_validated_full_suite` requires reviewed
artifacts and an explicit support metadata/docs update. Do not mark a scope
`live_validated_full_suite` in the same change that merely enables
validation-mode execution unless an actual reviewed artifact is already
provided and approved.

## VISA Backend Selection

VISA backend selection is not a model capability. When `visa_library` is unset,
Core creates live resource managers with `pyvisa.ResourceManager()` and uses the
system default VISA runtime. CLI commands that directly open VISA resources can
pass a PyVISA library/backend string such as `@py`; this only changes resource
manager creation to `pyvisa.ResourceManager("@py")`. It does not change SCPI
setup, trigger behavior, cleanup, CSV/JSONL schemas, or 34460A/34461A profile
validation.

The WebUI leaves `visa_library` unset and uses the default system VISA runtime.
For pyvisa-py diagnostics, LAN/TCPIP is the recommended first path to try.
USBTMC on Windows may require WinUSB/libusb setup. The `PYVISA_LIBRARY`
environment variable remains PyVISA-level behavior, but explicit CLI
`--visa-library "@py"` is preferred for reproducible tests.

LAN/TCPIP and pyvisa-py `@py` remain separate validation scopes. They are not
promoted by USB/system-VISA full-suite results. The current validated optional
backend scope is 34461A LAN/TCPIP with CLI-only pyvisa-py `@py`; pyvisa-py is
not required for normal system VISA usage, and the WebUI does not expose a
backend selector.

## Measurement Capability

The 34460A and 34461A profiles currently expose the same measurement names, in
profile order:

- `current-dc`
- `voltage-dc`
- `voltage-dc-ratio`
- `current-ac`
- `voltage-ac`
- `frequency`
- `period`
- `resistance-2w`
- `resistance-4w`

Profile data owns per-measurement range, NPLC, AC bandwidth/filter, gate time,
Frequency timeout, current terminal, DCV input impedance, and Auto Zero
validation where applicable. Adapters can retrieve the same Core-owned facts
through `get_core_capabilities()` instead of reading profile internals.

| Measurement | 34461A range choices | 34460A range choices | NPLC choices | AC filter | Gate time | Frequency timeout | Current terminal | DCV input Z | Auto Zero |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `current-dc` | 0.0001, 0.001, 0.01, 0.1, 1, 3, 10 A | 0.0001, 0.001, 0.01, 0.1, 1, 3 A | 0.02, 0.2, 1, 10, 100 | none | none | none | 34461A: 3, 10; 34460A: none | none | on, off, once |
| `voltage-dc` | 0.1, 1, 10, 100, 1000 V | same as 34461A | 0.02, 0.2, 1, 10, 100 | none | none | none | none | default, 10m, auto | on, off, once |
| `voltage-dc-ratio` | 0.1, 1, 10, 100, 1000 V | same as 34461A | 0.02, 0.2, 1, 10, 100 | none | none | none | none | default, 10m, auto | on/default only; no Auto Zero SCPI |
| `current-ac` | 0.0001, 0.001, 0.01, 0.1, 1, 3, 10 A | 0.0001, 0.001, 0.01, 0.1, 1, 3 A | none | 3, 20, 200 Hz | none | none | 34461A: 3, 10; 34460A: none | none | none |
| `voltage-ac` | 0.1, 1, 10, 100, 750 V | same as 34461A | none | 3, 20, 200 Hz | none | none | none | none | none |
| `frequency` | 0.1, 1, 10, 100, 750 V | same as 34461A | none | 3, 20, 200 Hz; default 20 | 0.01, 0.1, 1 s; default 0.1 | auto, 1s; default auto | none | none | none |
| `period` | 0.1, 1, 10, 100, 750 V | same as 34461A | none | 3, 20, 200 Hz; default 20 | 0.01, 0.1, 1 s; default 0.1 | none | none | none | none |
| `resistance-2w` | 100, 1000, 10000, 100000, 1000000, 10000000, 100000000 Ohm | same as 34461A | 0.02, 0.2, 1, 10, 100 | none | none | none | none | none | on, off, once |
| `resistance-4w` | 100, 1000, 10000, 100000, 1000000, 10000000, 100000000 Ohm | same as 34461A | 0.02, 0.2, 1, 10, 100 | none | none | none | none | none | none |

Auto Zero supports `on`, `off`, and `once` for `current-dc`, `voltage-dc`, and
`resistance-2w`. `voltage-dc-ratio` accepts only the default/on Auto Zero
request state and does not emit Auto Zero SCPI because the instrument does not
allow Auto Zero configuration after DCV Ratio is enabled. AC, Frequency, and
Period measurements do not use NPLC or Auto Zero. Resistance 4-wire uses the
`FRES` SCPI family and does not write Auto Zero SCPI, so
`auto_zero="once"` is rejected for `resistance-4w`.

DCV input impedance is available for `voltage-dc` and `voltage-dc-ratio`
through `dcv_input_impedance`. Allowed values are `default`, `10m`, and `auto`.
`default` preserves the current configured instrument state; `10m` writes
`VOLT:DC:IMP:AUTO OFF`; `auto` writes `VOLT:DC:IMP:AUTO ON`.

DCV Ratio stores the primary ratio in `MeasurementSample.value` with unit
`ratio`. Each ratio sample also stores `measurement_metadata` with
`signal_voltage_v`, `reference_voltage_v`, and `secondary_source="SENS:DATA"`.
Simple ratio reads use `READ?` or hardware-triggered `FETC?`, then `DATA2?`.
Custom buffered ratio modes drain one reading at a time with `DATA:REMove? 1`
and query `DATA2?` per sample so the secondary signal/reference voltages stay
paired with each ratio value.

AC bandwidth/filter selection is available for `current-ac`, `voltage-ac`,
`frequency`, and `period` through `ac_bandwidth_hz`. Allowed values are `3`,
`20`, and `200` Hz. Leaving the field unset preserves the existing AC
current/voltage behavior. Frequency and Period instead apply the effective
default `20` Hz filter.

Frequency and Period use voltage range choices of `0.1`, `1`, `10`, `100`, and
`750` V. Auto Range is the default. `gate_time_s` accepts `0.01`, `0.1`, or
`1.0` seconds and defaults to `0.1`. For Frequency,
`freq_period_timeout` accepts `auto` or `1s` and defaults to `auto`. Period
does not expose a timeout option and sends no timeout SCPI, leaving the
instrument's Period timeout state unchanged. Explicit Period timeout values are
rejected before instrument I/O. Frequency samples use unit `Hz`; Period samples
use unit `s`.

This Period behavior was validated on a 34461A with firmware A.03.03. The
[Keysight Truevolt Series DMM Operating and Service Guide](https://www.keysight.com/us/en/assets/9018-03876/service-manuals/9018-03876.pdf)
contains ambiguous timeout syntax; the implementation follows observed
instrument behavior and does not send the unsupported Period header.

Current terminal selection is available only for the 34461A `current-dc` and
`current-ac` profiles. Selecting the 10 A current range requires
`current_terminal=10`; selecting `current_terminal=10` requires the 10 A range
when a manual range is supplied. When the 10 A terminal is explicit, Core
writes `CURR:{DC|AC}:TERM 10` and does not write `CURR:{DC|AC}:RANG 10`.

The 34460A current profiles support up to 3 A only. They do not expose
`current_terminal` because the 34460A does not have the 34461A-style 10 A
terminal path.

## Trigger Capability

Core validation and planning derive trigger modes from the selected profile.

The 34461A profile supports:

- `software`
- software timer through `timer_interval_s`
- `external`
- `immediate`
- `immediate-custom`
- `software-custom`
- `external-custom`

The 34460A base profile supports:

- `software`
- software timer through `timer_interval_s`
- `immediate`
- `immediate-custom`
- `software-custom`

Simple software and immediate reads use `READ?`. Simple external-triggered
reads use `FETC?` after the hardware trigger adapter arms and completes the
measurement. Custom and buffered modes use the existing buffered acquisition
path.

The 34460A base profile does not enable external trigger modes because
LAN/LXI/external trigger capability is optional on that model. Add a separate
profile only after the option is confirmed and validated on hardware.

## Reading Memory

Custom modes compare `trigger_count * sample_count` with the selected
profile's `reading_memory_limit`.

- 34461A requests above 10000 readings require `--allow-buffer-overflow-risk`.
- 34460A requests above 1000 readings require `--allow-buffer-overflow-risk`.
- `--buffer-drain-size` remains capped at the profile reading memory and is not
  relaxed by `--allow-buffer-overflow-risk`.

## Hardware Validation Plan

34460A scripted live validation plan:

1. Identify the instrument and confirm IDN matches the selected 34460A profile.
2. `minimal` follows the existing `current-dc` immediate validation convention;
   current live cases require correct current input wiring.
3. `basic` mirrors supported 34461A live cases: DC/AC current, DC/AC voltage,
   2-wire/4-wire resistance, software trigger, CLI-side software timer,
   `immediate-custom`, and `software-custom`.
4. `frequency-period` runs one Frequency and one Period immediate sample and
   requires a stable input signal.
5. `full` is `basic` plus `frequency-period`; it does not include external
   trigger cases.
6. Confirm `current-dc` manual range 3 A dry-run is accepted.
7. Confirm `current-dc` manual range 10 A dry-run is rejected before VISA I/O.
8. Confirm expected readings 1001 without allow flag is rejected in dry-run.
9. Confirm expected readings 1001 with allow flag is accepted in dry-run.
10. Leave external trigger disabled until the specific 34460A has the required
   LAN/external trigger option confirmed.

## Future Models

Add new models by adding or extending Core profiles first. Add SCPI dialect
behavior only when a real model proves the shared command set is wrong for that
model. Keep model validation changes paired with focused Core tests and an
operator-approved hardware validation plan.
