# Meters Tool CLI Orchestration Skill

This directory publishes a Codex skill template for the
Meters Tool project. The skill helps Codex follow the documented
Meters CLI/worker subprocess lifecycle, JSON/JSONL contracts, dry-run and
simulator validation order, `run_id` correlation rules, and live resource
safety constraints.

`docs/skill/SKILL.md` is a template. Codex will not discover it while it stays
in this documentation directory. To use it, copy it into a Codex skill
directory such as `.agents/skills/meters-tool-cli-orchestration/` or
`~/.agents/skills/meters-tool-cli-orchestration/`.

## Scope

This skill is a project companion for Meters Tool. It is not a
Keysight driver, does not replace the CLI, and does not automatically control
hardware.

Use it when asking Codex to modify, review, test, debug, or orchestrate work
that touches:

- Meters CLI and worker lifecycle behavior.
- `start-trigger-record`, `dry-run`, `simulate`, `wait-ready`, `status`,
  `send-command`, and `stop`.
- Runtime JSONL events and single-response JSON client commands.
- Local control endpoints: `POST /command`, `POST /stop`, and `GET /status`.
- `run_id` correlation between stdout JSONL, `/status`, CSV, and `report.json`.
- Orchestrator workflows and live resource safety.

Do not use it for CSS-only UI styling, unrelated README wording changes, or
general refactors that do not affect the CLI/worker contract surface.

## Contract files

The skill expects these contract files to be available either from the upstream
repository or from a local `references/` snapshot:

- `common-worker-protocol.md`
- `common-cli-jsonl-contract.md`
- `common-orchestrator-workflows.md`
- `meters-worker-contract.md`
- `meters-cli-jsonl-contract.md`
- `meters-orchestrator-workflows.md`

When the skill is used inside the Meters Tool repository,
`docs/contracts/` is the upstream source of truth. When the skill is installed
standalone, copy the contract files into the installed skill's `references/`
directory.

A standalone `references/` directory is a contract snapshot. Update it whenever
upstream `docs/contracts/` changes.

## Repo-level installation

Use repo-level installation when you want the skill available only inside a
specific checkout or fork of Meters Tool.

Expected installed layout:

```text
meters-tool/
  .agents/
    skills/
      meters-tool-cli-orchestration/
        SKILL.md
        references/
          common-worker-protocol.md
          common-cli-jsonl-contract.md
          common-orchestrator-workflows.md
          meters-worker-contract.md
          meters-cli-jsonl-contract.md
          meters-orchestrator-workflows.md
        scripts/
          run_meter_sim_workflow.mjs
```

PowerShell from the repository root:

```powershell
$skill = ".agents\skills\meters-tool-cli-orchestration"
New-Item -ItemType Directory -Force "$skill\references", "$skill\scripts" | Out-Null

Copy-Item "docs\skill\SKILL.md" "$skill\SKILL.md"
Copy-Item "docs\skill\scripts\run_meter_sim_workflow.mjs" "$skill\scripts\"
Copy-Item "docs\contracts\common-worker-protocol.md" "$skill\references\"
Copy-Item "docs\contracts\common-cli-jsonl-contract.md" "$skill\references\"
Copy-Item "docs\contracts\common-orchestrator-workflows.md" "$skill\references\"
Copy-Item "docs\contracts\meters-worker-contract.md" "$skill\references\"
Copy-Item "docs\contracts\meters-cli-jsonl-contract.md" "$skill\references\"
Copy-Item "docs\contracts\meters-orchestrator-workflows.md" "$skill\references\"
```

Bash from the repository root:

```bash
skill=".agents/skills/meters-tool-cli-orchestration"
mkdir -p "$skill/references" "$skill/scripts"

cp docs/skill/SKILL.md "$skill/SKILL.md"
cp docs/skill/scripts/run_meter_sim_workflow.mjs "$skill/scripts/"
cp docs/contracts/common-worker-protocol.md "$skill/references/"
cp docs/contracts/common-cli-jsonl-contract.md "$skill/references/"
cp docs/contracts/common-orchestrator-workflows.md "$skill/references/"
cp docs/contracts/meters-worker-contract.md "$skill/references/"
cp docs/contracts/meters-cli-jsonl-contract.md "$skill/references/"
cp docs/contracts/meters-orchestrator-workflows.md "$skill/references/"
```

If Codex is run inside this repository and can read `docs/contracts/`, those
files remain the preferred upstream source of truth. The copied `references/`
files are useful when the installed skill is reused or reviewed outside the
original repository context.

## User-level installation

Use user-level installation when you want the skill available across multiple
workspaces.

Expected installed layout:

```text
~/.agents/
  skills/
    meters-tool-cli-orchestration/
      SKILL.md
      references/
        common-worker-protocol.md
        common-cli-jsonl-contract.md
        common-orchestrator-workflows.md
        meters-worker-contract.md
        meters-cli-jsonl-contract.md
        meters-orchestrator-workflows.md
      scripts/
        run_meter_sim_workflow.mjs
```

PowerShell from a Meters Tool checkout:

```powershell
$skill = Join-Path $HOME ".agents\skills\meters-tool-cli-orchestration"
New-Item -ItemType Directory -Force (Join-Path $skill "references"), (Join-Path $skill "scripts") | Out-Null

Copy-Item "docs\skill\SKILL.md" (Join-Path $skill "SKILL.md")
Copy-Item "docs\skill\scripts\run_meter_sim_workflow.mjs" (Join-Path $skill "scripts")
Copy-Item "docs\contracts\common-worker-protocol.md" (Join-Path $skill "references")
Copy-Item "docs\contracts\common-cli-jsonl-contract.md" (Join-Path $skill "references")
Copy-Item "docs\contracts\common-orchestrator-workflows.md" (Join-Path $skill "references")
Copy-Item "docs\contracts\meters-worker-contract.md" (Join-Path $skill "references")
Copy-Item "docs\contracts\meters-cli-jsonl-contract.md" (Join-Path $skill "references")
Copy-Item "docs\contracts\meters-orchestrator-workflows.md" (Join-Path $skill "references")
```

Bash from a Meters Tool checkout:

```bash
skill="$HOME/.agents/skills/meters-tool-cli-orchestration"
mkdir -p "$skill/references" "$skill/scripts"

cp docs/skill/SKILL.md "$skill/SKILL.md"
cp docs/skill/scripts/run_meter_sim_workflow.mjs "$skill/scripts/"
cp docs/contracts/common-worker-protocol.md "$skill/references/"
cp docs/contracts/common-cli-jsonl-contract.md "$skill/references/"
cp docs/contracts/common-orchestrator-workflows.md "$skill/references/"
cp docs/contracts/meters-worker-contract.md "$skill/references/"
cp docs/contracts/meters-cli-jsonl-contract.md "$skill/references/"
cp docs/contracts/meters-orchestrator-workflows.md "$skill/references/"
```

For user-level installation, keep the `references/` files synchronized with the
upstream `docs/contracts/` files in the Meters Tool repository.

## Bundled simulator helper

The skill also ships `scripts/run_meter_sim_workflow.mjs` for no-hardware
simulator smoke validation when Node.js is available. The helper runs a dry-run
and a separate simulator `start-trigger-record` software-trigger workflow,
then writes machine-readable artifacts and exits non-zero when the evidence
contract is not satisfied. Do not use this helper for live resources; changing
`--resource` to a live VISA address such as `USB0::...` does not make it a live
validation path.

Example from a workspace that contains a `meters-tool*.exe` executable:

```powershell
node .agents\skills\meters-tool-cli-orchestration\scripts\run_meter_sim_workflow.mjs `
  --exe .\meters-tool-<version>.exe `
  --out .tmp_tests\meter_sim_software_trigger `
  --resource SIM::34461A `
  --measurement current-dc `
  --max-samples 1 `
  --port 18765
```

The helper writes `dry_run.jsonl`, `sim_worker_stdout.jsonl`,
`sim_worker_stderr.txt`, `sim_samples.csv`, and `sim_report.json` under the
selected output directory. A successful run requires dry-run safety fields,
`wait-ready --json` control-plane readiness when needed, one accepted software
trigger, matching `run_id` values across JSONL/client responses/artifacts, one
CSV row, `summary.ok: true`, the expected captured count, zero errors, and
worker exit code `0`.

## Usage examples

See [EXAMPLES.md](EXAMPLES.md) for copyable prompts that show how to ask Codex
to validate a simulator workflow, prepare a safe live workflow, and review an
orchestrator change against the Meters CLI/worker contracts.

Explicitly invoke the skill when the task is contract-sensitive:

```text
Use $meters-tool-cli-orchestration to review this change against the Meters JSONL contract.
```

```text
Use $meters-tool-cli-orchestration to plan simulator validation for start-trigger-record.
```

```text
Use $meters-tool-cli-orchestration to check whether this orchestrator workflow respects run_id correlation and live resource safety.
```

## Safety notes

- Prefer dry-run and simulator validation before live hardware.
- Live mode requires an explicit user-selected `--resource`.
- Do not scan, guess, rotate, brute-force, or silently substitute live VISA
  resources inside an acquisition workflow.
- Treat `ready` and `wait-ready` as control-plane readiness only, not
  measurement completion.
- Use structured JSON/JSONL, CSV, `report.json`, and exit codes for machine
  decisions. Human-readable text is diagnostic only.
