# Changelog

## v1.1.6-cli - Unreleased

- Prepared the next patch baseline for current control-plane and discovery
  behavior without creating a Git tag.
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
