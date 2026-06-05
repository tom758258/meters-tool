# Changelog

Package-specific release notes live with each package:

- Core: `packages/core/CHANGELOG.md`
- CLI: `packages/cli/CHANGELOG.md`
- WebUI: `packages/webui/CHANGELOG.md`

## Workspace

### Monorepo migration

- Split Core, CLI, and WebUI into `packages/core`, `packages/cli`, and `packages/webui`.
- Renamed Python imports to `keysight_logger_core`, `keysight_logger_cli`, and `keysight_logger_webui`.
- Preserved the CLI command `keysight-logger` and WebUI command `keysight-logger-webui`.
- Kept runtime behavior contracts unchanged; this migration only changes structure, packaging, imports, docs, tests, and CI layout.
