---
name: keysight-meters-cli-orchestration
description: Use when modifying, testing, reviewing, or orchestrating Keysight_Meters_Logger Meters CLI/worker subprocess workflows, including start-trigger-record, JSON/JSONL contracts, dry-run, simulate, wait-ready, status, send-command, stop, POST /command, GET /status, report.json, CSV, run_id correlation, and live resource safety. Do not use for CSS-only UI styling, general documentation polishing, or unrelated Python refactors.
---

# Keysight Meters CLI Orchestration

This skill helps Codex follow the public Keysight_Meters_Logger Meters
CLI/worker subprocess contracts. It is an instruction-only skill. It does not
provide an instrument driver, replace the CLI, or authorize live hardware work.

## When to use this skill

Use this skill for tasks that affect or validate the Meters CLI/worker contract
surface, including:

- `start-trigger-record` lifecycle behavior.
- Runtime JSONL events and single-response JSON client commands.
- `dry-run`, `simulate`, and live validation planning.
- `wait-ready`, `status`, `send-command`, and `stop` client behavior.
- Local worker endpoints: `POST /command`, `POST /stop`, and `GET /status`.
- `run_id` correlation between stdout JSONL, status responses, CSV, and
  `report.json` artifacts.
- Orchestrator workflows, wrapper reports, and live resource safety.

Do not use this skill for CSS-only UI styling, plain README wording changes,
or unrelated Python refactors unless those changes affect the CLI/worker
contract surface.

## Contract lookup order

Before making contract-sensitive decisions, read the relevant contract files.
Use this lookup order:

1. If working inside the Keysight_Meters_Logger repository and `docs/contracts/`
   is available, treat those files as the upstream source of truth.
2. If this skill is installed standalone and has a local `references/` directory,
   read the copied contract files there as a contract snapshot.
3. If both `docs/contracts/` and `references/` are available and appear to
   differ, warn the user before making contract-sensitive changes.

Relevant contracts:

- `common-worker-protocol.md`
- `common-cli-jsonl-contract.md`
- `common-orchestrator-workflows.md`
- `meters-worker-contract.md`
- `meters-cli-jsonl-contract.md`
- `meters-orchestrator-workflows.md`

## Hard rules

- Treat machine JSON, JSONL, structured artifacts, CSV, `report.json`, and
  process exit codes as the contract surface.
- Do not make pass/fail decisions from human-readable text. Human text is
  diagnostic only.
- For acquisition workflow changes, prefer this validation order:
  1. dry-run JSONL validation,
  2. simulator JSONL run with a finite bound such as `--max-samples`,
  3. live run only when an explicit user-selected `--resource` is provided.
- Do not scan, guess, rotate, brute-force, or silently substitute live VISA
  resource strings inside an acquisition workflow.
- Treat `keysight-logger`, `keysight-logger.exe`, and
  `python -m keysight_logger_cli` as equivalent only when they preserve the
  documented CLI/worker subprocess behavior.
- Do not treat direct in-process Python API calls, such as importing core runner
  functions, as covered by the CLI/worker subprocess contract unless a separate
  Python API contract defines them.
- Wait for the `ready` JSONL event or `wait-ready --json` before sending
  lifecycle control requests.
- Treat `ready` and `wait-ready` as control-plane readiness only, not
  measurement completion.
- `GET /status` must be non-mutating. It must not trigger measurement, mutate
  queues, request stop, or perform device I/O.
- Use `POST /command` or `keysight-logger send-command --json` for Meters
  software-triggered measurement requests only after readiness.
- Use `POST /stop` or `keysight-logger stop --json` for cooperative cleanup.
- Correlate stdout JSONL, status responses, CSV, and report artifacts by
  `run_id` for one non-dry-run runtime session.
- Treat missing `ready`, malformed JSON, non-zero process exit, missing final
  summary, `summary.ok: false`, or `fatal_error` as failed or incomplete unless
  the instrument-specific contract says otherwise.
- Consumers must ignore unknown JSON fields under schema version `1`.

## Executable orchestration rules

Apply these rules before running or preparing executable Meters workflows such as
`start-trigger-record`, `wait-ready`, `status`, `send-command`, or `stop`:

- Read `common-orchestrator-workflows.md` and
  `meters-orchestrator-workflows.md` before choosing CLI flags, simulator
  resource strings, process-launch patterns, or software-trigger sequencing.
- Use the CLI spellings and simulator resource strings shown in the contracts as
  the source of truth. Do not invent flags such as `--function` or
  `--trigger-source`, SCPI-form measurement values such as `CURR:DC`, or
  simulator aliases such as `SIMULATOR` unless the repository contracts or CLI
  help explicitly support them.
- Use CLI help only to confirm behavior not covered by the contracts, or to
  diagnose a mismatch between the installed CLI and the documented contract.
- For software-trigger workflows, treat `start-trigger-record` as a worker
  subprocess. Do not run it as a blocking foreground command and wait for it to
  finish before sending the trigger. Stream stdout JSONL until `ready`, send the
  documented `software_trigger` command through the client or endpoint, continue
  reading JSONL until `summary`, then check artifacts and exit code.
- Prefer Python `subprocess.Popen` or the repository-documented orchestrator
  pattern for software-trigger worker orchestration so stdout JSONL, `run_id`,
  process exit code, and cleanup remain observable.
- Do not use detached shell-specific launch mechanisms such as PowerShell
  `Start-Process` or `cmd /c start /B` unless the repository explicitly
  documents that pattern. Detached shell launch can hide stdout JSONL, exit
  codes, cleanup state, and `run_id` correlation.
- If a required CLI spelling, resource string, or launch pattern is unclear,
  stop and re-read the source-of-truth contracts before running. Do not probe by
  inventing flags and treating CLI rejection as the normal discovery path.

## Work pattern

1. Identify whether the task touches the CLI/worker contract surface.
2. Read the relevant source-of-truth contracts before editing or reviewing.
3. Keep proposed changes inside the documented lifecycle and safety boundaries.
4. Prefer no-hardware validation first: dry-run, simulator, and contract tests.
5. Require explicit user-selected resources before proposing live runs.
6. Report any contract impact, validation coverage, and remaining live-hardware
   risk explicitly.
