# Keysight 34461A Validation History

Updated: 2026-05-31

This file archives historical validation notes and older handoff details that
were previously kept in `docs/session-handoff.md`. Current CLI status, active
risks, and next work stay in `docs/session-handoff.md`.

## 2026-06-01 cli-v1.3.0 Release Validation

- Target release: `cli-v1.3.0`.
- Package metadata: `keysight-logger-cli` version `1.3.0`.
- Workspace reinstall refreshed the editable CLI package from `1.2.1` to
  `1.3.0`.
- Version checks:
  `.\.venv\Scripts\python.exe -m keysight_logger_cli --version` and
  `.\.venv\Scripts\keysight-logger.exe --version` both reported
  `keysight-logger 1.3.0`.
- Full workspace validation:
  `.\.venv\Scripts\python.exe -m pytest packages tests -q -p no:cacheprovider --basetemp .tmp_tests\pytest_tmp_cli130`
  passed with `389 passed, 1 warning, 145 subtests passed`.
- Release wrapper gate:
  `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packages\cli\scripts\release-cli-check.ps1 -Target keysight-34461a`
  passed and wrote
  `.tmp_tests\cli_release\keysight-34461a\20260601-123707\summary.md`.
- Live Keysight 34461A validation for the monorepo package layout passed
  earlier on 2026-06-01; see `packages/cli/docs/session-handoff.md`.

## 2026-05-31 cli-v1.2.1 Release Validation

- Target release: `cli-v1.2.1`.
- Package metadata: `keysight-logger` version `1.2.1`.
- CLI runtime contract revision: `v1.5`; `schema_version` remains `1`.
- Intended no-hardware tag gate:
  `.\.venv\Scripts\python.exe -m pytest packages/cli/tests/test_cli_package_metadata.py tests/test_docs_cli_examples.py tests/test_core_public_api.py packages/cli/tests/test_cli_docs_ownership.py -q -p no:cacheprovider`
  passed with `16 passed`.
- Full no-hardware pytest gate:
  `.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --basetemp .tmp_tests\pytest_tmp`
  passed with `345 passed, 76 subtests passed`.
- Wrapper preflight gate:
  `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packages\cli\scripts\preflight-cli.ps1 -Target keysight-34461a`
  passed and wrote `E:\Git\Keysight\.tmp_tests\cli_preflight\keysight-34461a\summary.md`.
- No-hardware live-plan gate:
  `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packages\cli\scripts\live-cli-check.ps1 -Target keysight-34461a -Connection usb -Resource "SIM::34461A" -PlanOnly`
  passed and wrote `E:\Git\Keysight\.tmp_tests\cli_live\keysight-34461a\usb\minimal\20260531-190848\summary.md`.
- Release wrapper gate:
  `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packages\cli\scripts\release-cli-check.ps1 -Target keysight-34461a`
  passed and wrote `E:\Git\Keysight\.tmp_tests\cli_release\keysight-34461a\20260531-190729\summary.md`.
- `git diff --check` passed with only LF-to-CRLF normalization warnings.
- The local `.venv\Scripts\keysight-logger.exe` console script was not present
  in this checkout, and `python -m keysight_logger_cli --version` reported the
  venv's older installed distribution metadata (`1.1.5`). The release gate
  above validates `pyproject.toml` package metadata as `1.2.1`; reinstalling
  the editable package will refresh the command-line `--version` output.
- Scope is release metadata, additive CLI client diagnostics, no-hardware
  release validation/reporting, wrapper report metadata, Core/CLI boundary
  guards, and documentation cleanup. No SCPI, VISA timeout, trigger wait
  strategy, cleanup order, CSV schema, or existing JSON field meanings changed.

## 2026-05-31 Legacy Root-Level Import Cleanup Validation

- Static legacy import check:
  `rg -n "import keysight_logger\.(acquisition|instrument|instrument_backend|measurement|models|simulator|storage|trigger)|from keysight_logger import (acquisition|instrument|instrument_backend|measurement|models|simulator|storage|trigger)|from keysight_logger\.(acquisition|instrument|instrument_backend|measurement|models|simulator|storage|trigger) import" src tests docs README.md CHANGELOG.md`
  returned no matches.
- Compatibility wording check:
  `rg -n "compatibility shims|compatibility re-export shims|legacy top-level compatibility shims" docs README.md CHANGELOG.md tests`
  found only historical release/history text or current notes that the old
  root-level imports have been removed.
- Focused API/package/CLI/docs validation:
  `.\.venv\Scripts\python.exe -m pytest tests/test_core_public_api.py packages/cli/tests/test_cli_package_metadata.py tests/test_cli_args.py packages/cli/tests/test_cli_docs_ownership.py -q -p no:cacheprovider --basetemp .tmp_tests\pytest_tmp`
  passed with `128 passed, 12 subtests passed`.
- The planned broader command including `tests/test_storage.py` did not run
  because that file does not exist in this checkout. Per the cleanup plan, it
  was omitted rather than replaced with new coverage.
- Broader affected module validation:
  `.\.venv\Scripts\python.exe -m pytest tests/test_instrument.py tests/test_instrument_backend.py tests/test_measurement.py tests/test_simulator.py tests/test_trigger_router.py tests/test_acquisition_engine.py tests/test_core_runner.py tests/test_core_run_plan.py -q -p no:cacheprovider --basetemp .tmp_tests\pytest_tmp`
  passed with `170 passed, 5 subtests passed`.
- Full validation:
  `.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --basetemp .tmp_tests\pytest_tmp`
  passed with `343 passed, 76 subtests passed`.
- `git diff --check` passed with only LF-to-CRLF normalization warnings for
  edited Markdown files.
- Scope is removal of legacy root-level Core re-export modules and the matching
  compatibility import test, plus documentation updates. No `pyproject.toml`
  change was made. CLI runtime behavior, Core runtime behavior, SCPI command
  sequences, VISA timeout behavior, trigger wait strategy, stop/cleanup order,
  JSON/JSONL schema, and CSV columns are unchanged.

## 2026-05-31 CLI Contract v1.4 Validation

- Focused CLI/docs/wrapper validation:
  `.\.venv\Scripts\python.exe -m pytest tests/test_cli_args.py tests/test_cli_worker_subprocess.py tests/test_cli_wrappers.py packages/cli/tests/test_cli_docs_ownership.py tests/test_docs_cli_examples.py -q -p no:cacheprovider --basetemp .tmp_tests\pytest_tmp`
  passed with `131 passed, 12 subtests passed`.
- CLI/core boundary validation:
  `.\.venv\Scripts\python.exe -m pytest tests/test_cli_args.py tests/test_cli_worker_subprocess.py tests/test_cli_wrappers.py packages/cli/tests/test_cli_package_metadata.py tests/test_core_public_api.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py packages/cli/tests/test_cli_docs_ownership.py -q -p no:cacheprovider --basetemp .tmp_tests\pytest_tmp`
  passed with `172 passed, 71 subtests passed`.
- Full validation:
  `.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --basetemp .tmp_tests\pytest_tmp`
  passed with `344 passed, 76 subtests passed`.
- `git diff --check` passed with only LF-to-CRLF normalization warnings.
- An initial focused run without `--basetemp` hit the known local Windows temp
  permission issue under `C:\Users\tom75\AppData\Local\Temp\pytest-of-tom75`;
  rerunning with repo-local `.tmp_tests\pytest_tmp` passed.
- Scope is CLI client JSON diagnostics, simulator-only worker subprocess
  coverage, wrapper readiness/status orchestration, and documentation. No live
  hardware validation is required because SCPI behavior, VISA timeout behavior,
  trigger wait strategy, stop/cleanup order, and CSV columns are unchanged.

## Current Status

- Branch: `Cli`
- Current `cli-v1.2.1` release pass records the CLI branch after merging
  `Core-v1.1.0` while preserving CLI package identity, console script, wrapper
  scripts, CLI JSON/JSONL contracts, and tests. The CLI now exposes Core
  v1.1.0 measurement options (`voltage-dc-ratio`,
  `--auto-zero once`, `--ac-bandwidth-hz`, and `--current-terminal`) and has
  updated agent/orchestrator contract documentation, JSONL schema tests,
  additive v1.5 client diagnostics, and no-hardware release reporting.
- Current legacy import cleanup removes the old root-level Core module
  compatibility shims. Python integrations should use `keysight_logger_core`
  or `keysight_logger_core.*`; the `keysight-logger` console script and
  `keysight_logger_cli.cli` remain the CLI entry points. This cleanup does not
  change CLI runtime behavior, Core runtime behavior, SCPI command sequences,
  VISA timeout behavior, trigger wait strategy, stop/cleanup order, JSON/JSONL
  schema, or CSV columns.
- Current Core/CLI isolation scope is complete for this pass. The documented
  USB no-hardware acceptance, live minimal/basic/external wrapper suites, and
  manual focused live smoke commands have been run and recorded below. Live
  discovery (`list-resources --verify` / `--live-only`) has also been verified.
  LAN/network-path discovery and basic wrapper validation were also
  user-reported from a second checkout/machine. Remaining optional validation
  is LAN external/full coverage only if the operator wants to re-check external
  trigger behavior over TCPIP.
- Current hardware-test readiness review updates active wrapper examples to use
  `powershell.exe -NoProfile -ExecutionPolicy Bypass -File` and changes
  preflight/live wrapper case ports from random high ports to OS-assigned
  loopback ports. This avoids Windows excluded-port or execution-policy
  failures in the no-hardware validation path and does not change SCPI,
  acquisition behavior, trigger wait strategy, stop flow, cleanup order, VISA
  timeout behavior, release/local behavior, NPLC, Auto Range/Zero, or VM Comp
  behavior.
- Current Core/CLI boundary cleanup removes CLI command-name context from
  `core.validation.validate_client_port`; invalid `--port` errors now use a
  neutral TCP range message. `MeasurementDefinition.canonical_name` is now the
  preferred metadata field for stable external measurement names, with
  `cli_name` retained as a read-only compatibility alias. This pass does not
  change SCPI command sequences, acquisition runtime behavior, dry-run SCPI
  planning, CLI JSON/JSONL schema, package-root public API exports, WebUI
  workflow, VISA timeout behavior, trigger wait strategy, stop flow, cleanup
  order, release/local behavior, NPLC, Auto Range/Zero, or VM Comp behavior.
- Current public Core API pass defines `keysight_logger_core` as the formal
  minimal public entry point for WebUI/agent integrations. It exports the
  request/profile, validation, dry-run planning, runtime event/result/control
  plane, stop-control, and runner entry-point symbols needed by integrations,
  while leaving implementation submodules in place. This pass does not change
  CLI JSON schema, SCPI command sequences, VISA timeout behavior, trigger wait
  strategy, measurement logic, stop flow, release/local behavior, cleanup
  order, NPLC, Auto Range/Zero, or VM Comp behavior.
- Current Core boundary cleanup moves the shared UTC+8 timezone constant to
  `core.constants`, so `core.validation` no longer depends on `core.storage`.
  It also adds `docs/webui-integration.md` for the supported WebUI/agent
  package-root import boundary, dry-run/runtime examples, control-plane usage,
  and current one-session-per-instrument model. This pass does not change
  runtime behavior, dry-run SCPI planning, CLI schema, SCPI command sequences,
  VISA timeout behavior, trigger wait strategy, stop flow, cleanup order,
  release/local behavior, NPLC, Auto Range/Zero, or VM Comp behavior.
- Current WebUI guide follow-up expands `docs/webui-integration.md` with
  form-to-`StartRequest` mapping, validation flow, dry-run confirmation,
  runtime event handling, stop handling, internal symbol boundaries, and
  CLI-adapter responsibilities. This is documentation-only and does not change
  Core API exports, CLI schema, runtime behavior, dry-run planning, SCPI, VISA
  timeout behavior, trigger wait strategy, stop flow, cleanup order,
  release/local behavior, NPLC, Auto Range/Zero, or VM Comp behavior.
- Current CLI/Core boundary naming pass changes `core.validation` buffer
  overflow warnings to a generate/list model, renames the dry-run Core plan to
  neutral `StartPlan`/`measurement_name`, and keeps dry-run JSON schema v1
  output on `measurement_cli_name` for CLI wrappers and reports. This pass does
  not change SCPI command sequences, VISA timeout behavior, trigger wait
  strategy, measurement logic, stop flow, release/local behavior, cleanup
  order, NPLC, Auto Range/Zero, or VM Comp behavior.
- Current Web-ready start runner isolation pass adds `core.session` as the
  typed runtime API for `StartRunEvent`, `StartRunResult`, event sinks,
  pluggable control planes, no-op controls, and stop controller state.
  `core.runner` now returns typed results and emits typed runtime events; the
  CLI maps those events/results to existing text/JSONL output and process exit
  codes. Non-dry-run runtime JSONL and `GET /status` now include an optional
  `run_id` while keeping `schema_version: 1`; dry-run plans do not include
  `run_id`. The legacy `--enable-hw-trigger` alias is normalized in `cli.py`
  before `StartRequest` enters Core. This pass does not change SCPI command
  sequences, VISA timeout behavior, trigger wait strategy, NPLC, Auto
  Zero/Range, VM Comp, stop/release/local behavior, or cleanup order.
- Current program-boundary baseline adds `core.models.StartRequest`, changes
  `core.validation` and `core.run_plan` to consume that request model instead
  of `argparse.Namespace`, keeps adapter-only `status_format` out of
  `StartPlan`, and moves non-dry-run `start-trigger-record`
  orchestration into `core.runner`. `cli.py` now adapts argparse input,
  validates, emits dry-run plans, and delegates runtime execution with injected
  terminal controls. This pass does not change SCPI command sequences, VISA
  timeout behavior, trigger wait strategy, measurement logic, stop flow,
  release/local behavior, or cleanup order.
- Current CLI/Core split moves acquisition, instrument, instrument backend,
  measurement, models, simulator, storage, and trigger modules under
  `packages/core/src/keysight_logger_core/`, adds `core.validation` for shared start
  validation/path/mode helpers, and adds `core.run_plan` for dry-run start
  plan construction. The old top-level module paths remain thin compatibility
  shims, and `keysight_logger_cli.cli:main` remains the console-script entry point.
  No SCPI command sequences, VISA timeout behavior, trigger wait strategy,
  measurement logic, stop/release/local behavior, or cleanup order changed.
- Current CLI/Core test-boundary cleanup adds direct Core tests for
  `core.validation` and `core.run_plan`, then trims `tests/test_cli_args.py` so
  it owns parser defaults/help, JSON aliases, command dispatch, dry-run
  formatting, simulate workflows, and soft/list command behavior. This pass is
  test-structure only and does not change public CLI behavior, compatibility
  shims, SCPI command sequences, VISA timeout behavior, trigger wait strategy,
  measurement logic, stop/release/local behavior, or cleanup order.
- Current control-plane/discovery update adds a JSONL `ready` event for
  non-dry-run `start-trigger-record`, `list-resources --dry-run`, and optional
  resource-manager injection for discovery tests. This pass does not change
  SCPI command sequences, VISA timeout behavior, trigger wait strategy,
  acquisition/read paths, stop flow, cleanup order, or measurement logic.
- Current low-risk CLI/preflight/docs pass adds root `--version`, top-level and
  subcommand help coverage, dry-run JSON contract assertions, preflight
  `-ListTargets`, constrained preflight `-OutputRoot`, report summary counts,
  and active-doc console-script consistency checks. This pass does not change
  SCPI command sequences, VISA timeout behavior, trigger wait strategy,
  measurement logic, Auto Zero/Range, NPLC, VM Comp, stop/release/local
  behavior, or cleanup order.
- Current wrapper CI fix keeps interactive live and `-PlanOnly` preflight-first,
  but changes redirected-stdin live wrapper runs to skip nested preflight,
  generate dry-run plans, write `confirmation_required`, and refuse live
  acquisition. This keeps the no-live safety contract stable on GitHub Actions
  where nested PowerShell preflight can fail before the confirmation gate when
  stdin is redirected.
- `cli-v1.2.1` is the intended current CLI baseline after merging
  `Core-v1.1.0` into the CLI branch, clarifying the CLI/agent orchestrator
  contract, adding v1.5 client diagnostics, and adding the no-hardware release
  gate. Create the tag after committing these changes.
- `pyproject.toml` now exposes the installed console script
  `keysight-logger = "keysight_logger_cli.cli:main"`. The explicit
  `python -m keysight_logger_cli` form remains supported in documentation.
- Local tags:
  - `v0.2.0-cli`: current logging baseline before voltage support.
  - `v0.3.0-cli`: DC current plus DC voltage CLI baseline.
  - `v0.4.0-cli`: DC current, DC voltage, 2-wire resistance, 4-wire
    resistance, live-only resource listing, and locked CSV output error
    handling.
- Release baselines:
  - `v1.0.0-cli`: stable six-measurement CLI baseline for DCI, DCV, ACI, ACV,
    2-wire resistance, and 4-wire resistance. Includes AC current/voltage CLI
    support, console status readability improvements, optional timestamped CSV
    output path, software-custom waiting-status de-spam fix, and opt-in DCV
    Input Z control.
  - `v1.1.0-cli`: CLI validation baseline. Keeps `v1.0.0-cli` acquisition behavior
    and adds stricter preflight CLI validation for documented numeric limits,
    measurement range whitelists, AC/DC/resistance NPLC rules, and
    profile-backed 34461A range/NPLC metadata used by CLI help and validation.
  - `v1.1.5-cli`: resource-verify cleanup baseline. Keeps acquisition behavior unchanged
    and makes successful `list-resources --verify` / `--live-only` checks run
    best-effort release-to-local before closing the verification session.
  - `v1.1.6-cli`: control-plane/discovery baseline. Keeps acquisition behavior unchanged
    and adds the JSONL `ready` event for non-dry-run workers,
    `list-resources --dry-run`, and preflight coverage for the
    `list-resources --dry-run --live-only --json` contract.
  - `v1.1.7-cli`: Core/CLI boundary baseline. Keeps acquisition
    behavior unchanged, completes the Core/CLI naming and public API boundary
    cleanup, records completed USB hardware validation, ACI/ACV real-signal
    sanity checks, live discovery checks, and LAN basic wrapper validation.
  - `cli-v1.1.8`: intended current CLI release baseline. Records
    `core-v1.0.0` as the accepted Core merge-base while keeping the CLI file
    tree and runtime behavior stable, and clarifies that CLI compatibility
    aliases remain adapter-owned rather than Core schema.
  - `cli-v1.2.0`: CLI release baseline after merging
    `Core-v1.1.0`. Exposes the new measurement options in the CLI and records
    agent/orchestrator contract documentation plus JSONL schema tests.
  - `cli-v1.2.1`: intended current CLI release baseline. Adds v1.5 additive
    client diagnostics, no-hardware release validation/reporting, wrapper
    report metadata, and Core/CLI boundary guards.

## Previous cli-v1.2.0 Release Validation

Latest local package, docs, CLI contract, and no-hardware validation for the
intended `cli-v1.2.0` baseline:

```powershell
uv pip install -e ".[dev]" --link-mode=copy
# Uninstalled keysight-logger==1.1.8 and installed keysight-logger==1.2.0.

.\.venv\Scripts\keysight-logger.exe --version
# keysight-logger 1.2.0

.\.venv\Scripts\python.exe -m pytest tests/test_cli_args.py packages/cli/tests/test_cli_docs_ownership.py tests/test_docs_cli_examples.py -q -p no:cacheprovider
# 92 passed, 10 subtests passed

.\.venv\Scripts\python.exe -m pytest tests/test_cli_args.py packages/cli/tests/test_cli_package_metadata.py tests/test_core_public_api.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py packages/cli/tests/test_cli_docs_ownership.py -q -p no:cacheprovider
# 133 passed, 69 subtests passed

.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
# 310 passed, 74 subtests passed

git diff --check
# no whitespace errors; existing LF-to-CRLF working-copy warnings only
```

Focused live hardware validation for the merged Core v1.1.0 measurement options
was reported by the operator on 2026-05-29 and is summarized in
`docs/session-handoff.md`.

## Latest cli-v1.1.8 Release Validation

Latest local release-documentation, package, and CLI flag-removal validation
for the intended `cli-v1.1.8` baseline:

```powershell
.\.venv\Scripts\python.exe -m pytest packages/cli/tests/test_cli_package_metadata.py tests/test_docs_cli_examples.py tests/test_core_public_api.py packages/cli/tests/test_cli_docs_ownership.py -q -p no:cacheprovider
# 11 passed

.\.venv\Scripts\python.exe -m pytest tests/test_cli_args.py -q -p no:cacheprovider
# 84 passed, 10 subtests passed

uv pip install -e ".[dev]" --link-mode=copy
# Uninstalled keysight-logger==1.1.7 and installed keysight-logger==1.1.8.

.\.venv\Scripts\keysight-logger.exe --version
# keysight-logger 1.1.8

.\.venv\Scripts\keysight-logger.exe start-trigger-record --help | Select-String -Pattern "enable-hw-trigger"
# no output

.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
# 283 passed, 61 subtests passed

git diff --check
# no whitespace errors; existing LF-to-CRLF working-copy warnings only
```

No live acquisition was run for this pass because it does not alter
instrument-affecting behavior.

## CLI/Core Isolation Progress

Current isolation status for future maintenance:

- Done: runtime modules have moved under `keysight_logger_core.*`; the former
  top-level compatibility shim import paths have been removed.
- Done: `argparse.Namespace` is adapted in `cli.py` and no longer crosses into
  Core start validation, dry-run planning, or runtime orchestration.
- Done: `core.models.StartRequest` is the shared start-command request model.
- Done: `core.validation` owns shared request validation, mode/path resolution,
  and warning-list generation; CLI/WebUI adapters decide how to present those
  warnings.
- Done: `core.validation` imports shared `UTC_PLUS_8` from `core.constants`
  and is guarded by a static test against direct `core.storage` imports.
- Done: `core.run_plan` owns dry-run plan construction with neutral
  `StartPlan` / `measurement_name` internals; the CLI only formats the plan for
  text or JSONL output and preserves adapter-only schema fields such as
  `measurement_cli_name`.
- Done: `core.runner` owns non-dry-run `start-trigger-record` orchestration,
  including backend creation, router/server setup, CSV writer setup,
  acquisition worker lifecycle, summary, and cleanup.
- Done: `core.session` defines the typed runtime boundary:
  `StartRunEvent`, `StartRunResult`, event sinks, control planes, control
  handles, no-op controls, terminal-control hook points, and run IDs.
- Done: `keysight_logger_core` exports the minimal WebUI/agent public API for
  start request/profile models, validation, dry-run planning, runtime
  event/result/control-plane types, stop control, and `run_start_session`.
- Done: `docs/webui-integration.md` documents the direct WebUI workflow from
  form adapter through validation, dry-run confirmation, runtime event handling,
  stop routing, and CLI/Core responsibility boundaries.
- Done: old naming aliases and integration details such as `StartCommandPlan`,
  `print_buffer_overflow_warnings`, `StartRunnerDependencies`,
  `StartRunControls`, `NoOpStartRunControls`, `new_run_id`,
  `NullStartRunEventSink`, and `SoftwareTriggerControlPlane` are not exported
  from the public package root.
- Done: CLI runtime responsibility is now adapter-shaped: parse arguments,
  normalize legacy CLI aliases, format text/JSONL events, map typed results to
  process exit codes, and inject terminal controls.
- Done: Core and CLI test ownership has been split. Core behavior is covered by
  `tests/test_core_validation.py`, `tests/test_core_run_plan.py`, and
  `tests/test_core_runner.py`; CLI tests cover parser behavior, formatted
  output, command dispatch, and soft/list client workflows.
- Verified: Core contains no `print_buffer_overflow_warnings`,
  `StartCommandPlan`, `measurement_cli_name`, `argparse`,
  `argparse.Namespace`, `status_format`, `enable_hw_trigger`, `exit_code`, or
  `rc=` coupling after the latest pass.
- Verified: full automated suite and no-hardware preflight passed for the
  latest isolation pass; see "Validation Status" below for exact commands.
- Completed after the latest user-reported USB hardware pass: full basic live
  validation has a user-provided USB resource and passed; live discovery also
  passed for the target 34461A resource. ACI and ACV real-signal immediate
  readbacks were also user-checked against the instrument front panel.
  LAN/network-path discovery and basic wrapper validation also passed from a
  second checkout/machine. Remaining optional hardware follow-up is LAN
  external/full coverage only if the operator wants to re-check external
  trigger behavior over TCPIP. The isolation work itself intentionally did not
  change SCPI, VISA timeout behavior, trigger wait strategy, measurement logic,
  stop flow, cleanup order, Auto Range, Auto Zero, NPLC, VM Comp, or
  release/local behavior.
- AC current and AC voltage CLI support has been committed with automated tests
  and documentation. User has now reported real-instrument AC flow validation
  for AC voltage and AC current across the supported trigger-mode families,
  with software timer also checked under software mode: OK. User also reported
  an ACI real-signal immediate smoke where three CLI readings around
  `316 uA` matched the instrument front panel, and an ACV real-signal
  immediate smoke where three CLI readings around `270-291 uV` matched the
  instrument front panel.
- User has now reported low-cost real-instrument DC current and DC voltage
  regression tests after the refactor: OK.
- User has now reported required `resistance-2w` real-instrument smoke tests:
  OK.
- User has now reported `resistance-4w` real-instrument smoke tests after the
  `FRES:ZERO:AUTO` removal: OK; front-panel remote-command error cleared.
- User clarified that resistance software, external, software-custom, and
  external-custom trigger modes were also tested on the real instrument with
  short 5-10 reading runs: OK.
- `list-resources --verify` remains diagnostic and shows both live and stale
  VISA cache entries. Live entries that pass `*IDN?` are released back to local
  on a best-effort basis before closing the verification session.
- `list-resources --live-only` verifies resources, hides stale entries, and uses
  the same successful-live release cleanup.
- `--csv` is now optional. If omitted, the CLI prints and writes to a UTC+8
  timestamped path under `data`, for example `data/2026-05-11-14-30-05.csv`.
- DC voltage now supports an opt-in `--dcv-input-impedance default|10m|auto`
  setting. User has reported both `auto` and `10m` real-instrument smoke tests:
  OK. `default` preserves the previous behavior and writes no Input Z SCPI.
- CLI/backend start-argument validation now enforces measurement range and
  NPLC whitelists plus documented bounds for timer, timeout, count, buffer,
  trigger-server port, software queue/throttle, and hardware trigger delay
  parameters before opening VISA. `start-trigger-record --help` lists these
  limits directly.
- 2026-05-16 profile refactor status:
  - 34461A range/NPLC tables now live in `InstrumentProfile` as
    per-measurement `MeasurementOptions`.
  - `MeasurementDefinition` is now logical metadata only: canonical external
    name, internal type, unit, range label, and `--current-range` alias
    behavior.
  - CLI help and validation still expose the same default 34461A limits, but
    read them from the default profile.
  - No CLI model selector, `*IDN?` auto-profile switching, SCPI command
    sequence, trigger behavior, VISA timeout, stop flow, or cleanup behavior
    changed.
  - Reviewer reported no discrete correctness issues in the staged/unstaged
    changes, and local focused/full suites pass.
  - User asked whether real-instrument testing is required; answer was that it
    is recommended as a short smoke test when convenient, but this is not a
    high-risk mandatory block because no instrument I/O behavior changed.
- `pyproject.toml` `[project].version` is now `1.1.8` for the intended
  `cli-v1.1.8` release baseline.
- 2026-05-17 TriggerRouter defense-in-depth update:
  - `TriggerRouter` now owns the shared CLI/core queue bound instead of relying
    only on HTTP entry-point prechecks.
  - Normal trigger events are non-blocking and rejected when the bounded queue
    is full.
  - Stop/control events use a separate priority queue so `soft-stop` remains
    deliverable even when normal trigger events have filled the queue.
  - CLI `--sw-queue-max` is passed into `TriggerRouter`; `0` uses the default
    safety cap of 10000 pending normal events.
  - No SCPI, VISA timeout, trigger wait strategy, cleanup order, NPLC,
    Auto Zero, Auto Range, VM Comp, or release/local behavior changed.
- 2026-05-18 acquisition error and identity hardening:
  - Simple capture and custom/buffered capture exceptions now share one fatal
    acquisition-failure policy: increment `errors` once, best-effort query
    `SYST:ERR?`, emit the existing `capture error...` or
    `buffered capture error...` status text, set `fatal_error`, and stop the
    engine.
  - CLI `start-trigger-record` now returns `3` for those fatal acquisition
    failures through the existing `engine.fatal_error` path.
  - `VisaInstrument.connect()` now opens the resource, sets timeout, queries
    `*IDN?`, and accepts only Keysight/Agilent `34461A` identity before sending
    `*CLS` / `*RST`.
  - Failed IDN validation or IDN query failure closes the VISA session/resource
    manager, clears local handles, raises `InstrumentError`, and does not send
    reset/clear SCPI.
  - CLI connect-stage `InstrumentError` prints `error: ...`, returns `3`, and
    skips release/local cleanup SCPI for the unvalidated resource.
  - Hardware trigger timeout remains a protective re-arm condition, not an
    acquisition error.
- 2026-05-18 hardware status polling diagnostics:
  - Simple external hardware trigger status-byte polling now treats repeated
    PyVISA status-byte timeouts as nonfatal diagnostics instead of immediate
    acquisition errors.
  - The 5th consecutive status-byte timeout emits a warning; the 25th and every
    additional 25 consecutive timeouts increment `errors` and emit a degraded
    status. Any successful status-byte poll resets the consecutive count.
  - Non-timeout hardware wait exceptions still increment `errors` immediately
    and emit exception type/message, but do not set `fatal_error`.
  - User ran a real-instrument simple external no-edge smoke with
    `--trigger-timeout-ms 1000`, manual 0.1 A range, Auto Zero on, NPLC 10,
    and `--max-samples 10`: repeated protective re-arm messages appeared,
    no status poll warning/degraded error appeared, Ctrl+C stopped cleanly,
    `captured=0 errors=0`, and release/local plus cleanup release succeeded.
  - No SCPI sequence, VISA timeout value, trigger wait strategy, cleanup order,
    NPLC, Auto Zero, Auto Range, VM Comp, or release/local behavior changed.
- 2026-05-18 CLI agent support:
  - `start-trigger-record --dry-run` validates CLI arguments and emits a planned
    measurement/trigger/SCPI/read/cleanup contract without opening VISA,
    creating a CSV writer, or starting the HTTP trigger server.
  - `start-trigger-record --status-format jsonl` emits parseable JSON Lines
    events for messages, status, samples, errors, and summary while preserving
    the default text output when omitted.
  - `start-trigger-record --simulate` runs the normal acquisition engine against
    a deterministic simulated VISA instrument backend for workflow tests without
    PyVISA or a real 34461A.
  - `soft-trigger --format json` and `soft-stop --format json` provide
    structured single-response output for agent callers.
  - `VisaInstrument` accepts an injected resource manager factory for tests and
    future transport adapters while preserving the default PyVISA path.
  - No SCPI behavior, VISA timeout strategy, trigger wait strategy, stop flow,
    cleanup order, Auto Range, Auto Zero, NPLC, VM Comp, or release/local
    behavior changed for normal real-instrument runs.
- 2026-05-19 simulate agent coverage expansion:
  - CLI tests now exercise simulate JSONL success workflows for immediate,
    software, software timer, immediate-custom, software-custom, and
    external-custom trigger modes through the direct `cmd_start()` harness.
  - A representative failing simulator read verifies JSONL `error` output and
    `summary.fatal_error` with exit code `3`.
  - A real `CsvWriter` simulate smoke verifies CSV headers and one software
    trigger row, including parseable trigger metadata.
  - No runtime CLI options, JSONL schema, simulator accuracy model, SCPI
    behavior, VISA timeout, trigger wait strategy, stop flow, cleanup order,
    Auto Range, Auto Zero, NPLC, VM Comp, or release/local behavior changed.
- 2026-05-19 simulate failure/boundary coverage expansion:
  - CLI simulate tests now cover external simple JSONL hardware-trigger
    capture, immediate-custom buffered drain batch metadata, malformed
    `DATA:REMove?` buffered failure, JSONL CSV permission failure, and stop
    control delivery while the normal software trigger queue is full.
  - Simulator unit tests now pin BUS `*TRG` saturation at
    `trigger_count * sample_count` and status-byte armed/abort semantics for
    external/simple hardware completion.
  - No runtime CLI option, simulator accuracy model, SCPI behavior, VISA
    timeout, trigger wait strategy, stop flow, cleanup order, Auto Range, Auto
    Zero, NPLC, VM Comp, or release/local behavior changed.
- 2026-05-19 CLI ergonomics update:
  - Added `--json` aliases for `start-trigger-record`, `list-resources`,
    `soft-trigger`, and `soft-stop`.
  - Added local `--dry-run` previews for `soft-trigger` and `soft-stop`
    without sending HTTP requests.
  - Added a focused JSON/JSONL contract doc and CLI argument/output tests for
    the alias and preview paths.
  - No SCPI, VISA timeout, trigger wait strategy, stop flow, cleanup order,
    Auto Range, Auto Zero, NPLC, VM Comp, or release/local behavior changed.
- 2026-05-21 one-key CLI validation workflow:
  - Added `scripts/preflight-cli.ps1` for hardware-free all-target CLI validation.
    It currently runs the `keysight-34461a` target and writes artifacts under
    `.tmp_tests/cli_preflight/keysight-34461a/`.
  - Added `scripts/live-cli-check.ps1` for opt-in live smoke validation of the
    same target over USB/local or LAN/network. It requires explicit `-Target`,
    `-Connection`, and `-Resource`, runs preflight first, prints a same-args
    dry-run plan, then waits for Enter before running one live current-dc
    immediate sample. It refuses to run the live smoke if stdin is redirected
    and Enter cannot be confirmed interactively.
  - Added `docs/supported-models.md` as the manual source of truth for the CLI
    validation matrix and `docs/hardware-test-plan.md` as the preferred
    preflight/live workflow.
  - No `packages/cli/src/keysight_logger_cli/cli.py` live behavior changed. The scripts wrap
    existing CLI paths only.
  - Safety rules: live LAN validation never scans or guesses a resource; there
    is no restore switch because the CLI cannot snapshot/restore the initial
    instrument state; cleanup remains the existing best-effort release/local
    path.
  - Live validation was not executed in this implementation pass because it
    requires an explicitly approved real instrument resource and Enter
    confirmation.
- 2026-05-22 planning and validation consolidation:
  - Added `docs/project-plan.md` as the durable English project plan and
    removed the old split plan files
    `docs/keysight-34461a-plan-v2.md` and
    `docs/keysight-34461a-architecture-plan-v3.md`.
  - Rewrote `docs/hardware-test-plan.md` around pass levels: no-hardware
    acceptance, live basic acceptance, external trigger acceptance, and full
    current implementation pass.
  - Expanded `scripts/preflight-cli.ps1` so the no-hardware wrapper covers all
    six measurements, `READ?`, `FETC?`, buffered
    `DATA:POINts?` / `DATA:REMove?`, simulator end-to-end trigger modes, JSON
    soft client dry-runs, and mocked list-resource coverage.
  - Expanded `scripts/live-cli-check.ps1` with
    `-Suite minimal|basic|external|full`. The wrapper still requires explicit
    `-Target`, `-Connection`, and `-Resource`, runs preflight first, prints
    dry-run plans before live execution, refuses live runs when stdin is
    redirected, and uses known-port `soft-stop` cleanup for timed-out managed
    live cases.
  - Live managed-case failures and timeouts are recorded in `report.json` and
    `summary.md` with captured count, error count, CSV row count, and failure
    reasons before the wrapper exits nonzero.
  - Updated `README.md`, `docs/README_CLI_EN.md`, `docs/supported-models.md`,
    and `AGENTS.md` to point future agents to the durable plan, current
    handoff, hardware validation guide, and supported target/suite matrix.
  - No `packages/core/src/keysight_logger_core/*` behavior changed. No SCPI sequence, VISA
    timeout, trigger wait strategy, stop flow, cleanup order, Auto Range, Auto
    Zero, NPLC, VM Comp, or release/local behavior changed.
- 2026-05-23 worker control/status contract:
  - Added `GET /status` to `SoftwareTriggerAdapter`. It returns a
    non-mutating JSON object with schema version, service name, running/stopping
    status, trigger/stop/status URLs, queue size/limit, software trigger rate
    limit, captured count, error count, fatal error, and UTC timestamp.
  - `start-trigger-record` now passes a status provider backed by
    `engine.stats.captured`, `engine.stats.errors`, `engine.fatal_error`, and
    `stop_controller.stop`; it also prints the status endpoint beside the
    existing trigger and stop endpoints.
  - Added `docs/worker-contract.md` for Meters worker modes, local control
    endpoints, JSONL linkage, artifacts, and `report.json` / `summary.md` v1
    contract.
  - This is a control-plane and documentation contract change only. No SCPI,
    VISA timeout, trigger wait strategy, stop flow, cleanup order, Auto Range,
    Auto Zero, NPLC, VM Comp, measurement logic, or release/local behavior
    changed.

## AI Agent CLI Support Status

This section records the current state of the agent-control CLI work. It
answers the design question raised in the 2026-05-19 discussion: "Do we already
have injectable transport plus `--json`, `--simulate`, and `--dry-run` for
agent automation?"

Short answer for the next agent:

- The important agent-control foundations mostly exist for the current
  34461A-focused CLI.
- They are intentionally concentrated on the hardware-affecting main workflow,
  `start-trigger-record`, rather than mechanically adding all three flags to
  every command.
- The code is not yet a complete multi-instrument driver framework. It has a
  34461A `VisaInstrument`, an injected resource-manager path, a compatible
  simulator, test fakes, and a profile system with only the 34461A profile.

Implemented command support:

| Command | Structured output | Dry run | Simulator | Notes |
| --- | --- | --- | --- | --- |
| `start-trigger-record` | `--status-format jsonl` or `--json` | `--dry-run` | `--simulate` | Main acquisition workflow. JSONL is used instead of a single `--json` object because this command streams runtime events. |
| `soft-trigger` | `--format json` or `--json` | `--dry-run` | Not implemented | Client command that sends one HTTP trigger request. |
| `soft-stop` | `--format json` or `--json` | `--dry-run` | Not implemented | Client command that sends one HTTP stop request. |
| `list-resources` | `--format json` or `--json` | `--dry-run` | Not implemented | Discovery command. `--verify` opens resources and queries `*IDN?`; `--live-only` filters stale VISA cache entries. Dry-run reports the discovery contract without touching VISA. |

The running worker also exposes `GET /status` on the same local HTTP port as
`/trigger` and `/stop`. It is not a CLI command; it is the non-mutating
orchestrator health/status endpoint documented in `docs/worker-contract.md`.

`start-trigger-record` details:

- `--dry-run` validates arguments and prints a planned execution contract
  without opening VISA, creating a CSV writer, starting the software trigger
  HTTP server, starting the acquisition worker, or writing to a real instrument.
- Dry-run plans include resource, measurement CLI/internal names, unit, trigger
  mode, CSV path, simulation flag, planned SCPI/configuration commands, read
  path, cleanup contract, and notes.
- Dry-run read-path coverage is implemented and tested for immediate `READ?`,
  external `FETC?`, and custom/buffered `DATA:POINts?` / `DATA:REMove?`.
- `--dry-run` and `--simulate` are rejected together.
- `--status-format jsonl` emits structured JSON Lines for `message`, `ready`,
  `status`, `sample`, `error`, `summary`, and `dry_run` events without changing
  acquisition behavior.
- `--dry-run --status-format jsonl` emits exactly one `dry_run` JSON object.
  Buffer-overflow warnings are included in `dry_run.notes` instead of separate
  JSONL events or plain text.
- Non-dry-run JSONL buffer-overflow warnings remain structured `status` events.
- Non-dry-run JSONL workers emit exactly one `ready` event after the local HTTP
  server starts and before the worker thread starts. Text-mode workers still
  print trigger, stop, and status endpoint URL lines without an added ready
  line.
- `--simulate` runs the normal acquisition engine against
  `SimulatedVisaInstrument` without PyVISA or a real instrument.
- Simple-mode simulation requires a finite bound such as `--max-samples` and
  fails validation without one.
- Simulation supports the bounded workflow paths used by tests, including
  immediate, software, software timer, immediate-custom, software-custom,
  external simple, and external-custom cases.
- Simulate JSONL success tests assert structured
  message/status/sample/summary events.
- Simulate JSONL failure tests cover representative read failure, malformed
  buffered read, CSV permission failure, and stop delivery while the normal
  software trigger queue is full.
- Simulate CSV smoke coverage writes through the real `CsvWriter` and verifies
  the documented CSV field order plus parseable trigger metadata.

Transport, simulator, and fake support:

- `VisaInstrument` supports an injected `resource_manager_factory`, including
  tests with PyVISA patched unavailable.
- Injected `VisaInstrument` still validates `*IDN?`, accepts only
  Keysight/Agilent 34461A identity strings, sends `*CLS`/`*RST` only after
  validation succeeds, and closes opened handles/resource managers on IDN
  validation or query failure.
- `TriggerAcquisitionEngine` accepts an internal `InstrumentBackend` in its
  constructor, so the real `VisaInstrument`, `SimulatedVisaInstrument`, and
  test fakes can be swapped at that layer.
- `SimulatedVisaInstrument` implements the subset of the `VisaInstrument`
  surface needed by acquisition, measurement plugins, trigger adapters, and
  cleanup paths: connect/write/query/query-as-float/status byte/timeouts,
  resource id, system error polling, abort, release-to-local, cleanup release,
  and close.
- Tests also use lightweight fakes in acquisition, measurement, trigger-router,
  and CLI harnesses. The start/acquisition path is now documented by the
  internal `InstrumentBackend` Protocol.

Intentionally not done yet / do not misread as complete:

- There is no universal `--json` flag. Long-running acquisition uses
  `--status-format jsonl`; single-response commands use `--format json`.
- There is no formal public instrument-driver interface. The project has an
  internal `InstrumentBackend` Protocol for the start/acquisition path only.
- Static discovery helpers `VisaInstrument.list_resources()` and
  `VisaInstrument.verify_resource()` still call PyVISA directly; they are
  intentionally outside the start/acquisition backend factory.
- There is no automatic instrument model detection or profile switching.
- There is only one active instrument profile: Keysight 34461A.
- Simulation is deterministic workflow validation only. It is not a 34461A
  accuracy model and does not validate measured values.
- Real-instrument validation for agent-support control-plane changes may be
  deferred when the change does not affect SCPI or acquisition behavior. The
  latest hardware pass has since covered USB acquisition, live discovery, AC
  real-signal sanity checks, and LAN basic wrapper validation.
- LAN discovery and the `basic` wrapper suite have passed from a second
  checkout/machine. LAN `external`/`full` remains optional if TCPIP external
  trigger behavior needs a separate recheck.
- `rule.md` is now historical acceptance criteria for this completed task, not
  an active implementation plan.

Future difficulty estimate:

- Low difficulty: add convenience aliases such as `--json` mapping to
  `--format json` or `--status-format jsonl`, and add dry-run previews for
  `soft-trigger` / `soft-stop` if desired.
- Medium difficulty: define a formal instrument protocol/interface and make
  resource discovery/verification injectable instead of static PyVISA calls.
- Medium difficulty: centralize real/simulated instrument selection behind a
  small factory while preserving the current cleanup and stop behavior.
- High difficulty: add true multi-instrument drivers, automatic `*IDN?` profile
  switching, model-specific SCPI differences, or a high-fidelity 34461A
  measurement simulator.

User documentation was updated in `docs/README_CLI_EN.md`. Automated validation
results are recorded in `Validation Status`.

## Current Capability Summary

The target instrument profile is Keysight 34461A.

Supported measurement types:

| CLI name | Internal type | CSV unit |
| --- | --- | --- |
| `current-dc` | `current_dc` | `A` |
| `voltage-dc` | `voltage_dc` | `V` |
| `current-ac` | `current_ac` | `A` |
| `voltage-ac` | `voltage_ac` | `V` |
| `resistance-2w` | `resistance_2w` | `Ohm` |
| `resistance-4w` | `resistance_4w` | `Ohm` |

Supported simple acquisition modes:

| Mode | Trigger source | Read path | Bound |
| --- | --- | --- | --- |
| `software` | HTTP `/trigger` | `READ?` | Optional `--max-samples` |
| `software --timer-interval-s` | PC-side timer | `READ?` | Optional `--max-samples` |
| `external` | External trigger edge | `FETC?` after arm/complete | Optional `--max-samples` |
| `immediate` | Worker loop | `READ?` | Optional `--max-samples` |

Supported custom/buffered acquisition modes:

| Mode | SCPI trigger source | Start/advance behavior | Drain path | Bound |
| --- | --- | --- | --- | --- |
| `immediate-custom` | `TRIG:SOUR IMM` | `INIT` starts the full sequence | `DATA:POINts?` / `DATA:REMove?` | `trigger_count * sample_count` |
| `software-custom` | `TRIG:SOUR BUS` | `INIT`, then each accepted HTTP `/trigger` sends `*TRG` | `DATA:POINts?` / `DATA:REMove?` | `trigger_count * sample_count` |
| `external-custom` | `TRIG:SOUR EXT` | `INIT`, then external edges advance the sequence | `DATA:POINts?` / `DATA:REMove?` | `trigger_count * sample_count` |

Important capability assumptions for the 34461A:

- Reading memory limit: 10,000 readings.
- Buffered reading memory is supported.
- Bus trigger is supported.
- External trigger is supported.
- Deterministic instrument sample timer mode is not treated as supported.
- Custom/buffered modes use reading memory and PC-side drain, not a true
  per-reading timestamp stream.

## Measurement And Range Rules

- `--measurement` defaults to `current-dc`.
- `--range VALUE` is the preferred generic manual range option.
- `--current-range VALUE` is retained only as a compatibility alias for
  `current-dc`.
- `--range VALUE` means:
  - amps for `current-dc` and `current-ac`;
  - volts for `voltage-dc` and `voltage-ac`;
  - ohms for `resistance-2w` and `resistance-4w`.
- `--current-range` is invalid with `current-ac`, `voltage-dc`, `voltage-ac`,
  `resistance-2w`, and `resistance-4w`.
- For `current-dc`, `--range` and `--current-range` must not be used together.
- With `--auto-range off`, all currently supported measurements require a
  manual range.
- With `--auto-range on`, manual range remains optional and Auto Range takes
  priority.
- For `current-ac` and `voltage-ac`, the shared CLI still accepts `--nplc` and
  `--auto-zero`, but AC measurement configuration does not write NPLC or Auto
  Zero SCPI.
- `--dcv-input-impedance` is valid only with `--measurement voltage-dc`.
  - `default`: do not write any Input Z SCPI.
  - `10m`: write `VOLT:DC:IMP:AUTO OFF` for fixed 10 MOhm.
  - `auto`: write `VOLT:DC:IMP:AUTO ON`; the 34461A front panel may show HighZ
    on lower DC voltage ranges while Auto is active.

## SCPI Mapping

Current DC:

```text
CONF:CURR:DC AUTO
CURR:DC:RANG:AUTO ON
or CURR:DC:RANG <range>
CURR:DC:NPLC <nplc>
ZERO:AUTO ON|OFF
```

Voltage DC:

```text
CONF:VOLT:DC AUTO
VOLT:DC:RANG:AUTO ON
or VOLT:DC:RANG <range>
optional VOLT:DC:IMP:AUTO OFF|ON
VOLT:DC:NPLC <nplc>
VOLT:DC:ZERO:AUTO ON|OFF
```

Current AC:

```text
CONF:CURR:AC AUTO
CURR:AC:RANG:AUTO ON
or CURR:AC:RANG <range>
```

Voltage AC:

```text
CONF:VOLT:AC AUTO
VOLT:AC:RANG:AUTO ON
or VOLT:AC:RANG <range>
```

Resistance 2-wire:

```text
CONF:RES AUTO
RES:RANG:AUTO ON
or RES:RANG <range>
RES:NPLC <nplc>
RES:ZERO:AUTO ON|OFF
```

Resistance 4-wire:

```text
CONF:FRES AUTO
FRES:RANG:AUTO ON
or FRES:RANG <range>
FRES:NPLC <nplc>
```

Do not send `FRES:ZERO:AUTO`; the 34461A handles 4-wire resistance Auto Zero
internally, and real-instrument testing showed a front-panel remote-command
error when this was written.

AC current and AC voltage do not currently expose AC bandwidth/filter controls.
Do not write AC NPLC or Auto Zero commands unless the feature scope changes and
real-instrument behavior is confirmed.

AC bandwidth/filter support is intentionally deferred. It controls the AC
frequency/filter behavior and can affect low-frequency accuracy, settling time,
reading speed, and noise. Keep the current AC implementation on instrument
defaults until real-instrument testing shows a need for explicit AC bandwidth or
filter selection. If added later, first confirm the 34461A SCPI command names,
CLI naming, valid values, and behavior on real AC voltage/current signals.

Other measurement features intentionally excluded from the v1 CLI baseline:

- Resistance offset compensation: not implemented for this 34461A-focused CLI
  baseline. User did not see this setting on the 34461A front panel; do not add
  without confirming model support and real-instrument behavior.
- Auto Zero `once`: not implemented. The CLI supports only `on|off`; do not add
  `ONCE` without explicit scope and real-instrument validation.
- Null/relative: not implemented as instrument NULL state. If needed later,
  prefer software-side relative/offset handling first so raw measured values can
  remain available.

Read path policy:

- Simple software, timer, and immediate modes use `READ?`.
- Simple external hardware mode uses `FETC?` after the trigger adapter arms and
  completes measurement.
- Custom/buffered modes use `INIT`, trigger-specific advancement, and
  `DATA:POINts?` / `DATA:REMove?`.

Console status policy:

- Simple software mode prints `waiting trigger` once per continuous wait period
  instead of repeating it on every short poll timeout.
- `software-custom` mode prints `waiting software custom trigger` once per
  continuous wait period instead of repeating it on every short poll timeout.
- Capture status prints `captured=<N>` plus the latest measured value using a
  display-only engineering prefix such as `mA`, `mV`, `kOhm`, or `MOhm`.
- CSV output remains unchanged: values are still stored in the measurement's
  base unit (`A`, `V`, or `Ohm`).
- Custom/buffered mode can drain multiple samples at once; its capture status
  reports the last sample in that drain batch.

## Stop And Cleanup Contract

Preserve this shutdown design unless the user explicitly approves a change:

1. `engine.stop()` only sets stop state and stop events.
2. VISA I/O stays on the worker or cleanup path.
3. Cleanup order remains:
   - wait for worker;
   - `release_to_local`;
   - close;
   - cleanup release;
   - stop HTTP server.

All modes should continue supporting graceful stop:

- `soft-stop`
- Ctrl+C
- Ctrl+Break
- `q`

Mode-specific trigger handling:

- Timer mode ignores ordinary `soft-trigger` while honoring `soft-stop`.
- Immediate mode ignores ordinary `soft-trigger`.
- External simple mode ignores accidental software triggers.
- `external-custom` ignores ordinary HTTP `soft-trigger`; external edges are
  the only acquisition trigger. `soft-stop` still stops.
- Hardware trigger timeout in simple external mode is a protective re-arm
  condition, not a capture error by itself.
- In simple external mode, repeated PyVISA status-byte poll timeouts are
  nonfatal diagnostics: count 5 emits a warning, count 25 and every additional
  25 consecutive timeouts increment `errors` and emit degraded status, and any
  successful status-byte poll resets the count. Actual `READ?`, `FETC?`,
  connection, identity, or SCPI command failures should remain acquisition
  errors and may be fatal.
- `--trigger-timeout-ms` defaults to 10000 ms and is primarily an external
  trigger protective wait/re-arm setting. Very small manual values can also
  affect shared software wait/poll cadence, but no CLI/backend behavior change
  is planned because the default is safe for normal software-trigger use.
- `TriggerRouter` stop/control events are intentionally kept off the normal
  bounded trigger queue so stop delivery cannot be blocked by queued trigger
  pressure.

## Timestamp Policy

- CSV `timestamp_utc_plus_8` is user-facing and uses UTC+8.
- Default CSV filenames also use UTC+8 and are formatted as
  `data/YYYY-MM-DD-HH-MM-SS.csv` when `--csv` is omitted.
- Internal simple-mode sample timestamps remain UTC.
- Custom metadata `fetch_time_utc` remains UTC PC drain/fetch time.
- Custom/buffered CSV time is not exact instrument ADC/integration completion
  time.
- Custom/buffered metadata must include:
  `time_basis=pc_data_remove_time_not_instrument_sample_time`.

## High-Risk Areas

This project controls a real Keysight 34461A through VISA/SCPI. Do not change
these without explicit user confirmation:

- SCPI behavior for current, voltage, or resistance.
- VISA timeout.
- Trigger wait strategy.
- `TRIG:DEL`.
- NPLC.
- Auto Zero.
- Auto Range.
- VM Comp.
- stop/release/local behavior.
- Repeated `*OPC?` polling.

## Validation Status

Latest automated validation for the 2026-05-25 docs and hardware-test
readiness review:

```powershell
uv pip install -e ".[dev]"
# installed editable keysight-logger 1.1.6 and generated the console script

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packages\cli\scripts\preflight-cli.ps1 -Target keysight-34461a
# preflight passed: keysight-34461a

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packages\cli\scripts\live-cli-check.ps1 -Target keysight-34461a -Connection usb -Resource SIM::34461A -Suite minimal -PlanOnly
# live CLI plan generated: minimal

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packages\cli\scripts\live-cli-check.ps1 -Target keysight-34461a -Connection usb -Resource SIM::34461A -Suite full -PlanOnly
# live CLI plan generated: full

.\.venv\Scripts\keysight-logger.exe list-resources --dry-run --json
# exits 0 and reports dry_run_performs_visa_io=false

.\.venv\Scripts\python.exe -m pytest tests/test_docs_cli_examples.py packages/cli/tests/test_cli_package_metadata.py tests/test_cli_wrappers.py -q -p no:cacheprovider
# 8 passed in 39.42s

.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
# 280 passed, 61 subtests passed in 47.40s

rg -n "StartCommandPlan|print_buffer_overflow_warnings|measurement_cli_name|argparse|argparse\.Namespace|status_format|enable_hw_trigger|exit_code|rc=" packages\core\src\keysight_logger_core\core
# no matches

rg -n "Get-Random -Minimum 20000|Get-Random -Maximum|Get-Random" scripts\preflight-cli.ps1 scripts\live-cli-check.ps1
# no matches

git diff --check
# no whitespace errors; only existing LF-to-CRLF working-copy warnings
```

Direct `.\packages\cli\scripts\preflight-cli.ps1 ...` was blocked on this machine by
PowerShell execution policy, so active documentation now uses the explicit
`powershell.exe -NoProfile -ExecutionPolicy Bypass -File ...` form.

No live instrument validation was run for this docs/wrapper readiness pass
because it only changes no-hardware wrapper port selection and documentation.

User-reported no-hardware acceptance after the docs/wrapper readiness update:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packages\cli\scripts\preflight-cli.ps1 -Target keysight-34461a
# preflight passed: keysight-34461a

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packages\cli\scripts\live-cli-check.ps1 -Target keysight-34461a -Connection usb -Resource SIM::34461A -Suite minimal -PlanOnly
# live CLI plan generated: minimal

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packages\cli\scripts\live-cli-check.ps1 -Target keysight-34461a -Connection usb -Resource SIM::34461A -Suite full -PlanOnly
# live CLI plan generated: full

.\.venv\Scripts\keysight-logger.exe list-resources --dry-run --json
# exits 0 and reports dry_run_performs_visa_io=false

.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
# 280 passed, 61 subtests passed in 47.82s
```

This completed the documented no-hardware acceptance path before the later
real-instrument wrapper and manual smoke runs recorded below.

User-reported real-instrument minimal live smoke after no-hardware acceptance:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packages\cli\scripts\live-cli-check.ps1 -Target keysight-34461a -Connection usb -Resource "USB0::0x2A8D::0x1301::MY60045220::0::INSTR" -Suite minimal
# status: passed
# case: minimal_current_dc_immediate
# captured=1 errors=0 csv_rows=1
# report: .tmp_tests\cli_live\keysight-34461a\usb\minimal\20260525-190922\report.json
```

This confirms the lowest-risk real-instrument current DC immediate path after
the Core/CLI boundary cleanup and wrapper readiness updates. Later entries in
this section record the completed `basic` and `external` suites.

User-reported real-instrument basic live suite after minimal smoke:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packages\cli\scripts\live-cli-check.ps1 -Target keysight-34461a -Connection usb -Resource "USB0::0x2A8D::0x1301::MY60045220::0::INSTR" -Suite basic
# status: passed
# cases passed: 10/10
# each case captured=1 errors=0 csv_rows=1
# report: .tmp_tests\cli_live\keysight-34461a\usb\basic\20260525-191123\report.json
```

Covered live cases: immediate one-sample captures for `current-dc`,
`voltage-dc`, `current-ac`, `voltage-ac`, `resistance-2w`, and
`resistance-4w`; current DC software trigger; current DC software timer;
current DC immediate-custom buffered capture; and current DC software-custom
buffered capture. The following entry records the completed external trigger
suite.

User-reported real-instrument external trigger suite after basic live suite:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packages\cli\scripts\live-cli-check.ps1 -Target keysight-34461a -Connection usb -Resource "USB0::0x2A8D::0x1301::MY60045220::0::INSTR" -Suite external
# status: passed
# cases passed: 2/2
# external_simple: read_path=FETC?, captured=1 errors=0 csv_rows=1
# external_custom: read_path=DATA:POINts? / DATA:REMove?, captured=1 errors=0 csv_rows=1
# report: .tmp_tests\cli_live\keysight-34461a\usb\external\20260525-191344\report.json
```

This completes the documented wrapper-level live validation for USB on the
current implementation: no-hardware acceptance, minimal, basic, and external
all passed after the Core/CLI boundary cleanup and wrapper readiness updates.
Later entries also record ACI/ACV real-signal sanity checks and LAN `basic`
wrapper validation from a second checkout/machine.

User-reported repeat real-instrument wrapper-level live validation with the
same explicit USB VISA resource:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packages\cli\scripts\live-cli-check.ps1 -Target keysight-34461a -Connection usb -Resource "USB0::0x2A8D::0x1301::MY60045220::0::INSTR" -Suite basic
# status: passed
# cases passed: 10/10
# each case captured=1 errors=0 csv_rows=1
# report: .tmp_tests\cli_live\keysight-34461a\usb\basic\20260525-191900\report.json

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packages\cli\scripts\live-cli-check.ps1 -Target keysight-34461a -Connection usb -Resource "USB0::0x2A8D::0x1301::MY60045220::0::INSTR" -Suite external
# status: passed
# cases passed: 2/2
# external_simple: read_path=FETC?, captured=1 errors=0 csv_rows=1
# external_custom: read_path=DATA:POINts? / DATA:REMove?, captured=1 errors=0 csv_rows=1
# report: .tmp_tests\cli_live\keysight-34461a\usb\external\20260525-192047\report.json
```

This repeat pass supersedes the accidental literal `-Resource "<RESOURCE>"`
attempt, which failed before opening a valid VISA session with
`VI_ERROR_INV_RSRC_NAME`.

User-reported manual real-instrument option smoke with the same explicit USB
VISA resource:

```powershell
$RESOURCE = "USB0::0x2A8D::0x1301::MY60045220::0::INSTR"

.\.venv\Scripts\keysight-logger.exe start-trigger-record --resource $RESOURCE --csv ".tmp_tests\manual_live\dcv_input_auto.csv" --trigger-mode immediate --measurement voltage-dc --max-samples 1 --dcv-input-impedance auto --status-format jsonl
# captured=1 errors=0 value=-0.00835050197 V

.\.venv\Scripts\keysight-logger.exe start-trigger-record --resource $RESOURCE --csv ".tmp_tests\manual_live\dcv_input_10m.csv" --trigger-mode immediate --measurement voltage-dc --max-samples 1 --dcv-input-impedance 10m --status-format jsonl
# captured=1 errors=0 value=-0.000197088374 V

.\.venv\Scripts\keysight-logger.exe start-trigger-record --resource $RESOURCE --csv ".tmp_tests\manual_live\current_dc_manual_range.csv" --trigger-mode immediate --measurement current-dc --auto-range off --range 0.001 --max-samples 1 --status-format jsonl
# captured=1 errors=0 value=2.19152184e-09 A

.\.venv\Scripts\keysight-logger.exe start-trigger-record --resource $RESOURCE --csv ".tmp_tests\manual_live\current_ac_manual_range.csv" --trigger-mode immediate --measurement current-ac --auto-range off --range 0.1 --max-samples 1 --status-format jsonl
# captured=1 errors=0 value=0.0 A

.\.venv\Scripts\keysight-logger.exe start-trigger-record --resource $RESOURCE --csv ".tmp_tests\manual_live\voltage_ac_manual_range.csv" --trigger-mode immediate --measurement voltage-ac --auto-range off --range 10 --max-samples 1 --status-format jsonl
# captured=1 errors=0 value=0.0 V

.\.venv\Scripts\keysight-logger.exe start-trigger-record --resource $RESOURCE --csv ".tmp_tests\manual_live\resistance_2w_manual_range.csv" --trigger-mode immediate --measurement resistance-2w --auto-range off --range 1000 --max-samples 1 --status-format jsonl
# captured=1 errors=0 value=9.9e+37 Ohm

.\.venv\Scripts\keysight-logger.exe start-trigger-record --resource $RESOURCE --csv ".tmp_tests\manual_live\resistance_4w_manual_range.csv" --trigger-mode immediate --measurement resistance-4w --auto-range off --range 1000 --max-samples 1 --status-format jsonl
# captured=1 errors=0 value=9.9e+37 Ohm
```

These manual smokes confirm the immediate read path accepts and executes DCV
input impedance selection and representative manual ranges for current, AC
voltage/current, and 2W/4W resistance. The `9.9e+37 Ohm` resistance values are
the instrument's open/overload-style reading in this setup, so this validates
command execution and cleanup, not resistor accuracy.

User-reported manual real-instrument VM Comp and software-trigger smokes:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record --resource $RESOURCE --csv ".tmp_tests\manual_live\vm_comp_pos.csv" --trigger-mode immediate --measurement current-dc --max-samples 1 --vm-comp-slope pos --status-format jsonl
# captured=1 errors=0 value=-8.03451092e-11 A

.\.venv\Scripts\keysight-logger.exe start-trigger-record --resource $RESOURCE --csv ".tmp_tests\manual_live\vm_comp_neg.csv" --trigger-mode immediate --measurement current-dc --max-samples 1 --vm-comp-slope neg --status-format jsonl
# captured=1 errors=0 value=-2.1887116e-09 A

.\.venv\Scripts\keysight-logger.exe start-trigger-record --resource $RESOURCE --csv ".tmp_tests\manual_live\voltage_dc_software.csv" --trigger-mode software --measurement voltage-dc --max-samples 1 --sw-trigger-port 8765 --status-format jsonl
# emitted waiting trigger, then captured=1 errors=0 value=4.3380296e-05 V

.\.venv\Scripts\keysight-logger.exe soft-trigger --port 8765 --format json
# {"event": "soft-trigger", "http_status": 202, "status": "accepted", ...}
```

The software-trigger timestamp precedes the `voltage_dc` sample timestamp, so
this confirms the manual software trigger endpoint accepted a trigger and the
recording worker completed one sample. VM Comp positive/negative slope smoke
confirms command execution and cleanup on the current DC immediate path; it
does not validate source/sink threshold accuracy.

User-reported manual real-instrument timer and buffered custom smokes:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record --resource $RESOURCE --csv ".tmp_tests\manual_live\resistance_2w_timer.csv" --trigger-mode software --timer-interval-s 0.5 --measurement resistance-2w --max-samples 1 --status-format jsonl
# software timer enabled interval_s=0.5
# captured=1 errors=0 trigger_source=timer value=9.9e+37 Ohm

.\.venv\Scripts\keysight-logger.exe start-trigger-record --resource $RESOURCE --csv ".tmp_tests\manual_live\voltage_ac_immediate_custom.csv" --trigger-mode immediate-custom --measurement voltage-ac --trigger-count 1 --sample-count 1 --status-format jsonl
# immediate custom capture configured trigger_count=1 sample_count=1 expected_readings=1
# immediate custom capture started
# captured=1 errors=0 trigger_source=immediate-custom value=0.000227074332 V
# trigger_metadata includes buffered=true, buffer_batch_size=1, buffer_index=0,
# expected_readings=1, trigger_count=1, sample_count=1, and
# time_basis=pc_data_remove_time_not_instrument_sample_time

.\.venv\Scripts\keysight-logger.exe start-trigger-record --resource $RESOURCE --csv ".tmp_tests\manual_live\resistance_4w_software_custom.csv" --trigger-mode software-custom --measurement resistance-4w --trigger-count 1 --sample-count 1 --sw-trigger-port 8765 --status-format jsonl
# software custom capture configured trigger_count=1 sample_count=1 expected_readings=1
# software custom capture armed
# waiting software custom trigger
# software custom trigger sent=1/1
# captured=1 errors=0 trigger_source=software-custom value=-406195.597 Ohm

.\.venv\Scripts\keysight-logger.exe soft-trigger --port 8765 --format json
# {"event": "soft-trigger", "http_status": 202, "status": "accepted", ...}
```

The software-custom `soft-trigger` timestamp aligns with the
`software custom trigger sent=1/1` status timestamp and precedes the buffered
sample timestamp, confirming the HTTP trigger drove the one-reading custom
sequence. Resistance readings in this manual setup are treated as connectivity
and command-path evidence, not accuracy evidence.

User-reported manual real-instrument external trigger smokes:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record --resource $RESOURCE --csv ".tmp_tests\manual_live\voltage_dc_external.csv" --trigger-mode external --measurement voltage-dc --max-samples 1 --trigger-timeout-ms 10000 --status-format jsonl
# hardware trigger configured slope=NEG delay_s=0.0
# captured=1 errors=0 trigger_source=hardware value=1.51554022e-05 V

.\.venv\Scripts\keysight-logger.exe start-trigger-record --resource $RESOURCE --csv ".tmp_tests\manual_live\resistance_2w_external_custom.csv" --trigger-mode external-custom --measurement resistance-2w --trigger-count 1 --sample-count 1 --trigger-timeout-ms 10000 --status-format jsonl
# external custom capture configured trigger_count=1 sample_count=1 expected_readings=1 slope=NEG delay_s=0.0
# external custom capture armed
# captured=1 errors=0 trigger_source=external-custom value=9.9e+37 Ohm
# trigger_metadata includes buffered=true, buffer_batch_size=1, buffer_index=0,
# expected_readings=1, trigger_count=1, sample_count=1, and
# time_basis=pc_data_remove_time_not_instrument_sample_time
```

This confirms manual simple external and external-custom trigger paths on USB
with a 10 s trigger timeout. The simple external sample used
`trigger_source=hardware`; the external-custom sample used the buffered
`DATA:POINts?` / `DATA:REMove?` path metadata. The resistance value is again
treated as open/overload setup evidence, not accuracy evidence.

User-reported manual no-hardware sanity smokes:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record --resource "<RESOURCE>" --trigger-mode immediate --measurement current-dc --max-samples 1 --dry-run --status-format jsonl
# event=dry_run
# measurement_cli_name=current-dc
# measurement_type=current_dc
# read_path=READ?
# cleanup_steps=["wait for worker", "release_to_local", "close", "cleanup_release_to_local", "stop_http_server"]
# scpi_commands include CONF:CURR:DC AUTO, CURR:DC:RANG:AUTO ON, CURR:DC:NPLC 1.0, ZERO:AUTO ON

.\.venv\Scripts\keysight-logger.exe start-trigger-record --resource "SIM::34461A" --csv ".tmp_tests\manual_simulate.csv" --trigger-mode immediate --measurement current-dc --max-samples 1 --simulate --status-format jsonl
# captured=1 errors=0 value=1.23 A
# cleanup used simulated_release_to_local and simulated_cleanup_release_to_local
```

The dry-run JSONL output intentionally still exposes `measurement_cli_name` as
a stable CLI JSON compatibility field, while Core code should prefer
`MeasurementDefinition.canonical_name` internally.

User-reported focused no-hardware CLI args regression:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cli_args.py -q -p no:cacheprovider -k list_resources
# 18 passed, 67 deselected in 0.09s
```

User-reported live discovery and cleanup validation:

```powershell
.\.venv\Scripts\keysight-logger.exe list-resources --verify --json
# verify=true
# live: USB0::0x2A8D::0x1102::MY61007667::0::INSTR
#       Keysight Technologies,E36312A,MY61007667,2.1.3-1.0.4-1.14
# live: USB0::0x2A8D::0x1301::MY60045220::0::INSTR
#       Keysight Technologies,34461A,MY60045220,A.03.03-03.15-03.03-00.52-04-03
# stale cached USB/TCPIP entries were reported with VISA errors, as expected.

.\.venv\Scripts\keysight-logger.exe list-resources --live-only --json
# verify=true live_only=true
# resources contains only the live E36312A and target 34461A entries.
```

This completes the hardware-test-plan live discovery checks for the USB setup:
`--verify` marks the target 34461A resource live, `--live-only` filters stale
cached entries, and live discovery did not report acquisition-path errors.

User-reported ACI real-signal value sanity check:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record --resource $RESOURCE --csv ".tmp_tests\manual_live\aci_known_signal.csv" --trigger-mode immediate --measurement current-ac --auto-range on --max-samples 3 --status-format jsonl
# captured=3 errors=0
# values: 0.00031616692 A, 0.000316642121 A, 0.000316152841 A
# user confirmed the CLI values were consistent with the instrument front panel.
```

This closes the minimum real AC signal sanity check for AC current on the USB
34461A path.

User-reported ACV real-signal value sanity check:

```powershell
.\.venv\Scripts\keysight-logger.exe start-trigger-record --resource $RESOURCE --csv ".tmp_tests\manual_live\acv_known_signal.csv" --trigger-mode immediate --measurement voltage-ac --auto-range on --max-samples 3 --status-format jsonl
# captured=3 errors=0
# values: 0.000290654429 V, 0.000271814317 V, 0.000283870149 V
# user confirmed the CLI values were consistent with the instrument front panel.
```

This closes the minimum real AC signal sanity check for AC voltage on the USB
34461A path.

User-reported LAN/network-path validation from a second checkout/machine
(`D:\Tom\Keysight_Meters`):

```powershell
.\.venv\Scripts\keysight-logger.exe list-resources --verify --json
# verify=true
# live: TCPIP0::169.254.4.61::inst0::INSTR
#       Keysight Technologies,34461A,MY60045220,A.03.03-03.15-03.03-00.52-04-03
# stale cached TCPIP/USB entries were reported with VISA errors.

.\.venv\Scripts\keysight-logger.exe list-resources --live-only --json
# verify=true live_only=true
# resources contains only TCPIP0::169.254.4.61::inst0::INSTR.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packages\cli\scripts\live-cli-check.ps1 -Target keysight-34461a -Connection lan -Resource "TCPIP0::169.254.4.61::inst0::INSTR" -Suite basic
# status: passed
# cases passed: 10/10
# each case captured=1 errors=0 csv_rows=1
# summary: D:\Tom\Keysight_Meters\.tmp_tests\cli_live\keysight-34461a\lan\basic\20260525-202614\summary.md
```

This confirms the LAN/TCPIP transport path for live discovery and the full
`basic` wrapper suite. LAN `external`/`full` remains optional if external
trigger behavior specifically needs to be rechecked over TCPIP.

Previous local version/package validation for the `v1.1.7-cli`
baseline:

```powershell
uv pip install -e ".[dev]" --link-mode=copy
# Uninstalled keysight-logger==1.1.6 and installed keysight-logger==1.1.7.

.\.venv\Scripts\keysight-logger.exe --version
# keysight-logger 1.1.7

.\.venv\Scripts\python.exe -m pytest tests/test_docs_cli_examples.py packages/cli/tests/test_cli_package_metadata.py -q -p no:cacheprovider
# 3 passed

.\.venv\Scripts\python.exe -m pytest tests/test_cli_args.py -q -p no:cacheprovider -k version
# 2 passed, 83 deselected
```

Latest automated validation for the 2026-05-25 Core/CLI boundary cleanup:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_core_validation.py tests/test_measurement.py tests/test_core_run_plan.py tests/test_core_public_api.py tests/test_cli_args.py -q -p no:cacheprovider
# 179 passed, 56 subtests passed in 1.74s

.\.venv\Scripts\python.exe -m pytest tests/test_docs_cli_examples.py packages/cli/tests/test_cli_package_metadata.py -q -p no:cacheprovider
# 3 passed in 0.07s

rg -n "validate_client_port\([^,\n]+," src tests
# no matches

rg -n "definition\.cli_name|cli_name=" packages\core\src\keysight_logger_core\core
# no matches

.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
# first run: 279 passed, 61 subtests passed; one transient Windows loopback
# ConnectionAbortedError in
# tests/test_software_trigger_adapter.py::SoftwareTriggerAdapterTests::test_stop_endpoint_publishes_control_event

.\.venv\Scripts\python.exe -m pytest tests/test_software_trigger_adapter.py::SoftwareTriggerAdapterTests::test_stop_endpoint_publishes_control_event -q -p no:cacheprovider
# 1 passed in 0.58s

.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
# 280 passed, 61 subtests passed in 46.84s

git diff --check
# no whitespace errors; only existing LF-to-CRLF working-copy warnings
```

No live instrument validation was run for this pass because it does not alter
SCPI, VISA timeout behavior, trigger wait strategy, acquisition behavior, stop
flow, release/local behavior, cleanup order, NPLC, Auto Range/Zero, or VM Comp
behavior.

Latest automated validation for the 2026-05-25 Core validation timezone and
WebUI integration docs pass:

```powershell
rg -n "from \.storage|import .*storage" packages\core\src\keysight_logger_core\validation.py
# no matches

rg -n "UTC_PLUS_8" packages\core\src\keysight_logger_core\core
# packages\core\src\keysight_logger_core\constants.py definition plus validation.py/storage.py imports/usages only

.\.venv\Scripts\python.exe -m pytest tests/test_core_validation.py tests/test_csv_writer.py tests/test_core_public_api.py -q -p no:cacheprovider
# 23 passed, 44 subtests passed in 0.09s

.\.venv\Scripts\python.exe -m pytest tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py tests/test_cli_args.py -q -p no:cacheprovider
# 115 passed, 54 subtests passed in 1.36s

.\.venv\Scripts\python.exe -m pytest tests/test_docs_cli_examples.py packages/cli/tests/test_cli_package_metadata.py -q -p no:cacheprovider
# 3 passed in 0.08s

.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
# 278 passed, 59 subtests passed in 47.34s

git diff --check
# no whitespace errors; Git reported LF-to-CRLF working-copy warnings for touched files
```

Live instrument validation was not run for this boundary/docs pass because it
does not alter CLI JSON schema, SCPI, VISA timeout, trigger wait strategy,
measurement logic, stop flow, cleanup order, release/local behavior, NPLC,
Auto Range/Zero, or VM Comp behavior.

Latest automated validation for the 2026-05-25 WebUI integration guide
follow-up:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_docs_cli_examples.py packages/cli/tests/test_cli_package_metadata.py -q -p no:cacheprovider
# 3 passed in 0.06s

git diff --check
# no whitespace errors; Git reported LF-to-CRLF working-copy warnings for touched files
```

Live instrument validation is not required for this documentation-only pass.

Latest automated validation for the 2026-05-25 public Core API export pass:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_core_public_api.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py tests/test_cli_args.py -q -p no:cacheprovider
# 118 passed, 54 subtests passed in 1.56s

.\.venv\Scripts\python.exe -m pytest tests/test_cli_wrappers.py tests/test_docs_cli_examples.py packages/cli/tests/test_cli_package_metadata.py -q -p no:cacheprovider
# 8 passed in 38.18s

.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
# 277 passed, 59 subtests passed in 46.66s

rg -n "StartCommandPlan|print_buffer_overflow_warnings" src
# no matches

git diff --check
# no whitespace errors; Git reported LF-to-CRLF working-copy warnings for touched text files
```

Live instrument validation was not run for this public import/export boundary
pass because it does not alter CLI JSON schema, SCPI, VISA timeout, trigger
wait strategy, measurement logic, stop flow, cleanup order, release/local
behavior, NPLC, Auto Range/Zero, or VM Comp behavior.

Latest automated validation for the 2026-05-25 Web-ready start runner
boundary naming pass:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_core_validation.py tests/test_core_run_plan.py tests/test_cli_args.py -q -p no:cacheprovider
# 110 passed, 54 subtests passed in 2.08s

.\.venv\Scripts\python.exe -m pytest tests/test_cli_wrappers.py tests/test_docs_cli_examples.py packages/cli/tests/test_cli_package_metadata.py -q -p no:cacheprovider
# 8 passed in 39.33s

.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
# 273 passed, 59 subtests passed in 46.93s

rg -n "print_buffer_overflow_warnings|StartCommandPlan|measurement_cli_name|argparse|argparse\.Namespace|status_format|enable_hw_trigger|exit_code|rc=" packages\core\src\keysight_logger_core\core
# no matches

git diff --check
# no whitespace errors; only LF-to-CRLF working-copy warnings
```

Live instrument validation was not run because this pass is Core/CLI boundary
naming only and does not change instrument I/O behavior.

Latest automated validation for the 2026-05-25 Web-ready start runner
isolation pass:

```powershell
rg -n "argparse|argparse\.Namespace|status_format|enable_hw_trigger|exit_code|rc=" packages\core\src\keysight_logger_core\core
# no matches

.\.venv\Scripts\python.exe -m pytest tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py tests/test_software_trigger_adapter.py -q -p no:cacheprovider
# 38 passed, 44 subtests passed in 5.09s

.\.venv\Scripts\python.exe -m pytest tests/test_cli_args.py tests/test_acquisition_engine.py tests/test_software_trigger_adapter.py -q -p no:cacheprovider
# 124 passed, 10 subtests passed in 8.60s

.\.venv\Scripts\python.exe -m pytest tests/test_cli_wrappers.py tests/test_docs_cli_examples.py packages/cli/tests/test_cli_package_metadata.py -q -p no:cacheprovider
# 8 passed in 46.35s

.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
# 273 passed, 59 subtests passed in 54.57s

.\packages\cli\scripts\preflight-cli.ps1 -Target keysight-34461a
# preflight passed: keysight-34461a
# summary: E:\Git\Keysight\.tmp_tests\cli_preflight\keysight-34461a\summary.md

git diff --check
# no whitespace errors; only LF-to-CRLF working-copy warnings
```

At the time of this runtime/API isolation pass, full basic live validation was
pending a user-provided `-Connection` and complete `-Resource`. Later
2026-05-25 entries above record completed USB basic/external validation and LAN
basic validation. This pass itself did not change SCPI command sequences, VISA
timeout behavior, trigger wait strategy, measurement logic, stop flow, cleanup
order, Auto Range, Auto Zero, NPLC, VM Comp, VM Comp slope behavior, or
release/local behavior.

Latest automated validation for the 2026-05-24 CLI wrapper artifact contract
and live PlanOnly pass:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cli_wrappers.py -q -p no:cacheprovider
# 5 passed in 64.02s

.\.venv\Scripts\python.exe -m pytest tests/test_cli_wrappers.py tests/test_docs_cli_examples.py tests/test_cli_args.py -q -p no:cacheprovider
# 89 passed, 10 subtests passed in 65.98s

.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
# 266 passed, 59 subtests passed in 71.41s

.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
# Ran 257 tests in 8.287s, OK

.\packages\cli\scripts\preflight-cli.ps1 -Target keysight-34461a
# preflight passed: keysight-34461a
# summary: E:\Git\Keysight\.tmp_tests\cli_preflight\keysight-34461a\summary.md

.\packages\cli\scripts\live-cli-check.ps1 -Target keysight-34461a -Connection usb -Resource SIM::34461A -Suite minimal -PlanOnly
# status planned; plan_only=true; live_executed=false
# summary: E:\Git\Keysight\.tmp_tests\cli_live\keysight-34461a\usb\minimal\20260524-152319\summary.md

.\packages\cli\scripts\live-cli-check.ps1 -Target keysight-34461a -Connection usb -Resource SIM::34461A -Suite full -PlanOnly
# status planned; plan_only=true; live_executed=false
# summary: E:\Git\Keysight\.tmp_tests\cli_live\keysight-34461a\usb\full\20260524-152340\summary.md

'' | .\packages\cli\scripts\live-cli-check.ps1 -Target keysight-34461a -Connection usb -Resource SIM::34461A -Suite minimal
# nonzero as expected; status confirmation_required; plan_only=false; live_executed=false
# summary: E:\Git\Keysight\.tmp_tests\cli_live\keysight-34461a\usb\minimal\20260524-153801\summary.md
```

This pass adds `live-cli-check.ps1 -PlanOnly`, pytest coverage for wrapper
artifact contracts, and documentation for `planned` /
`confirmation_required` live report states. It does not change SCPI command
sequences, VISA timeout behavior, trigger wait strategy, measurement logic,
stop flow, cleanup order, Auto Range, Auto Zero, NPLC, VM Comp, or
release/local behavior. No live acquisition was run.

Latest automated validation for the 2026-05-24 program-boundary baseline:

```powershell
rg -n "argparse|argparse\.Namespace|status_format" packages\core\src\keysight_logger_core\validation.py packages\core\src\keysight_logger_core\run_plan.py
# no matches

.\.venv\Scripts\python.exe -m pytest tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py -q -p no:cacheprovider
# 28 passed, 44 subtests passed in 0.26s

.\.venv\Scripts\python.exe -m pytest tests/test_cli_args.py tests/test_acquisition_engine.py tests/test_software_trigger_adapter.py -q -p no:cacheprovider
# 122 passed, 10 subtests passed in 8.97s

.\.venv\Scripts\python.exe -m pytest tests/test_cli_wrappers.py tests/test_docs_cli_examples.py packages/cli/tests/test_cli_package_metadata.py -q -p no:cacheprovider
# 8 passed in 47.47s

.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
# 270 passed, 59 subtests passed in 58.85s

.\packages\cli\scripts\preflight-cli.ps1 -Target keysight-34461a
# preflight passed: keysight-34461a
# summary: E:\Git\Keysight\.tmp_tests\cli_preflight\keysight-34461a\summary.md

git diff --check
# no whitespace errors; only LF-to-CRLF working-copy warnings
```

Live acquisition was not run for this program-boundary baseline because it does
not alter SCPI command sequences, VISA timeout behavior, trigger wait strategy,
measurement logic, stop flow, cleanup order, Auto Range, Auto Zero, NPLC, VM
Comp, VM Comp slope behavior, or release/local behavior.

Latest automated validation for the 2026-05-24 redirected-stdin wrapper CI fix:

```powershell
$tokens=$null; $errors=$null; [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path .\packages\cli\scripts\live-cli-check.ps1), [ref]$tokens, [ref]$errors); $errors.Count
# 0

.\.venv\Scripts\python.exe -m pytest tests/test_cli_wrappers.py::test_live_redirected_stdin_writes_confirmation_required_report -q -p no:cacheprovider
# 1 passed in 0.70s

.\.venv\Scripts\python.exe -m pytest tests/test_cli_wrappers.py -q -p no:cacheprovider
# 5 passed in 49.41s

.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
# 266 passed, 59 subtests passed in 56.32s

.\.venv\Scripts\python.exe -m pytest tests/test_docs_cli_examples.py -q -p no:cacheprovider
# 2 passed in 0.01s

git diff --check
# no whitespace errors; only LF-to-CRLF working-copy warnings
```

No live acquisition was run for this CI fix.

Latest automated validation for the 2026-05-24 CLI/Core test-boundary cleanup:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_core_validation.py tests/test_core_run_plan.py -q -p no:cacheprovider
# 25 passed, 44 subtests passed in 0.11s

.\.venv\Scripts\python.exe -m pytest tests/test_cli_args.py tests/test_compat_imports.py -q -p no:cacheprovider
# 83 passed, 10 subtests passed in 1.67s

.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
# 261 passed, 59 subtests passed in 8.53s

.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
# Ran 257 tests in 8.234s, OK

.\packages\cli\scripts\preflight-cli.ps1 -Target keysight-34461a
# preflight passed: keysight-34461a
# summary: E:\Git\Keysight\.tmp_tests\cli_preflight\keysight-34461a\summary.md

git diff --check
# no output
```

Live acquisition was not run for this no-hardware structural/test pass because
it does not alter SCPI command sequences, VISA timeout behavior, trigger wait
strategy, measurement logic, stop flow, cleanup order, Auto Range, Auto Zero,
NPLC, VM Comp, or release/local behavior.

Latest automated validation for the 2026-05-24 CLI/Core split:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cli_args.py -q -p no:cacheprovider
# 145 passed, 90 subtests passed in 1.76s

.\.venv\Scripts\python.exe -m pytest tests/test_instrument_backend.py tests/test_acquisition_engine.py tests/test_measurement.py tests/test_compat_imports.py -q -p no:cacheprovider
# 97 passed in 2.26s

.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
# Ran 295 tests in 8.317s, OK

.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
# 299 passed, 95 subtests passed in 8.65s

git diff --check
# no whitespace errors; only LF-to-CRLF working-copy warnings
```

Live acquisition was not run for this structural split because it does not
alter SCPI command sequences, VISA timeout behavior, trigger wait strategy,
measurement logic, stop flow, cleanup order, Auto Range, Auto Zero, NPLC, VM
Comp, or release/local behavior.

Latest automated validation for the 2026-05-24 low-risk CLI/preflight/docs
pass:

```powershell
.\.venv\Scripts\python.exe -m pytest packages/cli/tests/test_cli_package_metadata.py tests/test_cli_args.py tests/test_docs_cli_examples.py -q -p no:cacheprovider
# 148 passed, 90 subtests passed in 1.74s

.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
# 294 passed, 95 subtests passed in 8.75s

.\.venv\Scripts\python.exe -m keysight_logger_cli --help
# usage: keysight-logger [-h] [--version] {list-resources,start-trigger-record,soft-trigger,soft-stop} ...

.\.venv\Scripts\python.exe -m keysight_logger_cli list-resources --dry-run
# includes dry_run_performs_visa_io: false and VISA I/O: no

.\.venv\Scripts\python.exe -m keysight_logger_cli list-resources --dry-run --json
# emitted one dry_run JSON object with dry_run_performs_visa_io=false

.\packages\cli\scripts\preflight-cli.ps1 -ListTargets
# keysight-34461a

.\packages\cli\scripts\preflight-cli.ps1 -Target keysight-34461a
# preflight passed: keysight-34461a
# summary: E:\Git\Keysight\.tmp_tests\cli_preflight\keysight-34461a\summary.md

.\packages\cli\scripts\preflight-cli.ps1 -Target keysight-34461a -OutputRoot ".tmp_tests\cli_preflight_custom"
# preflight passed: keysight-34461a
# summary: E:\Git\Keysight\.tmp_tests\cli_preflight_custom\keysight-34461a\summary.md

.\packages\cli\scripts\preflight-cli.ps1 -Target keysight-34461a -OutputRoot ".tmp_bad"
# rejected: Only paths under .tmp_tests are allowed for -OutputRoot and preflight output

$ast=$null; $tokens=$null; $errors=$null; $ast=[System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path .\packages\cli\scripts\preflight-cli.ps1), [ref]$tokens, [ref]$errors); $errors.Count
# 0

rg "python\.exe -m keysight_logger\.cli|python -m keysight_logger\.cli" README.md docs\README_CLI_EN.md docs\hardware-test-plan.md docs\project-plan.md
# Only the two explicit module-form alternative lines in docs\README_CLI_EN.md were found.

git diff --check
# no whitespace errors; only existing LF-to-CRLF working-copy warnings
```

The generated default and custom preflight reports include
`summary_counts = { commands_total = 24, checks_total = 24, dry_run_cases = 8,
simulate_cases = 12, soft_client_dry_runs = 2,
list_resources_contract_checks = 1, mocked_pytest_checks = 1 }`.

No live acquisition was run for this pass because it does not alter
instrument-affecting behavior.

Local editable-install refresh could not be completed in this sandbox:
`uv pip install -e ".[dev]"` failed on access to
`C:\Users\tom75\AppData\Local\uv\cache\sdists-v9\.git`, and the escalation
request could not complete because the approval review service returned 503.
As a result, local console-script smoke could not run in this checkout because
`.\.venv\Scripts\keysight-logger.exe` is absent, and the local stale installed
metadata still makes module-form `--version` report `keysight-logger 1.1.5`.
After a successful editable install for the current baseline, `--version`
should report the installed package metadata for the current `pyproject.toml`
version.

Latest automated and user-reported validation for the uv-native setup,
`keysight-logger` console script, and console-script metadata coverage:

```powershell
uv pip install -e ".[dev]"
# Installed keysight-logger==1.1.6 plus dev dependencies.
# uv warned that hardlinking failed and fell back to copying files.

.\.venv\Scripts\keysight-logger.exe --help
# usage: keysight-logger [-h] {list-resources,start-trigger-record,soft-trigger,soft-stop} ...

.\.venv\Scripts\keysight-logger.exe list-resources --dry-run --json
# emitted one dry_run JSON object with dry_run_performs_visa_io=false

.\packages\cli\scripts\preflight-cli.ps1 -Target keysight-34461a
# preflight passed: keysight-34461a
# summary: E:\Git\Keysight\.tmp_tests\cli_preflight\keysight-34461a\summary.md

.\.venv\Scripts\python.exe -m pytest tests/test_cli_args.py tests/test_instrument.py packages/cli/tests/test_cli_package_metadata.py -q -p no:cacheprovider
# 172 passed, 91 subtests passed in 1.71s

.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
# 289 passed, 91 subtests passed in 8.59s
```

The console-script install/help/dry-run checks above were user-reported from an
`E:\Download\Keysight` checkout. The preflight check was user-reported from
`E:\Git\Keysight` and was re-run locally in this checkout with the same pass
result. The pytest results above were run locally in this checkout after adding
the console-script metadata test. These checks do not touch live instrument
acquisition; the `list-resources --dry-run` command explicitly reports no VISA
I/O.

Local console-script smoke in this checkout could not be re-run because the
generated virtualenv entry point `.\.venv\Scripts\keysight-logger.exe` was not
present in this local `.venv`. That file is an install artifact, not a tracked
project file. A local `uv pip install -e ".[dev]"` refresh to regenerate it was
blocked by Windows access denial in
`C:\Users\tom75\AppData\Local\uv\cache\sdists-v9\.git`; the required escalation
request could not complete because the approval review service returned 503.
The equivalent module-form no-hardware checks did pass:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger_cli --help
# usage: keysight-logger [-h] {list-resources,start-trigger-record,soft-trigger,soft-stop} ...

.\.venv\Scripts\python.exe -m keysight_logger_cli list-resources --dry-run --json
# emitted one dry_run JSON object with dry_run_performs_visa_io=false
```

Latest automated validation for the 2026-05-23 worker control/status contract:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_software_trigger_adapter.py tests/test_cli_args.py -q -p no:cacheprovider
# 145 passed, 86 subtests passed

.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
# 277 passed, 91 subtests passed

.\packages\cli\scripts\preflight-cli.ps1 -Target keysight-34461a
# preflight passed: keysight-34461a
```

Live acquisition was not run for this control-plane/documentation pass because
the change does not alter SCPI, VISA timeout, trigger wait strategy,
measurement logic, stop flow, cleanup order, or release/local behavior.

Latest automated validation for the 2026-05-22 planning and validation
consolidation:

```powershell
$tokens=$null; $errors=$null; [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path .\packages\cli\scripts\preflight-cli.ps1), [ref]$tokens, [ref]$errors)
# preflight parse ok

$tokens=$null; $errors=$null; [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path .\packages\cli\scripts\live-cli-check.ps1), [ref]$tokens, [ref]$errors)
# live parse ok

.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
# 272 passed, 91 subtests passed

.\packages\cli\scripts\preflight-cli.ps1 -Target keysight-34461a
# preflight passed: keysight-34461a

.\packages\cli\scripts\live-cli-check.ps1 -Target keysight-34461a -Connection usb
# failed before prompt: Missing -Resource.

.\packages\cli\scripts\live-cli-check.ps1 -Target unsupported -Connection usb -Resource SIM::34461A
# failed before prompt: Unsupported target.

.\packages\cli\scripts\live-cli-check.ps1 -Target keysight-34461a -Connection gpib -Resource SIM::34461A
# failed before prompt: Unsupported connection.

'' | .\packages\cli\scripts\live-cli-check.ps1 -Target keysight-34461a -Connection usb -Resource SIM::34461A
# default minimal suite: preflight and dry-run plan printed; refused live run because stdin was redirected.

'' | .\packages\cli\scripts\live-cli-check.ps1 -Target keysight-34461a -Connection usb -Resource SIM::34461A -Suite basic
# preflight and dry-run plans for the 10 basic cases printed; refused live run because stdin was redirected.

'' | .\packages\cli\scripts\live-cli-check.ps1 -Target keysight-34461a -Connection usb -Resource SIM::34461A -Suite external
# preflight and dry-run plans for the 2 external cases printed; refused live run because stdin was redirected.
```

PSScriptAnalyzer was not run in this pass. Live acquisition was not run; it remains opt-in through
`scripts/live-cli-check.ps1` with an explicit real VISA resource and
interactive Enter confirmation.

Latest automated validation for the `v1.1.5-cli` resource-verify cleanup:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_instrument.py -q -p no:cacheprovider
# 20 passed, 5 subtests passed

.\.venv\Scripts\python.exe -m pytest tests/test_cli_args.py -q -p no:cacheprovider -k list_resources
# 10 passed, 84 deselected
```

Real-instrument validation reported by the user for the `v1.1.5-cli`
resource-verify cleanup:

- `list-resources --verify` reported six stale cached TCPIP/USB entries and one
  live 34461A:
  `USB0::0x2A8D::0x1301::MY60045220::0::INSTR`,
  `Keysight Technologies,34461A,MY60045220,A.03.03-03.15-03.03-00.52-04-03`.
- `list-resources --live-only` reported only that same live 34461A resource.
- Result: verified/live-only scan behavior OK for the connected real
  instrument. Stale cached resources remained stale and the live filter hid
  them as expected.

Latest automated validation for the current profile-refactor working tree:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_capabilities.py tests/test_cli_args.py tests/test_measurement.py -q -p no:cacheprovider
# 152 passed, 80 subtests passed

.\.venv\Scripts\python.exe -m pytest tests/test_capabilities.py tests/test_cli_args.py tests/test_acquisition_engine.py tests/test_measurement.py tests/test_csv_writer.py -q -p no:cacheprovider
# 177 passed, 80 subtests passed
```

Latest automated validation for the TriggerRouter bounded-queue update:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_trigger_router.py tests/test_software_trigger_adapter.py -q -p no:cacheprovider
# 10 passed

.\.venv\Scripts\python.exe -m pytest tests/test_trigger_router.py tests/test_software_trigger_adapter.py tests/test_acquisition_engine.py tests/test_cli_args.py -q -p no:cacheprovider
# 127 passed, 80 subtests passed

.\.venv\Scripts\python.exe -m pytest tests/test_capabilities.py tests/test_cli_args.py tests/test_acquisition_engine.py tests/test_measurement.py tests/test_csv_writer.py tests/test_trigger_router.py tests/test_software_trigger_adapter.py -q -p no:cacheprovider
# 194 passed, 80 subtests passed
```

Latest automated validation for the 2026-05-18 acquisition error and IDN
hardening update:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_instrument.py tests/test_acquisition_engine.py tests/test_cli_args.py -q -p no:cacheprovider
# 138 passed, 85 subtests passed

.\.venv\Scripts\python.exe -m pytest tests/test_capabilities.py tests/test_cli_args.py tests/test_acquisition_engine.py tests/test_measurement.py tests/test_csv_writer.py tests/test_trigger_router.py tests/test_software_trigger_adapter.py tests/test_instrument.py -q -p no:cacheprovider
# 215 passed, 85 subtests passed

.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
# Ran 215 tests in 4.718s, OK
```

Latest automated validation for the 2026-05-18 CLI agent support update:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cli_args.py tests/test_instrument.py tests/test_simulator.py -q -p no:cacheprovider
# 137 passed, 85 subtests passed

.\.venv\Scripts\python.exe -m pytest tests/test_capabilities.py tests/test_cli_args.py tests/test_acquisition_engine.py tests/test_measurement.py tests/test_csv_writer.py tests/test_trigger_router.py tests/test_software_trigger_adapter.py tests/test_instrument.py tests/test_simulator.py -q -p no:cacheprovider
# 246 passed, 85 subtests passed

.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
# Ran 246 tests in 4.864s, OK
```

Latest automated validation for the 2026-05-19 simulate agent coverage
expansion:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cli_args.py -q -p no:cacheprovider -k "simulate"
# 8 passed, 106 deselected, 6 subtests passed

.\.venv\Scripts\python.exe -m pytest tests/test_cli_args.py tests/test_instrument.py tests/test_simulator.py -q -p no:cacheprovider
# 140 passed, 91 subtests passed

.\.venv\Scripts\python.exe -m pytest tests/test_capabilities.py tests/test_cli_args.py tests/test_acquisition_engine.py tests/test_measurement.py tests/test_csv_writer.py tests/test_trigger_router.py tests/test_software_trigger_adapter.py tests/test_instrument.py tests/test_simulator.py -q -p no:cacheprovider
# 249 passed, 91 subtests passed

.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
# Ran 249 tests in 5.099s, OK
```

Latest automated validation for the 2026-05-19 simulate failure/boundary
coverage expansion:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cli_args.py tests/test_simulator.py -q -p no:cacheprovider -k "simulate or Simulated"
# 17 passed, 106 deselected, 6 subtests passed

.\.venv\Scripts\python.exe -m pytest tests/test_cli_args.py tests/test_instrument.py tests/test_simulator.py tests/test_trigger_router.py tests/test_software_trigger_adapter.py -q -p no:cacheprovider
# 159 passed, 91 subtests passed

.\.venv\Scripts\python.exe -m pytest tests/test_capabilities.py tests/test_cli_args.py tests/test_acquisition_engine.py tests/test_measurement.py tests/test_csv_writer.py tests/test_trigger_router.py tests/test_software_trigger_adapter.py tests/test_instrument.py tests/test_simulator.py -q -p no:cacheprovider
# 256 passed, 91 subtests passed
```

Real-instrument smoke for the new strict IDN gate reported by the user:

- Initial `python -m keysight_logger_cli ...` outside `.venv` failed with
  `ModuleNotFoundError: No module named 'keysight_logger'`; activating `.venv`
  resolved the environment issue.
- Immediate-mode default current measurement with `--max-samples 5` completed
  successfully on the real instrument.
- Result: `captured=5 errors=0`.
- Cleanup completed normally:
  `release_to_local` and `cleanup_release_to_local` both reported successful
  `visa_clear`, `*CLS`, `ABOR`, `SYST:LOC`, and `control_ren(0)` paths.

Command shape used:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger_cli start-trigger-record `
  --resource "<RESOURCE>" `
  --trigger-mode immediate `
  --trigger-timeout-ms 10000 `
  --max-samples 5
```

Real-instrument validation reported by the user:

- Baseline USB communication and current measurement: OK.
- DC current modes: software, software timer, external, immediate, and custom
  modes were previously reported OK.
- Stop paths `soft-stop`, Ctrl+C, Ctrl+Break, and `q`: OK in rough tests.
- `list-resources --verify`: previously did not leave the instrument stuck in
  remote state.
- DC voltage:
  - Auto Range immediate smoke: OK.
  - Manual 10 V immediate smoke: OK.
  - Software trigger, software timer, external trigger, and rough custom-mode
    checks: OK.
  - Post-refactor low-cost regression: OK.
- AC current and AC voltage:
  - Implemented and committed.
  - Automated validation: focused pytest, broader pytest, and unittest discover
    all passed in this session.
  - Real-instrument flow validation: user reported AC voltage and AC current
    were tested across the supported trigger-mode families, with software timer
    also checked under software mode; the process and console behavior looked
    normal.
  - Actual AC signal sanity validation: ACI and ACV immediate three-sample
    real-signal checks were later reported OK, with CLI values matching the
    34461A front panel.
  - AC bandwidth/filter controls are not implemented.
- DCV Input Z:
  - `--dcv-input-impedance auto` real-instrument immediate smoke: OK.
  - `--dcv-input-impedance 10m` real-instrument immediate smoke: OK.
  - Front-panel Input Z behavior matched expectations according to the user.
- Resistance 2-wire:
  - Auto Range immediate one-row smoke: OK.
  - Manual 1000 Ohm immediate one-row smoke: OK.
  - Software, external, software-custom, and external-custom trigger modes:
    OK in short 5-10 reading real-instrument tests reported by the user.
  - CSV fields and values reported normal.
- Resistance 4-wire:
  - Implemented and committed.
  - Initial real-instrument smoke measured plausible values but showed a
    front-panel `Error caused by remote command.`
  - Follow-up fix removes `FRES:ZERO:AUTO`.
  - Auto Range immediate one-row smoke after the fix: OK.
  - Manual 100k Ohm immediate one-row smoke after the fix: OK.
  - Software, external, software-custom, and external-custom trigger modes:
    OK in short 5-10 reading real-instrument tests reported by the user.
  - Front-panel remote-command error no longer appears.

Resistance 2-wire smoke commands that were validated:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger_cli start-trigger-record `
  --resource "<RESOURCE>" `
  --csv ".\data\resistance_2w_auto_smoke.csv" `
  --trigger-mode immediate `
  --measurement resistance-2w `
  --auto-range on `
  --auto-zero off `
  --nplc 1.0 `
  --max-samples 1
```

```powershell
.\.venv\Scripts\python.exe -m keysight_logger_cli start-trigger-record `
  --resource "<RESOURCE>" `
  --csv ".\data\resistance_2w_range1000_smoke.csv" `
  --trigger-mode immediate `
  --measurement resistance-2w `
  --auto-range off `
  --range 1000 `
  --auto-zero off `
  --nplc 1.0 `
  --max-samples 1
```

Expected resistance CSV checks:

- `measurement_type=resistance_2w`
- `unit=Ohm`
- `trigger_source=immediate`
- `status=ok`
- measured value plausible for the connected resistor or open/fixture condition

Resistance 4-wire smoke commands that were validated after the `FRES:ZERO:AUTO`
fix:

```powershell
.\.venv\Scripts\python.exe -m keysight_logger_cli start-trigger-record `
  --resource "<RESOURCE>" `
  --csv ".\data\resistance_4w_auto_smoke.csv" `
  --trigger-mode immediate `
  --measurement resistance-4w `
  --auto-range on `
  --nplc 1.0 `
  --max-samples 1
```

```powershell
.\.venv\Scripts\python.exe -m keysight_logger_cli start-trigger-record `
  --resource "<RESOURCE>" `
  --csv ".\data\resistance_4w_range100k_smoke.csv" `
  --trigger-mode immediate `
  --measurement resistance-4w `
  --auto-range off `
  --range 100000 `
  --nplc 1.0 `
  --max-samples 1
```

Expected 4-wire CSV checks:

- `measurement_type=resistance_4w`
- `unit=Ohm`
- `trigger_source=immediate`
- `status=ok`
- measured value plausible for the connected Kelvin wiring and resistor
- no front-panel `Error caused by remote command.`

## Implemented Architecture Summary

- Runtime core modules now live under `keysight_logger_core.*`; the former
  top-level module paths are compatibility re-export shims.
- `keysight_logger_core` is the formal minimal public entry point for
  WebUI/agent integrations. Its package-root `__all__` exports
  `InstrumentProfile`, `StartRequest`, the default profile accessor,
  validation and dry-run planning functions/types, runtime event/result/control
  plane types, `StopController`, and `run_start_session`.
- Implementation submodules remain available for existing internal code and
  tests, but public integrations should prefer the package-root exports.
  Legacy aliases, test dependency injection hooks, terminal-control hooks, run
  ID helpers, null sinks, software-trigger control-plane internals, and
  instrument/backend/simulator/storage/acquisition implementation classes are
  intentionally not exported from `keysight_logger_core`.
- `keysight_logger_cli.cli` is the CLI adapter: argparse setup, event/output
  formatting, dry-run plan formatting, soft/list client commands, and terminal
  controls for local stop handling.
- `core.models.StartRequest` is the shared start command request model.
  `argparse.Namespace` is adapted in `cli.py` and should not cross into Core
  validation, dry-run planning, or runtime orchestration.
- `MeasurementDefinition` registers canonical external/internal measurement
  metadata. Use `canonical_name` for the stable external name; `cli_name` is a
  read-only compatibility alias.
- `MeasurementDefinition` intentionally does not carry 34461A range or NPLC
  option tables after the 2026-05-16 profile refactor.
- `ScalarDmmMeasurement` owns shared scalar DMM readout behavior.
- `CurrentMeasurement` remains as a compatibility alias for
  `CurrentDcMeasurement`.
- `VoltageDcMeasurement` and `Resistance2wMeasurement` use the shared scalar
  base.
- `CurrentAcMeasurement` and `VoltageAcMeasurement` use the shared scalar base,
  configure only the AC function plus Auto Range/manual range, and do not write
  NPLC or Auto Zero SCPI.
- `Resistance4wMeasurement` also uses the shared scalar base and differs from
  2-wire resistance in the `FRES` SCPI family, internal measurement type, and
  by not writing Auto Zero SCPI.
- `InstrumentProfile` centralizes 34461A capabilities.
- `MeasurementOptions` on `InstrumentProfile` centralizes supported
  measurement types plus per-measurement range and NPLC options.
- `KEYSIGHT_34461A_CAPABILITIES` remains as a compatibility alias.
- `core.validation` uses `StartRequest` plus the default 34461A profile for
  supported measurement choices, range checks, NPLC checks, and reading memory
  checks.
- `core.run_plan` builds `start-trigger-record --dry-run` plans from
  `StartRequest`; `StartPlan` intentionally excludes adapter-only output fields
  such as `status_format` and dry-run JSON's `measurement_cli_name`, and
  `cli.py` formats plans for text or JSONL output.
- `core.runner` owns non-dry-run `start-trigger-record` orchestration:
  instrument/backend creation, trigger router, CSV writer, measurement plugin,
  acquisition engine, software trigger server, worker thread, summary, and
  final cleanup. CLI terminal signal/keyboard handling is injected through
  controls.
- Acquisition custom-mode checks use the injected profile.
- `TriggerRouter` owns a bounded normal trigger-event queue in the shared
  CLI/core layer and returns rejection status from `publish()` when that queue
  is full. Stop/control events use a separate priority queue.
- There is no automatic model detection or profile switching yet.
- `start-trigger-record --dry-run`, `--status-format jsonl`, and
  `--simulate` now exist as agent-friendly CLI workflows. They are documented
  in `docs/README_CLI_EN.md` and are intended for planning, structured
  observation, and deterministic workflow testing rather than replacing the
  real instrument path.
- `soft-trigger --format json` and `soft-stop --format json` emit structured
  JSON for agent callers.
- `VisaInstrument` supports injected `resource_manager_factory`.

## Resource Listing Behavior

- Plain `list-resources` prints raw VISA resources returned by PyVISA and may
  include stale cached entries. It does not open resources or run release
  cleanup.
- `list-resources --verify` opens each resource and queries `*IDN?`; text output
  marks rows as `live` or `stale`. When `*IDN?` succeeds, verification runs
  the existing best-effort release-to-local helper before closing the session;
  cleanup failures do not change the row to stale.
- `list-resources --live-only` performs verification, applies the same
  successful-live release cleanup, and prints only live rows.
- If no live resource is found, `--live-only` text output prints:
  `no live VISA resources found`.
- JSON output for `--live-only --format json` includes `live_only: true`,
  `verify: true`, and a filtered `resources` list.

## CSV Output Error Handling

- If `--csv` is omitted, the CLI chooses a UTC+8 timestamped default path under
  `data` and prints the selected path before connecting to the instrument.
- If the requested CSV output path cannot be opened because Windows denies
  write access, for example because the file is open in Excel, the worker
  records a fatal startup error instead of printing a Python thread traceback.
- CLI output should explain:
  - which CSV path could not be opened;
  - that permission was denied and the file may be open in Excel or another
    program;
  - to close the file or choose a different `--csv` path.
- The run still performs normal cleanup and returns a non-zero exit code.
- Automated validation for the committed CSV-open error handling change:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_acquisition_engine.py tests/test_cli_args.py -q -p no:cacheprovider
# 141 passed, 80 subtests passed

.\.venv\Scripts\python.exe -m pytest tests/test_capabilities.py tests/test_cli_args.py tests/test_acquisition_engine.py tests/test_measurement.py tests/test_csv_writer.py -q -p no:cacheprovider
# 208 passed, 80 subtests passed
```

## Branch Scope

This handoff tracks the `Cli` branch only. Keep CLI status, CLI validation, and
CLI release notes here. Do not use this file to track UI work; UI-specific
handoff/status belongs on the separate Codex branch.

CLI release tags use the `vX.Y.Z-cli` form. The Python package version in
`pyproject.toml` tracks the CLI package version on this branch.

## Next Work

Current known follow-ups for this `Cli`/34461A handoff:

1. USB hardware validation is complete for currently implemented features.
2. LAN discovery and the `basic` wrapper suite have passed from a second
   checkout/machine. Run LAN `external` or `full` only if the operator wants to
   re-check external-trigger behavior over TCPIP.
3. ACI and ACV real-signal sanity checks have passed against the 34461A front
   panel. If AC measurement problems appear later, revisit AC bandwidth or
   filter controls only after confirming 34461A SCPI command names, valid
   values, and behavior on real AC voltage/current signals.
4. Run `scripts/live-cli-check.ps1` only when the user explicitly provides the
   target connection/resource and chooses the needed suite. For a fresh
   hardware pass, start with `-Suite minimal`, then use `-Suite basic` for
   implemented-feature live coverage that does not need an external edge,
   `-Suite external` for operator-provided external trigger edges, or
   `-Suite full` for both. The wrapper runs preflight first and waits for Enter
   before touching the instrument.
5. `core.run_plan` still imports `HardwareTriggerAdapter` for dry-run external
   trigger preview generation. A future small refactor can extract a pure SCPI
   preview helper if this coupling becomes a maintenance issue; this pass
   intentionally left dry-run behavior unchanged.
No live hardware validation was run for this cut because no SCPI, VISA timeout,
trigger wait, cleanup order, or measurement behavior changed.

## DCV Ratio Core Implementation

Core DCV Ratio implementation and no-hardware validation were completed on
2026-05-27. The change adds `measurement="voltage-dc-ratio"`, ratio sample
metadata from `DATA2?`, stricter `dcv_input_impedance` validation, and CSV
`measurement_metadata` output.

Focused no-hardware validation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_capabilities.py tests/test_measurement.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_csv_writer.py tests/test_simulator.py -q -p no:cacheprovider
```

Result: 124 passed, 59 subtests passed.

Required Core guard validation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_core_public_api.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py packages/cli/tests/test_cli_package_metadata.py packages/cli/tests/test_cli_docs_ownership.py -q -p no:cacheprovider
```

Result: 47 passed, 59 subtests passed.

Full Core suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

Result: 216 passed, 64 subtests passed.

No live 34461A DCV Ratio validation was run in this pass. Live validation
should follow `docs/hardware-test-plan.md` and use operator-confirmed Input and
Sense wiring limits.

## Live 34461A Measurement Options

Live Core API validation was run on 2026-05-27 with explicit resource
`USB0::0x2A8D::0x1301::MY60045220::0::INSTR`.

Baseline live smoke:

- `measurement="current-dc"`, `trigger_mode="immediate"`, `max_samples=1`.
- Result: `ok=True`, `reason="completed"`, `captured=1`, `errors=0`,
  `fatal_error=None`.
- Cleanup completed and released the instrument to local.

New measurement option live checks:

- Auto Zero Once passed on the operator-selected supported measurements.
- AC bandwidth values `3`, `20`, and `200` passed.
- Invalid AC bandwidth input produced the expected validation error.
- 10 A current terminal selection passed with an operator-confirmed safe setup.

These checks validate the new explicit Core request fields. Default requests
continue to preserve the previous command sequence.
