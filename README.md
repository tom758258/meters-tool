[繁體中文](README.zh-TW.md)

# Meters Tool

Meters Tool is a Python data acquisition and logging toolkit for supported digital
multimeters, including Keysight 34460A and 34461A. See
[Supported Models](docs/core/supported-models.md) for exact Product support. The single
`meters-tool` distribution contains the independent Core, CLI, and WebUI packages.

It measures DC/AC voltage and current, DC voltage ratio, frequency, period, and 2-/4-wire
resistance over VISA. Samples default to compact `data` CSV (timestamp, value, unit). Use CLI
`--csv-format full` or WebUI/Desktop `Full` to retain trigger and measurement metadata,
with optional elapsed and sample-interval columns. Disable CSV with CLI `--no-csv` or the WebUI `CSV output`
checkbox. CLI `--streaming --json` defaults to no CSV; use `--csv PATH` to save.

System VISA requires a separate runtime; bundled PyVISA-py supports the Product-open
34461A TCPIP scope. Dry-run and simulation require no VISA runtime.

## Features

* Control supported digital multimeters over VISA
* Configure measurement range, NPLC, Auto Zero, AC bandwidth, current terminal, and DC
  voltage input impedance
* Run immediate, software (optional `--timer-interval-s` scheduling), external-hardware,
  and custom/buffered trigger workflows
* Preview instrument commands in dry-run mode
* Test workflows without hardware using the built-in simulator
* Operate through the CLI or local WebUI
* Access bundled offline CLI and WebUI/Desktop Help/User Guides in English and Traditional
  Chinese
* Switch browser WebUI languages without reloading or resetting runs, forms, samples,
  charts, or UI state; the choice persists
* Produce JSON and JSONL for automation, agents, and orchestrators
* Write timestamped CSV by default; disable it with CLI `--no-csv` or the WebUI
  `CSV output` checkbox

Live sessions detect the model through `*IDN?`; a selected model is only an
expected-model guard, not a capability override. Core enforces fail-closed support by
model, transport, backend, measurement, and trigger mode; see
[Supported Models](docs/core/supported-models.md).

## Project Structure

The single `meters-tool` distribution uses `<version>` from `[project].version` in the
root `pyproject.toml`:

* Distribution: `meters-tool` `<version>`
* Core import: `meters_tool_core`
* CLI import: `meters_tool_cli`
* WebUI import: `meters_tool_webui`

The import paths remain independent. Do not use a `meters_tool.*` namespace package.

```text
src/
  meters_tool_core/
  meters_tool_cli/
  meters_tool_webui/
desktop/
tests/
  core/
  cli/
  help/
  packaging/
  webui/
docs/
  architecture/
  cli/
  contracts/
  core/
  help/
  webui/
scripts/
```

## Install

From the repository root in PowerShell:

```powershell
cd path\to\meters-tool
```

Install uv if needed and verify it:

```powershell
py -m pip install --user uv
```

```powershell
uv --version
```

Create the virtual environment and sync development/test dependencies from `uv.lock`:

```powershell
uv venv .venv
```

```powershell
uv sync --all-extras --link-mode=copy
```

Use the committed lockfile unchanged for CI or strict local checks:

```powershell
uv sync --all-extras --locked --link-mode=copy
```

Python `>=3.10` is supported. `uv venv` selects a compatible version, or specify one:

```powershell
uv venv .venv --python 3.12
```

Windows creates `meters-tool.exe`, `meters-tool-webui.exe`, and
`meters-tool-webui-launcher.exe` under `.venv\Scripts\`. If these wrappers are missing
from an existing synced environment, reinstall only the project package:

```powershell
uv sync --all-extras --link-mode=copy --reinstall-package meters-tool
```

This repair is normally unnecessary for a new environment and needs no separate pip
install.

## Quick Start

Try a safe CLI simulator run without hardware:

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource SIM::34461A `
  --simulate `
  --measurement voltage-dc `
  --trigger-mode immediate `
  --max-samples 1 `
  --csv .tmp_tests\quick-start-simulator.csv `
  --status-format jsonl
```

Start the WebUI console server:

```powershell
.\.venv\Scripts\meters-tool-webui.exe --host 127.0.0.1 --port 8767
```

Or use the WebUI Launcher:

```powershell
.\.venv\Scripts\meters-tool-webui-launcher.exe
```

The Launcher binds only to local loopback, searches up to 100 ports starting at `8767`,
waits for the WebUI capabilities identity, and opens the browser. Use `--port 9000` for a
fixed port or `--port 9000 --auto-port` to search from `9000`.

For Desktop shell development, start Electron from `desktop/`:

```powershell
cd desktop
npm ci
npm start
```

Desktop development reuses the private FastAPI/WebUI host through the repository `.venv`;
Electron adds no separate frontend.

Live sessions default to System VISA via `pyvisa.ResourceManager("@ivi")`. CLI can select PyVISA-py with
`--visa-library "@py"`; WebUI/Desktop offer it under Device options > VISA Backend. There
is no automatic fallback or `PYVISA_LIBRARY` override. `@py` is Product-open only for
34461A TCPIP; System VISA is Product-open for 34461A USB/TCPIP and registered 34460A USB
features. Windows bundles PyVISA-py and the `psutil` /`zeroconf` LAN discovery
dependencies, but no extra USB drivers. See the [CLI README](docs/cli/README.md) and
[WebUI README](docs/webui/README.md) for details.

## Build

Build the single Python distribution's wheel and sdist with the `dev` extra's `build`
package:

```powershell
.\.venv\Scripts\python.exe -m build
```

Output:

```text
dist\meters_tool-<version>-py3-none-any.whl
dist\meters_tool-<version>.tar.gz
```

Windows `dev` dependencies include PyInstaller. Build the shared onedir CLI, WebUI
Launcher, and private Desktop host:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_windows_bundle.ps1
```

Output:

```text
dist\meters-tool\
  meters-tool.exe
  meters-tool-webui-launcher.exe
  meters-tool-webui-host.exe
  _internal\
```

Build the shared Windows onedir and Electron Desktop directory:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_desktop.ps1
```

Output:

```text
dist\desktop\win-unpacked\
  Meters Tool.exe
  meters-tool.exe
  meters-tool-webui-launcher.exe
  meters-tool-webui-host.exe
  _internal\
  resources\
  locales\
  ... Electron runtime files
```

The Desktop's `Meters Tool.exe` uses the adjacent private host and shares one `_internal`
with CLI/Launcher; no system Python or per-launch Electron extraction is needed.

Assemble the wheel, sdist, unified Windows ZIP, and checksums:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_release.ps1
```

Versioned artifacts:

```text
release\<version>\meters-tool-<version>-windows-x64.zip
release\<version>\meters_tool-<version>-py3-none-any.whl
release\<version>\meters_tool-<version>.tar.gz
release\<version>\checksums.txt
```

Extract the Windows ZIP once to run Desktop, CLI, or WebUI Launcher from a single
`meters-tool-<version>` directory with the shared `_internal` and Electron runtime.

Run formal no-hardware Release Acceptance from the repository root on a clean, committed
Git tree:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\release-acceptance.ps1
```

Without `-Release`, the version comes from `pyproject.toml`. On the unchanged commit,
acceptance runs the full no-hardware suite (including wrappers), one release build,
wheel/sdist/Windows ZIP and SHA-256 checks, clean-install, CLI/Launcher smoke, preflight,
and PlanOnly. It prints the passing artifact path but does not publish a release or
automatically perform Electron GUI smoke or live-instrument testing. Its final
`live-cli-check.ps1 -Suite minimal -PlanOnly -SkipPreflight` only generates plans and
never opens VISA. See [Testing Guidelines](docs/testing-guidelines.md) and
[Contributing](docs/CONTRIBUTING.md).

## Test

`scripts/preflight-cli.ps1` runs no-hardware checks; `scripts/live-cli-check.ps1` is for
explicitly operator-approved live validation. Suites include `full` (Finite Custom: 16
cases on 34460A, 20 on 34461A) plus separate `infinite-custom`, `overflow`, and
`worker-streaming` (`--streaming --json`, Active-boundary check). See the
[CLI validation suite matrix](docs/cli/README.md#cli-validation-scripts). `-PlanOnly`
never opens VISA; live runs require an exact resource and interactive confirmation.

Run focused component tests during development:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\core -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\cli -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\webui -q -p no:cacheprovider
```

Run Ruff:

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests
```

Run the daily fast no-hardware suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --ignore=tests\cli\test_cli_wrappers.py
```

Windows CI tests `tests\cli\test_cli_wrappers.py` separately; run full
`release-acceptance.ps1` only before a formal release.

If Windows temporary-directory permissions block pytest, use `.tmp_tests`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --ignore=tests\cli\test_cli_wrappers.py --basetemp .tmp_tests\pytest_tmp
```

## Documentation

* [Changelog](CHANGELOG.md)
* [Core README](docs/core/README.md)
* [Supported Models](docs/core/supported-models.md)
* [CLI User Guide](docs/cli/USER_GUIDE.md)
* [CLI README](docs/cli/README.md)
* [WebUI README](docs/webui/README.md)
* [WebUI / Desktop User Guide](docs/webui/USER_GUIDE.md)
* [Monorepo Architecture](docs/architecture/monorepo-layout.md)
* [Testing Guidelines](docs/testing-guidelines.md)
* [Contributing Guide](docs/CONTRIBUTING.md)
* [Public Contracts](docs/contracts)
* [Meters CLI JSONL Contract](docs/contracts/meters-cli-jsonl-contract.md)
* [Meters Worker Contract](docs/contracts/meters-worker-contract.md)

## Contributing

Contributions are welcome. Before opening a pull request, read the
[Contributing Guide](docs/CONTRIBUTING.md). Changes to instrument support or live
behavior require real-instrument validation evidence when applicable.

## License and Disclaimer

This project is licensed under the MIT License. See [LICENSE](LICENSE).

Application icon: The Meters Tool application icon was generated with OpenAI image
generation in ChatGPT, then reviewed and selected by the project maintainer.

This project is independent and unofficial. It is not affiliated with, endorsed by, or
sponsored by Keysight Technologies.

Users are responsible for complying with all applicable Keysight software, driver,
instrument, and documentation license terms.
