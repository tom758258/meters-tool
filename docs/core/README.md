# Meters Tool Core

Core contains the public API and acquisition runtime contract used by the CLI
and WebUI components for supported digital multimeter integrations. It ships
inside the single `meters-tool` distribution while preserving the
`meters_tool_core` import boundary.

## Purpose And Ownership

Core owns the shared request model, request validation, dry-run planning,
runtime session orchestration, instrument-profile metadata, live-support
policy, runtime events and results, control-plane interfaces, and acquisition
safety rules.

CLI and WebUI own their input parsing, display text, localization, terminal and
browser workflows, serialization, HTTP/SSE payloads, and other
adapter-specific contracts. Core must not import `meters_tool_cli` or
`meters_tool_webui`.

Core can carry an optional `visa_library` value through `StartRequest` and
`InstrumentConfig`. When it is unset, live VISA sessions use
`pyvisa.ResourceManager("@ivi")` to require the System VISA runtime without
auto-fallback or an environment backend override. CLI, WebUI, and Desktop can
select the bundled `@py` backend for the registered 34461A TCPIP scope.

For support-policy matching, an unset or blank selector maps to `system_visa`,
`@py` maps to `pyvisa_py`, `@bt` is reserved as the distinct `pyvisa_bt`
identity, and other selectors map to `custom_visa`. A backend identity does not
itself grant Product support; live acquisition requires an exact registered
Product-open scope in [Supported Models](supported-models.md). Unregistered backend
selectors fail closed under generic support-policy rules. The WebUI accepts only unset/empty System VISA or `@py` selectors.

## Request Admission And Adapter Boundary

`StartRequest` is the shared Core request boundary for validation, dry-run
planning, simulation, and runtime session setup. Adapters must convert their
own input into Core-owned values before submitting a request.

Before constructing `StartRequest`, adapters should:

- convert empty optional fields to `None`;
- convert numeric inputs to `int` or `float`;
- convert toggles to booleans or the documented Core semantic values;
- normalize adapter-owned aliases;
- map localized labels and display choices to canonical Core values;
- keep terminal formatting, localized strings, browser labels, HTTP/SSE
  payload details, wrapper compatibility fields, and other adapter schemas
  outside Core.

CLI `argparse.Namespace` objects and WebUI form or JSON objects must not become
the Core validation contract. They must first be translated into
`StartRequest`.

Core validation is authoritative even when an adapter has already disabled or
filtered an option. Unsupported profile combinations, invalid request values,
and missing live-support scopes fail closed. `run_start_session()` resolves
the runtime profile and repeats the final request-validation and support-policy
gate before backend connection and instrument setup, so direct Core callers
cannot bypass the same boundary used by CLI and WebUI.

See [Core Integration](integration.md#request-boundary) for the complete field
normalization and validation flow.

## Physical Identity And Profile Boundary

`InstrumentProfile.model` is the canonical instrument model token used by
existing request, expected-model, IDN, CLI, WebUI, and runtime contracts:

| Instrument | Canonical model | Stable model ID |
| --- | --- | --- |
| Keysight 34461A | `34461A` | `keysight-34461a` |
| Keysight 34460A | `34460A` | `keysight-34460a` |

The canonical model and stable model ID are related but have different roles.
Display text such as `Keysight 34461A` is presentation only. Stable model IDs
are explicitly declared by Core profiles and are not generated from localized
or display text.

For a live start:

- omitted `StartRequest.instrument_model` means that Core resolves the
  connected profile from `*IDN?`;
- an explicitly selected model is an expected-model guard only;
- the detected `*IDN?` identity remains authoritative;
- a selected/detected mismatch must fail before instrument-affecting setup or
  write SCPI;
- selecting a model or stable model ID never unlocks support for different
  hardware.

For dry-run and simulation, the selected model is the no-hardware planning
profile. An explicit model is required unless the simulator resource
deterministically names one, such as `SIM::34460A` or `SIM::34461A`.

Adapters must use Core profile lookup and normalization rather than maintaining
a competing model or model-ID registry.

See [Core Integration](integration.md#profile-identity) for the full identity
contract.

## Live Support Policy

Normal CLI, WebUI, and direct Core starts use Product mode. Product mode
requires the exact detected model, connection scope, and requested features to
be Product-open together. Live evaluation is based on all of the following:

1. the detected model profile;
2. the exact transport and VISA backend scope;
3. the normalized measurement feature;
4. the effective trigger-mode feature.

Support for one connection scope does not open another scope. For example,
USB/system-VISA support does not automatically open LAN/system-VISA or
LAN/pyvisa-py.

Core is the final support and safety gate for adapters and direct callers.
`run_start_session()` repeats the final request-validation and support-policy
check before backend connection and instrument setup. Unsupported or
non-Product-open scope requests fail closed. The simulator validates
deterministic no-hardware contracts and workflows only; it is not evidence of
live measurement accuracy or hardware support.

See [Supported Models](supported-models.md) for the user-facing support matrix
and [Core Integration](integration.md) for the support-policy machine contract
and policy modes. See [Contributing](../CONTRIBUTING.md) for contributor
validation and promotion.

## Frequency/Period SCPI Compatibility

Frequency and Period intentionally use different timeout configuration behavior.
Frequency supports timeout configuration, while Period does not expose a timeout
option or send a Period timeout SCPI command.

This distinction is deliberate and should not be changed solely by assuming
that Frequency and Period support equivalent SCPI commands. When revisiting the
behavior, consult the [Keysight Truevolt Series DMM Operating and Service Guide](https://www.keysight.com/us/en/assets/9018-03876/service-manuals/9018-03876.pdf)
and perform model-appropriate real-instrument validation before changing the
Core command sequence.

## Public Package Surface

Consumers should prefer imports from the `meters_tool_core` package root. The
package-root `__all__` list is the stable public import boundary. The following
modules provide the main public areas behind that boundary:

| Module | Public responsibility |
| --- | --- |
| `meters_tool_core.capabilities` | Adapter-facing measurement and profile capability projections |
| `meters_tool_core.models` | `StartRequest`, instrument profiles, model normalization, and profile resolution |
| `meters_tool_core.run_plan` | Dry-run `StartPlan` construction |
| `meters_tool_core.validation` | Request validation, trigger-mode resolution, and buffer-overflow warnings |
| `meters_tool_core.support_policy` | Exact live-support lookup, feature requirements, metadata validation, and enforcing policy gates |
| `meters_tool_core.session` | Runtime events, results, control-plane interfaces, and stop control |
| `meters_tool_core.runner` | Final runtime orchestration through `run_start_session()` |

These modules explain ownership; downstream adapters should still prefer the
documented package-root imports rather than relying on implementation-only
helpers inside submodules.

Do not present internal helpers, test hooks, or compatibility aliases as public
API. The exact package-root export list is defined by
`src/meters_tool_core/__init__.py` and documented in
[Core Integration](integration.md#public-imports).


## Validation

No-hardware Core validation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/core -q -p no:cacheprovider
```

Core validation should not require CLI or WebUI imports except through tests
that explicitly check the component boundary.

## Documentation

- [Core Integration](integration.md)
- [Supported Models](supported-models.md)
- [Changelog](../../CHANGELOG.md)
