# Monorepo Layout

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
  contracts/
scripts/
```

## Package Names

| Boundary | Name | Version |
| --- | --- | --- |
| Distribution | `keysight-logger` | `1.4.0` |
| Core import | `keysight_logger_core` | `1.4.0` distribution version |
| CLI import | `keysight_logger_cli` | `1.4.0` distribution version |
| WebUI import | `keysight_logger_webui` | `1.4.0` distribution version |

Console commands:

- `keysight-logger`
- `keysight-logger-webui`
- `keysight-logger-webui-launcher`

## Rationale

The repository keeps Core, CLI, and WebUI as separate Python import packages
and maintenance boundaries, but releases them as one distribution with one
version number. This avoids drift between Core, CLI, and WebUI package metadata
while preserving existing imports and user-facing console commands.

The old `keysight_logger` namespace for Core, CLI, and WebUI modules is
intentionally absent.

New code must use the clean package imports:

```python
keysight_logger_core
keysight_logger_cli
keysight_logger_webui
```
