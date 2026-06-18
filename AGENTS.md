# Agent Instructions

These instructions guide coding agents working in this repository. They are long-term working rules, not a project status log. Keep tracked public documentation limited to durable README, changelog, architecture, contract, integration, user-guide, supported-model, and change-rule content. Do not publish personal paths, real instrument identifiers, local network addresses, or transient project status in tracked docs.

## 1. Think Before Coding

- State assumptions before changing behavior.
- Ask when requirements are ambiguous, especially for instrument behavior or user-facing workflows.
- Surface tradeoffs instead of silently choosing when multiple valid interpretations exist.
- Push back on risky or overbroad changes.

## 2. Keep Changes Simple

- Implement the minimum code needed for the requested behavior.
- Do not add speculative features, generic frameworks, or one-use abstractions.
- Do not add configurability unless the request or current task context requires it.
- If a change becomes large, reassess whether a smaller fix satisfies the goal.

## 3. Make Surgical Edits

- Touch only files required by the task.
- Match the existing style and structure.
- Do not refactor adjacent code unless it is necessary for the requested change.
- Remove only unused imports, variables, or helpers created by your own changes.
- Mention unrelated dead code or cleanup opportunities; do not delete them unless asked.

## 4. Define Success Criteria

- Convert each task into verifiable checks before implementation.
- For bug fixes, prefer a test or focused reproduction that fails before the fix and passes after it.
- For refactors, verify behavior before and after where practical.
- For multi-step work, keep the plan short and tie every step to a concrete check.

## 5. Package Metadata Boundary

- The root `pyproject.toml` is the single distribution metadata boundary for `keysight-logger`.
- Do not recreate `packages/*/pyproject.toml` or split Core, CLI, and WebUI back into separate distributions without explicit user approval.
- Before modifying `pyproject.toml`, stop and ask the user. Clearly state whether the change affects package name, package version, package description, dependencies or optional dependency groups, console scripts or entry points, build system, pytest/ruff/mypy/tool configuration, or Core/CLI/WebUI component ownership.
- Do not rename the distribution, add or remove console scripts, or change dependency relationships as part of unrelated Core, CLI, WebUI, test, or documentation work.
- Preserve the current import boundaries: `keysight_logger_core`, `keysight_logger_cli`, and `keysight_logger_webui`.

## 6. Project-Specific Safety Rules

- This project controls a Keysight 34461A through VISA/SCPI. Treat instrument-affecting changes as high risk.
- Get user confirmation before changing SCPI behavior, VISA timeout, trigger wait strategy, `TRIG:DEL`, `NPLC`, Auto Zero, Auto Range, VM Comp, or stop/release/local behavior.
- Preserve the current stop design: `engine.stop()` only sets stop state and stop events; VISA I/O belongs on the worker/cleanup path.
- Preserve the current cleanup order unless explicitly changing it: wait for worker, `release_to_local`, close, cleanup release, stop HTTP server.
- Hardware trigger timeout is a normal protective re-arm condition, not an error. Do not count it as `errors` unless the requested behavior changes.
- Hardware-triggered reads use `FETC?` after the trigger adapter arms and completes measurement. Software-triggered reads use `READ?`.
- Avoid high-risk query polling conflicts; do not introduce repeated `*OPC?` polling without explicit approval.

## 7. Testing Rules

- Follow the contributor-facing [Testing Guidelines](docs/testing-guidelines.md): tests should protect public contracts, instrument safety boundaries, package ownership, stable schemas, stable endpoints, and private-info boundaries.
- Do not add overly precise prose, UI implementation, CSS, JavaScript helper-name, list-order, or generated-count assertions unless the checked detail is a public contract or safety/privacy boundary and the test makes that reason clear.
- Run the narrowest relevant tests first, then broader tests when practical.
- Common commands:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/core -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests/cli -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests/webui -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

- Full test runs may hit local Windows temp or pytest cache permission warnings. Report that clearly and rely on focused tests plus real instrument validation when full tests are blocked by environment permissions.
- Do not hide failed or skipped verification. State exactly what ran and what did not.

## 8. Documentation Boundary

- Keep long-term agent rules in this file.
- Keep tracked public docs limited to README, changelog, architecture, contracts, integration guides, user guides, supported models, and change rules.
- Keep current planning, package status, validation records, and hardware-specific operator context outside tracked public docs.
- Do not add personal filesystem paths, real VISA resources, instrument serial numbers, or link-local/private lab IP addresses to tracked docs.
- Do not duplicate large status sections here.
