[中文](README.zh-TW.md)

# Keysight Logger

Keysight Logger is a Python data acquisition and logging toolkit for the
Keysight 34461A digital multimeter. It provides one installable distribution,
`keysight-logger` `1.4.0`, while preserving three import packages:
`keysight_logger_core`, `keysight_logger_cli`, and `keysight_logger_webui`.

The project supports DC and AC current, DC and AC voltage, DC voltage ratio,
and 2-wire or 4-wire resistance measurements over VISA. Each captured sample is
written as one CSV row with timestamp, measurement type, unit, trigger source,
and related metadata.

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

The repository now has one distribution and one version number:

* Distribution: `keysight-logger` `1.4.0`
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

Development install with CLI, WebUI, and test/build tools:

```powershell
uv venv .venv
uv pip install -e ".[all,dev]" --link-mode=copy
```

Basic Core/CLI install:

```powershell
pip install .
```

Install WebUI dependencies:

```powershell
pip install ".[webui]"
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
dist\keysight_logger-1.4.0-py3-none-any.whl
dist\keysight_logger-1.4.0.tar.gz
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
release\1.4.0\keysight-logger-1.4.0.exe
release\1.4.0\keysight-logger-webui-launcher-1.4.0.exe
release\1.4.0\keysight_logger-1.4.0-py3-none-any.whl
release\1.4.0\keysight_logger-1.4.0.tar.gz
release\1.4.0\checksums.txt
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
