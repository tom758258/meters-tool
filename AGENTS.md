# Agent Instructions

These instructions define long-term, repository-specific boundaries for agents
working on Meters Tool. Global agent rules already cover communication,
planning, simple and surgical changes, and text-file hygiene.

## 1. Project Context

- Read the affected code and the relevant documentation before changing
  behavior. Use the root `README.md` and `pyproject.toml` when the task concerns
  installation, packaging, entry points, dependencies, or repository layout.
- Read the relevant files in `docs/contracts/` before changing CLI/WebUI
  adapter behavior, worker or subprocess orchestration, JSON/JSONL schemas, or
  HTTP control/status contracts.
- Preserve machine-mode stdout as structured JSON or JSONL only. Human-readable
  diagnostics belong in text mode or stderr; do not emit plain-text lifecycle
  output on machine-mode stdout.
- Get user confirmation before changing contract-defined queue admission or
  rejection semantics, worker lifecycle or HTTP control behavior, process exit
  meanings, run correlation, or artifact path, privacy, redaction, publication,
  or ownership rules.
- Read `docs/webui/web-ui-change-rules.md` before changing WebUI static files or
  in-app UI behavior.

## 2. Distribution And Import Boundaries

- The root `pyproject.toml` is the single distribution metadata boundary for
  `meters-tool`. Do not recreate component-local distributions or introduce a
  `meters_tool.*` namespace without explicit user approval.
- Get user confirmation before changing public packaging boundaries: package
  name or version, dependencies or optional dependency groups, console scripts
  or entry points, build system, or Core/CLI/WebUI component ownership. Tool
  configuration such as pytest, ruff, or mypy may be changed when the requested
  task clearly includes it.
- Preserve the import packages `meters_tool_core`, `meters_tool_cli`, and
  `meters_tool_webui`.
- Core must not import CLI or WebUI. CLI and WebUI may depend on Core, but must
  not depend on each other.
- Keep `desktop/` as a thin Node/Electron shell, not a Python namespace or
  import package. It must reuse the existing WebUI static application and must
  not own or copy Core, instrument, acquisition, or cleanup behavior.
- Keep the Desktop renderer sandboxed without Node or Electron APIs. Do not
  add a preload bridge unless a future approved requirement needs one.

## 3. Multi-Vendor Extension Boundary

- Keep the product identity and shared architecture vendor-neutral.
  Implementation details and user documentation may remain vendor- or
  model-specific where accurate. Validation evidence may also remain vendor-
  or model-specific, but belongs in private or separately shared review
  artifacts, not tracked public documentation.
- For future brands or models, keep capability, identification, validation,
  support-policy, and instrument-command differences primarily in Core. Keep
  detected manufacturer/model identity, canonical model tokens, stable model
  IDs, and aliases distinct; do not infer vendor or support identity by
  splitting or formatting a model ID.
- CLI and WebUI must not copy or reimplement brand/model capabilities, safety
  limits, identification rules, or instrument-command branches. They must use
  Core profile, capability, validation, and support-policy results. Pure
  presentation may be derived from Core metadata.
- Apply fail-closed behavior to normal product live paths. Unknown,
  unidentified, mismatched, unsupported, or unvalidated instruments and
  connection scopes must not run through normal CLI, WebUI, or direct Core
  starts. Maintained validation harnesses may exercise only explicitly
  registered pending scopes under the documented validation policy; this does
  not promote product support.
- These rules constrain future changes. Do not pre-build abstractions for an
  unsupported second vendor or refactor reasonable current model-specific code
  without a concrete requirement.

## 4. Instrument Safety

- Treat changes that can affect a live instrument as high risk. Get user
  confirmation before changing instrument command behavior, VISA timeouts,
  trigger or wait strategies, measurement safety settings, current range or
  terminal behavior, or stop/release/local behavior.
- Preserve the current stop design: `engine.stop()` only sets stop state and
  stop events; VISA I/O belongs on the worker or cleanup path.
- Preserve the cleanup order unless the task explicitly changes it: wait for
  worker, `release_to_local`, close, cleanup release, then stop the HTTP server.
- A hardware-trigger timeout is a normal protective re-arm condition, not an
  acquisition error. Do not count it as `errors` unless explicitly changing
  that contract.
- Keep concrete SCPI/driver commands and query/wait semantics, including
  `READ?`, `FETC?`, and `*OPC?` behavior, in Core, contracts, or supported-model
  documentation. Do not change or generalize them without explicit approval
  and model-appropriate real-instrument validation.
- Keep VISA resource strings configurable. Never commit real resource strings,
  instrument serial numbers, or private lab addresses.

## 5. Testing And Validation

- Follow [Testing Guidelines](docs/testing-guidelines.md). Default tests must
  run without hardware; use simulators or fake instruments for command,
  validation, trigger-routing, and error-path coverage.
- Prioritize tests that protect important system behavior, public contracts,
  cross-component integration, and safety boundaries. Test each contract
  primarily at its owning layer; avoid redundant cross-layer coverage unless
  needed to verify actual integration behavior.
- Do not automatically add permanent regression tests for every minor bug fix.
  Prefer improving or consolidating existing coverage. Avoid tests coupled to
  private implementation details, source text, incidental execution order, or
  non-contractual wording unless they protect an explicit contract or safety
  requirement. Keep test complexity and maintenance cost proportional to risk.
- Run pytest from the repository root. Run the narrowest relevant checks first,
  then broader no-hardware tests when practical.
- Use `.tmp_tests/` for intentional test and validation artifacts.
- Real-instrument validation must be explicit, opt-in, bounded, and use a VISA
  resource supplied by the user. Never infer, scan for, or guess a resource for
  unattended live validation. Do not describe dry-run, simulator, mocked, or
  plan-only results as real-instrument validation.
- If the full test suite is blocked by environment permissions, report the
  limitation and the focused checks that ran. Live validation is not a
  substitute and should run only when live behavior is in scope and approved.
- Report every failed, skipped, blocked, or unexecuted verification step.

## 6. Documentation Boundary

- Keep tracked documentation durable, public, and free of temporary planning,
  transient validation, review, or promotion status, private operator context,
  and run-specific validation results, records, evidence, or artifacts.
- Keep `USER_GUIDE.md` files operator-facing. Keep setup, build, maintainer,
  validation workflow and requirements, and detailed engineering material in
  `README.md` or focused contributor documentation. Include in `USER_GUIDE.md`
  only the minimum information required for normal user operation.
- English documentation is the default. Modify localized documentation only
  when the task explicitly includes it. Canonical Help content is maintained
  in Markdown; when canonical Help Markdown changes, regenerate the
  corresponding tracked runtime Help with the maintained generator. Never
  hand-edit generated Help HTML or recreate removed legacy README / USER_GUIDE
  HTML mirrors.
- Do not place personal filesystem paths, real VISA resources, instrument
  serial numbers, private lab addresses, or link-local/private network
  addresses in tracked public documentation.
- Operator-facing and product-support documentation must not include internal
  phase names, candidate evidence, unperformed validation, review or promotion
  status or plans, or temporary laboratory-specific context.
