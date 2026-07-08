# Agent Instructions

These instructions guide coding agents working in this repository. They are
long-term project rules, not a project status log. Global agent rules cover
general communication, planning, simplicity, and surgical-edit discipline; keep
this file focused on Meters Tool-specific boundaries.

## 1. Project Context To Read

- Read the root `README.md`, root `pyproject.toml`, and relevant package-local
  code and docs under `docs/core`, `docs/cli`, or `docs/webui` before
  implementing or modifying features.
- Read the root contracts in `docs/contracts/` before changing CLI/WebUI
  adapter behavior, worker behavior, subprocess orchestration, JSON/JSONL
  schemas, or HTTP control/status contracts.
- Read `docs/webui/web-ui-change-rules.md` before changing WebUI UI/static
  files or in-app UI behavior.
- Keep temporary AI planning notes, validation records, hardware-specific
  operator context, and transient project status out of tracked public
  documentation.

## 2. Text File Hygiene

- Save edited Markdown, plain-text, JSON, YAML, TOML, Python, HTML, CSS, and
  JavaScript files as UTF-8 without BOM.
- Preserve each file's existing line-ending style unless the task explicitly
  requires normalization.
- Do not use Windows PowerShell 5.1 `Set-Content -Encoding UTF8` or
  `Out-File -Encoding utf8` for final writes, because they can write a UTF-8
  BOM.
- If PowerShell 5.1 must write final text, use
  `[System.IO.File]::WriteAllText(..., (New-Object System.Text.UTF8Encoding($false)))`.
  In PowerShell 7+, `Set-Content -Encoding utf8` is acceptable.
- After rewriting files or editing non-ASCII text, verify the first three bytes
  are not `EF BB BF`, check for mojibake, and inspect `git diff` for
  unintended line-ending churn.

## 3. Package Metadata Boundary

- The root `pyproject.toml` is the single distribution metadata boundary for
  `meters-tool`.
- Do not recreate legacy component-local `packages/*/pyproject.toml` metadata
  or split Core, CLI, and WebUI back into separate distributions without
  explicit user approval.
- Before modifying `pyproject.toml`, stop and ask the user. Clearly state
  whether the change affects package name, package version, package
  description, dependencies or optional dependency groups, console scripts or
  entry points, build system, pytest/ruff/mypy/tool configuration, or
  Core/CLI/WebUI component ownership.
- Do not rename the distribution, add or remove console scripts, or change
  dependency relationships as part of unrelated Core, CLI, WebUI, test, or
  documentation work.
- Preserve the current import boundaries: `meters_tool_core`,
  `meters_tool_cli`, and `meters_tool_webui`.

## 4. Monorepo Structure and Import Boundaries

This repository is organized as a single-distribution monorepo for
`meters-tool` under the root `src/` directory:

- `src/meters_tool_core`: Core instrument, VISA/SCPI, logging, trigger, and
  runtime layer.
- `src/meters_tool_cli`: Command line interface adapter.
- `src/meters_tool_webui`: WebUI adapter, launcher, and static UI.

- Never let `meters_tool_core` import from `meters_tool_cli` or
  `meters_tool_webui`.
- Never let `meters_tool_cli` import from `meters_tool_webui`.
- Never let `meters_tool_webui` import from `meters_tool_cli`.
- CLI and WebUI may depend on Core through the existing
  `meters_tool_core` import package.
- CLI commands are invoked via `meters-tool` or
  `python -m meters_tool_cli`.
- WebUI commands are invoked via `meters-tool-webui` or
  `meters-tool-webui-launcher`.

## 5. Instrument Safety Rules

- This project controls a Keysight 34461A through VISA/SCPI. Treat
  instrument-affecting changes as high risk.
- Get user confirmation before changing SCPI behavior, VISA timeout, trigger
  wait strategy, `TRIG:DEL`, `NPLC`, Auto Zero, Auto Range, VM Comp, DCV Input
  Z, AC bandwidth, current terminal behavior, or stop/release/local behavior.
- Preserve the current stop design: `engine.stop()` only sets stop state and
  stop events; VISA I/O belongs on the worker/cleanup path.
- Preserve the current cleanup order unless explicitly changing it: wait for
  worker, `release_to_local`, close, cleanup release, stop HTTP server.
- Hardware trigger timeout is a normal protective re-arm condition, not an
  error. Do not count it as `errors` unless the requested behavior changes.
- Hardware-triggered reads use `FETC?` after the trigger adapter arms and
  completes measurement. Software-triggered reads use `READ?`.
- Avoid high-risk query polling conflicts; do not introduce repeated `*OPC?`
  polling without explicit approval.
- Keep resource strings configurable. Do not hard-code real VISA addresses in
  committed code, tests, examples, or public docs.
- Prefer no-hardware simulator or fake-instrument tests for command generation,
  validation, trigger routing, and error paths before using real hardware.

## 6. Testing Rules

- Follow the contributor-facing [Testing Guidelines](docs/testing-guidelines.md):
  tests should protect public contracts, instrument safety boundaries, package
  ownership, stable schemas, stable endpoints, and private-info boundaries.
- Do not add overly precise prose, UI implementation, CSS, JavaScript
  helper-name, list-order, or generated-count assertions unless the checked
  detail is a public contract or safety/privacy boundary and the test makes
  that reason clear.
- Run pytest from the repository root.
- Default tests must run without hardware.
- Hardware or live-instrument validation must be explicit, opt-in, and use a
  user-provided VISA resource. Do not infer, scan, or guess a real resource for
  unattended live runs.
- Run the narrowest relevant tests first, then broader tests when practical.
- Use `.tmp_tests/` for intentional test or validation artifacts. Do not use
  the repository-local private notes directory as a pytest basetemp or
  test-artifact output directory.
- Use the root `README.md` Test section and relevant package README for current
  test commands. Choose the equivalent Python entry point for the active
  platform and shell, such as Windows `.venv\Scripts\python.exe`, POSIX
  `.venv/bin/python`, or `uv run` when the environment is managed by uv.
- Do not maintain shell-specific test command inventories in this file.

- Full test runs may hit local Windows temp or pytest cache permission
  warnings. Report that clearly and rely on focused tests plus real instrument
  validation when full tests are blocked by environment permissions.
- Do not hide failed or skipped verification. State exactly what ran and what
  did not.

## 7. Documentation Boundary

- Keep long-term agent rules in this file.
- Keep tracked public docs limited to README, changelog, architecture,
  contracts, integration guides, user guides, supported models, testing
  guidelines, and change rules.
- Keep `USER_GUIDE.md` files operator/user-facing. Avoid source-checkout,
  virtualenv, build, validation, or maintainer workflow details there unless
  explicitly needed for the user-facing task.
- Keep `README.md` files available for engineering setup, build, validation,
  detailed reference, automation, and maintainer boundaries.
- Default documentation edits should update English `.md` source files only.
- Do not update Traditional Chinese or localized docs, including
  `README.zh-TW.md`, unless explicitly requested.
- If localized docs exist and English docs change, mention the possible
  follow-up instead of auto-syncing them.
- Generated or presentation-oriented documentation HTML may be updated only
  when the task explicitly concerns published docs or documentation
  presentation.
- Do not update product WebUI HTML, CSS, JavaScript, static assets, or in-app
  UI copy as part of ordinary documentation work unless explicitly requested or
  required by a user-facing UI change.
- Keep current planning, package status, validation records, and
  hardware-specific operator context outside tracked public docs.
- Do not add personal filesystem paths, real VISA resources, instrument serial
  numbers, or link-local/private lab IP addresses to tracked docs.
- Do not duplicate large status sections here.
