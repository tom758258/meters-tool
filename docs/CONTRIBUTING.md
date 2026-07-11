# Contributing to Meters Tool

Contributions are welcome, including issue reports, focused bug fixes,
documentation improvements, tests, supported-model work, and new measurement
or trigger capabilities. Before opening a pull request, read the relevant
component documentation, the public contracts in `docs/contracts/`, and the
[Testing Guidelines](testing-guidelines.md).

Keep each pull request focused. Describe changes to public contracts,
instrument-safety behavior, or support metadata explicitly; do not bundle an
unrelated refactor into a hardware, validation, or documentation change.

## Development Setup

Work from the repository root. The root `README.md` is the source for the
current installation and test commands. For the reproducible development
environment, use:

```powershell
uv venv .venv
uv sync --all-extras --locked --link-mode=copy
```

The root `pyproject.toml` is the single source of truth for Python
compatibility, dependencies, build metadata, package version, and console
entry points. Do not add component-local distribution metadata.

Run focused no-hardware tests for the affected component first, then run the
full no-hardware suite when practical. The root README documents the supported
commands and the repository-local `.tmp_tests` fallback for Windows temporary
directory permission issues.

## Architecture and Ownership

Meters Tool is one distribution with three independent import packages:

* `meters_tool_core` owns instrument, VISA/SCPI, logging, trigger, and runtime
  behavior.
* `meters_tool_cli` owns the command-line adapter and depends on Core.
* `meters_tool_webui` owns the WebUI adapter and depends on Core.

Core must not import CLI or WebUI. CLI must not import WebUI. Adapter UI state
is not a safety boundary: Core enforces the product support gate for CLI,
WebUI, and direct Core starts.

## Testing Expectations

Every pull request needs relevant no-hardware validation: focused Core, CLI,
or WebUI tests; documentation or layout tests when applicable; and the full
suite when practical. Tests should protect public contracts, component
ownership, safety boundaries, stable schemas and endpoints, and private-info
boundaries rather than incidental prose or layout details.

Real-instrument validation is required when a change affects a new model,
measurement capability, trigger workflow, SCPI behavior, VISA/backend behavior,
live transport scope, instrument setup, acquisition, trigger wait, timeout,
cleanup or release behavior, or promotion of a pending live scope. It is not
normally required for documentation-only changes, hardware-independent
refactors, or tests that can fully use simulators or fake instruments.

## Real-Instrument Validation

Live validation is explicit opt-in. Do not scan, infer, or guess a real
resource for unattended tests. Use an operator-provided resource and the
maintained wrapper, which selects target-aware cases, keeps runs bounded, and
writes reviewable artifacts:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\scripts\live-cli-check.ps1 `
  -Target "<SUPPORTED_TARGET>" `
  -Connection "<usb|lan>" `
  -Resource "<EXPLICIT_VISA_RESOURCE>" `
  -Suite "<SUITE>"
```

Use `-PlanOnly` first to inspect the plan without opening VISA. A live run
requires interactive confirmation. Where an optional backend is in scope, pass
`-VisaLibrary "@py"`; the wrapper records the selected backend in its report.
Do not place a real VISA resource, complete serial number, private or
link-local lab address, or personal filesystem path in a commit, issue, or
public artifact.

### New Models and Capabilities

Every new `InstrumentProfile` must explicitly declare a unique stable
`model_id` in lowercase hyphenated form, following the current format such as
`keysight-34461a` or `keysight-34460a`. Keep the canonical instrument `model`
token separate, and do not generate the model ID at runtime from vendor or
display text. Keep the ID unique across the registry and prevent cross-profile
collisions among canonical models, model IDs, and aliases.

Add registry consistency, lookup, and normalization tests for every profile
identity change. Preserve canonical requested-model output: requested-model
normalization returns `model`, while stable-ID normalization returns
`model_id`. Keep the maintained validation/release wrapper target inventory
aligned exactly with Core model IDs and cover that equality in tests.

Adding a model ID registers stable Core identity only. It does not make the
model Product-open, introduce `candidate`, `catalog_only`, `de_scoped`, or
`product_active` lifecycle state, or change Product/Validation policy modes.
Live support remains governed separately by exact workflow, connection,
measurement, and trigger-mode support metadata plus evidence-backed promotion.

When the maintained wrapper already supports a target, suite, or case,
contributors must use it for repeatable validation and formal pull-request
artifacts. For a new model, capability, workflow, or validation case, the usual
order is:

1. Implement the model/profile capability, SCPI path, hard limits, and request
   validation.
2. Register the measurement or trigger-mode feature as `feature_pending` in
   every exact transport/backend connection scope intended for validation.
3. Add simulator or fake-instrument no-hardware coverage, including policy
   inventory consistency and fail-closed missing-metadata cases.
4. Use the hidden validation mode or maintained wrapper with an explicit
   resource and bounded counts/timeouts. Extend the wrapper only when a small,
   repeatable case fits its current architecture.
5. Preserve and attach the complete commands, stdout/stderr, JSON/JSONL, CSV,
   report, errors, partial results, and cleanup artifacts.
6. Obtain maintainer review of the implementation and exact-scope evidence.
7. Promote the exact feature metadata and public documentation later, as an
   explicit reviewed decision. Passing evidence does not promote it
   automatically.

#### Support-Policy Granularity

Meters support policy is intentionally workflow-centric. Do not copy a
command-centric support matrix from another instrument project merely for
structural consistency.

The current independently promotable live workflow is
`start-trigger-record`. Its policy is evaluated by exact detected model,
transport, backend, measurement, and trigger mode. Internal acquisition phases
such as setup, initiate, wait, fetch, buffer drain, stop, cleanup, release, and
their low-level SCPI operations remain implementation details of that complete
workflow.

When contributing a new measurement or trigger capability to an existing
workflow:

* register the stable categorical feature as `feature_pending` in every exact
  connection scope intended for validation;
* preserve request validation, profile limits, simulator or fake-instrument
  coverage, cleanup, and release behavior;
* validate the complete workflow rather than claiming support from an isolated
  setup or query command; and
* promote only the exact reviewed feature and connection metadata.

When contributing another independently callable live workflow:

1. Define a separate workflow-level support policy.
2. Identify only the stable categorical features that require independent
   hardware evidence.
3. Register exact model, transport, backend, and pending feature scopes.
4. Add fail-closed metadata consistency and runtime lookup tests.
5. Add bounded maintained-wrapper cases and reviewable artifacts.
6. Promote the workflow or individual features only through a later explicit
   metadata and documentation decision.

Do not register low-level setup, query, fetch, stop, cleanup, or release
operations as separate Product capabilities unless they become independently
callable public workflows with their own stable contract and evidence boundary.

Missing feature metadata is not `feature_pending`. A contributor must add an
explicit pending entry for each profile-supported measurement and trigger mode
in every intended exact connection scope. Runtime lookup fails closed when an
entry is missing even if consistency tests were not run.

The wrapper is a validation harness, not a general product interface. It may
use the hidden CLI option
`--validation-allow-pending-live-support` for known pending live scopes. This
is an internal contributor/validation-harness option, deliberately absent from
normal CLI help; it is not a general `--force` switch. It does not bypass model
or profile recognition, hard profile limits, IDN checks, request validation,
unsupported workflows, buffer limits, current-terminal safety restrictions,
trigger safety rules, missing support metadata, or cleanup and release
behavior. It permits only explicitly registered `transport_pending`
connections and `feature_pending` measurement/trigger-mode entries. Do not use
it in root README examples or normal CLI guidance.

When adding a new model, workflow, capability, or validation case that the
wrapper does not support yet, an advanced contributor may invoke the hidden
CLI mode directly for bounded bootstrap validation only after:

* Core recognizes the model/profile;
* capability definitions and hard limits are implemented;
* request validation is in place;
* the exact transport/backend scope exists with `transport_pending` when the
  connection itself is pending;
* each required measurement and trigger-mode entry exists with
  `feature_pending`; and
* simulator or fake-instrument coverage has been added.

The direct bootstrap command is shaped like this:

```powershell
.\.venv\Scripts\python.exe -m meters_tool_cli `
  start-trigger-record `
  --validation-allow-pending-live-support `
  --resource "<EXPLICIT_VISA_RESOURCE>" `
  --model "<EXPECTED_MODEL>" `
  --measurement "<MEASUREMENT>" `
  --trigger-mode "<MODE>" `
  --max-samples "<BOUNDED_COUNT>" `
  --timeout-ms "<BOUNDED_TIMEOUT_MS>" `
  --csv "<ARTIFACT_PATH>" `
  --status-format jsonl
```

Use an explicit operator-provided VISA resource, bounded sample or trigger and
sample counts, and a bounded timeout where applicable. Write JSONL status and
CSV output to dedicated artifact paths. Preserve the exact command, stdout,
stderr, JSON/JSONL, CSV, exit code, errors, timeouts, partial results, and the
cleanup/release result.

This direct CLI path is contributor-only bootstrap validation for a new target
or case that the maintained wrapper does not support yet. Do not use it when an
equivalent wrapper target and case already exist. A contribution should then
extend `scripts/live-cli-check.ps1` with a repeatable target, suite, or case
when appropriate and use the maintained wrapper to produce the formal
pull-request validation artifacts. Direct bootstrap validation does not make a
scope publicly supported.

## Live-Validation Pull Requests

When live behavior is in scope, attach reviewable validation evidence rather
than only reporting success in prose. Include:

* repository commit SHA, package version, and relevant PR revision;
* detected manufacturer/model from `*IDN?`, firmware when available, and the
  expected-model guard (redact complete serial numbers);
* connection type and VISA resource type, plus system VISA or an explicit
  backend, without private connection details;
* exact wrapper invocation, target, connection, suite, selected cases, backend,
  and whether the result was plan-only or live;
* wrapper `report.json`, `summary.md`, generated JSON/JSONL logs, CSV output
  where acquisition ran, SCPI diagnostics where generated, and relevant
  stdout/stderr; and
* exit codes, captured row counts, errors or failures, skipped cases, partial
  output, and cleanup/release results.

Report failures as evidence too. Preserve failed cases, non-zero exits, SCPI
errors, timeouts, cleanup warnings, and partial CSV output after redacting
private identifiers.

Passing artifacts are candidate evidence only. They do not automatically
promote product support, and the hidden validation mode does not update public
support metadata. Promotion requires maintainer review followed by an explicit
`transport_pending` or `feature_pending` metadata and public-documentation
decision for the exact transport/backend scope. Normal CLI, WebUI, and direct
Core starts remain product-gated until that work is accepted.

## Safety and Privacy

Instrument-affecting changes need explicit review before changing SCPI
behavior, VISA timeout, trigger wait strategy, instrument setup, current
terminal behavior, range behavior, cleanup, or release/local behavior. Preserve
the documented worker and cleanup safety boundaries unless the requested change
specifically authorizes them.

Keep live runs bounded and explicitly opted in. Prefer simulator or fake-
instrument tests for command generation, validation, trigger routing, and error
paths. Do not commit generated binary validation artifacts; attach them through
the pull-request process when review needs them.

## Pull Request Checklist

- [ ] Scope is focused and unrelated refactors are excluded.
- [ ] Relevant no-hardware tests were added or updated, and focused tests pass.
- [ ] The full no-hardware suite was run, or the reason it was not run is documented.
- [ ] Public contracts and safety behavior are unchanged, or the change is documented.
- [ ] No real VISA resource, complete serial number, private lab address, or personal path was committed.
- [ ] Live validation is attached when the change affects live behavior.
- [ ] Existing wrapper targets and cases were used where available.
- [ ] New model or workflow contributions extend the maintained wrapper when repeatable validation is appropriate.
- [ ] Direct hidden CLI validation was used only as bounded bootstrap validation for a target or case not yet supported by the wrapper.
- [ ] Live artifacts identify revision, model, transport, backend, suite/cases, results, errors, and cleanup.
- [ ] Passing validation is not described as automatic support promotion.
- [ ] English documentation is updated where required; localized documentation is a follow-up unless explicitly synchronized.
