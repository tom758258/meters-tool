# Changelog

## Unreleased

- Added root `keysight-logger --version`, parser/help coverage, and dry-run
  contract assertions for no-hardware CLI workflows.
- Added preflight `-ListTargets`, constrained `-OutputRoot`, and summary count
  reporting.
- Updated active docs to prefer the installed console script and document
  no-hardware validation plus local install troubleshooting.

## v1.1.6-cli

- Released the current patch baseline for control-plane and discovery behavior.
- Documented JSONL `ready` events for non-dry-run workers and preserved
  summary-based wrapper completion checks.
- Added preflight coverage for `list-resources --dry-run --live-only --json`
  and its no-VISA-I/O discovery contract.
- Kept SCPI command sequences, VISA timeout behavior, trigger wait strategy,
  acquisition/read paths, stop flow, cleanup order, and measurement logic
  unchanged.

## v1.1.5-cli

- Kept acquisition behavior unchanged while making successful
  `list-resources --verify` / `--live-only` checks run best-effort
  release-to-local before closing the verification session.
