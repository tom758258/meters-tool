# Keysight Logger Monorepo

This workspace contains three separately installable packages:

- `packages/core`: `keysight-logger-core` `1.2.1`, imported as `keysight_logger_core`
- `packages/cli`: `keysight-logger-cli` `1.3.2`, imported as `keysight_logger_cli`, console command `keysight-logger`
- `packages/webui`: `keysight-logger-webui` `1.2.2`, imported as `keysight_logger_webui`, console command `keysight-logger-webui`

The root `pyproject.toml` is workspace tooling only. Package metadata lives in each package directory.

## Install

```powershell
uv venv .venv
uv pip install -e "packages/core[dev]" -e "packages/cli[dev]" -e "packages/webui[dev]" --link-mode=copy
```

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest packages/core/tests -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest packages/cli/tests -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest packages/webui/tests -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest packages tests -q -p no:cacheprovider
```

If Windows temp permissions block pytest, rerun with a repo-local temp root such as `--basetemp .tmp_tests\pytest_tmp`.

## Docs

- Core: [README](packages/core/README.md), [integration](packages/core/docs/integration.md), [supported models](packages/core/docs/supported-models.md)
- CLI: [README](packages/cli/README.md), [CLI guide](packages/cli/docs/README_CLI_EN.md), [integration](packages/cli/docs/cli-integration.md), [Meters JSONL contract](docs/contracts/meters-cli-jsonl-contract.md), [Meters worker contract](docs/contracts/meters-worker-contract.md)
- WebUI: [README](packages/webui/README.md), [WebUI guide](packages/webui/docs/Webui-README.md), [user guide](packages/webui/docs/USER_GUIDE.md), [change rules](packages/webui/docs/web-ui-ai-change-rules.md)
- Workspace: [architecture](docs/architecture/monorepo-layout.md), [public contracts](docs/contracts)
