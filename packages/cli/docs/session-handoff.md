# CLI Branch Handoff

Updated: 2026-06-02

This file tracks current CLI package status, latest validation, active risks,
and next work. Keep branch-neutral handoff routing in `docs/session-handoff.md`.
Durable direction stays in `docs/project-plan.md`; shared Core adapter
contracts stay in `docs/integration.md`; CLI adapter maintenance stays in
`docs/cli-integration.md`; hardware validation workflow stays in
`docs/hardware-test-plan.md`; historical validation details stay in
`docs/validation-history.md`.

## Current Status

- Branch: `main`.
- Current CLI release target: `cli-v1.3.1`.
- The CLI package keeps `keysight-logger` package metadata, the
  `keysight-logger` console script, CLI runtime, wrapper scripts, CLI
  JSON/JSONL contracts, and tests.
- The former Core, CLI, and WebUI product branches have been unified into
  `main`; package boundaries now live under `packages/*`.
- Core v1.1.0 runtime changes are available to the CLI package while preserving
  CLI package identity.
- CLI now exposes the Core v1.1.0 measurement options through parser fields:
  `--auto-zero once`, `--ac-bandwidth-hz`, `--current-terminal`, and
  `--measurement voltage-dc-ratio`.
- CLI/agent documentation now reflects those Core v1.1.0 fields, DCV Ratio
  `measurement_metadata`, exit code meanings, and the worker orchestrator flow:
  dry-run, simulate, live worker, wait for `ready`, `GET /status`, trigger/stop,
  then read JSONL/CSV/report artifacts.
- `StartRequest` remains the shared start request model. CLI converts
  `argparse.Namespace` before Core validation, dry-run planning, or runtime
  orchestration.
- `StartPlan` remains the shared dry-run plan model. CLI output may preserve
  adapter-only fields such as `measurement_cli_name`; those fields are not Core
  schema.
- `StartRunEvent` and `StartRunResult` are the typed runtime boundary. CLI maps
  them to text, JSONL, and exit codes.
- `--enable-hw-trigger` remains removed from the CLI parser. Use
  `--trigger-mode external`.
- CLI client contract v1.3 adds `soft-status`, `wait-ready`, and
  `--timeout-ms` for `soft-trigger`, `soft-stop`, and `soft-status`.
- CLI client contract v1.5 keeps `schema_version: 1` and adds additive
  diagnostic fields to soft-client JSON success/error objects plus
  orchestrator workflow docs.
- Legacy root-level Core module imports such as `keysight_logger.measurement`
  and `keysight_logger.instrument` are no longer supported. Use
  `keysight_logger_core`, `keysight_logger_core.*`, `keysight_logger_cli.cli`, or
  the `keysight-logger` console script.
- CLI `--version` uses installed distribution metadata first, then local
  `pyproject.toml`, then an internal fallback version for PyInstaller onefile
  executables where neither metadata source is available.
- Optional standalone console exe build instructions are documented in
  `README.md` and `docs/README_CLI_EN.md`.

## Latest Validation

Latest standalone CLI exe validation on 2026-06-02:

```powershell
.\.venv\Scripts\python.exe -m pytest packages\cli\tests\test_cli_package_metadata.py packages\cli\tests\test_cli_args.py -q -p no:cacheprovider --basetemp .tmp_tests\pytest_tmp_cli_version
# 118 passed, 12 subtests passed
```

```powershell
.\.venv\Scripts\python.exe -m pytest packages tests -q -p no:cacheprovider --basetemp .tmp_tests\pytest_tmp_full
# 410 passed, 1 warning, 149 subtests passed
```

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --onefile --console --name keysight-logger --paths packages\cli\src --paths packages\core\src packages\cli\src\keysight_logger_cli\cli.py
.\dist\keysight-logger.exe --version
.\dist\keysight-logger.exe --help
.\dist\keysight-logger.exe list-resources --dry-run --json
.\dist\keysight-logger.exe start-trigger-record --resource SIM::34461A --simulate --measurement voltage-dc --trigger-mode immediate --max-samples 1 --csv .tmp_tests\cli_exe_smoke.csv --status-format jsonl
```

Result: PyInstaller 6.20.0 built `dist\keysight-logger.exe`; `--version`
printed `keysight-logger 1.3.1`; help, dry-run list-resources, and simulated
one-sample acquisition smoke checks passed.

Latest local release validation for `cli-v1.3.1` covers the monorepo package
layout, CLI package metadata update to `1.3.1`, Core dependency alignment to
`keysight-logger-core>=1.2.0,<1.3`, CLI contract `v1.5`, and
wrapper reports. Full live Keysight 34461A validation passed immediately before
the metadata/dependency-only `1.3.1` bump; no SCPI, VISA timeout, trigger wait strategy,
cleanup order, CSV schema, or existing JSON field meanings changed after that
live pass.

```powershell
.\.venv\Scripts\python.exe -m pytest packages tests -q -p no:cacheprovider --basetemp .tmp_tests\pytest_tmp
# 389 passed, 1 warning, 145 subtests passed
```

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packages\cli\scripts\release-cli-check.ps1 -Target keysight-34461a
# release check passed: cli-v1.3.1
# summary: .tmp_tests\cli_release\keysight-34461a\20260601-131316\summary.md
```

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packages\cli\scripts\live-cli-check.ps1 -Target keysight-34461a -Connection usb -Resource "SIM::34461A" -Suite full -PlanOnly
# status: planned; live_executed: false; 12 dry-run cases generated
```

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packages\cli\scripts\live-cli-check.ps1 -Target keysight-34461a -Connection usb -Resource "USB0::0x2A8D::0x1301::MY60045220::0::INSTR" -Suite minimal
# passed; captured=1; errors=0; csv_rows=1
```

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packages\cli\scripts\live-cli-check.ps1 -Target keysight-34461a -Connection usb -Resource "USB0::0x2A8D::0x1301::MY60045220::0::INSTR" -Suite full
# passed; 12 live cases; captured=1, errors=0, csv_rows=1 for every case
```

The package is ready to commit and tag `cli-v1.3.1`.

Live hardware validation reported by the operator on 2026-05-29 with
`USB0::0x2A8D::0x1301::MY60045220::0::INSTR`:

- `voltage-ac`, immediate, `--ac-bandwidth-hz 20`, `max_samples=1` passed
  twice with `captured=1`, `errors=0`, `trigger_source="immediate"`, and
  normal release/local cleanup.
- `voltage-dc`, immediate, `--auto-zero once`, `max_samples=1` passed with
  `captured=1`, `errors=0`, and normal release/local cleanup.
- `voltage-dc-ratio`, immediate, `max_samples=1` passed with `captured=1`,
  `errors=0`, unit `ratio`, and `measurement_metadata` containing
  `signal_voltage_v`, `reference_voltage_v`, and
  `secondary_source="SENS:DATA"`.
- `current-dc`, immediate, `--auto-zero once --current-terminal 10`,
  `max_samples=1` passed with `captured=1`, `errors=0`, and normal cleanup.
- `current-dc`, immediate,
  `--auto-zero once --current-terminal 10 --range 10`, `max_samples=1` passed
  with `captured=1`, `errors=0`, and normal cleanup.

Live minimal validation on 2026-06-01 after monorepo migration with
`USB0::0x2A8D::0x1301::MY60045220::0::INSTR`:

- `live-cli-check.ps1 -Suite minimal` passed with status `passed`, package
  version `1.2.1`, and git HEAD
  `67613bde9e0f77e98e2933a1478abaaa4e08c8c4`.
- `current-dc`, immediate, `max_samples=1` used `READ?` and passed with
  `captured=1`, `errors=0`, `csv_rows=1`, and normal cleanup.
- Artifacts:
  `.tmp_tests/cli_live/keysight-34461a/usb/minimal/20260601-095632/summary.md`
  and `report.json`.

Additional monorepo validation on 2026-06-01:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packages\cli\scripts\live-cli-check.ps1 -Target keysight-34461a -Connection usb -Resource "SIM::34461A" -Suite full -PlanOnly
# status: planned; live_executed: false; 12 dry-run cases generated
```

Artifacts:
`.tmp_tests/cli_live/keysight-34461a/usb/full/20260601-102005/summary.md`
and `report.json`.

```powershell
.\.venv\Scripts\python.exe -m pytest packages tests -q -p no:cacheprovider --basetemp .tmp_tests\pytest_tmp
# 389 passed, 1 warning, 145 subtests passed
```

Full live validation on 2026-06-01 after monorepo migration with
`USB0::0x2A8D::0x1301::MY60045220::0::INSTR`:

- `live-cli-check.ps1 -Suite minimal` passed again:
  `.tmp_tests/cli_live/keysight-34461a/usb/minimal/20260601-115201/summary.md`.
- `live-cli-check.ps1 -Suite full` passed with status `passed`, package
  version `1.2.1`, git HEAD
  `67613bde9e0f77e98e2933a1478abaaa4e08c8c4`, and 12 live cases executed.
- All full-suite cases passed with `captured=1`, `errors=0`, and
  `csv_rows=1`: immediate current/voltage DC, immediate current/voltage AC,
  2-wire and 4-wire resistance, software trigger, software timer, immediate
  custom, software custom, external simple, and external custom.
- External simple used `FETC?`; external custom used
  `DATA:POINts? / DATA:REMove?`.
- Artifacts:
  `.tmp_tests/cli_live/keysight-34461a/usb/full/20260601-115305/summary.md`
  and `report.json`.

## Active Risks

- Core v1.1.0 adds SCPI only when the corresponding request fields are used:
  Auto Zero Once, AC bandwidth, current terminal, DCV input impedance, or
  `measurement="voltage-dc-ratio"`. Defaults should preserve existing command
  sequences.
- DCV Ratio live validation requires operator-confirmed Input and Sense wiring.
- LAN `external` or `full` validation remains optional and should run only if
  the operator wants to re-check external-trigger behavior over TCPIP.
- `core.run_plan` still imports `HardwareTriggerAdapter` for dry-run external
  trigger preview generation. A future small refactor can extract a pure SCPI
  preview helper if this coupling becomes a maintenance issue.
- WebUI integrations must call Core directly and must not scrape CLI JSON or
  JSONL as the backend API.

## Next Work

1. Review and commit the `cli-v1.3.1` release prep on `main`, then tag
   `cli-v1.3.1`.
2. Run `scripts/live-cli-check.ps1` only when the user explicitly provides the
   target connection/resource and chooses a live suite. For a fresh hardware
   pass, start with `-Suite minimal`.
## 2026-05-29 Contract v1.2 Update

- CLI JSONL runtime contract revision is `v1.2`.
- JSONL `summary` events include backward-compatible `ok`: `true` when no
  `fatal_error` is present, `false` when fatal.
- Added provisional lifecycle-only `docs/common-worker-protocol.md`.
- Clarified `docs/worker-contract.md` as the Meters-specific worker contract
  that follows the common lifecycle.
- Validation pending in this environment: shell startup is currently blocked by
  the Windows sandbox, and further escalated commands were rejected by the
  execution reviewer usage limit.

## 2026-05-31 Contract v1.3 Update

- CLI JSON/JSONL runtime contract revision is `v1.3`; `schema_version` remains
  `1`.
- Added `soft-status` as a CLI wrapper around non-mutating `GET /status`.
- Added `wait-ready` polling for orchestrators; success means any valid `200`
  JSON status response was reachable before the deadline.
- Added validated client `--timeout-ms` to `soft-trigger`, `soft-stop`, and
  `soft-status`; range is `100` to `600000` ms.
- No live hardware validation is required for this contract update because it
  does not alter SCPI, VISA timeout behavior, trigger wait strategy,
  stop/cleanup order, or measurement logic.

## 2026-05-31 Contract v1.4 Update

- CLI JSON/JSONL runtime contract revision is `v1.4`; `schema_version` remains
  `1`.
- Added `docs/cli-orchestrator-workflows.md` with a Python subprocess workflow
  using `ready`, `wait-ready`, `soft-status`, `soft-trigger`, `summary`, and
  `soft-stop` cleanup.
- Soft-client JSON errors now add `client_command`, `ok`, `port`,
  `request_sent`, `error_phase`, `reachable`, and optional `http_status`
  without changing existing `event: "error"` failures for `soft-trigger` and
  `soft-stop`.
- Preflight/live wrappers now use `wait-ready` and `soft-status` before
  software-trigger client calls and verify `run_id` correlation.
- No live hardware validation is required for this batch because it changes
  CLI clients, wrappers, docs, and simulator-only tests.

## 2026-05-31 Contract v1.5 / cli-v1.2.1 Update

- CLI JSON/JSONL runtime contract revision is `v1.5`; `schema_version` remains
  `1`.
- `soft-trigger`, `soft-stop`, `soft-status`, and `wait-ready` JSON responses
  now include additive request diagnostics where knowable: `method`, `url`,
  `endpoint`, `timeout_ms`, and `elapsed_ms`.
- `list-resources --json` adds summary fields while keeping `resources`,
  `verify`, and `live_only` stable.
- `start-trigger-record --dry-run` explicitly reports that dry-run performs no
  VISA I/O, writes no CSV, and starts no HTTP server.
- No SCPI, VISA timeout, trigger wait strategy, cleanup order, CSV columns, or
  existing JSON field meanings changed.
