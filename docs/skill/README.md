# Keysight Meters CLI Orchestration Skill

This directory publishes a Codex skill template for the
Keysight_Meters_Logger project. The skill helps Codex follow the documented
Meters CLI/worker subprocess lifecycle, JSON/JSONL contracts, dry-run and
simulator validation order, `run_id` correlation rules, and live resource
safety constraints.

`docs/skill/SKILL.md` is a template. Codex will not discover it while it stays
in this documentation directory. To use it, copy it into a Codex skill
directory such as `.agents/skills/keysight-meters-cli-orchestration/` or
`~/.agents/skills/keysight-meters-cli-orchestration/`.

## Scope

This skill is a project companion for Keysight_Meters_Logger. It is not a
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

When the skill is used inside the Keysight_Meters_Logger repository,
`docs/contracts/` is the upstream source of truth. When the skill is installed
standalone, copy the contract files into the installed skill's `references/`
directory.

A standalone `references/` directory is a contract snapshot. Update it whenever
upstream `docs/contracts/` changes.

## Repo-level installation

Use repo-level installation when you want the skill available only inside a
specific checkout or fork of Keysight_Meters_Logger.

Expected installed layout:

```text
Keysight_Meters_Logger/
  .agents/
    skills/
      keysight-meters-cli-orchestration/
        SKILL.md
        references/
          common-worker-protocol.md
          common-cli-jsonl-contract.md
          common-orchestrator-workflows.md
          meters-worker-contract.md
          meters-cli-jsonl-contract.md
          meters-orchestrator-workflows.md
```

PowerShell from the repository root:

```powershell
$skill = ".agents\skills\keysight-meters-cli-orchestration"
New-Item -ItemType Directory -Force "$skill\references" | Out-Null

Copy-Item "docs\skill\SKILL.md" "$skill\SKILL.md"
Copy-Item "docs\contracts\common-worker-protocol.md" "$skill\references\"
Copy-Item "docs\contracts\common-cli-jsonl-contract.md" "$skill\references\"
Copy-Item "docs\contracts\common-orchestrator-workflows.md" "$skill\references\"
Copy-Item "docs\contracts\meters-worker-contract.md" "$skill\references\"
Copy-Item "docs\contracts\meters-cli-jsonl-contract.md" "$skill\references\"
Copy-Item "docs\contracts\meters-orchestrator-workflows.md" "$skill\references\"
```

Bash from the repository root:

```bash
skill=".agents/skills/keysight-meters-cli-orchestration"
mkdir -p "$skill/references"

cp docs/skill/SKILL.md "$skill/SKILL.md"
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
    keysight-meters-cli-orchestration/
      SKILL.md
      references/
        common-worker-protocol.md
        common-cli-jsonl-contract.md
        common-orchestrator-workflows.md
        meters-worker-contract.md
        meters-cli-jsonl-contract.md
        meters-orchestrator-workflows.md
```

PowerShell from a Keysight_Meters_Logger checkout:

```powershell
$skill = Join-Path $HOME ".agents\skills\keysight-meters-cli-orchestration"
New-Item -ItemType Directory -Force (Join-Path $skill "references") | Out-Null

Copy-Item "docs\skill\SKILL.md" (Join-Path $skill "SKILL.md")
Copy-Item "docs\contracts\common-worker-protocol.md" (Join-Path $skill "references")
Copy-Item "docs\contracts\common-cli-jsonl-contract.md" (Join-Path $skill "references")
Copy-Item "docs\contracts\common-orchestrator-workflows.md" (Join-Path $skill "references")
Copy-Item "docs\contracts\meters-worker-contract.md" (Join-Path $skill "references")
Copy-Item "docs\contracts\meters-cli-jsonl-contract.md" (Join-Path $skill "references")
Copy-Item "docs\contracts\meters-orchestrator-workflows.md" (Join-Path $skill "references")
```

Bash from a Keysight_Meters_Logger checkout:

```bash
skill="$HOME/.agents/skills/keysight-meters-cli-orchestration"
mkdir -p "$skill/references"

cp docs/skill/SKILL.md "$skill/SKILL.md"
cp docs/contracts/common-worker-protocol.md "$skill/references/"
cp docs/contracts/common-cli-jsonl-contract.md "$skill/references/"
cp docs/contracts/common-orchestrator-workflows.md "$skill/references/"
cp docs/contracts/meters-worker-contract.md "$skill/references/"
cp docs/contracts/meters-cli-jsonl-contract.md "$skill/references/"
cp docs/contracts/meters-orchestrator-workflows.md "$skill/references/"
```

For user-level installation, keep the `references/` files synchronized with the
upstream `docs/contracts/` files in the Keysight_Meters_Logger repository.

## Usage examples

See [EXAMPLES.md](EXAMPLES.md) for copyable prompts that show how to ask Codex
to validate a simulator workflow, prepare a safe live workflow, and review an
orchestrator change against the Meters CLI/worker contracts.

Explicitly invoke the skill when the task is contract-sensitive:

```text
Use $keysight-meters-cli-orchestration to review this change against the Meters JSONL contract.
```

```text
Use $keysight-meters-cli-orchestration to plan simulator validation for start-trigger-record.
```

```text
Use $keysight-meters-cli-orchestration to check whether this orchestrator workflow respects run_id correlation and live resource safety.
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
