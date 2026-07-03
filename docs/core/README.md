# Keysight Logger Core

Core contains the public API and acquisition runtime contract used by the CLI
and WebUI components for supported Keysight Truevolt DMM integrations.

Core owns the shared request model, validation, dry-run planning, runtime
session orchestration, event/result types, control-plane interfaces, profile
metadata, and safety rules for the Keysight 34460A/34461A acquisition runtime. It is
shipped inside the single `keysight-logger` distribution while preserving the
`keysight_logger_core` import boundary.

The CLI and WebUI components own their command-line, web, wrapper, and
serialization layers. Core must not import `keysight_logger_cli` or
`keysight_logger_webui`.

## Validation

No-hardware Core validation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/core -q -p no:cacheprovider
```

Core validation should not require CLI or WebUI imports except through tests
that explicitly check the component boundary.

## Documentation

- [Core Integration](integration.md)
- [Supported Models](supported-models.md)
- [Changelog](CHANGELOG.md)
