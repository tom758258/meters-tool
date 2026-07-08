# CLI Integration

This document is for maintainers of the CLI adapter. Shared Core contracts live
in `docs/core/integration.md`; user-facing command usage lives in
`docs/cli/README.md`; shared and Meters JSON/JSONL schema details live in
root `docs/contracts/`.

This is documentation-only. It does not change runtime behavior, SCPI, VISA,
trigger handling, cleanup order, JSON schema, or public API.

## Adapter Role

`src/meters_tool_cli/cli.py` owns command-line concerns:

- `argparse` parser setup and help text.
- Legacy CLI alias normalization.
- CLI text, JSON, and JSONL formatting.
- Dry-run plan presentation.
- Process exit-code mapping.
- Terminal signal handling, Ctrl+C, Ctrl+Break, and local `q` polling.
- Client workflows such as `list-resources`, `send-command`, and `stop`.

Core owns shared validation, dry-run plan construction, runtime orchestration,
typed events/results, and cleanup sequencing. See
`docs/core/integration.md` for that boundary. The CLI package owns the
adapter runtime, argparse mapping, JSON/JSONL adaptation, wrapper scripts,
scripts, and tests. Root package metadata is shared by Core, CLI, and WebUI.
It no longer supports old root-level Core module import paths.

## Namespace To StartRequest

`argparse.Namespace` exists only in the CLI layer. Before calling Core start
validation, dry-run planning, or non-dry-run runtime orchestration, the CLI
must convert parsed arguments into `StartRequest`.

`--model` / `--instrument-model` remains free text at the argparse boundary.
The parser must not use supported-model `choices`; unknown values such as
`BADMODEL` are accepted by argparse and then rejected by Core profile
validation with the supported models listed. This keeps model aliases and
support policy centralized in Core.

For live starts, omitted `--model` means Core resolves the profile from `*IDN?`.
Supplying `--model` is only an expected-model guard: a mismatch between the
selected model and connected IDN fails before `run_start_session(...)`, and the
selected model must never override the IDN-selected profile. For `--dry-run`
and `--simulate`, the selected model chooses the planning/simulator profile;
omitted model is accepted only for deterministic simulator resources such as
`SIM::34460A` or `SIM::34461A`, and those modes must not perform VISA IDN
preflight.

CLI-only fields such as output format, JSON aliases, terminal behavior, and
wrapper compatibility details should not be added to `StartRequest` unless they
are truly shared Core behavior.

`--enable-hw-trigger` was removed from the CLI parser after the compatibility
period. Users must select simple external hardware triggering with
`--trigger-mode external`. Do not reintroduce this flag in Core models or
adapter contracts that do not parse CLI arguments.

## Dry-Run Formatting

Core returns a neutral `StartPlan` from `build_start_plan(...)`. The CLI may
format that plan as human text or JSONL dry-run output.

Adapter compatibility fields in CLI output are CLI schema fields, not Core
schema fields. For example, CLI dry-run JSON keeps `measurement_cli_name` for
wrapper compatibility while Core `StartPlan` uses `measurement_name`.
`measurement_cli_name` is not Core schema.

Do not move CLI output-only fields such as `status_format` or
`measurement_cli_name` into Core plan models.

## Runtime Mapping

Core emits typed `StartRunEvent` objects and returns `StartRunResult`. The CLI
adapter maps them to:

- human-readable status lines in text mode;
- one JSON object per line in `--status-format jsonl` or `--json` mode;
- process exit codes for success, validation errors, connection/runtime
  failures, and fatal acquisition failures.

The CLI JSON/JSONL schema remains the source of truth for command-line agents
and wrappers. See root `docs/contracts/meters-cli-jsonl-contract.md` and
`docs/contracts/meters-worker-contract.md`.

## Terminal Stop Handling

Terminal signal and keyboard stop handling are CLI concerns. The CLI injects
terminal controls into the Core runner; Core remains responsible for routing
stop into the acquisition engine and running cleanup in the documented order.

Do not move terminal-specific behavior into other adapters. Adapter stop
routing should use Core control-plane APIs or adapter-owned job controllers.

## Client Commands

`send-command`, `stop`, and `list-resources` are CLI/client workflows.
They are not Core `StartRequest` workflows and their JSON contracts are
documented in root `docs/contracts/meters-cli-jsonl-contract.md` and
`docs/contracts/meters-worker-contract.md`.

Keep these commands adapter-shaped: validate client inputs, format text/JSON,
and avoid changing acquisition or VISA behavior as part of client command
maintenance.

