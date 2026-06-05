# Supported Models

This file is the Core profile and model capability reference. Update it when
Core profile data, supported measurements, validation bounds, or live
validation expectations change.

## Current Profile

Core currently provides one default instrument profile:

| Profile | Instrument | Live validation |
| --- | --- | --- |
| `keysight-34461a` | Keysight 34461A digital multimeter | USB or LAN through explicit VISA resource |

Live validation must use the explicit VISA resource supplied by the operator.
Core branch validation must not scan, guess, or auto-select a resource.

## Measurement Capability

The 34461A profile supports these measurement names:

- `current-dc`
- `voltage-dc`
- `current-ac`
- `voltage-ac`
- `resistance-2w`
- `resistance-4w`

Profile data owns per-measurement range, NPLC, AC bandwidth, and current
terminal validation where applicable.

Auto Zero supports `on`, `off`, and `once` for `current-dc`, `voltage-dc`, and
`resistance-2w`. AC measurements do not use NPLC or Auto Zero. Resistance
4-wire uses the `FRES` SCPI family and does not write Auto Zero SCPI, so
`auto_zero="once"` is rejected for `resistance-4w`.

AC bandwidth is available for `current-ac` and `voltage-ac` through
`ac_bandwidth_hz`. Allowed values are `3`, `20`, and `200` Hz. Leaving the
field unset preserves the existing `CONF:*:AC AUTO` behavior and writes no
bandwidth SCPI.

Current terminal selection is available for `current-dc` and `current-ac`
through `current_terminal`. Allowed values are `3` and `10`. Selecting the
10 A current range requires `current_terminal=10`; selecting `current_terminal=10`
requires the 10 A range when a manual range is supplied. When the 10 A terminal
is explicit, Core writes `CURR:{DC|AC}:TERM 10` and does not write
`CURR:{DC|AC}:RANG 10`.

## Trigger Capability

Core validation and planning cover:

- `software`
- software timer through `timer_interval_s`
- `external`
- `immediate`
- `immediate-custom`
- `software-custom`
- `external-custom`

Simple software and immediate reads use `READ?`. Simple external-triggered
reads use `FETC?` after the hardware trigger adapter arms and completes the
measurement. Custom and buffered modes use the existing buffered acquisition
path.

## Future Models

Add new models by adding or extending Core profiles first. Add SCPI dialect
behavior only when a second real model proves the shared command set is wrong
for that model. Keep model validation changes paired with focused Core tests
and an operator-approved hardware validation plan.
