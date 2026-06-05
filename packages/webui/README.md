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

For double-click use, start the GUI launcher:

```powershell
.\.venv\Scripts\keysight-logger-webui-launcher.exe
```

The launcher defaults to `127.0.0.1:8767`, opens the browser after Start, and
uses Quit to stop the local server.

Open:

```text
http://127.0.0.1:8767/
```

## Build Launcher EXE

The `.venv\Scripts\keysight-logger-webui-launcher.exe` wrapper is created by
the editable Python install above. To build the optional standalone
`dist\keysight-logger-webui-launcher.exe`, install PyInstaller into the local
venv first:

```powershell
uv pip install pyinstaller
```

Then run the release-build command from the repository root:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --onefile --windowed --name keysight-logger-webui-launcher --paths packages/webui/src --paths packages/core/src --add-data "packages/webui/src/keysight_logger_webui/static;keysight_logger_webui/static" packages/webui/src/keysight_logger_webui/launcher.py
```

PyInstaller is a local release-build tool, not a WebUI runtime dependency, so
new environments do not install it through `packages/webui[dev]`.

## Validation

Focused no-hardware validation:

```powershell
.\.venv\Scripts\python.exe -m pytest packages/webui/tests/test_webui_package_metadata.py packages/webui/tests/test_web_ui.py packages/webui/tests/test_launcher.py -q -p no:cacheprovider
```

Then run the broader suite when practical:

```powershell
uv run pytest tests -q -p no:cacheprovider
```

This WebUI adapter update does not intentionally change SCPI commands, VISA
timeout behavior, trigger wait strategy, stop flow, cleanup order, measurement
behavior, or Core public API exports.

## Documentation

- [User Guide](docs/USER_GUIDE.md)
- [Detailed WebUI README](docs/Webui-README.md)
- [Web UI Change Rules](docs/web-ui-ai-change-rules.md)
- [Changelog](CHANGELOG.md)
