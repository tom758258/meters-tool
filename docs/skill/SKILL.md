---
name: keysight-meters-cli-orchestration
description: Use when modifying, testing, reviewing, or orchestrating Keysight_Meters_Logger Meters CLI/worker subprocess workflows, including start-trigger-record, JSON/JSONL contracts, dry-run, simulate, wait-ready, status, send-command, stop, POST /command, GET /status, report.json, CSV, run_id correlation, and live resource safety. Do not use for CSS-only UI styling, general documentation polishing, or unrelated Python refactors.
---

# Keysight Meters CLI Orchestration

This skill helps Codex follow the public Keysight_Meters_Logger Meters
CLI/worker subprocess contracts. It is an instruction-only skill. It does not
provide an instrument driver, replace the CLI, or authorize live hardware work.

## Contract lookup order

Before making contract-sensitive decisions, read the relevant contracts in this
order:

1. If working inside the Keysight_Meters_Logger repository and `docs/contracts/`
   is available, treat those files as the upstream source of truth.
2. If this skill is installed standalone and has a local `references/` directory,
   read the copied contract files there as a contract snapshot.
3. If both `docs/contracts/` and `references/` are available and appear to
   differ, warn the user before making contract-sensitive changes.

In executable-only workspaces, such as a folder with `keysight-logger*.exe` but
no repository `docs/contracts/`, first check this skill package's
`references/` directory. Read all six contract snapshots before using CLI help.
If they are not readable, stop and report a missing-contract blocker. CLI help
may confirm installed behavior only after contract lookup has been attempted.

Relevant contracts:

- `common-worker-protocol.md`
- `common-cli-jsonl-contract.md`
- `common-orchestrator-workflows.md`
- `meters-worker-contract.md`
- `meters-cli-jsonl-contract.md`
- `meters-orchestrator-workflows.md`

## Non-negotiables

- Treat machine JSON, JSONL, structured artifacts, CSV, `report.json`, and
  process exit codes as the evidence surface. Human text is diagnostic only.
- Parse CSV with a CSV parser. Meters CSV fields can contain quoted JSON
  metadata; comma splitting is not valid evidence.
- For acquisition changes, validate in this order: dry-run JSONL, simulator
  JSONL with a finite bound such as `--max-samples`, then live only with an
  explicit user-selected `--resource`.
- Keep dry-run and simulator validation as separate `start-trigger-record`
  invocations. Never combine `--dry-run` and `--simulate`.
- Do not scan, guess, rotate, brute-force, or silently substitute live VISA
  resource strings inside an acquisition workflow.
- Treat executable forms as equivalent only when they preserve the documented
  CLI/worker subprocess behavior. Direct in-process Python calls are outside
  this contract unless a separate Python API contract defines them.
- Wait for `ready` JSONL or `wait-ready --json` before lifecycle requests.
  Treat readiness as control-plane availability, not measurement completion.
- Do not use existing `run-artifacts` as evidence for a requested fresh
  validation. Dry-run JSON, worker JSONL, client JSON, CSV, summary, `run_id`,
  and exit code must come from the same fresh runtime session.
- Do not stop, kill, or reuse unrelated pre-existing `keysight-logger`
  processes unless the user explicitly approves it. Use a fresh explicit port
  for the owned worker, or report a pre-existing-worker/port blocker.

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
- Every non-dry-run worker invocation must use owned-process cleanup: keep the
  worker process handle, collect stdout JSONL and stderr, request `stop --json`
  if the owned worker is still running, wait a bounded time for process exit,
  and report the worker exit code. If the exit code is not collected, report
  incomplete lifecycle convergence.
- In executable-only Windows workspaces, an explicit high `--sw-trigger-port`
  plus `wait-ready --json` is an acceptable readiness synchronization path when
  the worker subprocess remains observable and its stdout JSONL, stderr,
  artifacts, and exit code are collected.
- In executable-only Windows workspaces where Python launchers are unavailable,
  Node.js `child_process.spawn` is an acceptable fallback for orchestration if
  it keeps the owned worker handle, streams stdout/stderr, captures client JSON,
  performs cooperative cleanup, and reports the worker exit code.
- For software-trigger workflows, treat `start-trigger-record` as a worker
  subprocess. Stream stdout JSONL incrementally until `ready`, send the
  documented `software_trigger`, continue through expected `sample` and
  `summary`, then check artifacts and exit code.
- If stdout `ready` is not observed within a bounded startup window but the
  worker subprocess is still owned and observable, use `wait-ready --json` as a
  control-plane readiness fallback. Continue collecting stdout JSONL through
  process exit, and require the final artifacts to show the same `run_id` across
  stdout JSONL, `wait-ready`, `status`, `sample`, and `summary`.
- Do not treat a host-side wrapper timeout as worker failure until stdout JSONL
  events, process state, stderr, client command results, status endpoint state
  when available, and generated artifacts have been checked. Report the last
  observed JSONL event, whether `ready` was observed, whether
  `software_trigger` was sent, and whether `summary` was reached.
- On Windows, do not use `WaitForExit`, host-side process waits, or wrapper
  command timeouts as the first synchronization point for software-trigger
  workflows. Start the worker subprocess first, read stdout JSONL immediately,
  then use `ready`, optional `wait-ready --json`, `status --json`, and exactly
  one `send-command --json` as distinct synchronization steps.
- Treat `summary` as acquisition completion evidence, not proof that the worker
  process has already exited. Treat `status.captured` as runtime state evidence,
  not proof that worker cleanup is complete.
- Treat `stop --json` responses such as `already_stopped` as normal cleanup
  states unless combined with other failure evidence.
- Prefer Python `subprocess.Popen` or the repository-documented orchestrator
  pattern for software-trigger worker orchestration so stdout JSONL, `run_id`,
  process exit code, and cleanup remain observable.
- For repeated executable-only simulator smoke validation, prefer the bundled
  helper `scripts/run_meter_sim_workflow.mjs` when Node.js is available. It
  runs a dry-run and an independent simulator software-trigger workflow, writes
  JSONL/CSV/report artifacts, and exits non-zero if the evidence contract is not
  satisfied.
- Do not use detached shell-specific launch mechanisms such as PowerShell
  `Start-Process` or `cmd /c start /B` unless the repository explicitly
  documents that pattern. Detached shell launch can hide stdout JSONL, exit
  codes, cleanup state, and `run_id` correlation.
  Diagnostic one-off use of `Start-Process` is not final workflow evidence.
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

## Bundled simulator helper

Use `scripts/run_meter_sim_workflow.mjs` only for no-hardware simulator smoke
validation. It does not authorize live resources or VISA discovery.

Typical executable-only use:

```powershell
node .agents\skills\keysight-meters-cli-orchestration\scripts\run_meter_sim_workflow.mjs `
  --exe .\keysight-logger-1.5.0.exe `
  --out .tmp_tests\meter_sim_software_trigger `
  --resource SIM::34461A `
  --measurement current-dc `
  --max-samples 1 `
  --port 18765
```

The helper writes:

- `dry_run.jsonl`
- `sim_worker_stdout.jsonl`
- `sim_worker_stderr.txt`
- `sim_samples.csv`
- `sim_report.json`

Treat the helper exit code as a verification result. A successful run requires
dry-run safety fields, exactly one accepted software trigger, matching `run_id`
values across worker JSONL/client responses/artifacts, one CSV row,
`summary.ok: true`, expected captured count, zero errors, and worker exit code
`0`.
