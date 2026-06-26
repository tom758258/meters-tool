# Keysight Meters CLI Orchestration Skill Examples

This file gives copyable example prompts for the
`keysight-meters-cli-orchestration` Codex skill. The examples show how to ask an
agent to follow the Meters CLI/worker contracts without guessing resources or
parsing human-readable text as the machine contract.

These examples assume the skill has already been installed from
`docs/skill/SKILL.md` into a Codex skill directory and that the relevant
contract files are available from either `docs/contracts/` or the installed
skill's `references/` directory.

## How to choose an example

This file contains three styles of prompts:

- **Guided examples** are for planning, review, and learning. Use them when you
  want the agent to explain the workflow, surface reasonable assumptions, and
  ask clarifying questions before taking action.
- **Direct-run examples** are for no-hardware validation or immediate review
  with safe defaults. Use them when you want the agent to read the skill and
  contracts, confirm the exact CLI spelling from the repository, and proceed
  without asking for confirmation unless the environment is missing, the CLI is
  unavailable, the contracts disagree with CLI help, or the action would touch
  live hardware.
- **Explicit live execution examples** can touch real instruments. Use them only
  when you provide an exact VISA resource and explicitly authorize live
  execution for that resource.

Use guided examples when you are still deciding what to measure or how strict
the workflow should be. Use direct-run examples when you want to test whether an
agent can follow the contract and execute the safe no-hardware path with minimal
back-and-forth. Use explicit live execution examples only when you are ready for
an agent to operate the real instrument after dry-run and simulator validation.

## Before running executable examples

For examples that run or prepare `start-trigger-record`, read the orchestrator
workflow contracts before choosing CLI flags, resource strings, or process-launch
behavior. Treat `common-orchestrator-workflows.md` and
`meters-orchestrator-workflows.md` as the source of truth for measurement names,
trigger mode spelling, simulator resource strings, JSONL mode, software-trigger
sequencing, and subprocess orchestration.

For software-trigger workflows, do not run the worker as a blocking foreground
command and wait for it to finish before sending the trigger. Start it as an
observable subprocess, stream stdout JSONL until `ready`, send exactly one
`software_trigger` command through the documented client or endpoint, continue
reading JSONL until `summary`, then check CSV, `report.json` when present,
`run_id`, and exit code.

Prefer Python `subprocess.Popen` or the repository-documented orchestrator
pattern. Do not use detached shell launch such as PowerShell `Start-Process` or
`cmd /c start /B` unless the repository explicitly documents that pattern,
because detached launch can hide stdout JSONL, exit code, cleanup state, and
`run_id` correlation.

Do not invent CLI flags, measurement values, simulator resource aliases, or
worker launch patterns. Use CLI help only to confirm behavior not covered by the
contracts or to diagnose a mismatch between the installed CLI and the documented
contract.

## Guided examples

### Guided Example 1: Simulator software-trigger workflow

#### Goal

Validate the Meters CLI orchestration flow without live hardware. This example
asks Codex to use the documented no-hardware path first, then run a bounded
simulator workflow that captures exactly one software-triggered sample.

#### User prompt

```text
Use $keysight-meters-cli-orchestration.

I want to validate the Meters CLI orchestration flow without hardware.
Plan and run a simulator software-trigger workflow that captures exactly one
sample. Use dry-run first, then simulate with a finite bound. Wait for ready,
send one software trigger, verify run_id correlation, and report which JSONL
events and artifacts should be checked.

Before choosing CLI flags or launch behavior, read the common and Meters
orchestrator workflow contracts. Use their documented subprocess orchestration
pattern for the software-trigger worker instead of detached shell launch.
```

#### Expected agent behavior

Codex should:

- Read the skill and the relevant Meters contracts before planning the workflow,
  including the common and Meters orchestrator workflow contracts.
- Avoid live hardware and avoid VISA resource discovery.
- Use the documented CLI spellings and simulator resource strings instead of
  inventing flags or aliases.
- Start with a `start-trigger-record --dry-run --status-format jsonl` plan.
- Use simulator mode, such as `--resource SIM::34461A --simulate`.
- Use a finite bound, such as `--max-samples 1`, so the workflow terminates.
- For software-trigger simulate runs, start the worker as an observable
  subprocess, stream stdout JSONL until `ready`, and only then send the trigger.
- Wait for the `ready` JSONL event or use `wait-ready --json` before sending a
  command.
- Send one `software_trigger` command through `send-command --json` or
  `POST /command`.
- Avoid detached shell launch such as PowerShell `Start-Process` or
  `cmd /c start /B` unless the repository explicitly documents it.
- Verify that `run_id` values match across stdout JSONL, status responses, and
  generated artifacts.
- Treat `summary.ok: true`, the expected captured count, zero errors, and a
  zero process exit code as the successful completion signal.
- Mention CSV and `report.json` or wrapper artifacts when applicable.

#### Expected result

The agent should produce or describe a no-hardware validation run. The final
answer should make clear which structured outputs were checked and should not
claim success based only on human-readable text.

This example proves that the skill can guide Codex through the safe contract
path: dry-run, simulator, readiness, command, status, summary, and artifact
checks.

### Guided Example 2: Live workflow planning with explicit resource

#### Goal

Prepare a safe live measurement workflow without letting the agent guess or scan
live VISA resources. This example asks Codex to plan the live path but to stop
before any live command until the user provides an explicit `--resource`.

#### User prompt

```text
Use $keysight-meters-cli-orchestration.

Prepare a live one-sample voltage_dc measurement workflow for my Keysight
34461A. Do not guess, scan, rotate, or substitute VISA resources. Ask me to
provide the explicit --resource before any live command. Use dry-run and
simulator validation first, then show the exact live command that would be run
after I confirm the resource.

Before choosing CLI flags or launch behavior, read the common and Meters
orchestrator workflow contracts. Use their documented subprocess orchestration
pattern for any software-trigger worker instead of detached shell launch.
```

#### Expected agent behavior

Codex should:

- Read the skill and the relevant Meters contracts before planning live work,
  including the common and Meters orchestrator workflow contracts.
- Refuse to guess, scan, rotate, or substitute live VISA resources inside the
  acquisition workflow.
- Use documented CLI spellings and resource strings instead of inventing flags,
  SCPI-form measurement values, or simulator aliases.
- Ask the user for the explicit `--resource` if it was not provided.
- Plan dry-run and simulator validation before any live command.
- Use repository-documented subprocess orchestration for software-trigger
  validation instead of detached shell launch.
- Treat `ready` and `wait-ready` as control-plane readiness only, not
  measurement completion.
- Show the live command only as a command to run after user confirmation and an
  explicit resource are available.
- Explain the structured outputs to check after the live run: JSONL events,
  `run_id`, status responses, CSV, `report.json`, final summary, and process
  exit code.

#### Expected result

The agent should produce a safe live-workflow plan and should not start live
hardware operations unless the user provides an explicit resource and requests
live execution.

This example proves that the skill preserves the live resource safety boundary
while still helping the user prepare a practical live measurement workflow.

### Guided Example 3: Contract-aware review of an orchestrator change

#### Goal

Review an orchestrator or wrapper change for contract compatibility without
running hardware.

#### User prompt

```text
Use $keysight-meters-cli-orchestration.

Review this orchestrator change against the Meters CLI/worker contracts. Focus
on JSONL parsing, ready/status handling, POST /command behavior, cooperative
stop, run_id correlation, final summary handling, exit codes, and whether the
change avoids guessing live VISA resources.
```

#### Expected agent behavior

Codex should:

- Read the relevant common and Meters-specific contracts.
- Check that machine decisions use JSON/JSONL, structured artifacts, and exit
  codes instead of human-readable text.
- Check that `GET /status` is treated as non-mutating.
- Check that `POST /command` is used only after readiness.
- Check that cleanup uses `POST /stop` or the documented CLI stop client.
- Check that missing `ready`, malformed JSON, non-zero exit, missing summary,
  `summary.ok: false`, and `fatal_error` are treated as failed or incomplete.
- Flag any resource scanning, guessing, rotation, or silent substitution in
  live acquisition workflows.

#### Expected result

The agent should return a contract-focused review with concrete findings,
including which contract boundary each issue affects and whether the change is
safe for no-hardware validation, simulator validation, or live execution.

## Direct-run examples

### Direct-run Example 1: No-hardware simulator software-trigger validation

#### Goal

Run a safe, no-hardware validation workflow with fixed defaults. This prompt is
intended to reduce back-and-forth when you want to test whether an agent can
follow the contracts and execute the dry-run plus simulator path.

#### User prompt

```text
Use $keysight-meters-cli-orchestration.

Run the no-hardware simulator software-trigger validation workflow now.

Use these defaults unless the repository contracts or CLI help require a
different spelling:

- measurement type: current-dc
- simulator resource: SIM::34461A
- trigger mode: software
- finite sample bound: exactly one sample
- output directory: .tmp_tests/skill_examples/simulator_software_trigger/
- worker observation output: JSONL
- client command output: JSON
- software-trigger port: choose an unused localhost port, or use 8765 if it is
  available

Steps:

1. Read the skill and the relevant common and Meters-specific contracts,
   including common-orchestrator-workflows.md and
   meters-orchestrator-workflows.md.
2. Confirm the exact CLI flag spelling from the contracts before using CLI help.
3. Run dry-run first.
4. Run simulator mode with a finite bound using the documented software-trigger
   subprocess orchestration pattern.
5. Start the worker as an observable subprocess, stream stdout JSONL until the
   ready event, and do not use detached shell launch such as PowerShell
   Start-Process or cmd /c start /B unless the repository documents it.
6. Wait for the ready JSONL event or use wait-ready --json.
7. Send exactly one software_trigger command after readiness.
8. Check run_id correlation across stdout JSONL, status response, CSV, and
   report.json if present.
9. Continue reading worker JSONL until summary, then report the JSONL events,
   artifacts, exit codes, summary.ok, captured count, errors, and any contract
   mismatch.

Do not ask for a live VISA resource. Do not ask for confirmation before running
dry-run or simulator commands. Do not invent CLI flags, measurement values,
simulator resource aliases, or worker launch patterns. Only stop to ask me a
question if the CLI cannot be invoked, dependencies are missing, the contracts
and CLI help disagree, the current-dc measurement cannot be expressed safely, or
the command would touch live hardware.
```

#### Expected agent behavior

Codex should:

- Proceed with dry-run and simulator validation instead of asking whether to
  run.
- Use the fixed no-hardware defaults unless the repository contradicts them.
- Read contracts before making contract-sensitive decisions, including the
  orchestrator workflow contracts before choosing flags or launch behavior.
- Confirm real CLI spelling from the repository rather than inventing flags.
- Use repository-documented subprocess orchestration for software-trigger runs
  instead of detached shell launch.
- Avoid live VISA resource questions because the workflow is explicitly
  no-hardware.
- Stop only for environment, dependency, contract, CLI, or live-hardware safety
  blockers.

#### Expected result

The agent should run or attempt the dry-run and simulator validation path and
produce a structured report of what happened. If it cannot run, it should state
the exact blocker rather than asking for optional preferences.

### Direct-run Example 2: Safe live workflow preparation without execution

#### Goal

Prepare a live workflow using safe defaults, but do not execute live hardware
commands. This prompt is useful when you want the agent to prepare the live
path while still preserving the explicit-resource safety boundary.

#### User prompt

```text
Use $keysight-meters-cli-orchestration.

Prepare the safe live one-sample measurement workflow now, but do not execute
any live hardware command.

Use these defaults for no-hardware validation before preparing the live command:

- measurement type: voltage-dc
- simulator resource: SIM::34461A
- trigger mode: software
- finite sample bound: exactly one sample
- output directory: .tmp_tests/skill_examples/live_preparation/
- worker observation output: JSONL
- client command output: JSON

For any dry-run or simulator command, read common-orchestrator-workflows.md and
meters-orchestrator-workflows.md before choosing CLI flags or launch behavior.
Use the documented software-trigger subprocess orchestration pattern. Do not use
detached shell launch such as PowerShell Start-Process or cmd /c start /B unless
the repository documents it.

After dry-run and simulator validation are planned or run, prepare the live
command as a template that uses this placeholder resource:

<USER_SELECTED_VISA_RESOURCE>

Do not scan, guess, rotate, or substitute VISA resources. Do not ask me for the
real live resource in this prompt. Do not execute the live command. Only stop to
ask me a question if the CLI cannot be invoked, dependencies are missing, the
contracts and CLI help disagree, or a planned command would touch live hardware
before I provide an explicit resource and request live execution.

Report:

1. The dry-run and simulator validation result or the blocker that prevented it.
2. The exact live command template using <USER_SELECTED_VISA_RESOURCE>.
3. The structured outputs that must be checked after a future live run.
4. The explicit user confirmation required before live execution.
```

#### Expected agent behavior

Codex should:

- Use dry-run and simulator validation before preparing the live template.
- Preserve the live safety boundary by using a placeholder resource.
- Avoid asking for the actual live resource because this prompt does not request
  live execution.
- Avoid scanning or guessing VISA resources.
- Use documented CLI spellings, simulator resource strings, and subprocess
  orchestration instead of invented flags or detached shell launch.
- Make clear that live execution requires an explicit user-selected resource and
  a separate user request.

#### Expected result

The agent should produce a live-workflow preparation result and an exact live
command template, while confirming that no live hardware command was executed.

### Direct-run Example 3: Immediate contract-aware review

#### Goal

Review the current repository changes against the Meters contracts without
requiring another confirmation step.

#### User prompt

```text
Use $keysight-meters-cli-orchestration.

Review the current repository changes against the Meters CLI/worker contracts
now. Use the current git diff, staged changes, or changed files available in the
workspace. If there are no changed files, report that there is no diff to
review.

Read the relevant common and Meters-specific contracts first. Focus on JSONL
parsing, ready/status handling, POST /command behavior, cooperative stop,
run_id correlation, final summary handling, exit codes, artifact decisions, and
whether the change avoids guessing live VISA resources.

Do not ask for confirmation before reviewing. Do not run live hardware. Only
stop to ask me a question if the changed files cannot be read, the contract
files are missing, or the available diff is ambiguous enough that a contract
review would be misleading.

Return concrete findings, affected contract boundaries, severity, and whether
the change is safe for no-hardware validation, simulator validation, or live
execution.
```

#### Expected agent behavior

Codex should:

- Inspect available changed files or diffs immediately.
- Read the relevant contract files before judging behavior.
- Review machine-output handling, lifecycle ordering, status semantics,
  command/stop behavior, `run_id` correlation, artifacts, and live resource
  safety.
- Avoid asking for confirmation unless it cannot access the diff or contracts.
- Avoid running live hardware.

#### Expected result

The agent should return a contract-focused review with actionable findings. If
there is no diff or the diff cannot be read, it should report that blocker
clearly.

## Explicit live execution examples

These examples can touch real instruments. Use them only when the operator has
selected the exact VISA resource and explicitly authorized live execution for
that resource. Do not use these prompts to discover, scan, guess, rotate, or
substitute live VISA resources.

### Explicit Live Example 1: Explicit-resource one-sample live validation

#### Goal

Run the full dry-run, simulator, and live validation sequence for exactly one
sample on a real Keysight 34461A, using only the explicitly provided VISA
resource.

#### User prompt

```text
Use $keysight-meters-cli-orchestration.

Run an explicit-resource live one-sample validation workflow.

I authorize live execution for this exact VISA resource only:

<PASTE_EXPLICIT_VISA_RESOURCE_HERE>

Use these defaults unless the repository contracts or CLI help require a
different spelling:

- measurement type: voltage-dc
- trigger mode: software
- finite sample bound: exactly one sample
- output directory: .tmp_tests/skill_examples/live_one_sample/
- worker observation output: JSONL
- client command output: JSON

Steps:

1. Read the skill and the relevant common and Meters-specific contracts,
   including common-orchestrator-workflows.md and
   meters-orchestrator-workflows.md.
2. Confirm the exact CLI flag spelling from the contracts before using CLI help.
3. Run dry-run first.
4. Run simulator validation with SIM::34461A and a finite bound using the
   documented software-trigger subprocess orchestration pattern.
5. Start the worker as an observable subprocess, stream stdout JSONL until the
   ready event, and do not use detached shell launch such as PowerShell
   Start-Process or cmd /c start /B unless the repository documents it.
6. Only after dry-run and simulator validation pass, run live using exactly the
   VISA resource provided above.
7. Wait for the ready JSONL event or use wait-ready --json.
8. Send exactly one software_trigger command after readiness.
9. Check run_id correlation across stdout JSONL, status response, CSV, and
   report.json if present.
10. Continue reading worker JSONL until summary, then report the JSONL events,
    artifacts, exit codes, summary.ok, captured count, errors, and any contract
    mismatch.

Do not scan, guess, rotate, brute-force, or substitute VISA resources. Do not
use any live resource other than the one explicitly provided above. Do not invent
CLI flags, measurement values, simulator resource aliases, or worker launch
patterns. If the resource is missing, ambiguous, unavailable, or does not match
the intended Keysight 34461A, fail closed and do not run live.
```

#### Expected agent behavior

Codex should:

- Treat this as a real-instrument workflow only because the user explicitly
  authorized live execution and supplied a concrete resource placeholder to be
  replaced by the operator.
- Run or attempt dry-run and simulator validation before any live command.
- Use documented CLI spellings, simulator resource strings, and subprocess
  orchestration instead of invented flags or detached shell launch.
- Use exactly the provided live resource and never scan, guess, rotate, or
  substitute another resource.
- Fail closed before live execution if the resource is missing, ambiguous,
  unavailable, or does not match the intended Keysight 34461A.
- Treat `ready` and `wait-ready` as control-plane readiness only, not
  measurement completion.
- Base pass/fail on structured JSON/JSONL, CSV, `report.json` when present, and
  process exit codes rather than human-readable text.

#### Expected result

The agent should either run the full dry-run, simulator, and explicit-resource
live sequence, or stop before live execution with a precise safety or environment
blocker. The final report should make clear whether live hardware was touched,
which exact resource was used, and which structured outputs were checked.
