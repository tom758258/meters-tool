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

See the CLI guide for full command usage.

## Documentation

- [CLI Guide - English](docs/README_CLI_EN.md)
- [Changelog](CHANGELOG.md)
- [Project Plan](docs/project-plan.md)
- [Core Integration](docs/integration.md)
- [CLI Integration](docs/cli-integration.md)
- [WebUI Integration](docs/webui-integration.md)
- [Common Worker Protocol](docs/common-worker-protocol.md)
- [CLI JSON / JSONL Contract](docs/cli-jsonl-contract.md)
- [CLI Orchestrator Workflows](docs/cli-orchestrator-workflows.md)
- [Worker Contract](docs/worker-contract.md)
- [Hardware Test Plan](docs/hardware-test-plan.md)
- [Current Handoff](docs/session-handoff.md)
- [Validation History](docs/validation-history.md)
- [Supported Models](docs/supported-models.md)
- [CLI Guide - Traditional Chinese](docs/README_CLI_ZH-TW.md) - planned
- [UI Guide - English](docs/README_UI_EN.md) - planned
- [UI Guide - Traditional Chinese](docs/README_UI_ZH-TW.md) - planned
