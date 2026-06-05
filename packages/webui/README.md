# Keysight Logger Web UI

This branch packages the local Web UI adapter for Keysight 34461A acquisition.
The Web UI is built on the shared Core runtime in `keysight_logger_core`; it
owns the browser interface, FastAPI endpoints, static assets, and WebUI-specific
serialization.

Core owns request validation, dry-run planning, acquisition runtime, trigger
routing, stop behavior, cleanup order, measurement/profile metadata, simulator,
and instrument safety rules. The Web UI must use that Core contract instead of
depending on the CLI adapter.

## Run

Install or refresh the editable WebUI package:

```powershell
uv pip install -e ".[dev]" --link-mode=copy
```

After install, Windows creates the WebUI console wrapper:

```powershell
.\.venv\Scripts\keysight-logger-webui.exe --version
.\.venv\Scripts\keysight-logger-webui.exe --port 8767
```

Open:

```text
http://127.0.0.1:8767/
```

## Validation

Focused no-hardware validation:

```powershell
uv run pytest tests/test_web_ui.py tests/test_core_public_api.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py packages/webui/tests/test_webui_package_metadata.py packages/webui/tests/test_webui_docs_ownership.py -q -p no:cacheprovider
```

Then run the broader suite when practical:

```powershell
uv run pytest tests -q -p no:cacheprovider
```

This WebUI adapter update does not intentionally change SCPI commands, VISA
timeout behavior, trigger wait strategy, stop flow, cleanup order, measurement
behavior, or Core public API exports.

## Documentation

- [Core Integration](docs/integration.md)
- [Detailed WebUI README](docs/Webui-README.md)
- [Web UI Change Rules](docs/web-ui-ai-change-rules.md)
- [Web UI Session Handoff](docs/session-handoff.md)
- [Hardware Test Plan](docs/hardware-test-plan.md)
- [Branch Handoff Index](docs/session-handoff.md)
- [Validation History](docs/validation-history.md)
- [Supported Models](docs/supported-models.md)
- [Project Plan](docs/project-plan.md)
- [Changelog](CHANGELOG.md)
