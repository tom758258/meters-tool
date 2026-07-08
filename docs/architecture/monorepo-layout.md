# Monorepo Layout

```text
src/
  meters_tool_core/
  meters_tool_cli/
  meters_tool_webui/
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

In examples, `<version>` means `[project].version` from the root
`pyproject.toml`.

| Boundary | Name | Version |
| --- | --- | --- |
| Distribution | `meters-tool` | `<version>` |
| Core import | `meters_tool_core` | distribution version |
| CLI import | `meters_tool_cli` | distribution version |
| WebUI import | `meters_tool_webui` | distribution version |

Console commands:

- `meters-tool`
- `meters-tool-webui`
- `meters-tool-webui-launcher`

## Rationale

The repository keeps Core, CLI, and WebUI as separate Python import packages
and maintenance boundaries, but releases them as one distribution with one
version number. This avoids drift between Core, CLI, and WebUI package metadata
while preserving existing imports and user-facing console commands.

The old `meters_tool` namespace for Core, CLI, and WebUI modules is
intentionally absent.

New code must use the clean package imports:

```python
meters_tool_core
meters_tool_cli
meters_tool_webui
```
