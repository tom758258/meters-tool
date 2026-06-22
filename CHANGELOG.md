# Changelog

Component release notes:

- Core: `docs/core/CHANGELOG.md`
- CLI: `docs/cli/CHANGELOG.md`
- WebUI: `docs/webui/CHANGELOG.md`

## v1.4.0

### Single distribution packaging

- Unified Core, CLI, and WebUI under one distribution, `keysight-logger` `1.4.0`.
- Moved import packages to root `src/`, tests to root `tests/`, component docs to root `docs/`, and release scripts to root `scripts/`.
- Preserved Python imports: `keysight_logger_core`, `keysight_logger_cli`, and `keysight_logger_webui`.
- Preserved console commands: `keysight-logger`, `keysight-logger-webui`, and `keysight-logger-webui-launcher`.
- Kept runtime behavior contracts unchanged; this migration changes distribution metadata, dependency declarations, build flow, docs, tests, and CI layout only.
- Finalized the CLI and WebUI operator guide split: `USER_GUIDE.md` files cover operator workflows, while README files retain engineering setup, reference, validation, and maintainer details.
