# Monorepo Layout

```text
packages/
  core/
    src/keysight_logger_core/
    tests/
    docs/
  cli/
    src/keysight_logger_cli/
    tests/
    docs/
    scripts/
  webui/
    src/keysight_logger_webui/
    tests/
    docs/
```

## Package Names

| Package | Distribution | Import | Version | Console command |
| --- | --- | --- | --- | --- |
| Core | `keysight-logger-core` | `keysight_logger_core` | `1.2.1` | None |
| CLI | `keysight-logger-cli` | `keysight_logger_cli` | `1.3.2` | `keysight-logger` |
| WebUI | `keysight-logger-webui` | `keysight_logger_webui` | `1.2.2` | `keysight-logger-webui`, `keysight-logger-webui-launcher` |

## Rationale

The monorepo keeps the three stable product lines together while preserving their independent package metadata, tests, docs, and changelogs. Tracked public docs should stay durable and avoid personal paths, real instrument identifiers, and transient project status.

The old `keysight_logger` namespace for Core, CLI, and WebUI modules is intentionally removed.

New code must use the clean package imports:

```python
keysight_logger_core
keysight_logger_cli
keysight_logger_webui
```
