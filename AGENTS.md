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

## 3. Multi-Vendor Extension Boundary

- Keep the product identity and shared architecture vendor-neutral. Current
  Keysight 34460A/34461A implementation, validation evidence, and user
  documentation may remain model-specific where accurate.
- For future brands or models, keep capability, identification, validation,
  support-policy, and instrument-command differences primarily in Core.
- CLI and WebUI must not copy or reimplement brand/model capabilities, safety
  limits, identification rules, or instrument-command branches. They must use
  Core profile, capability, validation, and support-policy results. Pure
  presentation may be derived from Core metadata.
- Apply fail-closed behavior to live hardware paths. Unknown, unidentified,
  mismatched, unsupported, or unvalidated instruments and connection scopes
  must not run live. Dry-run and simulator paths may use an explicitly selected
  registered profile as allowed by the existing contracts.
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
  documentation. Do not change or generalize them without model-appropriate
  validation and explicit approval.
- Keep VISA resource strings configurable. Never commit real resource strings,
  instrument serial numbers, or private lab addresses.

## 5. Testing And Validation

- Follow [Testing Guidelines](docs/testing-guidelines.md). Default tests must
  run without hardware; use simulators or fake instruments for command,
  validation, trigger-routing, and error-path coverage.
- Run pytest from the repository root. Run the narrowest relevant checks first,
  then broader no-hardware tests when practical.
- Use `.tmp_tests/` for intentional test and validation artifacts.
- Real-instrument validation must be explicit, opt-in, bounded, and use a VISA
  resource supplied by the user. Never infer, scan for, or guess a resource for
  unattended live validation.
- If the full test suite is blocked by environment permissions, report the
  limitation and the focused checks that ran. Live validation is not a
  substitute and should run only when live behavior is in scope and approved.
- Report every failed, skipped, blocked, or unexecuted verification step.

## 6. Documentation Boundary

- Keep tracked documentation durable, public, and free of temporary planning,
  transient status, private operator context, and hardware-specific validation
  artifacts.
- Keep `USER_GUIDE.md` files operator-facing. Keep setup, build, maintainer,
  validation, and detailed engineering material in `README.md` or focused
  contributor documentation unless it is required for user operation.
- English documentation is the default. Modify localized documentation only
  when the task explicitly includes it. If a modified localized Markdown file
  already has a corresponding HTML mirror, update that mirror in the same
  change.
- Do not place personal filesystem paths, real VISA resources, instrument
  serial numbers, private lab addresses, or link-local/private network
  addresses in tracked public documentation.
