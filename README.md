[繁體中文](README.zh-TW.md)

# Meters Tool

Meters Tool is a Python data acquisition and logging toolkit for supported
digital multimeters. Meters Tool supports the Keysight 34460A and
34461A; see [Supported Models](docs/core/supported-models.md) for the exact
Product support scope. It provides one installable distribution,
`meters-tool`, with the package version defined by the root
`pyproject.toml`, while preserving three import packages:
`meters_tool_core`, `meters_tool_cli`, and `meters_tool_webui`.

The project supports DC and AC current, DC and AC voltage, DC voltage ratio,
frequency, period, and 2-wire or 4-wire resistance measurements over VISA. By
default, each captured sample is written as one CSV row with timestamp,
measurement type, unit, trigger source, and related metadata. CLI callers can
use `--no-csv`; WebUI users can clear the `CSV output` checkbox. Both opt-outs
map to the same Core `csv_enabled` setting.

System VISA requires a separately installed runtime. Meters Tool bundles
PyVISA-py for supported 34461A TCPIP sessions; dry-run and simulation require
no VISA runtime.

## Features

* Control supported digital multimeters over VISA
* Configure measurement range, NPLC, Auto Zero, AC bandwidth, current terminal,
  and DC voltage input impedance
* Support software trigger workflows, including optional timer scheduling via
  `--timer-interval-s`, plus external hardware, immediate, and buffered workflows
* Preview instrument commands using dry-run mode
* Test workflows without hardware using the built-in simulator
* Operate through either the CLI or local WebUI
* Use bundled offline Help/User Guides for CLI and WebUI/Desktop in English and
  Traditional Chinese
* Switch the browser WebUI between English and Traditional Chinese at runtime
  without reloading the page or resetting the active run, form values, live
  samples, chart state, status, or other runtime UI state; the manual choice is
  persisted in the browser
* Produce JSON and JSONL output for automation, agents, and orchestrators
* Produce a timestamped CSV by default, with explicit opt-out through CLI
  `--no-csv` or the WebUI `CSV output` checkbox

Live starts auto-detect the connected model from `*IDN?`; an explicitly selected
model is an expected-model guard and does not unlock capabilities for another
instrument. Exact live support uses a fail-closed policy; see [Supported Models](docs/core/supported-models.md)
and the component documentation for model, transport/backend, measurement, and
trigger-mode status.

## Project Structure

The repository now has one distribution and one version number. In examples,
`<version>` means `[project].version` from the root `pyproject.toml`:

* Distribution: `meters-tool` `<version>`
* Core import: `meters_tool_core`
* CLI import: `meters_tool_cli`
* WebUI import: `meters_tool_webui`

The import paths remain independent. Do not use a `meters_tool.*`
namespace package.

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

Open PowerShell and enter the project root first:

```powershell
cd path\to\meters-tool
```

Install uv if it is not already available:

```powershell
py -m pip install --user uv
```

Verify uv:

```powershell
uv --version
```

Create the project virtual environment in the project folder:

```powershell
uv venv .venv
```

Sync the reproducible development and test environment from `uv.lock`:

```powershell
uv sync --all-extras --link-mode=copy
```

For CI or strict local checks, require the committed lock file to stay unchanged:

```powershell
uv sync --all-extras --locked --link-mode=copy
```

This project supports Python `>=3.10`. `uv venv .venv` uses an available
compatible Python. If you need a specific Python version, request it explicitly:

```powershell
uv venv .venv --python 3.12
```

The `uv.lock` file is used by uv for development and CI reproducibility.

Windows creates virtualenv console wrappers such as
`.\.venv\Scripts\meters-tool.exe`,
`.\.venv\Scripts\meters-tool-webui.exe`, and
`.\.venv\Scripts\meters-tool-webui-launcher.exe`.

If an existing virtual environment is synchronized but one or more console
wrappers are missing, force uv to reinstall only the project package:

```powershell
uv sync --all-extras --link-mode=copy --reinstall-package meters-tool
```

This rebuilds the project package and recreates the console wrappers without
requiring pip. It is normally unnecessary for a newly created virtual
environment.

## Quick Start

After installation, run a safe simulator workflow without hardware:

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

Or start the WebUI launcher:

```powershell
.\.venv\Scripts\meters-tool-webui-launcher.exe
```

The launcher binds only to local loopback. With no arguments it starts at port
`8767`, tries up to 100 ports until one can be bound, waits for the WebUI
capabilities identity, and then opens the browser. Use `--port 9000` for one
fixed port, or `--port 9000 --auto-port` to search from port `9000`.

For Desktop shell development, install the locked Node dependencies and start
Electron from `desktop/`:

```powershell
cd desktop
npm ci
npm start
```

Development mode starts the same private WebUI host through the repository
`.venv`; Electron is only a shell around the existing FastAPI and static WebUI.

See the [CLI README](docs/cli/README.md) and [WebUI README](docs/webui/README.md)
for detailed options and workflows.

By default, live sessions use the system VISA runtime through
`pyvisa.ResourceManager("@ivi")`. CLI VISA-opening commands can select the
bundled PyVISA-py backend with
`--visa-library "@py"`. WebUI and Desktop select it in Device options > VISA
Backend. System VISA remains the default and never falls back to `@py`.
PyVISA-py supports only 34461A TCPIP. The `psutil` and `zeroconf` dependencies
are included for LAN resource discovery; no extra USB drivers are included.

## Build

To build the wheel and source distribution directly into `dist\`, use the
`build` package from the `dev` extra installed above:

```powershell
.\.venv\Scripts\python.exe -m build
```

This produces only one Python distribution:

```text
dist\meters_tool-<version>-py3-none-any.whl
dist\meters_tool-<version>.tar.gz
```

The shared Windows bundle is a PyInstaller onedir workflow. PyInstaller is
included in the Windows `dev` dependency set, so the development environment
created by `uv sync --all-extras --locked --link-mode=copy` is ready for release
builds and formal release acceptance.

Build the CLI, WebUI Launcher, and private Desktop host into one shared bundle:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_windows_bundle.ps1
```

By default, this produces:

```text
dist\meters-tool\
  meters-tool.exe
  meters-tool-webui-launcher.exe
  meters-tool-webui-host.exe
  _internal\
```

The private host is also consumed by the Desktop build. Build the Windows x64
Desktop application directory:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_desktop.ps1
```

This builds the shared Windows onedir, builds Electron in directory mode, and
combines them as:

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

The Desktop application launches the shared private host beside `Meters Tool.exe`
and uses the same `_internal` directory as the CLI and Launcher. It does not
require a system Python installation or unpack a portable Electron executable on
each launch.

`build_release.ps1` assembles the wheel, source distribution, unified Windows
ZIP, and checksums into a versioned release folder:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_release.ps1
```

This produces versioned release artifacts:

```text
release\<version>\meters-tool-<version>-windows-x64.zip
release\<version>\meters_tool-<version>-py3-none-any.whl
release\<version>\meters_tool-<version>.tar.gz
release\<version>\checksums.txt
```

The Windows ZIP contains one `meters-tool-<version>` application directory with
`Meters Tool.exe`, the CLI, the WebUI Launcher, the private Desktop host, one
shared `_internal`, and the Electron runtime. Extract it once, then launch the
Desktop, browser WebUI, or CLI from that directory.

`release-acceptance.ps1` is the formal no-hardware release acceptance for a
clean committed tree. It runs the complete no-hardware test suite, including
wrapper tests, invokes `build_release.ps1` once, and validates the final wheel,
source distribution, unified Windows ZIP, and all three SHA-256 checksums. It
extracts the bundle and runs the existing CLI and Launcher smokes, followed by
clean-install package smokes, selected-target preflight, and the existing
PlanOnly validation. It does not automate an
Electron GUI runtime smoke. A passing run prints the versioned directory that
can be uploaded directly to a GitHub Release.
The final `live-cli-check.ps1` call is `-Suite minimal -PlanOnly -SkipPreflight`;
it only generates plans and does not open a VISA resource. Each recorded command
prints `[start]` and `[passed]` or `[failed]` with its duration, while detailed
child-process stdout/stderr remains in the acceptance run directory. The complete
pytest step may create `.tmp_tests\cli_live\...` through wrapper contract tests;
seeing that directory does not mean that real instrument testing is running. A
long PyInstaller build should not be mistaken for waiting for an external trigger.

## Test

Run focused tests while iterating:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\core -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\cli -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\webui -q -p no:cacheprovider
```

Run the static checks:

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests
```

Run the daily fast no-hardware suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --ignore=tests\cli\test_cli_wrappers.py
```

The Windows wrapper-contract CI job runs `tests\cli\test_cli_wrappers.py`
separately. Run the complete `release-acceptance.ps1` gate only before a formal
release.

If Windows temporary-directory permissions block pytest, rerun it with a
repository-local temporary directory:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --ignore=tests\cli\test_cli_wrappers.py --basetemp .tmp_tests\pytest_tmp
```

## Documentation

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
[Contributing Guide](docs/CONTRIBUTING.md). Changes to instrument support or
live behavior require real-instrument validation evidence when applicable.

## License and Disclaimer

This project is licensed under the MIT License. See [LICENSE](LICENSE).

Application icon: The Meters Tool application icon was generated with OpenAI
image generation in ChatGPT, then reviewed and selected by the project
maintainer.

This project is independent and unofficial. It is not affiliated with,
endorsed by, or sponsored by Keysight Technologies.

Users are responsible for complying with all applicable Keysight software,
driver, instrument, and documentation license terms.
