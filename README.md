[繁體中文](README.zh-TW.md)

# Keysight Logger

Keysight Logger is a Python data acquisition and logging toolkit for the
Keysight 34461A digital multimeter. It provides one installable distribution,
`keysight-logger`, with the package version defined by the root
`pyproject.toml`, while preserving three import packages:
`keysight_logger_core`, `keysight_logger_cli`, and `keysight_logger_webui`.

The project supports DC and AC current, DC and AC voltage, DC voltage ratio,
frequency, period, and 2-wire or 4-wire resistance measurements over VISA. Each
captured sample is written as one CSV row with timestamp, measurement type,
unit, trigger source, and related metadata.

## Features

* Control a Keysight 34461A over USB or LAN using VISA
* Configure measurement range, NPLC, Auto Zero, AC bandwidth, current terminal,
  and DC voltage input impedance
* Support software, timer, external hardware, immediate, and buffered trigger workflows
* Preview instrument commands using dry-run mode
* Test workflows without hardware using the built-in simulator
* Operate through either the CLI or local WebUI
* Produce JSON and JSONL output for automation, agents, and orchestrators

## Project Structure

The repository now has one distribution and one version number. In examples,
`<version>` means `[project].version` from the root `pyproject.toml`:

* Distribution: `keysight-logger` `<version>`
* Core import: `keysight_logger_core`
* CLI import: `keysight_logger_cli`
* WebUI import: `keysight_logger_webui`

The import paths remain independent. Do not use a `keysight_logger.*`
namespace package.

```text
src/
  keysight_logger_core/
  keysight_logger_cli/
  keysight_logger_webui/
tests/
  core/
  cli/
  webui/
docs/
  core/
  cli/
  webui/
scripts/
```

## Install

Open PowerShell and enter the project root first:

```powershell
cd path\to\Keysight_Meters_Logger
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
`pip install .` reads `pyproject.toml`, not `uv.lock`. Users without uv must
install uv before using the locked environment.

If you need pip directly, use the virtual environment's Python:

```powershell
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\python.exe -m pip install ".[webui]"
.\.venv\Scripts\python.exe -m pip install -e ".[all,dev]"
```

Windows creates virtualenv console wrappers such as
`.\.venv\Scripts\keysight-logger.exe`,
`.\.venv\Scripts\keysight-logger-webui.exe`, and
`.\.venv\Scripts\keysight-logger-webui-launcher.exe`.

## Build

Build the wheel and source distribution. This uses the `build` package from
the `dev` extra installed above:

```powershell
.\.venv\Scripts\python.exe -m build
```

This produces only one Python distribution:

```text
dist\keysight_logger-<version>-py3-none-any.whl
dist\keysight_logger-<version>.tar.gz
```

Standalone executables are separate PyInstaller workflows. Install PyInstaller
before building exe artifacts:

```powershell
uv pip install pyinstaller --python .\.venv\Scripts\python.exe
```

If your virtual environment uses pip directly:

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
```

Build the standalone CLI and WebUI launcher executables:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_cli_exe.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_webui_exe.ps1
```

By default, these commands produce:

```text
dist\keysight-logger.exe
dist\keysight-logger-webui-launcher.exe
```

Build a release folder with wheel, sdist, standalone executables, and checksums:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_release.ps1
```

This produces versioned release artifacts:

```text
release\<version>\keysight-logger-<version>.exe
release\<version>\keysight-logger-webui-launcher-<version>.exe
release\<version>\keysight_logger-<version>-py3-none-any.whl
release\<version>\keysight_logger-<version>.tar.gz
release\<version>\checksums.txt
```

## Test

Run focused tests while iterating:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\core -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\cli -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\webui -q -p no:cacheprovider
```

Run the full no-hardware suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

If Windows temporary-directory permissions block pytest, rerun it with a
repository-local temporary directory:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --basetemp .tmp_tests\pytest_tmp
```

## Documentation

* [Core README](docs/core/README.md)
* [CLI User Guide](docs/cli/USER_GUIDE.md)
* [CLI README](docs/cli/README.md)
* [WebUI README](docs/webui/README.md)
* [WebUI User Guide](docs/webui/USER_GUIDE.md)
* [Monorepo Architecture](docs/architecture/monorepo-layout.md)
* [Testing Guidelines](docs/testing-guidelines.md)
* [Public Contracts](docs/contracts)
* [Meters CLI JSONL Contract](docs/contracts/meters-cli-jsonl-contract.md)
* [Meters Worker Contract](docs/contracts/meters-worker-contract.md)

## License and Disclaimer

This project is licensed under the MIT License. See [LICENSE](LICENSE).

This project is independent and unofficial. It is not affiliated with,
endorsed by, or sponsored by Keysight Technologies.

Users are responsible for complying with all applicable Keysight software,
driver, instrument, and documentation license terms.
