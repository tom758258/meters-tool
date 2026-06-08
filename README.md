[中文版](README.zh-TW.md)

# Keysight Logger

Keysight Logger is a Python-based data acquisition and logging application for the Keysight 34461A digital multimeter.

It supports DC and AC current, DC and AC voltage, DC voltage ratio, and 2-wire or 4-wire resistance measurements over VISA. Each captured sample is written as one row in a CSV file, together with its timestamp, measurement type, unit, trigger source, and related metadata.

The project provides both a command-line interface and a local WebUI, and supports software, timer, external hardware, immediate, and buffered custom trigger modes.

## Features

* Control a Keysight 34461A over USB or LAN using VISA
* Measure:

  * DC current
  * AC current
  * DC voltage
  * AC voltage
  * DC voltage ratio
  * 2-wire resistance
  * 4-wire resistance
* Record one CSV row for every captured sample
* Configure measurement range, NPLC, Auto Zero, AC bandwidth, current terminal, and DC voltage input impedance
* Support software, timer, external hardware, immediate, and buffered trigger workflows
* Preview instrument commands using dry-run mode
* Test workflows without hardware using the built-in simulator
* Operate through either the CLI or local WebUI
* Produce JSON and JSONL output for automation, agents, and orchestrators

## Interfaces

Keysight Logger provides two user-facing interfaces:

### Command-line interface

The CLI is intended for scripting, repeatable tests, automated acquisition, and integration with agents or orchestration tools.

```powershell
keysight-logger start-trigger-record `
  --resource "SIM::34461A" `
  --measurement voltage-dc `
  --trigger-mode immediate `
  --max-samples 10 `
  --csv data/voltage.csv
```

### WebUI

The WebUI provides a local browser-based interface for configuring measurements, starting and stopping acquisition, sending software triggers, viewing live samples, and opening completed CSV files.

The WebUI runs locally and communicates with the same shared acquisition core used by the CLI.

## Project Structure

This repository is organized as a monorepo containing three separately installable packages:

* `packages/core`: `keysight-logger-core` `1.2.1`, imported as `keysight_logger_core` — instrument communication, measurement configuration, triggering, acquisition, validation, simulation, and CSV storage
* `packages/cli`: `keysight-logger-cli` `1.3.2`, imported as `keysight_logger_cli` — command-line interface and machine-readable JSON/JSONL integration
* `packages/webui`: `keysight-logger-webui` `1.2.2`, imported as `keysight_logger_webui` — local WebUI, HTTP API, live status, and acquisition controls

The root `pyproject.toml` is used only for workspace tooling. Package metadata is maintained inside each package directory.

## Install

```powershell
uv venv .venv
uv pip install -e "packages/core[dev]" -e "packages/cli[dev]" -e "packages/webui[dev]" --link-mode=copy
```

After installation, Windows creates virtualenv console wrappers such as
`.\.venv\Scripts\keysight-logger.exe`,
`.\.venv\Scripts\keysight-logger-webui.exe`, and
`.\.venv\Scripts\keysight-logger-webui-launcher.exe`. These wrappers require
the project virtual environment. Use the PyInstaller steps below when you need
a standalone executable under `dist\`.

## Build EXE

Install PyInstaller into the same virtual environment that already has Core,
CLI, and WebUI installed:

```powershell
uv pip install pyinstaller
```

Build the standalone CLI executable:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --onefile --console --name keysight-logger --paths packages\cli\src --paths packages\core\src packages\cli\src\keysight_logger_cli\cli.py
```

Result:

```text
dist\keysight-logger.exe
```

Build the standalone WebUI launcher executable:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --onefile --windowed --name keysight-logger-webui-launcher --paths packages\webui\src --paths packages\core\src --add-data "packages\webui\src\keysight_logger_webui\static;keysight_logger_webui\static" packages\webui\src\keysight_logger_webui\launcher.py
```

Result:

```text
dist\keysight-logger-webui-launcher.exe
```

Run no-hardware smoke checks after rebuilding:

```powershell
.\dist\keysight-logger.exe --version
.\dist\keysight-logger.exe --help
.\dist\keysight-logger.exe list-resources --dry-run --json
```

PyInstaller writes `.spec`, `build\`, and `dist\` artifacts locally. Do not
commit the generated `.spec` file unless the project intentionally switches to a
checked-in PyInstaller build recipe.

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest packages/core/tests -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest packages/cli/tests -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest packages/webui/tests -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest packages tests -q -p no:cacheprovider
```

If Windows temporary-directory permissions block pytest, rerun it with a repository-local temporary directory:

```powershell
.\.venv\Scripts\python.exe -m pytest packages tests -q -p no:cacheprovider --basetemp .tmp_tests\pytest_tmp
```

## Documentation

### User and integration documentation

* [Core README](packages/core/README.md)
* [CLI README](packages/cli/README.md)
* [CLI Guide](packages/cli/docs/README_CLI_EN.md)
* [WebUI README](packages/webui/README.md)
* [WebUI Guide](packages/webui/docs/Webui-README.md)
* [WebUI User Guide](packages/webui/docs/USER_GUIDE.md)

### Architecture and automation

* [Monorepo Architecture](docs/architecture/monorepo-layout.md)
* [Public Contracts](docs/contracts)
* [Meters CLI JSONL Contract](docs/contracts/meters-cli-jsonl-contract.md)
* [Meters Worker Contract](docs/contracts/meters-worker-contract.md)

## License and Disclaimer

This project is licensed under the MIT License. See [LICENSE](LICENSE).

This project is an independent, unofficial project and is not affiliated with, endorsed by, or sponsored by Keysight Technologies.

Users are responsible for complying with all applicable Keysight software, driver, instrument, and documentation license terms.
