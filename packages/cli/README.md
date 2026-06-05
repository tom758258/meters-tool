# Keysight Logger

Python tooling for logging measurements from a Keysight 34461A digital
multimeter over VISA.

## Quick Start

From PowerShell:

```powershell
uv venv .venv
uv pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

If `uv` warns that hardlinking failed and it is falling back to copying files,
the install usually still succeeded. On cross-drive or hardlink-restricted
setups, use:

```powershell
uv pip install -e ".[dev]" --link-mode=copy
```

After installation, run the CLI with:

```powershell
.\.venv\Scripts\keysight-logger.exe <command> [options]
```

The generated `.venv\Scripts\keysight-logger.exe` file is an install artifact,
not a tracked project file. If it is missing, rerun the editable install above.
If PowerShell activation is blocked, keep using explicit `.venv\Scripts\...`
commands.

No-hardware validation:

```powershell
uv pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packages\cli\scripts\preflight-cli.ps1 -Target keysight-34461a
.\.venv\Scripts\keysight-logger.exe list-resources --dry-run --json
```

`list-resources --dry-run` does not create a VISA resource manager, list/open
VISA resources, query instruments, or run release/local cleanup.

Build the optional standalone console exe with PyInstaller from an environment
that already has CLI and Core installed. PyInstaller is a local release-build
tool, not a CLI runtime dependency, so install it into the venv before
rebuilding on a fresh machine:

```powershell
uv pip install pyinstaller
```

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --onefile --console --name keysight-logger --paths packages\cli\src --paths packages\core\src packages\cli\src\keysight_logger_cli\cli.py
```

Result:

```text
dist\keysight-logger.exe
```

Smoke checks:

```powershell
.\dist\keysight-logger.exe --version
.\dist\keysight-logger.exe --help
.\dist\keysight-logger.exe list-resources --dry-run --json
```

PyInstaller writes `keysight-logger.spec` as a local build artifact. Do not
commit it unless the project intentionally switches to a checked-in build
recipe.

See the CLI guide for full command usage.

## Documentation

- [CLI Guide - English](docs/README_CLI_EN.md)
- [Changelog](CHANGELOG.md)
- [CLI Integration](docs/cli-integration.md)
- [Common Worker Protocol](../../docs/contracts/common-worker-protocol.md)
- [Common CLI JSON / JSONL Contract](../../docs/contracts/common-cli-jsonl-contract.md)
- [Meters CLI JSON / JSONL Contract](../../docs/contracts/meters-cli-jsonl-contract.md)
- [Common Orchestrator Workflows](../../docs/contracts/common-orchestrator-workflows.md)
- [Meters Orchestrator Workflows](../../docs/contracts/meters-orchestrator-workflows.md)
- [Meters Worker Contract](../../docs/contracts/meters-worker-contract.md)
- [CLI Guide - Traditional Chinese](docs/README_CLI_ZH-TW.md) - planned
- [UI Guide - English](docs/README_UI_EN.md) - planned
- [UI Guide - Traditional Chinese](docs/README_UI_ZH-TW.md) - planned
