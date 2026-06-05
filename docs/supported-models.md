# Supported Models

This file is the manually maintained source of truth for CLI validation
targets, connection aliases, and live validation suites. When
`scripts/preflight-cli.ps1` or `scripts/live-cli-check.ps1` changes supported
targets, connection names, or suite coverage, update this file in the same
change.

## CLI Validation Matrix

Current CLI validation supports one instrument profile:

| Target | Instrument | Connection | Live |
| --- | --- | --- | --- |
| `keysight-34461a` | Keysight 34461A | USB/local | yes |
| `keysight-34461a` | Keysight 34461A | LAN/network | yes |

Connection aliases accepted by `scripts/live-cli-check.ps1`:

| User input | Canonical connection |
| --- | --- |
| `usb` | `usb` |
| `local` | `usb` |
| `lan` | `lan` |
| `network` | `lan` |

Rules:

- `scripts/preflight-cli.ps1` defaults to all targets and currently runs
  `keysight-34461a`.
- `scripts/live-cli-check.ps1` requires explicit `-Target`, `-Connection`, and
  `-Resource`.
- LAN live validation must use the explicit `-Resource` provided by the user.
  The live wrapper must not scan, guess, or auto-select a LAN resource.
- Adding another model or connection requires updating this matrix, then the
  validation scripts.

## Live Suite Coverage

`scripts/live-cli-check.ps1` accepts these suites:

| Suite | Coverage | External edge needed |
| --- | --- | --- |
| `minimal` | One current DC immediate smoke. | no |
| `basic` | Immediate one-sample captures for all six measurements, plus software trigger, software timer, immediate-custom, and software-custom current DC checks. | no |
| `external` | Simple external current DC and external-custom current DC checks. | yes |
| `full` | `basic` followed by `external`. | yes |

The default suite is `minimal`. The `external` and `full` suites require the
operator to provide the requested external trigger edges.
