# Monorepo Layout

```text
src/
  meters_tool_core/
  meters_tool_cli/
  meters_tool_webui/
desktop/
tests/
  core/
  cli/
  help/
  packaging/
  webui/
docs/
  architecture/
  cli/
  contracts/
  core/
  help/
  webui/
scripts/
```

`desktop/` is the Node/Electron packaging shell for the local Desktop
application. It is not a fourth Python import package and is not part of the
root Python distribution metadata. It launches the private WebUI Desktop host,
reuses the existing FastAPI/static WebUI, and does not own or duplicate Core,
instrument, acquisition, or cleanup behavior.

## Dependency and Ownership

CLI and WebUI depend on Core; Core must not import CLI or WebUI. CLI and WebUI
are peer adapters and do not depend on each other. The thin Node/Electron
Desktop shell reuses WebUI and does not become a fourth Python package or own
Core behavior.

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
