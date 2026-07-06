# Supported Models

This file is the Core profile and model capability reference. Update it when
Core profile data, supported measurements, validation bounds, or live
validation expectations change.

## Model Profiles

Core currently provides these instrument profiles:

| Profile | Instrument | Reading memory | Current max | External trigger | Live validation |
| --- | --- | ---: | ---: | --- | --- |
| `keysight-34461a` | Keysight 34461A | 10000 | 10 A with 10A terminal | supported | expected IDN must match selected 34461A profile |
| `keysight-34460a` | Keysight 34460A | 1000 | 3 A | base profile disabled; optional LAN/external trigger not assumed | expected IDN must match selected 34460A profile; operator validation required |

The default profile is `keysight-34461a` to preserve existing behavior. CLI and
WebUI adapters can select the 34460A profile through their model selectors.

Live validation must use the explicit VISA resource supplied by the operator.
Core component validation must not scan, guess, or auto-select a resource.

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
