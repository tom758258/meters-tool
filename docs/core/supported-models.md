# Supported Models

This document describes current Product-open support for Meters Tool users.
It is the shared user-facing reference for supported models, connections,
backends, measurements, triggers, and important limits.

## Model Profiles

Meters Tool currently supports these instrument models:

| Model ID | Instrument | Reading memory | Current max | External trigger |
| --- | --- | ---: | ---: | --- |
| `keysight-34461a` | Keysight 34461A | 10000 | 10 A with 10A terminal | supported |
| `keysight-34460a` | Keysight 34460A | 1000 | 3 A | Not supported in base scope |

CLI and WebUI live runs detect 34460A/34461A from the connected instrument
identity when no model request is supplied. An explicitly selected model is an
expected-model check: a mismatch fails before setup instead of unlocking another
support scope. Dry-run and simulation may use the selected planning model.

## Exact-Scope Live Support

Live Product support is exact-scope based. Meters currently exposes one
independently supported Product workflow, `start-trigger-record`. A live run is
Product-open only when the detected model, workflow, exact transport/backend
connection scope, measurement, and trigger mode are supported together. Support
does not transfer between USB/system-VISA, TCPIP/system-VISA, and
TCPIP/pyvisa-py. Hard model/profile limits remain enforced.

Requests outside the current Product-open matrix, including unknown models,
unsupported connections or feature combinations, and hard safety limits, fail
closed.

In live mode, CLI `--model` and WebUI `Expected model` are expected-model
guards only. The runtime driver/profile is selected from the connected
instrument `*IDN?`. A selected/detected mismatch fails before instrument setup.
Dry-run and simulator runs use the selected/no-hardware planning profile and
do not query live hardware.

| Capability / workflow | 34461A | 34460A |
| --- | --- | --- |
| Immediate DC/AC voltage/current | Open | Open on USB/system-VISA |
| 2W/4W resistance | Open | Open on USB/system-VISA |
| Software trigger/timer | Open | Open on USB/system-VISA |
| Custom buffered workflows | Open | Open, limited by 1000-reading memory |
| Frequency | Open | Open on USB/system-VISA |
| Period | Open, no Period timeout option | Open, no Period timeout option |
| External simple/custom | Open | Not open in base 34460A profile |
| DCV Ratio | Open | Open only on USB/system-VISA |
| 10 A / current-terminal | Open with operator-confirmed wiring | Not supported |
| Buffer drain above profile memory | Up to 10000 readings | Not supported above 1000 |
| LAN/TCPIP with system VISA | Open for 34461A | Not currently supported |
| LAN/TCPIP with pyvisa-py `@py` | Open for 34461A in CLI, WebUI, and Desktop | Not currently supported |

### Exact-Scope Details

- **Wiring Safety & 10 A Path**: Selecting the 10 A current terminal requires manual operator confirmation of physical lead wiring to prevent hardware damage.
- **Reading Memory Limits**: 34461A custom runs above 10,000 readings and 34460A custom runs above 1,000 readings require explicit overflow-risk acknowledgement. Buffer drain remains capped at the model reading-memory limit.
- **Fail-Closed Policy**: Any model, transport, backend, measurement, or trigger combination not explicitly marked as open in the matrix above is unsupported and fails closed.

## VISA Backend Support

VISA backend support is part of the exact connection scope, not a model
capability. Normal Product operation uses the computer System VISA runtime
unless an interface explicitly exposes another supported backend. Optional
backend scopes remain independent: selecting another backend does not unlock
unsupported models, transports, measurements, or other Product support.
WebUI and Desktop expose System VISA (default) and PyVISA-py (`@py`) in
Device options. PyVISA-py is installed by default and bundled on Windows. It
supports 34461A TCPIP only; USB/`@py`, 34460A TCPIP, and other backends are
not Product-open. System VISA explicitly loads `@ivi` and fails if its runtime
is unavailable, even when `PYVISA_LIBRARY` requests another backend.

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

Each supported measurement has the model-specific ranges and limits listed in
the table below.

| Measurement | 34461A range choices | 34460A range choices | NPLC choices | AC filter | Gate time | Frequency timeout | Current terminal | DCV input Z | Auto Zero |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `current-dc` | 0.0001, 0.001, 0.01, 0.1, 1, 3, 10 A | 0.0001, 0.001, 0.01, 0.1, 1, 3 A | 0.02, 0.2, 1, 10, 100 | none | none | none | 34461A: 3, 10; 34460A: none | none | on, off, once |
| `voltage-dc` | 0.1, 1, 10, 100, 1000 V | same as 34461A | 0.02, 0.2, 1, 10, 100 | none | none | none | none | default, 10m, auto | on, off, once |
| `voltage-dc-ratio` | 0.1, 1, 10, 100, 1000 V | same as 34461A | 0.02, 0.2, 1, 10, 100 | none | none | none | none | default, 10m, auto | on/default only |
| `current-ac` | 0.0001, 0.001, 0.01, 0.1, 1, 3, 10 A | 0.0001, 0.001, 0.01, 0.1, 1, 3 A | none | 3, 20, 200 Hz | none | none | 34461A: 3, 10; 34460A: none | none | none |
| `voltage-ac` | 0.1, 1, 10, 100, 750 V | same as 34461A | none | 3, 20, 200 Hz | none | none | none | none | none |
| `frequency` | 0.1, 1, 10, 100, 750 V | same as 34461A | none | 3, 20, 200 Hz; default 20 | 0.01, 0.1, 1 s; default 0.1 | auto, 1s; default auto | none | none | none |
| `period` | 0.1, 1, 10, 100, 750 V | same as 34461A | none | 3, 20, 200 Hz; default 20 | 0.01, 0.1, 1 s; default 0.1 | none | none | none | none |
| `resistance-2w` | 100, 1000, 10000, 100000, 1000000, 10000000, 100000000 Ohm | same as 34461A | 0.02, 0.2, 1, 10, 100 | none | none | none | none | none | on, off, once |
| `resistance-4w` | 100, 1000, 10000, 100000, 1000000, 10000000, 100000000 Ohm | same as 34461A | 0.02, 0.2, 1, 10, 100 | none | none | none | none | none | none |

Auto Zero supports `on`, `off`, and `once` for `current-dc`, `voltage-dc`, and `resistance-2w`. `voltage-dc-ratio` accepts only the default/on Auto Zero request state. AC, Frequency, and Period measurements do not use NPLC or Auto Zero. Resistance 4-wire rejects the `once` Auto Zero choice.

DCV input impedance is available for `voltage-dc` and `voltage-dc-ratio`. Allowed values are `default`, `10m`, and `auto`; `default` preserves the current configured instrument state.

AC bandwidth/filter selection is available for `current-ac`, `voltage-ac`,
`frequency`, and `period`. Allowed values are `3`,
`20`, and `200` Hz. Leaving the field unset preserves the existing AC
current/voltage behavior. Frequency and Period instead apply the effective
default `20` Hz filter.

Frequency and Period use voltage range choices of `0.1`, `1`, `10`, `100`, and
`750` V. Auto Range is the default.

Gate time accepts `0.01`, `0.1`, or `1.0` seconds and defaults to `0.1`.

Frequency timeout accepts `auto` or `1s` and defaults to `auto`. Period does
not expose a timeout option. Explicit Period timeout values are rejected.

DCV Ratio readings use unit `ratio`. Frequency readings use `Hz`, and Period readings use `s`.

Current terminal selection is available only for the 34461A current profiles.
Selecting the 10 A range requires the 10 A terminal, and selecting the 10 A
terminal with a manual range requires the 10 A range. Operators must confirm
the range, terminal, and physical lead wiring to prevent hardware
damage. The 34460A current profiles support up to 3 A only and do not expose a
34461A-style 10 A terminal path.

## Trigger Capability

The 34461A supports:

- software
- software timer
- external
- immediate
- immediate-custom
- software-custom
- external-custom

The 34460A base scope supports:

- software
- software timer
- immediate
- immediate-custom
- software-custom

The 34460A base scope does not support external trigger modes because LAN/LXI/external trigger capability is optional on that model.

## Reading Memory

Custom runs compare the requested reading count with the model reading-memory limit.

- 34461A custom runs above 10000 readings require explicit overflow-risk acknowledgement.
- 34460A custom runs above 1000 readings require explicit overflow-risk acknowledgement.
- Buffer drain remains capped at the model reading-memory limit and is not relaxed by that acknowledgement.

## Unsupported Scope

Models not listed in this document are not currently supported in Product mode.
A model, connection/backend, measurement, trigger mode, or workflow combination
not listed as Product-open is unsupported. Unsupported combinations are rejected
rather than implicitly enabled.
